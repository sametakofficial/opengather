"""
Base Plugin Classes - Abstract base classes for plugins

Provides:
- BasePlugin: Common plugin interface
- InputPlugin: For input plugins (scanner, file_reader)
- OutputPlugin: For output plugins (tmdb, renamer, ffprobe)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .context import ExecutionContext


@dataclass
class ValidationResult:
    """Result of a validation test"""
    passed: bool
    details: dict[str, Any]


class BasePlugin(ABC):
    """Base class for all plugins."""

    def __init__(self, config: dict[str, Any]):
        """
        Initialize plugin with configuration.
        
        Args:
            config: Plugin-specific configuration from config.yml
        """
        self.config = config
        self.name: str | None = None
        self.category: str | None = None
        self._metadata: dict[str, Any] = {}
        self._context: ExecutionContext | None = None
        self._initialized: bool = False

    def set_context(self, context: ExecutionContext):
        """
        Set execution context (called by executor before execute()).
        
        Args:
            context: ExecutionContext with runtime dependencies
        """
        self._context = context

    @property
    def context(self) -> ExecutionContext | None:
        """Get current execution context"""
        return self._context

    # =========================================================================
    # Convenience Logging Methods (use context internally)
    # =========================================================================

    def log(self, level: str, message: str, **kwargs):
        """
        Log message through context debugger.
        
        Args:
            level: Log level (debug, info, warn, error)
            message: Log message
            **kwargs: Additional key-value pairs to log
        """
        if self._context and self._context.debugger:
            log_func = getattr(self._context.debugger, level, self._context.debugger.info)
            log_func(self.name or self.__class__.__name__, message, **kwargs)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.log("debug", message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self.log("info", message, **kwargs)

    def warn(self, message: str, **kwargs):
        """Log warning message"""
        self.log("warn", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self.log("error", message, **kwargs)

    # =========================================================================
    # Data Access Methods
    # =========================================================================

    def get_previous_result(self, plugin_name: str) -> dict[str, Any] | None:
        """
        Get result from a previous plugin.
        
        Args:
            plugin_name: Name of the plugin to get result from
            
        Returns:
            Plugin result dict or None if not available
        """
        if self._context:
            return self._context.get_plugin_result(plugin_name)
        return None

    # =========================================================================
    # Task & Progress Emission
    # =========================================================================

    def emit_task(self, task_config: dict[str, Any]) -> dict[str, Any] | None:
        """
        Convenience method for task emission.
        
        Allows plugins to emit tasks during execution.
        
        Args:
            task_config: Task configuration dict
            
        Returns:
            Task result or None if context not available
        """
        if self._context:
            return self._context.emit_task(task_config)
        return None

    def emit_progress(self, percent: float, message: str = ""):
        """
        Convenience method for progress emission.
        
        Args:
            percent: Progress percentage (0-100)
            message: Optional progress message
        """
        if self._context:
            self._context.emit_progress(percent, message)

    # =========================================================================
    # Lifecycle Hooks
    # =========================================================================

    def setup(self) -> None:
        """
        Called once when plugin is loaded.
        Override to initialize resources (API clients, caches, etc.)
        """
        self._initialized = True

    def teardown(self) -> None:
        """
        Called when plugin is unloaded.
        Override to cleanup resources.
        """
        pass

    @abstractmethod
    def execute(self, *args, **kwargs):
        """Execute plugin logic - must be implemented by subclasses"""
        pass

    def _validate_duration(
        self,
        ffprobe_duration: float,
        api_runtime_minutes: int | None,
        tolerance_seconds: int = 600
    ) -> ValidationResult:
        """
        Validate video duration against API runtime.
        
        Args:
            ffprobe_duration: Duration from ffprobe in seconds
            api_runtime_minutes: Runtime from API in minutes (None if not available)
            tolerance_seconds: Allowed difference in seconds (default: 600 = 10 min)
            
        Returns:
            ValidationResult with passed status and details
        """
        if api_runtime_minutes is None or api_runtime_minutes == 0:
            return ValidationResult(
                passed=False,
                details={
                    'ffprobe_duration': ffprobe_duration,
                    'api_runtime': None,
                    'diff_seconds': None,
                    'tolerance': tolerance_seconds,
                    'reason': 'API runtime not available'
                }
            )

        api_duration_seconds = api_runtime_minutes * 60
        diff_seconds = abs(ffprobe_duration - api_duration_seconds)
        passed = diff_seconds <= tolerance_seconds

        return ValidationResult(
            passed=passed,
            details={
                'ffprobe_duration': ffprobe_duration,
                'api_runtime': api_runtime_minutes,
                'diff_seconds': diff_seconds,
                'tolerance': tolerance_seconds
            }
        )


class InputPlugin(BasePlugin):
    """Base class for input plugins (per_run mode)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.category = "input"

    @abstractmethod
    def execute(self) -> list[dict[str, Any]]:
        """
        Execute input plugin.
        
        Returns:
            List of matches: [{status: {...}, input: {...}, ...}]
        """
        pass


class OutputPlugin(BasePlugin):
    """Base class for output plugins (per_job mode)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.category = "output"

    @abstractmethod
    def execute(self, match_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute output plugin.
        
        Args:
            match_data: Current match data with results from previous plugins
            
        Returns:
            Plugin result: {status: {...}, ...data}
        """
        pass
