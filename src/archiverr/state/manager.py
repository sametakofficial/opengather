"""Global State Manager - Unified state management for runs and jobs."""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

from .models import RunState, JobState, InputData, StateEnum
from .context import ExecutionContext

if TYPE_CHECKING:
    from archiverr.events import EventBus


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
        
        self._run: Optional[RunState] = None
        self._config: Dict[str, Any] = {}
        self._context: ExecutionContext = ExecutionContext()
    
    def configure(
        self, 
        persistence=None,
        debugger=None,
        event_bus: Optional['EventBus'] = None
    ):
        """Reconfigure dependencies."""
        if persistence is not None:
            self._persistence = persistence
        if debugger is not None:
            self._debugger = debugger
        if event_bus is not None:
            self._event_bus = event_bus
    
    def reset(self):
        """reset state for new run."""
        self._run = None
        self._config = {}
        self._context.reset()
    
    @property
    def run(self) -> Optional[RunState]:
        """Current run state (read-only for plugins)."""
        return self._run
    
    @property
    def config(self) -> Dict[str, Any]:
        """Frozen config (read-only for plugins)."""
        return self._config
    
    @property
    def context(self) -> ExecutionContext:
        """Unified execution context."""
        return self._context
    
    @property
    def job(self) -> Optional[JobState]:
        """Current job state."""
        return self._context._current_job
    
    @property
    def jobs(self) -> List[JobState]:
        """All jobs in current run."""
        return self._context.jobs
    
    @property
    def plugin(self) -> Dict[str, Dict]:
        """Current job's plugin data."""
        return self._context.plugin
    
    @property
    def plugins(self) -> Dict[str, Dict]:
        """All plugin data by target_id."""
        return self._context.plugins
    
    def _emit(self, event_name: str, data: Dict[str, Any] = None, source: str = "state"):
        """Emit event if event bus is configured."""
        if self._event_bus:
            self._event_bus.emit(event_name, data or {}, source)
    
    def _log(self, level: str, component: str, message: str, **kwargs):
        """Log with debugger."""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func(component, message, **kwargs)
    
    def _generate_id(self) -> str:
        """Generate unique ID."""
        return str(uuid4())[:8]
    
    def start_run(self, config: Dict[str, Any]) -> str:
        """Start new run with given config. Returns run ID."""
        run_id = self._generate_id()
        
        self._config = config.copy()
        
        self._run = RunState(
            id=run_id,
            config=config
        )
        self._run.start()
        
        if self._persistence and hasattr(self._persistence, 'save_run'):
            self._persistence.save_run(self._run)
        
        self._log("debug", "run", "Started run", id=run_id)
        
        self._emit("run.started", {
            "run_id": run_id,
            "config": config,
            "plugins": list(config.get('plugins', {}).keys()) if isinstance(config.get('plugins'), dict) else []
        })
        
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
        
        if self._persistence and hasattr(self._persistence, 'save_run'):
            self._persistence.save_run(self._run)
        
        self._log("info", "run", "Run completed",
                 matches=self._run.status.total_jobs,
                 errors=self._run.status.failed,
                 duration_ms=self._run.status.duration_ms)
        
        self._emit("execution.completed", {
            "execution_id": self._run.id,
            "total_matches": self._run.status.total_jobs,
            "completed_matches": self._run.status.completed,
            "failed_matches": self._run.status.failed,
            "duration_ms": self._run.status.duration_ms,
            "success": self._run.status.success
        })
        
        return self._run
    
    def create_job(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
        """Create new job. Returns job ID."""
        if not self._run:
            raise RuntimeError("no active run")
        
        index = len(self._context._jobs)
        
        job = JobState(
            index=index,
            run_id=self._run.id,
            input=InputData(
                value=input_value,
                data=input_data or {}
            )
        )
        job.start()
        
        self._context.add_job(job)
        self._run.increment_jobs()
        
        if self._persistence:
            if hasattr(self._persistence, 'save_job'):
                self._persistence.save_job(job)
            if hasattr(self._persistence, 'save_run'):
                self._persistence.save_run(self._run)
        
        self._log("debug", "job", f"Created job {index}", input_value=input_value)
        
        self._emit("job.created", {
            "index": index,
            "job_id": job.id,
            "input_value": input_value,
            "run_id": self._run.id
        })
        
        return job.id
    
    def set_current_job(self, job_id: str) -> None:
        """Set current job context for per_job plugin execution."""
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"job {job_id} not found")
        self._context.set_current_job(job)
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            self._context._current_plugins = job.plugins
    
    def clear_current_job(self) -> None:
        """Clear current job context."""
        self._context.clear_current_job()
    
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
        
        self._emit("job.updated", {
            "job_id": job_id,
            "key": key,
            "value": value
        })
    
    def update_plugin(self, target_id: str, plugin_name: str, data: Dict[str, Any]) -> None:
        """Update plugin data for a job or run target."""
        # Determine if this is a run or job target
        is_run_target = target_id.startswith("run_") or (self._run and target_id == self._run.id)
        
        if is_run_target:
            # Per-run plugin (e.g., scanner)
            run_id = target_id if target_id.startswith("run_") else f"run_{target_id}"
            
            if self._run:
                # Store directly in RunState.plugins
                self._run.plugins[plugin_name] = data

                # Store in unified context plugins map
                self._context._all_plugins.setdefault(run_id, {})[plugin_name] = data

                if self._persistence and hasattr(self._persistence, 'update_plugin_doc'):
                    try:
                        self._persistence.update_plugin_doc(run_id, plugin_name, data)
                    except Exception as e:
                        self._log("error", "state", f"Failed to update plugin doc: {e}")
                
                if self._persistence and hasattr(self._persistence, 'save_run'):
                    self._persistence.save_run(self._run)
            
            self._log("debug", "plugin_data",
                     f"Updated run plugin {plugin_name}",
                     run_id=run_id,
                     data_keys=list(data.keys()) if isinstance(data, dict) else [])
        else:
            # Per-job plugin
            job_id = target_id
            
            # Update JobState.plugins with flat data
            job = self.get_job_by_id(job_id)
            if job:
                job.plugins[plugin_name] = data

                # Store in unified context plugins map
                self._context._all_plugins.setdefault(job_id, {})[plugin_name] = data

                if self._persistence and hasattr(self._persistence, 'update_plugin_doc'):
                    try:
                        self._persistence.update_plugin_doc(job_id, plugin_name, data)
                    except Exception as e:
                        self._log("error", "state", f"Failed to update plugin doc: {e}")

                # Keep current job plugin view in sync
                if self._context._current_job and self._context._current_job.id == job_id:
                    self._context._current_plugins = job.plugins
                
                if self._persistence and hasattr(self._persistence, 'save_plugin'):
                    try:
                        plugin_doc = {
                            "job_id": job_id,
                            "plugin_name": plugin_name,
                            "data": data,
                            "run_id": job.run_id,
                            "job_index": job.index
                        }
                        self._persistence.save_plugin(plugin_doc)
                    except Exception as e:
                        self._log("error", "state", f"Failed to save plugin data: {e}")
                
                self._log("debug", "plugin_data", 
                         f"Updated plugin {plugin_name} for job {job_id}",
                         data_keys=list(data.keys()) if isinstance(data, dict) else [],
                         data_size=len(str(data)))
        
        self._emit("plugin.updated", {
            "target_id": target_id,
            "plugin_name": plugin_name,
            "data": data
        })
    
    def get_job(self, index: int) -> Optional[JobState]:
        """Get job by index."""
        return self._context.get_job_by_index(index)
    
    def get_job_by_id(self, job_id: str) -> Optional[JobState]:
        """Get job by ID."""
        return self._context.get_job(job_id)
    
    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs in current run."""
        return self._context.jobs
    
    def complete_job(self, index: int):
        """Mark job as completed."""
        job = self.get_job(index)
        if not job:
            raise ValueError(f"Job {index} not found")
        
        job.complete(success=job.status.success)
        
        # Update run stats
        self._run.increment_completed()
        if not job.status.success:
            self._run.increment_failed()
        
        if self._persistence and hasattr(self._persistence, 'save_job'):
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
        
        event_name = "job.completed" if job.status.success else "job.failed"
        self._emit(event_name, {
            "index": index,
            "success": job.status.success,
            "duration_ms": job.status.duration_ms,
            "executed_plugins": executed_plugins,
            "failed_plugins": failed_plugins
        })
    
    def get_job_plugin_names(self, job_id: str) -> List[str]:
        """
        Get list of all plugins that have data for a job.
        
        This replaces hardcoded plugin name lists.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of plugin names that have data for this job
        """
        job = self.get_job_by_id(job_id)
        if not job:
            return []
        
        # Get plugins from job.plugins dict
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            return list(job.plugins.keys())
        
        return []
    
    def get_all_plugin_names(self) -> List[str]:
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
        
        return sorted(list(plugin_names))
    
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin data for a job.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None
        """
        # Try from job.plugins
        job = self.get_job_by_id(job_id)
        if job:
            return job.plugins.get(plugin_name)
        
        return None
    
    def save_plugin_data(self, job_id: str, plugin_name: str, data: Dict[str, Any]):
        """
        Save plugin data for a job.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            data: Plugin output data
        """
        # Update job.plugins for template access
        job = self.get_job_by_id(job_id)
        if job:
            job.plugins[plugin_name] = data
        
        # Persist to plugins collection
        if self._persistence and hasattr(self._persistence, 'save_plugin'):
            try:
                plugin_doc = {
                    "job_id": job_id,
                    "plugin_name": plugin_name,
                    "data": data,
                    # Add metadata if available
                    "run_id": job.run_id if job else (self._run.id if self._run else ""),
                    "job_index": job.index if job else 0
                }
                self._persistence.save_plugin(plugin_doc)
            except Exception as e:
                self._log("error", "state", f"Failed to save plugin data: {e}")

    def get_all_plugin_data(self, job_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all plugin data for a job."""
        job = self.get_job_by_id(job_id)
        if job:
            return job.plugins.copy()
        return {}
    
    def update_plugin_result(self, job_index: int, plugin_name: str, result):
        """Update plugin result for a job."""
        job = self.get_job(job_index)
        if not job:
            raise ValueError(f"Job {job_index} not found")
        
        # Extract data from result
        data = {}
        if hasattr(result, 'data'):
            data = result.data
        elif isinstance(result, dict):
            data = result
        
        # Update job.plugins
        job.plugins[plugin_name] = data
        
                
        # Persist
        if self._persistence:
            if hasattr(self._persistence, 'save_plugin_result'):
                self._persistence.save_plugin_result(
                    self._run.id if self._run else "",
                    job_index,
                    plugin_name,
                    result.to_dict() if hasattr(result, 'to_dict') else data
                )
    
    def mark_plugin_not_supported(self, job_index: int, plugin_name: str):
        """Mark plugin as skipped."""
        # Legacy method - no longer needed with job.status.plugins
        self._emit("plugin.skipped", {
            "job_index": job_index,
            "plugin_name": plugin_name,
            "reason": "not_supported"
        })
    
    def add_task_result(self, job_index: int, task_result: Dict[str, Any]):
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
    
    def build_template_context(self, job_index: int) -> Dict[str, Any]:
        """Build Jinja2 template context from state."""
        job = self.get_job(job_index)
        if not job:
            return {}
        
        # Run context
        run_context = {
            "id": self._run.id if self._run else "",
            "status": {
                "success": self._run.status.success if self._run else True,
                "total_jobs": self._run.status.total_jobs if self._run else 0,
                "completed": self._run.status.completed if self._run else 0,
                "failed": self._run.status.failed if self._run else 0
            },
            "config": self._run.config if self._run else {}
        }
        
        # Build executed/failed/skipped from job.status.plugins
        executed = []
        failed = []
        skipped = []
        for pname, pstatus in job.status.plugins.items():
            if isinstance(pstatus, dict):
                state = pstatus.get('state', '')
                if state == 'failed' or not pstatus.get('success', True):
                    failed.append(pname)
                elif state == 'skipped':
                    skipped.append(pname)
                elif state == 'completed':
                    executed.append(pname)
        
        # Job context
        job_context = {
            "index": job.index,
            "id": job.id,
            "input": {
                "value": job.input.value,
                "data": job.input.data
            },
            "output": {
                "values": job.output.values,
                "data": job.output.data
            },
            "status": {
                "success": job.status.success,
                "executed": executed,
                "failed": failed,
                "skipped": skipped,
                "plugins": job.status.plugins
            },
            "plugins": job.plugins
        }
        
        # Full context
        context = {
            "run": run_context,
            "job": job_context,
            "jobs": [self._job_to_context(j) for j in self._context.jobs],
            "config": self._run.config if self._run else {},
            "options": self._run.config.get('options', {}) if self._run else {}
        }
        
        # Add plugin shortcuts
        for plugin_name, plugin_data in job.plugins.items():
            context[plugin_name] = plugin_data
        
        return context
    
    def _job_to_context(self, job: JobState) -> Dict[str, Any]:
        """Convert job to template context dict."""
        return {
            "index": job.index,
            "id": job.id,
            "input": {
                "value": job.input.value,
                "data": job.input.data
            },
            "plugins": job.plugins
        }
    


StateManager = GlobalStateManager
