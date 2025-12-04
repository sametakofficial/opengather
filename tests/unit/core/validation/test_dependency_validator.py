"""
Tests for DependencyValidator

Session 11 - Phase 7
"""

import pytest
from archiverr.core.validation.dependency_validator import DependencyValidator
from archiverr.core.validation.result import ValidationLevel
from archiverr.core.validation.error_codes import E014, E015


class TestDependencyValidator:
    """Test DependencyValidator class."""
    
    @pytest.fixture
    def validator(self):
        return DependencyValidator()
    
    def test_no_dependencies(self, validator):
        """Test plugins with no dependencies."""
        manifests = {
            "plugin1": {"name": "plugin1", "requires": []},
            "plugin2": {"name": "plugin2", "requires": []}
        }
        result = validator.validate(manifests)
        assert result.valid is True
    
    def test_valid_dependencies(self, validator):
        """Test valid dependency chain."""
        manifests = {
            "renamer": {"name": "renamer", "requires": []},
            "tmdb": {"name": "tmdb", "requires": ["job.plugins.renamer.parsed"]}
        }
        result = validator.validate(manifests)
        assert result.valid is True
    
    def test_missing_dependency(self, validator):
        """Test detection of missing dependency."""
        manifests = {
            "tmdb": {"name": "tmdb", "requires": ["job.plugins.renamer.parsed"]}
            # renamer not in manifests!
        }
        result = validator.validate(manifests)
        assert result.valid is False
        assert any(E014 in e.code for e in result.errors)
    
    def test_circular_dependency_simple(self, validator):
        """Test detection of simple circular dependency A → B → A."""
        manifests = {
            "a": {"name": "a", "requires": ["job.plugins.b.data"]},
            "b": {"name": "b", "requires": ["job.plugins.a.data"]}
        }
        result = validator.validate(manifests)
        assert result.valid is False
        assert any(E015 in e.code for e in result.errors)
        assert result.has_fatal() is True
    
    def test_circular_dependency_chain(self, validator):
        """Test detection of circular chain A → B → C → A."""
        manifests = {
            "a": {"name": "a", "requires": ["job.plugins.b.data"]},
            "b": {"name": "b", "requires": ["job.plugins.c.data"]},
            "c": {"name": "c", "requires": ["job.plugins.a.data"]}
        }
        result = validator.validate(manifests)
        assert result.valid is False
        assert any(E015 in e.code for e in result.errors)
    
    def test_self_dependency_not_circular(self, validator):
        """Test that self-dependency is ignored (filtered in graph building)."""
        manifests = {
            "a": {"name": "a", "requires": ["job.plugins.a.data"]}  # Self-ref
        }
        result = validator.validate(manifests)
        # Self-dependency is filtered out, so no cycle
        assert result.valid is True
    
    def test_legacy_requires_format(self, validator):
        """Test legacy requires format (plugin.path)."""
        manifests = {
            "renamer": {"name": "renamer", "requires": []},
            "tmdb": {"name": "tmdb", "requires": ["renamer.parsed"]}  # Legacy
        }
        result = validator.validate(manifests)
        assert result.valid is True
    
    def test_non_plugin_requires_ignored(self, validator):
        """Test that job.input.* and run.* requires are ignored."""
        manifests = {
            "scanner": {
                "name": "scanner",
                "requires": ["job.input.path", "run.config.option"]  # Not plugin deps
            }
        }
        result = validator.validate(manifests)
        assert result.valid is True  # These are not treated as plugin dependencies


class TestDependencyValidatorOrder:
    """Test execution order calculation."""
    
    @pytest.fixture
    def validator(self):
        return DependencyValidator()
    
    def test_order_no_dependencies(self, validator):
        """Test order when no dependencies."""
        manifests = {
            "b": {"name": "b", "requires": []},
            "a": {"name": "a", "requires": []},
            "c": {"name": "c", "requires": []}
        }
        order = validator.get_execution_order(manifests)
        assert set(order) == {"a", "b", "c"}
    
    def test_order_with_dependencies(self, validator):
        """Test order respects dependencies."""
        manifests = {
            "c": {"name": "c", "requires": ["job.plugins.b.data"]},
            "b": {"name": "b", "requires": ["job.plugins.a.data"]},
            "a": {"name": "a", "requires": []}
        }
        order = validator.get_execution_order(manifests)
        
        # a must come before b, b must come before c
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")
    
    def test_order_complex_graph(self, validator):
        """Test order with complex dependency graph."""
        manifests = {
            "renamer": {"name": "renamer", "requires": []},
            "tmdb": {"name": "tmdb", "requires": ["job.plugins.renamer.parsed"]},
            "tvdb": {"name": "tvdb", "requires": ["job.plugins.renamer.parsed"]},
            "tasker": {"name": "tasker", "requires": [
                "job.plugins.tmdb.movie",
                "job.plugins.tvdb.show"
            ]}
        }
        order = validator.get_execution_order(manifests)
        
        # renamer first
        assert order.index("renamer") < order.index("tmdb")
        assert order.index("renamer") < order.index("tvdb")
        # tmdb/tvdb before tasker
        assert order.index("tmdb") < order.index("tasker")
        assert order.index("tvdb") < order.index("tasker")


class TestDependencyValidatorHelpers:
    """Test helper methods."""
    
    @pytest.fixture
    def validator(self):
        return DependencyValidator()
    
    def test_get_dependencies(self, validator):
        """Test getting dependencies for a plugin."""
        manifests = {
            "a": {"name": "a", "requires": []},
            "b": {"name": "b", "requires": ["job.plugins.a.data"]}
        }
        deps = validator.get_dependencies(manifests, "b")
        assert "a" in deps
    
    def test_get_dependents(self, validator):
        """Test getting plugins that depend on a plugin."""
        manifests = {
            "a": {"name": "a", "requires": []},
            "b": {"name": "b", "requires": ["job.plugins.a.data"]},
            "c": {"name": "c", "requires": ["job.plugins.a.data"]}
        }
        dependents = validator.get_dependents(manifests, "a")
        assert "b" in dependents
        assert "c" in dependents
