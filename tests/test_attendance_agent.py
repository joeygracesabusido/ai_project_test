import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from attendance_agent import get_attendance_report, get_attendance_summary, _date_range, _build_attendance_pipeline, _format_attendance_report

class TestAttendanceAgent:
    def test_date_range_today(self):
        start, end = _date_range("today")
        assert start == end

    def test_date_range_week(self):
        start, end = _date_range("week")
        assert start < end

    def test_date_range_month(self):
        start, end = _date_range("month")
        assert start < end

    def test_date_range_custom(self):
        start, end = _date_range("2026-01-01:2026-01-31")
        assert start == "2026-01-01"
        assert end == "2026-01-31"

    def test_date_range_invalid(self):
        with pytest.raises(ValueError, match="Invalid period"):
            _date_range("invalid")

    def test_attendance_report_returns_structure(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"employeeName": "Alice", "date": "2026-05-26", "workHours": 8.0, "status": "ON_TIME", "clockIn": "08:00", "clockOut": "17:00"}
            ]
            result = get_attendance_report("today")
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result
            assert result["collection"] == "timelogs"

    def test_attendance_report_empty(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_attendance_report("today")
            assert "No timelogs" in result["report"]

    def test_attendance_summary_returns_structure(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"_id": "emp1", "fullName": "Alice", "department": "Engineering", "totalWorkHours": 40.0, "totalOtHours": 5.0, "lateDays": 1, "undertimeDays": 0}
            ]
            result = get_attendance_summary("month")
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result

    def test_attendance_report_with_employee_filter(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"employeeName": "Alice", "date": "2026-05-26", "workHours": 8.0, "status": "ON_TIME", "clockIn": "08:00", "clockOut": "17:00"}
            ]
            result = get_attendance_report("today", employee="Alice")
            assert "report" in result
            assert "Alice" in result["report"]

    def test_attendance_report_employee_not_found(self):
        with patch("attendance_agent.get_db") as mock_db, \
             patch("attendance_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_attendance_report("today", employee="Bob")
            assert "Bob" in result["report"]
            assert "not found" in result["report"].lower()

    def test_format_attendance_report_keyerror_safe(self):
        results = [{"employeeName": "Bob"}]
        report = _format_attendance_report(results, "2026-01-01", "2026-01-31")
        assert "Bob" in report

    def test_build_attendance_pipeline_structure(self):
        pipeline = _build_attendance_pipeline("2026-01-01", "2026-01-31")
        assert isinstance(pipeline, list)
        assert len(pipeline) > 0
        assert "$match" in pipeline[0]
        assert "$gte" in pipeline[0]["$match"]["date"]
        assert "$lte" in pipeline[0]["$match"]["date"]
        assert isinstance(pipeline[0]["$match"]["date"]["$gte"], datetime)
        assert isinstance(pipeline[0]["$match"]["date"]["$lte"], datetime)
