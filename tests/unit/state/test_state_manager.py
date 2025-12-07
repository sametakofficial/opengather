"""
State Manager Unit Tests

Tests GlobalStateManager WITHOUT real plugins.
Uses generic plugin names and mock persistence.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock


class TestGlobalStateManagerLifecycle:
    """State manager lifecycle tests"""
    
    @pytest.fixture
    def state_manager(self):
        """Get fresh state manager instance."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        return manager
    
    @pytest.fixture
    def mock_persistence(self):
        """Create mock persistence."""
        mock = MagicMock()
        mock.save_execution = MagicMock()
        mock.save_match = MagicMock()
        mock.save_plugin_result = MagicMock()
        mock.update_execution = MagicMock()
        mock.update_match = MagicMock()
        return mock
    
    @pytest.fixture
    def sample_config(self):
        """Sample config without real plugin names."""
        return {
            "options": {"debug": False, "dry_run": True},
            "plugins": {
                "generic_input": {"enabled": True},
                "generic_output": {"enabled": True}
            }
        }
    
    def test_di_creates_separate_instances(self, state_manager):
        """Test DI pattern creates separate instances (no singleton)."""
        from archiverr.state import StateManager
        
        manager1 = StateManager()
        manager2 = StateManager()
        
        # Each call creates a new instance (DI pattern)
        assert manager1 is not manager2
    
    def test_constructor_injection(self):
        """Test dependencies can be injected via constructor."""
        from archiverr.state import StateManager
        from unittest.mock import MagicMock
        
        mock_persistence = MagicMock()
        mock_debugger = MagicMock()
        mock_event_bus = MagicMock()
        
        manager = StateManager(
            persistence=mock_persistence,
            debugger=mock_debugger,
            event_bus=mock_event_bus
        )
        
        assert manager._persistence is mock_persistence
        assert manager._debugger is mock_debugger
        assert manager._event_bus is mock_event_bus
    
    def test_reset_clears_state(self, state_manager, sample_config):
        """Test reset clears all state."""
        state_manager.start_execution(sample_config)
        state_manager.register_match(0, "/path/to/file.mkv")
        
        state_manager.reset()
        
        # Session 11: Use run (not _execution) and _jobs (not _matches)
        assert state_manager.run is None
        assert state_manager._jobs == {}
    
    def test_start_execution_creates_execution_state(self, state_manager, sample_config):
        """Test start_execution creates proper state."""
        exec_id = state_manager.start_execution(sample_config)
        
        assert exec_id is not None
        assert len(exec_id) > 0  # Has an ID
        # Session 11: Use run (not _execution)
        assert state_manager.run is not None
        assert state_manager.run.status.state.value == "running"
    
    def test_complete_execution_updates_status(self, state_manager, sample_config):
        """Test complete_execution sets proper status."""
        state_manager.start_execution(sample_config)
        state_manager.complete_execution()
        
        # Session 11: Use run (not _execution)
        assert state_manager.run.status.state.value == "completed"
        assert state_manager.run.status.finished_at is not None


class TestGlobalStateManagerMatches:
    """Match management tests"""
    
    @pytest.fixture
    def configured_state(self):
        """State manager with execution started."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        manager.start_execution({"options": {}, "plugins": {}})
        return manager
    
    def test_register_match_creates_match_state(self, configured_state):
        """Test register_match creates match."""
        match = configured_state.register_match(0, "/path/to/file.mkv")
        
        assert match is not None
        assert match.index == 0
        assert match.input_path == "/path/to/file.mkv"  # Legacy property works
        # Session 11: Use status.state.value
        assert match.status.state.value in ["pending", "running"]
    
    def test_register_multiple_matches(self, configured_state):
        """Test multiple matches can be registered."""
        configured_state.register_match(0, "/path/file1.mkv")
        configured_state.register_match(1, "/path/file2.mkv")
        configured_state.register_match(2, "/path/file3.mkv")
        
        assert len(configured_state._matches) == 3
        assert 0 in configured_state._matches
        assert 1 in configured_state._matches
        assert 2 in configured_state._matches
    
    def test_complete_match_updates_status(self, configured_state):
        """Test complete_match sets proper status."""
        configured_state.register_match(0, "/path/file.mkv")
        configured_state.complete_match(0)
        
        # Session 11: Use _jobs (not _matches) and status.state.value
        match = configured_state._jobs[0]
        assert match.status.state.value == "completed"


class TestGlobalStateManagerPluginResults:
    """Plugin result management tests - PLUGIN AGNOSTIC"""
    
    @pytest.fixture
    def state_with_match(self):
        """State manager with execution and match."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        manager.start_execution({"options": {}, "plugins": {}})
        manager.register_match(0, "/path/to/file.mkv")
        return manager
    
    def test_update_plugin_result_generic_plugin(self, state_with_match):
        """Test plugin result with GENERIC plugin name."""
        # Session 11: Import PluginResult from archiverr.state (not .models)
        from archiverr.state import PluginResult
        
        # Use generic plugin name - NOT real plugin names
        # Session 11: PluginResult is Pydantic model without plugin_name
        result = PluginResult(
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={"key": "value", "nested": {"a": 1}}
        )
        
        state_with_match.update_plugin_result(0, "generic_plugin", result)
        
        # Session 11: Use _jobs (not _matches)
        match = state_with_match._jobs[0]
        assert "generic_plugin" in match.plugins
    
    def test_update_multiple_plugin_results(self, state_with_match):
        """Test multiple plugins can update same match."""
        # Session 11: Import PluginResult from archiverr.state
        from archiverr.state import PluginResult
        
        # Multiple generic plugins
        for plugin_name in ["plugin_a", "plugin_b", "plugin_c"]:
            # Session 11: PluginResult without plugin_name field
            result = PluginResult(
                success=True,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                data={f"{plugin_name}_data": True}
            )
            state_with_match.update_plugin_result(0, plugin_name, result)
        
        # Session 11: Use _jobs (not _matches)
        match = state_with_match._jobs[0]
        assert len(match.plugins) == 3
        assert "plugin_a" in match.plugins
        assert "plugin_b" in match.plugins
        assert "plugin_c" in match.plugins
    
    def test_plugin_result_error_handling(self, state_with_match):
        """Test plugin result with error."""
        # Session 11: Import PluginResult from archiverr.state
        from archiverr.state import PluginResult
        
        # Session 11: PluginResult without plugin_name field
        result = PluginResult(
            success=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            error="Something went wrong",
            data={}
        )
        
        state_with_match.update_plugin_result(0, "failing_plugin", result)
        
        # Session 11: Use _jobs (not _matches)
        match = state_with_match._jobs[0]
        # Failed plugin should be in failed list
        assert "failing_plugin" in match.status.failed


