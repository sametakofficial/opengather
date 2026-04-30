"""Plugin Data Manager - Extracted from GlobalStateManager.

This module handles plugin data operations.
Follows Single Responsibility Principle by separating plugin data management from state management.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .context import ExecutionContext
    from .event_emitter import StateEventEmitter
    from .models import RunState
    from .persistence_delegate import PersistenceDelegate

from archiverr.events import Events


class PluginDataManager:
    """
    Manages plugin data operations.
    
    Extracted from GlobalStateManager to follow SRP.
    Handles plugin data updates, retrieval, and persistence.
    """

    def __init__(
        self,
        context: 'ExecutionContext',
        persistence: 'PersistenceDelegate',
        event_emitter: 'StateEventEmitter' = None,
        logger=None
    ):
        """
        Initialize plugin data manager.
        
        Args:
            context: ExecutionContext for plugin data storage
            persistence: PersistenceDelegate for saving plugin data
            event_emitter: Optional StateEventEmitter for events
            logger: Optional logging function
        """
        self._context = context
        self._persistence = persistence
        self._event_emitter = event_emitter
        self._log = logger or self._noop_log

    def _noop_log(self, level: str, component: str, message: str, **kwargs):
        """No-op logger when none provided."""
        pass

    def _emit(self, event_name: str, data: dict[str, Any] = None):
        """Emit event if event emitter is configured."""
        if self._event_emitter:
            self._event_emitter.emit(event_name, data)

    def update_plugin(
        self,
        target_id: str,
        plugin_name: str,
        data: dict[str, Any],
        run: 'RunState' = None,
        get_job_func=None
    ) -> None:
        """
        Update plugin data for a job or run target.
        
        Args:
            target_id: Job ID or Run ID
            plugin_name: Plugin name
            data: Plugin data dictionary
            run: Current RunState (for run-level plugins)
            get_job_func: Function to get job by ID
        """
        # Determine if this is a run or job target
        is_run_target = target_id.startswith("run_") or (run and target_id == run.id)

        if is_run_target:
            self._update_run_plugin(target_id, plugin_name, data, run)
        else:
            self._update_job_plugin(target_id, plugin_name, data, get_job_func)

        self._emit(Events.PLUGIN_UPDATED, {
            "target_id": target_id,
            "plugin_name": plugin_name,
            "data": data
        })

    def _update_run_plugin(
        self,
        target_id: str,
        plugin_name: str,
        data: dict[str, Any],
        run: 'RunState'
    ) -> None:
        """Update per-run plugin data."""
        run_id = target_id if target_id.startswith("run_") else f"run_{target_id}"

        if run:
            # Store directly in RunState.plugins (canonical embedded surface)
            run.plugins[plugin_name] = data

            # Store in unified context plugins map
            self._context._all_plugins.setdefault(run_id, {})[plugin_name] = data

            # Persist via canonical save_run (runs.plugins embedded)
            self._persistence.save_run(run)

        self._log("debug", "plugin_data",
                 f"Updated run plugin {plugin_name}",
                 run_id=run_id,
                 data_keys=list(data.keys()) if isinstance(data, dict) else [])

    def _update_job_plugin(
        self,
        job_id: str,
        plugin_name: str,
        data: dict[str, Any],
        get_job_func
    ) -> None:
        """Update per-job plugin data."""
        job = get_job_func(job_id) if get_job_func else None

        if job:
            job.plugins[plugin_name] = data

            # Store in unified context plugins map
            self._context._all_plugins.setdefault(job_id, {})[plugin_name] = data

            # Keep current job plugin view in sync
            if self._context._current_job and self._context._current_job.id == job_id:
                self._context._current_plugins = job.plugins

            # Save plugin document
            plugin_doc = {
                "job_id": job_id,
                "plugin_name": plugin_name,
                "data": data,
                "run_id": job.run_id,
                "job_index": job.index
            }
            self._persistence.save_plugin(plugin_doc)

            self._log("debug", "plugin_data",
                     f"Updated plugin {plugin_name} for job {job_id}",
                     data_keys=list(data.keys()) if isinstance(data, dict) else [],
                     data_size=len(str(data)))

    def get_plugin_data(self, target_id: str, plugin_name: str) -> dict[str, Any]:
        """
        Get plugin data for a target.
        
        Args:
            target_id: Job ID or Run ID
            plugin_name: Plugin name
            
        Returns:
            Plugin data dictionary or empty dict
        """
        plugins = self._context._all_plugins.get(target_id, {})
        return plugins.get(plugin_name, {})

    def get_all_plugin_data(self, target_id: str) -> dict[str, dict[str, Any]]:
        """
        Get all plugin data for a target.
        
        Args:
            target_id: Job ID or Run ID
            
        Returns:
            Dictionary of plugin_name -> data
        """
        return self._context._all_plugins.get(target_id, {})

    def get_plugin_names(self, job_id: str, get_job_func=None) -> list[str]:
        """
        Get list of all plugins that have data for a job.
        
        Args:
            job_id: Job ID
            get_job_func: Function to get job by ID
            
        Returns:
            List of plugin names
        """
        job = get_job_func(job_id) if get_job_func else None
        if not job:
            return []

        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            return list(job.plugins.keys())

        return []

