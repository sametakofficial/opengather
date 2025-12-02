"""
Unit tests for Plugin SDK components.

Tests:
- PluginResult: Factory methods, serialization, timing
- PluginManifest: Validation, properties
"""

import pytest
from datetime import datetime, timedelta

from archiverr.core.plugins.sdk import (
    PluginResult,
    PluginManifest,
    ExecutionContext,
    BasePlugin,
    OutputPlugin,
    InputPlugin,
)


class TestPluginResult:
    """Tests for PluginResult class"""
    
    def test_success_result_factory(self):
        """Test PluginResult.success_result() factory method"""
        result = PluginResult.success_result(
            data={"movie": {"title": "Test Movie", "year": 2024}}
        )
        
        assert result.success is True
        assert result.error is None
        assert result.data["movie"]["title"] == "Test Movie"
        assert result.data["movie"]["year"] == 2024
    
    def test_success_result_with_metadata(self):
        """Test PluginResult.success_result() with metadata"""
        result = PluginResult.success_result(
            data={"show": {"name": "Test Show"}},
            metadata={"api_calls": 3, "cache_hits": 1}
        )
        
        assert result.success is True
        assert result.metadata["api_calls"] == 3
        assert result.metadata["cache_hits"] == 1
    
    def test_error_result_factory(self):
        """Test PluginResult.error_result() factory method"""
        result = PluginResult.error_result("API connection failed")
        
        assert result.success is False
        assert result.error == "API connection failed"
        assert result.data == {}
    
    def test_error_result_with_started_at(self):
        """Test PluginResult.error_result() with custom start time"""
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        result = PluginResult.error_result("Timeout", started_at=start_time)
        
        assert result.success is False
        assert result.started_at == start_time
        assert result.finished_at >= start_time
    
    def test_duration_ms_calculation(self):
        """Test duration_ms property calculation"""
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 1, 500000)  # 1.5 seconds later
        
        result = PluginResult(
            success=True,
            data={},
            started_at=start,
            finished_at=end
        )
        
        assert result.duration_ms == 1500
    
    def test_duration_ms_zero(self):
        """Test duration_ms when start and finish are same"""
        now = datetime.now()
        result = PluginResult(
            success=True,
            data={},
            started_at=now,
            finished_at=now
        )
        
        assert result.duration_ms == 0
    
    def test_to_status_dict(self):
        """Test to_status_dict() method"""
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 2)
        
        result = PluginResult(
            success=True,
            data={"movie": {}},
            started_at=start,
            finished_at=end
        )
        
        status = result.to_status_dict()
        
        assert status["success"] is True
        assert status["error"] is None
        assert status["started_at"] == "2024-01-01T12:00:00"
        assert status["finished_at"] == "2024-01-01T12:00:02"
        assert status["duration_ms"] == 2000
    
    def test_to_response_dict(self):
        """Test to_response_dict() method - full API response format"""
        result = PluginResult.success_result(
            data={"movie": {"title": "Test"}, "extras": {"credits": []}}
        )
        
        response = result.to_response_dict()
        
        assert "status" in response
        assert response["status"]["success"] is True
        assert response["movie"]["title"] == "Test"
        assert response["extras"]["credits"] == []
    
    def test_to_response_dict_error(self):
        """Test to_response_dict() for error result"""
        result = PluginResult.error_result("Not found")
        
        response = result.to_response_dict()
        
        assert response["status"]["success"] is False
        assert response["status"]["error"] == "Not found"


