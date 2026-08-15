"""
Plugin Registry - Central plugin management

- Phase 4: Unified plugin discovery, loading, and lookup.

Wraps PluginDiscovery and PluginLoader to provide:
- Stage-based plugin organization (input, parse, data, output)
- Lazy loading with caching
- Manifest access
- Topological sorting based on requires/provides
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from archiverr.utils.debug import Debugger, get_debugger

from .discovery import PluginDiscovery
from .loader import PluginLoader


class Stage(Enum):
    """
    Plugin execution stages (3 stages only).

    Order matters - stages execute in this sequence:
    1. PARSE: Filename parsing (renamer)
    2. DATA: External data fetching (tmdb, tvdb)
    3. OUTPUT: Output generation (tasker, reporter)

    Note: INPUT stage removed in .
    Input plugins (scanner) now run as per_run mode outside stages.
    """
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"

    @classmethod
    def from_string(cls, stage_str: str) -> 'Stage':
        """
        Get Stage from string.

        Args:
            stage_str: Stage name ("parse", "data", or "output")

        Returns:
            Stage enum

        Raises:
            ValueError: If stage_str is invalid
        """
        try:
            return cls(stage_str.lower())
        except ValueError as e:
            raise ValueError(
                f"Invalid stage: {stage_str}. "
                f"Valid stages: parse, data, output"
            ) from e


@dataclass
class PluginInfo:
    """Cached plugin information ()"""
    name: str
    stage: Stage | None  # None for per_run plugins
    manifest: dict[str, Any]
    instance: Any | None = None
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)


class PluginRegistry:
    """
    Central registry for plugin discovery, loading, and lookup.

    Usage:
        registry = PluginRegistry(config)
        registry.discover_and_load()

        input_plugins = registry.get_plugins_by_stage(Stage.INPUT)
        tmdb = registry.get_plugin("tmdb")
        manifest = registry.get_manifest("tmdb")

    Note: This class uses mevcut PluginDiscovery and PluginLoader.
    It's a facade that adds stage-based organization.
    """

    def __init__(
        self,
        config: dict[str, Any],
        plugins_dir: str = None,
        debugger: Debugger | None = None
    ):
        """
        Initialize plugin registry.

        Args:
            config: Application configuration dict
            plugins_dir: Optional custom plugins directory
            debugger: Optional debugger instance
        """
        self._config = config
        self._plugins_dir = plugins_dir
        self._debugger = debugger or get_debugger()

        # Lazy-loaded components
        self._discovery: PluginDiscovery | None = None
        self._loader: PluginLoader | None = None

        # Plugin caches
        self._all_manifests: dict[str, dict[str, Any]] = {}
        self._all_plugins: dict[str, Any] = {}
        self._plugins_by_stage: dict[Stage, dict[str, Any]] = {
            stage: {} for stage in Stage
        }
        self._plugin_info: dict[str, PluginInfo] = {}

        self._loaded = False

    def discover_and_load(self) -> None:
        """
        Discover all plugins and load enabled ones.

        This is the main initialization method.
        Call once at startup, results are cached.
        """
        if self._loaded:
            return

        self._debugger.debug("registry", "Starting plugin discovery and load")

        # Initialize discovery
        if self._plugins_dir:
            self._discovery = PluginDiscovery(self._plugins_dir)
        else:
            self._discovery = PluginDiscovery()

        # Discover all plugins (metadata only)
        self._all_manifests = self._discovery.discover()
        self._debugger.debug("registry", f"Discovered {len(self._all_manifests)} plugins")

        if not self._all_manifests:
            self._debugger.warn("registry", "No plugins discovered")
            self._loaded = True
            return

        # WP-2: enrich config['_plugins'] with the 3-layer structure
        # (_manifest / _defaults / user / _resolved) so downstream components
        # read a single canonical shape.
        from archiverr.core.config.manifest_merge import apply_to_config
        apply_to_config(self._config, self._all_manifests)

        # WP-3: resolve ${...} interpolation tokens across the merged tree.
        # On by default in session 34+.  ``options._use_legacy_alias = true``
        # is an escape hatch for users who haven't migrated yet; it skips
        # the new engine but leaves the regex alias path in config_loader
        # untouched either way.
        options = self._config.get("options") or {}
        if not bool(options.get("_use_legacy_alias", False)):
            from archiverr.core.config.interpolator import compile_config
            compiled = compile_config(self._config)
            self._config.clear()
            self._config.update(compiled)

        # Initialize loader with config
        self._loader = PluginLoader(self._all_manifests, self._config)

        # Load enabled plugins by category (using existing system)
        input_plugins = self._loader.load_by_category('input')
        output_plugins = self._loader.load_by_category('output')

        # Store all loaded plugins
        self._all_plugins = {**input_plugins, **output_plugins}

        # Organize by stage (INPUT removed, per_run mode)
        # Input plugins are per_run mode, not assigned to a stage
        for name, instance in input_plugins.items():
            manifest = self._all_manifests.get(name, {})
            # Input plugins don't have a stage in
            # They run as per_run before stages
            self._build_plugin_info(name, None, manifest, instance)

        for name, instance in output_plugins.items():
            manifest = self._all_manifests.get(name, {})
            # Determine stage from manifest (PARSE, DATA, or OUTPUT)
            stage = self._determine_stage(manifest)
            if stage:  # Only add if stage is defined
                self._plugins_by_stage[stage][name] = instance
                self._build_plugin_info(name, stage, manifest, instance)

        self._loaded = True

        self._debugger.info(
            "registry",
            "Plugin registry initialized",
            total=len(self._all_manifests),
            loaded=len(self._all_plugins),
            stages={s.value: len(p) for s, p in self._plugins_by_stage.items() if p}
        )

        # S39 R15 §I1: parse-time WARN scan on every plugin's effective
        # config. We can't fail the load — historical configs may have
        # stale references — but we surface the gap so operators see it.
        self._validate_template_dependencies()

    def _validate_template_dependencies(self) -> None:
        """Walk plugin configs and WARN on undeclared template refs.

        For each plugin's effective (merged) config, parse Jinja
        templates and check the plugins they reference against the
        plugin's ``manifest.requires``. Mismatches produce WARN-level
        log entries on the debugger; the load otherwise proceeds.

        Self-references and references to the plugin itself are
        ignored. References to plugin names not in the registry are
        flagged as a likely typo.
        """
        try:
            from archiverr.core.render import (
                ConfigRenderEngine, validate_plugin_template_refs,
            )
        except Exception as exc:  # noqa: BLE001 — engine optional
            self._debugger.debug(
                "registry",
                "render engine unavailable; skipping template validation",
                error=str(exc),
            )
            return

        engine = ConfigRenderEngine()
        plugins_block = self._config.get('plugins', {}) if isinstance(self._config, dict) else {}
        if not isinstance(plugins_block, dict):
            return

        known_plugins = list(self._all_plugins.keys())
        for plugin_name in known_plugins:
            cfg = plugins_block.get(plugin_name, {}) if isinstance(plugins_block, dict) else {}
            if not isinstance(cfg, dict):
                continue
            manifest = self._all_manifests.get(plugin_name, {})
            requires = manifest.get('requires', []) if isinstance(manifest, dict) else []
            warnings = validate_plugin_template_refs(
                plugin_name=plugin_name,
                plugin_config=cfg,
                declared_requires=requires,
                known_plugins=known_plugins,
                render_engine=engine,
            )
            for w in warnings:
                self._debugger.warn(
                    "registry",
                    "template-dependency mismatch",
                    plugin=w.plugin,
                    references=w.referenced_plugin,
                    location=w.location,
                    detail=w.message,
                )

    def _determine_stage(self, manifest: dict[str, Any]) -> Stage | None:
        stage_str = manifest.get('stage')
        if not stage_str:
            raise ValueError(
                f"Plugin '{manifest.get('name', '?')}': manifest.stage is required "
                f"(one of input, parse, data, output)"
            )
        if stage_str == 'input':
            return None
        try:
            return Stage(stage_str)
        except ValueError as e:
            raise ValueError(
                f"Plugin '{manifest.get('name', '?')}': invalid stage '{stage_str}'"
            ) from e

    def _build_plugin_info(
        self,
        name: str,
        stage: Stage | None,  # None for per_run plugins
        manifest: dict[str, Any],
        instance: Any | None
    ) -> None:
        """Build and cache PluginInfo for a plugin ()."""
        requires = manifest.get('requires', [])
        if isinstance(requires, str):
            requires = [requires]

        # Extract provides
        provides = manifest.get('provides', [])
        if isinstance(provides, str):
            provides = [provides]

        self._plugin_info[name] = PluginInfo(
            name=name,
            stage=stage,
            manifest=manifest,
            instance=instance,
            requires=requires,
            provides=provides
        )

    def get_plugins_by_stage(self, stage: Stage) -> dict[str, Any]:
        """
        Get all loaded plugins for a stage.

        Args:
            stage: Stage enum value

        Returns:
            Dict of plugin_name -> plugin_instance
        """
        if not self._loaded:
            self.discover_and_load()
        return self._plugins_by_stage.get(stage, {})

    def get_plugin(self, name: str) -> Any | None:
        """
        Get a loaded plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None if not loaded
        """
        if not self._loaded:
            self.discover_and_load()
        return self._all_plugins.get(name)

    def get_manifest(self, name: str) -> dict[str, Any] | None:
        """
        Get plugin manifest by name.

        Args:
            name: Plugin name

        Returns:
            Manifest dict or None if not found
        """
        if not self._loaded:
            self.discover_and_load()
        return self._all_manifests.get(name)

    def get_plugin_info(self, name: str) -> PluginInfo | None:
        """
        Get full plugin info by name.

        Args:
            name: Plugin name

        Returns:
            PluginInfo or None if not found
        """
        if not self._loaded:
            self.discover_and_load()
        return self._plugin_info.get(name)

    def get_all_plugins(self) -> dict[str, Any]:
        """
        Get all loaded plugin instances ().

        Returns:
            Dict of plugin_name -> plugin_instance
        """
        if not self._loaded:
            self.discover_and_load()
        return self._all_plugins.copy()

    def get_input_plugin_names(self) -> list[str]:
        """
        Get names of all input plugins (per_run mode, no stage).

        Returns list of plugin names that are input plugins.
        Replaces hardcoded ['scanner', 'file-reader', ...] lists.

        Returns:
            List of input plugin names
        """
        if not self._loaded:
            self.discover_and_load()

        input_plugins = []
        for name, info in self._plugin_info.items():
            # Input plugins have no stage (per_run mode)
            if info.stage is None or info.manifest.get('run_mode') == 'per_run':
                input_plugins.append(name)

        return input_plugins

    def get_all_manifests(self) -> dict[str, dict[str, Any]]:
        """Get all discovered manifests."""
        if not self._loaded:
            self.discover_and_load()
        return self._all_manifests.copy()

    @property
    def data_priority(self) -> dict[str, list[str]]:
        """Top-level ``data_priority`` config block (S39 R15 §D4).

        Returns a copy of the operator-supplied priority map (or an
        empty dict when unset). Consumed by the state manager to
        configure the resolver envelope.
        """
        if not isinstance(self._config, dict):
            return {}
        priority = self._config.get('data_priority')
        if isinstance(priority, dict):
            return dict(priority)
        return {}

    @property
    def emits_map(self) -> dict[str, dict[str, list[str]]]:
        """Aggregated ``manifest.emits`` view across loaded plugins.

        Shape: ``{plugin_name: {<category>: [<dotted.path>, ...]}}``.
        Plugins that didn't declare ``emits`` are absent (not present
        as empty dicts) so the resolver knows they opt out of the
        data namespace.
        """
        if not self._loaded:
            self.discover_and_load()
        out: dict[str, dict[str, list[str]]] = {}
        for name, manifest in self._all_manifests.items():
            if not isinstance(manifest, dict):
                continue
            emits = manifest.get('emits')
            if not isinstance(emits, dict) or not emits:
                continue
            # Defensive shallow copy so callers can't mutate manifests.
            out[name] = {
                cat: list(paths) if isinstance(paths, list) else []
                for cat, paths in emits.items()
            }
        return out

    @property
    def run_modes(self) -> dict[str, str]:
        """``{plugin_name: run_mode}`` from manifests (S40 auto-route)."""
        if not self._loaded:
            self.discover_and_load()
        out: dict[str, str] = {}
        for name, manifest in self._all_manifests.items():
            if not isinstance(manifest, dict):
                continue
            mode = manifest.get("run_mode")
            if mode in ("per_run", "per_job"):
                out[name] = mode
        return out

    def validate_data_priority(self) -> list[str]:
        """Sanity-check ``data_priority`` against loaded plugins (S39 §D4 / S40).

        Returns a list of human-readable WARN strings when:
        * a plugin in a priority list isn't registered (typo / disabled);
        * a plugin in a priority list doesn't declare ``emits`` for the
          path's category root, so it can never satisfy the lookup.

        Category-only keys (``show``, ``movie``) are canonical in S40.
        Legacy ``data.<jobindex>.*`` / ``data.run.*`` keys still work.
        """
        from archiverr.state.data_resolver import DataResolver

        warnings: list[str] = []
        priority = self.data_priority
        if not priority:
            return warnings
        emits = self.emits_map
        known = set(self._all_plugins.keys())
        for key, plugin_list in priority.items():
            if not isinstance(plugin_list, list):
                continue
            category_path = DataResolver.normalize_priority_key(key)
            cat_root = category_path.split(".", 1)[0] if category_path else ""
            if not cat_root:
                continue
            for plugin_name in plugin_list:
                if plugin_name not in known:
                    warnings.append(
                        f"data_priority[{key!r}] lists '{plugin_name}' "
                        "but plugin is not registered (typo or disabled)."
                    )
                    continue
                plugin_emits = emits.get(plugin_name) or {}
                if cat_root not in plugin_emits:
                    warnings.append(
                        f"data_priority[{key!r}] lists '{plugin_name}' "
                        f"but {plugin_name}.manifest.emits has no '{cat_root}' "
                        "category — it cannot satisfy this priority entry."
                    )
        return warnings

    def get_requires(self, name: str) -> list[str]:
        """Get requires list for a plugin."""
        info = self.get_plugin_info(name)
        return info.requires if info else []

    def get_provides(self, name: str) -> list[str]:
        """Get provides list for a plugin."""
        info = self.get_plugin_info(name)
        return info.provides if info else []

    @property
    def total_discovered(self) -> int:
        """Total number of discovered plugins (enabled + disabled)."""
        if not self._loaded:
            self.discover_and_load()
        return len(self._all_manifests)

    @property
    def total_loaded(self) -> int:
        """Total number of loaded (enabled) plugins."""
        if not self._loaded:
            self.discover_and_load()
        return len(self._all_plugins)

    @property
    def enabled_plugins(self) -> list[str]:
        """List of enabled plugin names."""
        if not self._loaded:
            self.discover_and_load()
        return list(self._all_plugins.keys())

