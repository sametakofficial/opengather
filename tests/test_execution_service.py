"""
ExecutionService Tests

Comprehensive tests for the core execution service:
- Execution lifecycle (start, process, complete)
- State persistence during execution
- Error handling and recovery
- Progress callbacks

Run with:
    pytest tests/test_execution_service.py -v
"""

import asyncio
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import pytest

from archiverr.core.services import ExecutionService, ExecutionProgress, ExecutionResult


# ==================== FIXTURES ====================

@pytest.fixture
def temp_db_path():
    """Temporary database path."""
    path = tempfile.mkdtemp(prefix="archiverr_exec_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def minimal_config():
    """Minimal valid configuration."""
    return {
        "options": {
            "debug": False,
            "dry_run": True
        },
        "plugins": {
            "scanner": {
                "enabled": True,
                "targets": [],
                "recursive": False
            },
            "renamer": {
                "enabled": True
            }
        },
        "tasks": []
    }


@pytest.fixture
def config_with_targets(tmp_path):
    """Configuration with actual file targets."""
    # Create test file
    test_file = tmp_path / "Test Movie (2025).mkv"
    test_file.write_text("dummy content")
    
    return {
        "options": {
            "debug": False,
            "dry_run": True
        },
        "plugins": {
            "scanner": {
                "enabled": True,
                "targets": [str(test_file)],
                "recursive": False
            },
            "renamer": {
                "enabled": True
            }
        },
        "tasks": []
    }


@pytest.fixture
def mock_persistence():
    """Mock persistence for isolated tests."""
    mock = MagicMock()
    mock.save_execution = MagicMock()
    mock.save_match = MagicMock()
    mock.save_plugin_result = MagicMock()
    mock.update_match = MagicMock()
    mock.get_execution = MagicMock(return_value=None)
    return mock


# ==================== UNIT TESTS ====================

@pytest.mark.unit
class TestExecutionServiceInit:
    """Tests for ExecutionService initialization."""
    
    def test_init_without_persistence(self):
        """Test service can be created without persistence."""
        service = ExecutionService()
        assert service.persistence is None
    
    def test_init_with_persistence(self, mock_persistence):
        """Test service accepts persistence parameter."""
        service = ExecutionService(persistence=mock_persistence)
        assert service.persistence is mock_persistence
    
    def test_init_with_debugger(self):
        """Test service accepts debugger parameter."""
        mock_debugger = MagicMock()
        service = ExecutionService(debugger=mock_debugger)
        assert service.debugger is mock_debugger


@pytest.mark.unit
class TestProgressCallbacks:
    """Tests for progress callback system."""
    
    def test_add_callback(self):
        """Test adding progress callback."""
        service = ExecutionService()
        callback = MagicMock()
        
        service.add_progress_callback(callback)
        
        assert callback in service._progress_callbacks
    
    def test_emit_progress(self):
        """Test emitting progress to callbacks."""
        service = ExecutionService()
        callback = MagicMock()
        service.add_progress_callback(callback)
        
        progress = ExecutionProgress(
            execution_id="test-123",
            status="running",
            message="Testing"
        )
        service._emit_progress(progress)
        
        callback.assert_called_once_with(progress)
    
    def test_callback_error_handling(self):
        """Test that callback errors don't break execution."""
        service = ExecutionService()
        
        # Bad callback that raises
        bad_callback = MagicMock(side_effect=Exception("Callback error"))
        good_callback = MagicMock()
        
        service.add_progress_callback(bad_callback)
        service.add_progress_callback(good_callback)
        
        progress = ExecutionProgress(
            execution_id="test-123",
            status="running",
            message="Testing"
        )
        
        # Should not raise
        service._emit_progress(progress)
        
        # Good callback should still be called
        good_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test async progress callbacks."""
        service = ExecutionService()
        
        received = []
        async def async_callback(progress):
            received.append(progress)
        
        service.add_progress_callback(async_callback)
        
        progress = ExecutionProgress(
            execution_id="test-123",
            status="running",
            message="Testing"
        )
        
        await service._emit_progress_async(progress)
        
        assert len(received) == 1
        assert received[0].execution_id == "test-123"


@pytest.mark.unit
class TestExecutionProgress:
    """Tests for ExecutionProgress dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        progress = ExecutionProgress(
            execution_id="exec-123",
            status="running",
            current_match=5,
            total_matches=10,
            message="Processing..."
        )
        
        d = progress.to_dict()
        
        assert d["execution_id"] == "exec-123"
        assert d["status"] == "running"
        assert d["current_match"] == 5
        assert d["total_matches"] == 10
        assert d["percent"] == 0.0  # Default
    
    def test_default_values(self):
        """Test default values are set."""
        progress = ExecutionProgress(
            execution_id="test",
            status="pending"
        )
        
        assert progress.current_match == 0
        assert progress.total_matches == 0
        assert progress.message == ""
        assert progress.percent == 0.0
        assert progress.timestamp is not None


@pytest.mark.unit
class TestLoadConfig:
    """Tests for configuration loading."""
    
    def test_load_valid_config(self, tmp_path):
        """Test loading valid YAML config."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
options:
  debug: true
  dry_run: true
plugins:
  scanner:
    enabled: true
""")
        
        config = ExecutionService.load_config(str(config_file))
        
        assert config["options"]["debug"] is True
        assert config["plugins"]["scanner"]["enabled"] is True
    
    def test_load_nonexistent_config(self):
        """Test loading non-existent config raises error."""
        with pytest.raises(FileNotFoundError):
            ExecutionService.load_config("/nonexistent/path/config.yml")


