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

from .manifest import PluginManifest
from .result import PluginResult
from .base import BasePlugin, InputPlugin, OutputPlugin, ValidationResult
from .context import ExecutionContext
from .types import PluginCategory, PluginStatus, MediaCategory
from .validators import (
    ConfigValidator,
    ValidationResult as ConfigValidationResult,
    ValidationError as ConfigValidationError,
    validate_plugin_config,
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
]
