"""
Tests for ManifestValidator

Session 11 - Phase 7
"""

import pytest
from archiverr.core.validation.manifest_validator import ManifestValidator
from archiverr.core.validation.error_codes import E012, E013, E016, E017


class TestManifestValidator:
    """Test ManifestValidator class."""
    
    @pytest.fixture
    def validator(self):
        return ManifestValidator()
    
    def test_valid_manifest(self, validator):
        """Test valid manifest passes."""
        manifest = {
            "name": "test_plugin",
            "stage": "data",
            "class_name": "TestPlugin",
            "requires": ["job.plugins.renamer.parsed"],
            "provides": ["http.request"]
        }
        result = validator.validate(manifest)
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_missing_name(self, validator):
        """Test missing name field."""
        manifest = {
            "stage": "data",
            "class_name": "TestPlugin"
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E012 in e.code for e in result.errors)
    
    def test_missing_stage(self, validator):
        """Test missing stage field."""
        manifest = {
            "name": "test",
            "class_name": "TestPlugin"
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E012 in e.code for e in result.errors)
    
    def test_missing_class_name(self, validator):
        """Test missing class_name field."""
        manifest = {
            "name": "test",
            "stage": "data"
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E012 in e.code for e in result.errors)
    
    def test_invalid_stage(self, validator):
        """Test invalid stage value."""
        manifest = {
            "name": "test",
            "stage": "invalid_stage",
            "class_name": "TestPlugin"
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E013 in e.code for e in result.errors)
    
    def test_valid_stages(self, validator):
        """Test all valid stage values."""
        for stage in ['input', 'parse', 'data', 'output']:
            manifest = {
                "name": "test",
                "stage": stage,
                "class_name": "TestPlugin"
            }
            result = validator.validate(manifest)
            assert result.valid is True
    
    def test_invalid_trigger_rule(self, validator):
        """Test invalid trigger_rule."""
        manifest = {
            "name": "test",
            "stage": "data",
            "class_name": "TestPlugin",
            "trigger_rule": "invalid_rule"
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E013 in e.code for e in result.errors)
    
    def test_valid_trigger_rules(self, validator):
        """Test all valid trigger rules."""
        valid_rules = ['all_success', 'one_success', 'all_done', 'all_fail', 'none_fail']
        for rule in valid_rules:
            manifest = {
                "name": "test",
                "stage": "data",
                "class_name": "TestPlugin",
                "trigger_rule": rule
            }
            result = validator.validate(manifest)
            assert result.valid is True, f"Rule '{rule}' should be valid"
    
    def test_dynamic_provides_forbidden(self, validator):
        """Test that job.* and run.* in provides is forbidden."""
        manifest = {
            "name": "test",
            "stage": "data",
            "class_name": "TestPlugin",
            "provides": ["job.plugins.test.data"]  # FORBIDDEN
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E017 in e.code for e in result.errors)
    
    def test_run_provides_forbidden(self, validator):
        """Test that run.* in provides is forbidden."""
        manifest = {
            "name": "test",
            "stage": "data",
            "class_name": "TestPlugin",
            "provides": ["run.config.option"]  # FORBIDDEN
        }
        result = validator.validate(manifest)
        assert result.valid is False
        assert any(E017 in e.code for e in result.errors)
    
    def test_static_provides_allowed(self, validator):
        """Test that static provides are allowed."""
        manifest = {
            "name": "test",
            "stage": "data",
            "class_name": "TestPlugin",
            "provides": ["http.request", "fs.write", "custom.feature"]
        }
        result = validator.validate(manifest)
        assert result.valid is True


class TestManifestValidatorAll:
    """Test validate_all for multiple manifests."""
    
    @pytest.fixture
    def validator(self):
        return ManifestValidator()
    
    def test_validate_all_valid(self, validator):
        """Test validating multiple valid manifests."""
        manifests = {
            "plugin1": {
                "name": "plugin1",
                "stage": "input",
                "class_name": "Plugin1"
            },
            "plugin2": {
                "name": "plugin2",
                "stage": "data",
                "class_name": "Plugin2"
            }
        }
        result = validator.validate_all(manifests)
        assert result.valid is True
    
    def test_provides_conflict_detection(self, validator):
        """Test detection of provides conflicts."""
        manifests = {
            "plugin1": {
                "name": "plugin1",
                "stage": "data",
                "class_name": "Plugin1",
                "provides": ["http.request"]
            },
            "plugin2": {
                "name": "plugin2",
                "stage": "data",
                "class_name": "Plugin2",
                "provides": ["http.request"]  # CONFLICT!
            }
        }
        result = validator.validate_all(manifests)
        assert result.valid is False
        assert any(E016 in e.code for e in result.errors)
    
    def test_no_conflict_different_provides(self, validator):
        """Test no conflict with different provides."""
        manifests = {
            "plugin1": {
                "name": "plugin1",
                "stage": "data",
                "class_name": "Plugin1",
                "provides": ["http.request"]
            },
            "plugin2": {
                "name": "plugin2",
                "stage": "data",
                "class_name": "Plugin2",
                "provides": ["fs.write"]
            }
        }
        result = validator.validate_all(manifests)
        assert result.valid is True
    
    def test_one_invalid_fails_all(self, validator):
        """Test that one invalid manifest fails validation."""
        manifests = {
            "plugin1": {
                "name": "plugin1",
                "stage": "input",
                "class_name": "Plugin1"
            },
            "plugin2": {
                "name": "plugin2",
                "stage": "invalid",  # INVALID
                "class_name": "Plugin2"
            }
        }
        result = validator.validate_all(manifests)
        assert result.valid is False
