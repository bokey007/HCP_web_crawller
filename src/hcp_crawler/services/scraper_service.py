"""PyDoll-based browser automation for Google search and page scraping."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from hcp_crawler.config import get_settings
from hcp_crawler.services.search_service import is_blocked_url, rank_url
from hcp_crawler.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchHit:
    """A single Google search result."""
    url: str
    title: str = ""
    snippet: str = ""
    rank: int = 5


@dataclass
class PageContent:
    """Extracted text content from a web page."""
    url: str
    text: str = ""
    title: str = ""
    success: bool = False


class ScraperService:
    """
    Manages a pool of PyDoll Chrome instances for Google search
    and page content extraction.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_browsers)
        self._search_timeout = settings.search_timeout_seconds
        self._page_timeout = settings.page_load_timeout_seconds

    async def google_search(self, query: str, max_results: int = 10) -> list[SearchHit]:
        """
        Execute a Google search using PyDoll and return parsed results.

        Uses a fresh browser instance per search to avoid session issues.
        """
        async with self._semaphore:
            return await self._do_google_search(query, max_results)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _do_google_search(self, query: str, max_results: int) -> list[SearchHit]:
        """Core search logic with retry."""
        from pydoll.browser.chromium import Chrome
        from pydoll.browser.options import ChromiumOptions

        options = ChromiumOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        hits: list[SearchHit] = []

        try:
            async with Chrome(options=options) as browser:
                tab = await browser.start()

                # Navigate to Google
                await tab.go_to("https://www.google.com")
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Type the search query
                search_box = await tab.find(tag_name="textarea", name="q", timeout=10)
                await search_box.type_text(query, interval=random.uniform(0.03, 0.08))
                await asyncio.sleep(random.uniform(0.3, 0.7))

                # Submit
                from pydoll.constants import Key
                await tab.keyboard.press(Key.ENTER)

                # Wait for results (longer to let Google fully render)
                await asyncio.sleep(random.uniform(3.0, 6.0))

                # Extract results from the page HTML
                page_source = await tab.page_source
                hits = self._parse_google_results(page_source, max_results)

                logger.info(
                    "google_search_complete",
                    query=query[:80],
                    results_found=len(hits),
                )
        except Exception as exc:
            logger.error("google_search_failed", query=query[:80], error=str(exc))
            raise

        return hits

    def _parse_google_results(self, html: str, max_results: int) -> list[SearchHit]:
        """Parse Google search results from raw HTML.
        
        Uses multiple selector strategies to handle Google's
        frequently-changing HTML structure.
        """
        soup = BeautifulSoup(html, "lxml")
        hits: list[SearchHit] = []
        seen_urls: set[str] = set()

        # Strategy 1: Modern Google selectors (MjjYud, g, data-sokoban)
        containers = soup.select("div.MjjYud, div.g, div[data-sokoban-container]")
        
        for g in containers:
            if len(hits) >= max_results:
                break

            # Find the first anchor that has an h3 inside it (the result title link)
            link_tag = None
            for a in g.select("a[href]"):
                href = a.get("href", "")
                if href.startswith("http") and a.select_one("h3"):
                    link_tag = a
                    break

            if not link_tag:
                # Fallback: any anchor with an http href
                link_tag = g.select_one("a[href^='http']")
                if not link_tag:
                    continue

            url = link_tag.get("href", "")
            if not url or not url.startswith("http"):
                continue
            
            # Skip Google internal links, social media, and duplicates
            if "google.com" in url or "google.co" in url:
                continue
            if is_blocked_url(url):
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title_tag = g.select_one("h3")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Try multiple snippet selectors
            snippet = ""
            for sel in ["div.VwiC3b", "span.aCOpRe", "div[data-sncf]", "div[style*='line-clamp']", "span.st"]:
                snippet_tag = g.select_one(sel)
                if snippet_tag:
                    snippet = snippet_tag.get_text(strip=True)
                    break

            hits.append(
                SearchHit(
                    url=url,
                    title=title,
                    snippet=snippet,
                    rank=rank_url(url),
                )
            )
        
        # Strategy 2 (fallback): If Strategy 1 found nothing, try
        # finding any <a> that has an <h3> descendant anywhere in the page
        if not hits:
            logger.info("google_parse_fallback", reason="no results from primary selectors")
            for a in soup.select("a[href^='http']"):
                if len(hits) >= max_results:
                    break
                h3 = a.select_one("h3")
                if not h3:
                    continue
                url = a.get("href", "")
                if "google.com" in url or "google.co" in url:
                    continue
                if is_blocked_url(url) or url in seen_urls:
                    continue
                seen_urls.add(url)
                hits.append(
                    SearchHit(
                        url=url,
                        title=h3.get_text(strip=True),
                        snippet="",
                        rank=rank_url(url),
                    )
                )

        # Sort by rank (trusted sites first)
        hits.sort(key=lambda h: h.rank)
        return hits

    async def scrape_page(self, url: str) -> PageContent:
        """
        Visit a URL using PyDoll and extract the text content.

        Resources (images, CSS, fonts) are blocked for speed.
        """
        async with self._semaphore:
            return await self._do_scrape_page(url)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    async def _do_scrape_page(self, url: str) -> PageContent:
        """Core page scraping with retry and resource blocking."""
        from pydoll.browser.chromium import Chrome
        from pydoll.browser.options import ChromiumOptions
        from pydoll.protocol.fetch.events import FetchEvent, RequestPausedEvent
        from pydoll.protocol.network.types import ErrorReason

        options = ChromiumOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        try:
            async with Chrome(options=options) as browser:
                tab = await browser.start()

                # Block images, stylesheets, fonts for speed
                async def block_heavy_resources(event: RequestPausedEvent):
                    request_id = event["params"]["requestId"]
                    resource_type = event["params"]["resourceType"]
                    if resource_type in ("Image", "Stylesheet", "Font", "Media"):
                        await tab.fail_request(request_id, ErrorReason.BLOCKED_BY_CLIENT)
                    else:
                        await tab.continue_request(request_id)

                await tab.enable_fetch_events()
                await tab.on(FetchEvent.REQUEST_PAUSED, block_heavy_resources)

                # Navigate
                await tab.go_to(url)
                await asyncio.sleep(random.uniform(1.0, 2.5))

                # Extract text
                page_source = await tab.page_source
                title = await tab.title

                soup = BeautifulSoup(page_source, "lxml")

                # Remove scripts and styles
                for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)

                # Truncate to ~8000 chars to stay within LLM context limits
                if len(text) > 8000:
                    text = text[:8000]

                await tab.disable_fetch_events()

                logger.info("page_scraped", url=url[:80], text_length=len(text))
                return PageContent(url=url, text=text, title=title or "", success=True)

        except Exception as exc:
            logger.error("page_scrape_failed", url=url[:80], error=str(exc))
            return PageContent(url=url, text="", success=False)


# Module-level singleton
_scraper: ScraperService | None = None


def get_scraper() -> ScraperService:
    """Return the module-level scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = ScraperService()
    return _scraper
