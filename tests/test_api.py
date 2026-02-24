"""Tests for the FastAPI endpoints."""

from __future__ import annotations

import io
import os

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook

# Use in-memory SQLite for tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

from hcp_crawler.main import app
from hcp_crawler.db.session import init_db


@pytest.fixture(autouse=True)
async def setup_db():
    """Initialise the DB tables before each test."""
    await init_db()
    yield



@pytest.fixture
def sample_excel():
    """Create a sample Excel file for testing."""
    wb = Workbook()
    ws = wb.active
    ws.append(["PROJECT_ID", "FIRST_NAME", "LAST_NAME", "CITY", "STATE_CODE"])
    ws.append(["P001", "John", "Smith", "Boston", "MA"])
    ws.append(["P002", "Jane", "Doe", "Chicago", "IL"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_check(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"


@pytest.mark.asyncio
class TestUploadEndpoint:
    async def test_upload_invalid_extension(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/upload",
                files={"file": ("test.csv", b"data", "text/csv")},
            )
            assert resp.status_code == 400

    async def test_upload_valid_excel(self, sample_excel):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/upload",
                files={"file": ("test.xlsx", sample_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
            assert data["total_records"] == 2


@pytest.mark.asyncio
class TestStatsEndpoint:
    async def test_get_stats(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "total_records_processed" in data
            assert "hours_saved" in data
            assert "dollars_saved" in data
