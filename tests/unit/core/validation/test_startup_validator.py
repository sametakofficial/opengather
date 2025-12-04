"""
Tests for StartupValidator

Session 11 - Phase 7
"""

import pytest
from archiverr.core.validation.startup_validator import (
    StartupValidator,
    validate_at_startup,
)
from archiverr.core.validation.error_codes import E015, W004


class TestStartupValidator:
    """Test StartupValidator class."""
    
    @pytest.fixture
    def validator(self):
        return StartupValidator()
    
    @pytest.fixture
    def valid_config(self):
        return {
            "_enabled_plugins": ["scanner", "renamer"],
            "options": {"debug": True}
        }
    
    @pytest.fixture
    def valid_manifests(self):
        return {
            "scanner": {
                "name": "scanner",
                "stage": "input",
                "class_name": "ScannerPlugin"
            },
            "renamer": {
                "name": "renamer",
                "stage": "parse",
                "class_name": "RenamerPlugin"
            }
        }
    
    def test_valid_startup(self, validator, valid_config, valid_manifests):
        """Test valid startup configuration."""
        result = validator.validate_startup(valid_config, valid_manifests)
        # May have warnings but should be valid
        assert result.valid is True
    
    def test_filters_enabled_plugins(self, validator, valid_config):
        """Test that only enabled plugins are validated."""
        manifests = {
            "scanner": {
                "name": "scanner",
                "stage": "input",
                "class_name": "ScannerPlugin"
            },
            "disabled_plugin": {
                "name": "disabled_plugin",
                "stage": "invalid_stage",  # Invalid but disabled
                "class_name": "DisabledPlugin"
            }
        }
        result = validator.validate_startup(
            valid_config,
            manifests,
            enabled_plugins=["scanner"]
        )
        # Invalid manifest for disabled plugin should not cause error
        assert result.valid is True
    
    def test_circular_dependency_fatal(self, validator, valid_config):
        """Test circular dependency causes fatal error."""
        manifests = {
            "scanner": {
                "name": "scanner",
                "stage": "input",
                "class_name": "ScannerPlugin"
            },
            "renamer": {
                "name": "renamer",
                "stage": "parse",
                "class_name": "RenamerPlugin",
                "requires": ["job.plugins.tmdb.data"]
            },
            "tmdb": {
                "name": "tmdb",
                "stage": "data",
                "class_name": "TmdbPlugin",
                "requires": ["job.plugins.renamer.parsed"]
            }
        }
        config = {
            "_enabled_plugins": ["scanner", "renamer", "tmdb"]
        }
        result = validator.validate_startup(config, manifests)
        assert result.valid is False
        assert result.has_fatal() is True
    
    def test_warning_no_input_plugins(self, validator):
        """Test warning when no input plugins."""
        config = {"_enabled_plugins": ["renamer"]}
        manifests = {
            "renamer": {
                "name": "renamer",
                "stage": "parse",  # Not input
                "class_name": "RenamerPlugin"
            }
        }
        result = validator.validate_startup(config, manifests)
        # Should have W004 warning
        assert any(W004 in w.code for w in result.warnings)
    
    def test_warning_no_output_plugins(self, validator):
        """Test warning when no output plugins."""
        config = {"_enabled_plugins": ["scanner"]}
        manifests = {
            "scanner": {
                "name": "scanner",
                "stage": "input",  # Not output
                "class_name": "ScannerPlugin"
            }
        }
        result = validator.validate_startup(config, manifests)
        # Should have W005 warning
        assert any("W005" in w.code for w in result.warnings)
    
    def test_get_execution_order(self, validator, valid_manifests):
        """Test getting execution order."""
        order = validator.get_execution_order(valid_manifests)
        assert isinstance(order, list)
        assert set(order) == {"scanner", "renamer"}


class TestValidateAtStartup:
    """Test convenience function."""
    
    def test_validate_at_startup_function(self):
        """Test validate_at_startup convenience function."""
        config = {"_enabled_plugins": ["scanner"]}
        manifests = {
            "scanner": {
                "name": "scanner",
                "stage": "input",
                "class_name": "ScannerPlugin"
            }
        }
        result = validate_at_startup(config, manifests)
        assert result.valid is True
