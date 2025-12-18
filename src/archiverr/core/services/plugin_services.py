"""
Plugin Services - Core plugin communication API.

Methods:
- create_job(input_value, input_data) -> job_id
- update_job(job_id, key, value)
- update_plugin(target_id, plugin_name, data)
- get_plugin_data(target_id, plugin_name)
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
    
    def create_job(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
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
    
    def createJob(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
        """Backward compatible alias for create_job."""
        return self.create_job(input_value, input_data)
    
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
    
    def updateJob(self, key: str, value: Any) -> None:
        """Backward compatible alias for update_job."""
        self.update_job(self._current_job_id, key, value)
    
    def update_plugin(self, target_id: str = None, plugin_name: str = None, data: Dict[str, Any] = None) -> None:
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
    
    def updatePlugin(self, data: Dict[str, Any]) -> None:
        """Backward compatible alias for update_plugin."""
        self.update_plugin(self._current_job_id, self._current_plugin_name, data)
    
    def get_plugin_data(self, target_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin data.
        
        Args:
            target_id: "job_xxx" or "run_xxx"
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None
        """
        return self._state.get_plugin_data(target_id, plugin_name)
    
    # ==================== STATE ACCESS ====================
    
    def get_run(self):
        """Get run state (read-only for all plugins)."""
        return self._state.run
    
    def get_config(self) -> Dict[str, Any]:
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
    
    def get_current_plugins(self) -> Dict[str, Any]:
        """
        Get current job's plugins.
        """
        return self._state.plugin
    
    def get_all_plugins(self):
        """
        Get all jobs' plugins (read-only).
        """
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
    
    # ==================== PLUGIN STATUS REPORTING ====================
    
    def update_status(
        self,
        state: str,
        success: bool,
        message: str = "",
        error: Optional[str] = None
    ) -> None:
        """
        plugin reports its own status (session 14 - plugin autonomy).
        
        args:
            state: plugin state (pending | running | completed | failed | skipped)
            success: whether plugin succeeded
            message: human-readable status message
            error: error message if failed
        
        example:
            services.update_status(
                state="completed",
                success=True,
                message="fetched 10 movies from tmdb"
            )
        """
        if not self._current_plugin_name:
            raise RuntimeError("update_status() requires plugin context")
        
        from datetime import datetime
        
        status_data = {
            "state": state,
            "success": success,
            "message": message,
            "error": error,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # update plugin status in state
        if self._current_job_id:
            # per_job plugin - update job's plugin status
            job = self._state.get_job_by_id(self._current_job_id)
            if job:
                # Session 17: Update job.status.plugins dict
                job.status.plugins[self._current_plugin_name] = status_data
                
                # add to executed/failed/skipped lists (Legacy/Compat)
                if state == "completed" and self._current_plugin_name not in job.status.executed:
                    job.status.executed.append(self._current_plugin_name)
                elif state == "failed" and self._current_plugin_name not in job.status.failed:
                    job.status.failed.append(self._current_plugin_name)
                elif state == "skipped" and self._current_plugin_name not in job.status.skipped:
                    job.status.skipped.append(self._current_plugin_name)
        elif self._state.run:
            # per_run plugin - update run's plugin status
            # Session 17: Update run.status.plugins dict
            self._state.run.status.plugins[self._current_plugin_name] = status_data
        
        # emit status event
        self._event_bus.emit(f"plugin.{state}", {
            "plugin": self._current_plugin_name,
            "job_id": self._current_job_id,
            "success": success,
            "message": message,
            "error": error
        }, source="plugin")
        
        self._logger.info(
            "plugin_services",
            f"plugin status updated: {state}",
            plugin=self._current_plugin_name,
            success=success,
            message=message
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
    
    @property
    def run_id(self) -> Optional[str]:
        """Get current run ID."""
        run = self._state.run
        return run.id if run else None
