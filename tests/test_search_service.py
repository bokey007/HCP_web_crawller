"""Tests for the search query construction and URL filtering."""

from __future__ import annotations

from hcp_crawler.models.schemas import HCPInput
from hcp_crawler.services.search_service import (
    build_base_query,
    build_search_queries,
    is_blocked_url,
    rank_url,
)


class TestBuildBaseQuery:
    def test_full_fields(self):
        hcp = HCPInput(
            project_id="P001",
            first_name="John",
            middle_name="M",
            last_name="Smith",
            city="Boston",
            state_code="MA",
        )
        query = build_base_query(hcp)
        assert "John" in query
        assert "M" in query
        assert "Smith" in query
        assert "Boston" in query
        assert "MA" in query
        assert "doctor" in query.lower()

    def test_partial_fields(self):
        hcp = HCPInput(project_id="P002", first_name="Jane", last_name="Doe")
        query = build_base_query(hcp)
        assert "Jane" in query
        assert "Doe" in query
        assert "doctor" in query.lower()

    def test_empty_fields(self):
        hcp = HCPInput(project_id="P003")
        query = build_base_query(hcp)
        assert "doctor" in query.lower()


class TestBuildSearchQueries:
    def test_returns_multiple_queries(self):
        hcp = HCPInput(
            project_id="P001", first_name="John", last_name="Smith", city="Boston"
        )
        queries = build_search_queries(hcp)
        assert len(queries) >= 3  # Tier 1, Tier 2, General

    def test_tier1_has_doximity(self):
        hcp = HCPInput(project_id="P001", first_name="John", last_name="Smith")
        queries = build_search_queries(hcp)
        assert any("doximity.com" in q for q in queries)

    def test_tier2_has_gov(self):
        hcp = HCPInput(project_id="P001", first_name="John", last_name="Smith")
        queries = build_search_queries(hcp)
        assert any(".gov" in q for q in queries)


class TestIsBlockedUrl:
    def test_blocks_social_media(self):
        assert is_blocked_url("https://www.facebook.com/dr.smith")
        assert is_blocked_url("https://twitter.com/drsmith")
        assert is_blocked_url("https://www.linkedin.com/in/smith")
        assert is_blocked_url("https://www.instagram.com/drsmith")
        assert is_blocked_url("https://reddit.com/r/medicine")

    def test_allows_trusted_sites(self):
        assert not is_blocked_url("https://www.doximity.com/pub/john-smith")
        assert not is_blocked_url("https://npiprofile.com/npi/1234567890")
        assert not is_blocked_url("https://www.massgeneral.org/doctors/john-smith")
        assert not is_blocked_url("https://health.gov/provider/123")


class TestRankUrl:
    def test_doximity_highest(self):
        assert rank_url("https://www.doximity.com/pub/john-smith") == 0

    def test_gov_second(self):
        assert rank_url("https://health.gov/providers/123") == 1

    def test_edu_third(self):
        assert rank_url("https://www.harvard.edu/faculty/smith") == 2

    def test_org_fourth(self):
        assert rank_url("https://www.hospital.org/staff/smith") == 3

    def test_general_last(self):
        assert rank_url("https://www.randomsite.com/page") == 5
