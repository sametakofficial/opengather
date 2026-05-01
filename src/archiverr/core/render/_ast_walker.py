"""Jinja AST walker for static plugin-name reference extraction.

S39 R15 §I2 — used by ``template_dependency_validator`` to detect
plugin names referenced from config templates so we can WARN at
parse-time when a template references plugin X but X is not declared
in the plugin's ``requires``.

Why a custom walker?

Audit blocker H10 in the plan: ``jinja2.meta.find_undeclared_variables``
only returns ROOT identifiers (e.g. ``jobs``, ``run``, ``data``). It
does NOT surface nested attribute access like
``jobs[job_id].plugins.tmdb.title`` — the ``tmdb`` segment is a
``Getattr`` deeper down the AST. The plan's hand-wave assumed
``find_undeclared_variables`` would do this; H10 corrected the
assumption and split the walker into a dedicated module.

Patterns we detect:

* ``jobs[<expr>].plugins.<plugin>``     -> plugin name = <plugin>
* ``run.plugins.<plugin>``              -> plugin name = <plugin>
* ``data.<jobindex>.<category>...``     -> NOT a plugin reference; the
   resolver (Phase D) maps category to plugin via ``data_priority``.
"""

from typing import Iterable

import jinja2.nodes as J


def extract_plugin_refs(ast: J.Template) -> set[str]:
    """Walk a Jinja AST and return plugin names referenced via the
    canonical ``jobs[...].plugins.<name>`` / ``run.plugins.<name>``
    chains.

    Args:
        ast: Jinja2 ``Template`` AST node (typically obtained from
            ``ConfigRenderEngine.parse(template)``).

    Returns:
        Set of plugin names. Empty set if no canonical chains are
        found. Order is not guaranteed.
    """
    refs: set[str] = set()
    if ast is None:
        return refs

    # ``find_all`` yields each Getattr/Getitem; for each we walk the
    # full chain back to a Name root and inspect the segment after
    # the literal "plugins".
    for node in ast.find_all((J.Getattr, J.Getitem)):
        chain = _walk_chain(node)
        plugin_name = _plugin_name_from_chain(chain)
        if plugin_name is not None:
            refs.add(plugin_name)
    return refs


def _walk_chain(node: J.Node) -> list[str]:
    """Walk a Getattr/Getitem chain back to its Name root.

    Returns the chain as a list of string segments, where:
    * a ``Name`` becomes its ``name`` (e.g. "jobs", "run").
    * a ``Getattr`` contributes its ``attr`` (e.g. "plugins", "tmdb").
    * a ``Getitem`` with a ``Const`` arg contributes the const value
       (e.g. ``["plugin.completed"]``); a non-const arg becomes the
       sentinel "?" so the chain length stays right but the segment
       can't masquerade as a real attribute.

    The list is in OUTSIDE-IN order, so for ``jobs[job_id].plugins.tmdb``
    the result is ``["jobs", "?", "plugins", "tmdb"]`` (the ``?``
    represents the dynamic ``job_id`` lookup).
    """
    segments: list[str] = []
    current: J.Node | None = node

    # Walk inside-out, then reverse.
    while current is not None:
        if isinstance(current, J.Getattr):
            segments.append(current.attr)
            current = current.node
        elif isinstance(current, J.Getitem):
            arg = getattr(current, 'arg', None)
            if isinstance(arg, J.Const):
                segments.append(str(arg.value))
            else:
                segments.append("?")
            current = current.node
        elif isinstance(current, J.Name):
            segments.append(current.name)
            current = None
        else:
            # Unknown chain root (e.g. a function call result). Stop.
            break

    segments.reverse()
    return segments


def _plugin_name_from_chain(chain: Iterable[str]) -> str | None:
    """Inspect a walked chain and return the plugin name segment if
    the chain matches one of the canonical render shapes.

    Recognised shapes (head -> plugin name):

      ["jobs", <any>, "plugins", "<name>", ...]      -> "<name>"
      ["run", "plugins", "<name>", ...]              -> "<name>"
      ["job", "plugins", "<name>", ...]              -> "<name>"

    The `job` form is the current-job shortcut also exposed by
    TemplateContextBuilder. Returns None for any chain that doesn't
    match.
    """
    seq = list(chain)
    if len(seq) < 3:
        return None

    head = seq[0]
    if head == "jobs":
        # jobs[...].plugins.<name>
        if len(seq) >= 4 and seq[2] == "plugins":
            candidate = seq[3]
            if _is_valid_plugin_segment(candidate):
                return candidate
        return None
    if head in ("job", "run"):
        # job.plugins.<name>  or  run.plugins.<name>
        if len(seq) >= 3 and seq[1] == "plugins":
            candidate = seq[2]
            if _is_valid_plugin_segment(candidate):
                return candidate
        return None
    return None


def _is_valid_plugin_segment(segment: str) -> bool:
    """A plugin name segment must be a real identifier-shaped token."""
    if not segment:
        return False
    if segment == "?":
        return False
    # Plugin names in this project are kebab-case or snake_case; the
    # AST walker just rejects the dynamic-lookup sentinel and empty
    # strings here. Validation against the registry lives in
    # template_dependency_validator.
    return True
