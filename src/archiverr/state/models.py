"""
State Models

Dataclasses for state management.
Flat structure - inspired by feature/mongodb-implementation branch.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class ExecutionStatus(Enum):
    """Execution status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionState:
    """
    Execution-level state.
    
    Represents a single run of Archiverr.
    """
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    success: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Summary stats
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    
    # Config snapshot (opaque to core)
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            "_id": f"exec_{self.id}",
            "id": self.id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "status": self.status.value,
            "summary": {
                "total_matches": self.total_matches,
                "completed_matches": self.completed_matches,
                "failed_matches": self.failed_matches
            },
            "config_snapshot": self.config_snapshot
        }


@dataclass
class PluginResult:
    """
    Single plugin execution result.
    
    Core doesn't know plugin internals - just stores as Dict[str, Any].
    """
    plugin_name: str
    success: bool
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            "status": {
                "success": self.success,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                "duration_ms": self.duration_ms,
                "error": self.error
            },
            **self.data  # Spread plugin data at root level
        }


@dataclass
class MatchState:
    """
    Per-match state.
    
    Flat structure - no nested globals wrapper.
    Plugin data stored in plugins dict, keyed by plugin name.
    """
    index: int
    input_path: str
    execution_id: str
    
    # Status
    success: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # Plugin tracking
    executed_plugins: List[str] = field(default_factory=list)
    failed_plugins: List[str] = field(default_factory=list)
    not_supported_plugins: List[str] = field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    
    # Task results
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    
    # Plugin data (flat - no wrapper)
    # Core doesn't know plugin internals, just stores Dict[str, Any]
    plugins: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            "_id": f"match_{self.index}_{self.execution_id}",
            "execution_id": f"exec_{self.execution_id}",
            "index": self.index,
            "input_path": self.input_path,
            "success": self.success,
            "status": self.status.value,
            "executed_plugins": self.executed_plugins,
            "failed_plugins": self.failed_plugins,
            "not_supported_plugins": self.not_supported_plugins,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "tasks": self.tasks
        }
    
    def add_plugin_result(self, plugin_name: str, result: PluginResult):
        """Add plugin result to match"""
        self.plugins[plugin_name] = result.to_dict()
        
        if result.success:
            if plugin_name not in self.executed_plugins:
                self.executed_plugins.append(plugin_name)
        else:
            if plugin_name not in self.failed_plugins:
                self.failed_plugins.append(plugin_name)
                self.success = False
    
    def add_not_supported(self, plugin_name: str):
        """Mark plugin as not supported for this match"""
        if plugin_name not in self.not_supported_plugins:
            self.not_supported_plugins.append(plugin_name)
    
    def add_task_result(self, task_result: Dict[str, Any]):
        """Add task execution result"""
        self.tasks.append(task_result)
    
    def complete(self):
        """Mark match as completed"""
        self.finished_at = datetime.now()
        if self.started_at:
            self.duration_ms = int((self.finished_at - self.started_at).total_seconds() * 1000)
        self.status = ExecutionStatus.COMPLETED if self.success else ExecutionStatus.FAILED
