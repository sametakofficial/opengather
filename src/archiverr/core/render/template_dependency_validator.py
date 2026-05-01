"""Parse-time validator for plugin template references.

S39 R15 §I1 — for each plugin's effective (post-merge) config, walk
every Jinja template string and check that the plugins it references
via the canonical ``jobs[...].plugins.<name>`` / ``run.plugins.<name>``
/ ``job.plugins.<name>`` chains are listed in the plugin's
``manifest.requires``.

Output is a list of ``ValidationWarning`` records the orchestrator can
log at registry init. We deliberately use WARN, not FAIL: the plan
treats this as a developer-experience aid, not a hard contract — a
template that references a plugin not in ``requires`` may still work
at runtime (as long as the data is present), but the dependency graph
will not reflect the real ordering need, which can break in edge
cases. WARN keeps configurations runnable while surfacing the gap.

Why a separate validator instead of letting Jinja fail at render?

ChainableUndefined makes ``{{ jobs[job_id].plugins.unwired.foo }}``
render gracefully to "" — so the silent-failure mode is to produce
empty config values without telling the operator. The validator
restores visibility at parse time.
"""

from dataclasses import dataclass
from typing import Any, Iterable

from ._ast_walker import extract_plugin_refs


@dataclass(frozen=True)
class ValidationWarning:
    """A single template-reference issue.

    Attributes:
        plugin: The plugin whose config carries the offending template.
        referenced_plugin: The plugin name found in the template.
        location: Dotted path inside the plugin's config where the
            template lives (e.g. ``"tasks[0].template"``,
            ``"condition"``). Best-effort string for the operator.
        template: The raw template string for context.
        message: Human-readable diagnosis.
    """
    plugin: str
    referenced_plugin: str
    location: str
    template: str
    message: str


def validate_plugin_template_refs(
    plugin_name: str,
    plugin_config: dict[str, Any],
    declared_requires: Iterable[str],
    known_plugins: Iterable[str],
    render_engine: Any,
) -> list[ValidationWarning]:
    """Walk a plugin's config templates and surface unresolved refs.

    Args:
        plugin_name: Name of the plugin being validated.
        plugin_config: The plugin's effective config dict (post merge).
            Strings containing ``{{`` or ``{%`` are treated as Jinja
            templates; anything else is skipped.
        declared_requires: ``manifest.requires`` entries
            (e.g. ``"plugin.renamer.parsed:success"``,
            ``"job.input.value"``). The validator extracts the plugin
            names from the ``plugin.<name>...`` form.
        known_plugins: Names of plugins registered in the registry.
            Used to distinguish "you forgot to declare this" from
            "you typo'd a plugin name".
        render_engine: ``ConfigRenderEngine`` instance — only its
            ``parse()`` method is used.

    Returns:
        List of ``ValidationWarning``. Empty list when every reference
        is in ``declared_requires``.
    """
    if not isinstance(plugin_config, dict):
        return []
    if render_engine is None or not hasattr(render_engine, "parse"):
        return []

    declared = _plugin_names_from_requires(declared_requires)
    known = set(known_plugins or [])

    warnings: list[ValidationWarning] = []
    for path, template in _iter_templated_strings(plugin_config):
        try:
            ast = render_engine.parse(template)
        except Exception:  # noqa: BLE001 — invalid templates surface elsewhere
            continue
        for ref in extract_plugin_refs(ast):
            if ref == plugin_name:
                # Self-reference is fine; no implicit dependency.
                continue
            if ref in declared:
                continue
            if ref not in known:
                msg = (
                    f"Template references unknown plugin '{ref}'. "
                    "Either typo or not yet registered."
                )
            else:
                msg = (
                    f"Template references plugin '{ref}' but '{ref}' "
                    f"is not listed in {plugin_name}.manifest.requires. "
                    "Add it so the dependency graph reflects the read."
                )
            warnings.append(
                ValidationWarning(
                    plugin=plugin_name,
                    referenced_plugin=ref,
                    location=path,
                    template=template,
                    message=msg,
                )
            )
    return warnings


def _plugin_names_from_requires(declared: Iterable[str]) -> set[str]:
    """Pull plugin names out of ``requires`` entries.

    Recognised forms:
      ``plugin.<name>.<field>:success``
      ``plugin.<name>.<field>:any``
      ``plugin.<name>``
    Anything that doesn't start with ``plugin.`` (e.g. ``job.input.value``,
    ``events.<name>:fired``) is ignored; it's not a plugin reference.
    """
    out: set[str] = set()
    for entry in declared or []:
        if not isinstance(entry, str):
            continue
        if not entry.startswith("plugin."):
            continue
        # plugin.<name>...  -> <name> is the segment between the first
        # and second dot. The trailing ":success"/":any" lives after a
        # colon and never inside <name>, so split on '.' is enough.
        parts = entry.split(".", 2)
        if len(parts) >= 2 and parts[1]:
            # Strip any trailing ":<status>" if there's no third dot.
            name = parts[1].split(":", 1)[0]
            if name:
                out.add(name)
    return out


def _iter_templated_strings(value: Any, prefix: str = ""):
    """Yield ``(path, template_string)`` pairs from a nested value.

    Walks dicts and lists recursively. A string is yielded only if it
    contains a Jinja marker (``{{`` or ``{%``). Plain strings are
    skipped to avoid wasting AST-parse work.
    """
    if isinstance(value, dict):
        for k, v in value.items():
            child_prefix = f"{prefix}.{k}" if prefix else str(k)
            yield from _iter_templated_strings(v, child_prefix)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            child_prefix = f"{prefix}[{i}]"
            yield from _iter_templated_strings(v, child_prefix)
    elif isinstance(value, str):
        if "{{" in value or "{%" in value:
            yield (prefix or "<root>", value)
