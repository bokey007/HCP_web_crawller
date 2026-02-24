"""Tests for the LLM service (mocked)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hcp_crawler.models.schemas import ExtractedContact, HCPInput
from hcp_crawler.services.llm_service import LLMService


@pytest.fixture
def mock_settings():
    with patch("hcp_crawler.services.llm_service.get_settings") as mock:
        settings = MagicMock()
        settings.llm_provider = "openai"
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4o-mini"
        mock.return_value = settings
        yield settings


@pytest.fixture
def hcp():
    return HCPInput(
        project_id="P001",
        first_name="John",
        middle_name="M",
        last_name="Smith",
        city="Boston",
        state_code="MA",
    )


class TestLLMServiceParsing:
    """Test JSON response parsing."""

    def test_parse_valid_json(self):
        content = '{"phone": "555-1234", "email": "dr@example.com", "full_address": "123 Main St"}'
        result = LLMService._parse_json_response(content)
        assert result["phone"] == "555-1234"
        assert result["email"] == "dr@example.com"

    def test_parse_empty_content(self):
        assert LLMService._parse_json_response(None) == {}
        assert LLMService._parse_json_response("") == {}

    def test_parse_json_in_code_block(self):
        content = '```json\n{"phone": "555-1234"}\n```'
        result = LLMService._parse_json_response(content)
        assert result["phone"] == "555-1234"

    def test_parse_invalid_json(self):
        content = "This is not JSON"
        result = LLMService._parse_json_response(content)
        assert result == {}


class TestLLMExtraction:
    """Test contact extraction with mocked LLM calls."""

    @pytest.mark.asyncio
    async def test_extract_contact_success(self, hcp, mock_settings):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "phone": "617-555-0123",
                        "email": "john.smith@hospital.org",
                        "full_address": "123 Main St, Boston, MA 02101",
                    })
                )
            )
        ]

        with patch("hcp_crawler.services.llm_service.LLMService._create_client") as mock_client:
            client = AsyncMock()
            client.chat.completions.create.return_value = mock_response
            mock_client.return_value = client

            service = LLMService()
            service._client = client

            result = await service.extract_contact(
                page_text="Dr. John M Smith, Boston MA, Phone: 617-555-0123",
                hcp=hcp,
                source_url="https://example.com/dr-smith",
            )

            assert result.phone == "617-555-0123"
            assert result.email == "john.smith@hospital.org"
            assert result.source_url == "https://example.com/dr-smith"


class TestLLMVerification:
    """Test identity verification with mocked LLM calls."""

    @pytest.mark.asyncio
    async def test_verify_identity_high_confidence(self, hcp, mock_settings):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "confidence": 92,
                        "reasoning": "Name and location match exactly.",
                    })
                )
            )
        ]

        with patch("hcp_crawler.services.llm_service.LLMService._create_client") as mock_client:
            client = AsyncMock()
            client.chat.completions.create.return_value = mock_response
            mock_client.return_value = client

            service = LLMService()
            service._client = client

            contact = ExtractedContact(
                phone="617-555-0123",
                email="john@hospital.org",
                full_address="123 Main St, Boston, MA",
                source_url="https://example.com",
            )

            score, reasoning = await service.verify_identity(
                hcp=hcp, extracted=contact, page_text="Dr. John M Smith practices in Boston, MA."
            )

            assert score == 92
            assert "match" in reasoning.lower()
