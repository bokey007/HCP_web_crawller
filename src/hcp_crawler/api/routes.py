"""FastAPI REST endpoints for the HCP Web Crawler."""

from __future__ import annotations

import asyncio
import json
import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from hcp_crawler.db.session import get_db
from hcp_crawler.models.database import HCPRecord, ProcessingJob
from hcp_crawler.models.schemas import (
    AgentStats,
    HCPResult,
    JobCreate,
    JobProgress,
    JobStatus,
    JobSummary,
)
from hcp_crawler.services.agent.graph import get_compiled_graph
from hcp_crawler.services.agent.state import HCPAgentState
from hcp_crawler.services.excel_service import parse_excel
from hcp_crawler.services.stats_service import compute_stats
from hcp_crawler.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["HCP Crawler"])


# ── Background processing ────────────────────────────────────────────

async def _process_job(job_id: str, records: list, db_factory) -> None:
    """Background task: process all HCP records for a job."""
    graph = get_compiled_graph()

    async with db_factory() as db:
        try:
            await db.execute(
                update(ProcessingJob)
                .where(ProcessingJob.job_id == job_id)
                .values(status="PROCESSING")
            )
            await db.commit()

            found = 0
            not_found = 0
            errors = 0

            for idx, hcp_input in enumerate(records):
                try:
                    # Human-like delay between HCP records to avoid Google rate-limiting
                    if idx > 0:
                        import random as _rnd
                        delay = _rnd.uniform(5.0, 12.0)
                        logger.info("inter_record_delay", job_id=job_id, record=idx + 1, delay_s=round(delay, 1))
                        await asyncio.sleep(delay)

                    # Run the LangGraph agent
                    initial_state: HCPAgentState = {"hcp_input": hcp_input}
                    result = await graph.ainvoke(initial_state)

                    # Update the HCP record with results
                    match_status = result.get("match_status", "NOT_FOUND")
                    best_contact = result.get("best_contact")

                    update_values = {
                        "match_status": match_status,
                        "confidence_score": result.get("confidence_score", 0.0),
                        "verification_reasoning": result.get("verification_reasoning", ""),
                        "source_urls_json": json.dumps(result.get("source_urls", [])),
                    }

                    if best_contact:
                        update_values.update({
                            "phone": best_contact.phone,
                            "email": best_contact.email,
                            "full_address": best_contact.full_address,
                        })

                    await db.execute(
                        update(HCPRecord)
                        .where(
                            HCPRecord.job_id == job_id,
                            HCPRecord.project_id == hcp_input.project_id,
                        )
                        .values(**update_values)
                    )

                    if match_status == "FOUND":
                        found += 1
                    elif match_status == "PARTIAL":
                        found += 1  # Count partial as found
                    else:
                        not_found += 1

                except Exception as exc:
                    logger.error(
                        "record_processing_error",
                        job_id=job_id,
                        project_id=hcp_input.project_id,
                        error=str(exc),
                    )
                    errors += 1
                    await db.execute(
                        update(HCPRecord)
                        .where(
                            HCPRecord.job_id == job_id,
                            HCPRecord.project_id == hcp_input.project_id,
                        )
                        .values(match_status="ERROR", verification_reasoning=str(exc))
                    )

                # Update job progress
                await db.execute(
                    update(ProcessingJob)
                    .where(ProcessingJob.job_id == job_id)
                    .values(
                        processed_records=idx + 1,
                        found_count=found,
                        not_found_count=not_found,
                        error_count=errors,
                    )
                )
                await db.commit()

            # Mark job complete
            await db.execute(
                update(ProcessingJob)
                .where(ProcessingJob.job_id == job_id)
                .values(status="COMPLETED")
            )
            await db.commit()
            logger.info("job_completed", job_id=job_id, found=found, not_found=not_found)

        except Exception as exc:
            logger.error("job_failed", job_id=job_id, error=str(exc))
            await db.execute(
                update(ProcessingJob)
                .where(ProcessingJob.job_id == job_id)
                .values(status="FAILED")
            )
            await db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/upload", response_model=JobCreate)
