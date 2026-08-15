"""
Plugin Services - Core plugin communication API.

S40 surface:
- create_job(input_value, input_data) -> job_id
- read_state(path=None)
- update_state(patch, mode='merge'|'replace')
- services.jobid

Deprecated (warn-once, S41 hard delete):
- update_job, update_plugin, get_* getters, current_* / run_id / mode
"""

import warnings
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from archiverr.core.render import ConfigRenderEngine
    from archiverr.events import EventBus
    from archiverr.state.manager import GlobalStateManager
    from archiverr.utils.debug import Debugger


class PluginServices:
    """Controlled access to state management for plugins."""

    def __init__(
        self,
        state: 'GlobalStateManager',
        event_bus: 'EventBus',
        logger: 'Debugger',
        config: dict[str, Any],
        mode: str,  # "per_run" or "per_job"
        current_job_id: str | None = None,
        current_plugin_name: str | None = None,
        provides_registry: 'Any' = None,
        run_safety: dict[str, bool] | None = None,
        render_engine: 'ConfigRenderEngine | None' = None,
    ):
        """
        Initialize Plugin Services.

        Args:
            state: GlobalStateManager instance
            event_bus: EventBus instance
            logger: Debugger instance
            config: Frozen config
            mode: "per_run" or "per_job"
            current_job_id: Current job ID (per_job only)
            current_plugin_name: Current plugin name (per_job only)
            provides_registry: Optional ProvidesRegistry for early completion
            run_safety: Resolved run-scope safety flags
                ({"dry_run", "hardlink", "no_delete"}). Required - must be
                resolved once at run start by the orchestrator via
                ``core.safety.resolve_run_safety``.
            render_engine: Optional ``ConfigRenderEngine`` instance
                (S39 R15 §H2). When provided, plugins can call
                ``services.get_runtime_config()`` to get their config
                block rendered against the live template context. When
                None (test fixtures, stub paths), ``get_runtime_config``
                falls back to returning the raw frozen config block.
        """
        self._state = state
        self._event_bus = event_bus
        self._logger = logger
        self._config = config
        self._mode = mode
        self._current_job_id = current_job_id
        self._current_plugin_name = current_plugin_name
        self._provides_registry = provides_registry
        self._run_safety = run_safety
        self._render_engine = render_engine
        self._event_service = None
        self._deprecation_warned: set[str] = set()

    @property
    def jobid(self) -> str | None:
        """Orchestrator-injected current job id. None for per_run plugins."""
        return self._current_job_id

    def _warn_deprecated(self, name: str, replacement: str) -> None:
        if name in self._deprecation_warned:
            return
        self._deprecation_warned.add(name)
        warnings.warn(
            f"services.{name} is deprecated (S40); use {replacement}. "
            "Hard-deleted in S41.",
            DeprecationWarning,
            stacklevel=3,
        )

    def read_state(self, path: str | None = None) -> Any:
        """Read the run snapshot. Optional dotted path projection."""
        return self._state.read_state(path)

    def update_state(
        self,
        patch: dict[str, Any],
        mode: Literal["merge", "replace"] = "merge",
    ) -> None:
        """RFC 7396 merge (default) or subtree replace into the run snapshot."""
        self._state.apply_state_patch(patch, mode=mode)
        self._logger.debug(
            "plugin_services",
            "update_state",
            mode=mode,
            keys=list(patch.keys()) if isinstance(patch, dict) else [],
            jobid=self._current_job_id,
            plugin=self._current_plugin_name,
        )

    def create_job(self, input_value: str, input_data: dict[str, Any] = None) -> str:
        """
        Create new job.
        
        Args:
            input_value: Job input (path, query, etc.)
            input_data: Plugin-specific data
            
        Returns:
            Job ID
        """
        job_id = self._state.create_job(
            input_value=input_value,
            input_data=input_data or {}
        )

        self._logger.debug(
            "plugin_services",
            f"Created job: {job_id}",
            mode=self._mode,
            input_value=input_value
        )

        return job_id

    def update_job(self, job_id: str = None, key: str = None, value: Any = None) -> None:
        """Deprecated S40 stub. Use ``update_state``."""
        self._warn_deprecated("update_job", "services.update_state")
        target_job_id = job_id or self._current_job_id
        if not target_job_id:
            raise ValueError("No job ID specified and no current job context")

        self._state.update_job(target_job_id, key, value)

        self._logger.debug(
            "plugin_services",
            f"Updated job: {target_job_id}",
            key=key,
            plugin=self._current_plugin_name
        )

    def update_plugin(self, target_id: str = None, plugin_name: str = None, data: dict[str, Any] = None) -> None:
        """Deprecated S40 stub. Use ``update_state``."""
        self._warn_deprecated("update_plugin", "services.update_state")
        tid = target_id or self._current_job_id
        pname = plugin_name or self._current_plugin_name

        if not tid:
            raise ValueError("No target_id specified and no current context")
        if not pname:
            raise ValueError("No plugin_name specified and no current context")

        self._state.update_plugin(tid, pname, data or {})

        self._logger.debug(
            "plugin_services",
            f"Updated plugin: {pname}",
            target_id=tid,
            data_keys=list(data.keys()) if data else []
        )

    def get_plugin_data(self, target_id: str, plugin_name: str) -> dict[str, Any] | None:
        """Deprecated S40 stub. Use ``read_state``."""
        self._warn_deprecated("get_plugin_data", "services.read_state")
        return self._state.get_plugin_data(target_id, plugin_name)

    def get_run(self):
        """Deprecated S40 stub. Use ``read_state``."""
        self._warn_deprecated("get_run", "services.read_state")
        return self._state.run

    def get_config(self) -> dict[str, Any]:
        """Deprecated S40 stub. Use ``read_state('config')`` or get_runtime_config."""
        self._warn_deprecated("get_config", "services.read_state")
        return self._config

    def get_runtime_config(self, plugin_name: str | None = None) -> dict[str, Any]:
        """Return the plugin's config block rendered against the live context.

        S39 R15 §H3 — the "config canlı playground" entry point. Plugins call
        this to read their own config with Jinja markers resolved against the
        active run/job state, instead of inspecting ``self.config`` (which
        was frozen at construction-time before any state existed). Plain
        string values pass through unchanged; only strings containing
        ``{{`` or ``{%`` trigger a render pass.

        Args:
            plugin_name: Plugin name. Defaults to the current plugin set on
                this services instance.

        Returns:
            Rendered config dict for the plugin (empty dict if the plugin
            has no config block). When the engine is not wired (test
            fixtures), returns the raw frozen config block.
        """
        pname = plugin_name or self._current_plugin_name
        if not pname:
            raise ValueError("No plugin_name and no current plugin context")

        plugins_block = self._config.get('plugins', {}) if isinstance(self._config, dict) else {}
        plugin_config = plugins_block.get(pname, {}) if isinstance(plugins_block, dict) else {}
        if not isinstance(plugin_config, dict):
            return plugin_config

        from archiverr.core.config.interpolator import apply_runtime_tokens
        plugin_config = apply_runtime_tokens(
            plugin_config, {"jobid": self._current_job_id},
        )
        if not isinstance(plugin_config, dict):
            return plugin_config

        if self._render_engine is None:
            # No engine wired (stub / test fixture) — return interpolated block.
            return plugin_config

        ctx = self._build_render_context()
        return self._render_engine.render_value(plugin_config, ctx)

    def _build_render_context(self) -> dict[str, Any]:
        """Build the Jinja context for ``get_runtime_config`` (S39 R15 §H3).

        Reuses ``TemplateContextBuilder`` for the per_job branch so the
        shape is identical to what tasker / config-render consumers see.
        For per_run plugins (no active job), constructs a minimal context
        with the same top-level keys but empty ``job`` / ``jobs`` and a
        synthesised ``job_id=None`` / ``job_index=None`` so chain access
        still resolves gracefully under ChainableUndefined.
        """
        from archiverr.state.template_context import TemplateContextBuilder

        run = self._state.run if hasattr(self._state, 'run') else None
        all_jobs = list(self._state.jobs) if hasattr(self._state, 'jobs') else []
        events = {}
        if self._event_bus is not None:
            try:
                events = self._event_bus.get_history_dict()
            except Exception:  # noqa: BLE001 — events are auxiliary
                events = {}

        current_job = self._state.job if hasattr(self._state, 'job') else None
        if current_job is not None:
            ctx = TemplateContextBuilder().build_job_context(
                current_job, run=run, all_jobs=all_jobs, events=events,
            )
            ctx["jobid"] = getattr(current_job, "id", None)
            return ctx

        # per_run scope — no active job. Mirror the top-level shape but
        # OMIT ``job_id`` / ``job_index`` so ChainableUndefined renders
        # them to "" gracefully (instead of the literal string "None"
        # that we'd get if we explicitly set the keys to ``None``).
        run_proj = (
            {
                "id": run.id,
                "status": {
                    "success": run.status.success,
                    "total_jobs": run.status.total_jobs,
                    "completed": run.status.completed,
                    "failed": run.status.failed,
                },
                "config": run.config,
            }
            if run is not None
            else {"id": "", "status": {}, "config": {}}
        )
        return {
            "run": run_proj,
            "job": {},
            "jobs": {},
            "config": run.config if run is not None else self._config,
            "options": (run.config.get('options', {}) if run is not None else {}),
            "events": events,
            "data": getattr(run, 'data', {}) if run is not None else {},
        }

    def get_current_job(self):
        """Deprecated S40 stub. Use ``read_state`` + ``services.jobid``."""
        self._warn_deprecated("get_current_job", "services.read_state")
        return self._state.job

    def get_all_jobs(self):
        """Deprecated S40 stub. Use ``read_state('jobs')``."""
        self._warn_deprecated("get_all_jobs", "services.read_state")
        return self._state.jobs

    def get_current_plugins(self) -> dict[str, Any]:
        """Deprecated S40 stub. Use ``read_state``."""
        self._warn_deprecated("get_current_plugins", "services.read_state")
        return self._state.plugin

    def get_all_plugins(self):
        """Deprecated S40 stub. Use ``read_state``."""
        self._warn_deprecated("get_all_plugins", "services.read_state")
        return self._state.plugins

    @property
    def render_engine(self):
        """Shared core ``ConfigRenderEngine`` (S39 R15 §H2/§H3).

        Plugins that need to render arbitrary template strings (e.g.
        tasker rendering each task's ``template`` / ``condition`` field)
        consume this property instead of importing ``jinja2`` themselves.
        Returns ``None`` when the engine was not wired (test fixtures);
        callers should handle that branch (treat as render-disabled or
        instantiate their own).
        """
        return self._render_engine

    @property
    def mode(self) -> str:
        """Deprecated S40 stub. Plugin reads ``self.manifest.run_mode``."""
        self._warn_deprecated("mode", "self.manifest.run_mode")
        return self._mode

    @property
    def current_job_id(self) -> str | None:
        """Deprecated S40 stub. Use ``services.jobid``."""
        self._warn_deprecated("current_job_id", "services.jobid")
        return self._current_job_id

    @property
    def current_plugin_name(self) -> str | None:
        """Deprecated S40 stub. Plugin uses ``self.name``."""
        self._warn_deprecated("current_plugin_name", "self.name")
        return self._current_plugin_name

    @property
    def run_id(self) -> str | None:
        """Deprecated S40 stub. Use ``read_state('id')``."""
        self._warn_deprecated("run_id", "services.read_state('id')")
        run = self._state.run
        return run.id if run else None

    @property
    def provides(self):
        """Get provides service for early completion.

        Allows plugins to mark individual provides as completed during execution:
            services.provides.complete("http.request")
            services.provides.is_completed("http.request")

        Raises:
            PluginError: If provides_registry was not wired at construction.
        """
        if self._provides_registry is None:
            from archiverr.core.exceptions import PluginError
            raise PluginError(
                "services.provides accessed without provides_registry wiring. "
                "Executor must construct PluginServices with provides_registry=... "
                f"(plugin={self._current_plugin_name or 'unknown'}, mode={self._mode})"
            )
        from archiverr.core.services.provides_service import ProvidesServiceImpl
        return ProvidesServiceImpl(self._provides_registry, self._current_plugin_name or "unknown")

    @property
    def events(self):
        """Read-only EventService.

        Plugins can ``has_fired(name)``, ``history(name)``, or
        ``snapshot()`` the event bus, but cannot emit or subscribe
        (that surface lives on the executor / lifecycle hooks only).
        """
        if self._event_bus is None:
            from archiverr.core.exceptions import PluginError
            raise PluginError(
                "services.events accessed without event_bus wiring "
                f"(plugin={self._current_plugin_name or 'unknown'}, mode={self._mode})"
            )
        if self._event_service is None:
            from archiverr.core.services.event_service import EventServiceImpl
            self._event_service = EventServiceImpl(self._event_bus)
        return self._event_service

    @property
    def run_safety(self) -> dict[str, bool]:
        """Resolved run-scope safety flags.

        Returns the dict produced by ``core.safety.resolve_run_safety``
        with keys ``dry_run``, ``hardlink``, ``no_delete``. Plugins must
        read these instead of poking at ``config['options']`` directly so
        the orchestrator stays the single source of truth.
        """
        if self._run_safety is None:
            from archiverr.core.exceptions import PluginError
            raise PluginError(
                "services.run_safety accessed without wiring. "
                "Executor must construct PluginServices with run_safety=... "
                f"(plugin={self._current_plugin_name or 'unknown'}, mode={self._mode})"
            )
        return dict(self._run_safety)