class TestPluginManifest:
    """Tests for PluginManifest validation"""
    
    def test_valid_output_manifest(self):
        """Test valid output plugin manifest"""
        manifest = PluginManifest(
            name="tmdb",
            version="1.0.0",
            category="output",
            description="TMDb metadata plugin"
        )
        
        assert manifest.name == "tmdb"
        assert manifest.version == "1.0.0"
        assert manifest.is_output is True
        assert manifest.is_input is False
    
    def test_valid_input_manifest(self):
        """Test valid input plugin manifest"""
        manifest = PluginManifest(
            name="scanner",
            version="1.0.0",
            category="input"
        )
        
        assert manifest.name == "scanner"
        assert manifest.is_input is True
        assert manifest.is_output is False
    
    def test_manifest_with_dependencies(self):
        """Test manifest with depends_on and expects"""
        manifest = PluginManifest(
            name="tmdb",
            version="1.0.0",
            category="output",
            depends_on=["renamer"],
            expects=["renamer.parsed"]
        )
        
        assert manifest.depends_on == ["renamer"]
        assert manifest.expects == ["renamer.parsed"]
    
    def test_manifest_rejects_invalid_category(self):
        """Test that invalid category raises validation error"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            PluginManifest(
                name="test",
                version="1.0.0",
                category="invalid"
            )
    
    def test_manifest_requires_name(self):
        """Test that name is required"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            PluginManifest(
                version="1.0.0",
                category="output"
            )
    
    def test_manifest_requires_version(self):
        """Test that version is required"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            PluginManifest(
                name="test",
                category="output"
            )
    
    def test_manifest_default_values(self):
        """Test that optional fields have correct defaults"""
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            category="output"
        )
        
        assert manifest.depends_on == []
        assert manifest.expects == []
        assert manifest.categories == []
        assert manifest.capabilities == []
        assert manifest.provides == []
        assert manifest.hooks == []
        assert manifest.config_schema is None
    
    def test_manifest_with_config_schema(self):
        """Test manifest with config_schema"""
        manifest = PluginManifest(
            name="tmdb",
            version="1.0.0",
            category="output",
            config_schema={
                "api_key": {"type": "string", "required": True},
                "language": {"type": "string", "default": "en-US"}
            }
        )
        
        assert manifest.config_schema is not None
        assert manifest.config_schema["api_key"]["required"] is True


class TestExecutionContext:
    """Tests for ExecutionContext"""
    
    def test_context_creation(self):
        """Test ExecutionContext can be created with defaults"""
        context = ExecutionContext()
        
        assert context.execution_id == ""
        assert context.match_index == 0
        assert context.total_matches == 0
        assert context.dry_run is True
    
    def test_context_with_values(self):
        """Test ExecutionContext with custom values"""
        context = ExecutionContext(
            execution_id="exec-123",
            match_index=5,
            total_matches=10,
            dry_run=False,
            debug=True
        )
        
        assert context.execution_id == "exec-123"
        assert context.match_index == 5
        assert context.total_matches == 10
        assert context.dry_run is False
        assert context.debug is True
    
    def test_get_plugin_result(self):
        """Test get_plugin_result() method"""
        context = ExecutionContext(
            previous_results={
                "renamer": {"parsed": {"movie": {"name": "Test"}}}
            }
        )
        
        result = context.get_plugin_result("renamer")
        assert result is not None
        assert result["parsed"]["movie"]["name"] == "Test"
        
        # Non-existent plugin
        assert context.get_plugin_result("nonexistent") is None
    
    def test_has_plugin_result(self):
        """Test has_plugin_result() method"""
        context = ExecutionContext(
            previous_results={"renamer": {}}
        )
        
        assert context.has_plugin_result("renamer") is True
        assert context.has_plugin_result("tmdb") is False
    
    def test_emit_task_without_task_manager(self):
        """Test emit_task() returns None when task_manager not available"""
        context = ExecutionContext()
        
        result = context.emit_task({"type": "print", "template": "test"})
        assert result is None
    
    def test_emit_progress_without_event_bus(self):
        """Test emit_progress() doesn't crash when event_bus not available"""
        context = ExecutionContext()
        
        # Should not raise
        context.emit_progress(50.0, "Processing...")


class TestBasePlugin:
    """Tests for BasePlugin abstract class"""
    
    def test_plugin_requires_execute(self):
        """Test that BasePlugin cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BasePlugin({})
    
    def test_output_plugin_initialization(self):
        """Test OutputPlugin can be subclassed"""
        class TestPlugin(OutputPlugin):
            def execute(self, match_data):
                return {"status": {"success": True}}
        
        plugin = TestPlugin({"key": "value"})
        assert plugin.config == {"key": "value"}
        assert plugin.category == "output"
    
    def test_input_plugin_initialization(self):
        """Test InputPlugin can be subclassed"""
        class TestPlugin(InputPlugin):
            def execute(self):
                return []
        
        plugin = TestPlugin({})
        assert plugin.category == "input"
    
    def test_set_context(self):
        """Test set_context() method"""
        class TestPlugin(OutputPlugin):
            def execute(self, match_data):
                return {}
        
        plugin = TestPlugin({})
        context = ExecutionContext(execution_id="test-123")
        
        plugin.set_context(context)
        
        assert plugin.context is not None
        assert plugin.context.execution_id == "test-123"
    
    def test_log_methods_without_context(self):
        """Test log methods don't crash without context"""
        class TestPlugin(OutputPlugin):
            def execute(self, match_data):
                return {}
        
        plugin = TestPlugin({})
        plugin.name = "test"
        
        # Should not raise even without context
        plugin.debug("test message")
        plugin.info("test message")
        plugin.warn("test message")
        plugin.error("test message")
    
    def test_emit_task_without_context(self):
        """Test emit_task() returns None without context"""
        class TestPlugin(OutputPlugin):
            def execute(self, match_data):
                return {}
        
        plugin = TestPlugin({})
        result = plugin.emit_task({"type": "print", "template": "test"})
        
        assert result is None
    
    def test_get_previous_result_without_context(self):
        """Test get_previous_result() returns None without context"""
        class TestPlugin(OutputPlugin):
            def execute(self, match_data):
                return {}
        
        plugin = TestPlugin({})
        result = plugin.get_previous_result("renamer")
        
        assert result is None
