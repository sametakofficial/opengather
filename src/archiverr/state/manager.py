"""
Global State Manager - Session 12 Refactored

Session 12: 6 Global State Objects
- run: RunState (read-only for all)
- config: Dict (frozen, read-only for all)
- job: JobState (current job, per_job only)
- jobs: List[JobState] (all jobs, per_job read-only)
- plugin: Dict (current job plugins, per_job only)
- plugins: List[Dict] (all jobs plugins, per_job read-only)
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

from .models import RunState, JobState, InputData, StateEnum, PluginData, PluginStatus, PluginState
from .context import ExecutionContext

if TYPE_CHECKING:
    from archiverr.events import EventBus


class GlobalStateManager:
    """
    session 14 global state manager - normalized.
    
    manages 3 global state objects (reduced from 6):
    1. run: runstate (read-only for all plugins)
    2. config: dict (frozen config, read-only for all)
    3. context: executioncontext (unified job + plugin state)
    
    context contains:
        - job: current job (read-write)
        - jobs: all jobs (read-only)
        - plugin: current job plugins (read-write)
        - plugins: all jobs plugins (read-only)
    """
    
    def __init__(
        self,
        persistence=None,
        debugger=None,
        event_bus: Optional['EventBus'] = None
    ):
        self._persistence = persistence
        self._debugger = debugger
        self._event_bus = event_bus
        
        # session 14: 3 global state objects
        self._run: Optional[RunState] = None
        self._config: Dict[str, Any] = {}
        self._context: ExecutionContext = ExecutionContext()
        
        # legacy: for backward compatibility during migration
        self._plugins_storage: Dict[str, Dict[str, PluginState]] = {}
    
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
        self._plugins_storage = {}
    
    # ==================== SESSION 14: GLOBAL STATE PROPERTIES ====================
    
    @property
    def run(self) -> Optional[RunState]:
        """global state 1: run (read-only for all plugins)"""
        return self._run
    
    @property
    def config(self) -> Dict[str, Any]:
        """global state 2: config (frozen, read-only for all plugins)"""
        return self._config
    
    @property
    def context(self) -> ExecutionContext:
        """global state 3: context (unified execution context)"""
        return self._context
    
    @property
    def job(self) -> Optional[JobState]:
        """current job (via context) - backward compat property"""
        return self._context._current_job
    
    @property
    def jobs(self) -> List[JobState]:
        """all jobs (via context) - backward compat property"""
        return self._context.jobs
    
    @property
    def plugin(self) -> Dict[str, Dict]:
        """current job plugins (via context) - backward compat property"""
        return self._context.plugin
    
    @property
    def plugins(self) -> List[Dict]:
        """all jobs plugins (via context) - backward compat property"""
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
    
    # ==================== RUN (was EXECUTION) ====================
    
    def start_run(self, config: Dict[str, Any]) -> str:
        """
        Start new run (Session 12).
        
        Args:
            config: Full config.yml content (frozen)
            
        Returns:
            Run ID
        """
        run_id = self._generate_id()
        
        # Session 12: Store frozen config
        self._config = config.copy()  # Frozen copy
        
        self._run = RunState(
            id=run_id,
            config=config
        )
        self._run.start()
        
        # Persist
        if self._persistence:
            if hasattr(self._persistence, 'save_run'):
                self._persistence.save_run(self._run)
            elif hasattr(self._persistence, 'save_execution'):
                # Legacy persistence adapter
                self._persistence.save_execution(self._run_to_execution())
        
        self._log("debug", "run", "Started run", id=run_id)
        
        self._emit("run.started", {
            "run_id": run_id,
            "config": config,
            "plugins": list(config.get('plugins', {}).keys()) if isinstance(config.get('plugins'), dict) else []
        })
        
        return run_id
    
    def complete_run(self, branch_name: str = "main") -> RunState:
        """
        Complete current run.
        
        Returns:
            Final RunState
        """
        if not self._run:
            raise RuntimeError("No active run")
        
        self._run.complete()
        
        # Persist
        if self._persistence:
            if hasattr(self._persistence, 'save_run'):
                self._persistence.save_run(self._run)
            elif hasattr(self._persistence, 'save_execution'):
                self._persistence.save_execution(self._run_to_execution())
        
        self._log("info", "execution", "Execution completed",
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
    
    def _run_to_execution(self):
        """Convert RunState to legacy ExecutionState format for persistence."""
        if not self._run:
            return None
        
        class LegacyExecution:
            def __init__(self, run: RunState):
                self.id = run.id
                self.started_at = run.status.started_at
                self.finished_at = run.status.finished_at
                self.duration_ms = run.status.duration_ms
                self.success = run.status.success
                self.status = type('Status', (), {'value': run.status.state.value})()
                self.total_matches = run.status.total_jobs
                self.completed_matches = run.status.completed
                self.failed_matches = run.status.failed
                self.config_snapshot = run.config
            
            def to_dict(self):
                return {
                    "_id": f"exec_{self.id}",
                    "id": self.id,
                    "started_at": self.started_at.isoformat() if self.started_at else None,
                    "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                    "duration_ms": self.duration_ms,
                    "success": self.success,
                    "status": self.status.value,
                    "summary": {
                        "total_matches": self.total_matches,
                        "completed_matches": self.completed_matches,
                        "failed_matches": self.failed_matches
                    },
                    "config_snapshot": self.config_snapshot
                }
        
        return LegacyExecution(self._run)
    
    @property
    def run(self) -> Optional[RunState]:
        """Get current run state."""
        return self._run
    
    @property
    def run_id(self) -> Optional[str]:
        """Get current run ID."""
        return self._run.id if self._run else None
    
    # Legacy property aliases
    @property
    def execution(self):
        """Legacy: Get current run as execution."""
        return self._run_to_execution()
    
    @property
    def execution_id(self) -> Optional[str]:
        """Legacy: Get current run ID."""
        return self.run_id
    
    # ==================== JOBS (was MATCHES) ====================
    
    def create_job(
        self,
        input_value: str,
        input_data: Dict[str, Any] = None,
        input_metadata: Dict[str, Any] = None,
        filled_by: str = None
    ) -> str:
        """
        create new job (session 14).
        
        args:
            input_value: input path or virtual identifier (plugin sets)
            input_data: plugin-specific input data (plugin sets)
            input_metadata: system metadata (source, modified_at, size_bytes, etc.)
            filled_by: plugin name that created this job
            
        returns:
            job id (string)
        """
        if not self._run:
            raise RuntimeError("no active run")
        
        index = len(self._context._jobs)
        
        # prepare metadata with system info + filled_by
        from datetime import datetime
        metadata = input_metadata or {}
        metadata['filled_by'] = filled_by or 'unknown'
        metadata['filled_at'] = datetime.utcnow().isoformat()
        
        job = JobState(
            index=index,
            run_id=self._run.id,
            input=InputData(
                value=input_value,
                data=input_data or {},
                metadata=metadata
            )
        )
        job.start()
        
        # session 14: add to context
        self._context.add_job(job)
        self._run.increment_jobs()
        
        # Initialize plugin storage for this job
        self._plugins_storage[job.id] = {}
        
        # Persist
        if self._persistence:
            if hasattr(self._persistence, 'save_job'):
                self._persistence.save_job(job)
            elif hasattr(self._persistence, 'save_match'):
                self._persistence.save_match(self._job_to_match(job))
            
            if hasattr(self._persistence, 'save_run'):
                self._persistence.save_run(self._run)
            elif hasattr(self._persistence, 'save_execution'):
                self._persistence.save_execution(self._run_to_execution())
        
        self._log("debug", "job", f"Created job {index}", input_value=input_value)
        
        self._emit("job.created", {
            "index": index,
            "job_id": job.id,
            "input_value": input_value,
            "run_id": self._run.id
        })
        
        return job.id
    
    def set_current_job(self, job_id: str) -> None:
        """
        set current job context (session 14).
        
        used by orchestrator to set current job before executing per_job plugins.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"job {job_id} not found")
        self._context.set_current_job(job)
    
    def clear_current_job(self) -> None:
        """clear current job context (session 14)."""
        self._context.clear_current_job()
    
    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """
        Update job state (Session 12 internal method).
        
        Called by PluginServices.updateJob(key, value).
        PluginServices provides job_id internally.
        
        Args:
            job_id: Job ID
            key: Dot-notation path (e.g., "output.values", "status.state")
            value: New value
        """
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
    
    def update_plugin(self, job_id: str, plugin_name: str, data: Dict[str, Any]) -> None:
        """
        Update plugin data (Session 12 internal method).
        
        Called by PluginServices.updatePlugin(data).
        PluginServices provides job_id and plugin_name internally.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            data: Plugin data (stored in plugin.{name}.data)
        """
        if job_id not in self._plugins_storage:
            self._plugins_storage[job_id] = {}
        
        if plugin_name not in self._plugins_storage[job_id]:
            self._plugins_storage[job_id][plugin_name] = PluginState()
        
        # Update plugin data
        self._plugins_storage[job_id][plugin_name].data = data
        
        # Also update JobState.plugins for backward compatibility
        job = self.get_job_by_id(job_id)
        if job:
            job.plugins[plugin_name] = self._plugins_storage[job_id][plugin_name].to_dict()
            
            # Debug logging
            data_keys = list(data.keys()) if isinstance(data, dict) else []
            self._log("debug", "plugin_data", 
                     f"Updated plugin {plugin_name} for job {job_id}",
                     data_keys=data_keys,
                     data_size=len(str(data)))
        
        self._emit("plugin.updated", {
            "job_id": job_id,
            "plugin_name": plugin_name,
            "data": data
        })
    
    def _job_to_match(self, job: JobState):
        """Convert JobState to legacy MatchState format for persistence."""
        class LegacyMatch:
            def __init__(self, j: JobState):
                self.index = j.index
                self.input_path = j.input.value
                self.execution_id = j.run_id
                self.success = j.status.success
                self.status = type('Status', (), {'value': j.status.state.value})()
                self.executed_plugins = j.status.executed
                self.failed_plugins = j.status.failed
                self.not_supported_plugins = j.status.skipped
                self.started_at = j.status.started_at
                self.finished_at = j.status.finished_at
                self.duration_ms = j.status.duration_ms
                self.plugins = j.plugins
                self.tasks = []
            
            @property
            def id(self):
                return f"match_{self.index}_{self.execution_id}"
            
            def to_dict(self):
                return {
                    "_id": self.id,
                    "execution_id": f"exec_{self.execution_id}",
                    "index": self.index,
                    "input_path": self.input_path,
                    "success": self.success,
                    "status": self.status.value,
                    "executed_plugins": self.executed_plugins,
                    "failed_plugins": self.failed_plugins,
                    "not_supported_plugins": self.not_supported_plugins,
                    "started_at": self.started_at.isoformat() if self.started_at else None,
                    "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                    "duration_ms": self.duration_ms,
                    "tasks": self.tasks
                }
        
        return LegacyMatch(job)
    
    def get_job(self, index: int) -> Optional[JobState]:
        """get job by index (session 14: via context)."""
        jobs = self._context._jobs
        if 0 <= index < len(jobs):
            return jobs[index]
        return None
    
    def get_job_by_id(self, job_id: str) -> Optional[JobState]:
        """get job by id (session 14: via context)."""
        try:
            parts = job_id.split('_')
            index = int(parts[-1])
            jobs = self._context._jobs
            if 0 <= index < len(jobs):
                return jobs[index]
        except (ValueError, IndexError):
            pass
        return None
    
    def get_all_jobs(self) -> List[JobState]:
        """get all jobs (session 14: via context)."""
        return self._context.jobs
    
    def complete_job(self, index: int):
        """Mark job as completed (Session 12)."""
        job = self.get_job(index)
        if not job:
            raise ValueError(f"Job {index} not found")
        
        job.complete(success=job.status.success)
        
        # Update run stats
        self._run.increment_completed()
        if not job.status.success:
            self._run.increment_failed()
        
        # Persist
        if self._persistence:
            if hasattr(self._persistence, 'save_job'):
                self._persistence.save_job(job)
            elif hasattr(self._persistence, 'save_match'):
                self._persistence.save_match(self._job_to_match(job))
        
        self._log("debug", "job", f"Job {index} completed",
                 success=job.status.success, duration_ms=job.status.duration_ms)
        
        event_name = "job.completed" if job.status.success else "job.failed"
        self._emit(event_name, {
            "index": index,
            "success": job.status.success,
            "duration_ms": job.status.duration_ms,
            "executed_plugins": job.status.executed,
            "failed_plugins": job.status.failed
        })
    
    # Legacy aliases
    def register_match(self, index: int, input_path: str):
        """Legacy: Create job."""
        return self.create_job(input_path)
    
    def get_match(self, index: int):
        """Legacy: Get job."""
        return self.get_job(index)
    
    def get_all_matches(self):
        """Legacy: Get all jobs as dict."""
        return {j.index: j for j in self._jobs.values()}
    
    def complete_match(self, index: int):
        """Legacy: Complete job."""
        self.complete_job(index)
    
    # Internal compatibility - expose _matches for code that accesses it directly
    @property
    def _matches(self):
        """Legacy: Direct access to jobs dict."""
        return self._jobs
    
    @_matches.setter
    def _matches(self, value):
        """Legacy: Set jobs dict."""
        self._jobs = value
    
    @property
    def _execution(self):
        """Legacy: Direct access to run."""
        return self._run_to_execution()
    
    # ==================== PLUGIN DATA ====================
    
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
        
        # Also check _plugins_storage
        if job_id in self._plugins_storage:
            return list(self._plugins_storage[job_id].keys())
        
        return []
    
    def get_all_plugin_names(self) -> List[str]:
        """
        Get list of all plugin names that have been used in current run.
        
        Returns:
            List of unique plugin names across all jobs
        """
        plugin_names = set()
        
        # Collect from all jobs
        for job in self._jobs.values():
            if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                plugin_names.update(job.plugins.keys())
        
        # Also check _plugins_storage
        for job_plugins in self._plugins_storage.values():
            plugin_names.update(job_plugins.keys())
        
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
        if job_id not in self._plugins:
            self._plugins[job_id] = {}
        
        if plugin_name in self._plugins[job_id]:
            return self._plugins[job_id][plugin_name]
        
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
        if job_id not in self._plugins:
            self._plugins[job_id] = {}
        
        self._plugins[job_id][plugin_name] = data
        
        # Also update job.plugins for template access
        job = self.get_job_by_id(job_id)
        if job:
            job.plugins[plugin_name] = data
        
        # Persist to plugins collection
        if self._persistence and hasattr(self._persistence, 'save_plugin_data'):
            try:
                # Get job info
                job_index = 0
                run_id = ""
                if job:
                    job_index = job.index
                    run_id = job.run_id
                
                plugin_data = PluginData(
                    job_id=job_id,
                    run_id=run_id,
                    job_index=job_index,
                    plugin_name=plugin_name,
                    stage="",  # Could be passed in
                    data=data
                )
                self._persistence.save_plugin_data(plugin_data)
            except Exception:
                pass
    
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get plugin data for a job."""
        if job_id in self._plugins:
            return self._plugins[job_id].get(plugin_name)
        
        # Try from job.plugins
        job = self.get_job_by_id(job_id)
        if job:
            return job.plugins.get(plugin_name)
        
        return None
    
    def get_all_plugin_data(self, job_id: str) -> Dict[str, Dict[str, Any]]:
        """Get all plugin data for a job."""
        result = {}
        
        if job_id in self._plugins:
            result.update(self._plugins[job_id])
        
        job = self.get_job_by_id(job_id)
        if job:
            result.update(job.plugins)
        
        return result
    
    # Legacy plugin result method
    def update_plugin_result(self, job_index: int, plugin_name: str, result):
        """Legacy: Update plugin result for a job."""
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
        
        # Update status
        success = True
        if hasattr(result, 'success'):
            success = result.success
        
        if success:
            job.add_executed(plugin_name)
        else:
            job.add_failed(plugin_name)
        
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
        job = self.get_job(job_index)
        if job:
            job.add_skipped(plugin_name)
            
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
    
    # ==================== TEMPLATE CONTEXT ====================
    
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
        
        # Job context
        job_context = {
            "index": job.index,
            "id": job.id,
            "input": {
                "value": job.input.value,
                "path": job.input.value,  # Legacy alias
                "data": job.input.data
            },
            "output": {
                "values": job.output.values,
                "data": job.output.data
            },
            "status": {
                "success": job.status.success,
                "executed": job.status.executed,
                "failed": job.status.failed,
                "skipped": job.status.skipped
            },
            "plugins": job.plugins
        }
        
        # Full context
        context = {
            "run": run_context,
            "job": job_context,
            "jobs": [self._job_to_context(j) for j in self._jobs.values()],
            
            # Legacy aliases
            "globals": run_context,
            "match_globals": job_context,
            "match": job_context,
            
            # Config access
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
    
    # ==================== LEGACY COMPATIBILITY ====================
    
    def start_execution(self, config: Dict[str, Any]) -> str:
        """Legacy: Start run."""
        return self.start_run(config)
    
    def complete_execution(self, branch_name: str = "main"):
        """Legacy: Complete run."""
        return self.complete_run(branch_name)
    
    def _create_config_snapshot(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create minimal config snapshot."""
        return {
            "plugins": list(config.keys()),
            "options": config.get("options", {}),
            "aliases": config.get("aliases", {})
        }


# Backward compatibility alias (Session 12: class renamed)
StateManager = GlobalStateManager
