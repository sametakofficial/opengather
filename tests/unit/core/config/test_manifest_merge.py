"""Unit tests for 3-layer plugin config merge (WP-2)."""

from archiverr.core.config.manifest_merge import (
    apply_to_config,
    merge_plugin_layers,
)


def _tmdb_manifest() -> dict:
    return {
        "name": "tmdb",
        "version": "1.0.0",
        "stage": "data",
        "run_mode": "per_job",
        "class_name": "TMDbPlugin",
        "requires": ["plugin.renamer.parsed:success"],
        "provides": ["http.request"],
        "config_schema": {
            "api_key": {"type": "string", "required": True},
            "language": {"type": "string", "default": "en-US"},
            "region": {"type": "string", "default": "US"},
            "extras": {
                "type": "object",
                "properties": {
                    "movie_credits": {"type": "boolean", "default": False},
                    "movie_images": {"type": "boolean", "default": False},
                },
            },
        },
        "defaults": {"region": "TR"},
    }


class TestMergePluginLayers:
    def test_produces_four_layer_structure(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc"}},
            {"tmdb": _tmdb_manifest()},
        )
        assert set(merged["tmdb"].keys()) >= {"_manifest", "_defaults", "user", "_resolved"}

    def test_manifest_block_is_read_only(self):
        manifests = {"tmdb": _tmdb_manifest()}
        merged = merge_plugin_layers({"tmdb": {}}, manifests)
        merged["tmdb"]["_manifest"]["version"] = "999"
        assert manifests["tmdb"]["version"] == "1.0.0"

    def test_user_wins_over_defaults(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc", "language": "tr-TR"}},
            {"tmdb": _tmdb_manifest()},
        )
        assert merged["tmdb"]["_resolved"]["language"] == "tr-TR"

    def test_explicit_defaults_override_schema_defaults(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc"}},
            {"tmdb": _tmdb_manifest()},
        )
        # defaults block sets region=TR; schema default was US
        assert merged["tmdb"]["_resolved"]["region"] == "TR"

    def test_schema_defaults_applied_when_user_silent(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc"}},
            {"tmdb": _tmdb_manifest()},
        )
        assert merged["tmdb"]["_resolved"]["language"] == "en-US"

    def test_nested_object_defaults_collected(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc"}},
            {"tmdb": _tmdb_manifest()},
        )
        assert merged["tmdb"]["_resolved"]["extras"]["movie_credits"] is False

    def test_nested_dict_deep_merge(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc", "extras": {"movie_images": True}}},
            {"tmdb": _tmdb_manifest()},
        )
        # user overrides one nested field; schema default for the other survives
        assert merged["tmdb"]["_resolved"]["extras"]["movie_images"] is True
        assert merged["tmdb"]["_resolved"]["extras"]["movie_credits"] is False

    def test_user_block_strips_internal_markers(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc", "_enabled": True, "_runtime_only": "x"}},
            {"tmdb": _tmdb_manifest()},
        )
        assert "_enabled" not in merged["tmdb"]["user"]
        assert merged["tmdb"]["user"]["api_key"] == "abc"

    def test_internal_markers_carried_over_at_top_level(self):
        merged = merge_plugin_layers(
            {"tmdb": {"api_key": "abc", "_enabled": True}},
            {"tmdb": _tmdb_manifest()},
        )
        assert merged["tmdb"]["_enabled"] is True

    def test_plugin_without_manifest_still_produces_entry(self):
        merged = merge_plugin_layers(
            {"mystery": {"key": "value"}},
            {},
        )
        assert merged["mystery"]["user"] == {"key": "value"}
        assert merged["mystery"]["_manifest"] == {}
        assert merged["mystery"]["_resolved"] == {"key": "value"}

    def test_plugin_without_user_config_still_produces_entry(self):
        merged = merge_plugin_layers({}, {"tmdb": _tmdb_manifest()})
        assert merged["tmdb"]["user"] == {}
        assert merged["tmdb"]["_resolved"]["language"] == "en-US"
        assert merged["tmdb"]["_resolved"]["region"] == "TR"

    def test_input_dicts_not_mutated(self):
        user = {"tmdb": {"api_key": "abc"}}
        manifests = {"tmdb": _tmdb_manifest()}
        _ = merge_plugin_layers(user, manifests)
        assert user == {"tmdb": {"api_key": "abc"}}
        assert "defaults" in manifests["tmdb"]


class TestApplyToConfig:
    def test_rewrites_plugins_entries_in_place(self):
        config = {
            "_plugins": {
                "tmdb": {"api_key": "abc", "_enabled": True},
            },
        }
        returned = apply_to_config(config, {"tmdb": _tmdb_manifest()})
        assert returned is config  # chaining return
        assert set(config["_plugins"]["tmdb"].keys()) >= {
            "_manifest", "_defaults", "user", "_resolved"
        }

    def test_preserves_enabled_marker(self):
        config = {"_plugins": {"tmdb": {"api_key": "abc", "_enabled": True}}}
        apply_to_config(config, {"tmdb": _tmdb_manifest()})
        assert config["_plugins"]["tmdb"]["_enabled"] is True

    def test_missing_plugins_key_is_noop(self):
        config = {"options": {"debug": True}}
        apply_to_config(config, {"tmdb": _tmdb_manifest()})
        assert config == {"options": {"debug": True}}
