"""Integration test for interpolator wiring in PluginRegistry (WP-3 Commit B).

Exercises the ``options._use_legacy_alias`` gate.  With the flag true
(default) the registry must not touch ``${...}`` tokens; with the flag
false the interpolator runs after manifest merge and resolves them.
"""

from unittest.mock import Mock, patch

import pytest

from archiverr.core.plugins.registry import PluginRegistry


@pytest.fixture
def mock_discovery_with_manifests():
    discovery = Mock()
    discovery.discover.return_value = {
        "tmdb": {
            "name": "tmdb",
            "stage": "data",
            "run_mode": "per_job",
            "version": "1.0.0",
            "_path": "/plugins/tmdb",
            "provides": ["tmdb.movie"],
        },
    }
    return discovery


@pytest.fixture
def mock_loader_noop():
    loader = Mock()
    loader.load_by_category = Mock(return_value={})
    return loader


@pytest.fixture
def debugger():
    d = Mock()
    d.debug = Mock()
    d.info = Mock()
    d.warn = Mock()
    d.error = Mock()
    return d


@patch("archiverr.core.plugins.registry.PluginDiscovery")
@patch("archiverr.core.plugins.registry.PluginLoader")
def test_default_resolves_tokens(
    loader_cls, discovery_cls, mock_discovery_with_manifests, mock_loader_noop, debugger
):
    """As of session 34 the interpolator runs by default."""
    discovery_cls.return_value = mock_discovery_with_manifests
    loader_cls.return_value = mock_loader_noop

    config = {
        "aliases": {"base_url": "https://api.example.com"},
        "tmdb": {"endpoint": "${alias:base_url}/movie"},
    }
    registry = PluginRegistry(config, debugger=debugger)
    registry.discover_and_load()

    assert config["tmdb"]["endpoint"] == "https://api.example.com/movie"


@patch("archiverr.core.plugins.registry.PluginDiscovery")
@patch("archiverr.core.plugins.registry.PluginLoader")
def test_legacy_escape_hatch_skips_interpolator(
    loader_cls, discovery_cls, mock_discovery_with_manifests, mock_loader_noop, debugger
):
    discovery_cls.return_value = mock_discovery_with_manifests
    loader_cls.return_value = mock_loader_noop

    config = {
        "options": {"_use_legacy_alias": True},
        "aliases": {"base_url": "https://api.example.com"},
        "tmdb": {"endpoint": "${alias:base_url}/movie"},
    }
    registry = PluginRegistry(config, debugger=debugger)
    registry.discover_and_load()

    assert config["tmdb"]["endpoint"] == "${alias:base_url}/movie"


@patch("archiverr.core.plugins.registry.PluginDiscovery")
@patch("archiverr.core.plugins.registry.PluginLoader")
def test_flag_false_resolves_tokens(
    loader_cls, discovery_cls, mock_discovery_with_manifests, mock_loader_noop, debugger
):
    discovery_cls.return_value = mock_discovery_with_manifests
    loader_cls.return_value = mock_loader_noop

    config = {
        "options": {"_use_legacy_alias": False},
        "aliases": {"base_url": "https://api.example.com"},
        "tmdb": {"endpoint": "${alias:base_url}/movie"},
    }
    registry = PluginRegistry(config, debugger=debugger)
    registry.discover_and_load()

    assert config["tmdb"]["endpoint"] == "https://api.example.com/movie"


@patch("archiverr.core.plugins.registry.PluginDiscovery")
@patch("archiverr.core.plugins.registry.PluginLoader")
def test_flag_false_env_resolver_works(
    loader_cls, discovery_cls, mock_discovery_with_manifests, mock_loader_noop, debugger, monkeypatch
):
    discovery_cls.return_value = mock_discovery_with_manifests
    loader_cls.return_value = mock_loader_noop
    monkeypatch.setenv("INTERP_TEST_TOKEN", "xyz123")

    config = {
        "options": {"_use_legacy_alias": False},
        "tmdb": {"api_key": "${env:INTERP_TEST_TOKEN}"},
    }
    registry = PluginRegistry(config, debugger=debugger)
    registry.discover_and_load()

    assert config["tmdb"]["api_key"] == "xyz123"