class TestGlobalStateManagerPersistence:
    """Persistence integration tests"""
    
    @pytest.fixture
    def mock_persistence(self):
        """Create mock persistence."""
        mock = MagicMock()
        # Session 11: New API uses save_run/save_job
        mock.save_run = MagicMock()
        mock.save_job = MagicMock()
        mock.save_plugin_result = MagicMock()
        mock.save_plugin_data = MagicMock()
        # Legacy methods
        mock.save_execution = MagicMock()
        mock.save_match = MagicMock()
        mock.update_execution = MagicMock()
        mock.update_match = MagicMock()
        return mock
    
    @pytest.fixture
    def state_with_persistence(self, mock_persistence):
        """State manager configured with mock persistence."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        manager.configure(persistence=mock_persistence)
        return manager, mock_persistence
    
    def test_start_execution_saves_to_persistence(self, state_with_persistence):
        """Test execution is saved to persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_execution({"options": {}})
        
        # Session 11: Uses save_run (new API)
        persistence.save_run.assert_called_once()
    
    def test_register_match_saves_to_persistence(self, state_with_persistence):
        """Test match is saved to persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_execution({"options": {}})
        manager.register_match(0, "/path/file.mkv")
        
        # Session 11: Uses save_job (new API)
        persistence.save_job.assert_called_once()
    
    def test_complete_execution_updates_persistence(self, state_with_persistence):
        """Test completion updates persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_execution({"options": {}})
        manager.complete_execution()
        
        # Session 11: Uses save_run (new API), called at start and complete
        assert persistence.save_run.call_count >= 2


class TestGlobalStateManagerTemplateContext:
    """Template context building tests (Session 11: replaces API response tests)"""
    
    @pytest.fixture
    def state_with_data(self):
        """State manager with sample data."""
        from archiverr.state import GlobalStateManager, PluginResult
        
        manager = GlobalStateManager()
        manager.reset()
        manager.start_execution({"options": {"debug": False}})
        
        # Add matches with generic plugin results
        for i in range(3):
            manager.register_match(i, f"/path/file{i}.mkv")
            
            # Session 11: PluginResult without plugin_name
            result = PluginResult(
                success=True,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                data={"index": i, "processed": True}
            )
            manager.update_plugin_result(i, "generic_plugin", result)
            manager.complete_match(i)
        
        manager.complete_execution()
        return manager
    
    def test_build_template_context_structure(self, state_with_data):
        """Test template context has correct structure."""
        # Session 11: Use build_template_context
        context = state_with_data.build_template_context(0)
        
        assert "run" in context
        assert "job" in context
        assert "jobs" in context
    
    def test_template_context_contains_run_info(self, state_with_data):
        """Test context contains run info."""
        context = state_with_data.build_template_context(0)
        
        run_data = context.get("run", {})
        assert "id" in run_data or "status" in run_data
    
    def test_template_context_job_count(self, state_with_data):
        """Test context has correct job count."""
        context = state_with_data.build_template_context(0)
        
        jobs = context.get("jobs", [])
        assert len(jobs) == 3
