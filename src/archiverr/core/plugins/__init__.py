"""Plugin System - Discovery, Loading, Resolution, Execution, SDK"""
from .discovery import PluginDiscovery
from .loader import PluginLoader
from .resolver import DependencyResolver
from .executor import PluginExecutor

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
    # System
    'PluginDiscovery',
    'PluginLoader',
    'DependencyResolver',
    'PluginExecutor',
    
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
