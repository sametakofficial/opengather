"""
Core Services - Shared business logic for CLI and API

Service protocols define interfaces, implementations provide concrete behavior.
The actual PluginServices class used by the pipeline is in plugin_services.py.
"""

from .config_service import ConfigServiceImpl
from .event_service import EventServiceImpl
from .logger_service import LoggerServiceImpl

# Protocol definitions
from .protocols import (
    ConfigService,
    EventService,
    LoggerService,
    ProvidesService,
    StateService,
    TemplateService,
)
from .provides_service import ProvidesServiceImpl

__all__ = [
    # Protocols
    'StateService',
    'EventService',
    'LoggerService',
    'ConfigService',
    'TemplateService',
    'ProvidesService',

    # Implementations
    'EventServiceImpl',
    'LoggerServiceImpl',
    'ConfigServiceImpl',
    'ProvidesServiceImpl',
]
