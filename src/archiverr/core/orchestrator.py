"""
Orchestrator - Main execution coordinator

Session 12: Central coordinator for plugin execution.

Responsibilities:
- Run lifecycle management (start → execute → finalize)
- 3-stage execution (parse → data → output)
- Per-run plugin execution (outside stages)
- Error handling and recovery
- Event emission for observability
- Persistence coordination

Note: INPUT stage removed. Input plugins run as per_run mode.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List

from archiverr.state.models import RunState, JobState, StateEnum
from archiverr.state.manager import GlobalStateManager
from archiverr.events import EventBus
from archiverr.utils.debug import Debugger, get_debugger
from archiverr.core.plugins.registry import PluginRegistry, Stage
from archiverr.core.plugins.stage_executor import StageExecutor
from archiverr.core.exceptions import CriticalError, StageError
from archiverr.core.locking import FSLockManager


@dataclass
class RunResult:
    """
    Orchestrator run result summary.
    
    Returned by Orchestrator.run() with execution statistics.
    """
    run_id: str
    success: bool
    total_jobs: int
    completed: int
    failed: int
    skipped: int
    duration_ms: int
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/logging"""
        return {
            "run_id": self.run_id,
            "success": self.success,
            "total_jobs": self.total_jobs,
            "completed": self.completed,
            "failed": self.failed,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
            "stages_completed": self.stages_completed,
            "stages_failed": self.stages_failed,
            "error": self.error
        }


