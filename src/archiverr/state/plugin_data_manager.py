"""Plugin Data Manager - Extracted from GlobalStateManager.

This module handles plugin data operations.
Follows Single Responsibility Principle by separating plugin data
management from state management.

S39 R15 §D3 — additions:

* ``threading.Lock`` guards ``_recompute_data_envelope`` so concurrent
  per_job stage workers can't interleave half-baked envelopes.
* New ``set_resolver_config(data_priority, emits_map)`` setter; called
  once per run by ``GlobalStateManager.configure_resolver`` after the
  registry exposes its data_priority + emits view.
* Every ``_update_run_plugin`` and ``_update_job_plugin`` call now
  triggers ``_recompute_data_envelope(run)`` which materialises the
  resolved values under ``run.data``. The DataResolverProxy still
  serves live render lookups; the envelope is the persistence
  snapshot the Mongo writer reads.
* Audit blocker H12 fix: ``_update_job_plugin`` now also calls
  ``persistence.save_run(run)`` so the data envelope is persisted
  alongside ``runs.data`` (it was previously only saved during
  ``_update_run_plugin``).
"""

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .context import ExecutionContext
    from .event_emitter import StateEventEmitter
    from .models import RunState
    from .persistence_delegate import PersistenceDelegate

from archiverr.events import Events

from .data_resolver import DataResolver


