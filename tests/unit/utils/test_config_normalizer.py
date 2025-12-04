"""
Unit tests for config_normalizer module.

Session 11 - Phase 6: FlexGet-style config normalization tests.
"""

import pytest

from archiverr.utils.config_normalizer import (
    normalize_config,
    detect_config_format,
    get_plugin_config,
    is_plugin_enabled,
    get_enabled_plugins,
    get_all_plugins,
    denormalize_config,
)


class TestDetectConfigFormat:
    """Tests for config format detection."""
    
    def test_detect_legacy_format(self):
        """Should detect legacy format with plugins: wrapper."""
        config = {
            "options": {"debug": True},
            "plugins": {
                "tmdb": {"enabled": True, "api_key": "xxx"}
            }
        }
        
        assert detect_config_format(config) == "legacy"
    
    def test_detect_flexget_format(self):
        """Should detect FlexGet format (no plugins: wrapper)."""
        config = {
            "options": {"debug": True},
            "tmdb": {"api_key": "xxx"},
            "scanner": {"targets": ["/movies"]}
        }
        
        assert detect_config_format(config) == "flexget"
    
    def test_detect_empty_config(self):
        """Should detect empty config as flexget."""
        assert detect_config_format({}) == "flexget"
    
    def test_detect_plugins_not_dict(self):
        """Should treat plugins: as non-legacy if not a dict."""
        config = {"plugins": ["tmdb", "scanner"]}
        
        assert detect_config_format(config) == "flexget"


