"""Core render engine — config + template rendering with ChainableUndefined.

S39 R15 §H1 — extracted from ``plugins/tasker`` into core. Tasker (and
any other render consumer) calls into this engine instead of importing
jinja2 directly. This keeps the architecture plugin-agnostic: the engine
only sees opaque template strings and an opaque context dict.

Behaviour:
- ``render_string(template, context)`` — render a single template string.
  Errors are caught and returned as ``"Template error: <reason>"`` so
  the caller can decide whether to treat the failure as fatal or as a
  graceful skip (per orchestrator policy). No silent ``pass``.
- ``render_value(value, context)`` — recursive walker. Dicts and lists
  are descended; strings containing ``{{`` or ``{%`` are rendered;
  other values pass through unchanged. This is what makes config a
  "live playground": any string value in the config tree can reference
  the runtime context.
- ``parse(template_str)`` — return the Jinja AST. Used by the
  template_dependency_validator (Phase I §I1/I2) to walk plugin-name
  references at parse time without re-tokenising.

Undefined access uses ``ChainableUndefined`` so missing keys in
arbitrarily deep chains (``{{ a.b.c.d.e }}``) render as empty string
rather than raising ``UndefinedError``. This matches the Flexget /
Airflow ergonomic where a config author writes the path optimistically
and gets a graceful empty rather than an exception.
"""

from typing import Any

from jinja2 import BaseLoader, ChainableUndefined, Environment


class ConfigRenderEngine:
    """Plugin-agnostic Jinja2 render engine for config + tasker templates.

    Stateless beyond the ``Environment`` instance; thread-safe for read
    (Jinja's Environment is documented thread-safe once configured).
    """

    def __init__(self) -> None:
        self.env = Environment(
            loader=BaseLoader(),
            undefined=ChainableUndefined,
            keep_trailing_newline=False,
        )
        # Filters mirrored from the legacy tasker env so existing
        # templates keep working after the relocation. ``format`` is a
        # convenience alias for percent-style formatting; ``count`` is
        # a None-safe alternative to Jinja's built-in ``length``.
        self.env.filters['count'] = self._filter_count
        self.env.filters['format'] = lambda fmt, *args: fmt % args
        self.env.filters['truncate'] = self._filter_truncate

    # -- Rendering -------------------------------------------------------

    def render_string(self, template: str, context: dict[str, Any]) -> str:
        """Render a single template string with the given context.

        Returns ``"Template error: <reason>"`` on render failure rather
        than raising, so callers (tasker, config interpolator) can
        decide how to handle the failure without wrapping every call in
        try/except. Callers that want strict semantics can detect the
        prefix.
        """
        try:
            tmpl = self.env.from_string(template)
            return tmpl.render(**context)
        except Exception as exc:  # noqa: BLE001 — report-and-continue
            return f"Template error: {exc}"

    def render_value(self, value: Any, context: dict[str, Any]) -> Any:
        """Recursively render dict/list/string values; pass others through.

        A string is rendered only if it contains a Jinja marker
        (``{{`` or ``{%``); otherwise it is returned unchanged. This
        avoids both unnecessary parse cost and accidentally rewriting
        strings that happen to contain Jinja-shaped substrings (rare).
        """
        if isinstance(value, str):
            if "{{" in value or "{%" in value:
                return self.render_string(value, context)
            return value
        if isinstance(value, dict):
            return {k: self.render_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render_value(v, context) for v in value]
        return value

    def render_to_bool(self, template: str, context: dict[str, Any]) -> bool:
        """Render a template and coerce the result to bool.

        Empty strings and ``"Template error: ..."`` are False; any other
        non-empty rendered string is True. Used for plugin condition
        fields (e.g. tasker task ``condition``) so the plugin itself
        does not have to import jinja2.
        """
        rendered = self.render_string(template, context)
        if not rendered:
            return False
        if rendered.startswith("Template error"):
            return False
        return bool(rendered.strip())

    # -- Static analysis -------------------------------------------------

    def parse(self, template_str: str):
        """Return the Jinja AST for static analysis.

        Consumed by ``template_dependency_validator`` (Phase I) so it
        can walk ``Getattr`` / ``Getitem`` chains and extract plugin
        names referenced from ``jobs[...].plugins.<name>`` and
        ``run.plugins.<name>``.
        """
        return self.env.parse(template_str)

    # -- Filters ---------------------------------------------------------

    @staticmethod
    def _filter_count(value: Any) -> int:
        """None-safe length: 0 for None / non-sized values."""
        if value is None:
            return 0
        try:
            return len(value)
        except TypeError:
            return 0

    @staticmethod
    def _filter_truncate(value: Any, length: int = 50, end: str = '...') -> str:
        """Simple truncate: return as-is if shorter than length, else clip + end."""
        if value is None:
            return ''
        text = str(value)
        if len(text) <= length:
            return text
        cut = max(length - len(end), 0)
        return text[:cut] + end
