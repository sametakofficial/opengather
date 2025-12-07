"""
Stage Executor - 4-stage plugin execution system

Session 11 - Phase 5: Executes plugins by stage with proper
lifecycle management, requires validation, and event emission.

Stages:
- INPUT: per_run mode - discovers files, creates jobs
- PARSE: per_job mode - parses filenames/metadata
- DATA: per_job mode - fetches external data (TMDB, TVDB)
- OUTPUT: mixed mode - executes tasks, writes files
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from archiverr.state.models import JobState, RunState
from archiverr.events import EventBus
from archiverr.utils.debug import Debugger, get_debugger
from archiverr.core.exceptions import StageError, PluginError
from archiverr.core.services import PluginServices, create_plugin_services

from .registry import PluginRegistry, Stage
from .requires_validator import RequiresValidator, RequiresResult


class ExecutionMode(Enum):
    """Plugin execution mode (Session 12)"""
    PER_RUN = "per_run"   # Execute once per run (outside stages)
    PER_JOB = "per_job"   # Execute for each job (PARSE, DATA, OUTPUT stages)


# Default execution mode by stage (Session 12: 3 stages only)
STAGE_MODES: Dict[Stage, ExecutionMode] = {
    Stage.PARSE: ExecutionMode.PER_JOB,
    Stage.DATA: ExecutionMode.PER_JOB,
    Stage.OUTPUT: ExecutionMode.PER_JOB,
}


@dataclass
class PluginExecutionResult:
    """Result of a single plugin execution"""
    plugin_name: str
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: int = 0
    skipped: bool = False
    skip_reason: Optional[str] = None


class StageExecutor:
    """
    Session 12: 3-stage plugin execution engine.
    
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
        config: Dict[str, Any],
        debugger: Optional[Debugger] = None
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
        self._plugin_data_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # Session 12: Provides registry removed
        # RequiresValidator now validates plugin data dependencies
        self._requires_validator = RequiresValidator(
            event_bus=self._event_bus
        )
    
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
        
        # Sort plugins by dependency order
        sorted_plugins = self._topological_sort(plugins, stage)
        
        # Determine execution mode
        mode = STAGE_MODES.get(stage, ExecutionMode.PER_JOB)
        
        try:
            if stage == Stage.OUTPUT:
                # OUTPUT stage uses mixed mode
                self._execute_mixed(stage, sorted_plugins)
            elif mode == ExecutionMode.PER_RUN:
                self._execute_per_run(stage, sorted_plugins)
            else:
                self._execute_per_job(stage, sorted_plugins)
                
        except Exception as e:
            self._log("error", f"Stage {stage.value} failed: {e}")
            raise StageError(f"Stage execution failed", stage=stage.value, context={"error": str(e)})
    
    def _execute_per_run(self, stage: Stage, plugins: List[Any]) -> None:
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
                if hasattr(plugin, 'execute_run'):
                    result = plugin.execute_run(services)
                elif hasattr(plugin, 'get_matches'):
                    # Legacy: input plugins use get_matches
                    matches = plugin.get_matches()
                    result = self._create_jobs_from_matches(matches)
                else:
                    self._log("warn", f"Plugin {plugin_name} has no execute_run or get_matches method")
                    continue
                
                duration_ms = self._calc_duration(start_time)
                
                # Session 12: Provides system removed
                
                # Emit success event
                self._emit_plugin_completed(
                    plugin_name=plugin_name,
                    stage=stage,
                    mode="per_run",
                    success=True,
                    data=getattr(result, 'data', {}) if result else {},
                    duration_ms=duration_ms
                )
                
            except Exception as e:
                duration_ms = self._calc_duration(start_time)
                self._log("error", f"Plugin {plugin_name} failed: {e}")
                
                # Session 12: Provides system removed
                
                self._emit_plugin_failed(
                    plugin_name=plugin_name,
                    stage=stage,
                    error=str(e),
                    duration_ms=duration_ms
                )
                # Continue with next plugin (best effort)
    
    def _execute_per_job(self, stage: Stage, plugins: List[Any]) -> None:
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
            self._event_bus.emit("job.stage_completed", {
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
        
        Handles:
        - Requires validation
        - Plugin execution
        - Result caching
        - Error handling
        """
        plugin_name = self._get_plugin_name(plugin)
        start_time = datetime.now()
        
        # Get requires and trigger_rule from manifest
        manifest = self._registry.get_manifest(plugin_name)
        requires = manifest.get('requires', []) if manifest else []
        trigger_rule = manifest.get('trigger_rule', 'all_success') if manifest else 'all_success'
        
        # Also check legacy expects/depends_on
        if not requires:
            requires = manifest.get('expects', []) if manifest else []
        
        # Validate requires (P1.1: with trigger_rule support)
        if requires:
            plugin_cache = self._plugin_data_cache.get(job.id, {})
            validation = self._requires_validator.validate(job, requires, plugin_cache)
            
            # P1.1: Check trigger_rule instead of simple satisfied check
            should_run = validation.check_trigger_rule(trigger_rule)
            
            if not should_run:
                self._log("debug", 
                         f"Skipping {plugin_name} for job {job.id}: "
                         f"trigger_rule={trigger_rule} not satisfied "
                         f"(success={validation.success_count}/{validation.total_count}, "
                         f"failed={validation.failed_count})")
                
                # Mark as skipped
                self._mark_skipped(job, plugin_name)
                
                return PluginExecutionResult(
                    plugin_name=plugin_name,
                    success=True,
                    data={},
                    skipped=True,
                    skip_reason=f"Trigger rule '{trigger_rule}' not satisfied: {', '.join(validation.missing)}"
                )
        
        try:
            self._log("debug", f"Executing {plugin_name} for job {job.id}")
            
            # Create services
            services = self._create_services(plugin_name)
            
            # Set current job in state service if supported
            if hasattr(services.state, 'set_current_job'):
                services.state.set_current_job(job.id)
            
            # Execute plugin - try new signature first, then legacy
            if hasattr(plugin, 'execute'):
                # Try new signature: execute(job, services) or execute(match_data, services)
                try:
                    import inspect
                    sig = inspect.signature(plugin.execute)
                    params = list(sig.parameters.keys())
                    
                    # New Session 11 format: execute(job, services)
                    if len(params) >= 2:
                        result = plugin.execute(job, services)
                    else:
                        # Legacy format: execute(match_data)
                        legacy_data = self._job_to_legacy_data(job)
                        result = plugin.execute(legacy_data)
                except TypeError:
                    # Fallback: try legacy format
                    legacy_data = self._job_to_legacy_data(job)
                    result = plugin.execute(legacy_data)
            elif hasattr(plugin, 'process'):
                # Legacy: process(match_data, context) pattern
                legacy_data = self._job_to_legacy_data(job)
                result = plugin.process(legacy_data, {})
            else:
                self._log("warn", f"Plugin {plugin_name} has no execute method")
                return PluginExecutionResult(
                    plugin_name=plugin_name,
                    success=False,
                    data={},
                    error="No execute method"
                )
            
            duration_ms = self._calc_duration(start_time)
            
            # Extract result data
            result_data = {}
            if hasattr(result, 'data') and result.data:
                result_data = result.data
            elif isinstance(result, dict):
                result_data = result
            
            # Cache plugin data for downstream plugins
            if result_data:
                self._plugin_data_cache.setdefault(job.id, {})[plugin_name] = result_data
                
                # Also update job.plugins dict for template access
                if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                    job.plugins[plugin_name] = result_data
                elif hasattr(job, 'plugins'):
                    # MatchState uses plugins dict
                    try:
                        job.plugins[plugin_name] = result_data
                    except (TypeError, AttributeError):
                        pass
            
            # Update job status
            success = True
            if hasattr(result, 'status'):
                success = result.status.value == "success" if hasattr(result.status, 'value') else bool(result.status)
            
            self._mark_executed(job, plugin_name, success)
            
            # Session 12: Provides system removed
            
            # Emit event
            self._emit_plugin_completed(
                plugin_name=plugin_name,
                stage=stage,
                mode="per_job",
                success=success,
                data=result_data,
                duration_ms=duration_ms,
                job_id=job.id
            )
            
            return PluginExecutionResult(
                plugin_name=plugin_name,
                success=success,
                data=result_data,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = self._calc_duration(start_time)
            error_msg = str(e)
            
            self._log("error", f"Plugin {plugin_name} failed for job {job.id}: {e}")
            self._mark_failed(job, plugin_name)
            
            self._emit_plugin_failed(
                plugin_name=plugin_name,
                stage=stage,
                error=error_msg,
                duration_ms=duration_ms,
                job_id=job.id
            )
            
            return PluginExecutionResult(
                plugin_name=plugin_name,
                success=False,
                data={},
                error=error_msg,
                duration_ms=duration_ms
            )
    
    def _execute_mixed(self, stage: Stage, plugins: List[Any]) -> None:
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
    
    def _topological_sort(self, plugins: Dict[str, Any], stage: Stage) -> List[Any]:
        """
        Sort plugins by dependency order.
        
        Simple implementation: plugins with no requires first,
        then by number of requires.
        """
        plugin_list = list(plugins.values())
        
        def sort_key(plugin):
            name = self._get_plugin_name(plugin)
            manifest = self._registry.get_manifest(name)
            requires = manifest.get('requires', []) if manifest else []
            return len(requires)
        
        return sorted(plugin_list, key=sort_key)
    
    def _group_parallel_plugins(self, plugins: List[Any]) -> List[List[Any]]:
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
            group_provides: Set[str] = self._get_plugin_provides(group[0])
            group_requires: Set[str] = self._get_plugin_requires(group[0])
            
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
    
    def _get_plugin_provides(self, plugin: Any) -> Set[str]:
        """Get provides declarations from plugin manifest."""
        name = self._get_plugin_name(plugin)
        manifest = self._registry.get_manifest(name)
        if not manifest:
            return set()
        
        provides = manifest.get('provides', [])
        if isinstance(provides, list):
            return set(provides)
        return set()
    
    def _get_plugin_requires(self, plugin: Any) -> Set[str]:
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
        plugins: List[Any],
        job: JobState,
        stage: Stage
    ) -> List[PluginExecutionResult]:
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
                except Exception as e:
                    plugin_name = self._get_plugin_name(plugin)
                    self._log("error", f"Parallel execution failed for {plugin_name}: {e}")
                    results.append(PluginExecutionResult(
                        plugin_name=plugin_name,
                        success=False,
                        data={},
                        error=str(e)
                    ))
        
        return results
    
    def _create_services(self, plugin_name: str) -> PluginServices:
        """Create PluginServices for a plugin"""
        return create_plugin_services(
            state_manager=self._state,
            event_bus=self._event_bus,
            debugger=self._debugger,
            config=self._config,
            plugin_name=plugin_name
        )
    
    def _create_jobs_from_matches(self, matches: List[Dict]) -> Any:
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
    
    def _get_all_jobs(self) -> List[JobState]:
        """Get all jobs from state"""
        if hasattr(self._state, 'get_all_jobs'):
            return self._state.get_all_jobs()
        elif hasattr(self._state, '_matches'):
            # Legacy: convert MatchState to JobState-like
            return list(self._state._matches.values())
        return []
    
    def _get_plugin_name(self, plugin: Any) -> str:
        """Get plugin name from plugin instance"""
        if hasattr(plugin, 'name'):
            return plugin.name
        if hasattr(plugin, '_name'):
            return plugin._name
        return str(type(plugin).__name__)
    
    def _job_to_legacy_data(self, job: JobState) -> Dict[str, Any]:
        """Convert JobState to legacy data format for old plugins"""
        # Get input value (Session 11: job.input.value, Legacy: job.input_path)
        input_value = ""
        input_data = {}
        
        if hasattr(job, 'input'):
            if hasattr(job.input, 'value'):
                input_value = job.input.value
            if hasattr(job.input, 'data'):
                input_data = job.input.data
        elif hasattr(job, 'input_path'):
            input_value = job.input_path
        
        # Get existing plugin data for downstream plugins
        plugin_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            plugin_data = job.plugins
        
        return {
            "input": {
                "path": input_value,    # Legacy key
                "value": input_value,   # Session 11 key
                "data": input_data      # Session 11 input.data
            },
            "plugins": plugin_data,     # For downstream plugins
            "index": job.index,
            "run_id": job.run_id
        }
    
    def _mark_executed(self, job: JobState, plugin_name: str, success: bool) -> None:
        """Mark plugin as executed in job status"""
        if success:
            if hasattr(job, 'add_executed'):
                job.add_executed(plugin_name)
            elif hasattr(job.status, 'executed'):
                if plugin_name not in job.status.executed:
                    job.status.executed.append(plugin_name)
        else:
            self._mark_failed(job, plugin_name)
    
    def _mark_failed(self, job: JobState, plugin_name: str) -> None:
        """Mark plugin as failed in job status"""
        if hasattr(job, 'add_failed'):
            job.add_failed(plugin_name)
        elif hasattr(job.status, 'failed'):
            if plugin_name not in job.status.failed:
                job.status.failed.append(plugin_name)
            job.status.success = False
    
    def _mark_skipped(self, job: JobState, plugin_name: str) -> None:
        """Mark plugin as skipped in job status"""
        if hasattr(job, 'add_skipped'):
            job.add_skipped(plugin_name)
        elif hasattr(job.status, 'skipped'):
            if plugin_name not in job.status.skipped:
                job.status.skipped.append(plugin_name)
    
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
        data: Dict,
        duration_ms: int,
        job_id: str = None
    ) -> None:
        """Emit plugin.completed event and update provides registry."""
        # Mark provides as completed
        self._complete_plugin_provides(plugin_name, success=success)
        
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
        
        self._event_bus.emit("plugin.completed", event_data)
    
    def _emit_plugin_failed(
        self,
        plugin_name: str,
        stage: Stage,
        error: str,
        duration_ms: int,
        job_id: str = None
    ) -> None:
        """Emit plugin.failed event and update provides registry."""
        # Mark provides as failed
        self._complete_plugin_provides(plugin_name, success=False)
        
        event_data = {
            "plugin_name": plugin_name,
            "stage": stage.value,
            "error": error,
            "duration_ms": duration_ms
        }
        if job_id:
            event_data["job_id"] = job_id
        
        self._event_bus.emit("plugin.failed", event_data)
    
    def _log(self, level: str, message: str, **kwargs) -> None:
        """Log message with debugger"""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func("stage_executor", message, **kwargs)
    
    def get_plugin_data_cache(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get plugin data cache (for testing/debugging)"""
        return self._plugin_data_cache.copy()
    
    def clear_cache(self) -> None:
        """Clear plugin data cache"""
        self._plugin_data_cache.clear()
    
    # Session 12: Provides registry methods removed
