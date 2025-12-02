"""
Unit tests for Plugin Config Validators.

Tests the ConfigValidator class that validates plugin config
against schemas defined in manifest.yml.
"""

import pytest

from archiverr.core.plugins.sdk.validators import (
    ConfigValidator,
    ValidationResult,
    ValidationError,
    validate_plugin_config,
)


class TestConfigValidator:
    """Tests for ConfigValidator class"""
    
    @pytest.fixture
    def validator(self):
        return ConfigValidator()
    
    def test_empty_schema_passes(self, validator):
        """No schema = no validation = always valid"""
        config = {"api_key": "test123", "timeout": 30}
        result = validator.validate(config, None, "test")
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_required_field_missing(self, validator):
        """Required field must be present"""
        schema = {
            "api_key": {"type": "string", "required": True}
        }
        config = {}
        
        result = validator.validate(config, schema, "test")
        
        assert result.valid is False
        assert len(result.errors) == 1
        assert "Required field is missing" in str(result.errors[0])
    
    def test_required_field_present(self, validator):
        """Required field present = valid"""
        schema = {
            "api_key": {"type": "string", "required": True}
        }
        config = {"api_key": "my-api-key-123"}
        
        result = validator.validate(config, schema, "test")
        
        assert result.valid is True
    
    def test_default_value_applied(self, validator):
        """Default value applied when field missing"""
        schema = {
            "timeout": {"type": "integer", "default": 30}
        }
        config = {}
        
        result = validator.validate(config, schema, "test")
        
        assert result.valid is True
        assert result.config.get("timeout") == 30
    
    def test_type_validation_string(self, validator):
        """Type validation for string"""
        schema = {"name": {"type": "string"}}
        
        # Valid string
        result = validator.validate({"name": "test"}, schema, "test")
        assert result.valid is True
        
        # Invalid type
        result = validator.validate({"name": 123}, schema, "test")
        assert result.valid is False
        assert "Expected type 'string'" in str(result.errors[0])
    
    def test_type_validation_integer(self, validator):
        """Type validation for integer"""
        schema = {"timeout": {"type": "integer"}}
        
        # Valid integer
        result = validator.validate({"timeout": 30}, schema, "test")
        assert result.valid is True
        
        # Invalid type
        result = validator.validate({"timeout": "30"}, schema, "test")
        assert result.valid is False
    
    def test_type_validation_boolean(self, validator):
        """Type validation for boolean"""
        schema = {"enabled": {"type": "boolean"}}
        
        # Valid boolean
        result = validator.validate({"enabled": True}, schema, "test")
        assert result.valid is True
        
        # Invalid type
        result = validator.validate({"enabled": "true"}, schema, "test")
        assert result.valid is False
    
    def test_min_length_string(self, validator):
        """Minimum length validation for strings"""
        schema = {
            "api_key": {"type": "string", "min_length": 10}
        }
        
        # Too short
        result = validator.validate({"api_key": "short"}, schema, "test")
        assert result.valid is False
        assert "Minimum length is 10" in str(result.errors[0])
        
        # Valid length
        result = validator.validate({"api_key": "longenoughkey"}, schema, "test")
        assert result.valid is True
    
    def test_max_length_string(self, validator):
        """Maximum length validation for strings"""
        schema = {
            "name": {"type": "string", "max_length": 10}
        }
        
        # Too long
        result = validator.validate({"name": "this is too long"}, schema, "test")
        assert result.valid is False
        assert "Maximum length is 10" in str(result.errors[0])
        
        # Valid length
        result = validator.validate({"name": "short"}, schema, "test")
        assert result.valid is True
    
    def test_pattern_validation(self, validator):
        """Regex pattern validation"""
        schema = {
            "language": {"type": "string", "pattern": "^[a-z]{2}-[A-Z]{2}$"}
        }
        
        # Valid pattern
        result = validator.validate({"language": "en-US"}, schema, "test")
        assert result.valid is True
        
        result = validator.validate({"language": "tr-TR"}, schema, "test")
        assert result.valid is True
        
        # Invalid pattern
        result = validator.validate({"language": "english"}, schema, "test")
        assert result.valid is False
        assert "Does not match required pattern" in str(result.errors[0])
    
    def test_not_contains_validation(self, validator):
        """Forbidden characters validation"""
        schema = {
            "api_key": {
                "type": "string",
                "not_contains": ['"', "'", " "]
            }
        }
        
        # Valid (no forbidden chars)
        result = validator.validate({"api_key": "abc123"}, schema, "test")
        assert result.valid is True
        
        # Contains quote
        result = validator.validate({"api_key": 'abc"123'}, schema, "test")
        assert result.valid is False
        assert 'Must not contain' in str(result.errors[0])
        
        # Contains space
        result = validator.validate({"api_key": "abc 123"}, schema, "test")
        assert result.valid is False
    
    def test_min_max_number(self, validator):
        """Numeric range validation"""
        schema = {
            "timeout": {"type": "integer", "min": 1, "max": 120}
        }
        
        # Valid range
        result = validator.validate({"timeout": 30}, schema, "test")
        assert result.valid is True
        
        # Below min
        result = validator.validate({"timeout": 0}, schema, "test")
        assert result.valid is False
        assert "Minimum value is 1" in str(result.errors[0])
        
        # Above max
        result = validator.validate({"timeout": 999}, schema, "test")
        assert result.valid is False
        assert "Maximum value is 120" in str(result.errors[0])
    
    def test_enum_validation(self, validator):
        """Enum (allowed values) validation"""
        schema = {
            "method": {"type": "string", "enum": ["GET", "POST", "PUT"]}
        }
        
        # Valid enum value
        result = validator.validate({"method": "GET"}, schema, "test")
        assert result.valid is True
        
        # Invalid enum value
        result = validator.validate({"method": "DELETE"}, schema, "test")
        assert result.valid is False
        assert "Must be one of" in str(result.errors[0])
    
    def test_list_min_length(self, validator):
        """List minimum length validation"""
        schema = {
            "targets": {"type": "list", "min_length": 1}
        }
        
        # Empty list
        result = validator.validate({"targets": []}, schema, "test")
        assert result.valid is False
        assert "Minimum items is 1" in str(result.errors[0])
        
        # Valid list
        result = validator.validate({"targets": ["/path/to/file"]}, schema, "test")
        assert result.valid is True
    
    def test_secret_field_hidden_in_errors(self, validator):
        """Secret fields should be hidden in error messages"""
        schema = {
            "api_key": {
                "type": "string",
                "min_length": 50,  # Will fail
                "secret": True
            }
        }
        config = {"api_key": "short-secret-key"}
        
        result = validator.validate(config, schema, "test")
        
        assert result.valid is False
        # Value should be hidden
        error_str = str(result.errors[0])
        assert "short-secret-key" not in error_str
        assert "***" in error_str or "got:" not in error_str
    
    def test_multiple_errors(self, validator):
        """Multiple validation errors collected"""
        schema = {
            "api_key": {"type": "string", "required": True},
            "timeout": {"type": "integer", "min": 1}
        }
        config = {"timeout": 0}  # Missing api_key, invalid timeout
        
        result = validator.validate(config, schema, "test")
        
        assert result.valid is False
        assert len(result.errors) == 2
    
    def test_extra_config_preserved(self, validator):
        """Config fields not in schema should be preserved"""
        schema = {"api_key": {"type": "string"}}
        config = {"api_key": "test", "extra_field": "value"}
        
        result = validator.validate(config, schema, "test")
        
        assert result.valid is True
        assert result.config.get("extra_field") == "value"
    
    def test_starts_with_validation(self, validator):
        """starts_with validation for strings"""
        schema = {
            "path": {"type": "string", "starts_with": "/"}
        }
        
        # Valid
        result = validator.validate({"path": "/home/user"}, schema, "test")
        assert result.valid is True
        
        # Invalid
        result = validator.validate({"path": "home/user"}, schema, "test")
        assert result.valid is False
        assert "Must start with '/'" in str(result.errors[0])
    
    def test_ends_with_validation(self, validator):
        """ends_with validation for strings"""
        schema = {
            "filename": {"type": "string", "ends_with": ".mkv"}
        }
        
        # Valid
        result = validator.validate({"filename": "movie.mkv"}, schema, "test")
        assert result.valid is True
        
        # Invalid
        result = validator.validate({"filename": "movie.avi"}, schema, "test")
        assert result.valid is False
        assert "Must end with '.mkv'" in str(result.errors[0])


