"""
Logger Service Implementation

Wraps Debugger to provide structured logging for plugins.
"""

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.utils.debug import Debugger


class LoggerServiceImpl:
    """
    LoggerService implementation that wraps Debugger.
    
    Provides consistent structured logging with plugin context.
    All log messages are prefixed with the plugin name.
    """
    
    def __init__(self, debugger: 'Debugger', plugin_name: str = "plugin"):
        """
        Initialize logger service.
        
        Args:
            debugger: Debugger instance
            plugin_name: Plugin name for log prefix
        """
        self._debugger = debugger
        self._plugin_name = plugin_name
    
    def _log(self, level: str, message: str, **kwargs) -> None:
        """Internal logging helper."""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.debug)
            log_func(self._plugin_name, message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log("info", message, **kwargs)
    
    def warn(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log("warn", message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log("error", message, **kwargs)
    
    def set_plugin_name(self, name: str) -> None:
        """Update plugin name context."""
        self._plugin_name = name
