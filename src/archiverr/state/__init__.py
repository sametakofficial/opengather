"""
State Management Module

State manager for Archiverr execution.
Provides centralized state tracking with persistence support.

Session 11 Update:
- New models: StateEnum, InputData, OutputData, JobStatus, RunStatus, JobState, RunState, PluginData
- Legacy models kept for backward compatibility: ExecutionState, MatchState, PluginResult
"""

from .manager import StateManager, GlobalStateManager
from .models import (
    # New models (Session 11 - FINAL_DATASETS.yml compliant)
    StateEnum,
    InputData,
    OutputData,
    JobStatus,
    RunStatus,
    JobState,
    RunState,
    PluginData,
    
    # Legacy models (DEPRECATED - for backward compatibility)
    ExecutionState,
    ExecutionStatus,
    MatchState,
    PluginResult,
)

__all__ = [
    # State Manager
    'StateManager',           # Primary class (DI pattern)
    'GlobalStateManager',     # Alias for backward compatibility
    
    # New State Models (preferred)
    'StateEnum',
    'InputData',
    'OutputData',
    'JobStatus',
    'RunStatus',
    'JobState',
    'RunState',
    'PluginData',
    
    # Legacy Models (DEPRECATED)
    'ExecutionState',
    'ExecutionStatus',
    'MatchState',
    'PluginResult',
]
