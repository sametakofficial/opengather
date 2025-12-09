"""
Debug System - Plugin-agnostic live debugging infrastructure

This module provides a professional, plugin-agnostic debug system that:
1. Allows plugins to send debug messages without knowing about system internals
2. Supports live, immediate output when debug mode is enabled
3. Provides standard log levels (DEBUG, INFO, WARN, ERROR)
4. Maintains strict plugin-agnostic principles (no plugin-specific logic)

Usage in plugins:
    debugger = get_debugger()
    debugger.debug("tmdb", "Searching for movie", query="Inception", year=2010)
    debugger.info("tmdb", "Match found", tmdb_id=27205, score=0.95)

Usage in core:
    debugger = get_debugger()
    debugger.info("discovery", "Found plugins", count=7)
    debugger.debug("executor", "Executing group", group=["ffprobe", "renamer"])
"""
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from pathlib import Path
import json


# Log level constants (Python standard)
class LogLevel:
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    NOTSET = 0

class DebugSystem:
    """
    Professional debug system with live output and optional MongoDB persistence.
    
    Features:
    - Config-driven log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Level-based filtering
    - Live output (immediate stderr flush)
    - Plugin-agnostic (any component can log)
    - Structured context fields
    - ISO8601 timestamps
    - Optional MongoDB diagnostics logging
    """
    
    def __init__(self, enabled: bool = False, level: int = None, diagnostics_logger = None):
        self.enabled = enabled
        # If level not specified, use DEBUG if enabled, else WARNING
        self.level = level if level is not None else (LogLevel.DEBUG if enabled else LogLevel.WARNING)
        self.log_buffer: List[Dict[str, Any]] = []  # Always collect logs, regardless of debug mode
        self._diagnostics_logger = diagnostics_logger
        self._execution_id: Optional[str] = None
    
    def set_execution_id(self, execution_id: str) -> None:
        """Set current execution ID for log correlation"""
        self._execution_id = execution_id
    
    def set_diagnostics_logger(self, logger) -> None:
        """Set MongoDB diagnostics logger"""
        self._diagnostics_logger = logger
    
    def _timestamp(self) -> str:
        """ISO8601 timestamp with timezone"""
        return datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds')
    
    def _should_log(self, level_num: int) -> bool:
        """Check if message should be logged based on level threshold."""
        return level_num >= self.level
    
    def _get_level_num(self, level: str) -> int:
        """Convert level name to numeric value."""
        level_map = {
            'DEBUG': LogLevel.DEBUG,
            'INFO': LogLevel.INFO,
            'WARNING': LogLevel.WARNING,
            'ERROR': LogLevel.ERROR,
            'CRITICAL': LogLevel.CRITICAL
        }
        return level_map.get(level, LogLevel.INFO)
    
    def _log(self, level: str, component: str, message: str, **fields):
        """
        Emit structured debug line immediately to stderr and save to buffer.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: Component name (plugin name or system component)
            message: Log message
            **fields: Additional context fields
        """
        level_num = self._get_level_num(level)
        
        # Skip if below threshold
        if not self._should_log(level_num):
            # Still buffer it for export
            self.log_buffer.append({
                "timestamp": self._timestamp(),
                "level": level,
                "level_num": level_num,
                "component": component,
                "message": message,
                "fields": {k: v for k, v in fields.items() if v is not None}
            })
            return
        ts = self._timestamp()
        
        # Always save to buffer (regardless of debug mode)
        log_entry = {
            "timestamp": ts,
            "level": level,
            "component": component,
            "message": message,
            "fields": {k: v for k, v in fields.items() if v is not None}
        }
        self.log_buffer.append(log_entry)
        
        # Write to MongoDB diagnostics if configured
        if self._diagnostics_logger is not None:
            try:
                self._diagnostics_logger.log(
                    level, 
                    component, 
                    message, 
                    execution_id=self._execution_id,
                    **fields
                )
            except Exception:
                pass  # Don't let diagnostics failures break the app
        
        # Only print to stderr if debug mode is enabled
        if not self.enabled:
            return
        
        context = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
        
        if context:
            line = f"{ts}  {level:5s}  {component:20s} [{context}] {message}"
        else:
            line = f"{ts}  {level:5s}  {component:20s} {message}"
        
        print(line, file=sys.stderr)
        sys.stderr.flush()  # Force immediate output
    
    def debug(self, component: str, message: str, **fields):
        """DEBUG level - Detailed diagnostic information"""
        self._log("DEBUG", component, message, **fields)
    
    def info(self, component: str, message: str, **fields):
        """INFO level - Confirmation that things are working as expected"""
        self._log("INFO", component, message, **fields)
    
    def warning(self, component: str, message: str, **fields):
        """WARNING level - An indication that something unexpected happened"""
        self._log("WARNING", component, message, **fields)
    
    def warn(self, component: str, message: str, **fields):
        """WARN level - Alias for warning() (deprecated, use warning())"""
        self.warning(component, message, **fields)
    
    def error(self, component: str, message: str, **fields):
        """ERROR level - Due to a more serious problem, software cannot perform function"""
        self._log("ERROR", component, message, **fields)
    
    def critical(self, component: str, message: str, **fields):
        """CRITICAL level - A serious error indicating the program may be unable to continue"""
        self._log("CRITICAL", component, message, **fields)
    
    def get_logs(self) -> List[Dict[str, Any]]:
        """Get all collected logs"""
        return self.log_buffer
    
    def export_logs(self, filepath: Path) -> None:
        """
        Export all collected logs to a JSON file.
        
        Args:
            filepath: Path to save the log file
        """
        # Create parent directory if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare export data with metadata
        export_data = {
            "_metadata": {
                "type": "debug_log",
                "total_entries": len(self.log_buffer),
                "debug_mode_was_enabled": self.enabled,
                "exported_at": datetime.now(timezone.utc).astimezone().isoformat()
            },
            "logs": self.log_buffer
        }
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def clear_logs(self) -> None:
        """Clear log buffer"""
        self.log_buffer.clear()
    
    def flush_diagnostics(self) -> None:
        """Flush diagnostics buffer to MongoDB"""
        if self._diagnostics_logger is not None:
            try:
                self._diagnostics_logger.flush()
            except Exception:
                pass


# Global instance
_debugger: Optional[DebugSystem] = None


def init_debugger(enabled: bool = False, level: str = None) -> DebugSystem:
    """
    Initialize global debug system.
    
    Args:
        enabled: Whether debug mode is enabled (legacy, use level instead)
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Initialized debugger instance
    """
    global _debugger
    
    # Convert level string to numeric
    level_num = None
    if level:
        level_map = {
            'DEBUG': LogLevel.DEBUG,
            'INFO': LogLevel.INFO,
            'WARNING': LogLevel.WARNING,
            'WARN': LogLevel.WARNING,  # Alias
            'ERROR': LogLevel.ERROR,
            'CRITICAL': LogLevel.CRITICAL
        }
        level_num = level_map.get(level.upper(), LogLevel.INFO)
    
    _debugger = DebugSystem(enabled=enabled, level=level_num)
    return _debugger


def get_debugger() -> DebugSystem:
    """
    Get global debugger instance.
    
    Returns:
        Debugger instance (creates disabled instance if not initialized)
    """
    global _debugger
    if _debugger is None:
        _debugger = DebugSystem(enabled=False)
    return _debugger


# Type alias for cleaner imports
Debugger = DebugSystem
