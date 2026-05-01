"""Unit tests for the AST walker (S39 R15 §I2)."""

from archiverr.core.render import ConfigRenderEngine
from archiverr.core.render._ast_walker import extract_plugin_refs


def _parse(template: str):
    return ConfigRenderEngine().parse(template)


class TestCanonicalShapes:
    def test_jobs_indexed_descent(self):
        ast = _parse("{{ jobs[job_id].plugins.tmdb.title }}")
        assert extract_plugin_refs(ast) == {"tmdb"}

    def test_jobs_with_const_id(self):
        ast = _parse("{{ jobs['abc-123'].plugins.renamer.parsed.movie }}")
        assert extract_plugin_refs(ast) == {"renamer"}

    def test_run_plugins_descent(self):
        ast = _parse("{{ run.plugins.scanner.count }}")
        assert extract_plugin_refs(ast) == {"scanner"}

    def test_job_plugins_shortcut(self):
        ast = _parse("{{ job.plugins.ffprobe.format.duration }}")
        assert extract_plugin_refs(ast) == {"ffprobe"}

    def test_multiple_refs_in_one_template(self):
        tmpl = (
            "{% if job.plugins.tmdb.title %}"
            "{{ jobs[job_id].plugins.renamer.parsed.movie }}"
            "{{ run.plugins.scanner.count }}"
            "{% endif %}"
        )
        ast = _parse(tmpl)
        assert extract_plugin_refs(ast) == {"tmdb", "renamer", "scanner"}


class TestNonMatching:
    def test_data_namespace_is_not_a_plugin_ref(self):
        """data.<jobindex>.<category> is the resolver namespace, not a
        direct plugin reference; the walker must NOT flag the category
        segment as a plugin."""
        ast = _parse("{{ data.0.show.title.primary }}")
        assert extract_plugin_refs(ast) == set()

    def test_top_level_name_only(self):
        ast = _parse("{{ events }}")
        assert extract_plugin_refs(ast) == set()

    def test_arbitrary_chain_not_via_plugins_segment(self):
        ast = _parse("{{ job.input.value }}")
        assert extract_plugin_refs(ast) == set()

    def test_plain_string_no_jinja(self):
        ast = _parse("static text")
        assert extract_plugin_refs(ast) == set()

    def test_legacy_plugin_namespace_not_flagged_as_canonical_ref(self):
        """The deprecated `plugin.<name>.data.X` shape doesn't match
        the canonical chain heads (jobs/job/run). It still shouldn't
        false-positive as a plugin ref via this walker (there are
        no `plugins` segments)."""
        ast = _parse("{{ plugin.tmdb.data.movie.title }}")
        assert extract_plugin_refs(ast) == set()


class TestEdgeCases:
    def test_dynamic_jobs_index_does_not_break_walker(self):
        ast = _parse("{{ jobs[some.fn()].plugins.tmdb.title }}")
        # Dynamic index leaves a "?" placeholder; plugin segment still
        # resolves correctly.
        assert extract_plugin_refs(ast) == {"tmdb"}

    def test_nested_attr_after_plugin_name_doesnt_pollute(self):
        ast = _parse("{{ jobs[job_id].plugins.tmdb.movie.title.primary }}")
        assert extract_plugin_refs(ast) == {"tmdb"}

    def test_empty_template_safe(self):
        ast = _parse("")
        assert extract_plugin_refs(ast) == set()