class TestNormalizeLegacyConfig:
    """Tests for normalizing legacy format configs."""
    
    def test_normalize_legacy_enabled(self):
        """Should normalize legacy format with enabled: true."""
        config = {
            "plugins": {
                "tmdb": {"enabled": True, "api_key": "xxx"},
                "scanner": {"enabled": True, "targets": ["/movies"]}
            }
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" in normalized["_enabled_plugins"]
        assert "scanner" in normalized["_enabled_plugins"]
        assert normalized["_plugins"]["tmdb"]["api_key"] == "xxx"
    
    def test_normalize_legacy_disabled(self):
        """Should normalize legacy format with enabled: false."""
        config = {
            "plugins": {
                "tmdb": {"enabled": False, "api_key": "xxx"},
                "tvdb": {"enabled": True}
            }
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" not in normalized["_enabled_plugins"]
        assert "tvdb" in normalized["_enabled_plugins"]
    
    def test_normalize_legacy_false_shorthand(self):
        """Should handle plugin: false shorthand."""
        config = {
            "plugins": {
                "tmdb": False,
                "tvdb": {"api_key": "xxx"}
            }
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" not in normalized["_enabled_plugins"]
        assert "tvdb" in normalized["_enabled_plugins"]
    
    def test_normalize_legacy_default_enabled(self):
        """Should default to enabled when enabled key missing."""
        config = {
            "plugins": {
                "tmdb": {"api_key": "xxx"}  # No enabled key
            }
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" in normalized["_enabled_plugins"]


class TestNormalizeFlexGetConfig:
    """Tests for normalizing FlexGet-style configs."""
    
    def test_normalize_flexget_top_level(self):
        """Should detect plugins from top-level keys."""
        config = {
            "options": {"debug": True},
            "tmdb": {"api_key": "xxx"},
            "scanner": {"targets": ["/movies"]}
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" in normalized["_enabled_plugins"]
        assert "scanner" in normalized["_enabled_plugins"]
        assert "options" not in normalized["_enabled_plugins"]
    
    def test_normalize_flexget_disabled(self):
        """Should handle plugin: false in FlexGet style."""
        config = {
            "tmdb": {"api_key": "xxx"},
            "tvdb": False
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" in normalized["_enabled_plugins"]
        assert "tvdb" not in normalized["_enabled_plugins"]
    
    def test_normalize_flexget_enabled_false(self):
        """Should handle enabled: false in FlexGet style."""
        config = {
            "tmdb": {"api_key": "xxx"},
            "omdb": {"enabled": False, "api_key": "yyy"}
        }
        
        normalized = normalize_config(config)
        
        assert "tmdb" in normalized["_enabled_plugins"]
        assert "omdb" not in normalized["_enabled_plugins"]
    
    def test_reserved_keys_not_plugins(self):
        """Should not treat reserved keys as plugins."""
        config = {
            "options": {"debug": True},
            "aliases": {"m": "movie"},
            "tasks": [{"name": "test"}],
            "tmdb": {"api_key": "xxx"}
        }
        
        normalized = normalize_config(config)
        
        assert "options" not in normalized["_plugins"]
        assert "aliases" not in normalized["_plugins"]
        assert "tasks" not in normalized["_plugins"]
        assert "tmdb" in normalized["_plugins"]


class TestPluginConfigAccessors:
    """Tests for plugin config accessor functions."""
    
    def test_get_plugin_config(self):
        """Should get config for a specific plugin."""
        config = normalize_config({
            "plugins": {
                "tmdb": {"enabled": True, "api_key": "xxx", "language": "tr"}
            }
        })
        
        plugin_cfg = get_plugin_config(config, "tmdb")
        
        assert plugin_cfg["api_key"] == "xxx"
        assert plugin_cfg["language"] == "tr"
        assert "_enabled" not in plugin_cfg  # Internal key removed
    
    def test_get_plugin_config_missing(self):
        """Should return empty dict for missing plugin."""
        config = normalize_config({"plugins": {}})
        
        plugin_cfg = get_plugin_config(config, "nonexistent")
        
        assert plugin_cfg == {}
    
    def test_is_plugin_enabled(self):
        """Should check if plugin is enabled."""
        config = normalize_config({
            "plugins": {
                "tmdb": {"enabled": True},
                "tvdb": {"enabled": False}
            }
        })
        
        assert is_plugin_enabled(config, "tmdb") is True
        assert is_plugin_enabled(config, "tvdb") is False
        assert is_plugin_enabled(config, "missing") is False
    
    def test_get_enabled_plugins(self):
        """Should get list of enabled plugin names."""
        config = normalize_config({
            "plugins": {
                "tmdb": {"enabled": True},
                "scanner": {"enabled": True},
                "tvdb": {"enabled": False}
            }
        })
        
        enabled = get_enabled_plugins(config)
        
        assert "tmdb" in enabled
        assert "scanner" in enabled
        assert "tvdb" not in enabled
    
    def test_get_all_plugins(self):
        """Should get all plugins including disabled."""
        config = normalize_config({
            "plugins": {
                "tmdb": {"enabled": True},
                "tvdb": {"enabled": False}
            }
        })
        
        all_plugins = get_all_plugins(config)
        
        assert "tmdb" in all_plugins
        assert "tvdb" in all_plugins


class TestDenormalizeConfig:
    """Tests for converting normalized config back to original format."""
    
    def test_denormalize_to_legacy(self):
        """Should convert back to legacy format."""
        config = normalize_config({
            "options": {"debug": True},
            "plugins": {
                "tmdb": {"enabled": True, "api_key": "xxx"}
            }
        })
        
        denorm = denormalize_config(config, format="legacy")
        
        assert "plugins" in denorm
        assert denorm["plugins"]["tmdb"]["api_key"] == "xxx"
    
    def test_denormalize_to_flexget(self):
        """Should convert to FlexGet format."""
        config = normalize_config({
            "plugins": {
                "tmdb": {"enabled": True, "api_key": "xxx"},
                "tvdb": {"enabled": False}
            }
        })
        
        denorm = denormalize_config(config, format="flexget")
        
        assert "plugins" not in denorm
        assert denorm["tmdb"]["api_key"] == "xxx"
        assert denorm["tvdb"] is False
    
    def test_denormalize_auto_format(self):
        """Should use original format when auto."""
        config = normalize_config({
            "plugins": {"tmdb": {"enabled": True}}
        })
        
        denorm = denormalize_config(config, format="auto")
        
        # Original was legacy, should stay legacy
        assert "plugins" in denorm


class TestConfigFormatMetadata:
    """Tests for config format metadata."""
    
    def test_format_stored_in_normalized(self):
        """Should store original format in normalized config."""
        legacy = normalize_config({"plugins": {"tmdb": {}}})
        flexget = normalize_config({"tmdb": {"api_key": "x"}})
        
        assert legacy["_config_format"] == "legacy"
        assert flexget["_config_format"] == "flexget"
