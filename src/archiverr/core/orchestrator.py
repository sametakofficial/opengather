"""Orchestrator - Main execution coordinator for plugin execution.

Refactored for Single Responsibility Principle:
- Orchestrator: Main coordination and lifecycle
- StateDumper: JSON state persistence  
- PerRunPluginExecutor: per_run plugin execution
- ResultBuilder: RunResult construction
- StageExecutor: Stage/job plugin execution (existing)
"""

from datetime import datetime
from typing import Any

from archiverr.core.exceptions import CriticalError, PluginError, StageError
from archiverr.core.locking import FSLockManager
from archiverr.core.per_run_executor import PerRunPluginExecutor
from archiverr.core.plugins.registry import PluginRegistry, Stage
from archiverr.core.plugins.stage_executor import StageExecutor
from archiverr.core.provides_registry import ProvidesRegistry
from archiverr.core.result_builder import ResultBuilder, RunResult
from archiverr.core.state_dumper import StateDumper
from archiverr.events import EventBus, Events
from archiverr.state.manager import GlobalStateManager
from archiverr.utils.debug import Debugger, get_debugger


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

    STAGES = [Stage.PARSE, Stage.DATA, Stage.OUTPUT]

    def __init__(
        self,
        event_bus: EventBus,
        state: GlobalStateManager,
        persistence: Any,  # PersistenceInterface
        plugin_registry: PluginRegistry,
        config: dict[str, Any],
        debugger: Debugger | None = None
    ):
        """
        Initialize orchestrator with all dependencies.
        
        Args:
            event_bus: Event bus for loose coupling
            state: State manager for run/job state
            persistence: Persistence layer for MongoDB
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

        self._fs_lock_manager = FSLockManager()

        # Delegate components (SRP)
        self._state_dumper = StateDumper(debugger=debugger)
        self._result_builder = ResultBuilder()
        self._per_run_executor: PerRunPluginExecutor | None = None
        self._stage_executor: StageExecutor | None = None
        self._provides_registry: ProvidesRegistry | None = None
        # ``full`` / ``degraded`` / ``off`` — populated by build_orchestrator.
        # Direct construction defaults to ``degraded``.
        self._persistence_mode: str = "degraded"

        # Runtime state
        self._run_id: str | None = None
        self._start_time: datetime | None = None
        self._stages_completed: list[str] = []
        self._stages_failed: list[str] = []

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

        except PluginError as e:
            self._log("error", f"Plugin error: {e}")
            self._emit_error(e, critical=False)
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))

        except (OSError, IOError) as e:
            self._log("error", f"I/O error: {e}")
            self._emit_error(e, critical=True)
            self._finalize(success=False)
            return self._build_result(success=False, error=f"I/O error: {e}")

        except Exception as e:
            self._log("error", f"Unexpected error: {type(e).__name__}: {e}")
            self._emit_error(e, critical=False)
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))

    def _execute_per_run_plugins(self) -> None:
        """Execute per_run plugins using PerRunPluginExecutor."""
        if self._per_run_executor is None:
            self._per_run_executor = PerRunPluginExecutor(
                state=self._state,
                plugin_registry=self._plugin_registry,
                event_bus=self._event_bus,
                config=self._config,
                debugger=self._debugger,
                provides_registry=self._provides_registry,
            )
        self._per_run_executor.execute()

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

        manifests = self._plugin_registry.get_all_manifests()

        # Startup validation: config, manifests, dependencies, provides conflicts
        from archiverr.core.validation.startup_validator import validate_at_startup
        validation_result = validate_at_startup(
            config=self._config,
            manifests=manifests,
            enabled_plugins=self._plugin_registry.enabled_plugins
        )

        # Log warnings
        for warning in validation_result.warnings:
            self._log("warn", f"Startup validation: {warning}")

        # Fatal errors stop execution
        if validation_result.has_fatal():
            error_msgs = validation_result.format_errors()
            for msg in error_msgs:
                self._log("error", f"Startup validation: {msg}")
            raise CriticalError(
                "Startup validation failed with fatal errors",
                {"errors": error_msgs}
            )

        # Non-fatal errors are logged as warnings (plugin-level issues)
        if not validation_result.valid:
            for error in validation_result.errors:
                self._log("warn", f"Startup validation: {error}")

        # FS Lock validation (static path enforcement)
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

        # Start run in state
        self._run_id = self._state.start_run(self._config)
        self._log("debug", f"Run started: {self._run_id}")

        # Startup recovery scan — only in mode=full.
        # Marks any non-terminal plugin_executions from previous runs as
        # ``crashed`` so operators can see what died mid-plugin.
        if self._persistence_mode == "full":
            self._recover_crashed()

        # Shared per-run ProvidesRegistry (per_run_executor + stage_executor use the same)
        self._provides_registry = ProvidesRegistry()

        # Create stage executor with shared per-run ProvidesRegistry
        self._stage_executor = StageExecutor(
            state=self._state,
            plugin_registry=self._plugin_registry,
            event_bus=self._event_bus,
            config=self._config,
            debugger=self._debugger,
            provides_registry=self._provides_registry
        )

        # Emit run.started event
        self._event_bus.emit(Events.RUN_STARTED, {
            "run_id": self._run_id,
            "config": self._summarize_config(),
            "plugins": self._plugin_registry.enabled_plugins
        })

        # Register event handlers for persistence
        self._register_event_handlers()

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

            self._event_bus.emit(Events.STAGE_STARTED, {
                "run_id": self._run_id,
                "stage": stage_name
            })

            try:
                self._execute_single_stage(stage)

                self._stages_completed.append(stage_name)
                self._event_bus.emit(Events.STAGE_COMPLETED, {
                    "run_id": self._run_id,
                    "stage": stage_name
                })
                self._log("debug", f"Stage completed: {stage_name}")

            except StageError as e:
                # Stage failed but continue (best effort)
                self._stages_failed.append(stage_name)
                self._event_bus.emit(Events.STAGE_FAILED, {
                    "run_id": self._run_id,
                    "stage": stage_name,
                    "error": str(e)
                })
                self._log("warn", f"Stage failed: {stage_name} - {e}")
                # Continue to next stage

            except Exception as e:
                # Unexpected error in stage
                self._stages_failed.append(stage_name)
                self._event_bus.emit(Events.STAGE_FAILED, {
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
        - Saves JSON output
        - Emits run.completed event
        """
        self._log("info", f"Finalizing run (success={success})")

        self._dump_global_state()

        # Complete all jobs that haven't been completed yet
        from archiverr.state.models import StateEnum
        for job in self._state.get_all_jobs():
            if job.status.state in (StateEnum.PENDING, StateEnum.RUNNING):
                try:
                    self._state.complete_job(job.index)
                except Exception as e:
                    self._log("warn", f"Failed to complete job {job.index}: {e}")

        # Complete run in state (uses job counts for SUCCESS/PARTIAL/FAILED)
        self._state.complete_run()

        # Build final statistics
        # Note: Using legacy state manager methods for now
        # Will use RunState directly after full migration

        # Emit run.completed event
        self._event_bus.emit(Events.RUN_COMPLETED, {
            "run_id": self._run_id,
            "success": success,
            "stages_completed": self._stages_completed,
            "stages_failed": self._stages_failed
        })

    def _register_event_handlers(self) -> None:
        """Register event handlers for persistence and logging."""

        def on_job_completed(event):
            """Persist job state on completion."""
            data = event.data if hasattr(event, 'data') else event
            job_id = data.get("job_id")
            if job_id and self._persistence:
                job = self._state.get_job_by_id(job_id) if hasattr(self._state, 'get_job_by_id') else None
                if job:
                    self._persistence.save_job({
                        "job_id": job_id,
                        "run_id": self._run_id,
                        "stage": data.get("stage"),
                        "status": job.status.to_dict() if hasattr(job.status, 'to_dict') else {},
                    })

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
        """Build RunResult using ResultBuilder delegate."""
        return self._result_builder.build(
            run_id=self._run_id,
            state=self._state,
            start_time=self._start_time,
            success=success,
            stages_completed=self._stages_completed,
            stages_failed=self._stages_failed,
            error=error
        )

    def _summarize_config(self) -> dict[str, Any]:
        """Create a safe config summary for events (no secrets)."""
        return {
            "options": self._config.get("options", {}),
            "enabled_plugins": self._plugin_registry.enabled_plugins
        }

    def _emit_error(self, error: Exception, critical: bool) -> None:
        """Emit error event."""
        self._event_bus.emit(Events.RUN_ERROR, {
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
        """Dump state using StateDumper delegate."""
        filepath = self._state_dumper.dump(self._run_id, self._state)
        if filepath:
            self._log("info", f"Global state dumped: {filepath}")

    def _recover_crashed(self) -> None:
        """Startup scan: mark non-terminal plugin_executions as ``crashed``.

        Only invoked in ``persistence_mode=full`` — the slim recovery
        contract (no lease, no heartbeat, no claim). Anything still
        ``started`` / ``running`` from a previous process is considered a
        crash and transitioned so operators have a durable signal.
        """
        if self._persistence is None:
            return
        try:
            orphans = self._persistence.get_unfinished_plugin_executions()
        except Exception as e:  # noqa: BLE001
            self._log("warn", f"Crashed scan: unable to query executions: {e}")
            return

        if not orphans:
            return

        from datetime import datetime

        now = datetime.utcnow()
        for doc in orphans:
            self._persistence.save_plugin_execution(
                run_id=doc.get("run_id", ""),
                job_id=doc.get("job_id", ""),
                plugin_name=doc.get("plugin_name", ""),
                state="crashed",
                attempt=int(doc.get("attempt", 1)),
                error="detected by startup recovery scan",
                timestamp=now,
            )
        self._log(
            "warn",
            f"Crashed scan: {len(orphans)} plugin execution(s) marked crashed",
        )


VALID_PERSISTENCE_MODES = {"full", "degraded", "off"}


def _resolve_persistence_mode(config: dict[str, Any]) -> str:
    """Resolve options.persistence_mode, defaulting to ``degraded``.

    Raises:
        CriticalError: if the configured mode is not in
            ``{full, degraded, off}``.
    """
    raw = (config.get("options") or {}).get("persistence_mode", "degraded")
    mode = str(raw).lower()
    if mode not in VALID_PERSISTENCE_MODES:
        raise CriticalError(
            f"Invalid persistence_mode '{raw}'. "
            f"Expected one of: {sorted(VALID_PERSISTENCE_MODES)}",
            {"mode": raw},
        )
    return mode


def build_orchestrator(
    config: dict[str, Any],
    debugger: Debugger | None = None,
    persistence: Any = None,
    event_bus: EventBus | None = None,
) -> Orchestrator:
    """
    Factory function to build Orchestrator with all dependencies.

    This is the recommended way to create an Orchestrator.
    It handles all dependency wiring automatically.

    Persistence mode contract (``options.persistence_mode``):
        - ``off``: NullPersistence, recovery disabled, no warning.
        - ``degraded`` (default): try Mongo; on failure fall back to
          NullPersistence with an explicit warning. Recovery disabled.
        - ``full``: Mongo REQUIRED; on failure raise ``CriticalError``.
          Startup recovery scan runs.

    Args:
        config: Application configuration dict
        debugger: Optional debugger (created if not provided)
        persistence: Optional persistence layer (forces mode=full if
            explicit)
        event_bus: Optional event bus (created if not provided)

    Returns:
        Configured Orchestrator instance
    """
    from archiverr.infrastructure.database import DatabaseConnection
    from archiverr.infrastructure.database.null_persistence import NullPersistence
    from archiverr.state import GlobalStateManager
    from archiverr.utils.debug import init_debugger

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

    mode = _resolve_persistence_mode(config)

    # Resolve persistence per mode contract.
    if persistence is None:
        if mode == "off":
            persistence = NullPersistence()
        elif mode == "full":
            # Required — any failure is fatal.
            try:
                persistence = DatabaseConnection.from_env().connect()
            except Exception as e:  # noqa: BLE001 — surface the cause
                raise CriticalError(
                    "persistence_mode=full requires a working Mongo connection",
                    {"error": str(e), "type": type(e).__name__},
                ) from e
            if persistence is None:
                raise CriticalError(
                    "persistence_mode=full: MongoDB connection returned no "
                    "persistence backend",
                    {},
                )
        else:  # degraded
            try:
                persistence = DatabaseConnection.from_env().connect()
            except Exception as e:  # noqa: BLE001
                persistence = None
                if debugger:
                    debugger.warn(
                        "orchestrator",
                        "persistence_mode=degraded: MongoDB unavailable, "
                        "continuing with NullPersistence (recovery disabled)",
                        error=str(e),
                    )
            if persistence is None:
                persistence = NullPersistence()
                if debugger:
                    debugger.warn(
                        "orchestrator",
                        "persistence_mode=degraded: using NullPersistence "
                        "(no data will be persisted, recovery disabled)",
                    )

    # Configure state with persistence
    state.configure(
        persistence=persistence,
        debugger=debugger,
        event_bus=event_bus,
    )

    # Create plugin registry
    plugin_registry = PluginRegistry(config, debugger=debugger)

    orch = Orchestrator(
        event_bus=event_bus,
        state=state,
        persistence=persistence,
        plugin_registry=plugin_registry,
        config=config,
        debugger=debugger,
    )
    orch._persistence_mode = mode
    return orch
