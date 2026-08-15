"""Single path-aware interpolation engine (WP-3).

Replaces the previous trio of regex alias rewrite + runtime
``AliasResolver`` + manifest-local Jinja.  Walks the compiled config
tree once, resolves every ``${...}`` token against a scope stack, and
returns a new tree with interpolated values.  Jinja is intentionally
NOT invoked here - render-time templates consume the *already*
interpolated config.

Supported syntax (per ``datasets/10-aliases.yml``):

* ``${a.b.c}``           - absolute dotted path from the config root
* ``${.field}``          - sibling of the string being resolved
* ``${..field}``         - sibling of the parent mapping
* ``${alias:name}``      - alias lookup in the current scope stack
* ``${env:VAR}``         - environment variable (reads ``os.environ``)
* ``${expr:-default}``   - fall back to ``default`` when ``expr`` is
                           missing or empty; this is the only implicit
                           fallback

Contract:

* Interpolation is structural - a value that is entirely a single
  ``${...}`` token takes the referenced value as-is (dict, list, int,
  …); tokens embedded in larger strings are stringified.
* Cyclic references raise ``InterpolationError``.
* Unresolved references raise ``InterpolationError`` unless a ``:-``
  default was supplied.
* Aliases are data; alias values are themselves interpolated.
"""

from __future__ import annotations

import copy
import os
import re
from typing import Any

from .scope_stack import ScopeFrame, ScopeStack

_TOKEN_RE = re.compile(r"\$\{([^}]*)\}")

RESERVED_ALIAS_NAMES: frozenset[str] = frozenset({
    "run", "job", "jobs", "plugin", "plugins",
    "config", "options", "provides", "events",
    "jobid",
})

# Tokens left intact at compile time and resolved when a runtime
# extras map is supplied (S40 Phase D).
DEFERRED_RUNTIME_TOKENS: frozenset[str] = frozenset({"jobid"})

_MISSING = object()


class InterpolationError(ValueError):
    """Raised for unresolved refs, cycles, or malformed expressions."""


