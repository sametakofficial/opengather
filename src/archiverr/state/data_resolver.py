"""Data namespace resolver — priority-based plugin lookup.

S39 R15 §D1 — implements the ``data.<jobindex>.<category>.<dotted.path>``
resolver that lets operators pick which plugin "wins" for any given
path via a single ``data_priority`` config block, instead of hand-
rolling ``{% if jobs[job_id].plugins.tmdb.show.title %}...{% else %}
{{ jobs[job_id].plugins.omdb.show.title }}{% endif %}`` ladders.

How it fits together
=====================

* ``data_priority`` lives in config.yml (D5) as
  ``dict[str, list[str]]`` mapping a path-pattern to an ordered list
  of plugin names. The longest-prefix match wins.

* Plugins declare what they emit in ``manifest.emits`` (Phase A).
  The resolver consumes ``emits`` to verify a configured priority
  entry actually has a plugin that can satisfy it; warnings happen
  in ``registry`` (D4).

* For each lookup ``resolve(state, dotted_path)`` walks the priority
  table from longest matching prefix to shortest, asks each plugin
  in the priority list for the path under its data block, and
  returns the first non-None hit.

* ``DataResolverProxy`` wraps the resolver in a Jinja-friendly object
  exposing ``__getattr__`` and ``__getitem__``. The render context
  exposes ``"data"`` as such a proxy so templates can write
  ``{{ data.0.show.title.primary }}``, ``{{ data.run.scanner.count }}``
  etc.

Path grammar
------------

* ``data.<jobindex>.<category>.<dotted.path>`` — looks up under the
  given job's plugin data. ``<jobindex>`` is substituted with the
  active job's index from ``state.context._current_job.index``.
* ``data.run.<category>.<dotted.path>`` — looks up under per_run
  plugin data (``run.plugins.<plugin>``).
* The literal token ``<jobindex>`` in priority patterns is a
  SENTINEL substituted at lookup time; do not write a literal job
  index in priority keys.
"""

from typing import Any, Callable, Iterable


# -----------------------------------------------------------------------------
# DataResolver — pure logic, no Jinja knowledge.
# -----------------------------------------------------------------------------


