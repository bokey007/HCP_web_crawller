"""SQLAlchemy ORM models for persistent storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class ProcessingJob(Base):
    """Represents a batch upload / processing job."""

    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    total_records = Column(Integer, nullable=False, default=0)
    processed_records = Column(Integer, nullable=False, default=0)
    found_count = Column(Integer, nullable=False, default=0)
    not_found_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="job_status"),
        nullable=False,
        default="PENDING",
    )
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class HCPRecord(Base):
    """Stores both the input HCP data and the extracted results."""

    __tablename__ = "hcp_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), nullable=False, index=True)

    # ── Input fields (from Excel) ────────────────────────────────────
    project_id = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False, default="")
    middle_name = Column(String(100), nullable=False, default="")
    last_name = Column(String(100), nullable=False, default="")
    address_line_1 = Column(String(255), nullable=False, default="")
    address_line_2 = Column(String(255), nullable=False, default="")
    city = Column(String(100), nullable=False, default="")
    state_code = Column(String(10), nullable=False, default="")

    # ── Extracted fields ─────────────────────────────────────────────
    phone = Column(String(50), nullable=False, default="")
    email = Column(String(255), nullable=False, default="")
    full_address = Column(Text, nullable=False, default="")
    source_urls_json = Column(Text, nullable=False, default="[]")
    confidence_score = Column(Float, nullable=False, default=0.0)
    match_status = Column(
        Enum("FOUND", "PARTIAL", "NOT_FOUND", "PROCESSING", "ERROR", name="match_status"),
        nullable=False,
        default="PROCESSING",
    )
    verification_reasoning = Column(Text, nullable=False, default="")

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Helpers ──────────────────────────────────────────────────────

    @property
    def source_urls(self) -> list[str]:
        """Deserialise the JSON-stored source URLs."""
        try:
            return json.loads(self.source_urls_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @source_urls.setter
    def source_urls(self, urls: list[str]) -> None:
        self.source_urls_json = json.dumps(urls)
