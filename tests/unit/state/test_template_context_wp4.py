"""WP-4 regression tests for TemplateContextBuilder + tasker overlay.

Guards against re-introduction of:
- ``context[plugin_name] = data`` top-level plugin-name shortcuts
- module-level ``build_template_context`` wrapper
- ``count:`` / ``index:`` template function regex in tasker
- top-level ``movie`` / ``show`` aliases
- separate ``_build_context`` helper (must stay inline in ``execute``)
"""

from unittest.mock import Mock

import pytest

from archiverr.state import template_context
from archiverr.state.template_context import TemplateContextBuilder


def _make_job(plugins):
    job = Mock()
    job.index = 0
    job.id = "job-1"
    job.input.value = "/x.mkv"
    job.input.data = {}
    job.output.values = []
    job.output.data = {}
    job.status.success = True
    job.status.plugins = {}
    job.plugins = plugins
    return job


def _make_services(plugins_data):
    services = Mock()
    services.get_run.return_value = None
    services.get_all_jobs.return_value = []
    services.run_safety = {"dry_run": True, "hardlink": False, "no_delete": True}
    services.events.snapshot.return_value = {}
    services.state.get_job_plugin_names.return_value = list(plugins_data.keys())
    services.state.get_plugin_data.side_effect = (
        lambda job_id, name: plugins_data.get(name, {})
    )
    return services


class TestTemplateContextBuilderTrim:
    def test_no_plugin_name_shortcut_at_top_level(self):
        """WP-4: context[plugin_name] injection is gone."""
        job = _make_job({"tmdb": {"movie": {"title": "X"}}})
        ctx = TemplateContextBuilder().build_job_context(job)

        assert "tmdb" not in ctx
        assert ctx["job"]["plugins"]["tmdb"] == {"movie": {"title": "X"}}

    def test_expected_top_level_keys(self):
        job = _make_job({})
        ctx = TemplateContextBuilder().build_job_context(job)

        assert set(ctx.keys()) == {"run", "job", "jobs", "config", "options", "events"}

    def test_module_wrapper_removed(self):
        """WP-4: module-level build_template_context function deleted."""
        assert not hasattr(template_context, "build_template_context")
        assert not hasattr(template_context, "_default_builder")


class TestTaskerContextShape:
    """Tasker exposes ``plugin.<name>.data.*`` via rendered templates."""

    def test_canonical_plugin_data_path(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ plugin.tmdb.data.title }}"}]}
        )
        data = {"tmdb": {"title": "X"}}
        result = plugin.execute(_make_job(data), _make_services(data))
        assert result.data["tasks"]["t"]["rendered"] == "X"

    def test_no_top_level_plugin_name_shortcut(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin(
            {"tasks": [{"name": "t", "type": "print",
                        "template": "{{ tmdb.title }}"}]}
        )
        data = {"tmdb": {"title": "X"}}
        result = plugin.execute(_make_job(data), _make_services(data))
        rendered = result.data["tasks"]["t"]["rendered"]
        assert "tmdb" in rendered and "undefined" in rendered
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
        assert "movie" in rendered and "undefined" in rendered
        assert "M" not in rendered

    def test_build_context_helper_deleted(self):
        """WP-4 Commit B: _build_context must be inlined in execute."""
        from archiverr.plugins.tasker.plugin import TaskerPlugin
        assert not hasattr(TaskerPlugin, "_build_context")


class TestCountFilter:
    def test_count_filter_on_list(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin({"tasks": []})
        tmpl = plugin.env.from_string("{{ items | count }}")
        assert tmpl.render(items=["a", "b", "c"]) == "3"

    def test_count_filter_on_none(self):
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        plugin = TaskerPlugin({"tasks": []})
        tmpl = plugin.env.from_string("{{ missing | count }}")
        assert tmpl.render(missing=None) == "0"

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
        job = _make_job(data)
        job.index = 7
        result = plugin.execute(job, _make_services(data))
        assert result.data["tasks"]["t"]["rendered"] == "idx=7"


@pytest.mark.parametrize(
    "tmpl,data,expected",
    [
        ("{{ plugin.tmdb.data.movie.title }}",
         {"tmdb": {"movie": {"title": "X"}}}, "X"),
        ("{{ plugin.renamer.data.category }}",
         {"renamer": {"category": "movie"}}, "movie"),
        ("{{ plugin.tmdb.data.tags | count }}",
         {"tmdb": {"tags": [1, 2, 3, 4]}}, "4"),
    ],
)
def test_canonical_template_paths(tmpl, data, expected):
    """End-to-end: canonical ``plugin.<name>.data.*`` paths render correctly."""
    from archiverr.plugins.tasker.plugin import TaskerPlugin

    plugin = TaskerPlugin(
        {"tasks": [{"name": "t", "type": "print", "template": tmpl}]}
    )
    result = plugin.execute(_make_job(data), _make_services(data))
    assert result.data["tasks"]["t"]["rendered"] == expected
