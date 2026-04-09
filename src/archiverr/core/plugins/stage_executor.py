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
from archiverr.core.provides_registry import ProvidesRegistry, get_provides_registry
from archiverr.core.services.plugin_services import PluginServices
from archiverr.core.triggers import TriggerRuleManager
from archiverr.events import EventBus, Events
from archiverr.state.models import JobState
from archiverr.utils.debug import Debugger, get_debugger

from .registry import PluginRegistry, Stage
from .resolver import DependencyResolver
from .sdk.result import PluginResult
from .sdk.types import PerRunPlugin


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
        debugger: Debugger | None = None
    ):
        """
        Initialize stage executor.
        
        Args:
            state: State manager for job/run state
            plugin_registry: Registry for plugin lookup
            event_bus: Event bus for notifications
            config: Application configuration
            debugger: Optional debugger for logging
        """
        self._state = state
        self._registry = plugin_registry
        self._event_bus = event_bus
        self._config = config
        self._debugger = debugger or get_debugger()

        # Plugin data cache: {job_id: {plugin_name: data}}
        self._plugin_data_cache: dict[str, dict[str, dict[str, Any]]] = {}

        # Trigger rule manager for dependency resolution
        self._trigger_manager = TriggerRuleManager()

        # Provides registry -- tracks plugin provide completion status
        self._provides_registry: ProvidesRegistry = get_provides_registry()
        self._register_provides_from_manifests()

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
                # OUTPUT stage uses mixed mode -- flatten groups for mixed dispatch
                all_plugins = [p for group in execution_groups for p in group]
                self._execute_mixed(stage, all_plugins)
            elif mode == ExecutionMode.PER_RUN:
                all_plugins = [p for group in execution_groups for p in group]
                self._execute_per_run(stage, all_plugins)
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

    def _execute_per_run(self, stage: Stage, plugins: list[Any]) -> None:
        """
        Execute plugins once per run (INPUT stage).
        
        Input plugins typically:
        - Discover files from filesystem
        - Create jobs via state.create_job()
        """
        self._log("debug", f"Executing {len(plugins)} plugins (per_run)")

        for plugin in plugins:
            plugin_name = self._get_plugin_name(plugin)
            start_time = datetime.now()

            try:
                self._log("debug", f"Executing plugin: {plugin_name}")

                # Create services for this plugin
                services = self._create_services(plugin_name)

                # Execute plugin (per_run mode uses execute_run)
                if isinstance(plugin, PerRunPlugin):
                    result = plugin.execute_run(services)
                elif hasattr(plugin, 'get_matches'):
                    # Legacy fallback: old input plugins use get_matches
                    self._log("warn", f"Plugin {plugin_name} uses legacy get_matches() -- migrate to execute_run()")
                    matches = plugin.get_matches()
                    result = self._create_jobs_from_matches(matches)
                else:
                    self._log("warn", f"Plugin {plugin_name} has no execute_run method")
                    continue

                duration_ms = self._calc_duration(start_time)

                # Emit success event
                self._emit_plugin_completed(
                    plugin_name=plugin_name,
                    stage=stage,
                    mode="per_run",
                    success=True,
                    data=getattr(result, 'data', {}) if result else {},
                    duration_ms=duration_ms
                )

            except PluginError as e:
                duration_ms = self._calc_duration(start_time)
                self._log("error", f"Plugin {plugin_name} error: {e}")

                self._emit_plugin_failed(
                    plugin_name=plugin_name,
                    stage=stage,
                    error=str(e),
                    duration_ms=duration_ms
                )
                # Continue with next plugin (best effort)
            except Exception as e:
                duration_ms = self._calc_duration(start_time)
                self._log("error", f"Plugin {plugin_name} unexpected error: {e}")

                self._emit_plugin_failed(
                    plugin_name=plugin_name,
                    stage=stage,
                    error=str(e),
                    duration_ms=duration_ms
                )
                # Continue with next plugin (best effort)

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

    def _execute_per_job(self, stage: Stage, plugins: list[Any]) -> None:
        """
        Execute plugins for each job (PARSE, DATA stages).

        For each job, groups plugins by requires/provides conflicts
        and executes conflict-free plugins in parallel.
        """
        jobs = self._get_all_jobs()

        if not jobs:
            self._log("warn", f"No jobs to process for stage: {stage.value}")
            return

        self._log("debug", f"Executing {len(plugins)} plugins for {len(jobs)} jobs")

        # Group plugins by conflicts for parallel execution
        plugin_groups = self._group_parallel_plugins(plugins)

        if len(plugin_groups) < len(plugins):
            self._log("debug", f"Parallel execution: {len(plugins)} plugins in {len(plugin_groups)} groups")

        for job in jobs:
            # Initialize cache for this job if needed
            if job.id not in self._plugin_data_cache:
                self._plugin_data_cache[job.id] = {}

            # Execute each group (groups run sequentially, plugins within group run parallel)
            for group in plugin_groups:
                if len(group) > 1:
                    # Multiple plugins can run in parallel
                    self._execute_plugin_group_parallel(group, job, stage)
                else:
                    # Single plugin, execute normally
                    self._execute_plugin_for_job(group[0], job, stage)

            # Emit job stage progress
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
        Execute a single plugin for a job.

        Coordinates: requires check -> invoke -> extract -> update state -> emit.
        Each step is delegated to a focused method.
        """
        plugin_name = self._get_plugin_name(plugin)
        start_time = datetime.now()
        manifest = self._registry.get_manifest(plugin_name)

        # Step 1: Check if plugin should run (requires + trigger rules)
        skip_result = self._check_plugin_requires(plugin_name, manifest, job)
        if skip_result:
            return skip_result

        try:
            self._log("debug", f"Executing {plugin_name} for job {job.id}")

            # Step 2: Invoke plugin (handles signature detection)
            services = self._create_services(plugin_name, job_id=job.id)
            result = self._invoke_plugin(plugin, job, services, plugin_name)
            if result is None:
                return PluginExecutionResult(
                    plugin_name=plugin_name, success=False, data={},
                    error="No execute method"
                )

            duration_ms = self._calc_duration(start_time)

            # Step 3: Extract result data and success status
            result_data, success = self._extract_plugin_result(result)

            # Step 4: Cache + update job state
            if result_data:
                self._plugin_data_cache.setdefault(job.id, {})[plugin_name] = result_data
            self._update_job_plugin_state(job, plugin_name, result_data, success, duration_ms)

            # Step 4.5: Update provides registry
            if success:
                self._provides_registry.complete_all(plugin_name)
            else:
                self._provides_registry.fail_all(plugin_name)

            # Step 5: Emit event and return
            self._emit_plugin_completed(
                plugin_name=plugin_name, stage=stage, mode="per_job",
                success=success, data=result_data, duration_ms=duration_ms,
                job_id=job.id
            )
            return PluginExecutionResult(
                plugin_name=plugin_name, success=success,
                data=result_data, duration_ms=duration_ms
            )

        except (PluginError, Exception) as e:
            # Mark provides as failed on error
            self._provides_registry.fail_all(plugin_name)
            return self._handle_plugin_error(
                e, plugin_name, job, stage, start_time
            )

    def _check_plugin_requires(
        self,
        plugin_name: str,
        manifest: dict[str, Any] | None,
        job: JobState
    ) -> PluginExecutionResult | None:
        """
        Check if plugin's requires/trigger_rule are satisfied.

        Returns PluginExecutionResult (skipped) if plugin should NOT run, None if OK.
        """
        requires = manifest.get('requires', []) if manifest else []
        trigger_rule = manifest.get('trigger_rule', 'all_success') if manifest else 'all_success'

        # Legacy expects fallback
        if not requires:
            requires = manifest.get('expects', []) if manifest else []

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

        self._log("debug",
                  f"Skipping {plugin_name} for job {job.id}: "
                  f"trigger_rule={trigger_rule} - {reason}")
        self._mark_skipped(job, plugin_name)

        return PluginExecutionResult(
            plugin_name=plugin_name, success=True, data={},
            skipped=True, skip_reason=f"Trigger rule '{trigger_rule}': {reason}"
        )

    def _invoke_plugin(
        self,
        plugin: Any,
        job: JobState,
        services: PluginServices,
        plugin_name: str
    ) -> Any | None:
        """
        Invoke plugin's execute method with signature detection.

        New-style (2+ params): plugin.execute(job, services) -> PluginResult
        Legacy (1 param): plugin.execute(match_data) -> dict
        Returns None if plugin has no execute method.
        """
        if not hasattr(plugin, 'execute'):
            self._log("warn", f"Plugin {plugin_name} has no execute method")
            return None

        import inspect
        try:
            sig = inspect.signature(plugin.execute)
            param_count = len(sig.parameters)
        except (ValueError, TypeError):
            param_count = 1  # Assume legacy on introspection failure

        if param_count >= 2:
            return plugin.execute(job, services)
        else:
            return plugin.execute(self._job_to_legacy_data(job))

    def _extract_plugin_result(self, result: Any) -> tuple[dict[str, Any], bool]:
        """
        Extract data dict and success bool from a plugin result.

        Handles PluginResult objects, plain dicts, and other return types.
        """
        # PluginResult (from sdk) -- preferred return type
        if isinstance(result, PluginResult):
            return result.data or {}, result.success

        # Plain dict -- legacy plugins return these directly
        if isinstance(result, dict):
            # Check for embedded status dict (legacy format: {status: {success: bool}, ...data})
            status = result.get('status')
            if isinstance(status, dict):
                success = status.get('success', True)
                # Data is everything except the status key
                result_data = {k: v for k, v in result.items() if k != 'status'}
                return result_data, success
            return result, True

        # Unknown return type -- try attribute access as fallback
        result_data: dict[str, Any] = {}
        if hasattr(result, 'data') and result.data:
            result_data = result.data

        success = True
        if hasattr(result, 'success'):
            success = bool(result.success)

        return result_data, success

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

    def _handle_plugin_error(
        self,
        error: Exception,
        plugin_name: str,
        job: JobState,
        stage: Stage,
        start_time: datetime
    ) -> PluginExecutionResult:
        """Handle plugin execution error: log, mark failed, emit event, return result."""
        duration_ms = self._calc_duration(start_time)
        error_msg = str(error)
        level = "error" if isinstance(error, PluginError) else "error"
        label = "error" if isinstance(error, PluginError) else "unexpected error"

        self._log(level, f"Plugin {plugin_name} {label} for job {job.id}: {error}")
        self._mark_failed(job, plugin_name)
        self._emit_plugin_failed(
            plugin_name=plugin_name, stage=stage, error=error_msg,
            duration_ms=duration_ms, job_id=job.id
        )

        return PluginExecutionResult(
            plugin_name=plugin_name, success=False, data={},
            error=error_msg, duration_ms=duration_ms
        )

    def _execute_mixed(self, stage: Stage, plugins: list[Any]) -> None:
        """
        Execute plugins in mixed mode (OUTPUT stage).
        
        Some plugins run per_job (tasker), some per_run (rclone).
        Mode is determined from manifest 'execution_mode' field.
        """
        per_job_plugins = []
        per_run_plugins = []

        for plugin in plugins:
            plugin_name = self._get_plugin_name(plugin)
            manifest = self._registry.get_manifest(plugin_name)
            mode = manifest.get('execution_mode', 'per_job') if manifest else 'per_job'

            if mode == 'per_run':
                per_run_plugins.append(plugin)
            else:
                per_job_plugins.append(plugin)

        # Execute per_job plugins first
        if per_job_plugins:
            self._execute_per_job(stage, per_job_plugins)

        # Then per_run plugins
        if per_run_plugins:
            self._execute_per_run(stage, per_run_plugins)

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

    def _topological_sort(self, plugins: dict[str, Any], stage: Stage) -> list[Any]:
        """
        Sort plugins by dependency order using topological sort.
        
        Simple implementation: plugins with no requires first,
        then by number of requires.
        """
        # Debug check
        if isinstance(plugins, list):
            self._log("error", f"_topological_sort received list instead of dict for stage {stage.value}")
            return plugins  # Return as-is if already a list

        plugin_list = list(plugins.values())

        def sort_key(plugin):
            name = self._get_plugin_name(plugin)
            manifest = self._registry.get_manifest(name)
            requires = manifest.get('requires', []) if manifest else []
            return len(requires)

        return sorted(plugin_list, key=sort_key)

    def _group_parallel_plugins(self, plugins: list[Any]) -> list[list[Any]]:
        """
        Group plugins that can run in parallel based on requires/provides conflicts.
        
        Two plugins can run in parallel if:
        - Neither provides something the other requires
        - They don't write to the same provides path (lockable resources)
        
        Returns:
            List of groups, where each group can run in parallel
        """
        if not plugins:
            return []

        groups = []
        remaining = list(plugins)

        while remaining:
            # Start new group with first remaining plugin
            group = [remaining.pop(0)]
            group_provides: set[str] = self._get_plugin_provides(group[0])
            group_requires: set[str] = self._get_plugin_requires(group[0])

            # Try to add more plugins to this group
            i = 0
            while i < len(remaining):
                plugin = remaining[i]
                plugin_provides = self._get_plugin_provides(plugin)
                plugin_requires = self._get_plugin_requires(plugin)

                # Check for conflicts
                has_conflict = False

                # Plugin requires something group provides → must wait
                if plugin_requires & group_provides:
                    has_conflict = True

                # Group requires something plugin provides → must wait
                if group_requires & plugin_provides:
                    has_conflict = True

                # Both provide same lockable resource → conflict
                if plugin_provides & group_provides:
                    # Check if any are lockable (fs.write:path style)
                    for p in plugin_provides:
                        if ':' in p and p in group_provides:
                            has_conflict = True
                            break

                if not has_conflict:
                    group.append(remaining.pop(i))
                    group_provides |= plugin_provides
                    group_requires |= plugin_requires
                else:
                    i += 1

            groups.append(group)

        return groups

    def _get_plugin_provides(self, plugin: Any) -> set[str]:
        """Get provides declarations from plugin manifest."""
        name = self._get_plugin_name(plugin)
        manifest = self._registry.get_manifest(name)
        if not manifest:
            return set()

        provides = manifest.get('provides', [])
        if isinstance(provides, list):
            return set(provides)
        return set()

    def _get_plugin_requires(self, plugin: Any) -> set[str]:
        """Get requires declarations from plugin manifest."""
        name = self._get_plugin_name(plugin)
        manifest = self._registry.get_manifest(name)
        if not manifest:
            return set()

        requires = manifest.get('requires', [])
        if isinstance(requires, list):
            return set(requires)
        return set()

    def _execute_plugin_group_parallel(
        self,
        plugins: list[Any],
        job: JobState,
        stage: Stage
    ) -> list[PluginExecutionResult]:
        """
        Execute a group of plugins in parallel for a single job.
        
        Uses ThreadPoolExecutor for parallel execution.
        """
        if len(plugins) == 1:
            # Single plugin, no need for threading overhead
            return [self._execute_plugin_for_job(plugins[0], job, stage)]

        results = []
        with ThreadPoolExecutor(max_workers=min(len(plugins), 4)) as executor:
            futures = {
                executor.submit(self._execute_plugin_for_job, plugin, job, stage): plugin
                for plugin in plugins
            }

            for future in as_completed(futures):
                plugin = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except PluginError as e:
                    plugin_name = self._get_plugin_name(plugin)
                    self._log("error", f"Parallel execution plugin error for {plugin_name}: {e}")
                    results.append(PluginExecutionResult(
                        plugin_name=plugin_name,
                        success=False,
                        data={},
                        error=str(e)
                    ))
                except Exception as e:
                    plugin_name = self._get_plugin_name(plugin)
                    self._log("error", f"Parallel execution unexpected error for {plugin_name}: {e}")
                    results.append(PluginExecutionResult(
                        plugin_name=plugin_name,
                        success=False,
                        data={},
                        error=str(e)
                    ))

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

        # Create services with context
        services = PluginServices(
            state=self._state,
            event_bus=self._event_bus,
            logger=self._debugger,
            config=self._config,
            mode=mode,
            current_job_id=job_id,
            current_plugin_name=plugin_name
        )

        return services

    def _create_jobs_from_matches(self, matches: list[dict]) -> Any:
        """
        Create jobs from legacy match format.
        
        Called when input plugin uses get_matches() instead of execute_run().
        """
        for i, match in enumerate(matches):
            # Extract input path
            input_path = ""
            if isinstance(match.get('input'), dict):
                input_path = match['input'].get('path', '')
            else:
                input_path = str(match.get('input', ''))

            # Create job via state manager
            if hasattr(self._state, 'register_match'):
                self._state.register_match(i, input_path)
            elif hasattr(self._state, 'create_job'):
                self._state.create_job(input_path)

        return matches

    def _get_all_jobs(self) -> list[JobState]:
        """Get all jobs from state"""
        if hasattr(self._state, 'get_all_jobs'):
            return self._state.get_all_jobs()
        elif hasattr(self._state, '_matches'):
            # Fallback for older state manager implementations
            return list(self._state._matches.values())
        return []

    def _get_plugin_name(self, plugin: Any) -> str:
        """Get plugin name from plugin instance."""
        return getattr(plugin, 'name', None) or getattr(plugin, '_name', None) or type(plugin).__name__

    def _job_to_legacy_data(self, job: JobState) -> dict[str, Any]:
        """Convert JobState to legacy data format for old plugins"""
        # Get input value (job.input.value, Legacy: job.input_path)
        input_value = ""
        input_data = {}

        # JobState has typed input field with value and data attributes
        input_value = job.input.value
        input_data = job.input.data

        # Get existing plugin data for downstream plugins
        plugin_data = job.plugins

        return {
            "input": {
                "path": input_value,    # Legacy key
                "value": input_value,   # key
                "data": input_data      # input.data
            },
            "plugins": plugin_data,     # For downstream plugins
            "index": job.index,
            "run_id": job.run_id
        }

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
        Build global state dict for trigger evaluation ().
        
        Args:
            job: Current job state
            
        Returns:
            Global state dict with run, config, job, plugin structure
        """
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

        return global_state