class TestValidationConvenienceFunction:
    """Tests for validate_plugin_config convenience function"""
    
    def test_convenience_function(self):
        """Test the convenience function works"""
        schema = {"api_key": {"type": "string", "required": True}}
        config = {"api_key": "test123"}
        
        result = validate_plugin_config(config, schema, "myplugin")
        
        assert result.valid is True


class TestValidationResult:
    """Tests for ValidationResult class"""
    
    def test_bool_conversion(self):
        """ValidationResult should be truthy when valid"""
        valid_result = ValidationResult(valid=True)
        invalid_result = ValidationResult(valid=False)
        
        assert bool(valid_result) is True
        assert bool(invalid_result) is False
    
    def test_error_messages(self):
        """error_messages() should return list of strings"""
        result = ValidationResult(
            valid=False,
            errors=[
                ValidationError(field="test.api_key", message="Required"),
                ValidationError(field="test.timeout", message="Invalid")
            ]
        )
        
        messages = result.error_messages()
        
        assert len(messages) == 2
        assert "test.api_key" in messages[0]


class TestValidationError:
    """Tests for ValidationError class"""
    
    def test_str_without_value(self):
        """String representation without value"""
        error = ValidationError(field="test.api_key", message="Required field is missing")
        
        assert str(error) == "test.api_key: Required field is missing"
    
    def test_str_with_value(self):
        """String representation with value"""
        error = ValidationError(
            field="test.timeout",
            message="Minimum value is 1",
            value=0
        )
        
        assert "test.timeout" in str(error)
        assert "Minimum value is 1" in str(error)
        assert "0" in str(error)
    
    def test_long_value_truncated(self):
        """Long values should be truncated"""
        error = ValidationError(
            field="test.content",
            message="Invalid",
            value="a" * 100
        )
        
        error_str = str(error)
        assert "..." in error_str
        assert len(error_str) < 150


