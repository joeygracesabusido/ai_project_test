import pytest
from agent import run_query
from db import get_db, introspect_schema

class TestIntegration:
    """Integration tests that exercise the full pipeline against real MongoDB."""

    def test_schema_discovers_collections(self):
        """Verify schema introspection discovers real collections."""
        db = get_db()
        schema = introspect_schema(db)
        assert len(schema["collection_names"]) > 0
        print(f"Found collections: {schema['collection_names']}")
        for coll_name, fields in schema["collections"].items():
            assert isinstance(fields, dict)
            print(f"  {coll_name}: {fields}")

    def test_full_query_flow(self):
        """Run a natural language query end-to-end and verify output structure."""
        result = run_query("list all collections in the database")
        assert isinstance(result, dict)
        assert "report" in result
        assert isinstance(result["report"], str)
        assert len(result["report"]) > 0
        assert "collection" in result
        assert "pipeline" in result
        assert "raw" in result

    def test_query_with_collection_filter(self):
        """Running with a specific collection should target that collection."""
        db = get_db()
        schema = introspect_schema(db)
        if not schema["collection_names"]:
            pytest.skip("No collections available")

        collection_name = schema["collection_names"][0]
        result = run_query("show me 5 records", target_collection=collection_name)
        assert result["collection"] == collection_name

    def test_query_nonexistent_collection(self):
        """Asking for a nonexistent collection should return helpful error."""
        result = run_query("anything", target_collection="_nonexistent_collection_xyz_")
        assert "not found" in result["report"].lower()

    def test_execute_pipeline_handles_serialization(self):
        """Verify pipeline execution returns serializable results."""
        db = get_db()
        schema = introspect_schema(db)
        if not schema["collection_names"]:
            pytest.skip("No collections available")

        coll = schema["collection_names"][0]
        results = db[coll].aggregate([{"$limit": 2}])
        for doc in results:
            import json
            # Should serialize without error
            json.dumps(doc, default=str)
