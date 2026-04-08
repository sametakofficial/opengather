"""
Unit tests for manifest_normalizer module.

Session 11 - Phase 6: Stage-based manifest normalization tests.
"""

import pytest
import warnings

from archiverr.core.plugins.manifest_normalizer import (
    normalize_manifest,
    validate_manifest,
    get_manifest_format,
    is_manifest_normalized,
    extract_plugin_dependencies,
    VALID_STAGES,
    VALID_TRIGGER_RULES,
)


class TestNormalizeManifest:
    """Tests for manifest normalization."""
    
    def test_normalize_legacy_manifest(self):
        """Should convert legacy category to stage."""
        old_manifest = {
            "name": "tmdb",
            "category": "output",
            "depends_on": ["renamer"],
            "expects": ["renamer.parsed.movie"],
            "class_name": "TMDbPlugin"
        }
        
        normalized = normalize_manifest(old_manifest)
        
        assert normalized["stage"] == "data"  # output category → data stage (generic)
        assert "job.plugins.renamer.parsed.movie" in normalized["requires"]
        assert "category" not in normalized or normalized.get("category") == "output"
        assert "depends_on" not in normalized
        assert "expects" not in normalized
    
    def test_preserve_new_format(self):
        """Should preserve new format manifest fields."""
        new_manifest = {
            "name": "tmdb",
            "stage": "data",
            "requires": ["job.plugins.renamer.parsed"],
            "provides": ["http.request", "state.update"],
            "trigger_rule": "all_success",
            "class_name": "TMDbPlugin"
        }
        
        normalized = normalize_manifest(new_manifest)
        
        assert normalized["stage"] == "data"
        assert normalized["requires"] == ["job.plugins.renamer.parsed"]
        assert normalized["provides"] == ["http.request", "state.update"]
        assert normalized["trigger_rule"] == "all_success"
    
    def test_infer_stage_from_category(self):
        """Should infer stage from category (generic, no plugin-name lookup)."""
        input_plugin = normalize_manifest(
            {"name": "any-input", "category": "input", "class_name": "S"}
        )
        output_plugin = normalize_manifest(
            {"name": "any-output", "category": "output", "class_name": "T"}
        )
        no_category = normalize_manifest(
            {"name": "any-plugin", "class_name": "P"}
        )

        assert input_plugin["stage"] == "input"
        assert output_plugin["stage"] == "data"  # output category -> data stage
        assert no_category["stage"] == "data"  # default

    def test_explicit_stage_preserved(self):
        """Should preserve explicit stage regardless of plugin name."""
        manifest = normalize_manifest(
            {"name": "custom-plugin", "stage": "parse", "class_name": "C"}
        )
        assert manifest["stage"] == "parse"
    
    def test_convert_expects_to_requires(self):
        """Should add job.plugins. prefix to expects."""
        manifest = {
            "name": "test",
            "expects": [
                "renamer.parsed.movie",
                "ffprobe.video.codec"
            ],
            "class_name": "Test"
        }
        
        normalized = normalize_manifest(manifest)
        
        assert "job.plugins.renamer.parsed.movie" in normalized["requires"]
        assert "job.plugins.ffprobe.video.codec" in normalized["requires"]
    
    def test_preserve_job_prefixed_requires(self):
        """Should not double-prefix already prefixed requires."""
        manifest = {
            "name": "test",
            "requires": [
                "job.plugins.renamer.parsed",
                "job.input.value"
            ],
            "class_name": "Test"
        }
        
        normalized = normalize_manifest(manifest)
        
        assert "job.plugins.renamer.parsed" in normalized["requires"]
        assert "job.input.value" in normalized["requires"]
        # Should not have double prefix
        assert not any("job.plugins.job." in r for r in normalized["requires"])
    
    def test_infer_provides_from_stage(self):
        """Should infer provides based on stage (generic, no plugin-name lookup)."""
        input_plugin = normalize_manifest(
            {"name": "any-input", "stage": "input", "class_name": "I"}
        )
        data_plugin = normalize_manifest(
            {"name": "any-data", "stage": "data", "class_name": "D"}
        )
        output_plugin = normalize_manifest(
            {"name": "any-output", "stage": "output", "class_name": "O"}
        )

        assert "job.create" in input_plugin["provides"]
        assert "fs.read" in input_plugin["provides"]
        assert "state.update" in data_plugin["provides"]
        assert "output.render" in output_plugin["provides"]
    
    def test_default_trigger_rule(self):
        """Should default to all_success trigger rule."""
        manifest = {"name": "test", "class_name": "Test"}
        
        normalized = normalize_manifest(manifest)
        
        assert normalized["trigger_rule"] == "all_success"
    
    def test_mark_as_normalized(self):
        """Should mark manifest as normalized."""
        manifest = {"name": "test", "class_name": "Test"}
        
        normalized = normalize_manifest(manifest)
        
        assert normalized["_normalized"] is True
        assert is_manifest_normalized(normalized) is True