class Orchestrator:
    """
    Main execution coordinator.
    
    Replaces the monolithic cli_main() function with a structured,
    testable, and maintainable orchestration layer.
    
    Usage:
        # Using factory (recommended)
        orchestrator = build_orchestrator(config)
        result = orchestrator.run()
        
        # Manual construction (for testing)
        orchestrator = Orchestrator(
            event_bus=event_bus,
            state=state,
            persistence=persistence,
            plugin_registry=registry,
            config=config
        )
        result = orchestrator.run()
    
    Lifecycle:
        1. run() is called
        2. _initialize() sets up run state and discovers plugins
        3. _execute_stages() runs each stage in order
        4. _finalize() completes run and persists state
        5. RunResult is returned
    """
    
    # Stage execution order (Session 12: 3 stages only)
    STAGES = [Stage.PARSE, Stage.DATA, Stage.OUTPUT]
    
    def __init__(
        self,
        event_bus: EventBus,
        state: GlobalStateManager,
        persistence: Any,  # PersistenceInterface
        plugin_registry: PluginRegistry,
        config: Dict[str, Any],
        debugger: Optional[Debugger] = None
    ):
        """
        Initialize orchestrator with all dependencies.
        
        Args:
            event_bus: Event bus for loose coupling
            state: State manager for run/job state
            persistence: Persistence layer for MongoDB/Mock
            plugin_registry: Registry for plugin discovery and loading
            config: Full application configuration
            debugger: Optional debugger for logging
        """
        self._event_bus = event_bus
        self._state = state
        self._persistence = persistence
        self._plugin_registry = plugin_registry
        self._config = config
        self._debugger = debugger or get_debugger()
        
        # Session 12: FS Lock Manager
        self._fs_lock_manager = FSLockManager()
        
        # Runtime state (set during run)
        self._run_id: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._stages_completed: List[str] = []
        self._stages_failed: List[str] = []
        self._stage_executor: Optional[StageExecutor] = None
    
    def run(self) -> RunResult:
        """
        Execute full run lifecycle.
        
        This is the main entry point. It:
        1. Initializes run state
        2. Executes all stages in order
        3. Finalizes and persists state
        4. Returns summary result
        
        Returns:
            RunResult with execution summary
        """
        self._start_time = datetime.now()
        self._stages_completed = []
        self._stages_failed = []
        
        try:
            # Phase 1: Initialize
            self._initialize()
            
            # Phase 1.5: Execute per_run plugins (Session 12: before stages)
            self._execute_per_run_plugins()
            
            # Phase 2: Execute stages (per_job plugins)
            self._execute_stages()
            
            # Phase 3: Finalize
            self._finalize(success=True)
            
            return self._build_result(success=True)
            
        except CriticalError as e:
            self._log("error", f"Critical error: {e}")
            self._emit_error(e, critical=True)
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))
            
        except Exception as e:
            import traceback
            error_detail = f"{e}\n{traceback.format_exc()}"
            self._log("error", f"Unexpected error: {error_detail}")
            self._emit_error(e, critical=False)
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))
    
    def _initialize(self) -> None:
        """
        Initialize run state and discover plugins.
        
        - Discovers and loads plugins
        - Validates at least one plugin loaded
        - Runs startup validation (config, manifests, dependencies)
        - Starts run in state manager
        - Emits run.started event
        - Registers event handlers
        """
        self._log("info", "Initializing orchestrator run")
        
        # Discover and load plugins
        self._plugin_registry.discover_and_load()
        
        loaded_count = self._plugin_registry.total_loaded
        discovered_count = self._plugin_registry.total_discovered
        
        self._log("debug", f"Plugins: {loaded_count} loaded / {discovered_count} discovered")
        
        if loaded_count == 0:
            raise CriticalError(
                "No plugins loaded",
                {"discovered": discovered_count, "enabled": 0}
            )
        
        # Session 12: Validate fs_lock paths (static paths only)
        manifests = self._plugin_registry.get_all_manifests()
        is_valid, fs_errors = self._fs_lock_manager.validate_all_manifests(manifests)
        
        if not is_valid:
            for error in fs_errors:
                self._log("error", f"FS Lock validation: {error}")
            raise CriticalError(
                "FS Lock validation failed: paths must be static (no variables)",
                {"errors": fs_errors}
            )
        
        # Check for fs_lock conflicts
        conflicts = self._fs_lock_manager.detect_conflicts(manifests)
        if conflicts:
            for conflict in conflicts:
                self._log("warn", f"FS Lock conflict: {conflict}")
        
        # Legacy dependency validation (will be removed after full migration)
        dep_errors = self._plugin_registry.validate_dependencies()
        if dep_errors:
            self._log("warn", f"Dependency warnings: {len(dep_errors)}")
            for err in dep_errors:
                self._log("warn", err)
        
        # Start run in state
        self._run_id = self._state.start_run(self._config)
        self._log("debug", f"Run started: {self._run_id}")
        
        # Create stage executor
        self._stage_executor = StageExecutor(
            state=self._state,
            plugin_registry=self._plugin_registry,
            event_bus=self._event_bus,
            config=self._config,
            debugger=self._debugger
        )
        
        # Emit run.started event
        self._event_bus.emit("run.started", {
            "run_id": self._run_id,
            "config": self._summarize_config(),
            "plugins": self._plugin_registry.enabled_plugins
        })
        
        # Register event handlers for persistence
        self._register_event_handlers()
    
    def _execute_per_run_plugins(self) -> None:
        """
        Execute per_run plugins (Session 12).
        
        Per_run plugins execute once per run, before stages.
        They typically create jobs (e.g., input/discovery plugins).
        """
        # Get all loaded plugins and filter for run_mode: per_run
        all_plugins = self._plugin_registry.get_all_plugins()
        per_run_plugins = []
        
        for plugin_name, plugin_instance in all_plugins.items():
            manifest = self._plugin_registry.get_manifest(plugin_name)
            self._log("debug", f"Checking {plugin_name}: run_mode={manifest.get('run_mode') if manifest else 'NO_MANIFEST'}, stage={manifest.get('stage') if manifest else 'NO_STAGE'}")
            if manifest and manifest.get('run_mode') == 'per_run':
                per_run_plugins.append((plugin_name, plugin_instance))
        
        if not per_run_plugins:
            self._log("debug", "No per_run plugins to execute")
            return
        
        self._log("info", f"Executing {len(per_run_plugins)} per_run plugins")
        
        for plugin_name, plugin_instance in per_run_plugins:
            try:
                self._log("debug", f"Executing per_run plugin: {plugin_name}")
                
                # Create PluginServices for per_run plugin
                from archiverr.core.services.plugin_services import PluginServices
                services = PluginServices(
                    state=self._state,
                    event_bus=self._event_bus,
                    logger=self._debugger,
                    config=self._config,
                    mode="per_run"
                )
                
                # Execute plugin (input plugins create jobs via services.createJob)
                if hasattr(plugin_instance, 'execute_run'):
                    result = plugin_instance.execute_run(services)
                    self._log("info", f"{plugin_name} completed: {result.get('data', {}).get('count', 0)} jobs created")
                elif hasattr(plugin_instance, 'get_matches'):
                    # Legacy: some input plugins use get_matches
                    matches = plugin_instance.get_matches()
                    self._log("debug", f"{plugin_name} returned {len(matches)} matches")
                    
                    # Create jobs from matches
                    for match in matches:
                        job_id = self._state.create_job(
                            input_value=match.get('path', match.get('value', '')),
                            input_data=match
                        )
                        self._log("info", f"Created job: {job_id} from {plugin_name}")
                
                self._log("info", f"Per_run plugin {plugin_name} completed")
                
            except Exception as e:
                self._log("error", f"Per_run plugin {plugin_name} failed: {e}")
                # Continue with next plugin (best effort)
    
    def _execute_stages(self) -> None:
        """
        Execute all 3 stages in order.
        
        Stage execution is best-effort: if a stage fails,
        we log the error and continue to the next stage.
        This allows partial results to be saved.
        """
        for stage in self.STAGES:
            stage_name = stage.value
            self._log("info", f"Executing stage: {stage_name}")
            
            self._event_bus.emit("stage.started", {
                "run_id": self._run_id,
                "stage": stage_name
            })
            
            try:
                self._execute_single_stage(stage)
                
                self._stages_completed.append(stage_name)
                self._event_bus.emit("stage.completed", {
                    "run_id": self._run_id,
                    "stage": stage_name
                })
                self._log("debug", f"Stage completed: {stage_name}")
                
            except StageError as e:
                # Stage failed but continue (best effort)
                self._stages_failed.append(stage_name)
                self._event_bus.emit("stage.failed", {
                    "run_id": self._run_id,
                    "stage": stage_name,
                    "error": str(e)
                })
                self._log("warn", f"Stage failed: {stage_name} - {e}")
                # Continue to next stage
                
            except Exception as e:
                # Unexpected error in stage
                self._stages_failed.append(stage_name)
                self._event_bus.emit("stage.failed", {
                    "run_id": self._run_id,
                    "stage": stage_name,
                    "error": str(e)
                })
                self._log("error", f"Unexpected error in stage {stage_name}: {e}")
                # Continue to next stage
    
    def _execute_single_stage(self, stage: Stage) -> None:
        """
        Execute a single stage using StageExecutor.
        
        Args:
            stage: Stage to execute
        """
        if self._stage_executor is None:
            raise CriticalError("StageExecutor not initialized")
        
        self._stage_executor.execute_stage(stage)
    
    def _finalize(self, success: bool) -> None:
        """
        Finalize run and persist state.
        
        - Completes run in state manager
        - Persists final state to database
        - Saves JSON output (Session 12)
        - Emits run.completed event
        """
        self._log("info", f"Finalizing run (success={success})")
        
        # Session 12: Save JSON output via tasker plugin
        try:
            tasker_plugin = self._plugin_registry.get_plugin('tasker')
            if tasker_plugin and hasattr(tasker_plugin, 'save_run_output'):
                output_path = tasker_plugin.save_run_output(self._run_id)
                if output_path:
                    self._log("debug", f"Run output saved: {output_path}")
        except Exception as e:
            self._log("warn", f"Failed to save run output: {e}")
        
        # Session 16: Global state dump
        self._dump_global_state()
        
        # Complete run in state
        self._state.complete_run()
        
        # Build final statistics
        # Note: Using legacy state manager methods for now
        # Will use RunState directly after full migration
        
        # Emit run.completed event
        self._event_bus.emit("run.completed", {
            "run_id": self._run_id,
            "success": success,
            "stages_completed": self._stages_completed,
            "stages_failed": self._stages_failed
        })
    
    def _register_event_handlers(self) -> None:
        """Register event handlers for persistence and logging."""
        
        def on_job_completed(event):
            """Persist job on completion"""
            data = event.data if hasattr(event, 'data') else event
            job_id = data.get("job_id")
            if job_id and self._persistence:
                # Persist job state
                pass
        
        def on_plugin_completed(event):
            """Persist plugin data on completion"""
            # Handle both Event object and dict
            data = event.data if hasattr(event, 'data') else event
            
            if self._persistence:
                job_id = data.get("job_id")
                plugin_name = data.get("plugin_name")
                if job_id and plugin_name:
                    self._persistence.save_plugin({
                        "job_id": job_id,
                        "run_id": self._run_id,
                        "plugin_name": plugin_name,
                        "stage": data.get("stage"),
                        "data": data.get("data", {}),
                        "status": data.get("status", {})
                    })
        
        self._event_bus.subscribe("job.completed", on_job_completed)
        self._event_bus.subscribe("plugin.completed", on_plugin_completed)
    
    def _build_result(self, success: bool, error: str = None) -> RunResult:
        """Build RunResult from current state."""
        duration_ms = 0
        if self._start_time:
            delta = datetime.now() - self._start_time
            duration_ms = int(delta.total_seconds() * 1000)
        
        run = self._state.run
        total_jobs = run.status.total_jobs if run else 0
        completed = run.status.completed if run else 0
        failed = run.status.failed if run else 0
        
        return RunResult(
            run_id=self._run_id or "",
            success=success and failed == 0,
            total_jobs=total_jobs,
            completed=completed,
            failed=failed,
            skipped=0,  # Will be calculated properly
            duration_ms=duration_ms,
            stages_completed=self._stages_completed,
            stages_failed=self._stages_failed,
            error=error
        )
    
    def _summarize_config(self) -> Dict[str, Any]:
        """Create a safe config summary for events (no secrets)."""
        return {
            "options": self._config.get("options", {}),
            "enabled_plugins": self._plugin_registry.enabled_plugins
        }
    
    def _emit_error(self, error: Exception, critical: bool) -> None:
        """Emit error event."""
        self._event_bus.emit("run.error", {
            "run_id": self._run_id,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "critical": critical
        })
    
    def _log(self, level: str, message: str, **kwargs) -> None:
        """Log with debugger."""
        log_func = getattr(self._debugger, level, self._debugger.info)
        log_func("orchestrator", message, **kwargs)
    
    def _dump_global_state(self) -> None:
        """
        Session 16: Dump complete global state to output folder.
        
        Creates output/run_{run_id}_state.json with:
        - run: RunState
        - jobs: All JobState objects
        - plugins: All plugin data by target_id
        """
        import json
        from pathlib import Path
        from datetime import datetime
        
        try:
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            run = self._state.run
            if not run:
                return
            
            run_dict = run.to_dict() if hasattr(run, 'to_dict') else {}
            
            # Session 17: Jobs as key-based dict (like plugins)
            jobs_dict = {}
            for job in self._state.get_all_jobs():
                job_dict = job.to_dict() if hasattr(job, 'to_dict') else {
                    "id": job.id,
                    "index": job.index,
                    "input": {"value": job.input.value, "data": job.input.data} if hasattr(job, 'input') else {},
                    "output": {"values": job.output.values, "data": job.output.data} if hasattr(job, 'output') else {},
                    "status": job.status.to_dict() if hasattr(job.status, 'to_dict') else {},
                    "plugins": job.plugins if hasattr(job, 'plugins') else {}
                }
                jobs_dict[job.id] = job_dict
            
            plugins_data = {}
            if hasattr(self._state, '_plugins_storage'):
                for target_id, plugins in self._state._plugins_storage.items():
                    plugins_data[target_id] = {}
                    for plugin_name, plugin_state in plugins.items():
                        if hasattr(plugin_state, 'to_dict'):
                            plugins_data[target_id][plugin_name] = plugin_state.to_dict()
                        elif hasattr(plugin_state, 'data'):
                            plugins_data[target_id][plugin_name] = plugin_state.data
                        else:
                            plugins_data[target_id][plugin_name] = plugin_state
            
            state_dump = {
                "dump_type": "global_state",
                "timestamp": datetime.now().isoformat(),
                "run": run_dict,
                "jobs": jobs_dict,
                "plugins": plugins_data
            }
            
            filename = f"run_{self._run_id}_state.json"
            filepath = output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state_dump, f, indent=2, ensure_ascii=False, default=str)
            
            self._log("info", f"Global state dumped: {filepath}")
            print(f"\n[STATE DUMP] {filepath}")
            
        except Exception as e:
            self._log("warn", f"Failed to dump global state: {e}")