async def upload_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an Excel file and start processing HCP records."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are accepted.")

    contents = await file.read()

    try:
        hcp_records = parse_excel(contents, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not hcp_records:
        raise HTTPException(status_code=400, detail="No valid HCP records found in the file.")

    # Create job
    job_id = str(uuid.uuid4())
    job = ProcessingJob(
        job_id=job_id,
        filename=file.filename,
        total_records=len(hcp_records),
        status="PENDING",
    )
    db.add(job)

    # Create HCP records in DB
    for hcp in hcp_records:
        record = HCPRecord(
            job_id=job_id,
            project_id=hcp.project_id,
            first_name=hcp.first_name,
            middle_name=hcp.middle_name,
            last_name=hcp.last_name,
            address_line_1=hcp.address_line_1,
            address_line_2=hcp.address_line_2,
            city=hcp.city,
            state_code=hcp.state_code,
        )
        db.add(record)

    await db.commit()

    # Start background processing
    from hcp_crawler.db.session import get_session_factory

    asyncio.create_task(_process_job(job_id, hcp_records, get_session_factory()))

    logger.info("job_created", job_id=job_id, total_records=len(hcp_records))
    return JobCreate(
        job_id=job_id,
        total_records=len(hcp_records),
        status=JobStatus.PENDING,
    )


@router.get("/jobs/{job_id}", response_model=JobProgress)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get the current status and progress of a processing job."""
    result = await db.execute(
        select(ProcessingJob).where(ProcessingJob.job_id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    progress = (
        (job.processed_records / job.total_records * 100)
        if job.total_records > 0
        else 0.0
    )

    return JobProgress(
        job_id=job.job_id,
        status=JobStatus(job.status),
        total_records=job.total_records,
        processed_records=job.processed_records,
        found_count=job.found_count,
        not_found_count=job.not_found_count,
        error_count=job.error_count,
        progress_pct=round(progress, 1),
    )


@router.get("/jobs", response_model=list[JobSummary])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    """Get a list of all jobs ordered by created_at descending."""
    result = await db.execute(
        select(ProcessingJob)
        .order_by(ProcessingJob.created_at.desc())
        .limit(100)
    )
    jobs = result.scalars().all()
    
    return [
        JobSummary(
            id=job.id,
            job_id=job.job_id,
            filename=job.filename,
            status=JobStatus(job.status),
            total_records=job.total_records,
            processed_records=job.processed_records,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
    ]


@router.get("/jobs/{job_id}/results", response_model=list[HCPResult])
async def get_job_results(
    job_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get processed results for a job (paginated)."""
    result = await db.execute(
        select(HCPRecord)
        .where(HCPRecord.job_id == job_id)
        .offset(skip)
        .limit(limit)
        .order_by(HCPRecord.id)
    )
    records = result.scalars().all()

    return [
        HCPResult(
            id=r.id,
            job_id=r.job_id,
            project_id=r.project_id,
            first_name=r.first_name,
            middle_name=r.middle_name,
            last_name=r.last_name,
            city=r.city,
            state_code=r.state_code,
            phone=r.phone,
            email=r.email,
            full_address=r.full_address,
            source_urls=r.source_urls,
            confidence_score=r.confidence_score,
            match_status=r.match_status,
            verification_reasoning=r.verification_reasoning,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]


@router.get("/jobs/{job_id}/export")
async def export_results(job_id: str, db: AsyncSession = Depends(get_db)):
    """Export job results as an Excel file."""
    result = await db.execute(
        select(HCPRecord)
        .where(HCPRecord.job_id == job_id)
        .order_by(HCPRecord.id)
    )
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail="No results found for this job.")

    import xlsxwriter

    output = BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = wb.add_worksheet("HCP Results")

    # Headers
    headers = [
        "PROJECT_ID", "FIRST_NAME", "MIDDLE_NAME", "LAST_NAME",
        "CITY", "STATE_CODE", "PHONE", "EMAIL", "FULL_ADDRESS",
        "CONFIDENCE_SCORE", "MATCH_STATUS", "SOURCE_URLS",
        "VERIFICATION_REASONING",
    ]

    header_fmt = wb.add_format({"bold": True, "bg_color": "#1a1a2e", "font_color": "#ffffff"})
    for col, header in enumerate(headers):
        ws.write(0, col, header, header_fmt)

    # Data rows
    for row_idx, r in enumerate(records, start=1):
        ws.write(row_idx, 0, r.project_id)
        ws.write(row_idx, 1, r.first_name)
        ws.write(row_idx, 2, r.middle_name)
        ws.write(row_idx, 3, r.last_name)
        ws.write(row_idx, 4, r.city)
        ws.write(row_idx, 5, r.state_code)
        ws.write(row_idx, 6, r.phone)
        ws.write(row_idx, 7, r.email)
        ws.write(row_idx, 8, r.full_address)
        ws.write(row_idx, 9, r.confidence_score)
        ws.write(row_idx, 10, r.match_status)
        ws.write(row_idx, 11, ", ".join(r.source_urls))
        ws.write(row_idx, 12, r.verification_reasoning)

    ws.autofit()
    wb.close()
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=hcp_results_{job_id[:8]}.xlsx"},
    )


@router.get("/stats", response_model=AgentStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate agent statistics and impact metrics."""
    return await compute_stats(db)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "hcp-web-crawler"}
