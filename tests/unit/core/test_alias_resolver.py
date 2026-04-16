"""Alias-resolver regression tests, retargeted at the interpolator (WP-3).

``AliasResolver`` was deleted in session 34; its role is covered by
:mod:`archiverr.core.config.interpolator`.  These tests mirror every
behavioural surface the old resolver exposed (resolve, build_context,
get_all_aliases, expand_alias_in_path, create_alias_resolver, reserved
names) so the regression net stays intact.
"""

import pytest

from archiverr.core.config.interpolator import (
    RESERVED_ALIAS_NAMES,
    InterpolationError,
    compile_config,
)


class TestAliasLookup:
    def test_alias_resolves_to_value(self):
        cfg = {
            "aliases": {"movie": "${parser.parsed.movie}"},
            "parser": {"parsed": {"movie": {"title": "X"}}},
            "echo": "${alias:movie}",
        }
        out = compile_config(cfg)
        assert out["echo"] == {"title": "X"}

    def test_unknown_alias_fails_fast(self):
        cfg = {"echo": "${alias:missing}"}
        with pytest.raises(InterpolationError):
            compile_config(cfg)

    def test_alias_default_fallback(self):
        cfg = {"echo": "${alias:missing:-fallback}"}
        out = compile_config(cfg)
        assert out["echo"] == "fallback"

    def test_reserved_name_rejected(self):
        cfg = {
            "aliases": {"plugin": "illegal"},
            "echo": "${alias:plugin}",
        }
        with pytest.raises(InterpolationError, match="reserved"):
            compile_config(cfg)

    def test_user_alias_literal_string(self):
        cfg = {
            "aliases": {"m": "job.plugins.tmdb.movie"},
            "echo": "${alias:m}",
        }
        out = compile_config(cfg)
        assert out["echo"] == "job.plugins.tmdb.movie"


class TestScopedAliases:
    def test_inner_shadows_outer(self):
        cfg = {
            "aliases": {"tag": "OUTER"},
            "sub": {
                "aliases": {"tag": "INNER"},
                "echo": "${alias:tag}",
            },
        }
        out = compile_config(cfg)
        assert out["sub"]["echo"] == "INNER"

    def test_sibling_cannot_see_subtree_alias(self):
        cfg = {
            "a": {"aliases": {"secret": "hidden"}, "v": "${alias:secret}"},
            "b": {"v": "${alias:secret:-default}"},
        }
        out = compile_config(cfg)
        assert out["a"]["v"] == "hidden"
        assert out["b"]["v"] == "default"

    def test_outer_alias_visible_from_inner(self):
        cfg = {
            "aliases": {"lang": "tr-TR"},
            "sub": {"echo": "${alias:lang}"},
        }
        out = compile_config(cfg)
        assert out["sub"]["echo"] == "tr-TR"


class TestAbsoluteAndRelative:
    def test_absolute_path_lookup(self):
        cfg = {"tmdb": {"lang": "${api.default_lang}"}, "api": {"default_lang": "tr-TR"}}
        out = compile_config(cfg)
        assert out["tmdb"]["lang"] == "tr-TR"

    def test_relative_sibling(self):
        cfg = {"svc": {"host": "localhost", "url": "http://${.host}"}}
        out = compile_config(cfg)
        assert out["svc"]["url"] == "http://localhost"

    def test_relative_parent(self):
        cfg = {
            "svc": {
                "host": "h1",
                "nested": {"full": "${..host}:443"},
            }
        }
        out = compile_config(cfg)
        assert out["svc"]["nested"]["full"] == "h1:443"

    def test_deeply_nested_absolute(self):
        cfg = {
            "echo": "${job.plugins.tmdb.movie.details.title}",
            "job": {"plugins": {"tmdb": {"movie": {"details": {"title": "Deep"}}}}},
        }
        out = compile_config(cfg)
        assert out["echo"] == "Deep"

    def test_missing_absolute_path_fails_fast(self):
        cfg = {"echo": "${job.nonexistent.path}"}
        with pytest.raises(InterpolationError):
            compile_config(cfg)

    def test_missing_absolute_path_with_default(self):
        cfg = {"echo": "${job.nonexistent.path:-fallback}"}
        out = compile_config(cfg)
        assert out["echo"] == "fallback"


