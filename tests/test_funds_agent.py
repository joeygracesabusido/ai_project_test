import pytest
from unittest.mock import patch, MagicMock
from pymongo.errors import ConnectionFailure
from funds_agent import (
    get_funds_overview, get_petty_cash_status, get_advance_summary,
    _petty_cash_pipeline, _advance_pipeline, _account_balance_pipeline
)


class TestFundsAgent:
    def test_funds_overview_returns_structure(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.side_effect = [
                [{"name": "Petty Cash 1", "fundAmount": 10000.0, "currentBalance": 5000.0, "utilization": 50.0}],
                [{"employeeName": "Alice", "totalOutstanding": 1500.0, "advanceCount": 2}],
                [{"accountType": "ASSET", "totalDebit": 50000.0, "totalCredit": 10000.0, "netBalance": 40000.0}]
            ]
            result = get_funds_overview()
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result
            assert result["collection"] == "funds"
            assert "petty_cash" in result["raw"]
            assert "advances" in result["raw"]
            assert "account_balances" in result["raw"]

    def test_funds_overview_empty(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.side_effect = [[], [], []]
            result = get_funds_overview()
            assert "No active petty cash funds" in result["report"]
            assert "No active advances" in result["report"]
            assert "No account balances" in result["report"]

    def test_petty_cash_status_returns_structure(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"name": "Office Supplies", "fundAmount": 5000.0, "currentBalance": 2500.0, "utilization": 50.0}
            ]
            result = get_petty_cash_status()
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result
            assert result["collection"] == "petty_cash"
            assert "Office Supplies" in result["report"]

    def test_petty_cash_status_empty(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_petty_cash_status()
            assert "No petty cash funds" in result["report"]

    def test_advance_summary_returns_structure(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"employeeName": "Bob", "totalOutstanding": 3000.0, "advanceCount": 1}
            ]
            result = get_advance_summary()
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result
            assert result["collection"] == "advances"
            assert "Bob" in result["report"]
            assert "Total Outstanding" in result["report"]

    def test_advance_summary_empty(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_advance_summary()
            assert "No active advances found" in result["report"]

    def test_funds_overview_db_error(self):
        with patch("funds_agent.get_db") as mock_db:
            mock_db.side_effect = ValueError("DATABASE_URL not set in .env")
            result = get_funds_overview()
            assert "Database error" in result["report"]
            assert "raw" in result
            assert "collection" in result
            assert result["collection"] == "funds"

    def test_pipeline_structure_valid(self):
        pc_pipeline = _petty_cash_pipeline()
        assert isinstance(pc_pipeline, list)
        assert len(pc_pipeline) > 0
        assert "$match" in pc_pipeline[0]
        assert "$project" in pc_pipeline[1]

        adv_pipeline = _advance_pipeline()
        assert isinstance(adv_pipeline, list)
        assert len(adv_pipeline) > 0
        assert "$match" in adv_pipeline[0]
        assert "$group" in adv_pipeline[1]
        assert "$lookup" in adv_pipeline[2]

        acct_pipeline = _account_balance_pipeline()
        assert isinstance(acct_pipeline, list)
        assert len(acct_pipeline) > 0
        assert "$lookup" in acct_pipeline[0]

    def test_petty_cash_status_with_name_filter(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = [
                {"name": "Office Supplies", "fundAmount": 5000.0, "currentBalance": 2500.0, "utilization": 50.0}
            ]
            result = get_petty_cash_status(name="Office Supplies")
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert result["collection"] == "petty_cash"
            assert "Office Supplies" in result["report"]

    def test_petty_cash_status_name_not_found(self):
        with patch("funds_agent.get_db") as mock_db, \
             patch("funds_agent.execute_pipeline") as mock_exec:
            mock_db.return_value = MagicMock()
            mock_exec.return_value = []
            result = get_petty_cash_status(name="NonExistentFund")
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "not found" in result["report"].lower()
            assert result["raw"] == []

    def test_petty_cash_status_db_error(self):
        with patch("funds_agent.get_db") as mock_db:
            mock_db.side_effect = ValueError("DATABASE_URL not set in .env")
            result = get_petty_cash_status()
            assert "Database error" in result["report"]
            assert "raw" in result
            assert "collection" in result
            assert result["collection"] == "petty_cash"

    def test_advance_summary_db_error(self):
        with patch("funds_agent.get_db") as mock_db:
            mock_db.side_effect = ConnectionFailure("Cannot connect to MongoDB")
            result = get_advance_summary()
            assert "Database error" in result["report"]
            assert "raw" in result
            assert "collection" in result
            assert result["collection"] == "advances"
