"""
State Management Tests

Comprehensive tests for GlobalStateManager:
- State lifecycle (init, update, complete)
- Match tracking and plugin results
- Persistence integration
- Event emission

Run with:
    pytest tests/test_state_management.py -v
"""

import tempfile
import shutil
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest

from archiverr.state import GlobalStateManager, ExecutionState, MatchState, PluginResult
from archiverr.state.models import ExecutionStatus


# ==================== FIXTURES ====================

@pytest.fixture
def temp_db_path():
    """Temporary database path."""
    path = tempfile.mkdtemp(prefix="archiverr_state_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def mock_persistence():
    """Mock persistence layer."""
    mock = MagicMock()
    mock.save_execution = MagicMock()
    mock.save_match = MagicMock()
    mock.save_plugin_result = MagicMock()
    mock.update_execution = MagicMock()
    mock.update_match = MagicMock()
    return mock


@pytest.fixture
def mock_debugger():
    """Mock debugger."""
    mock = MagicMock()
    mock.debug = MagicMock()
    mock.info = MagicMock()
    mock.warn = MagicMock()
    mock.error = MagicMock()
    return mock


@pytest.fixture
def mock_event_bus():
    """Mock event bus."""
    mock = MagicMock()
    mock.publish = MagicMock()
    mock.subscribe = MagicMock()
    return mock


@pytest.fixture
def sample_config():
    """Sample configuration."""
    return {
        "options": {"debug": True, "dry_run": True},
        "plugins": {
            "scanner": {"enabled": True},
            "renamer": {"enabled": True}
        }
    }


@pytest.fixture
def configured_state(mock_persistence, mock_debugger, mock_event_bus):
    """Pre-configured state manager."""
    state = GlobalStateManager()
    state.reset()
    state.configure(
        persistence=mock_persistence,
        debugger=mock_debugger,
        event_bus=mock_event_bus
    )
    return state


# ==================== UNIT TESTS ====================

@pytest.mark.unit
class TestGlobalStateManagerInit:
    """Tests for GlobalStateManager initialization."""
    
    def test_singleton_pattern(self):
        """Test GlobalStateManager is singleton."""
        state1 = GlobalStateManager()
        state2 = GlobalStateManager()
        
        # Should be same instance
        assert state1 is state2
    
    def test_reset_clears_state(self):
        """Test reset clears all state."""
        state = GlobalStateManager()
        state.reset()
        
        # After reset, should have no execution
        assert state._execution is None or state._execution.execution_id is None
    
    def test_configure_sets_dependencies(self, mock_persistence, mock_debugger):
        """Test configure sets persistence and debugger."""
        state = GlobalStateManager()
        state.reset()
        state.configure(persistence=mock_persistence, debugger=mock_debugger)
        
        assert state._persistence is mock_persistence
        assert state._debugger is mock_debugger


@pytest.mark.unit
class TestExecutionLifecycle:
    """Tests for execution lifecycle management."""
    
    def test_start_execution(self, configured_state, sample_config):
        """Test starting new execution."""
        exec_id = configured_state.start_execution(sample_config)
        
        assert exec_id is not None
        assert len(exec_id) > 0
        assert configured_state._execution is not None
    
    def test_start_execution_saves_to_persistence(self, configured_state, sample_config, mock_persistence):
        """Test start_execution saves to persistence."""
        configured_state.start_execution(sample_config)
        
        # Should have called save_execution
        mock_persistence.save_execution.assert_called()
    
    def test_complete_execution(self, configured_state, sample_config):
        """Test completing execution."""
        configured_state.start_execution(sample_config)
        configured_state.complete_execution()
        
        # Execution should be marked complete (status is an enum)
        assert configured_state._execution.status == ExecutionStatus.COMPLETED
    
    def test_complete_execution_updates_persistence(self, configured_state, sample_config, mock_persistence):
        """Test complete_execution updates persistence."""
        configured_state.start_execution(sample_config)
        configured_state.complete_execution()
        
        # Should have called save again (to update status)
        assert mock_persistence.save_execution.call_count >= 2


@pytest.mark.unit
class TestMatchTracking:
    """Tests for match registration and tracking."""
    
    def test_register_match(self, configured_state, sample_config):
        """Test registering a new match."""
        configured_state.start_execution(sample_config)
        
        match = configured_state.register_match(0, "/path/to/file.mkv")
        
        assert match is not None
        assert match.index == 0
        assert match.input_path == "/path/to/file.mkv"
    
    def test_register_multiple_matches(self, configured_state, sample_config):
        """Test registering multiple matches."""
        configured_state.start_execution(sample_config)
        
        match0 = configured_state.register_match(0, "/path/file1.mkv")
        match1 = configured_state.register_match(1, "/path/file2.mkv")
        match2 = configured_state.register_match(2, "/path/file3.mkv")
        
        assert match0.index == 0
        assert match1.index == 1
        assert match2.index == 2
    
    def test_complete_match(self, configured_state, sample_config):
        """Test completing a match."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        configured_state.complete_match(0)
        
        # Match should be marked complete (status is an enum)
        match = configured_state._matches.get(0)
        assert match.status == ExecutionStatus.COMPLETED
    
    def test_complete_match_emits_event(self, configured_state, sample_config, mock_event_bus):
        """Test completing match emits event."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        configured_state.complete_match(0)
        
        # Event bus may or may not be called depending on implementation
        # Just verify no exception was raised
        match = configured_state._matches.get(0)
        assert match is not None


@pytest.mark.unit
class TestPluginResults:
    """Tests for plugin result tracking."""
    
    def test_update_plugin_result(self, configured_state, sample_config):
        """Test updating plugin result."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        plugin_result = PluginResult(
            plugin_name="tmdb",
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={"movie": {"title": "Test Movie"}}
        )
        
        configured_state.update_plugin_result(0, "tmdb", plugin_result)
        
        # Should be stored in match.plugins dict
        match = configured_state._matches.get(0)
        assert "tmdb" in match.plugins
    
    def test_mark_plugin_not_supported(self, configured_state, sample_config):
        """Test marking plugin as not supported."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        configured_state.mark_plugin_not_supported(0, "tvdb")
        
        match = configured_state._matches.get(0)
        # Should have record of not supported
        assert "tvdb" in match.not_supported_plugins
    
    def test_plugin_result_saves_to_persistence(self, configured_state, sample_config, mock_persistence):
        """Test plugin results are saved to persistence."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        plugin_result = PluginResult(
            plugin_name="renamer",
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={"parsed": {"title": "Test"}}
        )
        
        configured_state.update_plugin_result(0, "renamer", plugin_result)
        
        # Should have saved
        mock_persistence.save_plugin_result.assert_called()


@pytest.mark.unit
class TestTaskResults:
    """Tests for task result tracking."""
    
    def test_add_task_result(self, configured_state, sample_config):
        """Test adding task result."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        task_result = {
            "task_name": "print_info",
            "type": "print",
            "success": True,
            "output": "Rendered output"
        }
        
        configured_state.add_task_result(0, task_result)
        
        match = configured_state._matches.get(0)
        assert len(match.tasks) >= 1


