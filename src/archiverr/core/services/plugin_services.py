"""
Plugin Services - Session 12

Provides 3 core methods for plugin communication:
1. createJob(input_value, input_data) -> job_id
2. updateJob(key, value)  # No ID - current context
3. updatePlugin(data)     # No name - current context

Access Control:
- per_run: Only createJob allowed
- per_job: All methods allowed

Current Context:
- job_id: Set by Orchestrator before plugin execution
- plugin_name: Set by Orchestrator before plugin execution
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.state.manager import GlobalStateManager
    from archiverr.events import EventBus
    from archiverr.utils.debug import Debugger


class PluginServices:
    """
    Session 12 Plugin Services.
    
    Provides controlled access to state management for plugins.
    Enforces per_run vs per_job access rules.
    Maintains current job/plugin context internally.
    
    Usage:
        # For per_run plugins
        services = PluginServices(
            state=state,
            event_bus=event_bus,
            logger=logger,
            config=config,
            mode="per_run"
        )
        
        # For per_job plugins
        services = PluginServices(
            state=state,
            event_bus=event_bus,
            logger=logger,
            config=config,
            mode="per_job",
            current_job_id="job_abc_0",
            current_plugin_name="tmdb"
        )
    """
    
    def __init__(
        self,
        state: 'GlobalStateManager',
        event_bus: 'EventBus',
        logger: 'Debugger',
        config: Dict[str, Any],
        mode: str,  # "per_run" or "per_job"
        current_job_id: Optional[str] = None,
        current_plugin_name: Optional[str] = None
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
        """
        self._state = state
        self._event_bus = event_bus
        self._logger = logger
        self._config = config
        self._mode = mode
        self._current_job_id = current_job_id
        self._current_plugin_name = current_plugin_name
    
    # ==================== CORE METHODS ====================
    
    def createJob(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
        """
        Create new job (both per_run and per_job).
        
        Args:
            input_value: Job input (path, query, etc.)
            input_data: Additional input metadata
            
        Returns:
            Job ID (string)
        """
        job_id = self._state.create_job(input_value, input_data or {})
        
        self._logger.debug(
            "plugin_services",
            f"Created job: {job_id}",
            mode=self._mode,
            input_value=input_value
        )
        
        return job_id
    
    def updateJob(self, key: str, value: Any) -> None:
        """
        Update CURRENT job (per_job only).
        
        Args:
            key: Dot-notation path (e.g., "output.values")
            value: New value
            
        Raises:
            PermissionError: If called from per_run plugin
            ValueError: If no current job context
        """
        self._check_per_job_access("updateJob")
        
        if not self._current_job_id:
            raise ValueError("No current job context")
        
        self._state.update_job(self._current_job_id, key, value)
        
        self._logger.debug(
            "plugin_services",
            f"Updated job: {self._current_job_id}",
            key=key,
            plugin=self._current_plugin_name
        )
    
    def updatePlugin(self, data: Dict[str, Any]) -> None:
        """
        Update CURRENT plugin data (per_job only).
        
        Data is stored in: plugin.{current_plugin_name}.data
        
        Args:
            data: Plugin data
            
        Raises:
            PermissionError: If called from per_run plugin
            ValueError: If no current job/plugin context
        """
        self._check_per_job_access("updatePlugin")
        
        if not self._current_job_id:
            raise ValueError("No current job context")
        if not self._current_plugin_name:
            raise ValueError("No current plugin context")
        
        self._state.update_plugin(self._current_job_id, self._current_plugin_name, data)
        
        self._logger.debug(
            "plugin_services",
            f"Updated plugin: {self._current_plugin_name}",
            job=self._current_job_id,
            data_keys=list(data.keys())
        )
    
    # ==================== STATE ACCESS ====================
    
    def get_run(self):
        """Get run state (read-only for all plugins)."""
        return self._state.run
    
    def get_config(self) -> Dict[str, Any]:
        """Get frozen config (read-only for all plugins)."""
        return self._config
    
    def get_current_job(self):
        """
        Get current job (per_job only).
        
        Raises:
            PermissionError: If called from per_run plugin
        """
        self._check_per_job_access("get_current_job")
        return self._state.job
    
    def get_all_jobs(self):
        """
        Get all jobs (per_job only, read-only).
        
        Raises:
            PermissionError: If called from per_run plugin
        """
        self._check_per_job_access("get_all_jobs")
        return self._state.jobs
    
    def get_current_plugins(self) -> Dict[str, Any]:
        """
        Get current job's plugins (per_job only).
        
        Raises:
            PermissionError: If called from per_run plugin
        """
        self._check_per_job_access("get_current_plugins")
        return self._state.plugin
    
    def get_all_plugins(self):
        """
        Get all jobs' plugins (per_job only, read-only).
        
        Raises:
            PermissionError: If called from per_run plugin
        """
        self._check_per_job_access("get_all_plugins")
        return self._state.plugins
    
    # ==================== EVENT BUS ====================
    
    def emit(self, event: str, data: Dict[str, Any] = None) -> None:
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
    
    # ==================== ACCESS CONTROL ====================
    
    def _check_per_job_access(self, method_name: str) -> None:
        """
        Check if per_job method can be called.
        
        Raises:
            PermissionError: If called from per_run plugin
        """
        if self._mode != "per_job":
            raise PermissionError(
                f"{method_name}() can only be called by per_job plugins. "
                f"Current mode: {self._mode}"
            )
    
    # ==================== PROPERTIES ====================
    
    @property
    def mode(self) -> str:
        """Get plugin mode (per_run or per_job)."""
        return self._mode
    
    @property
    def current_job_id(self) -> Optional[str]:
        """Get current job ID."""
        return self._current_job_id
    
    @property
    def current_plugin_name(self) -> Optional[str]:
        """Get current plugin name."""
        return self._current_plugin_name
