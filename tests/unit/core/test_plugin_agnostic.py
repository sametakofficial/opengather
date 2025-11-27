"""
Plugin-Agnostic Core Tests

These tests verify core functionality WITHOUT depending on specific plugin names.
Use mock_input_plugin, mock_output_plugin fixtures instead of real plugins.

This pattern ensures:
1. Core tests don't break when plugins change
2. Tests run fast (no real plugin execution)
3. Plugin-agnostic architecture is maintained
"""

import pytest
from unittest.mock import MagicMock, patch


class TestPluginAgnosticExecution:
    """Test execution flow without real plugins."""
    
    def test_state_manager_with_mock_plugin(self, mock_input_plugin, mock_output_plugin):
        """Test GlobalStateManager works with generic plugin data."""
        from archiverr.state import GlobalStateManager, PluginResult
        
        state = GlobalStateManager()
        state.reset()
        
        # Start execution
        config = {
            "options": {"debug": False},
            "plugins": {
                mock_input_plugin["name"]: {"enabled": True},
                mock_output_plugin["name"]: {"enabled": True}
            }
        }
        
        exec_id = state.start_execution(config)
        assert exec_id is not None
        
        # Register match
        match = state.register_match(0, "/path/test.mkv")
        assert match.index == 0
        
        # Update with mock plugin results (generic names)
        from datetime import datetime
        now = datetime.now()
        
        input_result = PluginResult(
            plugin_name=mock_input_plugin["name"],
            success=True,
            started_at=now,
            finished_at=now,
            duration_ms=10,
            data={"matches": ["/path/test.mkv"]}
        )
        state.update_plugin_result(0, mock_input_plugin["name"], input_result)
        
        output_result = PluginResult(
            plugin_name=mock_output_plugin["name"],
            success=True,
            started_at=now,
            finished_at=now,
            duration_ms=50,
            data={"processed": True}
        )
        state.update_plugin_result(0, mock_output_plugin["name"], output_result)
        
        # Complete
        state.complete_match(0)
        execution = state.complete_execution()
        
        # Verify using generic assertions (no plugin-specific checks)
        assert execution.total_matches == 1
        assert execution.completed_matches == 1
    
    def test_plugin_result_generic_structure(self, mock_output_plugin):
        """Test PluginResult works with any plugin data."""
        from archiverr.state import PluginResult
        from datetime import datetime
        
        now = datetime.now()
        
        # Plugin-agnostic: use data from fixture, not hardcoded
        result = PluginResult(
            plugin_name=mock_output_plugin["name"],
            success=True,
            started_at=now,
            finished_at=now,
            duration_ms=100,
            data=mock_output_plugin["execute_result"]["data"]
        )
        
        assert result.success is True
        assert result.duration_ms == 100
        assert "title" in result.data
    
    def test_match_state_plugins_are_generic(self, mock_match_data):
        """Test MatchState plugins dict is plugin-agnostic."""
        from archiverr.state.models import MatchState
        
        match = MatchState(
            index=mock_match_data["index"],
            input_path=mock_match_data["input_path"],
            execution_id="test-123"
        )
        
        # Add plugins using generic names from fixture
        for plugin_name, plugin_data in mock_match_data["plugins"].items():
            match.plugins[plugin_name] = plugin_data
        
        # Verify generically
        assert len(match.plugins) == 2
        for plugin_name in mock_match_data["plugins"]:
            assert plugin_name in match.plugins


class TestPluginAgnosticConfiguration:
    """Test configuration without hardcoded plugin names."""
    
    def test_config_with_mock_plugins(self, mock_plugin_config):
        """Test config structure is plugin-agnostic."""
        assert "options" in mock_plugin_config
        assert "plugins" in mock_plugin_config
        
        # Don't assert specific plugin names exist
        # Instead verify the structure
        for plugin_name, plugin_conf in mock_plugin_config["plugins"].items():
            assert "enabled" in plugin_conf
    
    def test_config_plugins_are_dictionaries(self, mock_plugin_config):
        """Test all plugin configs are valid dictionaries."""
        for plugin_name, plugin_conf in mock_plugin_config["plugins"].items():
            assert isinstance(plugin_conf, dict)
            assert isinstance(plugin_name, str)


class TestPluginAgnosticMetadata:
    """Test plugin metadata handling without specific plugins."""
    
    def test_metadata_has_required_fields(self, mock_plugin_metadata):
        """Test plugin metadata structure."""
        for category, metadata in mock_plugin_metadata.items():
            assert "name" in metadata
            assert "version" in metadata
            assert "category" in metadata
            assert "class_name" in metadata
            assert "depends_on" in metadata
            assert "expects" in metadata
    
    def test_input_plugin_has_no_dependencies(self, mock_plugin_metadata):
        """Test input plugins typically have no dependencies."""
        input_meta = mock_plugin_metadata["input"]
        assert input_meta["category"] == "input"
        assert input_meta["depends_on"] == []
    
    def test_output_plugin_depends_on_input(self, mock_plugin_metadata):
        """Test output plugins depend on input plugins."""
        output_meta = mock_plugin_metadata["output"]
        assert output_meta["category"] == "output"
        assert len(output_meta["depends_on"]) > 0


class TestPluginAgnosticDiscovery:
    """Test plugin discovery with mock data."""
    
    def test_dependency_resolver_with_mock_plugins(self, mock_plugin_metadata):
        """Test DependencyResolver works with any plugin structure."""
        from archiverr.core.plugins.resolver import DependencyResolver
        
        # Build plugins dict from mock metadata
        plugins = {
            mock_plugin_metadata["input"]["name"]: mock_plugin_metadata["input"],
            mock_plugin_metadata["output"]["name"]: mock_plugin_metadata["output"]
        }
        
        resolver = DependencyResolver(plugins)
        enabled = list(plugins.keys())
        groups = resolver.resolve(enabled)
        
        # Generic assertions: groups are lists, dependencies respected
        assert isinstance(groups, list)
        assert len(groups) > 0
        
        # Input should come before output (no specific plugin name check)
        input_name = mock_plugin_metadata["input"]["name"]
        output_name = mock_plugin_metadata["output"]["name"]
        
        input_index = None
        output_index = None
        
        for i, group in enumerate(groups):
            if input_name in group:
                input_index = i
            if output_name in group:
                output_index = i
        
        assert input_index is not None, "Input plugin not found in groups"
        assert output_index is not None, "Output plugin not found in groups"
        assert input_index <= output_index, "Input should execute before output"


class TestNoHardcodedPluginNames:
    """Verify tests don't use hardcoded plugin names."""
    
    FORBIDDEN_PLUGIN_NAMES = ["scanner", "renamer", "tmdb", "tvdb", "omdb", "ffprobe", "tvmaze"]
    
    def test_mock_input_has_generic_name(self, mock_input_plugin):
        """Test mock_input_plugin doesn't use real plugin name."""
        assert mock_input_plugin["name"] not in self.FORBIDDEN_PLUGIN_NAMES
    
    def test_mock_output_has_generic_name(self, mock_output_plugin):
        """Test mock_output_plugin doesn't use real plugin name."""
        assert mock_output_plugin["name"] not in self.FORBIDDEN_PLUGIN_NAMES
    
    def test_mock_match_data_uses_generic_names(self, mock_match_data):
        """Test mock_match_data doesn't use real plugin names."""
        for plugin_name in mock_match_data["plugins"]:
            assert plugin_name not in self.FORBIDDEN_PLUGIN_NAMES
