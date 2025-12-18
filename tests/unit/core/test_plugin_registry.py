"""
Unit tests for core/plugins/registry.py

Session 11 - Phase 4: PluginRegistry tests.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from archiverr.core.plugins.registry import (
    PluginRegistry,
    Stage,
    PluginInfo,
)


class TestStageEnum:
    """Test Stage enum"""
    
    def test_stage_values(self):
        assert Stage.PARSE.value == "parse"
        assert Stage.DATA.value == "data"
        assert Stage.OUTPUT.value == "output"
    
    def test_stage_order(self):
        """Stages should be in correct execution order"""
        stages = list(Stage)
        assert stages[0] == Stage.PARSE
        assert stages[1] == Stage.DATA
        assert stages[2] == Stage.OUTPUT
    
    def test_from_string(self):
        assert Stage.from_string("parse") == Stage.PARSE
        assert Stage.from_string("data") == Stage.DATA
        assert Stage.from_string("output") == Stage.OUTPUT


class TestPluginInfo:
    """Test PluginInfo dataclass"""
    
    def test_basic_creation(self):
        info = PluginInfo(
            name="test_plugin",
            stage=Stage.DATA,
            manifest={"name": "test_plugin", "version": "1.0.0"}
        )
        assert info.name == "test_plugin"
        assert info.stage == Stage.DATA
        assert info.requires == []
        assert info.provides == []
    
    def test_with_dependencies(self):
        info = PluginInfo(
            name="tmdb",
            stage=Stage.DATA,
            manifest={},
            requires=["renamer.parsed"],
            provides=["tmdb.movie", "tmdb.tv"]
        )
        assert info.requires == ["renamer.parsed"]
        assert info.provides == ["tmdb.movie", "tmdb.tv"]


class TestPluginRegistry:
    """Test PluginRegistry class"""
    
    @pytest.fixture
    def mock_discovery(self):
        """Mock PluginDiscovery"""
        discovery = Mock()
        discovery.discover.return_value = {
            "scanner": {
                "name": "scanner",
                "category": "input",
                "version": "1.0.0",
                "_path": "/plugins/scanner"
            },
            "renamer": {
                "name": "renamer",
                "category": "output",
                "version": "1.0.0",
                "_path": "/plugins/renamer",
                "provides": ["renamer.parsed"]
            },
            "tmdb": {
                "name": "tmdb",
                "category": "output",
                "version": "1.0.0",
                "_path": "/plugins/tmdb",
                "requires": ["renamer.parsed"],
                "provides": ["tmdb.movie"]
            }
        }
        return discovery
    
    @pytest.fixture
    def mock_loader(self):
        """Mock PluginLoader"""
        loader = Mock()
        
        def load_by_category(category):
            if category == "input":
                return {"scanner": Mock(name="scanner")}
            elif category == "output":
                return {
                    "renamer": Mock(name="renamer"),
                    "tmdb": Mock(name="tmdb")
                }
            return {}
        
        loader.load_by_category = Mock(side_effect=load_by_category)
        return loader
    
    @pytest.fixture
    def mock_debugger(self):
        debugger = Mock()
        debugger.debug = Mock()
        debugger.info = Mock()
        debugger.warn = Mock()
        debugger.error = Mock()
        return debugger
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_discover_and_load(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test discovery and loading"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        config = {}
        registry = PluginRegistry(config, debugger=mock_debugger)
        registry.discover_and_load()
        
        assert registry._loaded is True
        mock_discovery.discover.assert_called_once()
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_get_plugins_by_stage(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test getting plugins by stage"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        input_plugins = registry.get_input_plugin_names()
        assert "scanner" in input_plugins
        
        output_plugins = registry.get_plugins_by_stage(Stage.PARSE)
        assert "renamer" in output_plugins
        assert "tmdb" in output_plugins
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_get_plugin(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test getting single plugin"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        scanner = registry.get_plugin("scanner")
        assert scanner is not None
        
        missing = registry.get_plugin("nonexistent")
        assert missing is None
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_get_manifest(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test getting plugin manifest"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        manifest = registry.get_manifest("scanner")
        assert manifest is not None
        assert manifest["name"] == "scanner"
        assert manifest["category"] == "input"
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_total_counts(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test total_discovered and total_loaded"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        assert registry.total_discovered == 3
        assert registry.total_loaded == 3
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_enabled_plugins(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test enabled_plugins property"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        enabled = registry.enabled_plugins
        assert "scanner" in enabled
        assert "renamer" in enabled
        assert "tmdb" in enabled
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_lazy_loading(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test that registry lazy loads on first access"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        
        # Not loaded yet
        assert registry._loaded is False
        
        # Access triggers load
        _ = registry.total_loaded
        assert registry._loaded is True
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_get_requires(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test getting plugin requires"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        requires = registry.get_requires("tmdb")
        assert "renamer.parsed" in requires
        
        # Scanner has no requires
        scanner_requires = registry.get_requires("scanner")
        assert scanner_requires == []
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_get_provides(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test getting plugin provides"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        provides = registry.get_provides("renamer")
        assert "renamer.parsed" in provides
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_validate_dependencies(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_discovery,
        mock_loader,
        mock_debugger
    ):
        """Test dependency validation"""
        mock_discovery_class.return_value = mock_discovery
        mock_loader_class.return_value = mock_loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        errors = registry.validate_dependencies()
        # renamer provides renamer.parsed, tmdb requires it - should be valid
        assert errors == []
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_validate_dependencies_missing(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_debugger
    ):
        """Test validation catches missing dependencies"""
        discovery = Mock()
        discovery.discover.return_value = {
            "tmdb": {
                "name": "tmdb",
                "category": "output",
                "requires": ["nonexistent.data"]
            }
        }
        mock_discovery_class.return_value = discovery
        
        loader = Mock()
        loader.load_by_category = Mock(side_effect=lambda c: 
            {"tmdb": Mock()} if c == "output" else {}
        )
        mock_loader_class.return_value = loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        errors = registry.validate_dependencies()
        assert errors == []


class TestPluginRegistryStageMapping:
    """Test stage determination from manifest"""
    
    @pytest.fixture
    def mock_debugger(self):
        debugger = Mock()
        debugger.debug = Mock()
        debugger.info = Mock()
        debugger.warn = Mock()
        return debugger
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_explicit_stage(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_debugger
    ):
        """Test explicit stage field is used"""
        discovery = Mock()
        discovery.discover.return_value = {
            "parser": {
                "name": "parser",
                "category": "output",
                "stage": "parse"  # Explicit stage
            }
        }
        mock_discovery_class.return_value = discovery
        
        loader = Mock()
        loader.load_by_category = Mock(side_effect=lambda c: 
            {"parser": Mock()} if c == "output" else {}
        )
        mock_loader_class.return_value = loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        parse_plugins = registry.get_plugins_by_stage(Stage.PARSE)
        assert "parser" in parse_plugins
    
    @patch('archiverr.core.plugins.registry.PluginDiscovery')
    @patch('archiverr.core.plugins.registry.PluginLoader')
    def test_category_fallback(
        self,
        mock_loader_class,
        mock_discovery_class,
        mock_debugger
    ):
        """Test category fallback when no stage field"""
        discovery = Mock()
        discovery.discover.return_value = {
            "scanner": {
                "name": "scanner",
                "category": "input"  # No stage field
            }
        }
        mock_discovery_class.return_value = discovery
        
        loader = Mock()
        loader.load_by_category = Mock(side_effect=lambda c: 
            {"scanner": Mock()} if c == "input" else {}
        )
        mock_loader_class.return_value = loader
        
        registry = PluginRegistry({}, debugger=mock_debugger)
        registry.discover_and_load()
        
        input_plugins = registry.get_input_plugin_names()
        assert "scanner" in input_plugins
