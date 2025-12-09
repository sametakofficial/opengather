"""
State Management Module

Session 11 - Clean state management.

Terminology:
- RunState (was ExecutionState)
- JobState (was MatchState)
- StateEnum (was ExecutionStatus)

Legacy aliases are provided for backward compatibility during transition.
"""

from .manager import StateManager, GlobalStateManager
from .models import (
    StateEnum,
    InputData,
    OutputData,
    JobStatus,
    RunStatus,
    JobState,
    RunState,
    PluginData,
)
from .context import ExecutionContext

# Legacy aliases - will be removed after test migration
ExecutionStatus = StateEnum  # Legacy: use StateEnum
MatchState = JobState        # Legacy: use JobState
ExecutionState = RunState    # Legacy: use RunState

# PluginResult re-export for backward compatibility
try:
    from archiverr.core.plugins.sdk.result import PluginResult
except ImportError:
    # Fallback if sdk not available
    from dataclasses import dataclass, field
    from datetime import datetime
    from typing import Dict, Any, Optional
    
    @dataclass
    class PluginResult:
        """Fallback PluginResult for testing."""
        plugin_name: str = ""
        success: bool = True
        started_at: datetime = field(default_factory=datetime.now)
        finished_at: datetime = field(default_factory=datetime.now)
        data: Dict[str, Any] = field(default_factory=dict)
        error: Optional[str] = None
        metadata: Dict[str, Any] = field(default_factory=dict)
        
        @property
        def duration_ms(self) -> int:
            return int((self.finished_at - self.started_at).total_seconds() * 1000)
        
        def to_dict(self) -> Dict[str, Any]:
            return {
                "plugin_name": self.plugin_name,
                "success": self.success,
                "data": self.data,
                "error": self.error
            }

__all__ = [
    # New API
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
    'PluginData',
    
    # Legacy aliases (deprecated)
    'ExecutionStatus',
    'MatchState',
    'ExecutionState',
    'PluginResult',
]
