"""Plugin System - Discovery, Loading, Resolution, Execution, SDK"""
from .discovery import PluginDiscovery
from .loader import PluginLoader

from .registry import PluginInfo, PluginRegistry, Stage
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
    # System
    'PluginDiscovery',
    'PluginLoader',
    'DependencyResolver',

    # Registry & Execution
    'PluginRegistry',
    'Stage',
    'PluginInfo',
    'StageExecutor',
    'ExecutionMode',
    'STAGE_MODES',

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
