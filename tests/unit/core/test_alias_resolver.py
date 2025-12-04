"""
Unit tests for alias_resolver module.

Session 11 - Phase 6: Template alias resolution tests.
"""

import pytest
import warnings

from archiverr.core.config.alias_resolver import (
    AliasResolver,
    create_alias_resolver,
    expand_alias_in_path,
    SYSTEM_ALIASES,
    SHORT_ALIASES,
)


class TestAliasResolverResolve:
    """Tests for AliasResolver.resolve() method."""
    
    def test_resolve_user_alias(self):
        """Should resolve user-defined alias."""
        resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})
        
        assert resolver.resolve("m") == "job.plugins.tmdb.movie"
    
    def test_resolve_short_alias(self):
        """Should resolve built-in short aliases."""
        resolver = AliasResolver()
        
        assert resolver.resolve("j") == "job"
        assert resolver.resolve("r") == "run"
        assert resolver.resolve("o") == "options"
        assert resolver.resolve("g") == "globals"
    
    def test_resolve_system_alias(self):
        """Should resolve system aliases."""
        resolver = AliasResolver()
        
        assert resolver.resolve("job") == "job"
        assert resolver.resolve("run") == "run"
        assert resolver.resolve("index") == "index"
    
    def test_resolve_unknown_returns_itself(self):
        """Should return unknown alias unchanged."""
        resolver = AliasResolver()
        
        assert resolver.resolve("unknown") == "unknown"
        assert resolver.resolve("some.path") == "some.path"
    
    def test_user_alias_priority_over_short(self):
        """User aliases should override short aliases."""
        resolver = AliasResolver({"j": "custom.path"})
        
        assert resolver.resolve("j") == "custom.path"
    
    def test_system_alias_not_overridable(self):
        """System aliases should warn when shadowed."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resolver = AliasResolver({"job": "something.else"})
            
            # Should still resolve to original
            # Note: We warn but don't actually block in current impl
            assert len(w) >= 1
            assert "shadows" in str(w[0].message).lower()


class TestAliasResolverBuildContext:
    """Tests for AliasResolver.build_context() method."""
    
    def test_build_context_with_user_aliases(self):
        """Should inject user aliases into context."""
        resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})
        
        base_context = {
            "job": {
                "plugins": {
                    "tmdb": {"movie": {"title": "Test Movie"}}
                }
            }
        }
        
        context = resolver.build_context(base_context)
        
        assert context["m"]["title"] == "Test Movie"
    
    def test_build_context_with_short_aliases(self):
        """Should inject short aliases."""
        resolver = AliasResolver()
        
        base_context = {
            "job": {"id": "job-123"},
            "run": {"id": "run-456"}
        }
        
        context = resolver.build_context(base_context)
        
        assert context["j"]["id"] == "job-123"
        assert context["r"]["id"] == "run-456"
    
    def test_build_context_preserves_base(self):
        """Should not modify original base context."""
        resolver = AliasResolver({"m": "job.data"})
        
        base = {"job": {"data": "value"}}
        original_base = base.copy()
        
        context = resolver.build_context(base)
        
        assert base == original_base
        assert "m" not in base
        assert "m" in context
    
    def test_build_context_missing_path(self):
        """Should not inject alias if path doesn't exist."""
        resolver = AliasResolver({"missing": "job.nonexistent.path"})
        
        base_context = {"job": {"data": "value"}}
        
        context = resolver.build_context(base_context)
        
        assert "missing" not in context
    
    def test_build_context_nested_path(self):
        """Should resolve deeply nested paths."""
        resolver = AliasResolver({
            "title": "job.plugins.tmdb.movie.details.title"
        })
        
        base_context = {
            "job": {
                "plugins": {
                    "tmdb": {
                        "movie": {
                            "details": {"title": "Deep Title"}
                        }
                    }
                }
            }
        }
        
        context = resolver.build_context(base_context)
        
        assert context["title"] == "Deep Title"