class DataResolver:
    """Priority-aware lookup over the plugin data envelope.

    The resolver knows nothing about Jinja or even the state
    structure beyond two arrows it borrows from the caller:

    * ``priority``: the ``data_priority`` map, e.g.
      ``{"data.<jobindex>.show": ["tmdb", "omdb", "tvmaze"]}``
    * ``plugin_data_for(scope, plugin_name)``: a callable that
      returns the data dict for a plugin under either ``"run"`` or
      a specific job index. The state manager owns this lookup;
      the resolver doesn't reach into state itself, which keeps
      the class pure-functional and testable.

    The active job index is supplied per ``resolve()`` call so the
    same resolver instance can serve every template render in a
    multi-job run without thread-local state.
    """

    def __init__(
        self,
        priority: dict[str, list[str]] | None = None,
        run_modes: dict[str, str] | None = None,
    ):
        # We keep a normalised view: every priority key has its
        # dotted segments split once, which makes longest-prefix
        # matching cheap and avoids re-splitting on every lookup.
        self._priority_raw = dict(priority or {})
        self._run_modes = dict(run_modes or {})

    @property
    def priority(self) -> dict[str, list[str]]:
        """Raw priority map (read-only view)."""
        return dict(self._priority_raw)

    # -- core lookup ----------------------------------------------------

    def resolve(
        self,
        dotted_path: str,
        plugin_data_for: Callable[[str | int, str], Any],
        active_job_index: int | None = None,
    ) -> Any:
        """Resolve a single dotted path against the priority table.

        Args:
            dotted_path: Lookup, e.g. ``"data.<jobindex>.show.title.primary"``,
                ``"data.0.show.title.primary"``, ``"data.run.scanner.count"``.
                The ``data.`` prefix is optional but recommended for
                clarity; it is stripped before matching.
            plugin_data_for: ``(scope, plugin_name) -> dict | None``.
                Called once per candidate plugin in the priority
                list. Caller decides how to source it (state manager,
                test stub, etc.).
            active_job_index: Used to substitute the ``<jobindex>``
                sentinel in priority keys and in dotted_path itself
                when present.

        Returns:
            The leaf value, or None when no plugin in any matching
            priority entry has data at this path.
        """
        norm_path = self._strip_data_prefix(dotted_path)
        if not norm_path:
            return None

        scope, category_path = self._split_scope(norm_path, active_job_index)
        if category_path == "" and scope is None:
            return None
        if scope is None and category_path:
            # Category-only lookup: pick scope from candidates' run_mode.
            candidates = self._candidates_for_path(category_path, active_job_index)
            if not candidates:
                return None
            return self._first_hit(
                candidates, category_path, plugin_data_for, active_job_index,
            )

        if scope is None:
            return None

        candidates = self._candidates_for_path(category_path, active_job_index)
        if not candidates:
            return None

        return self._first_hit_in_scope(
            candidates, scope, category_path, plugin_data_for,
        )

    def _first_hit_in_scope(
        self,
        candidates: list[str],
        scope: str | int,
        category_path: str,
        plugin_data_for: Callable[[str | int, str], Any],
    ) -> Any:
        for plugin_name in candidates:
            block = plugin_data_for(scope, plugin_name)
            if not isinstance(block, dict):
                continue
            value = _walk_dotted(block, category_path)
            if value is not None:
                return value
        return None

    def _first_hit(
        self,
        candidates: list[str],
        category_path: str,
        plugin_data_for: Callable[[str | int, str], Any],
        active_job_index: int | None,
    ) -> Any:
        """Resolve when the caller omitted the scope segment."""
        for plugin_name in candidates:
            mode = self._run_modes.get(plugin_name, "per_job")
            if mode == "per_run":
                scope: str | int = "run"
            elif active_job_index is None:
                continue
            else:
                scope = active_job_index
            block = plugin_data_for(scope, plugin_name)
            if not isinstance(block, dict):
                continue
            value = _walk_dotted(block, category_path)
            if value is not None:
                return value
        return None

    # -- internals ------------------------------------------------------

    @staticmethod
    def _strip_data_prefix(path: str) -> str:
        if path.startswith("data."):
            return path[len("data."):]
        if path == "data":
            return ""
        return path

    @staticmethod
    def normalize_priority_key(key: str) -> str:
        """Strip ``data.`` and optional ``<jobindex>`` / ``run`` scope heads.

        S40 category-only keys (``show``, ``movie``, ``show.episode_title``)
        pass through. Legacy S39 keys stay accepted.
        """
        stripped = DataResolver._strip_data_prefix(key)
        if not stripped:
            return ""
        head, _, rest = stripped.partition(".")
        if head in ("<jobindex>", "run") and rest:
            return rest
        try:
            int(head)
        except ValueError:
            return stripped
        return rest

    @staticmethod
    def _split_scope(
        norm_path: str,
        active_job_index: int | None,
    ) -> tuple[str | int | None, str]:
        """Split an optional ``<jobindex|run|int>.<rest>`` into ``(scope, rest)``.

        Category-only paths (``show.title``) return ``(None, full_path)``
        so ``resolve`` can auto-route from ``run_modes``.
        """
        parts = norm_path.split(".", 1)
        head = parts[0]
        rest = parts[1] if len(parts) == 2 else ""
        if not head:
            return None, ""
        if head == "run":
            return "run", rest
        if head == "<jobindex>":
            if active_job_index is None:
                return None, ""
            return active_job_index, rest
        try:
            return int(head), rest
        except ValueError:
            return None, norm_path

    def _candidates_for_path(
        self,
        category_path: str,
        active_job_index: int | None,
    ) -> list[str]:
        """Return plugin candidates for the longest matching prefix.

        Iterates priority keys ordered by descending segment length so
        the most specific match wins. Sentinel ``<jobindex>`` in keys
        is matched against the resolver's job-scoped key form.
        """
        if not category_path:
            return []

        scored: list[tuple[int, str, list[str]]] = []
        for key, plugins in self._priority_raw.items():
            key_rest = self.normalize_priority_key(key)
            if not key_rest:
                continue
            scored.append((_segment_count(key_rest), key_rest, list(plugins or [])))

        scored.sort(key=lambda triple: triple[0], reverse=True)
        for _, key_rest, plugins in scored:
            if _is_prefix(key_rest, category_path):
                return plugins
        return []


