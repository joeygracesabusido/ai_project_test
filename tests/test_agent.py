import pytest
import json
from unittest.mock import patch, MagicMock
from agent import run_query

class TestAgentEngine:
    def test_run_query_returns_report_structure(self):
        """Verify run_query returns expected dict keys."""
        with patch("agent.get_db") as mock_db, \
             patch("agent.introspect_schema") as mock_schema, \
             patch("agent.select_collection") as mock_select, \
             patch("agent.generate_pipeline") as mock_gen, \
             patch("agent.execute_pipeline") as mock_exec, \
             patch("agent.interpret_results") as mock_interp:

            mock_db.return_value = MagicMock()
            mock_schema.return_value = {
                "database": "test_db",
                "collections": {"users": {"name": "str"}},
                "collection_names": ["users"],
            }
            mock_select.return_value = "users"
            mock_gen.return_value = [{"$limit": 5}]
            mock_exec.return_value = [{"name": "Alice"}, {"name": "Bob"}]
            mock_interp.return_value = "Found 2 users."

            result = run_query("show users")
            assert isinstance(result, dict)
            assert "report" in result
            assert "raw" in result
            assert "collection" in result
            assert "pipeline" in result
            assert result["report"] == "Found 2 users."
            assert len(result["raw"]) == 2
            assert result["collection"] == "users"

    def test_run_query_handles_missing_collection(self):
        """Verify error handling for non-existent target collection."""
        with patch("agent.get_db") as mock_db, \
             patch("agent.introspect_schema") as mock_schema:

            mock_db.return_value = MagicMock()
            mock_schema.return_value = {
                "database": "test_db",
                "collections": {"users": {"name": "str"}},
                "collection_names": ["users"],
            }

            result = run_query("show users", target_collection="nonexistent")
            assert "not found" in result["report"]
            assert result["collection"] is None
            assert result["raw"] == []

    def test_run_query_handles_empty_db(self):
        """Verify graceful handling when database has no collections."""
        with patch("agent.get_db") as mock_db, \
             patch("agent.introspect_schema") as mock_schema:

            mock_db.return_value = MagicMock()
            mock_schema.return_value = {
                "database": "empty_db",
                "collections": {},
                "collection_names": [],
            }

            result = run_query("anything")
            assert "No collections" in result["report"]

    def test_run_query_retries_on_bad_pipeline(self):
        """Verify retry logic when pipeline generation fails."""
        with patch("agent.get_db") as mock_db, \
             patch("agent.introspect_schema") as mock_schema, \
             patch("agent.select_collection") as mock_select, \
             patch("agent.generate_pipeline") as mock_gen, \
             patch("agent.execute_pipeline") as mock_exec, \
             patch("agent.interpret_results") as mock_interp:

            mock_db.return_value = MagicMock()
            mock_schema.return_value = {
                "database": "test_db",
                "collections": {"users": {"name": "str"}},
                "collection_names": ["users"],
            }
            mock_select.return_value = "users"
            # Fail twice then succeed
            mock_gen.side_effect = [
                json.JSONDecodeError("bad json", "", 0),
                json.JSONDecodeError("bad json", "", 0),
                [{"$limit": 5}],
            ]
            mock_exec.return_value = [{"name": "Alice"}]
            mock_interp.return_value = "Found 1 user."

            result = run_query("show users")
            assert mock_gen.call_count == 3
            assert result["report"] == "Found 1 user."
