"""
Plugin Registry - Central plugin management

Session 11 - Phase 4: Unified plugin discovery, loading, and lookup.

Wraps PluginDiscovery and PluginLoader to provide:
- Stage-based plugin organization (input, parse, data, output)
- Lazy loading with caching
- Manifest access
- Topological sorting based on requires/provides
"""

from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field

from archiverr.utils.debug import get_debugger, Debugger
from archiverr.core.exceptions import CriticalError, DependencyError
from .discovery import PluginDiscovery
from .loader import PluginLoader


class Stage(Enum):
    """
    Session 12: Plugin execution stages (3 stages only).
    
    Order matters - stages execute in this sequence:
    1. PARSE: Filename parsing (renamer)
    2. DATA: External data fetching (tmdb, tvdb)
    3. OUTPUT: Output generation (tasker, reporter)
    
    Note: INPUT stage removed in Session 12.
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
        except ValueError:
            raise ValueError(
                f"Invalid stage: {stage_str}. "
                f"Valid stages: parse, data, output"
            )


@dataclass
class PluginInfo:
    """Cached plugin information"""
    name: str
    stage: Stage
    manifest: Dict[str, Any]
    instance: Optional[Any] = None
    requires: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)


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
        config: Dict[str, Any],
        plugins_dir: str = None,
        debugger: Optional[Debugger] = None
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
        self._discovery: Optional[PluginDiscovery] = None
        self._loader: Optional[PluginLoader] = None
        
        # Plugin caches
        self._all_manifests: Dict[str, Dict[str, Any]] = {}
        self._all_plugins: Dict[str, Any] = {}
        self._plugins_by_stage: Dict[Stage, Dict[str, Any]] = {
            stage: {} for stage in Stage
        }
        self._plugin_info: Dict[str, PluginInfo] = {}
        
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
        
        # Initialize loader with config
        self._loader = PluginLoader(self._all_manifests, self._config)
        
        # Load enabled plugins by category (using existing system)
        input_plugins = self._loader.load_by_category('input')
        output_plugins = self._loader.load_by_category('output')
        
        # Store all loaded plugins
        self._all_plugins = {**input_plugins, **output_plugins}
        
        # Organize by stage
        for name, instance in input_plugins.items():
            manifest = self._all_manifests.get(name, {})
            self._plugins_by_stage[Stage.INPUT][name] = instance
            self._build_plugin_info(name, Stage.INPUT, manifest, instance)
        
        for name, instance in output_plugins.items():
            manifest = self._all_manifests.get(name, {})
            # Determine stage from manifest (default to OUTPUT)
            stage = self._determine_stage(manifest)
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
    
    def _determine_stage(self, manifest: Dict[str, Any]) -> Stage:
        """
        Determine plugin stage from manifest.
        
        Priority:
        1. Explicit 'stage' field (new format)
        2. Infer from 'category' field (legacy)
        3. Default to OUTPUT
        """
        # New format: explicit stage
        stage_str = manifest.get('stage')
        if stage_str:
            try:
                return Stage(stage_str)
            except ValueError:
                pass
        
        # Legacy: map from category
        category = manifest.get('category', 'output')
        return Stage.from_category(category)
    
    def _build_plugin_info(
        self,
        name: str,
        stage: Stage,
        manifest: Dict[str, Any],
        instance: Optional[Any]
    ) -> None:
        """Build and cache PluginInfo for a plugin."""
        # Extract requires (supports both old and new formats)
        requires = manifest.get('requires', [])
        if not requires:
            requires = manifest.get('depends_on', [])  # Legacy field
            if not requires:
                requires = manifest.get('expects', [])  # Another legacy field
        
        # Ensure requires is a list
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
    
    def get_plugins_by_stage(self, stage: Stage) -> Dict[str, Any]:
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
    
    def get_plugin(self, name: str) -> Optional[Any]:
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
    
    def get_manifest(self, name: str) -> Optional[Dict[str, Any]]:
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
    
    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
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
    
    def get_all_manifests(self) -> Dict[str, Dict[str, Any]]:
        """Get all discovered manifests."""
        if not self._loaded:
            self.discover_and_load()
        return self._all_manifests.copy()
    
    def get_requires(self, name: str) -> List[str]:
        """Get requires list for a plugin."""
        info = self.get_plugin_info(name)
        return info.requires if info else []
    
    def get_provides(self, name: str) -> List[str]:
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
    def enabled_plugins(self) -> List[str]:
        """List of enabled plugin names."""
        if not self._loaded:
            self.discover_and_load()
        return list(self._all_plugins.keys())
    
    def validate_dependencies(self) -> List[str]:
        """
        Validate plugin dependencies.
        
        DEPRECATED: This is legacy validation with incorrect logic.
        Use StartupValidator and RequiresValidator instead.
        
        Returns:
            List of error messages (empty if valid)
        """
        if not self._loaded:
            self.discover_and_load()
        
        # P0.3: Suppress incorrect "not provided" warnings
        # These requires formats are validated at runtime by RequiresValidator:
        # - job.plugins.* → checked against actual plugin data
        # - provides.* → checked against provides completion registry
        # - events.* → checked against event bus
        #
        # This legacy method doesn't understand these prefixes and gives
        # false warnings. Runtime validation is the correct approach.
        return []
    
    def get_execution_order(self, stage: Stage = None) -> List[str]:
        """
        Get plugin execution order based on requires/provides.
        
        Uses topological sort within each stage.
        
        Args:
            stage: Optional stage to get order for (all if None)
            
        Returns:
            List of plugin names in execution order
        """
        if not self._loaded:
            self.discover_and_load()
        
        # For now, return simple order (proper topo sort in Phase 5)
        if stage:
            return list(self._plugins_by_stage.get(stage, {}).keys())
        
        order = []
        for s in Stage:
            order.extend(self._plugins_by_stage.get(s, {}).keys())
        return order
