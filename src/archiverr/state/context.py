"""
execution context - unified job and plugin state container

consolidates job, jobs, plugin, plugins into single context object.
reduces 6 global state objects to 3.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import JobState


@dataclass
class ExecutionContext:
    """
    unified execution context for job-level state.
    
    replaces separate job, jobs, plugin, plugins objects with single unified container.
    provides clear read-only vs read-write boundaries.
    """
    
    _current_job: Optional[JobState] = None
    _jobs: List[JobState] = field(default_factory=list)
    _current_plugins: Dict[str, Dict] = field(default_factory=dict)
    _all_plugins: List[Dict] = field(default_factory=list)
    
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
        """all jobs in current run (read-only)."""
        return self._jobs
    
    @property
    def plugin(self) -> Dict[str, Dict]:
        """current job's plugin data (read-write)."""
        return self._current_plugins
    
    @property
    def plugins(self) -> List[Dict]:
        """all jobs' plugin data (read-only)."""
        return self._all_plugins
    
    def set_current_job(self, job: JobState) -> None:
        """set current job for processing."""
        self._current_job = job
    
    def clear_current_job(self) -> None:
        """clear current job after processing."""
        self._current_job = None
        self._current_plugins = {}
    
    def add_job(self, job: JobState) -> None:
        """add job to jobs list."""
        self._jobs.append(job)
    
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
        self._jobs = []
        self._current_plugins = {}
        self._all_plugins = []
