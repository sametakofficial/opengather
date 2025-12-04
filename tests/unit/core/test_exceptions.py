"""
Unit tests for core/exceptions.py

Session 11 - Phase 4: Exception hierarchy tests.
"""

import pytest
from archiverr.core.exceptions import (
    ArchiverrError,
    CriticalError,
    StageError,
    PluginError,
    ValidationError,
    ConfigError,
    ManifestError,
    DependencyError,
    RequiresError,
    StateError,
)


class TestArchiverrError:
    """Test base exception class"""
    
    def test_basic_creation(self):
        err = ArchiverrError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.context == {}
    
    def test_with_context(self):
        err = ArchiverrError("Failed", {"key": "value", "count": 42})
        assert "key=value" in str(err)
        assert "count=42" in str(err)
        assert err.context["key"] == "value"
    
    def test_to_dict(self):
        err = ArchiverrError("Test error", {"foo": "bar"})
        d = err.to_dict()
        
        assert d["error"] == "ArchiverrError"
        assert d["message"] == "Test error"
        assert d["context"]["foo"] == "bar"


class TestCriticalError:
    """Test critical (run-stopping) errors"""
    
    def test_is_archiverr_error(self):
        err = CriticalError("Config not found")
        assert isinstance(err, ArchiverrError)
    
    def test_with_context(self):
        err = CriticalError("Database connection failed", {"uri": "mongodb://..."})
        assert "Database connection failed" in str(err)
        assert err.context["uri"] == "mongodb://..."
    
    def test_to_dict(self):
        err = CriticalError("Critical failure")
        d = err.to_dict()
        assert d["error"] == "CriticalError"


class TestStageError:
    """Test stage-level errors"""
    
    def test_is_archiverr_error(self):
        err = StageError("Stage failed")
        assert isinstance(err, ArchiverrError)
    
    def test_with_stage(self):
        err = StageError("All plugins failed", stage="input")
        assert err.stage == "input"
        assert err.context["stage"] == "input"
    
    def test_with_context_and_stage(self):
        err = StageError(
            "Stage timeout",
            stage="data",
            context={"timeout_ms": 5000}
        )
        assert err.stage == "data"
        assert err.context["stage"] == "data"
        assert err.context["timeout_ms"] == 5000
    
    def test_state_error_alias(self):
        """StateError should be alias for StageError"""
        assert StateError is StageError


class TestPluginError:
    """Test plugin-level errors"""
    
    def test_is_archiverr_error(self):
        err = PluginError("Plugin crashed")
        assert isinstance(err, ArchiverrError)
    
    def test_with_plugin_name(self):
        err = PluginError("API timeout", plugin_name="tmdb")
        assert err.plugin_name == "tmdb"
        assert err.context["plugin"] == "tmdb"
    
    def test_with_context(self):
        err = PluginError(
            "Parse error",
            plugin_name="renamer",
            context={"input": "invalid.mkv", "pattern": ".*"}
        )
        assert err.plugin_name == "renamer"
        assert err.context["input"] == "invalid.mkv"


class TestValidationError:
    """Test validation errors"""
    
    def test_is_archiverr_error(self):
        err = ValidationError("Invalid config")
        assert isinstance(err, ArchiverrError)
    
    def test_with_errors_list(self):
        errors = ["Field 'api_key' required", "Field 'timeout' must be integer"]
        err = ValidationError("Config validation failed", errors=errors)
        assert err.errors == errors
        assert err.context["validation_errors"] == errors
    
    def test_config_error_subclass(self):
        err = ConfigError("Missing required field")
        assert isinstance(err, ValidationError)
        assert isinstance(err, ArchiverrError)
    
    def test_manifest_error_subclass(self):
        err = ManifestError("Invalid manifest structure")
        assert isinstance(err, ValidationError)
        assert isinstance(err, ArchiverrError)


class TestDependencyError:
    """Test dependency resolution errors"""
    
    def test_is_archiverr_error(self):
        err = DependencyError("Circular dependency")
        assert isinstance(err, ArchiverrError)
    
    def test_with_context(self):
        err = DependencyError(
            "Circular dependency detected",
            {"cycle": ["a", "b", "a"]}
        )
        assert err.context["cycle"] == ["a", "b", "a"]


class TestRequiresError:
    """Test plugin requires errors"""
    
    def test_is_plugin_error(self):
        err = RequiresError("Missing required data")
        assert isinstance(err, PluginError)
        assert isinstance(err, ArchiverrError)
    
    def test_with_requires_info(self):
        err = RequiresError(
            "Requires not satisfied",
            plugin_name="tmdb",
            context={"requires": ["renamer.parsed"], "missing": ["renamer.parsed"]}
        )
        assert err.plugin_name == "tmdb"
        assert "renamer.parsed" in err.context["missing"]


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy"""
    
    def test_all_inherit_from_base(self):
        exceptions = [
            CriticalError("test"),
            StageError("test"),
            PluginError("test"),
            ValidationError("test"),
            ConfigError("test"),
            ManifestError("test"),
            DependencyError("test"),
            RequiresError("test"),
        ]
        
        for exc in exceptions:
            assert isinstance(exc, ArchiverrError)
            assert isinstance(exc, Exception)
    
    def test_can_catch_by_base(self):
        """All exceptions catchable by ArchiverrError"""
        for exc_class in [CriticalError, StageError, PluginError, ValidationError]:
            try:
                raise exc_class("test")
            except ArchiverrError as e:
                assert e.message == "test"