class TestValidateManifest:
    """Tests for manifest validation."""
    
    def test_valid_manifest(self):
        """Should validate a correct manifest."""
        manifest = {
            "name": "test",
            "stage": "data",
            "class_name": "TestPlugin",
            "requires": [],
            "provides": ["state.update"]
        }
        
        is_valid, error = validate_manifest(manifest)
        
        assert is_valid is True
        assert error is None
    
    def test_missing_name(self):
        """Should fail if name is missing."""
        manifest = {"class_name": "Test"}
        
        is_valid, error = validate_manifest(manifest)
        
        assert is_valid is False
        assert "name" in error
    
    def test_missing_class_name(self):
        """Should fail if class_name is missing."""
        manifest = {"name": "test"}
        
        is_valid, error = validate_manifest(manifest)
        
        assert is_valid is False
        assert "class_name" in error
    
    def test_invalid_stage(self):
        """Should fail for invalid stage value."""
        manifest = {
            "name": "test",
            "class_name": "Test",
            "stage": "invalid_stage"
        }
        
        is_valid, error = validate_manifest(manifest)
        
        assert is_valid is False
        assert "stage" in error.lower()
    
    def test_invalid_trigger_rule(self):
        """Should fail for invalid trigger_rule."""
        manifest = {
            "name": "test",
            "class_name": "Test",
            "trigger_rule": "always"  # Invalid, removed in session 11
        }
        
        is_valid, error = validate_manifest(manifest)
        
        assert is_valid is False
        assert "trigger_rule" in error.lower()
    
    def test_requires_must_be_list(self):
        """Should fail if requires is not a list."""
        manifest = {
            "name": "test",
            "class_name": "Test",
            "requires": "renamer.parsed"  # Should be list
        }
        
        is_valid, error = validate_manifest(manifest)
        
        assert is_valid is False
        assert "list" in error.lower()


class TestManifestFormat:
    """Tests for manifest format detection."""
    
    def test_detect_new_format(self):
        """Should detect new format with stage field."""
        manifest = {"name": "test", "stage": "data"}
        
        assert get_manifest_format(manifest) == "new"
    
    def test_detect_legacy_format(self):
        """Should detect legacy format with category field."""
        manifest = {"name": "test", "category": "output"}
        
        assert get_manifest_format(manifest) == "legacy"
    
    def test_detect_unknown_as_new(self):
        """Should treat manifest without stage/category as new."""
        manifest = {"name": "test", "class_name": "Test"}
        
        assert get_manifest_format(manifest) == "new"


class TestExtractDependencies:
    """Tests for extracting plugin dependencies from requires."""
    
    def test_extract_single_dependency(self):
        """Should extract plugin name from requires path."""
        manifest = {
            "name": "tmdb",
            "requires": ["job.plugins.renamer.parsed.movie"]
        }
        
        deps = extract_plugin_dependencies(manifest)
        
        assert deps == ["renamer"]
    
    def test_extract_multiple_dependencies(self):
        """Should extract multiple plugin names."""
        manifest = {
            "name": "tasker",
            "requires": [
                "job.plugins.renamer.parsed",
                "job.plugins.tmdb.movie",
                "job.plugins.ffprobe.video"
            ]
        }
        
        deps = extract_plugin_dependencies(manifest)
        
        assert "renamer" in deps
        assert "tmdb" in deps
        assert "ffprobe" in deps
    
    def test_ignore_non_plugin_paths(self):
        """Should ignore non-plugin paths like job.input."""
        manifest = {
            "name": "test",
            "requires": [
                "job.plugins.renamer.parsed",
                "job.input.value",
                "job.output.data"
            ]
        }
        
        deps = extract_plugin_dependencies(manifest)
        
        assert deps == ["renamer"]
    
    def test_no_duplicate_dependencies(self):
        """Should not include duplicate plugin names."""
        manifest = {
            "name": "test",
            "requires": [
                "job.plugins.renamer.parsed.movie",
                "job.plugins.renamer.parsed.show"
            ]
        }
        
        deps = extract_plugin_dependencies(manifest)
        
        assert deps == ["renamer"]


class TestValidConstants:
    """Tests for valid stage and trigger rule constants."""
    
    def test_valid_stages(self):
        """Should have correct valid stages."""
        assert "input" in VALID_STAGES
        assert "parse" in VALID_STAGES
        assert "data" in VALID_STAGES
        assert "output" in VALID_STAGES
        assert len(VALID_STAGES) == 4
    
    def test_valid_trigger_rules(self):
        """Should have correct trigger rules (no 'always')."""
        assert "all_success" in VALID_TRIGGER_RULES
        assert "one_success" in VALID_TRIGGER_RULES
        assert "all_done" in VALID_TRIGGER_RULES
        assert "all_fail" in VALID_TRIGGER_RULES
        assert "none_fail" in VALID_TRIGGER_RULES
        assert "always" not in VALID_TRIGGER_RULES  # Removed in session 11
