"""
execution context - unified job and plugin state container

consolidates job, jobs, plugin, plugins into single context object.
reduces 6 global state objects to 3.

Session 17: Changed _jobs from List to Dict (key-based like plugins).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .models import JobState


@dataclass
class ExecutionContext:
    """
    unified execution context for job-level state.
    
    replaces separate job, jobs, plugin, plugins objects with single unified container.
    provides clear read-only vs read-write boundaries.
    
    Session 17: jobs is now key-based Dict[job_id, JobState] like plugins.
    """
    
    _current_job: Optional[JobState] = None
    _jobs: Dict[str, JobState] = field(default_factory=dict)
    _current_plugins: Dict[str, Dict] = field(default_factory=dict)
    _all_plugins: Dict[str, Dict] = field(default_factory=dict)
    
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
    def jobs(self) -> List[JobState]:
        """all jobs in current run (read-only list for backward compat)."""
        return list(self._jobs.values())
    
    @property
    def jobs_dict(self) -> Dict[str, JobState]:
        """all jobs as key-based dict (Session 17)."""
        return self._jobs
    
    @property
    def plugin(self) -> Dict[str, Dict]:
        """current job's plugin data (read-write)."""
        return self._current_plugins
    
    @property
    def plugins(self) -> Dict[str, Dict]:
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
        """add job to jobs dict (Session 17: key-based)."""
        self._jobs[job.id] = job
    
    def get_job(self, job_id: str) -> Optional[JobState]:
        """get job by id (Session 17)."""
        return self._jobs.get(job_id)
    
    def get_job_by_index(self, index: int) -> Optional[JobState]:
        """get job by index (backward compat)."""
        for job in self._jobs.values():
            if job.index == index:
                return job
        return None
    
    def update_plugin_data(self, plugin_name: str, data: Dict) -> None:
        """update plugin data for current job."""
        if plugin_name not in self._current_plugins:
            self._current_plugins[plugin_name] = {}
        self._current_plugins[plugin_name] = data
    
    def get_plugin_data(self, plugin_name: str) -> Optional[Dict]:
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
