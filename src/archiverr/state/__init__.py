"""
State Management Module

Global state manager for Archiverr execution.
Provides centralized state tracking with persistence support.
"""

from .manager import GlobalStateManager
from .models import ExecutionState, MatchState, PluginResult

__all__ = [
    'GlobalStateManager',
    'ExecutionState',
    'MatchState',
    'PluginResult'
]
