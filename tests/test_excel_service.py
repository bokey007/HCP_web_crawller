"""Tests for the Excel ingestion service."""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from hcp_crawler.services.excel_service import parse_excel


def _create_excel(rows: list[list], headers: list[str] | None = None) -> bytes:
    """Helper: create an in-memory Excel file from rows."""
    wb = Workbook()
    ws = wb.active
    if headers:
        ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestParseExcel:
    """Tests for parse_excel function."""

    def test_valid_file_with_all_columns(self):
        headers = [
            "PROJECT_ID", "FIRST_NAME", "MIDDLE_NAME", "LAST_NAME",
            "ADDRESS_LINE_1", "ADDRESS_LINE_2", "CITY", "STATE_CODE",
        ]
        rows = [
            ["P001", "John", "M", "Smith", "123 Main St", "", "Boston", "MA"],
            ["P002", "Jane", "", "Doe", "456 Oak Ave", "Apt 2", "Chicago", "IL"],
        ]
        data = _create_excel(rows, headers)
        records = parse_excel(data)
        assert len(records) == 2
        assert records[0].project_id == "P001"
        assert records[0].first_name == "John"
        assert records[0].city == "Boston"
        assert records[1].project_id == "P002"
        assert records[1].middle_name == ""

    def test_missing_project_id_column(self):
        headers = ["FIRST_NAME", "LAST_NAME"]
        rows = [["John", "Smith"]]
        data = _create_excel(rows, headers)
        with pytest.raises(ValueError, match="Missing required column 'PROJECT_ID'"):
            parse_excel(data)

    def test_empty_file(self):
        wb = Workbook()
        buf = io.BytesIO()
        wb.save(buf)
        with pytest.raises(ValueError, match="at least one data row"):
            parse_excel(buf.getvalue())

    def test_skips_rows_without_project_id(self):
        headers = ["PROJECT_ID", "FIRST_NAME", "LAST_NAME"]
        rows = [
            ["P001", "John", "Smith"],
            ["", "Jane", "Doe"],  # Empty PROJECT_ID
            [None, "Bob", "Brown"],  # None PROJECT_ID
            ["P004", "Alice", "Lee"],
        ]
        data = _create_excel(rows, headers)
        records = parse_excel(data)
        assert len(records) == 2
        assert records[0].project_id == "P001"
        assert records[1].project_id == "P004"

    def test_case_insensitive_headers(self):
        headers = ["project_id", "First_Name", "LAST_NAME", "city"]
        rows = [["P001", "John", "Smith", "Boston"]]
        data = _create_excel(rows, headers)
        records = parse_excel(data)
        assert len(records) == 1
        assert records[0].first_name == "John"
        assert records[0].city == "Boston"

    def test_partial_columns(self):
        headers = ["PROJECT_ID", "FIRST_NAME", "LAST_NAME"]
        rows = [["P001", "John", "Smith"]]
        data = _create_excel(rows, headers)
        records = parse_excel(data)
        assert len(records) == 1
        assert records[0].city == ""
        assert records[0].middle_name == ""
