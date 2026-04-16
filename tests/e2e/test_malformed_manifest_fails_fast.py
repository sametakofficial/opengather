"""E2E: discovery must fail fast on a manifest missing ``stage``.

Session 34 WP-1 removed the implicit ``PARSE`` default from
``PluginRegistry._determine_stage``. This guard prevents reintroduction.
"""

import pytest

from archiverr.core.plugins.registry import PluginRegistry


class _FakePlugin:
    name = "fake-no-stage"

    def execute(self, job, services):  # pragma: no cover - never invoked
        return None


def test_missing_stage_raises(monkeypatch):
    registry = PluginRegistry(config={}, debugger=None)
    # Manifest lacks the required ``stage`` key entirely.
    manifest_without_stage = {"name": "fake-no-stage", "version": "0.0.0"}
    with pytest.raises(ValueError) as exc_info:
        registry._determine_stage(manifest_without_stage)
    assert "stage is required" in str(exc_info.value)


def test_invalid_stage_raises():
    registry = PluginRegistry(config={}, debugger=None)
    manifest = {"name": "fake", "stage": "transform"}  # not in enum
    with pytest.raises(ValueError) as exc_info:
        registry._determine_stage(manifest)
    assert "invalid stage" in str(exc_info.value).lower()


def test_input_stage_returns_none():
    """``stage: input`` is the sentinel for per_run plugins (no Stage assigned)."""
    registry = PluginRegistry(config={}, debugger=None)
    assert registry._determine_stage({"name": "scanner", "stage": "input"}) is None