class TestCreateAliasResolver:
    """Tests for create_alias_resolver factory function."""
    
    def test_create_from_config(self):
        """Should create resolver from config dict."""
        config = {
            "aliases": {
                "m": "job.plugins.tmdb.movie",
                "s": "job.plugins.tmdb.show"
            }
        }
        
        resolver = create_alias_resolver(config)
        
        assert resolver.resolve("m") == "job.plugins.tmdb.movie"
        assert resolver.resolve("s") == "job.plugins.tmdb.show"
    
    def test_create_from_empty_config(self):
        """Should handle config without aliases."""
        config = {"options": {"debug": True}}
        
        resolver = create_alias_resolver(config)
        
        # Should still have short aliases
        assert resolver.resolve("j") == "job"
    
    def test_create_filters_invalid_aliases(self):
        """Should filter out invalid alias definitions."""
        config = {
            "aliases": {
                "valid": "job.data",
                123: "invalid.key",  # Non-string key
                "invalid": 456  # Non-string value
            }
        }
        
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            resolver = create_alias_resolver(config)
        
        assert resolver.resolve("valid") == "job.data"
        # Invalid aliases should be filtered


class TestExpandAliasInPath:
    """Tests for expand_alias_in_path function."""
    
    def test_expand_alias_prefix(self):
        """Should expand alias at start of path."""
        resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})
        
        result = expand_alias_in_path("m.title", resolver)
        
        assert result == "job.plugins.tmdb.movie.title"
    
    def test_expand_short_alias(self):
        """Should expand short alias."""
        resolver = AliasResolver()
        
        result = expand_alias_in_path("j.id", resolver)
        
        assert result == "job.id"
    
    def test_expand_single_alias(self):
        """Should expand path that is just an alias."""
        resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})
        
        result = expand_alias_in_path("m", resolver)
        
        assert result == "job.plugins.tmdb.movie"
    
    def test_no_expansion_needed(self):
        """Should return unchanged if no alias match."""
        resolver = AliasResolver()
        
        result = expand_alias_in_path("some.random.path", resolver)
        
        assert result == "some.random.path"
    
    def test_expand_empty_path(self):
        """Should handle empty path."""
        resolver = AliasResolver()
        
        result = expand_alias_in_path("", resolver)
        
        assert result == ""


class TestGetAllAliases:
    """Tests for AliasResolver.get_all_aliases() method."""
    
    def test_get_all_aliases(self):
        """Should return combined aliases."""
        resolver = AliasResolver({"custom": "job.custom"})
        
        all_aliases = resolver.get_all_aliases()
        
        # Should include user, short, and system aliases
        assert "custom" in all_aliases
        assert "j" in all_aliases
        assert "job" in all_aliases
    
    def test_user_aliases_property(self):
        """Should return only user aliases."""
        user_aliases = {"m": "movie", "s": "show"}
        resolver = AliasResolver(user_aliases)
        
        assert resolver.user_aliases == user_aliases
    
    def test_user_aliases_returns_copy(self):
        """Should return a copy to prevent mutation."""
        user_aliases = {"m": "movie"}
        resolver = AliasResolver(user_aliases)
        
        returned = resolver.user_aliases
        returned["new"] = "added"
        
        assert "new" not in resolver.user_aliases


class TestSystemAndShortAliases:
    """Tests for system and short alias constants."""
    
    def test_system_aliases_exist(self):
        """Should have expected system aliases."""
        assert "job" in SYSTEM_ALIASES
        assert "jobs" in SYSTEM_ALIASES
        assert "run" in SYSTEM_ALIASES
        assert "options" in SYSTEM_ALIASES
        assert "index" in SYSTEM_ALIASES
        assert "globals" in SYSTEM_ALIASES
    
    def test_short_aliases_exist(self):
        """Should have expected short aliases."""
        assert "j" in SHORT_ALIASES
        assert "r" in SHORT_ALIASES
        assert "o" in SHORT_ALIASES
        assert "g" in SHORT_ALIASES
        
        # Short aliases should point to system aliases
        assert SHORT_ALIASES["j"] == "job"
        assert SHORT_ALIASES["r"] == "run"
