"""Plugin System - Discovery, Loading, Resolution, Execution, SDK"""
from .discovery import PluginDiscovery
from .executor import PluginExecutor
from .loader import PluginLoader

# additions
from .registry import PluginInfo, PluginRegistry, Stage
from .requires_validator import RequiresResult, RequiresValidator
from .resolver import DependencyResolver

# SDK exports (for convenience: from archiverr.core.plugins import BasePlugin)
from .sdk import (
    BasePlugin,
    ExecutionContext,
    InputPlugin,
    MediaCategory,
    OutputPlugin,
    PluginCategory,
    PluginManifest,
    PluginResult,
    PluginStatus,
    ValidationResult,
)
from .stage_executor import STAGE_MODES, ExecutionMode, StageExecutor

__all__ = [
    # System (legacy)
    'PluginDiscovery',
    'PluginLoader',
    'DependencyResolver',
    'PluginExecutor',

    # Registry & Execution
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
