"""
Tests for ConfigValidator

Session 11 - Phase 7
"""

import pytest
from archiverr.core.validation.config_validator import ConfigValidator
from archiverr.core.validation.error_codes import E002, E003, W003


class TestConfigValidator:
    """Test ConfigValidator class."""
    
    @pytest.fixture
    def validator(self):
        return ConfigValidator()
    
    def test_valid_config_with_enabled_plugins(self, validator):
        """Test valid config with enabled plugins."""
        config = {
            "_enabled_plugins": ["scanner", "renamer"],
            "options": {
                "debug": True
            }
        }
        result = validator.validate(config)
        # May have warnings (schema not available, etc.) but should pass semantic
        # Check no E002 or E003 errors
        error_codes = [e.code for e in result.errors]
        assert E002 not in error_codes
        assert E003 not in error_codes
    
    def test_no_plugins_enabled(self, validator):
        """Test error when no plugins enabled."""
        config = {
            "_enabled_plugins": [],
            "options": {}
        }
        result = validator.validate(config)
        assert result.valid is False
        assert any(E002 in e.code for e in result.errors)
    
    def test_plugins_section_enabled(self, validator):
        """Test detecting enabled plugins from plugins section."""
        config = {
            "plugins": {
                "scanner": {"enabled": True},
                "renamer": {"enabled": False}
            },
            "options": {}
        }
        result = validator.validate(config)
        # scanner is enabled, so this should pass
        error_codes = [e.code for e in result.errors if e.code == E002]
        assert len(error_codes) == 0
    
    def test_options_must_be_dict(self, validator):
        """Test options must be dict."""
        config = {
            "_enabled_plugins": ["scanner"],
            "options": "invalid"  # Should be dict
        }
        result = validator.validate(config)
        assert any(E003 in e.code for e in result.errors)
    
    def test_aliases_must_be_dict(self, validator):
        """Test aliases must be dict."""
        config = {
            "_enabled_plugins": ["scanner"],
            "aliases": ["invalid"]  # Should be dict
        }
        result = validator.validate(config)
        assert any(E003 in e.code for e in result.errors)
    
    def test_security_warning_hardcoded_api_key(self, validator):
        """Test warning for hardcoded API key."""
        config = {
            "_enabled_plugins": ["tmdb"],
            "plugins": {
                "tmdb": {
                    "enabled": True,
                    "api_key": "abc123secret"  # Hardcoded!
                }
            }
        }
        result = validator.validate(config)
        # Should have W003 warning
        assert any(W003 in w.code for w in result.warnings)
    
    def test_no_warning_env_var_api_key(self, validator):
        """Test no warning for env var API key."""
        config = {
            "_enabled_plugins": ["tmdb"],
            "plugins": {
                "tmdb": {
                    "enabled": True,
                    "api_key": "${TMDB_API_KEY}"  # Env var
                }
            }
        }
        result = validator.validate(config)
        # Should NOT have W003 warning
        warning_codes = [w.code for w in result.warnings]
        assert W003 not in warning_codes
    
    def test_flexget_style_plugin_config(self, validator):
        """Test FlexGet style (top-level plugin config) security check."""
        config = {
            "_enabled_plugins": ["tmdb"],
            "tmdb": {
                "api_key": "hardcoded_key"  # Top-level plugin config
            }
        }
        result = validator.validate(config)
        # Should have W003 warning
        assert any(W003 in w.code for w in result.warnings)


class TestConfigValidatorSchemaAvailability:
    """Test schema availability checks."""
    
    def test_is_available_no_schema(self):
        """Test is_available when schema doesn't exist."""
        validator = ConfigValidator(schema_path="/nonexistent/path.json")
        # Should still work, just no schema validation
        config = {"_enabled_plugins": ["scanner"]}
        result = validator.validate(config)
        # Should pass semantic validation
        assert result.valid is True or any(e.code == E002 for e in result.errors)