# -----------------------------------------------------------------------------
# DataResolverProxy — Jinja-facing wrapper for ``{{ data.0.show.title }}``.
# -----------------------------------------------------------------------------


class DataResolverProxy:
    """Lazy proxy exposed to Jinja templates as ``data``.

    On ``__getattr__`` / ``__getitem__`` we accumulate path segments
    and only call into ``DataResolver`` when the chain is consumed
    (str-cast, comparison, equality, iteration). This preserves the
    optimistic descent ergonomic — missing leaves render to "" via
    ``ChainableUndefined`` after the lookup returns None.
    """

    __slots__ = ("_resolver", "_plugin_data_for", "_active_index", "_segments")

    def __init__(
        self,
        resolver: DataResolver,
        plugin_data_for: Callable[[str | int, str], Any],
        active_index: int | None,
        segments: tuple[str, ...] = (),
    ):
        self._resolver = resolver
        self._plugin_data_for = plugin_data_for
        self._active_index = active_index
        self._segments = segments

    def _step(self, segment: str) -> "DataResolverProxy":
        return DataResolverProxy(
            self._resolver,
            self._plugin_data_for,
            self._active_index,
            self._segments + (str(segment),),
        )

    # Attribute access — used by Jinja for the dotted form.
    def __getattr__(self, name: str) -> "DataResolverProxy":
        if name.startswith("_"):
            raise AttributeError(name)
        return self._step(name)

    # Item access — used by Jinja when the segment is dynamic
    # (``data[job_index].show.title``).
    def __getitem__(self, key: Any) -> "DataResolverProxy":
        return self._step(key)

    # Resolve to the actual value when the chain is consumed.
    def _resolved(self) -> Any:
        if not self._segments:
            return None
        path = ".".join(self._segments)
        return self._resolver.resolve(
            f"data.{path}",
            self._plugin_data_for,
            active_job_index=self._active_index,
        )

    def __str__(self) -> str:
        value = self._resolved()
        return "" if value is None else str(value)

    def __repr__(self) -> str:
        return f"DataResolverProxy(segments={'.'.join(self._segments)!r})"

    def __bool__(self) -> bool:
        return bool(self._resolved())

    def __eq__(self, other: object) -> bool:
        return self._resolved() == other

    def __ne__(self, other: object) -> bool:
        return self._resolved() != other

    def __iter__(self):
        value = self._resolved()
        if value is None:
            return iter(())
        return iter(value)

    def __len__(self) -> int:
        value = self._resolved()
        if value is None:
            return 0
        try:
            return len(value)
        except TypeError:
            return 0


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _walk_dotted(block: dict, dotted: str) -> Any:
    """Walk a dict following dotted segments. Return None on miss."""
    if not dotted:
        return block
    cursor: Any = block
    for segment in dotted.split("."):
        if isinstance(cursor, dict):
            cursor = cursor.get(segment)
        else:
            return None
        if cursor is None:
            return None
    return cursor


def _segment_count(path: str) -> int:
    return 0 if not path else len(path.split("."))


def _is_prefix(prefix: str, full: str) -> bool:
    if not prefix:
        return True
    if prefix == full:
        return True
    return full.startswith(prefix + ".")
