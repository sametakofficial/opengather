"""WP-4 + S39 §C1 regression tests for TemplateContextBuilder.

S39 §C1 paradigm shift:
- ``plugin.<name>.{data,status}`` namespace REMOVED (tasker / other render
  consumers must use ``jobs[job_id].plugins.<name>.<field>`` or the
  forthcoming ``data.<jobindex>.<category>.<path>`` resolver namespace).
- ``jobs`` shape: list -> dict keyed by ``job.id``.
- New top-level shortcuts: ``job_id``, ``job_index``, ``data``.

Guards against re-introduction of:
- ``context[plugin_name] = data`` top-level plugin-name shortcuts
- module-level ``build_template_context`` wrapper
- ``count:`` / ``index:`` template function regex in tasker
- top-level ``movie`` / ``show`` aliases
- separate ``_build_context`` helper (must stay inline in ``execute``)
- legacy ``plugin`` synthetic namespace
"""

from unittest.mock import Mock

import pytest

from archiverr.state import template_context
from archiverr.state.template_context import TemplateContextBuilder


def _make_job(plugins, job_id="job-1", index=0):
    job = Mock()
    job.index = index
    job.id = job_id
    job.input.value = "/x.mkv"
    job.input.data = {}
    job.output.values = []
    job.output.data = {}
    job.status.success = True
    job.status.plugins = {}
    job.plugins = plugins
    return job


def _make_services(plugins_data, jobs=None):
    services = Mock()
    job_list = list(jobs) if jobs else []
    services._state = Mock()
    services._state.run = None
    services._state.jobs = job_list
    services.run_safety = {"dry_run": True, "hardlink": False, "no_delete": True}
    services.events.snapshot.return_value = {}
    services.jobid = None
    services.update_state = Mock()
    services.state.get_job_plugin_names.return_value = list(plugins_data.keys())
    services.state.get_plugin_data.side_effect = (
        lambda job_id, name: plugins_data.get(name, {})
    )
    return services


class TestTemplateContextBuilderShape:
    def test_no_plugin_name_shortcut_at_top_level(self):
        """WP-4: context[plugin_name] injection is gone."""
        job = _make_job({"tmdb": {"movie": {"title": "X"}}})
        ctx = TemplateContextBuilder().build_job_context(job)

        assert "tmdb" not in ctx
        assert ctx["job"]["plugins"]["tmdb"] == {"movie": {"title": "X"}}

    def test_expected_top_level_keys(self):
        """S39 §C1 — new canonical top-level shape."""
        job = _make_job({})
        ctx = TemplateContextBuilder().build_job_context(job)

        assert set(ctx.keys()) == {
            "run", "job", "jobs",
            "config", "options", "events",
            "data", "job_id", "jobid", "job_index",
        }

    def test_no_legacy_plugin_namespace(self):
        """S39 §C1 — synthetic 'plugin' namespace must NOT be injected."""
        job = _make_job({"tmdb": {"x": 1}})
        ctx = TemplateContextBuilder().build_job_context(job)
        assert "plugin" not in ctx

    def test_jobs_is_dict_keyed_by_id(self):
        """S39 §C1 — jobs shape: list -> dict keyed by job.id."""
        j1 = _make_job({"tmdb": {"x": 1}}, job_id="job-1", index=0)
        j2 = _make_job({"tmdb": {"x": 2}}, job_id="job-2", index=1)

        ctx = TemplateContextBuilder().build_job_context(j1, all_jobs=[j1, j2])

        assert isinstance(ctx["jobs"], dict)
        assert set(ctx["jobs"].keys()) == {"job-1", "job-2"}
        assert ctx["jobs"]["job-1"]["plugins"]["tmdb"] == {"x": 1}
        assert ctx["jobs"]["job-2"]["plugins"]["tmdb"] == {"x": 2}

    def test_jobs_dict_empty_when_no_jobs_passed(self):
        ctx = TemplateContextBuilder().build_job_context(_make_job({}))
        assert ctx["jobs"] == {}

    def test_job_id_and_job_index_aliases_present(self):
        job = _make_job({}, job_id="abc-123", index=4)
        ctx = TemplateContextBuilder().build_job_context(job)
        assert ctx["job_id"] == "abc-123"
        assert ctx["job_index"] == 4

    def test_data_namespace_is_dict_default_empty(self):
        """S39 §C1 — `data` namespace exposed forward-looking; D phase wires it."""
        ctx = TemplateContextBuilder().build_job_context(_make_job({}))
        assert ctx["data"] == {}

    def test_data_namespace_pulled_from_run_when_present(self):
        run = Mock()
        run.id = "run-1"
        run.status.success = True
        run.status.total_jobs = 1
        run.status.completed = 1
        run.status.failed = 0
        run.config = {}
        run.data = {"<jobindex>": {"show": {"title": {"primary": "X"}}}}

        ctx = TemplateContextBuilder().build_job_context(_make_job({}), run=run)
        assert ctx["data"] == {"<jobindex>": {"show": {"title": {"primary": "X"}}}}

    def test_module_wrapper_removed(self):
        """WP-4: module-level build_template_context function deleted."""
        assert not hasattr(template_context, "build_template_context")
        assert not hasattr(template_context, "_default_builder")

    def test_build_plugin_surface_method_deleted(self):
        """S39 §C1 — _build_plugin_surface method removed entirely."""
        assert not hasattr(TemplateContextBuilder, "_build_plugin_surface")


