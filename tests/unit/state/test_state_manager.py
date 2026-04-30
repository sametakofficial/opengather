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
        mock.save_run = MagicMock()
        mock.save_job = MagicMock()
        mock.save_plugin = MagicMock()
        mock.update_plugin_doc = MagicMock()
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
        state_manager.start_run(sample_config)
        state_manager.create_job("/path/to/file.mkv")
        
        state_manager.reset()
        
        # Session 11: Use run (not _execution) and jobs (not _matches)
        assert state_manager.run is None
        assert state_manager.jobs == []
    
    def test_start_run_creates_run_state(self, state_manager, sample_config):
        """Test start_run creates proper state."""
        run_id = state_manager.start_run(sample_config)
        
        assert run_id is not None
        assert len(run_id) > 0  # Has an ID
        # Session 11: Use run (not _execution)
        assert state_manager.run is not None
        assert state_manager.run.status.state.value == "running"
    
    def test_complete_run_updates_status(self, state_manager, sample_config):
        """Test complete_run sets proper status."""
        state_manager.start_run(sample_config)
        state_manager.complete_run()
        
        # Session 11: Use run (not _execution)
        assert state_manager.run.status.state.value in ["completed", "success"]
        assert state_manager.run.status.finished_at is not None


class TestGlobalStateManagerJobs:
    """Job management tests"""
    
    @pytest.fixture
    def configured_state(self):
        """State manager with execution started."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        manager.start_run({"options": {}, "plugins": {}})
        return manager
    
    def test_create_job_creates_job_state(self, configured_state):
        """Test create_job creates job."""
        job_id = configured_state.create_job("/path/to/file.mkv")
        
        assert job_id is not None
        job = configured_state.get_job(0)
        assert job is not None
        assert job.index == 0
        assert job.input.value == "/path/to/file.mkv"
        # Session 11: Use status.state.value
        assert job.status.state.value in ["pending", "running"]
    
    def test_create_multiple_jobs(self, configured_state):
        """Test multiple jobs can be registered."""
        configured_state.create_job("/path/file1.mkv")
        configured_state.create_job("/path/file2.mkv")
        configured_state.create_job("/path/file3.mkv")
        
        assert len(configured_state.jobs) == 3
        assert configured_state.get_job(0) is not None
        assert configured_state.get_job(1) is not None
        assert configured_state.get_job(2) is not None
    
    def test_complete_job_updates_status(self, configured_state):
        """Test complete_job sets proper status."""
        configured_state.create_job("/path/file.mkv")
        configured_state.complete_job(0)
        
        # Session 11: Use jobs (not _matches) and status.state.value
        job = configured_state.get_job(0)
        assert job.status.state.value in ["completed", "success"]


class TestGlobalStateManagerPluginResults:
    """Plugin result management tests - PLUGIN AGNOSTIC"""
    
    @pytest.fixture
    def state_with_match(self):
        """State manager with execution and match."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        manager.start_run({"options": {}, "plugins": {}})
        manager.create_job("/path/to/file.mkv")
        return manager
    
    def test_update_plugin_generic_plugin(self, state_with_match):
        """Test plugin data write via canonical update_plugin path."""
        # Plugin data flows: services.update_plugin -> GlobalStateManager.update_plugin
        # -> PluginDataManager.update_plugin -> _update_job_plugin -> save_plugin
        job = state_with_match.get_job(0)
        state_with_match.update_plugin(job.id, "generic_plugin", {"key": "value", "nested": {"a": 1}})

        assert "generic_plugin" in job.plugins
        assert job.plugins["generic_plugin"]["key"] == "value"

    def test_update_multiple_plugins(self, state_with_match):
        """Test multiple plugins write to the same job via update_plugin."""
        job = state_with_match.get_job(0)
        for plugin_name in ["plugin_a", "plugin_b", "plugin_c"]:
            state_with_match.update_plugin(job.id, plugin_name, {f"{plugin_name}_data": True})

        assert len(job.plugins) == 3
        assert "plugin_a" in job.plugins
        assert "plugin_b" in job.plugins
        assert "plugin_c" in job.plugins

    def test_update_plugin_with_empty_data(self, state_with_match):
        """Test update_plugin handles error/empty data scenario."""
        job = state_with_match.get_job(0)
        # Plugins record their own success/failure via job.status.plugins;
        # update_plugin only writes the data payload.
        state_with_match.update_plugin(job.id, "failing_plugin", {})

        assert "failing_plugin" in job.plugins
        assert job.plugins["failing_plugin"] == {}


class TestGlobalStateManagerPersistence:
    """Persistence integration tests"""
    
    @pytest.fixture
    def mock_persistence(self):
        """Create mock persistence."""
        mock = MagicMock()
        mock.save_run = MagicMock()
        mock.save_job = MagicMock()
        mock.save_plugin = MagicMock()
        mock.update_plugin_doc = MagicMock()
        return mock
    
    @pytest.fixture
    def state_with_persistence(self, mock_persistence):
        """State manager configured with mock persistence."""
        from archiverr.state import GlobalStateManager
        manager = GlobalStateManager()
        manager.reset()
        manager.configure(persistence=mock_persistence)
        return manager, mock_persistence
    
    def test_start_run_saves_to_persistence(self, state_with_persistence):
        """Test run is saved to persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_run({"options": {}})
        
        # Session 11: Uses save_run (new API)
        persistence.save_run.assert_called_once()
    
    def test_create_job_saves_to_persistence(self, state_with_persistence):
        """Test job is saved to persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_run({"options": {}})
        manager.create_job("/path/file.mkv")
        
        # Session 11: Uses save_job (new API)
        persistence.save_job.assert_called_once()
    
    def test_complete_run_updates_persistence(self, state_with_persistence):
        """Test completion updates persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_run({"options": {}})
        manager.complete_run()
        
        # Session 11: Uses save_run (new API), called at start and complete
        assert persistence.save_run.call_count >= 2


class TestGlobalStateManagerTemplateContext:
    """Template context building tests (Session 11: replaces API response tests)"""
    
    @pytest.fixture
    def state_with_data(self):
        """State manager with sample data."""
        from archiverr.state import GlobalStateManager

        manager = GlobalStateManager()
        manager.reset()
        manager.start_run({"options": {"debug": False}})

        # Add jobs with generic plugin data via canonical update_plugin path
        for i in range(3):
            manager.create_job(f"/path/file{i}.mkv")
            job = manager.get_job(i)
            manager.update_plugin(job.id, "generic_plugin", {"index": i, "processed": True})
            manager.complete_job(i)

        manager.complete_run()
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
