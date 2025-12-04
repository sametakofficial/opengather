"""
Tests for ValidationResult and ValidationError

Session 11 - Phase 7
"""

import pytest
from archiverr.core.validation.result import (
    ValidationLevel,
    ValidationError,
    ValidationResult,
)


class TestValidationLevel:
    """Test ValidationLevel enum."""
    
    def test_level_values(self):
        """Test all level values exist."""
        assert ValidationLevel.FATAL.value == "fatal"
        assert ValidationLevel.ERROR.value == "error"
        assert ValidationLevel.WARNING.value == "warning"
        assert ValidationLevel.INFO.value == "info"


class TestValidationError:
    """Test ValidationError dataclass."""
    
    def test_basic_error(self):
        """Test creating basic error."""
        error = ValidationError(
            code="E001",
            message="Test error"
        )
        assert error.code == "E001"
        assert error.message == "Test error"
        assert error.level == ValidationLevel.ERROR
        assert error.path is None
    
    def test_error_with_path(self):
        """Test error with path."""
        error = ValidationError(
            code="E002",
            message="Missing field",
            path="plugins.tmdb.api_key"
        )
        assert error.path == "plugins.tmdb.api_key"
    
    def test_error_str_without_path(self):
        """Test string representation without path."""
        error = ValidationError(code="E001", message="Test")
        assert str(error) == "[E001] Test"
    
    def test_error_str_with_path(self):
        """Test string representation with path."""
        error = ValidationError(
            code="E002",
            message="Missing field",
            path="plugins.tmdb"
        )
        assert str(error) == "[E002] plugins.tmdb: Missing field"
    
    def test_error_to_dict(self):
        """Test conversion to dict."""
        error = ValidationError(
            code="E001",
            message="Test",
            path="config.options",
            context={"key": "value"}
        )
        d = error.to_dict()
        assert d["code"] == "E001"
        assert d["message"] == "Test"
        assert d["path"] == "config.options"
        assert d["context"] == {"key": "value"}


class TestValidationResult:
    """Test ValidationResult dataclass."""
    
    def test_ok_result(self):
        """Test creating OK result."""
        result = ValidationResult.ok()
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_fail_result(self):
        """Test creating failed result."""
        result = ValidationResult.fail("E001", "Test error")
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "E001"
    
    def test_bool_true(self):
        """Test boolean context - valid result."""
        result = ValidationResult.ok()
        assert bool(result) is True
        if result:
            pass  # Should execute
    
    def test_bool_false(self):
        """Test boolean context - invalid result."""
        result = ValidationResult.fail("E001", "Error")
        assert bool(result) is False
    
    def test_add_error(self):
        """Test adding error."""
        result = ValidationResult.ok()
        result.add_error("E001", "Test error", path="test.path")
        
        assert result.valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "E001"
        assert result.errors[0].path == "test.path"
    
    def test_add_warning(self):
        """Test adding warning."""
        result = ValidationResult.ok()
        result.add_warning("W001", "Test warning")
        
        assert result.valid is True  # Warnings don't affect validity
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "W001"
    
    def test_add_fatal_error(self):
        """Test adding fatal error."""
        result = ValidationResult.ok()
        result.add_error("E015", "Circular dep", level=ValidationLevel.FATAL)
        
        assert result.valid is False
        assert result.has_fatal() is True
    
    def test_merge_results(self):
        """Test merging two results."""
        r1 = ValidationResult.ok()
        r1.add_warning("W001", "Warning 1")
        
        r2 = ValidationResult.fail("E001", "Error 1")
        
        r1.merge(r2)
        
        assert r1.valid is False
        assert len(r1.errors) == 1
        assert len(r1.warnings) == 1
    
    def test_merge_chaining(self):
        """Test merge returns self for chaining."""
        r1 = ValidationResult.ok()
        r2 = ValidationResult.ok()
        r3 = ValidationResult.ok()
        
        result = r1.merge(r2).merge(r3)
        assert result is r1
    
    def test_error_count(self):
        """Test error count."""
        result = ValidationResult.ok()
        result.add_error("E001", "Error 1")
        result.add_error("E002", "Error 2")
        result.add_warning("W001", "Warning 1")
        
        assert result.error_count() == 2
        assert result.warning_count() == 1
    
    def test_format_errors(self):
        """Test formatting errors."""
        result = ValidationResult.ok()
        result.add_error("E001", "Error 1")
        result.add_error("E002", "Error 2", path="test.path")
        
        formatted = result.format_errors()
        assert len(formatted) == 2
        assert "[E001] Error 1" in formatted
        assert "[E002] test.path: Error 2" in formatted
    
    def test_to_dict(self):
        """Test conversion to dict."""
        result = ValidationResult.ok()
        result.add_error("E001", "Error")
        result.add_warning("W001", "Warning")
        
        d = result.to_dict()
        assert d["valid"] is False
        assert d["error_count"] == 1
        assert d["warning_count"] == 1
        assert len(d["errors"]) == 1
        assert len(d["warnings"]) == 1
