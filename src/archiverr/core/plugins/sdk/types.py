"""
Plugin Types - Type definitions for plugin system

Provides type aliases, enums, and Plugin Protocols for type safety.
"""

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

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


# ---------------------------------------------------------------------------
# Plugin Protocols -- formalize what the executor expects from plugins
# ---------------------------------------------------------------------------

@runtime_checkable
class PerRunPlugin(Protocol):
    """Protocol for per_run plugins (scanner, file-reader).

    These run once per run before stages, creating jobs via services.create_job().
    Method: execute_run(services) -> dict
    """
    name: str

    def execute_run(self, services: Any) -> dict[str, Any]: ...


@runtime_checkable
class PerJobPlugin(Protocol):
    """Protocol for per_job plugins (renamer, tmdb, ffprobe, tasker).

    These run once per job within a stage (PARSE, DATA, OUTPUT).
    Method: execute(job, services) -> PluginResult | dict

    Note: Legacy plugins (tvdb, tvmaze, omdb) also have execute() but with
    a single argument: execute(match_data). The executor distinguishes them
    by checking parameter count via inspect.signature(). Legacy plugins should
    be migrated to this 2-argument interface over time.
    """
    name: str

    def execute(self, job: Any, services: Any) -> Any: ...