class TestRealWorldScenarios:
    """Integration tests with real-world plugin schemas"""
    
    def test_tmdb_config_validation(self):
        """Test TMDb-like config validation"""
        schema = {
            "api_key": {
                "type": "string",
                "required": True,
                "min_length": 10,
                "pattern": "^[a-zA-Z0-9_-]+$",
                "not_contains": ['"', "'", " "],
                "secret": True
            },
            "language": {
                "type": "string",
                "pattern": "^[a-z]{2}-[A-Z]{2}$",
                "default": "en-US"
            },
            "region": {
                "type": "string",
                "pattern": "^[A-Z]{2}$",
                "default": "TR"
            }
        }
        
        # Valid config
        valid_config = {
            "api_key": "abc123def456",
            "language": "tr-TR",
            "enabled": True
        }
        result = validate_plugin_config(valid_config, schema, "tmdb")
        assert result.valid is True
        assert result.config.get("region") == "TR"  # Default applied
        
        # Invalid API key (too short)
        invalid_config = {"api_key": "short"}
        result = validate_plugin_config(invalid_config, schema, "tmdb")
        assert result.valid is False
        
        # Invalid language format
        invalid_config = {"api_key": "abc123def456", "language": "english"}
        result = validate_plugin_config(invalid_config, schema, "tmdb")
        assert result.valid is False
    
    def test_scanner_config_validation(self):
        """Test scanner-like config validation"""
        schema = {
            "targets": {
                "type": "list",
                "required": True,
                "min_length": 1
            },
            "recursive": {
                "type": "boolean",
                "default": False
            }
        }
        
        # Valid config
        valid_config = {
            "targets": ["/path/to/movies"],
            "enabled": True
        }
        result = validate_plugin_config(valid_config, schema, "scanner")
        assert result.valid is True
        assert result.config.get("recursive") is False  # Default
        
        # Missing required targets
        invalid_config = {"enabled": True}
        result = validate_plugin_config(invalid_config, schema, "scanner")
        assert result.valid is False
        
        # Empty targets list
        invalid_config = {"targets": [], "enabled": True}
        result = validate_plugin_config(invalid_config, schema, "scanner")
        assert result.valid is False
    
    def test_ffprobe_config_validation(self):
        """Test ffprobe-like config validation"""
        schema = {
            "timeout": {
                "type": "integer",
                "min": 1,
                "max": 300,
                "default": 30
            }
        }
        
        # Valid config (uses default)
        result = validate_plugin_config({"enabled": True}, schema, "ffprobe")
        assert result.valid is True
        assert result.config.get("timeout") == 30
        
        # Valid custom timeout
        result = validate_plugin_config({"timeout": 60}, schema, "ffprobe")
        assert result.valid is True
        
        # Invalid timeout (too high)
        result = validate_plugin_config({"timeout": 999}, schema, "ffprobe")
        assert result.valid is False
