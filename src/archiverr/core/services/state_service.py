"""
State Service Implementation

Wraps StateManager to provide clean interface for plugins.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from archiverr.state.manager import StateManager
    from archiverr.state.models import JobState, RunState
    from archiverr.infrastructure.database.interface import PersistenceInterface


class StateServiceImpl:
    """
    StateService implementation that wraps StateManager.
    
    Provides:
    - Read-only access to run/job state
    - Plugin data access (from separate collection)
    - Plugin data persistence
    """
    
    def __init__(
        self,
        state_manager: 'StateManager',
        persistence: Optional['PersistenceInterface'] = None,
        current_job_id: Optional[str] = None
    ):
        """
        Initialize state service.
        
        Args:
            state_manager: StateManager instance
            persistence: Persistence layer for plugin data
            current_job_id: Current job context (set by executor)
        """
        self._manager = state_manager
        self._persistence = persistence
        self._current_job_id = current_job_id
        
        # In-memory plugin data cache (for current run)
        self._plugin_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
    
    def set_current_job(self, job_id: str) -> None:
        """
        Set current job context.
        
        Called by executor before plugin execution.
        """
        self._current_job_id = job_id
    
    def get_current_job(self) -> 'JobState':
        """Get currently executing job."""
        from archiverr.state.models import JobState
        
        if not self._current_job_id:
            raise RuntimeError("No current job set - ensure executor sets job context")
        
        # Try to get from manager's jobs dict
        if hasattr(self._manager, '_jobs'):
            for job in self._manager._jobs.values():
                if hasattr(job, 'id') and job.id == self._current_job_id:
                    return job
        
        # Fallback: parse job_id to get index
        # job_id format: job_run_abc123_0
        try:
            parts = self._current_job_id.split('_')
            if len(parts) >= 2:
                index = int(parts[-1])
                job = self._manager.get_match(index)
                if job:
                    return job
        except (ValueError, AttributeError):
            pass
        
        raise RuntimeError(f"Job not found: {self._current_job_id}")
    
    def get_job(self, job_id: str) -> Optional['JobState']:
        """Get job by ID."""
        # Parse job_id to get index
        try:
            parts = job_id.split('_')
            if len(parts) >= 2:
                index = int(parts[-1])
                return self._manager.get_match(index)
        except (ValueError, AttributeError):
            pass
        return None
    
    def get_job_by_index(self, index: int) -> Optional['JobState']:
        """Get job by index within current run."""
        return self._manager.get_match(index)
    
    def get_all_jobs(self) -> List['JobState']:
        """Get all jobs in current run."""
        if hasattr(self._manager, '_matches'):
            return list(self._manager._matches.values())
        if hasattr(self._manager, '_jobs'):
            return list(self._manager._jobs.values())
        return []
    
    def get_run(self) -> 'RunState':
        """Get current run state."""
        from archiverr.state.models import RunState
        
        # Try new-style manager
        if hasattr(self._manager, '_run') and self._manager._run:
            return self._manager._run
        
        # Try legacy-style manager
        if hasattr(self._manager, '_execution') and self._manager._execution:
            # Convert ExecutionState to RunState-like object
            exec_state = self._manager._execution
            return exec_state
        
        raise RuntimeError("No active run")
    
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Dict[str, Any]:
        """
        Get plugin result data for a job.
        
        Checks cache first, then persistence layer.
        """
        # Check cache
        job_plugins = self._plugin_cache.get(job_id, {})
        if plugin_name in job_plugins:
            cached = job_plugins[plugin_name]
            return cached.get('data', {})
        
        # Try persistence
        if self._persistence:
            try:
                plugin_data = self._persistence.get_plugin(job_id, plugin_name)
                if plugin_data:
                    # Cache it
                    if job_id not in self._plugin_cache:
                        self._plugin_cache[job_id] = {}
                    self._plugin_cache[job_id][plugin_name] = plugin_data
                    return plugin_data.get('data', {})
            except Exception:
                pass
        
        # Try legacy: get from job's plugins dict
        job = self.get_job(job_id)
        if job and hasattr(job, 'plugins'):
            return job.plugins.get(plugin_name, {})
        
        return {}
    
    def save_plugin_data(
        self,
        job_id: str,
        plugin_name: str,
        stage: str,
        data: Dict[str, Any],
        status: Dict[str, Any] = None
    ) -> None:
        """
        Save plugin execution result.
        
        Saves to:
        1. In-memory cache
        2. Persistence layer (if available)
        """
        # Get run_id from current run
        run_id = ""
        try:
            run = self.get_run()
            run_id = getattr(run, 'id', '') or getattr(run, 'execution_id', '')
        except RuntimeError:
            pass
        
        # Parse job_index from job_id
        job_index = 0
        try:
            parts = job_id.split('_')
            if len(parts) >= 2:
                job_index = int(parts[-1])
        except (ValueError, IndexError):
            pass
        
        # Build plugin document
        plugin_doc = {
            'job_id': job_id,
            'run_id': run_id,
            'job_index': job_index,
            'plugin_name': plugin_name,
            'stage': stage,
            'status': status or {
                'success': True,
                'started_at': datetime.now().isoformat(),
                'finished_at': datetime.now().isoformat(),
                'duration_ms': 0
            },
            'data': data
        }
        
        # Cache
        if job_id not in self._plugin_cache:
            self._plugin_cache[job_id] = {}
        self._plugin_cache[job_id][plugin_name] = plugin_doc
        
        # Persist
        if self._persistence:
            try:
                self._persistence.save_plugin(plugin_doc)
            except Exception:
                pass  # Log warning but don't fail
        
        # Also update legacy job.plugins if available
        try:
            job = self.get_job(job_id)
            if job and hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                job.plugins[plugin_name] = {'status': plugin_doc['status'], **data}
        except (AttributeError, TypeError):
            pass  # Job not found or plugins not a dict
    
    def clear_cache(self) -> None:
        """Clear plugin data cache (call at run end)."""
        self._plugin_cache.clear()
