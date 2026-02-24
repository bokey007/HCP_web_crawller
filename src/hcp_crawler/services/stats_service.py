"""Impact metrics and statistics computation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hcp_crawler.config import get_settings
from hcp_crawler.models.database import HCPRecord, ProcessingJob
from hcp_crawler.models.schemas import AgentStats


async def compute_stats(db: AsyncSession) -> AgentStats:
    """Compute aggregate agent statistics from all processing jobs."""
    settings = get_settings()

    # Count by match status
    found = await db.scalar(
        select(func.count()).where(HCPRecord.match_status == "FOUND")
    ) or 0

    partial = await db.scalar(
        select(func.count()).where(HCPRecord.match_status == "PARTIAL")
    ) or 0

    not_found = await db.scalar(
        select(func.count()).where(HCPRecord.match_status == "NOT_FOUND")
    ) or 0

    total_processed = await db.scalar(
        select(func.count()).where(
            HCPRecord.match_status.in_(["FOUND", "PARTIAL", "NOT_FOUND", "ERROR"])
        )
    ) or 0

    total_jobs = await db.scalar(select(func.count()).select_from(ProcessingJob)) or 0

    # Compute impact metrics
    success_rate = (found / total_processed * 100) if total_processed > 0 else 0.0
    hours_saved = total_processed * settings.manual_minutes_per_record / 60
    dollars_saved = hours_saved * settings.hourly_rate_usd

    return AgentStats(
        total_records_processed=total_processed,
        hcps_found=found,
        hcps_partial=partial,
        hcps_not_found=not_found,
        success_rate_pct=round(success_rate, 1),
        hours_saved=round(hours_saved, 1),
        dollars_saved=round(dollars_saved, 2),
        total_jobs=total_jobs,
    )
