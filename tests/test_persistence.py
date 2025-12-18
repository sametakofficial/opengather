"""
Persistence Layer Tests

Comprehensive tests for database persistence:
- PyMongoPersistence (MongoDB)
- State saving and loading consistency

Run with:
    pytest tests/test_persistence.py -v
"""

import os
from datetime import datetime
from uuid import uuid4

import pytest

from archiverr.infrastructure.database import DatabaseConnection, PyMongoPersistence


# ==================== FIXTURES ====================

@pytest.fixture
def mongodb_persistence():
    """Create PyMongoPersistence for tests (requires running MongoDB)."""
    pytest.importorskip("pymongo")

    if PyMongoPersistence is None:
        pytest.skip("PyMongoPersistence not available")

    # Quick connection check
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
    except Exception as e:
        pytest.skip(f"MongoDB not available: {e}")

    test_db = f"archiverr_test_{uuid4().hex[:8]}"
    persistence = PyMongoPersistence(
        uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        database=test_db,
    )
    persistence.connect()
    yield persistence

    try:
        persistence._client.drop_database(test_db)
    except Exception:
        pass
    persistence.disconnect()


@pytest.fixture
def sample_execution():
    """Sample execution data."""
    return {
        "id": f"run_{uuid4().hex[:8]}",
        "status": {"state": "running", "success": True},
        "created_at": datetime.now().isoformat(),
        "config": {"options": {"debug": True}},
        "jobs": []
    }


# ==================== PYMONGO PERSISTENCE TESTS ====================

@pytest.mark.integration
class TestPyMongoPersistence:
    """Tests for PyMongoPersistence backend (requires running MongoDB)."""

    def test_save_and_load_run(self, mongodb_persistence, sample_execution):
        mongodb_persistence.save_run(sample_execution)
        loaded = mongodb_persistence.get_run(sample_execution["id"])
        assert loaded is not None
        assert loaded["id"] == sample_execution["id"]

    def test_save_and_load_job(self, mongodb_persistence, sample_execution):
        mongodb_persistence.save_run(sample_execution)
        job = {
            "id": f"job_{uuid4().hex[:8]}",
            "run_id": sample_execution["id"],
            "index": 0,
            "status": {"state": "pending", "success": True},
            "input": {"value": "/path/to/movie.mkv", "data": {}},
            "output": {"values": [], "data": {}},
            "plugins": {},
        }
        mongodb_persistence.save_job(job)
        loaded = mongodb_persistence.get_job(job["id"])
        assert loaded is not None
        assert loaded["id"] == job["id"]
        assert loaded["run_id"] == job["run_id"]

    def test_save_and_load_plugin(self, mongodb_persistence, sample_execution):
        mongodb_persistence.save_run(sample_execution)
        job_id = f"job_{uuid4().hex[:8]}"
        mongodb_persistence.save_job({
            "id": job_id,
            "run_id": sample_execution["id"],
            "index": 0,
            "status": {"state": "pending", "success": True},
            "input": {"value": "x", "data": {}},
            "output": {"values": [], "data": {}},
            "plugins": {},
        })

        plugin_doc = {
            "job_id": job_id,
            "run_id": sample_execution["id"],
            "job_index": 0,
            "plugin_name": "test_plugin",
            "stage": "data",
            "status": {"success": True},
            "data": {"k": "v"},
        }
        mongodb_persistence.save_plugin(plugin_doc)
        loaded = mongodb_persistence.get_plugin(job_id, "test_plugin")
        assert loaded is not None
        assert loaded["job_id"] == job_id
        assert loaded["plugin_name"] == "test_plugin"
