"""Global State Manager - Unified state management for runs and jobs."""

from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from .context import ExecutionContext
from .data_resolver import _walk_dotted
from .event_emitter import StateEventEmitter
from .job_manager import JobManager
from .merge import merge_patch
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
        event_bus: Optional['EventBus'] = None,
        persistence_mode: Optional[str] = None,
    ):
        """Reconfigure dependencies.

        ``persistence_mode`` (S37 PASS 2): the resolved mode used for the
        run ('full' | 'degraded' | 'off'). Threaded into RunState so the
        Mongo `runs.persistence_mode` field reflects what actually ran (not
        only what config requested). Defaults to 'degraded' if never set.
        """
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
        if persistence_mode is not None:
            self._persistence_mode_resolved = persistence_mode

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
            config=config,
            persistence_mode=getattr(self, "_persistence_mode_resolved", "degraded"),
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

    def configure_resolver(
        self,
        data_priority: dict[str, list[str]],
        emits_map: dict[str, dict[str, list[str]]],
        run_modes: dict[str, str] | None = None,
    ) -> None:
        """Configure the data namespace resolver (S39 R15 §D3 / S40).

        Called by the orchestrator after the registry has loaded
        plugins (so ``emits_map`` and ``run_modes`` are known) and
        the run config is merged (so ``data_priority`` is known).
        Subsequent plugin writes recompute ``run.data``.
        """
        self._plugin_manager.set_resolver_config(
            data_priority, emits_map, run_modes=run_modes,
        )

    def read_state(self, path: str | None = None) -> Any:
        """Return the run snapshot, optionally projected by dotted path."""
        snapshot = self._snapshot()
        if not path:
            return snapshot
        return _walk_dotted(snapshot, path)

    def apply_state_patch(self, patch: dict[str, Any], mode: str = "merge") -> None:
        """Apply a JSON patch to the live run (S40).

        ``mode='merge'`` is RFC 7396. ``mode='replace'`` overwrites
        named subtrees. Identity fields (run id, job id/index) are
        ignored. ``data`` is recomputed from emits/priority, not
        written by the patch.
        """
        if not self._run:
            raise RuntimeError("No active run")
        if not isinstance(patch, dict):
            raise TypeError("update_state patch must be a dict")
        if mode not in ("merge", "replace"):
            raise ValueError(f"update_state mode must be 'merge' or 'replace', got {mode!r}")

        replace = mode == "replace"
        touched_jobs: list[JobState] = []

        plugins_patch = patch.get("plugins")
        if isinstance(plugins_patch, dict):
            self._apply_plugin_map(self._run.plugins, plugins_patch, replace)
            run_slot = self._run.id
            self._context._all_plugins.setdefault(run_slot, {})
            self._context._all_plugins[run_slot] = dict(self._run.plugins)

        jobs_patch = patch.get("jobs")
        if isinstance(jobs_patch, dict):
            for job_id, job_patch in jobs_patch.items():
                if job_patch is None:
                    continue
                job = self.get_job_by_id(job_id)
                if not job:
                    raise ValueError(
                        f"Job {job_id} not found; use create_job to create jobs"
                    )
                if not isinstance(job_patch, dict):
                    continue
                self._apply_job_patch(job, job_patch, replace)
                touched_jobs.append(job)
                plugins_patch = job_patch.get("plugins")
                if isinstance(plugins_patch, dict) and self._run:
                    for pname, pdata in plugins_patch.items():
                        if pdata is None:
                            continue
                        self._persistence_delegate.save_plugin({
                            "job_id": job.id,
                            "plugin_name": pname,
                            "data": job.plugins.get(pname, pdata),
                            "run_id": job.run_id,
                            "job_index": job.index,
                        })

        for job in touched_jobs:
            self._persistence_delegate.save_job(job)

        self._plugin_manager._recompute_data_envelope(self._run)
        self._persistence_delegate.save_run(self._run)

    def _snapshot(self) -> dict[str, Any]:
        if not self._run:
            raise RuntimeError("No active run")
        jobs: dict[str, Any] = {}
        for job in self.get_all_jobs():
            jobs[job.id] = {
                "id": job.id,
                "index": job.index,
                "input": job.input.to_dict(),
                "output": job.output.to_dict(),
                "status": job.status.to_dict(),
                "plugins": job.plugins,
            }
        return {
            "id": self._run.id,
            "status": self._run.status.to_dict(),
            "config": self._run.config,
            "plugins": self._run.plugins,
            "jobs": jobs,
            "data": self._run.data,
        }

    def _apply_plugin_map(
        self,
        target: dict[str, Any],
        patch: dict[str, Any],
        replace: bool,
    ) -> None:
        for name, payload in patch.items():
            if payload is None:
                target.pop(name, None)
            elif replace or name not in target or not isinstance(payload, dict):
                target[name] = payload
            elif isinstance(target.get(name), dict) and isinstance(payload, dict):
                target[name] = merge_patch(target[name], payload)
            else:
                target[name] = payload

    def _apply_job_patch(
        self,
        job: JobState,
        job_patch: dict[str, Any],
        replace: bool,
    ) -> None:
        plugins_patch = job_patch.get("plugins")
        if isinstance(plugins_patch, dict):
            self._apply_plugin_map(job.plugins, plugins_patch, replace)
            self._context._all_plugins.setdefault(job.id, {})
            self._context._all_plugins[job.id] = dict(job.plugins)
            if self._context._current_job and self._context._current_job.id == job.id:
                self._context._current_plugins = job.plugins

        output_patch = job_patch.get("output")
        if isinstance(output_patch, dict):
            if "values" in output_patch:
                job.output.values = list(output_patch["values"] or [])
            if "data" in output_patch:
                data = output_patch["data"]
                if replace or not isinstance(data, dict) or not isinstance(job.output.data, dict):
                    job.output.data = data if isinstance(data, dict) else {}
                else:
                    job.output.data = merge_patch(job.output.data, data)

        input_patch = job_patch.get("input")
        if isinstance(input_patch, dict):
            if "value" in input_patch and input_patch["value"] is not None:
                job.input.value = input_patch["value"]
            if "data" in input_patch and isinstance(input_patch["data"], dict):
                if replace:
                    job.input.data = dict(input_patch["data"])
                else:
                    job.input.data = merge_patch(job.input.data, input_patch["data"])

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