def build_orchestrator(
    config: Dict[str, Any],
    debugger: Optional[Debugger] = None,
    persistence: Any = None,
    event_bus: Optional[EventBus] = None
) -> Orchestrator:
    """
    Factory function to build Orchestrator with all dependencies.
    
    This is the recommended way to create an Orchestrator.
    It handles all dependency wiring automatically.
    
    Args:
        config: Application configuration dict
        debugger: Optional debugger (created if not provided)
        persistence: Optional persistence layer (from env if not provided)
        event_bus: Optional event bus (created if not provided)
        
    Returns:
        Configured Orchestrator instance
        
    Usage:
        config = load_config_with_tracking("config.yml")
        orchestrator = build_orchestrator(config)
        result = orchestrator.run()
    """
    from archiverr.utils.debug import init_debugger, get_debugger
    from archiverr.state import GlobalStateManager
    from archiverr.infrastructure.database import DatabaseConnection
    
    # Create debugger if not provided
    if debugger is None:
        debug_enabled = config.get('options', {}).get('debug', False)
        debugger = init_debugger(enabled=debug_enabled)
    
    # Create event bus if not provided
    if event_bus is None:
        event_bus = EventBus(debugger=debugger)
    
    # Create state manager
    state = GlobalStateManager()
    state.reset()
    
    # Create persistence if not provided (REQUIRED - no fallback)
    if persistence is None:
        db_connection = DatabaseConnection.from_env()
        persistence = db_connection.connect()
    
    # Configure state with persistence
    state.configure(
        persistence=persistence,
        debugger=debugger,
        event_bus=event_bus
    )
    
    # Create plugin registry
    plugin_registry = PluginRegistry(config, debugger=debugger)
    
    return Orchestrator(
        event_bus=event_bus,
        state=state,
        persistence=persistence,
        plugin_registry=plugin_registry,
        config=config,
        debugger=debugger
    )
