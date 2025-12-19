"""State Management Module."""

from .manager import StateManager, GlobalStateManager
from .models import (
    StateEnum,
    InputData,
    OutputData,
    JobStatus,
    RunStatus,
    JobState,
    RunState,
)
from .context import ExecutionContext


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
