"""
Plugin Types - Type definitions for plugin system

Provides type aliases and enums for type safety.
"""

from enum import Enum
from typing import Dict, Any, List, Callable, TypeVar


class PluginCategory(str, Enum):
    """Plugin category types"""
    INPUT = "input"
    OUTPUT = "output"


class PluginStatus(str, Enum):
    """Plugin execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class MediaCategory(str, Enum):
    """Supported media types"""
    MOVIE = "movie"
    SHOW = "show"
    EPISODE = "episode"
    SEASON = "season"


# Type aliases
PluginConfig = Dict[str, Any]
MatchData = Dict[str, Any]
PluginOutput = Dict[str, Any]

# Generic plugin type
T = TypeVar('T', bound='BasePlugin')

# Handler type for plugin events
PluginEventHandler = Callable[[str, Dict[str, Any]], None]
