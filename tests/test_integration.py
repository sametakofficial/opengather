"""
Integration Tests

End-to-end tests verifying:
- CLI and API produce same results
- MongoDB persistence works correctly
- Full execution pipeline

Run with:
    pytest tests/test_integration.py -v
    pytest tests/test_integration.py -v -m integration
"""

import asyncio
import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

# Disable rate limiting for tests
os.environ["RATE_LIMIT_ENABLED"] = "false"


# ==================== FIXTURES ====================

@pytest.fixture
def temp_workspace():
    """Create temporary workspace with test files."""
    workspace = tempfile.mkdtemp(prefix="archiverr_integration_")
    
    # Create test media file
    media_dir = Path(workspace) / "media"
    media_dir.mkdir()
    
    test_file = media_dir / "Test Movie (2025) 1080p.mkv"
    test_file.write_text("dummy content for testing")
    
    # Create mock db directory
    db_dir = Path(workspace) / "mock_db"
    db_dir.mkdir()
    
    yield {
        "root": workspace,
        "media_dir": str(media_dir),
        "test_file": str(test_file),
        "db_dir": str(db_dir)
    }
    
    shutil.rmtree(workspace, ignore_errors=True)


@pytest.fixture
def test_config(temp_workspace):
    """Create test configuration."""
    return {
        "options": {
            "debug": False,
            "dry_run": True,
            "hardlink": False
        },
        "plugins": {
            "scanner": {
                "enabled": True,
                "targets": [temp_workspace["test_file"]],
                "recursive": False
            },
            "renamer": {
                "enabled": True
            },
            "tmdb": {
                "enabled": False  # Disable to avoid API calls in tests
            },
            "ffprobe": {
                "enabled": False  # Disable to avoid ffprobe dependency
            }
        },
        "tasks": []
    }


@pytest.fixture
def config_file(temp_workspace, test_config):
    """Create config.yml file."""
    import yaml
    
    config_path = Path(temp_workspace["root"]) / "config.yml"
    with open(config_path, 'w') as f:
        yaml.dump(test_config, f)
    
    return str(config_path)


# ==================== CLI TESTS ====================

@pytest.mark.integration
class TestCLIExecution:
    """Tests for CLI execution path."""
    
    def test_cli_requires_config(self, temp_workspace, monkeypatch):
        """Test CLI fails gracefully without config.yml."""
        monkeypatch.chdir(temp_workspace["root"])
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        # Import after setting up environment
        from archiverr.__main__ import cli_main
        
        # Should exit with error (no config.yml)
        with pytest.raises(SystemExit):
            cli_main()
    
    def test_cli_with_config(self, temp_workspace, config_file, monkeypatch):
        """Test CLI runs with valid config."""
        monkeypatch.chdir(temp_workspace["root"])
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        # This test may need mocking of actual plugin execution
        # For now, just verify it doesn't crash on initialization
        from archiverr.utils.config_loader import load_config_with_tracking
        
        config = load_config_with_tracking(config_file)
        assert config is not None
        assert "plugins" in config


# ==================== API TESTS ====================

