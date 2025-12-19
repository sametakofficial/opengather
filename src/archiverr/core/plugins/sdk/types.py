"""
Plugin Types - Type definitions for plugin system

Provides type aliases and enums for type safety.
"""

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from .base import BasePlugin


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
PluginConfig = dict[str, Any]
MatchData = dict[str, Any]
PluginOutput = dict[str, Any]

# Generic plugin type
T = TypeVar('T', bound='BasePlugin')

# Handler type for plugin events
PluginEventHandler = Callable[[str, dict[str, Any]], None]
