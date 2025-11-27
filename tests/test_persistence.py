"""
Persistence Layer Tests

Comprehensive tests for database persistence:
- MockPersistence (file-based)
- MongoDBPersistence (when available)
- State saving and loading consistency

Run with:
    pytest tests/test_persistence.py -v
    pytest tests/test_persistence.py -v -k "test_mock"  # Only mock tests
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import pytest

from archiverr.infrastructure.database import (
    DatabaseConnection,
    DatabaseConfig,
    MockPersistence,
    MONGODB_AVAILABLE
)


# ==================== FIXTURES ====================

@pytest.fixture
def temp_db_path():
    """Create temporary directory for mock database."""
    path = tempfile.mkdtemp(prefix="archiverr_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def mock_persistence(temp_db_path):
    """Create MockPersistence with temporary storage."""
    persistence = MockPersistence(base_path=temp_db_path)
    persistence.connect()
    yield persistence
    persistence.disconnect()


@pytest.fixture
def sample_execution():
    """Sample execution data."""
    return {
        "_id": f"exec_{uuid4().hex[:8]}",
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "config": {"options": {"debug": True}},
        "total_matches": 0,
        "completed_matches": 0,
        "failed_matches": 0
    }


@pytest.fixture
def sample_match():
    """Sample match data."""
    return {
        "_id": f"match_{uuid4().hex[:8]}",
        "index": 0,
        "input_path": "/path/to/movie.mkv",
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "plugin_results": {}
    }


# ==================== MOCK PERSISTENCE TESTS ====================

@pytest.mark.unit
class TestMockPersistence:
    """Tests for MockPersistence file-based backend."""
    
    def test_connect_creates_directory(self, temp_db_path):
        """Test that connect creates the database directory."""
        persistence = MockPersistence(base_path=temp_db_path)
        persistence.connect()
        
        assert Path(temp_db_path).exists()
        persistence.disconnect()
    
    def test_save_and_load_execution(self, mock_persistence, sample_execution):
        """Test saving and loading execution."""
        # Save
        mock_persistence.save_execution(sample_execution)
        
        # Load
        loaded = mock_persistence.get_execution(sample_execution["_id"])
        
        assert loaded is not None
        assert loaded["_id"] == sample_execution["_id"]
        assert loaded["status"] == sample_execution["status"]
    
    def test_update_execution(self, mock_persistence, sample_execution):
        """Test updating execution status."""
        # Save initial
        mock_persistence.save_execution(sample_execution)
        
        # Update
        sample_execution["status"] = "completed"
        sample_execution["completed_matches"] = 5
        mock_persistence.save_execution(sample_execution)
        
        # Verify update
        loaded = mock_persistence.get_execution(sample_execution["_id"])
        assert loaded["status"] == "completed"
        assert loaded["completed_matches"] == 5
    
    def test_list_executions(self, mock_persistence):
        """Test listing multiple executions."""
        # Save multiple executions
        for i in range(5):
            exec_data = {
                "_id": f"exec_{i}",
                "status": "completed",
                "started_at": datetime.now().isoformat()
            }
            mock_persistence.save_execution(exec_data)
        
        # List
        executions = mock_persistence.get_recent_executions(limit=10)
        assert len(executions) >= 5
    
    def test_save_match(self, mock_persistence, sample_execution, sample_match):
        """Test saving match with execution reference."""
        mock_persistence.save_execution(sample_execution)
        
        sample_match["execution_id"] = sample_execution["_id"]
        mock_persistence.save_match(sample_match)
        
        # Verify match exists
        matches = mock_persistence.get_matches(sample_execution["_id"])
        assert len(matches) >= 1
    
    def test_save_plugin_result(self, mock_persistence, sample_execution, sample_match):
        """Test saving plugin result."""
        mock_persistence.save_execution(sample_execution)
        
        sample_match["execution_id"] = sample_execution["_id"]
        mock_persistence.save_match(sample_match)
        
        # Use the correct method signature
        execution_id = sample_execution["_id"].replace("exec_", "")
        mock_persistence.save_plugin_result(
            execution_id=execution_id,
            match_index=0,
            plugin_name="tmdb",
            result={"movie": {"title": "Test Movie"}}
        )
    
    def test_delete_execution(self, mock_persistence, sample_execution):
        """Test deleting execution."""
        mock_persistence.save_execution(sample_execution)
        
        # Verify exists
        assert mock_persistence.get_execution(sample_execution["_id"]) is not None
        
        # Delete
        result = mock_persistence.delete_execution(sample_execution["_id"])
        assert result is True
        
        # Verify deleted
        assert mock_persistence.get_execution(sample_execution["_id"]) is None
    
    def test_get_statistics(self, mock_persistence, sample_execution):
        """Test getting database statistics."""
        mock_persistence.save_execution(sample_execution)
        
        stats = mock_persistence.get_statistics()
        
        assert "backend" in stats
        assert "executions" in stats
    
    def test_persistence_across_reconnect(self, temp_db_path, sample_execution):
        """Test data persists after disconnect/reconnect."""
        # First connection - save data
        p1 = MockPersistence(base_path=temp_db_path)
        p1.connect()
        p1.save_execution(sample_execution)
        p1.disconnect()
        
        # Second connection - load data
        p2 = MockPersistence(base_path=temp_db_path)
        p2.connect()
        loaded = p2.get_execution(sample_execution["_id"])
        p2.disconnect()
        
        assert loaded is not None
        assert loaded["_id"] == sample_execution["_id"]


# ==================== DATABASE CONNECTION TESTS ====================

@pytest.mark.unit
class TestDatabaseConnection:
    """Tests for DatabaseConnection manager."""
    
    def test_from_env_defaults_to_mock(self, monkeypatch):
        """Test default backend is mock."""
        monkeypatch.delenv("ARCHIVERR_DB_BACKEND", raising=False)
        
        db = DatabaseConnection.from_env()
        assert db.config.backend == "mock"
    
    def test_from_env_respects_mongodb(self, monkeypatch):
        """Test MongoDB backend when specified."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mongodb")
        
        db = DatabaseConnection.from_env()
        assert db.config.backend == "mongodb"
    
    def test_connect_returns_persistence(self, temp_db_path, monkeypatch):
        """Test connect returns persistence interface."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        assert persistence is not None
        assert hasattr(persistence, "save_execution")
        
        db.disconnect()
    
    def test_invalid_backend_raises_error(self, temp_db_path):
        """Test invalid backend raises ValueError."""
        config = DatabaseConfig(backend="invalid_backend")
        db = DatabaseConnection(config)
        
        with pytest.raises(ValueError, match="Unknown database backend"):
            db.get_persistence()


# ==================== MONGODB PERSISTENCE TESTS ====================

@pytest.mark.integration
@pytest.mark.skipif(not MONGODB_AVAILABLE, reason="MongoDB not available")
class TestMongoDBPersistence:
    """Tests for MongoDB backend (requires running MongoDB)."""
    
    @pytest.fixture
    def mongodb_persistence(self, monkeypatch):
        """Create MongoDB persistence for tests."""
        from archiverr.infrastructure.database import MongoDBPersistence
        
        # Use test database
        test_db = f"archiverr_test_{uuid4().hex[:8]}"
        persistence = MongoDBPersistence(
            uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            database=test_db
        )
        persistence.connect()
        yield persistence
        
        # Cleanup - drop test database
        try:
            persistence._client.drop_database(test_db)
        except:
            pass
        persistence.disconnect()
    
    def test_mongodb_save_and_load(self, mongodb_persistence, sample_execution):
        """Test save and load with MongoDB."""
        mongodb_persistence.save_execution(sample_execution)
        
        loaded = mongodb_persistence.get_execution(sample_execution["_id"])
        
        assert loaded is not None
        assert loaded["_id"] == sample_execution["_id"]
    
    def test_mongodb_statistics(self, mongodb_persistence, sample_execution):
        """Test MongoDB statistics."""
        mongodb_persistence.save_execution(sample_execution)
        
        stats = mongodb_persistence.get_statistics()
        
        assert stats["backend"] == "MongoDBPersistence"
        assert stats["executions"] >= 1


# ==================== CONSISTENCY TESTS ====================

@pytest.mark.unit
class TestPersistenceConsistency:
    """Tests for data consistency across operations."""
    
    def test_concurrent_saves(self, mock_persistence):
        """Test multiple rapid saves don't corrupt data."""
        execution_id = f"exec_concurrent_{uuid4().hex[:8]}"
        
        # Rapid updates
        for i in range(100):
            exec_data = {
                "_id": execution_id,
                "counter": i,
                "status": "running"
            }
            mock_persistence.save_execution(exec_data)
        
        # Final state should have last counter value
        loaded = mock_persistence.get_execution(execution_id)
        assert loaded["counter"] == 99
    
    def test_special_characters_in_paths(self, mock_persistence, sample_execution):
        """Test handling of special characters in file paths."""
        sample_match = {
            "_id": f"match_{uuid4().hex[:8]}",
            "execution_id": sample_execution["_id"],
            "input_path": "/path/to/Movie (2025) [4K HDR] 'Special'.mkv",
            "status": "completed"
        }
        
        mock_persistence.save_execution(sample_execution)
        mock_persistence.save_match(sample_match)
        
        matches = mock_persistence.get_matches(sample_execution["_id"])
        assert len(matches) >= 1
        assert "Special" in matches[0]["input_path"]
    
    def test_large_plugin_data(self, mock_persistence, sample_execution):
        """Test handling of large plugin result data."""
        # Create large data
        large_data = {
            "metadata": {"key_" + str(i): "value_" * 100 for i in range(100)}
        }
        
        mock_persistence.save_execution(sample_execution)
        
        # Use correct method signature
        execution_id = sample_execution["_id"].replace("exec_", "")
        mock_persistence.save_plugin_result(
            execution_id=execution_id,
            match_index=0,
            plugin_name="tmdb",
            result=large_data
        )
        
        # Should not raise
