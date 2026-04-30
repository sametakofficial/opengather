"""Global State Manager - Unified state management for runs and jobs."""

from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from .context import ExecutionContext
from .event_emitter import StateEventEmitter
from .job_manager import JobManager
from .models import JobState, RunState
from .persistence_delegate import PersistenceDelegate
from .plugin_data_manager import PluginDataManager
from .template_context import TemplateContextBuilder

if TYPE_CHECKING:
    from archiverr.events import EventBus

from archiverr.events import Events


class GlobalStateManager:
    """Unified state manager for runs, jobs, and plugin data."""

    def __init__(
        self,
        persistence=None,
        debugger=None,
        event_bus: Optional['EventBus'] = None
    ):
        self._persistence = persistence
        self._debugger = debugger
        self._event_bus = event_bus
        self._template_builder = TemplateContextBuilder()
        self._persistence_delegate = PersistenceDelegate(persistence, self._log)
        self._event_emitter = StateEventEmitter(event_bus, source="state")
        self._context: ExecutionContext = ExecutionContext()
        self._job_manager = JobManager(
            context=self._context,
            persistence=self._persistence_delegate,
            event_bus=event_bus,
            logger=self._log
        )
        self._plugin_manager = PluginDataManager(
            context=self._context,
            persistence=self._persistence_delegate,
            event_emitter=self._event_emitter,
            logger=self._log
        )

        self._run: RunState | None = None
        self._config: dict[str, Any] = {}

    def configure(
        self,
        persistence=None,
        debugger=None,
        event_bus: Optional['EventBus'] = None
    ):
        """Reconfigure dependencies."""
        if persistence is not None:
            self._persistence = persistence
            self._persistence_delegate.configure(persistence=persistence)
        if debugger is not None:
            self._debugger = debugger
            self._persistence_delegate.configure(logger=self._log)
        if event_bus is not None:
            self._event_bus = event_bus
            self._event_emitter.configure(event_bus=event_bus)
            self._job_manager.configure(event_bus=event_bus)

    def reset(self):
        """reset state for new run."""
        self._run = None
        self._config = {}
        self._context.reset()

    @property
    def persistence(self):
        """Persistence backend (``PersistenceInterface``).

        Exposed for executor-level recovery writes. May be ``None`` until
        ``configure()`` has been called.
        """
        return self._persistence

    @property
    def run(self) -> RunState | None:
        """Current run state (read-only for plugins)."""
        return self._run

    @property
    def config(self) -> dict[str, Any]:
        """Frozen config (read-only for plugins)."""
        return self._config

    @property
    def context(self) -> ExecutionContext:
        """Unified execution context."""
        return self._context

    @property
    def job(self) -> JobState | None:
        """Current job state."""
        return self._context._current_job

    @property
    def jobs(self) -> list[JobState]:
        """All jobs in current run."""
        return self._context.jobs

    @property
    def plugin(self) -> dict[str, dict]:
        """Current job's plugin data."""
        return self._context.plugin

    @property
    def plugins(self) -> dict[str, dict]:
        """All plugin data by target_id."""
        return self._context.plugins

    def _emit(self, event_name: str, data: dict[str, Any] = None, source: str = "state"):
        """Emit event. Delegates to StateEventEmitter."""
        self._event_emitter.emit(event_name, data, source)

    def _log(self, level: str, component: str, message: str, **kwargs):
        """Log with debugger."""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func(component, message, **kwargs)

    def _generate_id(self) -> str:
        """Generate unique ID."""
        return str(uuid4())

    def start_run(self, config: dict[str, Any]) -> str:
        """Start new run with given config. Returns run ID."""
        run_id = self._generate_id()

        self._config = config.copy()

        self._run = RunState(
            id=run_id,
            config=config
        )
        self._run.start()

        self._persistence_delegate.save_run(self._run)

        self._log("debug", "run", "Started run", id=run_id)

        return run_id

    def complete_run(self) -> RunState:
        """
        Complete current run.
        
        Returns:
            Final RunState
        """
        if not self._run:
            raise RuntimeError("No active run")

        self._run.complete()

        self._persistence_delegate.save_run(self._run)

        self._log("info", "run", "Run completed",
                 matches=self._run.status.total_jobs,
                 errors=self._run.status.failed,
                 duration_ms=self._run.status.duration_ms)

        return self._run

    def create_job(self, input_value: str, input_data: dict[str, Any] = None) -> str:
        """Create new job. Returns job ID. Delegates to JobManager."""
        if not self._run:
            raise RuntimeError("no active run")
        return self._job_manager.create_job(self._run, input_value, input_data)

    def set_current_job(self, job_id: str) -> None:
        """Set current job context. Delegates to JobManager."""
        self._job_manager.set_current_job(job_id)

    def clear_current_job(self) -> None:
        """Clear current job context. Delegates to JobManager."""
        self._job_manager.clear_current_job()

    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """Update job state. Delegates to JobManager."""
        self._job_manager.update_job(job_id, key, value)

    def update_plugin(self, target_id: str, plugin_name: str, data: dict[str, Any]) -> None:
        """Update plugin data. Delegates to PluginDataManager."""
        self._plugin_manager.update_plugin(
            target_id=target_id,
            plugin_name=plugin_name,
            data=data,
            run=self._run,
            get_job_func=self.get_job_by_id
        )

    def get_job(self, index: int) -> JobState | None:
        """Get job by index. Delegates to JobManager."""
        return self._job_manager.get_job(index)

    def get_job_by_id(self, job_id: str) -> JobState | None:
        """Get job by ID. Delegates to JobManager."""
        return self._job_manager.get_job_by_id(job_id)

    def get_all_jobs(self) -> list[JobState]:
        """Get all jobs in current run. Delegates to JobManager."""
        return self._job_manager.get_all_jobs()

    def complete_job(self, index: int):
        """Mark job as completed. Delegates to JobManager."""
        if not self._run:
            raise RuntimeError("No active run")
        self._job_manager.complete_job(self._run, index)

    def get_job_plugin_names(self, job_id: str) -> list[str]:
        """Get list of plugins for a job. Delegates to PluginDataManager."""
        return self._plugin_manager.get_plugin_names(job_id, self.get_job_by_id)

    def get_all_plugin_names(self) -> list[str]:
        """
        Get list of all plugin names that have been used in current run.
        
        Returns:
            List of unique plugin names across all jobs
        """
        plugin_names = set()

        for job in self._context.jobs:
            if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                plugin_names.update(job.plugins.keys())

        # Collect from run state
        if self._run and self._run.plugins:
            plugin_names.update(self._run.plugins.keys())

        return sorted(plugin_names)

    def get_plugin_data(self, job_id: str, plugin_name: str) -> dict[str, Any] | None:
        """Get plugin data for a job. Delegates to PluginDataManager."""
        return self._plugin_manager.get_plugin_data(job_id, plugin_name)

    def get_all_plugin_data(self, job_id: str) -> dict[str, dict[str, Any]]:
        """Get all plugin data for a job. Delegates to PluginDataManager."""
        return self._plugin_manager.get_all_plugin_data(job_id)

    def mark_plugin_not_supported(self, job_index: int, plugin_name: str):
        """Mark plugin as skipped."""
        # Legacy method - no longer needed with job.status.plugins
        self._emit(Events.PLUGIN_SKIPPED, {
            "job_index": job_index,
            "plugin_name": plugin_name,
            "reason": "not_supported"
        })

    def add_task_result(self, job_index: int, task_result: dict[str, Any]):
        """Add task result to job output."""
        job = self.get_job(job_index)
        if job:
            if 'tasks' not in job.output.data:
                job.output.data['tasks'] = {}

            task_name = task_result.get('name', 'unnamed')
            job.output.data['tasks'][task_name] = task_result

            # Add to output.values if save task
            if task_result.get('type') == 'save' and task_result.get('success'):
                dest = task_result.get('destination')
                if dest:
                    job.output.values.append(dest)

    def build_template_context(self, job_index: int) -> dict[str, Any]:
        """Build Jinja2 template context from state.
        
        Delegates to TemplateContextBuilder for SRP compliance.
        """
        job = self.get_job(job_index)
        if not job:
            return {}

        return self._template_builder.build_job_context(
            job=job,
            run=self._run,
            all_jobs=self._context.jobs
        )



StateManager = GlobalStateManager
