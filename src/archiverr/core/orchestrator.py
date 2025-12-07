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

from .plugins.registry import PluginRegistry, Stage
from .plugins.stage_executor import StageExecutor
from .exceptions import CriticalError, StageError, PluginError
from .validation import validate_at_startup, ValidationResult


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
            
            # Phase 2: Execute stages
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
            self._log("error", f"Unexpected error: {e}")
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
        
        # Run startup validation
        manifests = self._plugin_registry.get_all_manifests()
        enabled_plugins = self._plugin_registry.enabled_plugins
        
        validation_result = validate_at_startup(
            config=self._config,
            manifests=manifests,
            enabled_plugins=enabled_plugins
        )
        
        # Log warnings
        for warning in validation_result.warnings:
            self._log("warn", str(warning))
        
        # Check for errors
        if not validation_result.valid:
            for error in validation_result.errors:
                self._log("error", str(error))
            
            if validation_result.has_fatal():
                raise CriticalError(
                    "Startup validation failed with fatal errors",
                    {"error_count": validation_result.error_count()}
                )
            else:
                # Non-fatal errors: log and continue (best effort)
                self._log("warn", f"Startup validation found {validation_result.error_count()} errors, continuing...")
        
        # Legacy dependency validation (will be removed after full migration)
        dep_errors = self._plugin_registry.validate_dependencies()
        if dep_errors:
            self._log("warn", f"Dependency warnings: {len(dep_errors)}")
            for err in dep_errors:
                self._log("warn", err)
        
        # Start run in state
        self._run_id = self._state.start_execution(self._config)
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
        
        # Session 12: Provides registry removed
        # No need to register provides or track reactive plugins
        
        # Register event handlers for persistence
        self._register_event_handlers()
    
    def _execute_stages(self) -> None:
        """
        Execute all 4 stages in order.
        
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
        - Emits run.completed event
        """
        self._log("info", f"Finalizing run (success={success})")
        
        # Complete run in state
        self._state.complete_execution()
        
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
        
        # Get stats from state manager
        # Using legacy methods for now
        execution = self._state._execution
        
        total_jobs = 0
        completed = 0
        failed = 0
        
        if execution:
            total_jobs = execution.total_matches
            completed = execution.completed_matches
            failed = execution.failed_matches
        
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
    from archiverr.utils.debug import init_debugger
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
    
    # Create persistence if not provided
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
