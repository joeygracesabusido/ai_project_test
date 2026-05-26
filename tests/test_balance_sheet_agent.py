import pytest
from unittest.mock import patch, MagicMock
from pymongo.errors import ConnectionFailure
from balance_sheet_agent import (
    check_debits_equal_credits, check_assets_equals_liabilities_equity,
    find_unbalanced_entries, check_balance,
    _debits_equal_credits_pipeline, _assets_liabilities_equity_pipeline,
    _unbalanced_entries_pipeline
)


class TestBalanceSheetAgent:
    def test_check_debits_equal_credits_balanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"totalDebit": 1000.0, "totalCredit": 1000.0, "variance": 0.0, "balanced": True}]
            result = check_debits_equal_credits()
            assert "PASS" in result["report"] or "balanced" in result["report"]

    def test_check_debits_equal_credits_unbalanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [{"totalDebit": 1000.0, "totalCredit": 900.0, "variance": 100.0, "balanced": False}]
            result = check_debits_equal_credits()
            assert "FAIL" in result["report"] or "variance" in result["report"]

    def test_check_debits_equal_credits_empty(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = check_debits_equal_credits()
            assert "No journal line entries" in result["report"]

    def test_assets_equals_liabilities_equity_balanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"accountType": "ASSET", "netBalance": 50000.0},
                {"accountType": "LIABILITY", "netBalance": 30000.0},
                {"accountType": "EQUITY", "netBalance": 20000.0}
            ]
            result = check_assets_equals_liabilities_equity()
            assert "PASS" in result["report"]

    def test_assets_equals_liabilities_equity_unbalanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"accountType": "ASSET", "netBalance": 50000.0},
                {"accountType": "LIABILITY", "netBalance": 20000.0},
                {"accountType": "EQUITY", "netBalance": 20000.0}
            ]
            result = check_assets_equals_liabilities_equity()
            assert "FAIL" in result["report"] or "gap" in result["report"]

    def test_assets_equals_liabilities_equity_empty(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = check_assets_equals_liabilities_equity()
            assert "No account balances" in result["report"]

    def test_find_unbalanced_entries_returns_list(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"entryId": "e1", "date": "2026-01-15", "description": "Test", "reference": "JV-001", "totalDebit": 100.0, "totalCredit": 90.0, "variance": 10.0}
            ]
            result = find_unbalanced_entries()
            assert "raw" in result
            assert len(result["raw"]) > 0

    def test_find_unbalanced_entries_all_balanced(self):
        with patch("balance_sheet_agent.get_db") as mock_db, \
             patch("balance_sheet_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = find_unbalanced_entries()
            assert "All journal entries are balanced" in result["report"]

    def test_check_balance_returns_all_checks(self):
        with patch("balance_sheet_agent.check_debits_equal_credits") as mock_debits, \
             patch("balance_sheet_agent.check_assets_equals_liabilities_equity") as mock_ale, \
             patch("balance_sheet_agent.find_unbalanced_entries") as mock_unbalanced:
            mock_debits.return_value = {"report": "PASS", "raw": []}
            mock_ale.return_value = {"report": "PASS", "raw": []}
            mock_unbalanced.return_value = {"report": "All balanced", "raw": []}
            result = check_balance()
            assert "DEBITS = CREDITS" in result["report"]
            assert "A = L + E" in result["report"]
            assert "raw" in result
            assert "debits_equal_credits" in result["raw"]
            assert "assets_equals_liabilities_equity" in result["raw"]
            assert "unbalanced_entries" in result["raw"]

    def test_check_debits_equal_credits_db_error(self):
        with patch("balance_sheet_agent.get_db") as mock_db:
            mock_db.side_effect = ValueError("DATABASE_URL not set in .env")
            result = check_debits_equal_credits()
            assert "Database error" in result["report"]
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result

    def test_assets_equals_liabilities_equity_db_error(self):
        with patch("balance_sheet_agent.get_db") as mock_db:
            mock_db.side_effect = ConnectionFailure("Cannot connect to MongoDB")
            result = check_assets_equals_liabilities_equity()
            assert "Database error" in result["report"]
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result
