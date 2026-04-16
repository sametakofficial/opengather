"""State Management Module."""

from archiverr.core.plugins.sdk.result import PluginResult

from .context import ExecutionContext
from .manager import GlobalStateManager, StateManager
from .models import (
    InputData,
    JobState,
    JobStatus,
    OutputData,
    RunState,
    RunStatus,
    StateEnum,
)

__all__ = [
    'StateManager',
    'GlobalStateManager',
    'ExecutionContext',
    'StateEnum',
    'InputData',
    'OutputData',
    'JobStatus',
    'RunStatus',
    'JobState',
    'RunState',
    'PluginResult',
]
