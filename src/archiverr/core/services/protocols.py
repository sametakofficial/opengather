"""
Service Protocol Definitions

Type-safe interfaces for plugin dependency injection.
All plugin services must implement these protocols.
"""

from typing import Protocol, Dict, Any, List, Optional, Callable, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    from archiverr.state.models import JobState, RunState


@runtime_checkable
class StateService(Protocol):
    """
    State management service protocol.
    
    Provides access to run and job state for plugins.
    Plugins use this instead of directly accessing StateManager.
    
    Note: Plugin data is stored in separate 'plugins' collection,
    accessed via get_plugin_data() method.
    """
    
    def get_current_job(self) -> 'JobState':
        """
        Get currently executing job.
        
        Raises:
            RuntimeError: If no current job is set
        """
        ...
    
    def get_job(self, job_id: str) -> Optional['JobState']:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID (format: job_run_abc123_0)
            
        Returns:
            JobState or None if not found
        """
        ...
    
    def get_job_by_index(self, index: int) -> Optional['JobState']:
        """
        Get job by index within current run.
        
        Args:
            index: Job index (0-based)
            
        Returns:
            JobState or None if not found
        """
        ...
    
    def get_all_jobs(self) -> List['JobState']:
        """
        Get all jobs in current run.
        
        Returns:
            List of JobState objects
        """
        ...
    
    def get_run(self) -> 'RunState':
        """
        Get current run state.
        
        Raises:
            RuntimeError: If no active run
        """
        ...
    
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Dict[str, Any]:
        """
        Get plugin result data for a job.
        
        This accesses the separate 'plugins' collection for memory efficiency.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name (e.g., "tmdb", "renamer")
            
        Returns:
            Plugin data dict or empty dict if not found
        """
        ...
    
    def save_plugin_data(
        self,
        job_id: str,
        plugin_name: str,
        stage: str,
        data: Dict[str, Any],
        status: Dict[str, Any] = None
    ) -> None:
        """
        Save plugin execution result.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            stage: Plugin stage (input|parse|data|output)
            data: Plugin output data
            status: Execution status dict (optional)
        """
        ...


@runtime_checkable
class EventService(Protocol):
    """
    Event bus service protocol.
    
    Provides event emission and subscription for plugins.
    """
    
    def emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an event.
        
        Args:
            event: Event name (e.g., "plugin.completed", "file.created")
            data: Event payload
        """
        ...
    
    def subscribe(self, event: str, handler: Callable) -> None:
        """
        Subscribe to an event.
        
        Args:
            event: Event name pattern (supports wildcards)
            handler: Callback function(event_name, data)
        """
        ...


@runtime_checkable
class LoggerService(Protocol):
    """
    Structured logging service protocol.
    
    Provides consistent logging with plugin context.
    """
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with optional context"""
        ...
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with optional context"""
        ...
    
    def warn(self, message: str, **kwargs) -> None:
        """Log warning message with optional context"""
        ...
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with optional context"""
        ...


@runtime_checkable
class ConfigService(Protocol):
    """
    Configuration service protocol.
    
    Provides read-only access to configuration.
    """
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value by key (supports dot notation).
        
        Args:
            key: Config key (e.g., "options.debug", "tmdb.api_key")
            default: Default value if key not found
            
        Returns:
            Config value or default
        """
        ...
    
    def get_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get plugin configuration.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Plugin config dict or empty dict
        """
        ...
    
    def get_option(self, option: str, default: Any = None) -> Any:
        """
        Get from options section.
        
        Shorthand for get(f"options.{option}", default)
        
        Args:
            option: Option name
            default: Default value
            
        Returns:
            Option value or default
        """
        ...


@runtime_checkable
class TemplateService(Protocol):
    """
    Template rendering service protocol.
    
    Provides Jinja2 template rendering with context.
    """
    
    def render(self, template: str, context: Dict[str, Any] = None) -> str:
        """
        Render a template string.
        
        Args:
            template: Jinja2 template string
            context: Additional context to merge
            
        Returns:
            Rendered string
        """
        ...
    
    def build_context(self, job_id: str) -> Dict[str, Any]:
        """
        Build template context for a job.
        
        Includes run, job, plugins, config, and aliases.
        
        Args:
            job_id: Job ID
            
        Returns:
            Template context dict
        """
        ...
