"""
ResultBuilder - Builds RunResult from execution state.

Extracted from Orchestrator for Single Responsibility Principle.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from archiverr.state.manager import GlobalStateManager


@dataclass
class RunResult:
    """Orchestrator run result summary."""
    run_id: str
    success: bool
    total_jobs: int
    completed: int
    failed: int
    skipped: int
    duration_ms: int
    stages_completed: list[str] = field(default_factory=list)
    stages_failed: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API/logging"""
        return {
            "run_id": self.run_id,
            "success": self.success,
            "total_jobs": self.total_jobs,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
            "stages_completed": self.stages_completed,
            "stages_failed": self.stages_failed,
            "error": self.error
        }


class ResultBuilder:
    """Builds RunResult from execution state."""

    def build(
        self,
        run_id: str,
        state: 'GlobalStateManager',
        start_time: datetime,
        success: bool,
        stages_completed: list[str],
        stages_failed: list[str],
        error: str = None
    ) -> RunResult:
        """
        Build RunResult from current state.
        
        Args:
            run_id: Current run ID
            state: GlobalStateManager instance
            start_time: When the run started
            success: Whether the run succeeded
            stages_completed: List of completed stage names
            stages_failed: List of failed stage names
            error: Optional error message
            
        Returns:
            RunResult with execution summary
        """
        duration_ms = 0
        if start_time:
            delta = datetime.now() - start_time
            duration_ms = int(delta.total_seconds() * 1000)

        run = state.run
        total_jobs = run.status.total_jobs if run else 0
        completed = run.status.completed if run else 0
        failed = run.status.failed if run else 0

        return RunResult(
            run_id=run_id or "",
            success=success and failed == 0,
            total_jobs=total_jobs,
            completed=completed,
            failed=failed,
            skipped=0,
            duration_ms=duration_ms,
            stages_completed=stages_completed,
            stages_failed=stages_failed,
            error=error
        )
