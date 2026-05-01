"""Unit tests for core.render.ConfigRenderEngine (S39 R15 §H1)."""

from archiverr.core.render import ConfigRenderEngine


class TestRenderString:
    def test_simple_substitution(self):
        engine = ConfigRenderEngine()
        out = engine.render_string("Hello {{ name }}", {"name": "world"})
        assert out == "Hello world"

    def test_chainable_undefined_swallows_missing_keys(self):
        """Deep chain on missing keys renders empty rather than raising."""
        engine = ConfigRenderEngine()
        out = engine.render_string("{{ a.b.c.d.e }}", {})
        assert out == ""

    def test_chainable_undefined_partial_chain(self):
        engine = ConfigRenderEngine()
        out = engine.render_string("{{ a.b.c }}", {"a": {"b": {}}})
        assert out == ""

    def test_template_error_returns_marker(self):
        """Syntax errors return a marker string, not raise."""
        engine = ConfigRenderEngine()
        out = engine.render_string("{{ unclosed ", {})
        assert out.startswith("Template error:")

    def test_count_filter_on_list(self):
        engine = ConfigRenderEngine()
        out = engine.render_string("{{ xs | count }}", {"xs": [1, 2, 3]})
        assert out == "3"

    def test_count_filter_on_none(self):
        engine = ConfigRenderEngine()
        out = engine.render_string("{{ missing | count }}", {"missing": None})
        assert out == "0"

    def test_format_filter(self):
        engine = ConfigRenderEngine()
        out = engine.render_string("{{ '%02d' | format(7) }}", {})
        assert out == "07"

    def test_truncate_filter(self):
        engine = ConfigRenderEngine()
        out = engine.render_string(
            "{{ s | truncate(10) }}", {"s": "abcdefghijklmnop"}
        )
        assert out.endswith("...")
        assert len(out) == 10


class TestRenderValueRecursive:
    def test_passthrough_plain_strings(self):
        engine = ConfigRenderEngine()
        assert engine.render_value("hello", {}) == "hello"

    def test_render_string_with_marker(self):
        engine = ConfigRenderEngine()
        assert engine.render_value("hi {{ x }}", {"x": "y"}) == "hi y"

    def test_dict_descent(self):
        engine = ConfigRenderEngine()
        out = engine.render_value(
            {"a": "{{ x }}", "b": "static", "c": {"d": "{{ y }}"}},
            {"x": "X", "y": "Y"},
        )
        assert out == {"a": "X", "b": "static", "c": {"d": "Y"}}

    def test_list_descent(self):
        engine = ConfigRenderEngine()
        out = engine.render_value(["{{ a }}", "raw", "{{ b }}"], {"a": "1", "b": "2"})
        assert out == ["1", "raw", "2"]

    def test_non_string_passthrough(self):
        engine = ConfigRenderEngine()
        assert engine.render_value(42, {}) == 42
        assert engine.render_value(None, {}) is None
        assert engine.render_value(True, {}) is True


class TestRenderToBool:
    def test_truthy_template(self):
        engine = ConfigRenderEngine()
        assert engine.render_to_bool("{% if x %}true{% endif %}", {"x": True}) is True

    def test_falsy_empty(self):
        engine = ConfigRenderEngine()
        assert engine.render_to_bool("{% if x %}true{% endif %}", {"x": False}) is False

    def test_falsy_template_error(self):
        engine = ConfigRenderEngine()
        assert engine.render_to_bool("{{ unclosed ", {}) is False

    def test_falsy_undefined_chain(self):
        engine = ConfigRenderEngine()
        # ChainableUndefined renders to "", which is falsy.
        assert engine.render_to_bool("{{ missing.deep.path }}", {}) is False

    def test_whitespace_only_is_falsy(self):
        engine = ConfigRenderEngine()
        assert engine.render_to_bool("   ", {}) is False


class TestParse:
    def test_returns_jinja_ast(self):
        from jinja2 import nodes as J

        engine = ConfigRenderEngine()
        ast = engine.parse("{{ jobs[job_id].plugins.tmdb.title }}")
        # Sanity check: AST has at least one Getattr and one Getitem.
        getattrs = list(ast.find_all(J.Getattr))
        getitems = list(ast.find_all(J.Getitem))
        assert len(getattrs) >= 1
        assert len(getitems) >= 1

    def test_parse_doesnt_render(self):
        """Parse must not raise on undefined chains; just produce AST."""
        engine = ConfigRenderEngine()
        engine.parse("{{ nothing.here.at.all }}")
