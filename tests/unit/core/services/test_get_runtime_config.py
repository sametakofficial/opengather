"""Tests for PluginServices.get_runtime_config (S39 R15 §H3).

The "config canlı playground" entry point: a plugin asks services for
its config block rendered against the live run/job context. Plain
strings pass through; templated strings get Jinja-resolved.
"""

from unittest.mock import Mock

import pytest

from archiverr.core.render import ConfigRenderEngine
from archiverr.core.services.plugin_services import PluginServices


def _make_state(*, run=None, job=None, jobs=None):
    state = Mock()
    state.run = run
    state.job = job
    state.jobs = list(jobs) if jobs else []
    return state


def _make_run(config, data=None):
    run = Mock()
    run.id = "run-1"
    run.status.success = True
    run.status.total_jobs = 1
    run.status.completed = 1
    run.status.failed = 0
    run.config = config
    run.data = data or {}
    return run


def _make_job(plugins, job_id="job-1", index=0):
    job = Mock()
    job.id = job_id
    job.index = index
    job.input.value = "/x.mkv"
    job.input.data = {}
    job.output.values = []
    job.output.data = {}
    job.status.success = True
    job.status.plugins = {}
    job.plugins = plugins
    return job


def _make_services(*, config, render_engine=None, current_job=None,
                   current_plugin="myplugin", run=None, all_jobs=None,
                   event_bus=None):
    state = _make_state(run=run, job=current_job, jobs=all_jobs)
    return PluginServices(
        state=state,
        event_bus=event_bus,
        logger=Mock(),
        config=config,
        mode="per_job" if current_job else "per_run",
        current_job_id=current_job.id if current_job else None,
        current_plugin_name=current_plugin,
        provides_registry=None,
        run_safety={"dry_run": True, "hardlink": False, "no_delete": True},
        render_engine=render_engine,
    )


class TestPlainPassthrough:
    def test_returns_raw_when_no_render_engine(self):
        config = {"plugins": {"myplugin": {"key": "{{ x }}"}}}
        services = _make_services(config=config, render_engine=None)
        out = services.get_runtime_config()
        assert out == {"key": "{{ x }}"}  # unrendered, engine missing

    def test_plain_string_unchanged(self):
        engine = ConfigRenderEngine()
        config = {"plugins": {"myplugin": {"key": "static"}}}
        run = _make_run(config)
        services = _make_services(
            config=config, render_engine=engine,
            current_job=_make_job({}), run=run,
        )
        out = services.get_runtime_config()
        assert out == {"key": "static"}

    def test_empty_dict_when_plugin_absent(self):
        engine = ConfigRenderEngine()
        config = {"plugins": {}}
        services = _make_services(
            config=config, render_engine=engine,
            current_job=_make_job({}), run=_make_run(config),
        )
        assert services.get_runtime_config() == {}


class TestRendering:
    def test_render_against_job_plugins(self):
        engine = ConfigRenderEngine()
        config = {
            "plugins": {
                "myplugin": {
                    "title": "{{ job.plugins.tmdb.title }}",
                    "static": "no-render",
                }
            }
        }
        job = _make_job({"tmdb": {"title": "Inception"}})
        services = _make_services(
            config=config, render_engine=engine,
            current_job=job, run=_make_run(config),
        )
        out = services.get_runtime_config()
        assert out == {"title": "Inception", "static": "no-render"}

    def test_render_against_jobs_dict(self):
        engine = ConfigRenderEngine()
        config = {
            "plugins": {
                "myplugin": {
                    "ref": "{{ jobs[job_id].plugins.tmdb.title }}",
                }
            }
        }
        job = _make_job({"tmdb": {"title": "Matrix"}}, job_id="job-A")
        services = _make_services(
            config=config, render_engine=engine,
            current_job=job, all_jobs=[job], run=_make_run(config),
        )
        out = services.get_runtime_config()
        assert out == {"ref": "Matrix"}

    def test_chainable_undefined_renders_empty(self):
        """Missing chain renders to empty string, not raise."""
        engine = ConfigRenderEngine()
        config = {
            "plugins": {
                "myplugin": {"missing": "{{ a.b.c.d }}"}
            }
        }
        job = _make_job({})
        services = _make_services(
            config=config, render_engine=engine,
            current_job=job, run=_make_run(config),
        )
        out = services.get_runtime_config()
        assert out == {"missing": ""}

    def test_recursive_dict_descent(self):
        engine = ConfigRenderEngine()
        config = {
            "plugins": {
                "myplugin": {
                    "outer": {
                        "inner": "{{ job_index }}",
                        "list": ["{{ job_id }}", "raw"],
                    }
                }
            }
        }
        job = _make_job({}, job_id="J", index=5)
        services = _make_services(
            config=config, render_engine=engine,
            current_job=job, run=_make_run(config),
        )
        out = services.get_runtime_config()
        assert out == {
            "outer": {
                "inner": "5",
                "list": ["J", "raw"],
            }
        }


class TestPerRunScope:
    def test_render_when_no_active_job(self):
        engine = ConfigRenderEngine()
        config = {
            "plugins": {
                "myplugin": {
                    "ref": "run={{ run.id }} jobid={{ job_id }}",
                }
            }
        }
        services = _make_services(
            config=config, render_engine=engine,
            current_job=None, run=_make_run(config), current_plugin="myplugin",
        )
        out = services.get_runtime_config()
        # job_id is None → renders to empty under ChainableUndefined.
        assert out == {"ref": "run=run-1 jobid="}


class TestPluginNameSelection:
    def test_explicit_plugin_name_overrides_current(self):
        engine = ConfigRenderEngine()
        config = {
            "plugins": {
                "alpha": {"x": "alpha"},
                "beta":  {"x": "beta"},
            }
        }
        services = _make_services(
            config=config, render_engine=engine,
            current_job=_make_job({}), run=_make_run(config),
            current_plugin="alpha",
        )
        assert services.get_runtime_config() == {"x": "alpha"}
        assert services.get_runtime_config("beta") == {"x": "beta"}

    def test_no_plugin_no_context_raises(self):
        engine = ConfigRenderEngine()
        services = _make_services(
            config={"plugins": {}}, render_engine=engine,
            current_job=_make_job({}), run=_make_run({}),
            current_plugin=None,
        )
        with pytest.raises(ValueError):
            services.get_runtime_config()
