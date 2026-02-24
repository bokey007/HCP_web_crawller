"""Pydantic request/response schemas for the HCP Web Crawler API."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────

class MatchStatus(str, enum.Enum):
    """Result of identity verification for an HCP record."""
    FOUND = "FOUND"
    PARTIAL = "PARTIAL"
    NOT_FOUND = "NOT_FOUND"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"


class JobStatus(str, enum.Enum):
    """Processing state for a batch upload job."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ── Input ─────────────────────────────────────────────────────────────

class HCPInput(BaseModel):
    """A single HCP row from the uploaded Excel sheet."""
    project_id: str
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state_code: str = ""


# ── Extracted / Output ────────────────────────────────────────────────

class ExtractedContact(BaseModel):
    """Contact details extracted from a web page by the LLM."""
    phone: str = ""
    email: str = ""
    full_address: str = ""
    source_url: str = ""


class HCPResult(BaseModel):
    """Full result for a single HCP record after agent processing."""
    id: int | None = None
    job_id: str = ""
    project_id: str = ""
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    city: str = ""
    state_code: str = ""
    # Extracted
    phone: str = ""
    email: str = ""
    full_address: str = ""
    source_urls: list[str] = Field(default_factory=list)
    confidence_score: float = 0.0
    match_status: MatchStatus = MatchStatus.PROCESSING
    verification_reasoning: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Job ───────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    """Response when a new processing job is created."""
    job_id: str
    total_records: int
    status: JobStatus = JobStatus.PENDING


class JobProgress(BaseModel):
    """Real-time progress update for a job."""
    job_id: str
    status: JobStatus
    total_records: int = 0
    processed_records: int = 0
    found_count: int = 0
    not_found_count: int = 0
    error_count: int = 0
    progress_pct: float = 0.0


class JobSummary(BaseModel):
    """High-level summary of a job for listing."""
    id: int
    job_id: str
    filename: str
    status: JobStatus
    total_records: int
    processed_records: int
    created_at: datetime
    updated_at: datetime

# ── Stats ─────────────────────────────────────────────────────────────

class AgentStats(BaseModel):
    """Aggregated impact metrics across all jobs."""
    total_records_processed: int = 0
    hcps_found: int = 0
    hcps_partial: int = 0
    hcps_not_found: int = 0
    success_rate_pct: float = 0.0
    hours_saved: float = 0.0
    dollars_saved: float = 0.0
    total_jobs: int = 0