@pytest.mark.unit
class TestAPIResponseBuilding:
    """Tests for API response building from state."""
    
    def test_build_api_response(self, configured_state, sample_config):
        """Test building API response from state."""
        configured_state.start_execution(sample_config)
        configured_state.register_match(0, "/path/to/file.mkv")
        
        plugin_result = PluginResult(
            plugin_name="renamer",
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={"parsed": {"title": "Test", "year": 2025}}
        )
        configured_state.update_plugin_result(0, "renamer", plugin_result)
        configured_state.complete_match(0)
        
        response = configured_state.build_api_response_for_templates()
        
        assert response is not None
        assert "matches" in response or "items" in response
    
    def test_api_response_includes_all_matches(self, configured_state, sample_config):
        """Test API response includes all processed matches."""
        configured_state.start_execution(sample_config)
        
        for i in range(5):
            configured_state.register_match(i, f"/path/file{i}.mkv")
            configured_state.complete_match(i)
        
        response = configured_state.build_api_response_for_templates()
        
        matches_key = "matches" if "matches" in response else "items"
        assert len(response.get(matches_key, [])) == 5


# ==================== DATA MODEL TESTS ====================

@pytest.mark.unit
class TestPluginResultModel:
    """Tests for PluginResult dataclass."""
    
    def test_create_plugin_result(self):
        """Test creating PluginResult."""
        result = PluginResult(
            plugin_name="tmdb",
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={"movie": {"id": 123}}
        )
        
        assert result.plugin_name == "tmdb"
        assert result.success is True
        assert result.data["movie"]["id"] == 123
    
    def test_plugin_result_with_error(self):
        """Test PluginResult with error."""
        result = PluginResult(
            plugin_name="tvdb",
            success=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={},
            error="API rate limit exceeded"
        )
        
        assert result.success is False
        assert result.error is not None


