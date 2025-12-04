"""
PluginServices Unit Tests

Tests for Session 11 plugin services dependency injection system.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any


class TestConfigService:
    """ConfigService implementation tests"""
    
    def test_get_simple_key(self):
        """Test getting simple config key"""
        from archiverr.core.services import ConfigServiceImpl
        
        config = {"debug": True, "dry_run": False}
        service = ConfigServiceImpl(config)
        
        assert service.get("debug") is True
        assert service.get("dry_run") is False
    
    def test_get_with_dot_notation(self):
        """Test getting nested config with dot notation"""
        from archiverr.core.services import ConfigServiceImpl
        
        config = {
            "options": {
                "debug": True,
                "nested": {"value": 42}
            }
        }
        service = ConfigServiceImpl(config)
        
        assert service.get("options.debug") is True
        assert service.get("options.nested.value") == 42
    
    def test_get_with_default(self):
        """Test get returns default for missing keys"""
        from archiverr.core.services import ConfigServiceImpl
        
        config = {"exists": "value"}
        service = ConfigServiceImpl(config)
        
        assert service.get("missing") is None
        assert service.get("missing", "default") == "default"
        assert service.get("exists.nested", "default") == "default"
    
    def test_get_plugin(self):
        """Test getting plugin configuration"""
        from archiverr.core.services import ConfigServiceImpl
        
        config = {
            "tmdb": {"api_key": "xxx", "language": "en"},
            "renamer": {"pattern": "movie"}
        }
        service = ConfigServiceImpl(config)
        
        tmdb_config = service.get_plugin("tmdb")
        assert tmdb_config["api_key"] == "xxx"
        assert tmdb_config["language"] == "en"
        
        # Non-existent plugin returns empty dict
        assert service.get_plugin("unknown") == {}
    
    def test_get_option(self):
        """Test getting from options section"""
        from archiverr.core.services import ConfigServiceImpl
        
        config = {"options": {"debug": True, "dry_run": False}}
        service = ConfigServiceImpl(config)
        
        assert service.get_option("debug") is True
        assert service.get_option("dry_run") is False
        assert service.get_option("missing", "default") == "default"
    
    def test_get_alias(self):
        """Test getting alias definitions"""
        from archiverr.core.services import ConfigServiceImpl
        
        config = {
            "aliases": {
                "m": "job.plugins.tmdb.movie",
                "movie": "job.plugins.renamer.parsed.movie"
            }
        }
        service = ConfigServiceImpl(config)
        
        assert service.get_alias("m") == "job.plugins.tmdb.movie"
        assert service.get_alias("unknown") == ""


class TestLoggerService:
    """LoggerService implementation tests"""
    
    def test_log_methods_exist(self):
        """Test all log methods exist"""
        from archiverr.core.services import LoggerServiceImpl
        
        mock_debugger = Mock()
        service = LoggerServiceImpl(mock_debugger, "test_plugin")
        
        assert hasattr(service, 'debug')
        assert hasattr(service, 'info')
        assert hasattr(service, 'warn')
        assert hasattr(service, 'error')
    
    def test_debug_calls_debugger(self):
        """Test debug calls underlying debugger"""
        from archiverr.core.services import LoggerServiceImpl
        
        mock_debugger = Mock()
        service = LoggerServiceImpl(mock_debugger, "test_plugin")
        
        service.debug("Test message", key="value")
        
        mock_debugger.debug.assert_called_once_with("test_plugin", "Test message", key="value")
    
    def test_info_calls_debugger(self):
        """Test info calls underlying debugger"""
        from archiverr.core.services import LoggerServiceImpl
        
        mock_debugger = Mock()
        service = LoggerServiceImpl(mock_debugger, "tmdb")
        
        service.info("Fetching movie")
        
        mock_debugger.info.assert_called_once_with("tmdb", "Fetching movie")
    
    def test_set_plugin_name(self):
        """Test setting plugin name context"""
        from archiverr.core.services import LoggerServiceImpl
        
        mock_debugger = Mock()
        service = LoggerServiceImpl(mock_debugger, "initial")
        
        service.set_plugin_name("changed")
        service.info("Test")
        
        mock_debugger.info.assert_called_once_with("changed", "Test")


class TestEventService:
    """EventService implementation tests"""
    
    def test_emit_calls_bus(self):
        """Test emit calls underlying event bus"""
        from archiverr.core.services import EventServiceImpl
        
        mock_bus = Mock()
        service = EventServiceImpl(mock_bus, source="test_plugin")
        
        service.emit("plugin.completed", {"plugin": "test"})
        
        mock_bus.emit.assert_called_once_with(
            "plugin.completed", 
            {"plugin": "test"}, 
            source="test_plugin"
        )
    
    def test_emit_with_no_data(self):
        """Test emit with no data uses empty dict"""
        from archiverr.core.services import EventServiceImpl
        
        mock_bus = Mock()
        service = EventServiceImpl(mock_bus)
        
        service.emit("some.event")
        
        mock_bus.emit.assert_called_once_with("some.event", {}, source="plugin")
    
    def test_subscribe_calls_bus(self):
        """Test subscribe calls underlying event bus"""
        from archiverr.core.services import EventServiceImpl
        
        mock_bus = Mock()
        service = EventServiceImpl(mock_bus)
        handler = lambda event, data: None
        
        service.subscribe("plugin.*", handler)
        
        mock_bus.subscribe.assert_called_once_with("plugin.*", handler)


class TestStateService:
    """StateService implementation tests"""
    
    def test_get_current_job_raises_without_context(self):
        """Test get_current_job raises when no job is set"""
        from archiverr.core.services import StateServiceImpl
        
        mock_manager = Mock()
        service = StateServiceImpl(mock_manager)
        
        with pytest.raises(RuntimeError, match="No current job"):
            service.get_current_job()
    
    def test_set_current_job(self):
        """Test setting current job context"""
        from archiverr.core.services import StateServiceImpl
        
        mock_manager = Mock()
        service = StateServiceImpl(mock_manager)
        
        service.set_current_job("job_run_abc123_0")
        
        assert service._current_job_id == "job_run_abc123_0"
    
    def test_get_plugin_data_from_cache(self):
        """Test getting plugin data from cache"""
        from archiverr.core.services import StateServiceImpl
        
        mock_manager = Mock()
        service = StateServiceImpl(mock_manager)
        
        # Pre-populate cache
        service._plugin_cache["job_run_test_0"] = {
            "tmdb": {"data": {"movie": {"title": "Test Movie"}}}
        }
        
        result = service.get_plugin_data("job_run_test_0", "tmdb")
        
        assert result["movie"]["title"] == "Test Movie"
    
    def test_get_plugin_data_from_persistence(self):
        """Test getting plugin data from persistence layer"""
        from archiverr.core.services import StateServiceImpl
        
        mock_manager = Mock()
        mock_persistence = Mock()
        mock_persistence.get_plugin.return_value = {
            "data": {"movie": {"title": "From DB"}}
        }
        
        service = StateServiceImpl(mock_manager, persistence=mock_persistence)
        
        result = service.get_plugin_data("job_test_0", "tmdb")
        
        assert result["movie"]["title"] == "From DB"
        mock_persistence.get_plugin.assert_called_once_with("job_test_0", "tmdb")
    
    def test_save_plugin_data_caches(self):
        """Test saving plugin data updates cache"""
        from archiverr.core.services import StateServiceImpl
        
        mock_manager = Mock()
        mock_manager._execution = None  # No active run
        service = StateServiceImpl(mock_manager)
        
        service.save_plugin_data(
            job_id="job_run_test_0",
            plugin_name="tmdb",
            stage="data",
            data={"movie": {"title": "Cached"}}
        )
        
        # Verify cached
        assert "job_run_test_0" in service._plugin_cache
        assert "tmdb" in service._plugin_cache["job_run_test_0"]
    
    def test_save_plugin_data_persists(self):
        """Test saving plugin data calls persistence"""
        from archiverr.core.services import StateServiceImpl
        
        mock_manager = Mock()
        mock_manager._execution = None
        mock_persistence = Mock()
        
        service = StateServiceImpl(mock_manager, persistence=mock_persistence)
        
        service.save_plugin_data(
            job_id="job_run_test_0",
            plugin_name="tmdb",
            stage="data",
            data={"movie": {"title": "Persisted"}}
        )
        
        mock_persistence.save_plugin.assert_called_once()
        call_args = mock_persistence.save_plugin.call_args[0][0]
        assert call_args["plugin_name"] == "tmdb"
        assert call_args["data"]["movie"]["title"] == "Persisted"


class TestPluginServices:
    """PluginServices dataclass tests"""
    
    def test_create_plugin_services(self):
        """Test factory function creates valid services"""
        from archiverr.core.services import create_plugin_services, PluginServices
        
        mock_manager = Mock()
        mock_bus = Mock()
        mock_debugger = Mock()
        config = {"options": {"debug": True}}
        
        services = create_plugin_services(
            state_manager=mock_manager,
            event_bus=mock_bus,
            debugger=mock_debugger,
            config=config,
            plugin_name="test_plugin"
        )
        
        assert isinstance(services, PluginServices)
        assert services.state is not None
        assert services.events is not None
        assert services.logger is not None
        assert services.config is not None
    
    def test_plugin_services_dataclass(self):
        """Test PluginServices is a proper dataclass"""
        from archiverr.core.services import PluginServices, StateServiceImpl, EventServiceImpl, LoggerServiceImpl, ConfigServiceImpl
        
        mock_manager = Mock()
        mock_bus = Mock()
        mock_debugger = Mock()
        
        services = PluginServices(
            state=StateServiceImpl(mock_manager),
            events=EventServiceImpl(mock_bus),
            logger=LoggerServiceImpl(mock_debugger),
            config=ConfigServiceImpl({})
        )
        
        # Verify fields are accessible
        assert hasattr(services, 'state')
        assert hasattr(services, 'events')
        assert hasattr(services, 'logger')
        assert hasattr(services, 'config')


class TestProtocolCompliance:
    """Tests verifying protocol compliance"""
    
    def test_state_service_protocol(self):
        """Test StateServiceImpl implements StateService protocol"""
        from archiverr.core.services import StateServiceImpl
        from archiverr.core.services.protocols import StateService
        
        mock_manager = Mock()
        service = StateServiceImpl(mock_manager)
        
        assert isinstance(service, StateService)
    
    def test_event_service_protocol(self):
        """Test EventServiceImpl implements EventService protocol"""
        from archiverr.core.services import EventServiceImpl
        from archiverr.core.services.protocols import EventService
        
        mock_bus = Mock()
        service = EventServiceImpl(mock_bus)
        
        assert isinstance(service, EventService)
    
    def test_logger_service_protocol(self):
        """Test LoggerServiceImpl implements LoggerService protocol"""
        from archiverr.core.services import LoggerServiceImpl
        from archiverr.core.services.protocols import LoggerService
        
        mock_debugger = Mock()
        service = LoggerServiceImpl(mock_debugger)
        
        assert isinstance(service, LoggerService)
    
    def test_config_service_protocol(self):
        """Test ConfigServiceImpl implements ConfigService protocol"""
        from archiverr.core.services import ConfigServiceImpl
        from archiverr.core.services.protocols import ConfigService
        
        service = ConfigServiceImpl({})
        
        assert isinstance(service, ConfigService)
