"""
Core Services - Shared business logic for CLI and API

Session 11 Update:
- Added PluginServices for plugin dependency injection
- Service protocols: StateService, EventService, LoggerService, ConfigService
- Factory functions: create_plugin_services, services_from_context
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, TYPE_CHECKING

# Legacy service
from .execution_service import ExecutionService, ExecutionProgress, ExecutionResult

# New protocol definitions
from .protocols import (
    StateService,
    EventService,
    LoggerService,
    ConfigService,
    TemplateService,
    ProvidesService,
)

# Service implementations
from .state_service import StateServiceImpl
from .event_service import EventServiceImpl
from .logger_service import LoggerServiceImpl
from .config_service import ConfigServiceImpl
from .provides_service import ProvidesServiceImpl

if TYPE_CHECKING:
    from archiverr.state.manager import StateManager
    from archiverr.events import EventBus
    from archiverr.utils.debug import Debugger
    from archiverr.infrastructure.database.interface import PersistenceInterface
    from archiverr.core.provides_registry import ProvidesRegistry


@dataclass
class PluginServices:
    """
    Single interface for plugin dependency injection.
    
    Plugins access all system resources through this interface.
    No global functions or direct state access allowed.
    
    Usage in plugin:
        def execute(self, job: JobState, services: PluginServices) -> PluginResult:
            services.logger.info("Starting execution...")
            parsed = services.state.get_plugin_data(job.id, "renamer")
            
            # Mark provide as completed early
            services.provides.complete("http.request")
            
            services.events.emit("plugin.completed", {"plugin": self.name})
            return PluginResult.success({"movie": movie_data})
    """
    state: StateService
    events: EventService
    logger: LoggerService
    config: ConfigService
    provides: ProvidesService


def create_plugin_services(
    state_manager: 'StateManager',
    event_bus: 'EventBus',
    debugger: 'Debugger',
    config: Dict[str, Any],
    plugin_name: str = "plugin",
    persistence: Optional['PersistenceInterface'] = None,
    provides_registry: Optional['ProvidesRegistry'] = None
) -> PluginServices:
    """
    Factory function to create PluginServices.
    
    Args:
        state_manager: StateManager instance
        event_bus: EventBus instance
        debugger: Debugger instance
        config: Full config dictionary
        plugin_name: Plugin name for logging context
        persistence: Optional persistence layer for plugin data
        provides_registry: Optional provides registry for early completion
        
    Returns:
        PluginServices instance with all services configured
    """
    from archiverr.core.provides_registry import get_provides_registry
    
    registry = provides_registry or get_provides_registry()
    
    return PluginServices(
        state=StateServiceImpl(state_manager, persistence),
        events=EventServiceImpl(event_bus, source=plugin_name),
        logger=LoggerServiceImpl(debugger, plugin_name),
        config=ConfigServiceImpl(config),
        provides=ProvidesServiceImpl(registry, plugin_name)
    )


def services_from_context(context, state_manager: 'StateManager') -> PluginServices:
    """
    DEPRECATED: Create PluginServices from legacy ExecutionContext.
    
    Use during migration period. New code should use create_plugin_services().
    
    Args:
        context: Legacy ExecutionContext
        state_manager: StateManager instance
        
    Returns:
        PluginServices instance
    """
    from archiverr.utils.debug import get_debugger
    from archiverr.core.provides_registry import get_provides_registry
    
    registry = get_provides_registry()
    
    return PluginServices(
        state=StateServiceImpl(state_manager),
        events=EventServiceImpl(context.event_bus, source="plugin"),
        logger=LoggerServiceImpl(get_debugger(), "plugin"),
        config=ConfigServiceImpl(context.config),
        provides=ProvidesServiceImpl(registry, "plugin")
    )


__all__ = [
    # Legacy
    'ExecutionService',
    'ExecutionProgress', 
    'ExecutionResult',
    
    # Protocols
    'StateService',
    'EventService',
    'LoggerService',
    'ConfigService',
    'TemplateService',
    'ProvidesService',
    
    # Implementations
    'StateServiceImpl',
    'EventServiceImpl',
    'LoggerServiceImpl',
    'ConfigServiceImpl',
    'ProvidesServiceImpl',
    
    # PluginServices
    'PluginServices',
    'create_plugin_services',
    'services_from_context',
]
