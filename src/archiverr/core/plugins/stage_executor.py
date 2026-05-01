"""
Stage Executor - 3-stage plugin execution system.

Executes plugins by stage with lifecycle management,
requires validation, and event emission.

Stages:
- PARSE: per_job mode - parses filenames/metadata
- DATA: per_job mode - fetches external data (TMDB, TVDB)
- OUTPUT: per_job mode - executes tasks, writes files

Note: INPUT stage removed - input plugins run as per_run mode before stages.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from archiverr.core.exceptions import PluginError, StageError
from archiverr.core.provides_registry import ProvidesRegistry
from archiverr.core.services.plugin_services import PluginServices
from archiverr.core.triggers import TriggerRuleManager
from archiverr.events import EventBus, Events
from archiverr.state.models import JobState
from archiverr.utils.debug import Debugger, get_debugger

from .registry import PluginRegistry, Stage
from .resolver import DependencyResolver
from .sdk.result import PluginResult


class ExecutionMode(Enum):
    """Plugin execution mode."""
    PER_RUN = "per_run"   # Execute once per run (outside stages)
    PER_JOB = "per_job"   # Execute for each job (PARSE, DATA, OUTPUT stages)


# Default execution mode by stage (3 stages)
STAGE_MODES: dict[Stage, ExecutionMode] = {
    Stage.PARSE: ExecutionMode.PER_JOB,
    Stage.DATA: ExecutionMode.PER_JOB,
    Stage.OUTPUT: ExecutionMode.PER_JOB,
}


@dataclass
class PluginExecutionResult:
    """Result of a single plugin execution"""
    plugin_name: str
    success: bool
    data: dict[str, Any]
    error: str | None = None
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: str | None = None


class StageExecutor:
    """
    3-stage plugin execution engine.
    
    Orchestrates plugin execution across 3 stages:
    1. PARSE: Parse filenames, extract metadata (per_job)
    2. DATA: Fetch external data like TMDB/TVDB (per_job)
    3. OUTPUT: Execute tasks, write files (per_job)
    
    Note: INPUT stage removed. Input plugins run as per_run outside stages.
    
    Features:
    - Requires validation before plugin execution
    - Event emission for observability
    - Best-effort execution (failures don't stop other plugins)
    - Plugin data caching for requires validation
    
    Usage:
        executor = StageExecutor(
            state=state_manager,
            plugin_registry=registry,
            event_bus=event_bus,
            config=config
        )
        
        # Execute a single stage
        executor.execute_stage(Stage.INPUT)
        
        # Or use from Orchestrator
        for stage in [Stage.INPUT, Stage.PARSE, Stage.DATA, Stage.OUTPUT]:
            executor.execute_stage(stage)
    """

    def __init__(
        self,
        state: Any,  # StateManager
        plugin_registry: PluginRegistry,
        event_bus: EventBus,
        config: dict[str, Any],
        debugger: Debugger | None = None,
        provides_registry: ProvidesRegistry | None = None,
        run_safety: dict[str, bool] | None = None,
    ):
        """
        Initialize stage executor.

        Args:
            state: State manager for job/run state
            plugin_registry: Registry for plugin lookup
            event_bus: Event bus for notifications
            config: Application configuration
            debugger: Optional debugger for logging
            provides_registry: Per-run provides registry (created if not provided)
            run_safety: Resolved run-scope safety flags (dry_run, hardlink, no_delete)
        """
        self._state = state
        self._registry = plugin_registry
        self._event_bus = event_bus
        self._config = config
        self._debugger = debugger or get_debugger()

        # Plugin data cache: {job_id: {plugin_name: data}}
        self._plugin_data_cache: dict[str, dict[str, dict[str, Any]]] = {}

        # Global state cache per job (invalidated after each plugin completes)
        self._global_state_cache: dict[str, dict[str, Any]] = {}

        # Trigger rule manager for dependency resolution. The bus is
        # threaded in so ``requires: events.<name>:fired`` can resolve
        # against the live event history at decide-skip time.
        self._trigger_manager = TriggerRuleManager(event_bus=event_bus)

        # Provides registry -- per-run instance, no shared global state
        self._provides_registry: ProvidesRegistry = provides_registry or ProvidesRegistry()
        self._register_provides_from_manifests()

        # Run-scope safety flags resolved once at run start; threaded into PluginServices
        self._run_safety = run_safety
        # _save_exec_state failure counter (warn-once-per-run discipline)
        self._exec_state_failures = 0
        # Lazy-initialised core RenderEngine (S39 R15 §H2). Threaded into
        # every PluginServices instance so plugins can resolve their own
        # config templates via ``services.get_runtime_config()`` (§H3).
        self._render_engine = None

    def _register_provides_from_manifests(self) -> None:
        """Register all plugin provides from manifests into the ProvidesRegistry."""
        all_manifests = self._registry.get_all_manifests()
        for plugin_name, manifest in all_manifests.items():
            provides = manifest.get('provides', [])
            if provides:
                self._provides_registry.register_from_manifest(plugin_name, provides)
        if all_manifests:
            self._log("debug", f"Registered provides from {len(all_manifests)} plugin manifests")

    def execute_stage(self, stage: Stage) -> None:
        """
        Execute all plugins for a given stage.
        
        Args:
            stage: Stage to execute
            
        Raises:
            StageError: If stage execution fails critically
        """
        self._log("info", f"Executing stage: {stage.value}")

        plugins = self._registry.get_plugins_by_stage(stage)

        if not plugins:
            self._log("debug", f"No plugins for stage: {stage.value}")
            return

        self._log("debug", f"Stage {stage.value}: {len(plugins)} plugins")

        # Resolve execution groups using proper topological sort
        execution_groups = self._resolve_execution_groups(plugins, stage)

        # Determine execution mode
        mode = STAGE_MODES.get(stage, ExecutionMode.PER_JOB)

        try:
            if stage == Stage.OUTPUT:
                # OUTPUT stage flattens groups; all plugins run per_job
                all_plugins = [p for group in execution_groups for p in group]
                self._execute_mixed(stage, all_plugins)
            else:
                self._execute_per_job_grouped(stage, execution_groups)

        except StageError:
            raise  # Re-raise StageError as-is
        except PluginError as e:
            self._log("error", f"Stage {stage.value} plugin error: {e}")
            raise StageError("Stage execution failed due to plugin error", stage=stage.value, context={"error": str(e)})
        except Exception as e:
            import traceback
            self._log("error", f"Stage {stage.value} unexpected error: {e}")
            self._log("error", f"Traceback: {traceback.format_exc()}")
            raise StageError("Stage execution failed", stage=stage.value, context={"error": str(e)})

    def _execute_per_job_grouped(self, stage: Stage, groups: list[list[Any]]) -> None:
        """
        Execute pre-resolved plugin groups for each job.

        Groups come from DependencyResolver -- plugins within a group
        can safely run in parallel (no dependency conflicts).
        Groups execute sequentially in dependency order.
        """
        jobs = self._get_all_jobs()

        if not jobs:
            self._log("warn", f"No jobs to process for stage: {stage.value}")
            return

        total_plugins = sum(len(g) for g in groups)
        self._log("debug", f"Executing {total_plugins} plugins in {len(groups)} groups for {len(jobs)} jobs")

        for job in jobs:
            if job.id not in self._plugin_data_cache:
                self._plugin_data_cache[job.id] = {}

            for group in groups:
                if len(group) > 1:
                    self._execute_plugin_group_parallel(group, job, stage)
                else:
                    self._execute_plugin_for_job(group[0], job, stage)

            self._event_bus.emit(Events.JOB_STAGE_COMPLETED, {
                "job_id": job.id,
                "stage": stage.value
            })

    def _execute_plugin_for_job(
        self,
        plugin: Any,
        job: JobState,
        stage: Stage
    ) -> PluginExecutionResult:
        """
        Execute a single plugin for a job (sequential path).

        Decide -> invoke -> commit, all on the caller thread. For parallel
        execution within a group, _execute_plugin_group_parallel splits these
        so that only _invoke_safely runs in workers and commit is serial.
        """
        plugin_name = self._get_plugin_name(plugin)
        manifest = self._registry.get_manifest(plugin_name)

        skip_decision = self._decide_skip(plugin_name, manifest, job)
        if skip_decision:
            self._apply_skip(job, plugin_name, skip_decision)
            return skip_decision

        exec_result = self._invoke_safely(plugin, job, plugin_name)
        self._commit_invocation(job, stage, exec_result)
        return exec_result

    def _decide_skip(
        self,
        plugin_name: str,
        manifest: dict[str, Any] | None,
        job: JobState
    ) -> PluginExecutionResult | None:
        """
        Decide whether a plugin should be skipped based on requires/trigger_rule.

        Pure read; does NOT mutate shared state. Callers apply the skip separately
        via _apply_skip on the main thread.
        """
        requires = manifest.get('requires', []) if manifest else []
        trigger_rule = manifest.get('trigger_rule', 'all_success') if manifest else 'all_success'

        if not requires:
            return None

        global_state = self._build_global_state(job)
        should_run, reason = self._trigger_manager.should_execute(
            trigger_rule=trigger_rule,
            requirements=requires,
            state=global_state
        )

        if should_run:
            return None

        return PluginExecutionResult(
            plugin_name=plugin_name, success=True, data={},
            skipped=True, skip_reason=f"Trigger rule '{trigger_rule}': {reason}"
        )

    def _apply_skip(
        self,
        job: JobState,
        plugin_name: str,
        skip_result: PluginExecutionResult
    ) -> None:
        """Apply skip side effects. MAIN THREAD ONLY."""
        self._log("debug",
                  f"Skipping {plugin_name} for job {job.id}: {skip_result.skip_reason}")
        self._mark_skipped(job, plugin_name)

    def _invoke_safely(
        self,
        plugin: Any,
        job: JobState,
        plugin_name: str
    ) -> PluginExecutionResult:
        """
        Invoke plugin.execute and build a PluginExecutionResult.

        Does NOT mutate shared executor/job state. Safe to run in worker threads;
        the caller applies all side effects via _commit_invocation.
        """
        start_time = datetime.now()
        self._save_exec_state(job, plugin_name, "started", timestamp=start_time)
        try:
            self._log("debug", f"Executing {plugin_name} for job {job.id}")
            services = self._create_services(plugin_name, job_id=job.id)
            result = self._invoke_plugin(plugin, job, services, plugin_name)
            duration_ms = self._calc_duration(start_time)
            if result is None:
                return PluginExecutionResult(
                    plugin_name=plugin_name, success=False, data={},
                    error="No execute method", duration_ms=duration_ms
                )
            result_data, success = self._extract_plugin_result(result)
            return PluginExecutionResult(
                plugin_name=plugin_name, success=success,
                data=result_data, duration_ms=duration_ms
            )
        except PluginError as e:
            return PluginExecutionResult(
                plugin_name=plugin_name, success=False, data={},
                error=str(e), duration_ms=self._calc_duration(start_time)
            )
        except Exception as e:
            return PluginExecutionResult(
                plugin_name=plugin_name, success=False, data={},
                error=str(e), duration_ms=self._calc_duration(start_time)
            )

    def _commit_invocation(
        self,
        job: JobState,
        stage: Stage,
        exec_result: PluginExecutionResult
    ) -> None:
        """
        Apply all side effects of a plugin invocation. MAIN THREAD ONLY.

        Updates plugin data cache, job state, provides registry and emits events.
        """
        plugin_name = exec_result.plugin_name
        if exec_result.skipped:
            self._save_exec_state(job, plugin_name, "skipped")
            return
        if exec_result.success:
            if exec_result.data:
                self._plugin_data_cache.setdefault(job.id, {})[plugin_name] = exec_result.data
            self._update_job_plugin_state(
                job, plugin_name, exec_result.data, True, exec_result.duration_ms
            )
            self._provides_registry.complete_all(plugin_name)
            self._emit_plugin_completed(
                plugin_name=plugin_name, stage=stage, mode="per_job",
                success=True, data=exec_result.data,
                duration_ms=exec_result.duration_ms, job_id=job.id
            )
            self._save_exec_state(job, plugin_name, "completed")
        else:
            level = "warn" if exec_result.error else "error"
            label = "plugin error" if exec_result.error else "unexpected error"
            if exec_result.error:
                self._log(level, f"Plugin {plugin_name} {label} for job {job.id}: {exec_result.error}")
            self._mark_failed(job, plugin_name)
            self._provides_registry.fail_all(plugin_name)
            self._emit_plugin_failed(
                plugin_name=plugin_name, stage=stage,
                error=exec_result.error or "unknown",
                duration_ms=exec_result.duration_ms, job_id=job.id
            )
            self._save_exec_state(
                job, plugin_name, "failed", error=exec_result.error
            )

    def _save_exec_state(
        self,
        job: JobState,
        plugin_name: str,
        state: str,
        *,
        error: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Write a plugin_execution state transition via persistence.

        No-op for NullPersistence. Persistence failures are warned the
        first time they occur per run (then counted) — execution state is
        auxiliary so the pipeline keeps running, but operators must see
        that recovery bookkeeping is degraded.

        SCOPE NOTE: this is the per_job recovery surface. Per_run input
        plugins do NOT write plugin_executions (they precede job_id).
        See datasets/11-recovery.yml#out_of_scope.per_run_plugin_executions.
        """
        persistence = getattr(self._state, "persistence", None)
        if persistence is None:
            return
        try:
            run = self._state.run
            persistence.save_plugin_execution(
                run_id=run.id if run else "",
                job_id=job.id,
                plugin_name=plugin_name,
                state=state,
                attempt=1,
                error=error,
                timestamp=timestamp,
            )
        except Exception as e:  # noqa: BLE001
            self._exec_state_failures += 1
            if self._exec_state_failures == 1:
                self._log(
                    "warn",
                    "save_plugin_execution failed; recovery bookkeeping degraded "
                    f"({plugin_name}, {state}): {e}. Subsequent failures will be "
                    "counted but not warned.",
                )
            else:
                self._log(
                    "debug",
                    f"save_plugin_execution failure #{self._exec_state_failures} "
                    f"({plugin_name}, {state}): {e}",
                )

    def _invoke_plugin(
        self,
        plugin: Any,
        job: JobState,
        services: PluginServices,
        plugin_name: str
    ) -> Any | None:
        """Invoke modern per_job plugin: execute(job, services) -> PluginResult."""
        if not hasattr(plugin, 'execute'):
            raise PluginError(
                f"Plugin {plugin_name} has no execute() method",
                plugin_name=plugin_name,
            )
        return plugin.execute(job, services)

    def _extract_plugin_result(self, result: Any) -> tuple[dict[str, Any], bool]:
        """Extract (data, success) from a plugin's return value.

        Per the modern contract, per_job plugins return a PluginResult.
        """
        if isinstance(result, PluginResult):
            return result.data or {}, result.success
        raise PluginError(
            f"Plugin returned unsupported type {type(result).__name__}; expected PluginResult"
        )

    def _update_job_plugin_state(
        self,
        job: JobState,
        plugin_name: str,
        result_data: dict[str, Any],
        success: bool,
        duration_ms: int
    ) -> None:
        """
        Update job.plugins (flat data) and job.status.plugins (status tracking).
        """
        # Store flat plugin data
        if plugin_name not in job.plugins or not job.plugins[plugin_name]:
            job.plugins[plugin_name] = result_data if result_data else {}
            self._log("debug", f"Plugin {plugin_name}: stored result data flat",
                      data_keys=list(result_data.keys()) if result_data else [])
        else:
            self._log("debug", f"Plugin {plugin_name}: data exists from update_plugin",
                      data_keys=list(job.plugins[plugin_name].keys()))

        # Store plugin status
        if not isinstance(job.status.plugins, dict):
            job.status.plugins = {}
        job.status.plugins[plugin_name] = {
            'state': 'completed',
            'success': success,
            'duration_ms': duration_ms
        }

        self._mark_executed(job, plugin_name, success)
        # Invalidate global state cache for this job (plugin data changed)
        self._global_state_cache.pop(job.id, None)

    def _execute_mixed(self, stage: Stage, plugins: list[Any]) -> None:
        """Execute OUTPUT stage plugins (all per_job under the modern contract)."""
        per_job_plugins = {self._get_plugin_name(p): p for p in plugins}
        if not per_job_plugins:
            return
        groups = self._resolve_execution_groups(per_job_plugins, stage)
        self._execute_per_job_grouped(stage, groups)

    def _resolve_execution_groups(self, plugins: dict[str, Any], stage: Stage) -> list[list[Any]]:
        """
        Resolve plugin execution groups using proper topological sort.

        Uses DependencyResolver for cycle detection and dependency-ordered grouping.
        Plugins within a group can run in parallel safely.

        Args:
            plugins: Dict of plugin_name -> plugin_instance from registry
            stage: Current execution stage

        Returns:
            List of groups, each group is a list of plugin instances
        """
        if isinstance(plugins, list):
            self._log("error", f"_resolve_execution_groups received list instead of dict for stage {stage.value}")
            return [plugins]

        if not plugins:
            return []

        # Build metadata dict for DependencyResolver: {name: manifest}
        metadata = {}
        for name in plugins:
            manifest = self._registry.get_manifest(name)
            if manifest:
                metadata[name] = manifest
            else:
                metadata[name] = {}

        # Resolve execution order with proper topological sort
        resolver = DependencyResolver(metadata)
        try:
            name_groups = resolver.resolve(list(plugins.keys()))
        except ValueError as e:
            self._log("error", f"Dependency resolution failed for stage {stage.value}: {e}")
            # Fallback: all plugins in a single group
            return [list(plugins.values())]

        # Convert name groups to instance groups
        instance_groups = []
        for name_group in name_groups:
            group = []
            for name in name_group:
                if name in plugins:
                    group.append(plugins[name])
            if group:
                instance_groups.append(group)

        if len(instance_groups) > 1:
            self._log("debug",
                       f"Dependency resolution: {len(plugins)} plugins -> "
                       f"{len(instance_groups)} sequential groups")

        return instance_groups

    def _execute_plugin_group_parallel(
        self,
        plugins: list[Any],
        job: JobState,
        stage: Stage
    ) -> list[PluginExecutionResult]:
        """
        Execute a group of plugins in parallel for a single job.

        Phase 1 (main thread): decide skips, emit skip side effects.
        Phase 2 (workers): _invoke_safely runs plugin.execute, returns a result only.
        Phase 3 (main thread): commit results in deterministic group order.

        This guarantees all mutations of _plugin_data_cache, job.plugins,
        job.status.plugins, _provides_registry and the event bus happen on the
        main thread, eliminating the race the previous design had.
        """
        if len(plugins) == 1:
            return [self._execute_plugin_for_job(plugins[0], job, stage)]

        decisions: dict[str, PluginExecutionResult] = {}
        pending: list[tuple[str, Any]] = []
        for plugin in plugins:
            plugin_name = self._get_plugin_name(plugin)
            manifest = self._registry.get_manifest(plugin_name)
            decision = self._decide_skip(plugin_name, manifest, job)
            if decision:
                self._apply_skip(job, plugin_name, decision)
                decisions[plugin_name] = decision
            else:
                pending.append((plugin_name, plugin))

        invocations: dict[str, PluginExecutionResult] = {}
        if pending:
            with ThreadPoolExecutor(max_workers=min(len(pending), 4)) as executor:
                futures = {
                    executor.submit(self._invoke_safely, plugin, job, name): name
                    for name, plugin in pending
                }
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        invocations[name] = future.result()
                    except Exception as e:
                        self._log("error", f"Parallel execution unexpected error for {name}: {e}")
                        invocations[name] = PluginExecutionResult(
                            plugin_name=name, success=False, data={}, error=str(e)
                        )

        results: list[PluginExecutionResult] = []
        for plugin in plugins:
            plugin_name = self._get_plugin_name(plugin)
            if plugin_name in decisions:
                results.append(decisions[plugin_name])
                continue
            exec_result = invocations[plugin_name]
            self._commit_invocation(job, stage, exec_result)
            results.append(exec_result)

        return results

    def _create_services(self, plugin_name: str, job_id: str = None) -> PluginServices:
        """
        Create PluginServices for a plugin ().

        Args:
            plugin_name: Plugin name
            job_id: Current job ID (for per_job plugins)

        Returns:
            PluginServices instance with context set
        """
        # Determine mode based on job_id
        mode = "per_job" if job_id else "per_run"

        # Create services with context (S39 R15 §H2 — render_engine threaded)
        services = PluginServices(
            state=self._state,
            event_bus=self._event_bus,
            logger=self._debugger,
            config=self._config,
            mode=mode,
            current_job_id=job_id,
            current_plugin_name=plugin_name,
            provides_registry=self._provides_registry,
            run_safety=self._run_safety,
            render_engine=self._get_render_engine(),
        )

        return services

    def _get_render_engine(self):
        """Lazy-init shared ConfigRenderEngine (S39 R15 §H2)."""
        if self._render_engine is None:
            from archiverr.core.render import ConfigRenderEngine
            self._render_engine = ConfigRenderEngine()
        return self._render_engine

    def _get_all_jobs(self) -> list[JobState]:
        """Get all jobs from state"""
        return self._state.get_all_jobs()

    def _get_plugin_name(self, plugin: Any) -> str:
        """Get plugin name from plugin instance."""
        return getattr(plugin, 'name', None) or getattr(plugin, '_name', None) or type(plugin).__name__

    def _ensure_status_plugins(self, job: JobState) -> None:
        """Ensure job.status.plugins is a dict."""
        if not isinstance(job.status.plugins, dict):
            job.status.plugins = {}

    def _mark_executed(self, job: JobState, plugin_name: str, success: bool) -> None:
        """Mark plugin as executed in job.status.plugins."""
        if not success:
            self._mark_failed(job, plugin_name)
            return

        self._ensure_status_plugins(job)
        job.status.plugins[plugin_name] = {'state': 'completed', 'success': True}

    def _mark_failed(self, job: JobState, plugin_name: str) -> None:
        """Mark plugin as failed in job.status.plugins."""
        self._ensure_status_plugins(job)
        job.status.plugins[plugin_name] = {'state': 'failed', 'success': False}
        job.status.success = False

    def _mark_skipped(self, job: JobState, plugin_name: str) -> None:
        """Mark plugin as skipped in job.status.plugins."""
        self._ensure_status_plugins(job)
        job.status.plugins[plugin_name] = {'state': 'skipped', 'success': True}

    def _calc_duration(self, start_time: datetime) -> int:
        """Calculate duration in milliseconds"""
        delta = datetime.now() - start_time
        return int(delta.total_seconds() * 1000)

    def _emit_plugin_completed(
        self,
        plugin_name: str,
        stage: Stage,
        mode: str,
        success: bool,
        data: dict,
        duration_ms: int,
        job_id: str = None
    ) -> None:
        """Emit plugin.completed event."""
        event_data = {
            "plugin_name": plugin_name,
            "stage": stage.value,
            "mode": mode,
            "success": success,
            "data": data,
            "duration_ms": duration_ms
        }
        if job_id:
            event_data["job_id"] = job_id

        self._event_bus.emit(Events.PLUGIN_COMPLETED, event_data)

    def _emit_plugin_failed(
        self,
        plugin_name: str,
        stage: Stage,
        error: str,
        duration_ms: int,
        job_id: str = None
    ) -> None:
        """Emit plugin.failed event."""
        event_data = {
            "plugin_name": plugin_name,
            "stage": stage.value,
            "error": error,
            "duration_ms": duration_ms
        }
        if job_id:
            event_data["job_id"] = job_id

        self._event_bus.emit(Events.PLUGIN_FAILED, event_data)

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Log message with debugger"""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func("stage_executor", message, **kwargs)

    def get_plugin_data_cache(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Get plugin data cache (for testing/debugging)"""
        return self._plugin_data_cache.copy()

    def clear_cache(self) -> None:
        """Clear plugin data cache"""
        self._plugin_data_cache.clear()

    def _build_global_state(self, job: JobState) -> dict[str, Any]:
        """
        Build global state dict for trigger evaluation.

        Cached per-job, invalidated after each plugin completes.
        """
        if job.id in self._global_state_cache:
            return self._global_state_cache[job.id]

        # Get run state
        run_state = self._state.run

        # Build global state structure
        global_state = {
            'run': {
                'id': run_state.id if run_state else '',
                'status': run_state.status.to_dict() if run_state else {}
            },
            'config': self._config,
            'job': {
                'id': job.id,
                'index': job.index,
                'input': {
                    'value': job.input.value,
                    'data': job.input.data
                },
                'output': {
                    'values': job.output.values,
                    'data': job.output.data
                },
                'status': job.status.to_dict(),
                'plugins': job.plugins  # Legacy access
            },
            'plugin': {}  # Current job's plugins
        }

        # Add plugin data from job.plugins
        # format: plugin.{name}.status and plugin.{name}.data
        for plugin_name, plugin_data in job.plugins.items():
            if isinstance(plugin_data, dict):
                global_state['plugin'][plugin_name] = plugin_data

        # Add provides registry data for provides.* prefix resolution
        # This enables requires like: provides.http.request
        global_state['provides'] = self._provides_registry.to_dict()

        self._global_state_cache[job.id] = global_state
        return global_state
