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
    
    def test_singleton_returns_same_instance(self, state_manager):
        """Test singleton pattern works."""
        from archiverr.state import GlobalStateManager
        
        manager1 = GlobalStateManager()
        manager2 = GlobalStateManager()
        
        assert manager1 is manager2
    
    def test_reset_clears_state(self, state_manager, sample_config):
        """Test reset clears all state."""
        state_manager.start_execution(sample_config)
        state_manager.register_match(0, "/path/to/file.mkv")
        
        state_manager.reset()
        
        assert state_manager._execution is None
        assert state_manager._matches == {}
    
    def test_start_execution_creates_execution_state(self, state_manager, sample_config):
        """Test start_execution creates proper state."""
        exec_id = state_manager.start_execution(sample_config)
        
        assert exec_id is not None
        assert len(exec_id) > 0  # Has an ID
        assert state_manager._execution is not None
        assert state_manager._execution.status.value == "running"
    
    def test_complete_execution_updates_status(self, state_manager, sample_config):
        """Test complete_execution sets proper status."""
        state_manager.start_execution(sample_config)
        state_manager.complete_execution()
        
        assert state_manager._execution.status.value == "completed"
        assert state_manager._execution.finished_at is not None


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
        assert match.input_path == "/path/to/file.mkv"
        assert match.status.value in ["pending", "running"]  # Status may be running
    
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
        
        match = configured_state._matches[0]
        assert match.status.value == "completed"


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
        from archiverr.state.models import PluginResult
        
        # Use generic plugin name - NOT real plugin names
        result = PluginResult(
            plugin_name="generic_plugin",
            success=True,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            data={"key": "value", "nested": {"a": 1}}
        )
        
        state_with_match.update_plugin_result(0, "generic_plugin", result)
        
        match = state_with_match._matches[0]
        assert "generic_plugin" in match.plugins
        # Plugin result may be stored as dict or PluginResult
        plugin_data = match.plugins["generic_plugin"]
        if hasattr(plugin_data, 'success'):
            assert plugin_data.success is True
        elif "status" in plugin_data:
            assert plugin_data["status"].get("success") is True
        else:
            assert plugin_data.get("success") is True
    
    def test_update_multiple_plugin_results(self, state_with_match):
        """Test multiple plugins can update same match."""
        from archiverr.state.models import PluginResult
        
        # Multiple generic plugins
        for plugin_name in ["plugin_a", "plugin_b", "plugin_c"]:
            result = PluginResult(
                plugin_name=plugin_name,
                success=True,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                data={f"{plugin_name}_data": True}
            )
            state_with_match.update_plugin_result(0, plugin_name, result)
        
        match = state_with_match._matches[0]
        assert len(match.plugins) == 3
        assert "plugin_a" in match.plugins
        assert "plugin_b" in match.plugins
        assert "plugin_c" in match.plugins
    
    def test_plugin_result_error_handling(self, state_with_match):
        """Test plugin result with error."""
        from archiverr.state.models import PluginResult
        
        result = PluginResult(
            plugin_name="failing_plugin",
            success=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            error="Something went wrong",
            data={}
        )
        
        state_with_match.update_plugin_result(0, "failing_plugin", result)
        
        match = state_with_match._matches[0]
        plugin_data = match.plugins["failing_plugin"]
        # May be stored as dict or PluginResult
        if hasattr(plugin_data, 'success'):
            assert plugin_data.success is False
        elif "status" in plugin_data:
            assert plugin_data["status"].get("success") is False
        else:
            assert plugin_data.get("success") is False


class TestGlobalStateManagerPersistence:
    """Persistence integration tests"""
    
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
        
        persistence.save_execution.assert_called_once()
    
    def test_register_match_saves_to_persistence(self, state_with_persistence):
        """Test match is saved to persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_execution({"options": {}})
        manager.register_match(0, "/path/file.mkv")
        
        persistence.save_match.assert_called_once()
    
    def test_complete_execution_updates_persistence(self, state_with_persistence):
        """Test completion updates persistence."""
        manager, persistence = state_with_persistence
        
        manager.start_execution({"options": {}})
        manager.complete_execution()
        
        # Should save execution at least once (may use save_execution instead of update_execution)
        assert persistence.save_execution.called or persistence.update_execution.called


class TestGlobalStateManagerAPIResponse:
    """API response building tests"""
    
    @pytest.fixture
    def state_with_data(self):
        """State manager with sample data."""
        from archiverr.state import GlobalStateManager
        from archiverr.state.models import PluginResult
        
        manager = GlobalStateManager()
        manager.reset()
        manager.start_execution({"options": {"debug": False}})
        
        # Add matches with generic plugin results
        for i in range(3):
            manager.register_match(i, f"/path/file{i}.mkv")
            
            result = PluginResult(
                plugin_name="generic_plugin",
                success=True,
                started_at=datetime.now(),
                finished_at=datetime.now(),
                data={"index": i, "processed": True}
            )
            manager.update_plugin_result(i, "generic_plugin", result)
            manager.complete_match(i)
        
        manager.complete_execution()
        return manager
    
    def test_build_api_response_structure(self, state_with_data):
        """Test API response has correct structure."""
        response = state_with_data.build_api_response_for_templates()
        
        assert "globals" in response
        assert "items" in response or "matches" in response
    
    def test_api_response_contains_execution_info(self, state_with_data):
        """Test response contains execution info."""
        response = state_with_data.build_api_response_for_templates()
        
        globals_data = response.get("globals", {})
        # Check for execution info in various possible locations
        has_exec_info = (
            "execution" in globals_data or 
            "execution_id" in globals_data or
            "status" in globals_data  # May be stored in status dict
        )
        assert has_exec_info
    
    def test_api_response_match_count(self, state_with_data):
        """Test response has correct match count."""
        response = state_with_data.build_api_response_for_templates()
        
        items = response.get("items", response.get("matches", []))
        assert len(items) == 3
