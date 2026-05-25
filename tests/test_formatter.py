import pytest
from formatter import print_report, print_error, print_info
from rich.console import Console

class TestFormatter:
    def test_print_report_runs_without_error(self):
        """Smoke test — print_report should not raise."""
        print_report("Test summary", [{"name": "Alice", "age": 30}], show_raw=True)

    def test_print_report_empty_raw(self):
        """Should handle empty raw data gracefully."""
        print_report("No data found", [], show_raw=True)

    def test_print_report_no_raw_flag(self):
        """Should work with show_raw=False (default)."""
        print_report("Just a summary", [{"name": "Alice"}])

    def test_print_error_runs_without_error(self):
        """Smoke test — print_error should not raise."""
        print_error("Something went wrong")

    def test_print_info_runs_without_error(self):
        """Smoke test — print_info should not raise."""
        print_info("Processing complete")
