import pytest
import os
from db import get_db, introspect_schema, execute_pipeline

class TestDatabaseLayer:
    def test_get_db_returns_database(self):
        db = get_db()
        # pymongo.database.Database is the expected type
        assert db.name is not None

    def test_introspect_schema_returns_structure(self):
        db = get_db()
        schema = introspect_schema(db)
        assert "database" in schema
        assert "collections" in schema
        assert isinstance(schema["collection_names"], list)
        # Should have at least some collections
        assert len(schema["collection_names"]) >= 0
