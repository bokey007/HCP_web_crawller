"""LLM-powered contact extraction and identity verification."""

from __future__ import annotations

import json
from typing import Any

from hcp_crawler.config import get_settings
from hcp_crawler.models.schemas import ExtractedContact, HCPInput
from hcp_crawler.utils.logger import get_logger

logger = get_logger(__name__)

# ── System prompts ────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """\
You are an expert data extraction assistant specialising in healthcare provider (HCP) contact information.

Given the raw text from a web page, extract the following contact details for the specified healthcare provider:
- phone: Phone number (with area code if available)
- email: Email address
- full_address: Complete mailing/practice address

Rules:
1. Only extract information that clearly belongs to the specified person.
2. If a field is not found, return an empty string for that field.
3. Return ONLY valid JSON with the keys: phone, email, full_address.
4. Do NOT make up or guess information.
"""

VERIFICATION_SYSTEM_PROMPT = """\
You are an identity verification expert for healthcare providers.

Given an HCP's known details (name, city, state) and extracted contact information from a web page, determine whether the extracted information belongs to the same person.

Consider:
1. Name match (exact or close variations)
2. Location match (city, state)
3. Professional context (healthcare/medical field)
4. Any other identifying details on the page

Return ONLY valid JSON with:
- confidence: integer 0-100 (0 = definitely not the same person, 100 = definitely the same)
- reasoning: brief explanation of your assessment
"""


class LLMService:
    """Handles LLM calls for extraction and verification using OpenAI or Azure OpenAI."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = self._create_client()

    def _create_client(self):
        """Create the appropriate OpenAI client based on config."""
        if self._settings.llm_provider == "azure_openai":
            from openai import AsyncAzureOpenAI

            return AsyncAzureOpenAI(
                azure_endpoint=self._settings.azure_openai_endpoint,
                api_key=self._settings.azure_openai_api_key,
                api_version=self._settings.azure_openai_api_version,
            )
        else:
            from openai import AsyncOpenAI

            return AsyncOpenAI(api_key=self._settings.openai_api_key)

    @property
    def _model(self) -> str:
        if self._settings.llm_provider == "azure_openai":
            return self._settings.azure_openai_deployment
        return self._settings.openai_model

    async def extract_contact(
        self, page_text: str, hcp: HCPInput, source_url: str
    ) -> ExtractedContact:
        """
        Extract phone, email, and address from page text for a given HCP.
        """
        name_parts = [hcp.first_name, hcp.middle_name, hcp.last_name]
        full_name = " ".join(p for p in name_parts if p)

        user_message = (
            f"Healthcare Provider: {full_name}\n"
            f"Location: {hcp.city}, {hcp.state_code}\n\n"
            f"Web page text:\n{page_text[:6000]}"
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result = self._parse_json_response(response.choices[0].message.content)
            return ExtractedContact(
                phone=result.get("phone", ""),
                email=result.get("email", ""),
                full_address=result.get("full_address", ""),
                source_url=source_url,
            )

        except Exception as exc:
            logger.error(
                "llm_extraction_failed",
                hcp_project_id=hcp.project_id,
                error=str(exc),
            )
            return ExtractedContact(source_url=source_url)

    async def verify_identity(
        self, hcp: HCPInput, extracted: ExtractedContact, page_text: str
    ) -> tuple[float, str]:
        """
        Verify whether the extracted contact belongs to the input HCP.

        Returns (confidence_score, reasoning).
        """
        name_parts = [hcp.first_name, hcp.middle_name, hcp.last_name]
        full_name = " ".join(p for p in name_parts if p)

        user_message = (
            f"Known HCP Details:\n"
            f"  Name: {full_name}\n"
            f"  City: {hcp.city}\n"
            f"  State: {hcp.state_code}\n"
            f"  Address: {hcp.address_line_1} {hcp.address_line_2}\n\n"
            f"Extracted Contact:\n"
            f"  Phone: {extracted.phone}\n"
            f"  Email: {extracted.email}\n"
            f"  Address: {extracted.full_address}\n"
            f"  Source: {extracted.source_url}\n\n"
            f"Page context (first 3000 chars):\n{page_text[:3000]}"
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": VERIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                max_tokens=300,
                response_format={"type": "json_object"},
            )

            result = self._parse_json_response(response.choices[0].message.content)
            confidence = float(result.get("confidence", 0))
            reasoning = result.get("reasoning", "")

            logger.info(
                "identity_verified",
                hcp_project_id=hcp.project_id,
                confidence=confidence,
            )
            return confidence, reasoning

        except Exception as exc:
            logger.error(
                "llm_verification_failed",
                hcp_project_id=hcp.project_id,
                error=str(exc),
            )
            return 0.0, f"Verification failed: {exc}"

    @staticmethod
    def _parse_json_response(content: str | None) -> dict[str, Any]:
        """Safely parse JSON from LLM response."""
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```" in content:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
            return {}


# Module-level singleton
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Return the module-level LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
