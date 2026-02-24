"""LangGraph agent state schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from hcp_crawler.models.schemas import ExtractedContact, HCPInput
from hcp_crawler.services.scraper_service import PageContent, SearchHit


class HCPAgentState(TypedDict, total=False):
    """
    State that flows through the LangGraph HCP search agent.

    Every node reads from and writes to this state dict.
    """
    # Input
    hcp_input: HCPInput

    # Search phase
    search_queries: list[str]
    current_query_idx: int
    search_results: list[SearchHit]

    # Scrape phase
    scraped_pages: list[PageContent]
    current_page_idx: int

    # Extraction phase
    extracted_contacts: list[ExtractedContact]
    best_contact: ExtractedContact | None

    # Verification phase
    confidence_score: float
    verification_reasoning: str

    # Output
    source_urls: list[str]
    match_status: str  # FOUND | PARTIAL | NOT_FOUND
    retry_count: int
    error: str