class PluginDataManager:
    """Manages plugin data operations.

    Extracted from GlobalStateManager to follow SRP. Handles plugin
    data updates, retrieval, and persistence — and (S39 §D3) the
    eager recomputation of the data resolver envelope on every
    write.
    """

    def __init__(
        self,
        context: 'ExecutionContext',
        persistence: 'PersistenceDelegate',
        event_emitter: 'StateEventEmitter' = None,
        logger=None
    ):
        self._context = context
        self._persistence = persistence
        self._event_emitter = event_emitter
        self._log = logger or self._noop_log

        # S39 §D3 — resolver wiring (set lazily; defaults to empty so
        # _recompute_data_envelope is a no-op until configured).
        self._data_priority: dict[str, list[str]] = {}
        self._emits_map: dict[str, dict[str, list[str]]] = {}
        self._envelope_lock = threading.Lock()

    def _noop_log(self, level: str, component: str, message: str, **kwargs):
        """No-op logger when none provided."""
        pass

    def _emit(self, event_name: str, data: dict[str, Any] = None):
        """Emit event if event emitter is configured."""
        if self._event_emitter:
            self._event_emitter.emit(event_name, data)

    # -- Resolver wiring (S39 §D3) -------------------------------------

    def set_resolver_config(
        self,
        data_priority: dict[str, list[str]],
        emits_map: dict[str, dict[str, list[str]]],
    ) -> None:
        """Configure the data envelope recomputation inputs.

        Called once per run by ``GlobalStateManager.configure_resolver``
        after the registry has loaded plugins (and therefore knows the
        ``emits`` block from each manifest) and after the orchestrator
        has the merged config (and therefore the ``data_priority``).
        """
        self._data_priority = dict(data_priority or {})
        self._emits_map = dict(emits_map or {})

    # -- Public update_plugin -------------------------------------------

    def update_plugin(
        self,
        target_id: str,
        plugin_name: str,
        data: dict[str, Any],
        run: 'RunState' = None,
        get_job_func=None
    ) -> None:
        """Update plugin data for a job or run target."""
        # Determine if this is a run or job target
        is_run_target = target_id.startswith("run_") or (run and target_id == run.id)

        if is_run_target:
            self._update_run_plugin(target_id, plugin_name, data, run)
        else:
            self._update_job_plugin(target_id, plugin_name, data, get_job_func, run)

        self._emit(Events.PLUGIN_UPDATED, {
            "target_id": target_id,
            "plugin_name": plugin_name,
            "data": data
        })

    # -- Internals ------------------------------------------------------

    def _update_run_plugin(
        self,
        target_id: str,
        plugin_name: str,
        data: dict[str, Any],
        run: 'RunState'
    ) -> None:
        """Update per-run plugin data."""
        run_id = target_id if target_id.startswith("run_") else f"run_{target_id}"

        if run:
            # Store directly in RunState.plugins (canonical embedded surface)
            run.plugins[plugin_name] = data

            # Store in unified context plugins map
            self._context._all_plugins.setdefault(run_id, {})[plugin_name] = data

            # S39 §D3: refresh data envelope BEFORE persisting.
            self._recompute_data_envelope(run)

            # Persist via canonical save_run (runs.plugins + runs.data embedded)
            self._persistence.save_run(run)

        self._log("debug", "plugin_data",
                 f"Updated run plugin {plugin_name}",
                 run_id=run_id,
                 data_keys=list(data.keys()) if isinstance(data, dict) else [])

    def _update_job_plugin(
        self,
        job_id: str,
        plugin_name: str,
        data: dict[str, Any],
        get_job_func,
        run: 'RunState | None' = None,
    ) -> None:
        """Update per-job plugin data."""
        job = get_job_func(job_id) if get_job_func else None

        if job:
            job.plugins[plugin_name] = data

            # Store in unified context plugins map
            self._context._all_plugins.setdefault(job_id, {})[plugin_name] = data

            # Keep current job plugin view in sync
            if self._context._current_job and self._context._current_job.id == job_id:
                self._context._current_plugins = job.plugins

            # Save plugin document (legacy per-plugin collection)
            plugin_doc = {
                "job_id": job_id,
                "plugin_name": plugin_name,
                "data": data,
                "run_id": job.run_id,
                "job_index": job.index
            }
            self._persistence.save_plugin(plugin_doc)

            # S39 §D3 (audit H12 fix): a per_job plugin write also
            # invalidates the run.data envelope. Recompute and call
            # ``save_run`` so the envelope persists alongside runs.data.
            if run is not None:
                self._recompute_data_envelope(run)
                self._persistence.save_run(run)

            self._log("debug", "plugin_data",
                     f"Updated plugin {plugin_name} for job {job_id}",
                     data_keys=list(data.keys()) if isinstance(data, dict) else [],
                     data_size=len(str(data)))

    # -- Data envelope (S39 §D3) ---------------------------------------

    def _recompute_data_envelope(self, run: 'RunState | None') -> None:
        """Materialise resolver-priority view under ``run.data``.

        For every priority key in ``data_priority`` we iterate the
        scope (``<jobindex>`` -> every known job; ``run`` -> the
        run-scope branch) and the emit paths declared by the
        candidate plugins, asking the resolver for each path. The
        first non-None hit per (scope, path) is stored in a nested
        dict under ``run.data``.

        Empty inputs are a no-op: when ``data_priority`` is empty
        (e.g. at run start before configure_resolver is called, or
        when the operator simply doesn't use the data namespace),
        we leave ``run.data`` untouched.

        Thread-safety: the recompute is wrapped in
        ``self._envelope_lock`` so two parallel-group workers can't
        interleave writes. Each worker rebuilds the FULL envelope
        rather than diffing — simpler and safe; the priority table
        is small (typically <20 keys) and emit lists short.
        """
        if run is None:
            return
        if not self._data_priority:
            return

        with self._envelope_lock:
            resolver = DataResolver(self._data_priority)
            new_envelope: dict[str | int, Any] = {}

            for priority_key, _plugin_list in self._data_priority.items():
                stripped = priority_key
                if stripped.startswith("data."):
                    stripped = stripped[len("data."):]
                if not stripped:
                    continue

                if "." in stripped:
                    scope_segment, category_path = stripped.split(".", 1)
                else:
                    scope_segment, category_path = stripped, ""
                if not category_path:
                    continue

                cat_root = category_path.split(".", 1)[0]

                # Collect emit paths from candidate plugins under cat_root.
                paths: set[str] = set()
                for plugin_name in _plugin_list:
                    emits = self._emits_map.get(plugin_name) or {}
                    if not isinstance(emits, dict):
                        continue
                    if cat_root not in emits:
                        continue
                    for emit_path in emits[cat_root]:
                        # Compose category-relative dotted path.
                        full = f"{cat_root}.{emit_path}" if emit_path else cat_root
                        paths.add(full)

                # Determine which scopes to walk.
                scopes: list[str | int] = []
                if scope_segment == "<jobindex>":
                    scopes = [j.index for j in self._context._jobs.values()]
                elif scope_segment == "run":
                    scopes = ["run"]
                else:
                    # Direct numeric form — treat as concrete scope.
                    try:
                        scopes = [int(scope_segment)]
                    except ValueError:
                        continue

                lookup = self._build_plugin_data_lookup(run)
                for scope in scopes:
                    for path in paths:
                        full_path = (
                            f"data.<jobindex>.{path}"
                            if scope_segment == "<jobindex>"
                            else f"data.{scope_segment}.{path}"
                        )
                        active_idx = scope if isinstance(scope, int) else None
                        value = resolver.resolve(
                            full_path, lookup, active_job_index=active_idx,
                        )
                        if value is None:
                            continue
                        # Write into new_envelope under [scope][...path].
                        scope_bucket = new_envelope.setdefault(scope, {})
                        cursor = scope_bucket
                        segs = path.split(".")
                        for i, seg in enumerate(segs):
                            if i == len(segs) - 1:
                                cursor[seg] = value
                            else:
                                cursor = cursor.setdefault(seg, {})

            run.data = new_envelope

    def _build_plugin_data_lookup(self, run: 'RunState'):
        """Return ``(scope, plugin_name) -> dict | None`` callable.

        Used by DataResolver. Walks the live state to find a plugin's
        data block under either ``"run"`` (run.plugins.<name>) or a
        numeric job index (jobs[index].plugins.<name>).
        """
        def _lookup(scope, plugin_name):
            if scope == "run":
                return run.plugins.get(plugin_name) if run else None
            job = self._context.get_job_by_index(scope) if isinstance(scope, int) else None
            return job.plugins.get(plugin_name) if job else None
        return _lookup

    # -- Reads ----------------------------------------------------------

    def get_plugin_data(self, target_id: str, plugin_name: str) -> dict[str, Any]:
        """Get plugin data for a target."""
        plugins = self._context._all_plugins.get(target_id, {})
        return plugins.get(plugin_name, {})

    def get_all_plugin_data(self, target_id: str) -> dict[str, dict[str, Any]]:
        """Get all plugin data for a target."""
        return self._context._all_plugins.get(target_id, {})

    def get_plugin_names(self, job_id: str, get_job_func=None) -> list[str]:
        """Get list of all plugins that have data for a job."""
        job = get_job_func(job_id) if get_job_func else None
        if not job:
            return []

        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            return list(job.plugins.keys())

        return []
