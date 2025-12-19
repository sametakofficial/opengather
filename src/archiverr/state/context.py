"""Execution context - unified job and plugin state container."""

from dataclasses import dataclass, field

from .models import JobState


@dataclass
class ExecutionContext:
    """Unified execution context for job-level state."""

    _current_job: JobState | None = None
    _jobs: dict[str, JobState] = field(default_factory=dict)
    _current_plugins: dict[str, dict] = field(default_factory=dict)
    _all_plugins: dict[str, dict] = field(default_factory=dict)

    @property
    def job(self) -> JobState:
        """
        current job being processed (read-write).
        
        raises:
            runtimeerror: if no active job
        """
        if not self._current_job:
            raise RuntimeError("no active job in context")
        return self._current_job

    @property
    def jobs(self) -> list[JobState]:
        """all jobs in current run (read-only list for backward compat)."""
        return list(self._jobs.values())

    @property
    def jobs_dict(self) -> dict[str, JobState]:
        """All jobs as key-based dict."""
        return self._jobs

    @property
    def plugin(self) -> dict[str, dict]:
        """current job's plugin data (read-write)."""
        return self._current_plugins

    @property
    def plugins(self) -> dict[str, dict]:
        """all jobs' plugin data (read-only, key-based)."""
        return self._all_plugins

    def set_current_job(self, job: JobState) -> None:
        """set current job for processing."""
        self._current_job = job

    def clear_current_job(self) -> None:
        """clear current job after processing."""
        self._current_job = None
        self._current_plugins = {}

    def add_job(self, job: JobState) -> None:
        """Add job to jobs dict."""
        self._jobs[job.id] = job

    def get_job(self, job_id: str) -> JobState | None:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def get_job_by_index(self, index: int) -> JobState | None:
        """get job by index (backward compat)."""
        for job in self._jobs.values():
            if job.index == index:
                return job
        return None

    def update_plugin_data(self, plugin_name: str, data: dict) -> None:
        """update plugin data for current job."""
        if plugin_name not in self._current_plugins:
            self._current_plugins[plugin_name] = {}
        self._current_plugins[plugin_name] = data

    def get_plugin_data(self, plugin_name: str) -> dict | None:
        """get plugin data for current job."""
        return self._current_plugins.get(plugin_name)

    def has_active_job(self) -> bool:
        """check if there is an active job."""
        return self._current_job is not None

    def reset(self) -> None:
        """reset context (for testing)."""
        self._current_job = None
        self._jobs = {}
        self._current_plugins = {}
        self._all_plugins = {}
