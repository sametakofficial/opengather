"""
State Management Module

State manager for Archiverr execution.
Provides centralized state tracking with persistence support.
"""

from .manager import StateManager, GlobalStateManager
from .models import ExecutionState, MatchState, PluginResult

__all__ = [
    'StateManager',           # Primary class (DI pattern)
    'GlobalStateManager',     # Alias for backward compatibility
    'ExecutionState',
    'MatchState',
    'PluginResult'
]
