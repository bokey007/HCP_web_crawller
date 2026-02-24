"""LangGraph state machine definition for the HCP search agent."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from hcp_crawler.services.agent.nodes import (
    build_queries,
    google_search,
    llm_extract,
    llm_verify,
    prepare_retry,
    scrape_pages,
    should_retry,
)
from hcp_crawler.services.agent.state import HCPAgentState


def build_agent_graph() -> StateGraph:
    """
    Construct the LangGraph state machine for processing a single HCP record.

    Flow:
        build_queries → google_search → scrape_pages → llm_extract → llm_verify
                                ↑                                         │
                                └──── prepare_retry ◄── (retry?) ─────────┘
                                                             │
                                                          (done) → END
    """
    graph = StateGraph(HCPAgentState)

    # ── Add nodes ─────────────────────────────────────────────────────
    graph.add_node("build_queries", build_queries)
    graph.add_node("google_search", google_search)
    graph.add_node("scrape_pages", scrape_pages)
    graph.add_node("llm_extract", llm_extract)
    graph.add_node("llm_verify", llm_verify)
    graph.add_node("prepare_retry", prepare_retry)

    # ── Define edges ──────────────────────────────────────────────────
    graph.set_entry_point("build_queries")
    graph.add_edge("build_queries", "google_search")
    graph.add_edge("google_search", "scrape_pages")
    graph.add_edge("scrape_pages", "llm_extract")
    graph.add_edge("llm_extract", "llm_verify")

    # Conditional: retry or finish
    graph.add_conditional_edges(
        "llm_verify",
        should_retry,
        {
            "retry": "prepare_retry",
            "done": END,
        },
    )
    graph.add_edge("prepare_retry", "google_search")

    return graph


def get_compiled_graph():
    """Build and compile the agent graph (ready to invoke)."""
    graph = build_agent_graph()
    return graph.compile()
