"""Job Manager - Extracted from GlobalStateManager.

This module handles job lifecycle operations.
Follows Single Responsibility Principle by separating job management from state management.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from archiverr.events import EventBus

    from .context import ExecutionContext
    from .models import JobState, RunState
    from .persistence_delegate import PersistenceDelegate

from archiverr.events import Events

from .models import InputData, JobState


class JobManager:
    """
    Manages job lifecycle operations.
    
    Extracted from GlobalStateManager to follow SRP.
    Handles job creation, completion, and status updates.
    """

    def __init__(
        self,
        context: 'ExecutionContext',
        persistence: 'PersistenceDelegate',
        event_bus: Optional['EventBus'] = None,
        logger=None
    ):
        """
        Initialize job manager.
        
        Args:
            context: ExecutionContext for job storage
            persistence: PersistenceDelegate for saving jobs
            event_bus: Optional EventBus for events
            logger: Optional logging function
        """
        self._context = context
        self._persistence = persistence
        self._event_bus = event_bus
        self._log = logger or self._noop_log

    def _noop_log(self, level: str, component: str, message: str, **kwargs):
        """No-op logger when none provided."""
        pass

    def _emit(self, event_name: str, data: dict[str, Any] = None, source: str = "job_manager"):
        """Emit event if event bus is configured."""
        if self._event_bus:
            self._event_bus.emit(event_name, data or {}, source)

    def create_job(
        self,
        run: 'RunState',
        input_value: str,
        input_data: dict[str, Any] = None
    ) -> str:
        """
        Create new job.
        
        Args:
            run: Parent run state
            input_value: Input file path or value
            input_data: Additional input data
            
        Returns:
            Job ID
        """
        index = len(self._context._jobs)

        job = JobState(
            index=index,
            run_id=run.id,
            input=InputData(
                value=input_value,
                data=input_data or {}
            )
        )
        job.start()

        self._context.add_job(job)
        run.increment_jobs()

        self._persistence.save_job(job)
        self._persistence.save_run(run)

        self._log("debug", "job", f"Created job {index}", input_value=input_value)

        self._emit(Events.JOB_CREATED, {
            "index": index,
            "job_id": job.id,
            "input_value": input_value,
            "run_id": run.id
        })

        return job.id

    def complete_job(self, run: 'RunState', index: int) -> None:
        """
        Mark job as completed.
        
        Args:
            run: Parent run state
            index: Job index
        """
        job = self._context.get_job_by_index(index)
        if not job:
            raise ValueError(f"Job {index} not found")

        job.complete(success=job.status.success)

        # Update run stats
        run.increment_completed()
        if not job.status.success:
            run.increment_failed()

        self._persistence.save_job(job)

        self._log("debug", "job", f"Job {index} completed",
                 success=job.status.success, duration_ms=job.status.duration_ms)

        # Calculate executed/failed from job.status.plugins
        executed_plugins = []
        failed_plugins = []
        for pname, pstatus in job.status.plugins.items():
            if isinstance(pstatus, dict):
                if pstatus.get('state') == 'failed' or not pstatus.get('success', True):
                    failed_plugins.append(pname)
                elif pstatus.get('state') in ('completed', 'skipped'):
                    executed_plugins.append(pname)

        event_name = Events.JOB_COMPLETED if job.status.success else Events.JOB_FAILED
        self._emit(event_name, {
            "index": index,
            "success": job.status.success,
            "duration_ms": job.status.duration_ms,
            "executed_plugins": executed_plugins,
            "failed_plugins": failed_plugins
        })

    def set_current_job(self, job_id: str) -> None:
        """Set current job context for per_job plugin execution."""
        job = self._context.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        self._context.set_current_job(job)
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            self._context._current_plugins = job.plugins

    def clear_current_job(self) -> None:
        """Clear current job context."""
        self._context.clear_current_job()

    def get_job(self, index: int) -> Optional['JobState']:
        """Get job by index."""
        return self._context.get_job_by_index(index)

    def get_job_by_id(self, job_id: str) -> Optional['JobState']:
        """Get job by ID."""
        return self._context.get_job(job_id)

    def get_all_jobs(self) -> list['JobState']:
        """Get all jobs in current run."""
        return self._context.jobs

    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """Update job state using dot-notation path."""
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Parse dot notation and set value
        parts = key.split('.')
        obj = job
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

        self._emit(Events.JOB_UPDATED, {
            "job_id": job_id,
            "key": key,
            "value": value
        })
