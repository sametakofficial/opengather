"""Plugin System - Discovery, Loading, Resolution, Execution, SDK"""
from .discovery import PluginDiscovery
from .loader import PluginLoader
from .resolver import DependencyResolver
from .executor import PluginExecutor

# Session 11 additions
from .registry import PluginRegistry, Stage, PluginInfo
from .stage_executor import StageExecutor, ExecutionMode, STAGE_MODES
from .requires_validator import RequiresValidator, RequiresResult

# SDK exports (for convenience: from archiverr.core.plugins import BasePlugin)
from .sdk import (
    PluginManifest,
    PluginResult,
    BasePlugin,
    InputPlugin,
    OutputPlugin,
    ExecutionContext,
    ValidationResult,
    PluginCategory,
    PluginStatus,
    MediaCategory,
)

__all__ = [
    # System (legacy)
    'PluginDiscovery',
    'PluginLoader',
    'DependencyResolver',
    'PluginExecutor',
    
    # Session 11: Registry & Execution
    'PluginRegistry',
    'Stage',
    'PluginInfo',
    'StageExecutor',
    'ExecutionMode',
    'STAGE_MODES',
    'RequiresValidator',
    'RequiresResult',
    
    # SDK
    'PluginManifest',
    'PluginResult',
    'BasePlugin',
    'InputPlugin',
    'OutputPlugin',
    'ExecutionContext',
    'ValidationResult',
    'PluginCategory',
    'PluginStatus',
    'MediaCategory',
]
