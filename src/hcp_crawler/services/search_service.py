"""Search query construction and site prioritisation logic."""

from __future__ import annotations

from hcp_crawler.models.schemas import HCPInput
from hcp_crawler.utils.logger import get_logger

logger = get_logger(__name__)

# ── Priority site groups (searched in order) ──────────────────────────
PRIORITY_SITES: list[list[str]] = [
    # Tier 1: HCP-specific directories
    ["doximity.com", "npiprofile.com"],
    # Tier 2: Government & academic
    [".gov", ".edu"],
    # Tier 3: Hospital / institution / general (no site: filter)
]

# ── Social media blocklist — excluded from results ────────────────────
SOCIAL_MEDIA_BLOCKLIST: set[str] = {
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "reddit.com",
    "pinterest.com",
    "snapchat.com",
    "threads.net",
    "tumblr.com",
    "youtube.com",
}


def build_base_query(hcp: HCPInput) -> str:
    """
    Build a human-readable search query from HCP fields.

    Combines: first name, middle name, last name, city, state code.
    Adds "doctor" and "healthcare provider" keywords for better relevance.
    """
    parts: list[str] = []
    if hcp.first_name:
        parts.append(hcp.first_name)
    if hcp.middle_name:
        parts.append(hcp.middle_name)
    if hcp.last_name:
        parts.append(hcp.last_name)

    # Location context
    if hcp.city:
        parts.append(hcp.city)
    if hcp.state_code:
        parts.append(hcp.state_code)

    # Role keywords
    parts.append("doctor healthcare provider")

    query = " ".join(parts)
    logger.debug("base_query_built", project_id=hcp.project_id, query=query)
    return query


def build_search_queries(hcp: HCPInput) -> list[str]:
    """
    Build a list of prioritised search queries for an HCP record.

    Returns queries in order: site-specific (tier 1 → tier 2) → general.
    """
    base = build_base_query(hcp)
    queries: list[str] = []

    # Tier 1 & 2: site-specific searches
    for site_group in PRIORITY_SITES:
        if not site_group:
            continue
        # Combine sites with OR for a single query
        site_filter = " OR ".join(f"site:{s}" for s in site_group)
        queries.append(f"{base} ({site_filter})")

    # Tier 3: general search (no site filter)
    queries.append(f"{base} contact information")

    logger.info(
        "search_queries_built",
        project_id=hcp.project_id,
        num_queries=len(queries),
    )
    return queries


def is_blocked_url(url: str) -> bool:
    """Return True if the URL belongs to a blocked social media domain."""
    url_lower = url.lower()
    return any(blocked in url_lower for blocked in SOCIAL_MEDIA_BLOCKLIST)


def rank_url(url: str) -> int:
    """
    Return a priority rank for a URL (lower = better).

    0 = HCP-specific sites (doximity, npiprofile)
    1 = Government (.gov)
    2 = Education (.edu)
    3 = Organisation (.org)
    4 = Other trusted
    5 = General
    """
    url_lower = url.lower()
    if "doximity.com" in url_lower or "npiprofile.com" in url_lower:
        return 0
    if ".gov" in url_lower:
        return 1
    if ".edu" in url_lower:
        return 2
    if ".org" in url_lower:
        return 3
    if any(kw in url_lower for kw in ["hospital", "health", "medical", "clinic"]):
        return 4
    return 5
