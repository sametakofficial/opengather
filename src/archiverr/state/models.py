"""
State Models - Core data structures for run and job state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class StateEnum(Enum):
    """Unified state enum for Run and Job states."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class InputData:
    """Job input data container."""
    value: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "data": self.data
        }


@dataclass
class OutputData:
    """Job output data container."""
    values: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "values": self.values,
            "data": self.data
        }


@dataclass
class JobStatus:
    """Job execution status with per-plugin tracking."""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        # Derive executed/failed/skipped from plugins dict
        executed = []
        failed = []
        skipped = []
        for pname, pstatus in self.plugins.items():
            if isinstance(pstatus, dict):
                pstate = pstatus.get('state', '')
                if pstate == 'failed' or not pstatus.get('success', True):
                    failed.append(pname)
                elif pstate == 'skipped':
                    skipped.append(pname)
                elif pstate == 'completed':
                    executed.append(pname)

        return {
            "state": self.state.value,
            "success": self.success,
            "executed": executed,
            "failed": failed,
            "skipped": skipped,
            "plugins": self.plugins,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms
        }


@dataclass
class RunStatus:
    """Run execution status."""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "success": self.success,
            "total_jobs": self.total_jobs,
            "completed": self.completed,
            "failed": self.failed,
            "plugins": self.plugins,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms
        }


@dataclass
class JobState:
    """Per-job state container."""
    index: int
    run_id: str
    id: str = field(default="")
    input: InputData = field(default_factory=lambda: InputData(""))
    output: OutputData = field(default_factory=OutputData)
    status: JobStatus = field(default_factory=JobStatus)
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"job_{self.run_id}_{self.index}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "run_id": self.run_id,
            "input": self.input.to_dict(),
            "output": self.output.to_dict(),
            "status": self.status.to_dict(),
            "plugins": self.plugins
        }

    def start(self):
        """Mark job as started."""
        self.status.state = StateEnum.RUNNING
        self.status.started_at = datetime.now()

    def complete(self, success: bool = True):
        """Mark job as completed."""
        self.status.finished_at = datetime.now()
        if self.status.started_at:
            delta = self.status.finished_at - self.status.started_at
            self.status.duration_ms = int(delta.total_seconds() * 1000)
        self.status.success = success
        self.status.state = StateEnum.SUCCESS if success else StateEnum.FAILED



@dataclass
class RunState:
    """Execution-level state. ID Format: run_{uuid8}"""
    id: str
    status: RunStatus = field(default_factory=RunStatus)
    config: dict[str, Any] = field(default_factory=dict)
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.to_dict(),
            "config": self.config,
            "plugins": self.plugins
        }

    def start(self):
        """Mark run as started."""
        self.status.state = StateEnum.RUNNING
        self.status.started_at = datetime.now()

    def complete(self):
        """Mark run as completed."""
        self.status.finished_at = datetime.now()
        if self.status.started_at:
            delta = self.status.finished_at - self.status.started_at
            self.status.duration_ms = int(delta.total_seconds() * 1000)
        self.status.success = self.status.failed == 0
        if self.status.failed == 0:
            self.status.state = StateEnum.SUCCESS
        elif 0 < self.status.failed < self.status.total_jobs:
            self.status.state = StateEnum.PARTIAL
        else:
            self.status.state = StateEnum.FAILED

    def increment_jobs(self):
        """Increment total job count."""
        self.status.total_jobs += 1

    def increment_completed(self):
        """Increment completed job count."""
        self.status.completed += 1

    def increment_failed(self):
        """Increment failed job count."""
        self.status.failed += 1