class TestInputPreservation:
    def test_compile_does_not_mutate_input(self):
        cfg = {
            "aliases": {"m": "${parsed.movie}"},
            "parsed": {"movie": {"title": "X"}},
            "echo": "${alias:m}",
        }
        original = {
            "aliases": {"m": "${parsed.movie}"},
            "parsed": {"movie": {"title": "X"}},
            "echo": "${alias:m}",
        }
        compile_config(cfg)
        assert cfg == original

    def test_aliases_preserved_in_output(self):
        cfg = {
            "aliases": {"m": "${parser.movie}"},
            "parser": {"movie": "X"},
        }
        out = compile_config(cfg)
        # alias declarations survive compilation for debugging / inspection
        assert "aliases" in out
        assert "m" in out["aliases"]


class TestReservedNames:
    def test_all_reserved_names_present(self):
        expected = frozenset(
            {"run", "job", "jobs", "plugin", "plugins",
             "config", "options", "provides", "events"}
        )
        assert expected == RESERVED_ALIAS_NAMES

    @pytest.mark.parametrize("name", sorted(RESERVED_ALIAS_NAMES))
    def test_reserved_name_is_rejected(self, name):
        cfg = {
            "aliases": {name: "anything"},
            "echo": f"${{alias:{name}}}",
        }
        with pytest.raises(InterpolationError, match="reserved"):
            compile_config(cfg)

    def test_non_reserved_user_alias_passes(self):
        cfg = {
            "aliases": {"m": "X"},
            "echo": "${alias:m}",
        }
        out = compile_config(cfg)
        assert out["echo"] == "X"


class TestAliasValueKinds:
    def test_alias_value_is_dict(self):
        cfg = {
            "aliases": {"movie": "${parsed.movie}"},
            "parsed": {"movie": {"year": 2020, "title": "T"}},
            "echo": "${alias:movie}",
        }
        out = compile_config(cfg)
        assert out["echo"] == {"year": 2020, "title": "T"}

    def test_alias_value_is_list(self):
        cfg = {
            "aliases": {"tags": "${meta.tags}"},
            "meta": {"tags": ["a", "b", "c"]},
            "echo": "${alias:tags}",
        }
        out = compile_config(cfg)
        assert out["echo"] == ["a", "b", "c"]

    def test_alias_value_is_int(self):
        cfg = {
            "aliases": {"n": "${meta.count}"},
            "meta": {"count": 42},
            "echo": "${alias:n}",
        }
        out = compile_config(cfg)
        assert out["echo"] == 42

    def test_alias_embedded_in_string_stringifies(self):
        cfg = {
            "aliases": {"n": "42"},
            "label": "count=${alias:n}",
        }
        out = compile_config(cfg)
        assert out["label"] == "count=42"


class TestEnvResolver:
    def test_env_resolves_from_custom_env(self):
        cfg = {"key": "${env:MY_TOKEN}"}
        out = compile_config(cfg, env={"MY_TOKEN": "abc"})
        assert out["key"] == "abc"

    def test_env_missing_fails_fast(self):
        cfg = {"key": "${env:DOES_NOT_EXIST_9x}"}
        with pytest.raises(InterpolationError):
            compile_config(cfg, env={})

    def test_env_missing_with_default(self):
        cfg = {"key": "${env:DOES_NOT_EXIST_9x:-fallback}"}
        out = compile_config(cfg, env={})
        assert out["key"] == "fallback"


class TestCycleDetection:
    def test_direct_cycle_raises(self):
        cfg = {"a": "${b}", "b": "${a}"}
        with pytest.raises(InterpolationError, match="cyclic"):
            compile_config(cfg)

    def test_indirect_cycle_raises(self):
        cfg = {"a": "${b}", "b": "${c}", "c": "${a}"}
        with pytest.raises(InterpolationError, match="cyclic"):
            compile_config(cfg)


class TestEmbeddedTokens:
    def test_embedded_token_in_string(self):
        cfg = {"greet": "hi ${name}", "name": "world"}
        out = compile_config(cfg)
        assert out["greet"] == "hi world"

    def test_multiple_tokens_in_string(self):
        cfg = {
            "host": "srv",
            "port": 8080,
            "url": "http://${host}:${port}/",
        }
        out = compile_config(cfg)
        assert out["url"] == "http://srv:8080/"
