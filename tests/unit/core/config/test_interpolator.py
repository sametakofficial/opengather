"""Unit tests for core.config.interpolator (WP-3)."""

import pytest

from archiverr.core.config.interpolator import (
    InterpolationError,
    Interpolator,
    compile_config,
)
from archiverr.core.config.scope_stack import ScopeFrame, ScopeStack


class TestScopeStack:
    def test_empty_stack_paths(self):
        s = ScopeStack()
        assert s.current_path() == ()
        assert s.parent_path() == ()
        assert s.resolve_alias("x") is None

    def test_push_and_lookup_innermost_wins(self):
        s = ScopeStack()
        s.push(ScopeFrame(path=(), aliases={"a": "root"}))
        s.push(ScopeFrame(path=("nested",), aliases={"a": "inner"}))
        assert s.resolve_alias("a") == "inner"

    def test_outer_visible_when_inner_lacks(self):
        s = ScopeStack()
        s.push(ScopeFrame(path=(), aliases={"root_only": 1}))
        s.push(ScopeFrame(path=("x",), aliases={}))
        assert s.resolve_alias("root_only") == 1

    def test_parent_path(self):
        s = ScopeStack()
        s.push(ScopeFrame(path=("tmdb", "data"), aliases={}))
        assert s.current_path() == ("tmdb", "data")
        assert s.parent_path() == ("tmdb",)

    def test_visible_aliases_flattened(self):
        s = ScopeStack()
        s.push(ScopeFrame(path=(), aliases={"a": 1, "b": 2}))
        s.push(ScopeFrame(path=("x",), aliases={"b": 3, "c": 4}))
        assert s.visible_aliases() == {"a": 1, "b": 3, "c": 4}


class TestAbsolutePaths:
    def test_simple_absolute_ref(self):
        cfg = {"tmdb": {"language": "${api.default_lang}"}, "api": {"default_lang": "tr-TR"}}
        out = compile_config(cfg)
        assert out["tmdb"]["language"] == "tr-TR"

    def test_absolute_preserves_non_string_type(self):
        cfg = {"a": "${b.c}", "b": {"c": 42}}
        out = compile_config(cfg)
        assert out["a"] == 42

    def test_absolute_preserves_dict(self):
        cfg = {"a": "${b.c}", "b": {"c": {"nested": True}}}
        out = compile_config(cfg)
        assert out["a"] == {"nested": True}

    def test_embedded_token_stringifies(self):
        cfg = {"greeting": "hello ${name}", "name": "world"}
        out = compile_config(cfg)
        assert out["greeting"] == "hello world"


class TestRelativePaths:
    def test_sibling_lookup(self):
        cfg = {
            "tmdb": {
                "key": "abc",
                "url": "https://api/${.key}",
            }
        }
        out = compile_config(cfg)
        assert out["tmdb"]["url"] == "https://api/abc"

    def test_parent_sibling_lookup(self):
        cfg = {
            "service": {
                "host": "localhost",
                "nested": {"full": "${..host}:8080"},
            }
        }
        out = compile_config(cfg)
        assert out["service"]["nested"]["full"] == "localhost:8080"


class TestAliasResolution:
    def test_root_alias(self):
        cfg = {
            "aliases": {"movie": "${parser.movie}"},
            "parser": {"movie": {"title": "X"}},
            "tasker": {"out": "${alias:movie}"},
        }
        out = compile_config(cfg)
        assert out["tasker"]["out"] == {"title": "X"}

    def test_subtree_alias_shadows_root(self):
        cfg = {
            "aliases": {"tag": "ROOT"},
            "sub": {
                "aliases": {"tag": "INNER"},
                "echo": "${alias:tag}",
            },
        }
        out = compile_config(cfg)
        assert out["sub"]["echo"] == "INNER"

    def test_subtree_alias_not_visible_to_siblings(self):
        cfg = {
            "a": {
                "aliases": {"x": "hidden"},
                "v": "${alias:x}",
            },
            "b": {"v": "${alias:x:-fallback}"},
        }
        out = compile_config(cfg)
        assert out["a"]["v"] == "hidden"
        assert out["b"]["v"] == "fallback"

    def test_reserved_alias_name_rejected(self):
        cfg = {
            "aliases": {"config": "illegal"},
            "x": "${alias:config}",
        }
        with pytest.raises(InterpolationError, match="reserved"):
            compile_config(cfg)


class TestEnvResolver:
    def test_env_hit(self):
        cfg = {"k": "${env:MY_TEST_VAR}"}
        out = Interpolator(env={"MY_TEST_VAR": "secret"}).compile(cfg)
        assert out["k"] == "secret"

    def test_env_missing_fails_without_default(self):
        cfg = {"k": "${env:DEFINITELY_NOT_SET_XYZ}"}
        with pytest.raises(InterpolationError):
            Interpolator(env={}).compile(cfg)

    def test_env_missing_with_default(self):
        cfg = {"k": "${env:NOT_SET:-fallback}"}
        out = Interpolator(env={}).compile(cfg)
        assert out["k"] == "fallback"


class TestDefaults:
    def test_default_when_path_missing(self):
        cfg = {"k": "${not.there:-fallback}"}
        out = compile_config(cfg)
        assert out["k"] == "fallback"

    def test_default_preserves_literal_string(self):
        cfg = {"k": "${env:NOPE:-hello world}"}
        out = Interpolator(env={}).compile(cfg)
        assert out["k"] == "hello world"

    def test_default_not_used_when_value_present(self):
        cfg = {"k": "${a:-fallback}", "a": "real"}
        out = compile_config(cfg)
        assert out["k"] == "real"


class TestFailFast:
    def test_unresolved_absolute_raises(self):
        cfg = {"k": "${does.not.exist}"}
        with pytest.raises(InterpolationError, match="unresolved"):
            compile_config(cfg)

    def test_unknown_resolver_raises(self):
        cfg = {"k": "${unknown:arg}"}
        with pytest.raises(InterpolationError, match="unknown resolver"):
            compile_config(cfg)

    def test_empty_expression_raises(self):
        cfg = {"k": "${}"}
        with pytest.raises(InterpolationError, match="empty"):
            compile_config(cfg)


class TestCycleDetection:
    def test_direct_cycle(self):
        cfg = {"a": "${b}", "b": "${a}"}
        with pytest.raises(InterpolationError, match="cyclic"):
            compile_config(cfg)

    def test_self_cycle(self):
        cfg = {"a": "${a}"}
        with pytest.raises(InterpolationError, match="cyclic"):
            compile_config(cfg)


class TestEndToEndSamples:
    def test_dataset_config_sample(self):
        """Mirrors the config_sample in datasets/10-aliases.yml shape."""
        cfg = {
            "aliases": {"movie": "${parser.parsed.movie}"},
            "parser": {"parsed": {"movie": {"name": "Tenet", "year": 2020}}},
            "tasker": {
                "aliases": {"title": "${alias:movie}"},
                "dest": "${alias:title}",
            },
        }
        out = compile_config(cfg)
        assert out["tasker"]["dest"] == {"name": "Tenet", "year": 2020}

    def test_deep_tree_preserves_unrelated(self):
        cfg = {
            "x": "${.y}",  # bad: .y has no sibling at root
            "y": "literal",
        }
        # At root scope, .y is the same as y (both siblings at root)
        out = compile_config(cfg)
        assert out["x"] == "literal"
        assert out["y"] == "literal"

    def test_non_dict_root_rejected(self):
        with pytest.raises(TypeError):
            compile_config(["not", "a", "dict"])  # type: ignore[arg-type]
