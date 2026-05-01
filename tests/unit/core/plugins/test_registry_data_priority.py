"""Unit tests for PluginRegistry data_priority + emits_map (S39 R15 §D4)."""

from unittest.mock import MagicMock

from archiverr.core.plugins.registry import PluginRegistry


def _make_registry(*, config=None, all_plugins=None, all_manifests=None):
    """Build a partly-initialised registry with the required fields.

    Avoids the full discover_and_load path; we only need the
    config/manifests state for the public-property surface.
    """
    debugger = MagicMock()
    reg = PluginRegistry.__new__(PluginRegistry)
    reg._config = config or {}
    reg._all_plugins = all_plugins or {}
    reg._all_manifests = all_manifests or {}
    reg._debugger = debugger
    reg._loaded = True
    return reg


class TestDataPriorityProperty:
    def test_returns_copy_of_dict(self):
        priority = {"data.<jobindex>.show": ["tmdb", "omdb"]}
        reg = _make_registry(config={"data_priority": priority})
        assert reg.data_priority == priority
        # Mutation must not affect registry.
        out = reg.data_priority
        out["new"] = ["x"]
        assert "new" not in reg.data_priority

    def test_empty_when_unset(self):
        reg = _make_registry(config={})
        assert reg.data_priority == {}

    def test_empty_when_non_dict(self):
        reg = _make_registry(config={"data_priority": "not a dict"})
        assert reg.data_priority == {}


class TestEmitsMapProperty:
    def test_aggregates_from_manifests(self):
        reg = _make_registry(
            all_manifests={
                "tmdb": {"emits": {"show": ["title.primary"], "movie": ["title.primary"]}},
                "omdb": {"emits": {"movie": ["title.primary"]}},
                "renamer": {},  # no emits => not in map
            },
        )
        emits = reg.emits_map
        assert set(emits.keys()) == {"tmdb", "omdb"}
        assert emits["tmdb"]["show"] == ["title.primary"]
        assert emits["omdb"]["movie"] == ["title.primary"]

    def test_empty_when_no_manifests_have_emits(self):
        reg = _make_registry(
            all_manifests={"a": {}, "b": {"requires": ["plugin.a"]}},
        )
        assert reg.emits_map == {}


class TestValidateDataPriority:
    def test_warns_on_unknown_plugin(self):
        reg = _make_registry(
            config={"data_priority": {"data.<jobindex>.show": ["tmdb", "ghost"]}},
            all_plugins={"tmdb": object()},
            all_manifests={"tmdb": {"emits": {"show": ["title.primary"]}}},
        )
        warnings = reg.validate_data_priority()
        assert any("ghost" in w and "not registered" in w for w in warnings)

    def test_warns_when_plugin_doesnt_emit_category(self):
        reg = _make_registry(
            config={"data_priority": {"data.<jobindex>.movie": ["tvmaze"]}},
            all_plugins={"tvmaze": object()},
            all_manifests={"tvmaze": {"emits": {"show": ["title.primary"]}}},
        )
        warnings = reg.validate_data_priority()
        assert any("tvmaze" in w and "movie" in w and "no" in w.lower() for w in warnings)

    def test_no_warnings_when_priority_clean(self):
        reg = _make_registry(
            config={"data_priority": {"data.<jobindex>.show": ["tmdb"]}},
            all_plugins={"tmdb": object()},
            all_manifests={"tmdb": {"emits": {"show": ["title.primary"]}}},
        )
        assert reg.validate_data_priority() == []

    def test_empty_priority_yields_no_warnings(self):
        reg = _make_registry(config={}, all_plugins={"tmdb": object()})
        assert reg.validate_data_priority() == []
