"""Unit tests for template_dependency_validator (S39 R15 §I1)."""

from archiverr.core.render import (
    ConfigRenderEngine,
    validate_plugin_template_refs,
)


def _engine():
    return ConfigRenderEngine()


class TestNoWarningsWhenAllDeclared:
    def test_simple_referenced_in_requires(self):
        config = {
            "tasks": [
                {"name": "t", "type": "print",
                 "template": "{{ jobs[job_id].plugins.tmdb.title }}"}
            ]
        }
        warnings = validate_plugin_template_refs(
            plugin_name="tasker",
            plugin_config=config,
            declared_requires=["plugin.tmdb.movie:success"],
            known_plugins=["tasker", "tmdb", "renamer"],
            render_engine=_engine(),
        )
        assert warnings == []

    def test_self_reference_is_silent(self):
        config = {"tasks": [{"name": "t", "type": "print",
                             "template": "{{ job.plugins.myplugin.x }}"}]}
        warnings = validate_plugin_template_refs(
            plugin_name="myplugin",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["myplugin"],
            render_engine=_engine(),
        )
        assert warnings == []

    def test_static_strings_skipped(self):
        config = {"a": "no jinja here", "b": "still none"}
        warnings = validate_plugin_template_refs(
            plugin_name="x",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["x"],
            render_engine=_engine(),
        )
        assert warnings == []


class TestWarnsOnUndeclared:
    def test_undeclared_known_plugin(self):
        config = {"k": "{{ run.plugins.scanner.count }}"}
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["reporter", "scanner"],
            render_engine=_engine(),
        )
        assert len(warnings) == 1
        assert warnings[0].referenced_plugin == "scanner"
        assert warnings[0].plugin == "reporter"
        assert "not listed" in warnings[0].message

    def test_undeclared_unknown_plugin(self):
        config = {"k": "{{ jobs[job_id].plugins.typo_plugin.x }}"}
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["reporter"],
            render_engine=_engine(),
        )
        assert len(warnings) == 1
        assert warnings[0].referenced_plugin == "typo_plugin"
        assert "unknown plugin" in warnings[0].message.lower()

    def test_multiple_warnings_one_per_ref(self):
        config = {
            "tasks": [
                {"template": "{{ job.plugins.alpha.x }}"},
                {"template": "{{ run.plugins.beta.x }}"},
            ]
        }
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["reporter", "alpha", "beta"],
            render_engine=_engine(),
        )
        refs = sorted(w.referenced_plugin for w in warnings)
        assert refs == ["alpha", "beta"]

    def test_location_path_includes_indices(self):
        config = {
            "tasks": [
                {"template": "{{ job.plugins.alpha.x }}"},
            ]
        }
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["reporter", "alpha"],
            render_engine=_engine(),
        )
        assert len(warnings) == 1
        assert "tasks[0].template" in warnings[0].location


class TestRequiresPlatformParsing:
    def test_plugin_dot_name_field_status_form(self):
        config = {"k": "{{ run.plugins.scanner.count }}"}
        # scanner is declared via `plugin.scanner.<field>:success` form
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=["plugin.scanner.count:success"],
            known_plugins=["reporter", "scanner"],
            render_engine=_engine(),
        )
        assert warnings == []

    def test_plugin_only_form(self):
        config = {"k": "{{ run.plugins.scanner.x }}"}
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=["plugin.scanner"],
            known_plugins=["reporter", "scanner"],
            render_engine=_engine(),
        )
        assert warnings == []

    def test_non_plugin_requires_ignored(self):
        config = {"k": "{{ run.plugins.scanner.x }}"}
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=["job.input.value", "events.scan.fired"],
            known_plugins=["reporter", "scanner"],
            render_engine=_engine(),
        )
        assert len(warnings) == 1
        assert warnings[0].referenced_plugin == "scanner"


class TestEdgeCases:
    def test_no_render_engine_returns_empty(self):
        config = {"k": "{{ run.plugins.scanner.x }}"}
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["reporter", "scanner"],
            render_engine=None,
        )
        assert warnings == []

    def test_non_dict_config_returns_empty(self):
        warnings = validate_plugin_template_refs(
            plugin_name="reporter",
            plugin_config="not a dict",  # type: ignore[arg-type]
            declared_requires=[],
            known_plugins=["reporter"],
            render_engine=_engine(),
        )
        assert warnings == []

    def test_invalid_jinja_template_swallowed(self):
        config = {"k": "{{ broken"}
        warnings = validate_plugin_template_refs(
            plugin_name="x",
            plugin_config=config,
            declared_requires=[],
            known_plugins=["x"],
            render_engine=_engine(),
        )
        # Validator skips broken templates; the engine itself surfaces
        # them at render time as "Template error: ...".
        assert warnings == []