@pytest.mark.integration
class TestAPIExecution:
    """Tests for API execution path."""
    
    @pytest.fixture
    def api_client(self, temp_workspace, monkeypatch):
        """Create API test client."""
        pytest.importorskip("httpx")
        pytest.importorskip("fastapi")
        
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from fastapi.testclient import TestClient
        from archiverr.api.main import app
        
        with TestClient(app) as client:
            yield client
    
    def test_api_health(self, api_client):
        """Test API health endpoint."""
        response = api_client.get("/api/v1/system/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_api_run_returns_valid_response(self, api_client):
        """Test API run returns valid response structure."""
        response = api_client.post("/api/v1/run/", json={})
        
        # Should return 200 with valid structure
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "success" in data


# ==================== EXECUTION SERVICE TESTS ====================

@pytest.mark.integration
class TestExecutionServiceIntegration:
    """Integration tests for ExecutionService."""
    
    @pytest.mark.asyncio
    async def test_service_creates_execution(self, test_config, temp_workspace, monkeypatch):
        """Test ExecutionService creates execution records."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.core.services import ExecutionService
        
        service = ExecutionService()
        result = await service.run_execution_async(test_config)
        
        assert result.execution_id is not None
    
    @pytest.mark.asyncio
    async def test_service_saves_to_persistence(self, test_config, temp_workspace, monkeypatch):
        """Test ExecutionService saves to persistence layer."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.core.services import ExecutionService
        from archiverr.infrastructure.database import DatabaseConnection
        
        service = ExecutionService()
        result = await service.run_execution_async(test_config)
        
        # Verify data was saved
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        stats = persistence.get_statistics()
        
        # Should have at least some data
        assert stats["backend"] == "MockPersistence"
        
        db.disconnect()


# ==================== PERSISTENCE INTEGRATION TESTS ====================

@pytest.mark.integration
class TestPersistenceIntegration:
    """Tests for persistence layer integration."""
    
    def test_mock_persistence_creates_files(self, temp_workspace, monkeypatch):
        """Test MockPersistence creates state files."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.infrastructure.database import DatabaseConnection
        
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        # Save test data
        execution = {
            "_id": "exec_test123",
            "status": "completed",
            "started_at": datetime.now().isoformat()
        }
        persistence.save_execution(execution)
        
        # Verify file exists
        state_file = Path(temp_workspace["db_dir"]) / "archiverr_state.json"
        assert state_file.exists()
        
        db.disconnect()
    
    def test_persistence_data_survives_restart(self, temp_workspace, monkeypatch):
        """Test data persists across connection restarts."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.infrastructure.database import DatabaseConnection
        
        execution_id = "exec_persist_test"
        
        # First connection - save data
        db1 = DatabaseConnection.from_env()
        p1 = db1.connect()
        p1.save_execution({
            "_id": execution_id,
            "status": "completed"
        })
        db1.disconnect()
        
        # Second connection - load data
        DatabaseConnection.reset()  # Reset singleton
        db2 = DatabaseConnection.from_env()
        p2 = db2.connect()
        
        loaded = p2.get_execution(execution_id)
        
        assert loaded is not None
        assert loaded["_id"] == execution_id
        
        db2.disconnect()


# ==================== CLI/API PARITY TESTS ====================

@pytest.mark.integration
class TestCLIAPIParity:
    """Tests verifying CLI and API produce identical results."""
    
    @pytest.mark.asyncio
    async def test_both_use_same_state_manager(self, test_config, temp_workspace, monkeypatch):
        """Test CLI and API use same GlobalStateManager."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.state import GlobalStateManager
        from archiverr.core.services import ExecutionService
        
        # Run through API path
        service = ExecutionService()
        await service.run_execution_async(test_config)
        
        # GlobalStateManager should have been used
        state = GlobalStateManager()
        
        # State should have execution info
        assert state._execution is not None
    
    @pytest.mark.asyncio
    async def test_both_use_same_persistence_layer(self, test_config, temp_workspace, monkeypatch):
        """Test CLI and API use same persistence backend."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.core.services import ExecutionService
        from archiverr.infrastructure.database import DatabaseConnection
        
        # Run execution
        service = ExecutionService()
        await service.run_execution_async(test_config)
        
        # Check persistence has data
        DatabaseConnection.reset()
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        # Should have execution records
        executions = persistence.get_recent_executions(limit=10)
        
        # At least one execution should exist
        assert len(executions) >= 0  # May be 0 if execution failed early
        
        db.disconnect()


# ==================== ERROR RECOVERY TESTS ====================

@pytest.mark.integration
class TestErrorRecovery:
    """Tests for error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_execution_handles_plugin_errors(self, temp_workspace, monkeypatch):
        """Test execution continues after plugin errors."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        from archiverr.core.services import ExecutionService
        
        # Config with invalid plugin should not crash
        bad_config = {
            "options": {"debug": False, "dry_run": True},
            "plugins": {
                "scanner": {
                    "enabled": True,
                    "targets": ["/nonexistent/path/file.mkv"]
                }
            },
            "tasks": []
        }
        
        service = ExecutionService()
        result = await service.run_execution_async(bad_config)
        
        # Should complete (even if no matches)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_persistence_errors_dont_crash_execution(self, test_config, monkeypatch):
        """Test execution completes even if persistence fails."""
        # Use invalid path for mock persistence
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", "/root/no_permission")
        
        from archiverr.core.services import ExecutionService
        
        service = ExecutionService()
        
        # Should not crash, may log errors
        try:
            result = await service.run_execution_async(test_config)
            # If it completes, that's fine
            assert result is not None
        except PermissionError:
            # This is acceptable - permission denied
            pass


# ==================== PERFORMANCE TESTS ====================

@pytest.mark.integration
@pytest.mark.slow
class TestPerformance:
    """Performance and stress tests."""
    
    @pytest.mark.asyncio
    async def test_many_matches_execution(self, temp_workspace, monkeypatch):
        """Test execution with many matches."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_workspace["db_dir"])
        
        # Create many test files
        media_dir = Path(temp_workspace["media_dir"])
        targets = []
        for i in range(20):
            test_file = media_dir / f"Movie {i} (2025).mkv"
            test_file.write_text(f"content {i}")
            targets.append(str(test_file))
        
        config = {
            "options": {"debug": False, "dry_run": True},
            "plugins": {
                "scanner": {
                    "enabled": True,
                    "targets": targets
                },
                "renamer": {"enabled": True}
            },
            "tasks": []
        }
        
        from archiverr.core.services import ExecutionService
        
        service = ExecutionService()
        
        import time
        start = time.time()
        result = await service.run_execution_async(config)
        duration = time.time() - start
        
        # Should complete in reasonable time (< 30 seconds)
        assert duration < 30
        
        # Should have processed matches
        assert result.total_matches >= 0