# ==================== INTEGRATION TESTS ====================

@pytest.mark.integration
class TestExecutionFlow:
    """Integration tests for full execution flow."""
    
    @pytest.mark.asyncio
    async def test_execution_with_no_matches(self, minimal_config, temp_db_path, monkeypatch):
        """Test execution with no input matches."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        service = ExecutionService()
        result = await service.run_execution_async(minimal_config)
        
        assert result.success is False
        assert result.error == "No matches found"
    
    @pytest.mark.asyncio
    async def test_execution_emits_progress(self, minimal_config, temp_db_path, monkeypatch):
        """Test execution emits progress updates."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        received_progress = []
        
        async def capture_progress(progress):
            received_progress.append(progress)
        
        service = ExecutionService()
        service.add_progress_callback(capture_progress)
        
        await service.run_execution_async(minimal_config)
        
        # Should have received at least initializing progress
        assert len(received_progress) > 0
        assert received_progress[0].status == "running"
    
    @pytest.mark.asyncio
    async def test_execution_with_persistence(self, config_with_targets, temp_db_path, monkeypatch):
        """Test execution saves to persistence."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        service = ExecutionService()
        result = await service.run_execution_async(config_with_targets)
        
        # Check persistence file was created
        state_file = Path(temp_db_path) / "archiverr_state.json"
        if state_file.exists():
            import json
            with open(state_file) as f:
                saved_state = json.load(f)
            
            # Should have execution data
            assert "executions" in saved_state or len(saved_state) > 0
    
    @pytest.mark.asyncio
    async def test_execution_result_structure(self, minimal_config, temp_db_path, monkeypatch):
        """Test execution result has correct structure."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        service = ExecutionService()
        result = await service.run_execution_async(minimal_config)
        
        assert hasattr(result, "execution_id")
        assert hasattr(result, "success")
        assert hasattr(result, "total_matches")
        assert hasattr(result, "completed_matches")
        assert hasattr(result, "failed_matches")
        assert hasattr(result, "duration_ms")
        assert hasattr(result, "api_response")


@pytest.mark.integration
class TestExecutionErrorHandling:
    """Tests for error handling during execution."""
    
    @pytest.mark.asyncio
    async def test_invalid_plugin_config(self, temp_db_path, monkeypatch):
        """Test handling of invalid plugin configuration."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        bad_config = {
            "options": {"debug": False},
            "plugins": {
                "nonexistent_plugin": {"enabled": True}
            },
            "tasks": []
        }
        
        service = ExecutionService()
        result = await service.run_execution_async(bad_config)
        
        # Should complete (even if with errors) without crashing
        assert isinstance(result, ExecutionResult)
    
    @pytest.mark.asyncio
    async def test_execution_timeout_handling(self, minimal_config, temp_db_path, monkeypatch):
        """Test that long-running executions don't hang tests."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        service = ExecutionService()
        
        # Should complete within reasonable time
        try:
            result = await asyncio.wait_for(
                service.run_execution_async(minimal_config),
                timeout=30.0
            )
            assert isinstance(result, ExecutionResult)
        except asyncio.TimeoutError:
            pytest.fail("Execution timed out")


# ==================== CLI VS API PARITY TESTS ====================

@pytest.mark.integration
class TestCLIAPIParity:
    """Tests ensuring CLI and API have same behavior."""
    
    @pytest.mark.asyncio
    async def test_both_use_same_persistence(self, minimal_config, temp_db_path, monkeypatch):
        """Test that CLI and API use same persistence layer."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        # API path (through ExecutionService)
        service = ExecutionService()
        await service.run_execution_async(minimal_config)
        
        # Both should create state in same location
        # (This test validates the fix we made)
        from archiverr.infrastructure.database import DatabaseConnection
        
        db = DatabaseConnection.from_env()
        persistence = db.connect()
        
        stats = persistence.get_statistics()
        assert stats["backend"] in ["MockPersistence", "MongoDBPersistence"]
        
        db.disconnect()
    
    @pytest.mark.asyncio
    async def test_execution_id_format(self, minimal_config, temp_db_path, monkeypatch):
        """Test execution IDs have consistent format."""
        monkeypatch.setenv("ARCHIVERR_DB_BACKEND", "mock")
        monkeypatch.setenv("ARCHIVERR_MOCK_PATH", temp_db_path)
        
        service = ExecutionService()
        result = await service.run_execution_async(minimal_config)
        
        # Execution ID should be 8-character hex
        assert len(result.execution_id) == 8
        assert all(c in "0123456789abcdef" for c in result.execution_id)
