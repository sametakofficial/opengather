"""
Plugin Discovery Unit Tests

Tests plugin discovery WITHOUT real plugins.
Uses mock plugin.json files for isolation.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPluginDiscovery:
    """Plugin discovery tests - NO REAL PLUGINS"""
    
    @pytest.fixture
    def mock_plugin_dir(self, tmp_path):
        """Create mock plugin structure for testing."""
        # Create fake plugin 1
        plugin1_dir = tmp_path / "fake_input"
        plugin1_dir.mkdir()
        (plugin1_dir / "plugin.json").write_text(json.dumps({
            "name": "fake_input",
            "version": "1.0.0",
            "category": "input",
            "class_name": "FakeInputPlugin",
            "depends_on": [],
            "expects": []
        }))
        (plugin1_dir / "client.py").write_text('''
class FakeInputPlugin:
    def execute(self, data):
        return {"status": {"success": True}, "matches": []}
''')
        
        # Create fake plugin 2
        plugin2_dir = tmp_path / "fake_output"
        plugin2_dir.mkdir()
        (plugin2_dir / "plugin.json").write_text(json.dumps({
            "name": "fake_output",
            "version": "1.0.0",
            "category": "output",
            "class_name": "FakeOutputPlugin",
            "depends_on": ["fake_input"],
            "expects": ["fake_input.matches"]
        }))
        (plugin2_dir / "client.py").write_text('''
class FakeOutputPlugin:
    def execute(self, data):
        return {"status": {"success": True}, "processed": True}
''')
        
        return tmp_path
    
    @pytest.fixture
    def mock_invalid_plugin_dir(self, tmp_path):
        """Create invalid plugin structure for testing."""
        # Plugin without plugin.json
        invalid_dir = tmp_path / "invalid_plugin"
        invalid_dir.mkdir()
        (invalid_dir / "client.py").write_text("# No plugin.json")
        
        return tmp_path
    
    def test_discovers_plugins_from_directory(self, mock_plugin_dir):
        """Test plugin discovery finds valid plugins."""
        from archiverr.core.plugins import PluginDiscovery
        
        discovery = PluginDiscovery(plugins_dir=str(mock_plugin_dir))
        plugins = discovery.discover()
        
        assert "fake_input" in plugins
        assert "fake_output" in plugins
        assert plugins["fake_input"]["category"] == "input"
        assert plugins["fake_output"]["category"] == "output"
    
    def test_plugin_metadata_parsed_correctly(self, mock_plugin_dir):
        """Test plugin.json metadata is parsed correctly."""
        from archiverr.core.plugins import PluginDiscovery
        
        discovery = PluginDiscovery(plugins_dir=str(mock_plugin_dir))
        plugins = discovery.discover()
        
        input_plugin = plugins["fake_input"]
        assert input_plugin["version"] == "1.0.0"
        assert input_plugin["class_name"] == "FakeInputPlugin"
        assert input_plugin["depends_on"] == []
        
        output_plugin = plugins["fake_output"]
        assert output_plugin["depends_on"] == ["fake_input"]
        assert output_plugin["expects"] == ["fake_input.matches"]
    
    def test_skips_directories_without_plugin_json(self, mock_invalid_plugin_dir):
        """Test discovery skips invalid plugins."""
        from archiverr.core.plugins import PluginDiscovery
        
        discovery = PluginDiscovery(plugins_dir=str(mock_invalid_plugin_dir))
        plugins = discovery.discover()
        
        assert "invalid_plugin" not in plugins
    
    def test_empty_directory_returns_empty_dict(self, tmp_path):
        """Test empty directory returns no plugins."""
        from archiverr.core.plugins import PluginDiscovery
        
        discovery = PluginDiscovery(plugins_dir=str(tmp_path))
        plugins = discovery.discover()
        
        assert plugins == {}
    
    def test_discovers_input_and_output_categories(self, mock_plugin_dir):
        """Test both input and output plugins are discovered."""
        from archiverr.core.plugins import PluginDiscovery
        
        discovery = PluginDiscovery(plugins_dir=str(mock_plugin_dir))
        plugins = discovery.discover()
        
        categories = [p["category"] for p in plugins.values()]
        assert "input" in categories
        assert "output" in categories


class TestPluginLoader:
    """Plugin loader tests - mock based"""
    
    @pytest.fixture
    def mock_plugin_metadata(self):
        """Mock plugin metadata."""
        return {
            "sample_plugin": {
                "name": "sample_plugin",
                "version": "1.0.0",
                "category": "output",
                "class_name": "SamplePlugin",
                "depends_on": [],
                "expects": []
            }
        }
    
    def test_loader_respects_enabled_config(self, mock_plugin_metadata):
        """Test loader respects enabled config."""
        from archiverr.core.plugins import PluginLoader
        
        # Disabled plugin should not be loaded
        config = {
            "plugins": {
                "sample_plugin": {"enabled": False}
            }
        }
        
        loader = PluginLoader(mock_plugin_metadata, config)
        result = loader.load_plugin("sample_plugin")
        
        # Should return None for disabled plugin
        assert result is None
    
    def test_loader_returns_none_for_unknown_plugin(self):
        """Test loader returns None for unknown plugin."""
        from archiverr.core.plugins import PluginLoader
        
        loader = PluginLoader({}, {})
        result = loader.load_plugin("nonexistent")
        
        assert result is None


class TestDependencyResolver:
    """Dependency resolver tests - pure logic"""
    
    def test_resolve_no_dependencies(self):
        """Test resolving plugins with no dependencies."""
        from archiverr.core.plugins import DependencyResolver
        
        plugins = {
            "a": {"name": "a", "depends_on": []},
            "b": {"name": "b", "depends_on": []},
            "c": {"name": "c", "depends_on": []}
        }
        
        resolver = DependencyResolver(plugins)
        groups = resolver.resolve(["a", "b", "c"])
        
        # All can run in parallel (one group)
        assert len(groups) == 1
        assert set(groups[0]) == {"a", "b", "c"}
    
    def test_resolve_with_dependencies(self):
        """Test resolving respects dependencies."""
        from archiverr.core.plugins import DependencyResolver
        
        plugins = {
            "scanner": {"name": "scanner", "depends_on": []},
            "renamer": {"name": "renamer", "depends_on": ["scanner"]},
            "output": {"name": "output", "depends_on": ["renamer"]}
        }
        
        resolver = DependencyResolver(plugins)
        groups = resolver.resolve(["scanner", "renamer", "output"])
        
        # Should be 3 groups in order
        assert len(groups) == 3
        assert groups[0] == ["scanner"]
        assert groups[1] == ["renamer"]
        assert groups[2] == ["output"]
    
    def test_detects_circular_dependency(self):
        """Test circular dependency detection."""
        from archiverr.core.plugins import DependencyResolver
        
        plugins = {
            "a": {"name": "a", "depends_on": ["b"]},
            "b": {"name": "b", "depends_on": ["c"]},
            "c": {"name": "c", "depends_on": ["a"]}  # Circular!
        }
        
        resolver = DependencyResolver(plugins)
        
        with pytest.raises(ValueError, match="[Cc]ircular"):
            resolver.resolve(["a", "b", "c"])
    
    def test_check_expects_satisfied(self):
        """Test expects checking."""
        from archiverr.core.plugins import DependencyResolver
        
        plugins = {
            "output": {
                "name": "output",
                "depends_on": [],
                "expects": ["input", "parsed.title"]
            }
        }
        
        resolver = DependencyResolver(plugins)
        
        # All expects available
        assert resolver.check_expects("output", {"input", "parsed.title", "extra"})
        
        # Missing expect
        assert not resolver.check_expects("output", {"input"})
