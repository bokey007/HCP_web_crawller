"""Application settings loaded from environment variables via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration — values are read from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Provider ──────────────────────────────────────────────────
    llm_provider: Literal["azure_openai", "openai"] = "azure_openai"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-10-21"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./hcp_crawler.db"

    # ── Agent Configuration ───────────────────────────────────────────
    max_concurrent_browsers: int = Field(default=3, ge=1, le=10)
    max_results_per_hcp: int = Field(default=5, ge=1, le=20)
    confidence_threshold: int = Field(default=70, ge=0, le=100)
    search_timeout_seconds: int = Field(default=30, ge=5)
    page_load_timeout_seconds: int = Field(default=15, ge=5)

    # ── Impact Metrics ────────────────────────────────────────────────
    manual_minutes_per_record: int = Field(default=15, ge=1)
    hourly_rate_usd: int = Field(default=50, ge=1)

    # ── Application ──────────────────────────────────────────────────
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:8501"]


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()
