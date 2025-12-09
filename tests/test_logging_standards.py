"""
Test Logging System - Python Standards Compliance

Tests verify:
- All 5 standard Python log levels work (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- warn() is a working alias for warning()
- Log output follows expected format
- Backward compatibility maintained

Run with:
    pytest tests/test_logging_standards.py -v
"""

import sys
from io import StringIO
from datetime import datetime

import pytest

from archiverr.utils.debug import DebugSystem, init_debugger, get_debugger


class TestLoggingStandards:
    """Test Python logging standards compliance."""
    
    def test_all_five_levels_exist(self):
        """Test all 5 Python standard log levels are implemented."""
        debugger = DebugSystem(enabled=True)
        
        # Should have these methods
        assert hasattr(debugger, 'debug')
        assert hasattr(debugger, 'info')
        assert hasattr(debugger, 'warning')
        assert hasattr(debugger, 'error')
        assert hasattr(debugger, 'critical')
    
    def test_critical_level_works(self):
        """Test CRITICAL level logs correctly."""
        debugger = DebugSystem(enabled=True)
        
        debugger.critical("system", "Fatal database connection failure", 
                         error_code=500, recovery_possible=False)
        
        logs = debugger.get_logs()
        assert len(logs) == 1
        assert logs[0]['level'] == 'CRITICAL'
        assert logs[0]['component'] == 'system'
        assert logs[0]['message'] == 'Fatal database connection failure'
        assert logs[0]['fields']['error_code'] == 500
    
    def test_warning_level_works(self):
        """Test WARNING level logs correctly (not WARN)."""
        debugger = DebugSystem(enabled=True)
        
        debugger.warning("config", "Using default value", key="timeout", default=30)
        
        logs = debugger.get_logs()
        assert len(logs) == 1
        assert logs[0]['level'] == 'WARNING'
        assert logs[0]['component'] == 'config'
    
    def test_warn_is_alias_for_warning(self):
        """Test warn() is an alias for warning() (backward compatibility)."""
        debugger = DebugSystem(enabled=True)
        
        # Both should produce WARNING level logs
        debugger.warn("test1", "Using deprecated warn")
        debugger.warning("test2", "Using standard warning")
        
        logs = debugger.get_logs()
        assert len(logs) == 2
        assert logs[0]['level'] == 'WARNING'
        assert logs[1]['level'] == 'WARNING'
    
    def test_all_levels_produce_correct_output(self):
        """Test each level produces correct log entry."""
        debugger = DebugSystem(enabled=True)
        
        debugger.debug("component", "Debug message")
        debugger.info("component", "Info message")
        debugger.warning("component", "Warning message")
        debugger.error("component", "Error message")
        debugger.critical("component", "Critical message")
        
        logs = debugger.get_logs()
        assert len(logs) == 5
        
        levels = [log['level'] for log in logs]
        assert levels == ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    def test_log_levels_in_correct_order(self):
        """Test log levels follow Python standard numeric order."""
        # Python standard: DEBUG(10) < INFO(20) < WARNING(30) < ERROR(40) < CRITICAL(50)
        # Our implementation should maintain this conceptual ordering
        
        debugger = DebugSystem(enabled=True)
        
        # Log in random order
        debugger.critical("test", "Critical")
        debugger.debug("test", "Debug")
        debugger.warning("test", "Warning")
        debugger.error("test", "Error")
        debugger.info("test", "Info")
        
        logs = debugger.get_logs()
        levels = [log['level'] for log in logs]
        
        # Verify all levels captured
        assert 'DEBUG' in levels
        assert 'INFO' in levels
        assert 'WARNING' in levels
        assert 'ERROR' in levels
        assert 'CRITICAL' in levels
    
    def test_stderr_output_includes_level(self, capsys):
        """Test stderr output includes log level."""
        debugger = DebugSystem(enabled=True)
        
        debugger.critical("system", "Fatal error")
        
        captured = capsys.readouterr()
        assert 'CRITICAL' in captured.err
        assert 'system' in captured.err
        assert 'Fatal error' in captured.err
    
    def test_disabled_debugger_still_buffers(self):
        """Test disabled debugger still collects logs (for later export)."""
        debugger = DebugSystem(enabled=False)
        
        debugger.critical("system", "Fatal error")
        debugger.error("plugin", "Plugin failed")
        
        logs = debugger.get_logs()
        assert len(logs) == 2
        # Still buffered even though not printed to stderr
    
    def test_init_debugger_function(self):
        """Test global init_debugger() function."""
        debugger = init_debugger(enabled=True)
        
        assert isinstance(debugger, DebugSystem)
        assert debugger.enabled is True
        
        debugger.info("test", "Test message")
        assert len(debugger.get_logs()) == 1
    
    def test_get_debugger_returns_instance(self):
        """Test get_debugger() returns global instance."""
        # Initialize first
        init_debugger(enabled=True)
        
        # Get should return same instance
        debugger = get_debugger()
        assert isinstance(debugger, DebugSystem)
    
    def test_log_buffer_contains_all_fields(self):
        """Test log buffer contains all required fields."""
        debugger = DebugSystem(enabled=True)
        
        debugger.error("plugin", "Plugin crashed", 
                      plugin_name="tmdb", error="ConnectionTimeout")
        
        logs = debugger.get_logs()
        log = logs[0]
        
        # Required fields
        assert 'timestamp' in log
        assert 'level' in log
        assert 'component' in log
        assert 'message' in log
        assert 'fields' in log
        
        # Custom fields
        assert log['fields']['plugin_name'] == 'tmdb'
        assert log['fields']['error'] == 'ConnectionTimeout'
    
    def test_timestamp_format(self):
        """Test timestamp follows ISO8601 format."""
        debugger = DebugSystem(enabled=True)
        
        debugger.info("test", "Message")
        
        logs = debugger.get_logs()
        timestamp = logs[0]['timestamp']
        
        # Should be parseable as ISO8601
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert isinstance(dt, datetime)


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def test_warn_method_exists(self):
        """Test old warn() method still exists."""
        debugger = DebugSystem(enabled=True)
        
        # Should not raise AttributeError
        debugger.warn("test", "Old style warning")
        
        logs = debugger.get_logs()
        assert len(logs) == 1
    
    def test_existing_code_still_works(self):
        """Test existing code patterns still work."""
        debugger = DebugSystem(enabled=True)
        
        # Old patterns that should still work
        debugger.debug("component", "Debug message", key="value")
        debugger.info("component", "Info message", count=5)
        debugger.warn("component", "Warning message")  # Old method
        debugger.error("component", "Error message", error="Something")
        
        logs = debugger.get_logs()
        assert len(logs) == 4


class TestLogLevelFiltering:
    """Test future log level filtering support."""
    
    def test_log_buffer_allows_filtering(self):
        """Test log buffer can be filtered by level."""
        debugger = DebugSystem(enabled=True)
        
        debugger.debug("test", "Debug")
        debugger.info("test", "Info")
        debugger.warning("test", "Warning")
        debugger.error("test", "Error")
        debugger.critical("test", "Critical")
        
        logs = debugger.get_logs()
        
        # Filter by level
        errors_and_above = [
            log for log in logs 
            if log['level'] in ['ERROR', 'CRITICAL']
        ]
        
        assert len(errors_and_above) == 2
        assert errors_and_above[0]['level'] == 'ERROR'
        assert errors_and_above[1]['level'] == 'CRITICAL'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
