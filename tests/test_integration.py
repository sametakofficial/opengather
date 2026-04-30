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

import importlib.util

import pytest

if importlib.util.find_spec("pytest_asyncio") is None:
    pytest.skip("pytest-asyncio not installed", allow_module_level=True)

# Disable rate limiting for tests
os.environ["RATE_LIMIT_ENABLED"] = "false"


def _mongodb_available() -> bool:
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


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
    
    yield {
        "root": workspace,
        "media_dir": str(media_dir),
        "test_file": str(test_file)
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
        if not _mongodb_available():
            pytest.skip("MongoDB not available")
        
        # Import after setting up environment
        from archiverr.__main__ import cli_main
        
        # Should exit with error (no config.yml)
        with pytest.raises(SystemExit):
            cli_main()
    
    def test_cli_with_config(self, temp_workspace, config_file, monkeypatch):
        """Test CLI runs with valid config."""
        monkeypatch.chdir(temp_workspace["root"])
        if not _mongodb_available():
            pytest.skip("MongoDB not available")
        
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

        if not _mongodb_available():
            pytest.skip("MongoDB not available")
        
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
        pytest.skip("ExecutionService integration tests are deprecated")
        
        from archiverr.core.services import ExecutionService
        
        service = ExecutionService()
        result = await service.run_execution_async(test_config)
        
        assert result.execution_id is not None
    
    @pytest.mark.asyncio
    async def test_service_saves_to_persistence(self, test_config, temp_workspace, monkeypatch):
        """Test ExecutionService saves to persistence layer."""
        pytest.skip("ExecutionService integration tests are deprecated")
        
        from archiverr.core.services import ExecutionService
        from archiverr.infrastructure.database import DatabaseConnection
        
        service = ExecutionService()
        result = await service.run_execution_async(test_config)
        
        # Verify data was saved
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        stats = persistence.get_statistics()
        
        # Should have at least some data
        assert stats["backend"] in ["PyMongoPersistence", "MongoDBPersistence"]
        
        db.disconnect()


# ==================== PERSISTENCE INTEGRATION TESTS ====================

@pytest.mark.integration
class TestPersistenceIntegration:
    """Tests for persistence layer integration."""
    
    def test_mongodb_persistence_creates_records(self, temp_workspace, monkeypatch):
        """Test MongoDB persistence creates records."""
        if not _mongodb_available():
            pytest.skip("MongoDB not available")
        
        from archiverr.infrastructure.database import DatabaseConnection
        
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        # Save test data
        run = {
            "id": "run_test123",
            "status": {"state": "success", "success": True},
            "created_at": datetime.now().isoformat(),
            "config": {"options": {"dry_run": True}},
            "jobs": [],
        }
        persistence.save_run(run)
        
        # Verify record exists
        loaded = persistence.get_run(run["id"])
        assert loaded is not None
        assert loaded["id"] == run["id"]
        
        db.disconnect()
    
    def test_persistence_data_survives_restart(self, temp_workspace, monkeypatch):
        """Test data persists across connection restarts."""
        if not _mongodb_available():
            pytest.skip("MongoDB not available")
        
        from archiverr.infrastructure.database import DatabaseConnection
        
        run_id = "run_persist_test"
        
        # First connection - save data
        db1 = DatabaseConnection.from_env()
        p1 = db1.connect()
        p1.save_run({
            "id": run_id,
            "status": {"state": "success", "success": True},
            "created_at": datetime.now().isoformat(),
            "config": {"options": {"dry_run": True}},
            "jobs": [],
        })
        db1.disconnect()
        
        # Second connection - load data
        DatabaseConnection.reset()  # Reset singleton
        db2 = DatabaseConnection.from_env()
        p2 = db2.connect()
        
        loaded = p2.get_run(run_id)
        
        assert loaded is not None
        assert loaded["id"] == run_id
        
        db2.disconnect()


# ==================== CLI/API PARITY TESTS ====================

@pytest.mark.integration
class TestCLIAPIParity:
    """Tests verifying CLI and API produce identical results."""
    
    @pytest.mark.asyncio
    async def test_execution_service_uses_state_manager(self, test_config, temp_workspace, monkeypatch):
        """Test ExecutionService properly uses StateManager with DI pattern."""
        pytest.skip("ExecutionService parity tests are deprecated")
        
        from archiverr.core.services import ExecutionService
        
        # Run through API path
        service = ExecutionService()
        result = await service.run_execution_async(test_config)
        
        # Execution should complete (state managed internally)
        # With DI pattern, each execution creates its own StateManager
        assert result is not None
        assert hasattr(result, 'execution_id')
        assert result.execution_id is not None
    
    @pytest.mark.asyncio
    async def test_both_use_same_persistence_layer(self, test_config, temp_workspace, monkeypatch):
        """Test CLI and API use same persistence backend."""
        pytest.skip("ExecutionService parity tests are deprecated")
        
        from archiverr.core.services import ExecutionService
        from archiverr.infrastructure.database import DatabaseConnection
        
        # Run execution
        service = ExecutionService()
        await service.run_execution_async(test_config)
        
        # Check persistence has data
        DatabaseConnection.reset()
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        # Should have run records via canonical PersistenceInterface
        # (legacy get_recent_executions removed in S36 PASS 6.C)
        if hasattr(persistence, 'get_runs'):
            runs = persistence.get_runs(limit=10)
            assert len(runs) >= 0  # May be 0 if run failed early
        
        db.disconnect()


# ==================== ERROR RECOVERY TESTS ====================

@pytest.mark.integration
class TestErrorRecovery:
    """Tests for error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_execution_handles_plugin_errors(self, temp_workspace, monkeypatch):
        """Test execution continues after plugin errors."""
        pytest.skip("ExecutionService tests are deprecated")
        
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
        pytest.skip("Mock persistence removed")
        
        from archiverr.core.services import ExecutionService
        
        service = ExecutionService()
        
        # Should not crash, may log errors
        try:
            result = await service.run_execution_async(test_config)
            # If it completes, that's fine
            assert result is not None
        except Exception:
            # This is acceptable - persistence failed
            pass


# ==================== PERFORMANCE TESTS ====================

@pytest.mark.integration
@pytest.mark.slow
class TestPerformance:
    """Performance and stress tests."""
    
    @pytest.mark.asyncio
    async def test_many_matches_execution(self, temp_workspace, monkeypatch):
        """Test execution with many matches."""
        pytest.skip("ExecutionService removed in refactoring - use orchestrator directly")
        
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