class TestTaskerNewParadigm:
    """Tasker must use the canonical descent paths after S39 §C1."""

    def test_canonical_jobs_descent_path(self):
        """Canonical: `{{ jobs[job_id].plugins.<name>.<field> }}`."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ jobs[job_id].plugins.tmdb.title }}"}]}
        )
        data = {"tmdb": {"title": "X"}}
        job = _make_job(data)
        result = plugin.execute(job, _make_services(data, jobs=[job]))
        assert result.data["tasks"]["t"]["rendered"] == "X"

    def test_job_plugins_shortcut_path(self):
        """`{{ job.plugins.<name>.<field> }}` resolves to current job."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ job.plugins.tmdb.title }}"}]}
        )
        data = {"tmdb": {"title": "Y"}}
        result = plugin.execute(_make_job(data), _make_services(data))
        assert result.data["tasks"]["t"]["rendered"] == "Y"

    def test_legacy_plugin_namespace_renders_undefined(self):
        """Legacy `plugin.<name>.data.X` no longer resolves (synthetic surface gone)."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ plugin.tmdb.data.title }}"}]}
        )
        data = {"tmdb": {"title": "X"}}
        result = plugin.execute(_make_job(data), _make_services(data))
        rendered = result.data["tasks"]["t"]["rendered"]
        # Either raises silently to "Template error" string, or renders as
        # undefined chain. Concrete contract: original "X" must NOT appear.
        assert "X" not in rendered

    def test_no_top_level_plugin_name_shortcut(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ tmdb.title }}"}]}
        )
        data = {"tmdb": {"title": "X"}}
        result = plugin.execute(_make_job(data), _make_services(data))
        rendered = result.data["tasks"]["t"]["rendered"]
        assert "X" not in rendered

    def test_no_movie_or_show_shortcut(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ movie.name }}"}]}
        )
        data = {"renamer": {"category": "movie",
                            "parsed": {"movie": {"name": "M"}}}}
        result = plugin.execute(_make_job(data), _make_services(data))
        rendered = result.data["tasks"]["t"]["rendered"]
        assert "M" not in rendered

    def test_build_context_helper_deleted(self):
        """WP-4 Commit B: _build_context must be inlined in execute."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin
        assert not hasattr(TaskerPlugin, "_build_context")


class TestCountFilter:
    """S39 §H4a: filter implementations live in core.render now;
    these guard rails track what the tasker plugin must NOT carry."""

    def test_count_filter_lives_in_core_engine(self):
        """Filter coverage moved to ConfigRenderEngine; smoke check via core."""
        from archiverr.core.render import ConfigRenderEngine

        engine = ConfigRenderEngine()
        assert engine.render_string("{{ items | count }}",
                                    {"items": ["a", "b", "c"]}) == "3"
        assert engine.render_string("{{ missing | count }}",
                                    {"missing": None}) == "0"

    def test_tasker_does_not_import_jinja2(self):
        """S39 §H4a: tasker source must not import jinja2 directly."""
        import inspect

        from archiverr.plugins.tasker import plugin as tasker_mod
        src = inspect.getsource(tasker_mod)
        assert "from jinja2" not in src
        assert "import jinja2" not in src

    def test_tasker_has_no_local_filter_methods(self):
        """S39 §H4a: filter shims relocated; tasker no longer owns them."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        assert not hasattr(TaskerPlugin, "_filter_count")
        assert not hasattr(TaskerPlugin, "_filter_truncate")

    def test_tasker_has_no_local_render_methods(self):
        """S39 §H4a: rendering goes through services.render_engine."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        assert not hasattr(TaskerPlugin, "_render_template")
        assert not hasattr(TaskerPlugin, "_evaluate_condition")

    def test_tasker_has_no_env_attribute(self):
        """S39 §H4a: tasker does not own a Jinja Environment."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin({"tasks": []})
        assert not hasattr(plugin, "env")

    def test_no_more_legacy_function_regex(self):
        from archiverr.plugins.tasker import plugin as tasker_mod

        assert not hasattr(tasker_mod.TaskerPlugin, "_FUNCTION_PATTERN")
        assert not hasattr(tasker_mod.TaskerPlugin, "_process_functions")
        assert not hasattr(tasker_mod.TaskerPlugin, "_resolve_path")

    def test_index_is_context_variable(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "idx={{ index }}"}]}
        )
        data = {"tmdb": {"x": 1}}
        job = _make_job(data, index=7)
        result = plugin.execute(job, _make_services(data))
        assert result.data["tasks"]["t"]["rendered"] == "idx=7"


@pytest.mark.parametrize(
    "tmpl,data,expected",
    [
        ("{{ job.plugins.tmdb.movie.title }}",
         {"tmdb": {"movie": {"title": "X"}}}, "X"),
        ("{{ job.plugins.renamer.category }}",
         {"renamer": {"category": "movie"}}, "movie"),
        ("{{ job.plugins.tmdb.tags | count }}",
         {"tmdb": {"tags": [1, 2, 3, 4]}}, "4"),
    ],
)
def test_canonical_template_paths(tmpl, data, expected):
    """End-to-end: canonical `job.plugins.<name>.<field>` paths render correctly."""
    from archiverr.plugins.tasker.plugin import TaskerPlugin

    plugin = TaskerPlugin(
        {"tasks": [{"name": "t", "type": "print", "template": tmpl}]}
    )
    result = plugin.execute(_make_job(data), _make_services(data))
    assert result.data["tasks"]["t"]["rendered"] == expected
