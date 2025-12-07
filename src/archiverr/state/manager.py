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

if TYPE_CHECKING:
    from archiverr.events import EventBus


class GlobalStateManager:
    """
    Session 12 Global State Manager.
    
    Manages 6 global state objects:
    1. run: RunState (read-only for all plugins)
    2. config: Dict (frozen config, read-only for all)
    3. job: JobState (current job, per_job only)
    4. jobs: List[JobState] (all jobs, per_job read-only)
    5. plugin: Dict[str, PluginState] (current job plugins, per_job only)
    6. plugins: List[Dict] (all jobs' plugins, per_job read-only)
    
    Plugin Data Structure:
        plugin.{name}.status: PluginStatus
        plugin.{name}.data: Dict (plugin's own data)
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
        
        # Session 12: 6 global state objects
        self._run: Optional[RunState] = None
        self._config: Dict[str, Any] = {}
        self._current_job: Optional[JobState] = None
        self._jobs: List[JobState] = []
        self._plugins_storage: Dict[str, Dict[str, PluginState]] = {}  # job_id -> plugin_name -> PluginState
    
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
        """Reset state for new run (Session 12)."""
        self._run = None
        self._config = {}
        self._current_job = None
        self._jobs = []
        self._plugins_storage = {}
    
    # ==================== SESSION 12: GLOBAL STATE PROPERTIES ====================
    
    @property
    def run(self) -> Optional[RunState]:
        """Global state 1: run (read-only for all plugins)"""
        return self._run
    
    @property
    def config(self) -> Dict[str, Any]:
        """Global state 2: config (frozen, read-only for all plugins)"""
        return self._config
    
    @property
    def job(self) -> Optional[JobState]:
        """Global state 3: job (current job, per_job plugins only)"""
        return self._current_job
    
    @property
    def jobs(self) -> List[JobState]:
        """Global state 4: jobs (all jobs, per_job read-only)"""
        return self._jobs.copy()  # Return copy to prevent mutation
    
    @property
    def plugin(self) -> Dict[str, PluginState]:
        """Global state 5: plugin (current job's plugins, per_job only)"""
        if not self._current_job:
            return {}
        return self._plugins_storage.get(self._current_job.id, {}).copy()
    
    @property
    def plugins(self) -> List[Dict[str, Any]]:
        """
        Global state 6: plugins (all jobs' plugins, per_job read-only)
        
        Returns:
            List of {job_id, job_index, run_id, plugins: {...}}
        """
        result = []
        for job in self._jobs:
            job_plugins = self._plugins_storage.get(job.id, {})
            result.append({
                "job_id": job.id,
                "job_index": job.index,
                "run_id": job.run_id,
                "plugins": {
                    name: state.to_dict()
                    for name, state in job_plugins.items()
                }
            })
        return result
    
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
            
            # Create commit
            self._create_commit(branch_name)
        
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
    
    def _create_commit(self, branch_name: str = "main"):
        """Create commit for versioning."""
        if not self._persistence or not self._run:
            return
        
        if not hasattr(self._persistence, 'create_branch'):
            return
        
        try:
            branch = self._persistence.get_branch(name=branch_name)
            
            if not branch:
                branch = self._persistence.create_branch(
                    name=branch_name,
                    description=f"Default branch" if branch_name == "main" else f"Branch: {branch_name}",
                    is_default=(branch_name == "main")
                )
                self._log("info", "state", f"Created branch", branch=branch_name)
            else:
                self._log("debug", "state", f"Using existing branch", branch=branch_name)
            
            branch_id = branch.get("_id")
            
            commit = self._persistence.create_commit(
                branch_id=branch_id,
                execution_id=self._run.id,
                message=f"Run {self._run.id}: {self._run.status.total_jobs} jobs",
                metadata={
                    "success": self._run.status.success,
                    "total_jobs": self._run.status.total_jobs,
                    "completed": self._run.status.completed,
                    "failed": self._run.status.failed,
                    "duration_ms": self._run.status.duration_ms
                }
            )
            
            self._log("info", "state", f"Created commit", 
                     commit=commit.get("_id", "unknown"), branch=branch_name)
            
        except Exception as e:
            self._log("warn", "state", f"Failed to create commit: {e}")
    
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
    
    def create_job(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
        """
        Create new job (Session 12).
        
        Args:
            input_value: Input path or virtual identifier
            input_data: Additional input metadata
            
        Returns:
            Job ID (string)
        """
        if not self._run:
            raise RuntimeError("No active run")
        
        index = len(self._jobs)
        
        job = JobState(
            index=index,
            run_id=self._run.id,
            input=InputData(
                value=input_value,
                data=input_data or {}
            )
        )
        job.start()
        
        # Session 12: Use list instead of dict
        self._jobs.append(job)
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
        Set current job context (Session 12).
        
        Used by Orchestrator to set current job before executing per_job plugins.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        self._current_job = job
    
    def clear_current_job(self) -> None:
        """Clear current job context (Session 12)."""
        self._current_job = None
    
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
        """Get job by index (Session 12: _jobs is a list)."""
        if 0 <= index < len(self._jobs):
            return self._jobs[index]
        return None
    
    def get_job_by_id(self, job_id: str) -> Optional[JobState]:
        """Get job by ID (Session 12)."""
        try:
            parts = job_id.split('_')
            index = int(parts[-1])
            if 0 <= index < len(self._jobs):
                return self._jobs[index]
        except (ValueError, IndexError):
            pass
        return None
    
    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs (Session 12: _jobs is already a list)."""
        return self._jobs.copy()  # Return copy to prevent mutation
    
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