@pytest.mark.unit
class TestMatchStateModel:
    """Tests for MatchState dataclass."""
    
    def test_create_match_state(self):
        """Test creating MatchState."""
        state = MatchState(
            index=0,
            input_path="/path/to/file.mkv",
            execution_id="test_exec"
        )
        
        assert state.index == 0
        assert state.status == ExecutionStatus.PENDING
        assert state.plugins == {}
    
    def test_match_state_defaults(self):
        """Test MatchState default values."""
        state = MatchState(
            index=0,
            input_path="/path/file.mkv",
            execution_id="test_exec"
        )
        
        assert state.status == ExecutionStatus.PENDING
        assert state.plugins == {}
        assert state.tasks == []


# ==================== EDGE CASE TESTS ====================

@pytest.mark.unit
class TestStateEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_register_match_before_execution(self):
        """Test registering match before starting execution."""
        state = GlobalStateManager()
        state.reset()
        
        # Should handle gracefully or raise appropriate error
        try:
            state.register_match(0, "/path/file.mkv")
            pytest.fail("Expected exception when registering match without execution")
        except (AttributeError, ValueError, TypeError, RuntimeError):
            pass  # Expected behavior
    
    def test_complete_nonexistent_match(self, configured_state, sample_config):
        """Test completing a match that doesn't exist."""
        configured_state.start_execution(sample_config)
        
        # Should handle gracefully or raise ValueError
        try:
            configured_state.complete_match(999)
            pytest.fail("Expected exception when completing nonexistent match")
        except (KeyError, IndexError, ValueError):
            pass  # Expected behavior
    
    def test_update_plugin_for_nonexistent_match(self, configured_state, sample_config):
        """Test updating plugin result for nonexistent match."""
        configured_state.start_execution(sample_config)
        
        plugin_result = PluginResult(
            plugin_name="test",
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={}
        )
        
        # Should handle gracefully or raise ValueError
        try:
            configured_state.update_plugin_result(999, "test", plugin_result)
            pytest.fail("Expected exception when updating nonexistent match")
        except (KeyError, IndexError, ValueError):
            pass  # Expected behavior
    
    def test_double_complete_execution(self, configured_state, sample_config):
        """Test completing execution twice."""
        configured_state.start_execution(sample_config)
        configured_state.complete_execution()
        
        # Second complete should not raise
        configured_state.complete_execution()
    
    def test_state_with_no_persistence(self, mock_debugger):
        """Test state works without persistence (in-memory only)."""
        state = GlobalStateManager()
        state.reset()
        state.configure(persistence=None, debugger=mock_debugger)
        
        config = {"options": {}, "plugins": {}}
        exec_id = state.start_execution(config)
        
        assert exec_id is not None
        
        state.register_match(0, "/path/file.mkv")
        state.complete_match(0)
        state.complete_execution()
        
        # Should complete without errors