def compile_config(
    config_tree: dict[str, Any],
    *,
    env: dict[str, str] | None = None,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a new config tree with all ``${...}`` tokens resolved.

    ``env`` lets callers inject a custom environment (tests); when
    ``None`` we read from ``os.environ`` at resolve time.

    ``runtime`` supplies deferred tokens such as ``${jobid}``. When
    omitted, those tokens stay as ``${jobid}`` for a later pass
    (S40 Phase D).

    The input is not mutated.
    """
    return Interpolator(env=env, runtime=runtime).compile(config_tree)


def apply_runtime_tokens(value: Any, runtime: dict[str, Any]) -> Any:
    """Resolve leftover ``${jobid}`` tokens in an already-compiled tree."""
    return Interpolator(runtime=runtime)._apply_runtime(value)


class Interpolator:
    """Two-pass walker: push scopes, resolve strings.

    Kept as a class so the mutable resolution stack (for cycle
    detection) can live on the instance instead of being threaded as an
    argument through every recursion.
    """

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        runtime: dict[str, Any] | None = None,
    ) -> None:
        self._env = env if env is not None else os.environ
        self._runtime = runtime
        self._root: dict[str, Any] | None = None
        self._in_flight: list[tuple[str, ...]] = []
        self._in_flight_aliases: set[str] = set()

    def compile(self, config_tree: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(config_tree, dict):
            raise TypeError("Interpolator expects a dict at the root")

        compiled = copy.deepcopy(config_tree)
        self._root = compiled

        stack = ScopeStack()
        root_aliases = compiled.get("aliases")
        stack.push(ScopeFrame(path=(), aliases=root_aliases if isinstance(root_aliases, dict) else {}))

        try:
            self._walk(compiled, path=(), stack=stack)
        finally:
            self._root = None
            self._in_flight.clear()
            self._in_flight_aliases.clear()

        return compiled

    def _apply_runtime(self, node: Any) -> Any:
        if isinstance(node, dict):
            return {k: self._apply_runtime(v) for k, v in node.items()}
        if isinstance(node, list):
            return [self._apply_runtime(v) for v in node]
        if isinstance(node, str) and "${" in node:
            return self._replace_deferred(node)
        return node

    def _replace_deferred(self, text: str) -> Any:
        runtime = self._runtime or {}

        def _value(name: str) -> Any:
            raw = runtime.get(name)
            return "" if raw is None else raw

        match = _TOKEN_RE.fullmatch(text)
        if match is not None and match.group(1).strip() in DEFERRED_RUNTIME_TOKENS:
            return _value(match.group(1).strip())

        def substitute(m: re.Match[str]) -> str:
            body = m.group(1).strip()
            if body in DEFERRED_RUNTIME_TOKENS:
                val = _value(body)
                return "" if val is None else str(val)
            return m.group(0)

        return _TOKEN_RE.sub(substitute, text)

    def _walk(self, node: Any, *, path: tuple[str, ...], stack: ScopeStack) -> Any:
        """Recurse into ``node`` in place (mappings / lists) and resolve
        every string leaf.  Returns the (possibly new) value for the
        caller to re-assign; required because a whole-string token may
        collapse to a non-string value.
        """
        if isinstance(node, dict):
            self._resolve_mapping(node, path=path, stack=stack)
            return node
        if isinstance(node, list):
            for i, item in enumerate(node):
                node[i] = self._walk(item, path=path + (f"[{i}]",), stack=stack)
            return node
        if isinstance(node, str):
            return self._resolve_string(node, path=path, stack=stack)
        return node

    def _resolve_mapping(
        self,
        node: dict[str, Any],
        *,
        path: tuple[str, ...],
        stack: ScopeStack,
    ) -> None:
        local_aliases = node.get("aliases")
        pushed = False
        if isinstance(local_aliases, dict) and path:
            stack.push(ScopeFrame(path=path, aliases=local_aliases))
            pushed = True

        try:
            for key, value in list(node.items()):
                # alias definitions are data; leave them untouched so
                # they survive for debugging and so relookups below
                # still see the raw declaration.
                if key == "aliases" and path == ():
                    continue
                child_path = path + (str(key),)
                node[key] = self._walk(value, path=child_path, stack=stack)
        finally:
            if pushed:
                stack.pop()

    def _resolve_string(
        self,
        text: str,
        *,
        path: tuple[str, ...],
        stack: ScopeStack,
    ) -> Any:
        match = _TOKEN_RE.fullmatch(text)
        if match is not None:
            # Whole-string token → preserve native type
            return self._resolve_expression(match.group(1), path=path, stack=stack)

        def substitute(m: re.Match[str]) -> str:
            value = self._resolve_expression(m.group(1), path=path, stack=stack)
            return "" if value is None else str(value)

        return _TOKEN_RE.sub(substitute, text)

    def _resolve_expression(
        self,
        expr: str,
        *,
        path: tuple[str, ...],
        stack: ScopeStack,
    ) -> Any:
        expr = expr.strip()
        if not expr:
            raise InterpolationError("empty ${} expression")

        body, default = _split_default(expr)
        try:
            value = self._evaluate(body, path=path, stack=stack)
        except InterpolationError:
            if default is not None:
                return default
            raise

        if value is _MISSING or value is None or value == "":
            if default is not None:
                return default
            if value is _MISSING:
                raise InterpolationError(f"unresolved reference: ${{{expr}}}")
        return value

    def _evaluate(
        self,
        body: str,
        *,
        path: tuple[str, ...],
        stack: ScopeStack,
    ) -> Any:
        if body in DEFERRED_RUNTIME_TOKENS:
            if self._runtime is None:
                return f"${{{body}}}"
            value = self._runtime.get(body)
            return "" if value is None else value

        if ":" in body:
            head, _, tail = body.partition(":")
            head = head.strip()
            tail = tail.strip()
            if head == "env":
                return self._env.get(tail, _MISSING)
            if head == "alias":
                return self._resolve_alias(tail, path=path, stack=stack)
            raise InterpolationError(f"unknown resolver: {head!r}")

        # Relative lookups are anchored to the *node currently being
        # resolved*, not to scope frames.  ``path`` points at the
        # string value itself so the parent mapping sits at path[:-1].
        if body.startswith(".."):
            return self._lookup_path(path[:-2], body[2:], allow_missing=True)
        if body.startswith("."):
            return self._lookup_path(path[:-1], body[1:], allow_missing=True)

        return self._lookup_absolute(body)

    def _resolve_alias(
        self,
        name: str,
        *,
        path: tuple[str, ...],
        stack: ScopeStack,
    ) -> Any:
        if not name:
            raise InterpolationError("alias lookup with empty name")
        if name in RESERVED_ALIAS_NAMES:
            raise InterpolationError(
                f"alias {name!r} shadows reserved name "
                f"(one of {sorted(RESERVED_ALIAS_NAMES)})"
            )
        raw = stack.resolve_alias(name)
        if raw is None:
            return _MISSING
        if name in self._in_flight_aliases:
            raise InterpolationError(f"cyclic alias reference: {name!r}")
        # Alias values are themselves interpolable; re-enter with the
        # declaring frame as the scope context so ${.x} inside an alias
        # resolves against the declarer, not the caller.
        self._in_flight_aliases.add(name)
        try:
            return self._walk(copy.deepcopy(raw), path=path, stack=stack)
        finally:
            self._in_flight_aliases.discard(name)

    def _lookup_absolute(self, dotted: str) -> Any:
        assert self._root is not None, "compile() must be active"
        target = tuple(p for p in dotted.split(".") if p != "")
        return self._lookup_path((), ".".join(target), allow_missing=True)

    def _lookup_path(
        self,
        base_path: tuple[str, ...],
        rel: str,
        *,
        allow_missing: bool,
    ) -> Any:
        assert self._root is not None
        parts = [p for p in rel.split(".") if p != ""]
        full_path = base_path + tuple(parts)

        if full_path in self._in_flight:
            raise InterpolationError(
                f"cyclic reference: {'.'.join(full_path)}"
            )

        self._in_flight.append(full_path)
        try:
            node: Any = self._root
            for part in full_path:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                elif isinstance(node, list):
                    try:
                        node = node[int(part)]
                    except (ValueError, IndexError):
                        return _MISSING if allow_missing else None
                else:
                    return _MISSING if allow_missing else None

            # Recursively resolve the looked-up subtree so nested
            # ${...} inside the target get materialised into the
            # returned value.
            if isinstance(node, (dict, list, str)):
                stack = ScopeStack()
                root_aliases = self._root.get("aliases") if isinstance(self._root, dict) else None
                stack.push(ScopeFrame(
                    path=full_path[:-1] if full_path else (),
                    aliases=root_aliases if isinstance(root_aliases, dict) else {},
                ))
                return self._walk(copy.deepcopy(node), path=full_path, stack=stack)
            return node
        finally:
            self._in_flight.pop()


def _split_default(expr: str) -> tuple[str, str | None]:
    """Split ``expr`` into ``(body, default)`` at the ``:-`` separator.

    Only the *last* ``:-`` counts so ``${env:VAR:-fallback}`` parses as
    ``body="env:VAR"``, ``default="fallback"``.
    """
    idx = expr.rfind(":-")
    if idx == -1:
        return expr, None
    return expr[:idx].rstrip(), expr[idx + 2 :]
