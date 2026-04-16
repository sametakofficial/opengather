"""E2E: interpolator resolves scopes, fails fast on unresolved / cycles.

Session 34 WP-3 replaced the regex alias rewriter with
``archiverr.core.config.interpolator.compile_config``. Guards the
dataset contract from ``datasets/10-aliases.yml``.
"""

import pytest

from archiverr.core.config.interpolator import (
    InterpolationError,
    compile_config,
)


def test_absolute_alias_resolves():
    """An alias whose value is itself a ``${...}`` token collapses to the
    native value at that path."""
    cfg = {
        "aliases": {"movie": "${renamer.parsed.movie}"},
        "renamer": {"parsed": {"movie": {"title": "X"}}},
        "tasker": {"label": "${alias:movie}"},
    }
    out = compile_config(cfg)
    assert out["tasker"]["label"] == {"title": "X"}


def test_embedded_alias_stringifies():
    cfg = {
        "aliases": {"year": "${meta.year}"},
        "meta": {"year": 2024},
        "label": "release-${alias:year}",
    }
    out = compile_config(cfg)
    assert out["label"] == "release-2024"


def test_scope_stacking_inner_shadows_outer():
    """Inner ``aliases`` mapping shadows outer when the same name is defined."""
    cfg = {
        "aliases": {"x": "${outer}"},
        "outer": "OUTER",
        "inner": "INNER",
        "block": {
            "aliases": {"x": "${inner}"},
            "value": "${alias:x}",
        },
    }
    out = compile_config(cfg)
    assert out["block"]["value"] == "INNER"


def test_missing_reference_fails_fast():
    cfg = {"value": "${does.not.exist}"}
    with pytest.raises(InterpolationError):
        compile_config(cfg)


def test_default_fallback_resolves():
    cfg = {"value": "${does.not.exist:-fallback}"}
    out = compile_config(cfg)
    assert out["value"] == "fallback"


def test_env_reference(monkeypatch):
    cfg = {"value": "${env:ARCHIVERR_TEST_VAR}"}
    out = compile_config(cfg, env={"ARCHIVERR_TEST_VAR": "hello"})
    assert out["value"] == "hello"


def test_env_missing_fails_fast():
    cfg = {"value": "${env:NEVER_SET_XYZ}"}
    with pytest.raises(InterpolationError):
        compile_config(cfg, env={})


def test_direct_cycle_detected():
    """Two paths that point at each other raise rather than loop forever."""
    cfg = {"a": "${b}", "b": "${a}"}
    with pytest.raises(InterpolationError):
        compile_config(cfg)
