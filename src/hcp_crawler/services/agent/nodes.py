"""LangGraph node functions for the HCP search agent pipeline."""

from __future__ import annotations

from hcp_crawler.config import get_settings
from hcp_crawler.services.agent.state import HCPAgentState
from hcp_crawler.services.llm_service import get_llm_service
from hcp_crawler.services.scraper_service import get_scraper
from hcp_crawler.services.search_service import build_search_queries
from hcp_crawler.utils.logger import get_logger

logger = get_logger(__name__)


async def build_queries(state: HCPAgentState) -> HCPAgentState:
    """Build prioritised search queries from the HCP input."""
    hcp = state["hcp_input"]
    queries = build_search_queries(hcp)

    logger.info(
        "node.build_queries",
        project_id=hcp.project_id,
        num_queries=len(queries),
    )

    return {
        **state,
        "search_queries": queries,
        "current_query_idx": 0,
        "search_results": [],
        "scraped_pages": [],
        "extracted_contacts": [],
        "best_contact": None,
        "confidence_score": 0.0,
        "verification_reasoning": "",
        "source_urls": [],
        "match_status": "NOT_FOUND",
        "retry_count": 0,
        "error": "",
    }


async def google_search(state: HCPAgentState) -> HCPAgentState:
    """Execute the current search query via PyDoll and collect results."""
    queries = state.get("search_queries", [])
    idx = state.get("current_query_idx", 0)
    settings = get_settings()

    if idx >= len(queries):
        logger.info("node.google_search.no_more_queries", project_id=state["hcp_input"].project_id)
        return {**state, "search_results": []}

    query = queries[idx]
    scraper = get_scraper()

    try:
        # Human-like delay between search tiers to avoid Google rate-limiting
        if idx > 0:
            import asyncio as _aio
            import random as _rnd
            delay = _rnd.uniform(3.0, 8.0)
            logger.info("node.google_search.delay", project_id=state["hcp_input"].project_id, delay_s=round(delay, 1))
            await _aio.sleep(delay)

        hits = await scraper.google_search(query, max_results=settings.max_results_per_hcp)
        logger.info(
            "node.google_search.complete",
            project_id=state["hcp_input"].project_id,
            query_idx=idx,
            results=len(hits),
        )
        return {**state, "search_results": hits}
    except Exception as exc:
        logger.error(
            "node.google_search.error",
            project_id=state["hcp_input"].project_id,
            error=str(exc),
        )
        return {**state, "search_results": [], "error": str(exc)}


async def scrape_pages(state: HCPAgentState) -> HCPAgentState:
    """Scrape the top search result pages to extract text content."""
    hits = state.get("search_results", [])
    scraper = get_scraper()
    pages = []

    for hit in hits[:5]:  # Top 5 results
        page = await scraper.scrape_page(hit.url)
        if page.success and page.text:
            pages.append(page)

    logger.info(
        "node.scrape_pages.complete",
        project_id=state["hcp_input"].project_id,
        pages_scraped=len(pages),
    )
    return {**state, "scraped_pages": pages, "current_page_idx": 0}


async def llm_extract(state: HCPAgentState) -> HCPAgentState:
    """Use the LLM to extract contact info from scraped pages."""
    pages = state.get("scraped_pages", [])
    hcp = state["hcp_input"]
    llm = get_llm_service()
    contacts = []

    for page in pages:
        contact = await llm.extract_contact(page.text, hcp, page.url)
        # Only keep contacts that have at least one useful field
        if contact.phone or contact.email or contact.full_address:
            contacts.append(contact)

    logger.info(
        "node.llm_extract.complete",
        project_id=hcp.project_id,
        contacts_found=len(contacts),
    )
    return {**state, "extracted_contacts": contacts}


async def llm_verify(state: HCPAgentState) -> HCPAgentState:
    """Verify identity match for extracted contacts and pick the best one."""
    contacts = state.get("extracted_contacts", [])
    pages = state.get("scraped_pages", [])
    hcp = state["hcp_input"]
    llm = get_llm_service()
    settings = get_settings()

    best_contact = None
    best_score = 0.0
    best_reasoning = ""
    source_urls = []

    # Build a URL → page text map for verification context
    page_texts = {p.url: p.text for p in pages}

    for contact in contacts:
        page_text = page_texts.get(contact.source_url, "")
        score, reasoning = await llm.verify_identity(hcp, contact, page_text)

        if score > best_score:
            best_score = score
            best_contact = contact
            best_reasoning = reasoning

        if score >= settings.confidence_threshold:
            source_urls.append(contact.source_url)

    # Determine match status
    if best_score >= settings.confidence_threshold and best_contact:
        match_status = "FOUND"
        if not best_contact.phone and not best_contact.email:
            match_status = "PARTIAL"
    else:
        match_status = "NOT_FOUND"
        best_contact = None

    logger.info(
        "node.llm_verify.complete",
        project_id=hcp.project_id,
        best_score=best_score,
        match_status=match_status,
    )

    return {
        **state,
        "best_contact": best_contact,
        "confidence_score": best_score,
        "verification_reasoning": best_reasoning,
        "source_urls": source_urls,
        "match_status": match_status,
    }


def should_retry(state: HCPAgentState) -> str:
    """
    Conditional edge: decide whether to retry with next query or finish.

    Returns "retry" to try the next query tier, or "done" to finalise.
    """
    match_status = state.get("match_status", "NOT_FOUND")
    if match_status == "FOUND":
        return "done"

    # Try next query tier
    current_idx = state.get("current_query_idx", 0)
    queries = state.get("search_queries", [])
    retry_count = state.get("retry_count", 0)

    if current_idx + 1 < len(queries) and retry_count < 3:
        return "retry"

    return "done"


async def prepare_retry(state: HCPAgentState) -> HCPAgentState:
    """Advance to the next query tier for retry."""
    return {
        **state,
        "current_query_idx": state.get("current_query_idx", 0) + 1,
        "retry_count": state.get("retry_count", 0) + 1,
        "search_results": [],
        "scraped_pages": [],
        "extracted_contacts": [],
    }
