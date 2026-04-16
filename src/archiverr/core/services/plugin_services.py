"""
Plugin Services - Core plugin communication API.

Methods:
- create_job(input_value, input_data) -> job_id
- update_job(job_id, key, value)
- update_plugin(target_id, plugin_name, data)
- get_plugin_data(target_id, plugin_name)
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from archiverr.events import EventBus
    from archiverr.state.manager import GlobalStateManager
    from archiverr.utils.debug import Debugger


class PluginServices:
    """Controlled access to state management for plugins."""

    def __init__(
        self,
        state: 'GlobalStateManager',
        event_bus: 'EventBus',
        logger: 'Debugger',
        config: dict[str, Any],
        mode: str,  # "per_run" or "per_job"
        current_job_id: str | None = None,
        current_plugin_name: str | None = None,
        provides_registry: 'Any' = None
    ):
        """
        Initialize Plugin Services.

        Args:
            state: GlobalStateManager instance
            event_bus: EventBus instance
            logger: Debugger instance
            config: Frozen config
            mode: "per_run" or "per_job"
            current_job_id: Current job ID (per_job only)
            current_plugin_name: Current plugin name (per_job only)
            provides_registry: Optional ProvidesRegistry for early completion
        """
        self._state = state
        self._event_bus = event_bus
        self._logger = logger
        self._config = config
        self._mode = mode
        self._current_job_id = current_job_id
        self._current_plugin_name = current_plugin_name
        self._provides_registry = provides_registry

    def create_job(self, input_value: str, input_data: dict[str, Any] = None) -> str:
        """
        Create new job.
        
        Args:
            input_value: Job input (path, query, etc.)
            input_data: Plugin-specific data
            
        Returns:
            Job ID
        """
        job_id = self._state.create_job(
            input_value=input_value,
            input_data=input_data or {}
        )

        self._logger.debug(
            "plugin_services",
            f"Created job: {job_id}",
            mode=self._mode,
            input_value=input_value
        )

        return job_id

    def update_job(self, job_id: str = None, key: str = None, value: Any = None) -> None:
        """
        Update job state.
        
        Args:
            job_id: Target job ID (uses current context if None)
            key: Dot-notation path (e.g., "output.values")
            value: New value
        """
        target_job_id = job_id or self._current_job_id
        if not target_job_id:
            raise ValueError("No job ID specified and no current job context")

        self._state.update_job(target_job_id, key, value)

        self._logger.debug(
            "plugin_services",
            f"Updated job: {target_job_id}",
            key=key,
            plugin=self._current_plugin_name
        )

    def update_plugin(self, target_id: str = None, plugin_name: str = None, data: dict[str, Any] = None) -> None:
        """
        Update plugin data.
        
        Args:
            target_id: "job_xxx" or "run_xxx" (uses current context if None)
            plugin_name: Plugin name (uses current context if None)
            data: Plugin data
        """
        tid = target_id or self._current_job_id
        pname = plugin_name or self._current_plugin_name

        if not tid:
            raise ValueError("No target_id specified and no current context")
        if not pname:
            raise ValueError("No plugin_name specified and no current context")

        self._state.update_plugin(tid, pname, data or {})

        self._logger.debug(
            "plugin_services",
            f"Updated plugin: {pname}",
            target_id=tid,
            data_keys=list(data.keys()) if data else []
        )

    def get_plugin_data(self, target_id: str, plugin_name: str) -> dict[str, Any] | None:
        """
        Get plugin data.
        
        Args:
            target_id: "job_xxx" or "run_xxx"
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None
        """
        return self._state.get_plugin_data(target_id, plugin_name)

    def get_run(self):
        """Get run state (read-only for all plugins)."""
        return self._state.run

    def get_config(self) -> dict[str, Any]:
        """Get frozen config (read-only for all plugins)."""
        return self._config

    def get_current_job(self):
        """
        Get current job.
        """
        return self._state.job

    def get_all_jobs(self):
        """
        Get all jobs (read-only).
        """
        return self._state.jobs

    def get_current_plugins(self) -> dict[str, Any]:
        """
        Get current job's plugins.
        """
        return self._state.plugin

    def get_all_plugins(self):
        """
        Get all jobs' plugins (read-only).
        """
        return self._state.plugins

    def emit(self, event: str, data: dict[str, Any] = None) -> None:
        """
        Emit event (both modes).
        
        Args:
            event: Event name
            data: Event data
        """
        self._event_bus.emit(event, data or {}, source=self._current_plugin_name or "plugin")

        self._logger.debug(
            "plugin_services",
            f"Emitted event: {event}",
            plugin=self._current_plugin_name,
            mode=self._mode
        )

    @property
    def mode(self) -> str:
        """Get plugin mode (per_run or per_job)."""
        return self._mode

    @property
    def current_job_id(self) -> str | None:
        """Get current job ID."""
        return self._current_job_id

    @property
    def current_plugin_name(self) -> str | None:
        """Get current plugin name."""
        return self._current_plugin_name

    @property
    def run_id(self) -> str | None:
        """Get current run ID."""
        run = self._state.run
        return run.id if run else None

    @property
    def provides(self):
        """Get provides service for early completion.

        Allows plugins to mark individual provides as completed during execution:
            services.provides.complete("http.request")
            services.provides.is_completed("http.request")

        Raises:
            PluginError: If provides_registry was not wired at construction.
        """
        if self._provides_registry is None:
            from archiverr.core.exceptions import PluginError
            raise PluginError(
                "services.provides accessed without provides_registry wiring. "
                "Executor must construct PluginServices with provides_registry=... "
                f"(plugin={self._current_plugin_name or 'unknown'}, mode={self._mode})"
            )
        from archiverr.core.services.provides_service import ProvidesServiceImpl
        return ProvidesServiceImpl(self._provides_registry, self._current_plugin_name or "unknown")
