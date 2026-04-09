"""
Plugin SDK - Standardized plugin development kit

Location: core/plugins/sdk/ (inside plugins infrastructure)

Provides:
- PluginManifest: Pydantic model for plugin.json validation
- PluginResult: Standardized result format
- BasePlugin, InputPlugin, OutputPlugin: Base classes
- ExecutionContext: Runtime context for plugins
- ConfigValidator: Plugin config validation against schema
"""

from .base import BasePlugin, InputPlugin, OutputPlugin, ValidationResult
from .context import ExecutionContext
from .manifest import PluginManifest
from .result import PluginResult
from .types import MediaCategory, PerJobPlugin, PerRunPlugin, PluginCategory, PluginStatus
from .validators import (
    ConfigValidator,
    validate_plugin_config,
)
from .validators import (
    ValidationError as ConfigValidationError,
)
from .validators import (
    ValidationResult as ConfigValidationResult,
)

__all__ = [
    # Models
    'PluginManifest',
    'PluginResult',
    'ExecutionContext',

    # Base classes
    'BasePlugin',
    'InputPlugin',
    'OutputPlugin',
    'ValidationResult',

    # Config Validation
    'ConfigValidator',
    'ConfigValidationResult',
    'ConfigValidationError',
    'validate_plugin_config',

    # Types
    'PluginCategory',
    'PluginStatus',
    'MediaCategory',

    # Protocols
    'PerRunPlugin',
    'PerJobPlugin',
]
