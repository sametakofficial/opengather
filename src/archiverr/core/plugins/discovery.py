"""Plugin Discovery - Scan and load plugin metadata"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from archiverr.utils.debug import get_debugger
from archiverr.core.plugins.sdk import PluginManifest
from pydantic import ValidationError

# Optional YAML support (fallback to JSON-only if not installed)
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class PluginDiscovery:
    """
    Discovers plugins by scanning manifest files.
    
    Priority:
    1. manifest.yml (new standard, preferred)
    2. manifest.yaml
    3. plugin.yml (legacy, backward compatibility)
    4. plugin.yaml
    5. plugin.json (fallback - JSON format)
    
    This allows gradual migration to the new manifest.yml format.
    """
    
    def __init__(self, plugins_dir: str = None):
        if plugins_dir is None:
            # Default: src/archiverr/plugins
            base = Path(__file__).parent.parent.parent
            plugins_dir = base / 'plugins'
        
        self.plugins_dir = Path(plugins_dir)
        self.debugger = get_debugger()
    
    def discover(self) -> Dict[str, Dict[str, Any]]:
        """
        Scan plugins directory and load plugin metadata.
        
        Checks for plugin.yml first, falls back to plugin.json.
        
        Returns:
            Dict[plugin_name, plugin_metadata]
        """
        plugins = {}
        
        if not self.plugins_dir.exists():
            self.debugger.warn("discovery", "Plugins directory not found", path=str(self.plugins_dir))
            return plugins
        
        self.debugger.debug("discovery", "Scanning plugins directory", path=str(self.plugins_dir))
        
        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            
            metadata = self._load_plugin_metadata(plugin_dir)
            if metadata is None:
                continue
            
            plugin_name = metadata.get('name')
            if not plugin_name:
                self.debugger.warn("discovery", "Plugin missing name field", dir=plugin_dir.name)
                continue
            
            # Add path info
            metadata['_path'] = str(plugin_dir)
            plugins[plugin_name] = metadata
            
            category = metadata.get('category', 'unknown')
            version = metadata.get('version', '?')
            manifest_type = metadata.get('_manifest_type', 'unknown')
            self.debugger.debug("discovery", f"Found plugin", 
                              name=plugin_name, category=category, 
                              version=version, manifest=manifest_type)
        
        return plugins
    
    def _load_plugin_metadata(self, plugin_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Load and validate plugin metadata from yml or json.
        
        Priority: manifest.yml > manifest.yaml > plugin.yml > plugin.yaml > plugin.json
        Validates with Pydantic PluginManifest model.
        
        Args:
            plugin_dir: Plugin directory path
            
        Returns:
            Validated plugin metadata dict or None
        """
        # Manifest files (new standard, preferred)
        manifest_yml = plugin_dir / 'manifest.yml'
        manifest_yaml = plugin_dir / 'manifest.yaml'
        # Legacy plugin files (backward compatibility)
        plugin_yml = plugin_dir / 'plugin.yml'
        plugin_yaml = plugin_dir / 'plugin.yaml'
        plugin_json = plugin_dir / 'plugin.json'
        
        raw_data = None
        manifest_type = None
        
        # Try YAML first (if available) - manifest.yml has highest priority
        if YAML_AVAILABLE:
            for yaml_file in [manifest_yml, manifest_yaml, plugin_yml, plugin_yaml]:
                if yaml_file.exists():
                    try:
                        with open(yaml_file, 'r', encoding='utf-8') as f:
                            raw_data = yaml.safe_load(f)
                        manifest_type = yaml_file.name
                        break
                    except Exception as e:
                        self.debugger.error("discovery", f"Failed to load {yaml_file.name}", 
                                          dir=plugin_dir.name, error=str(e))
                        continue
        
        # Fall back to JSON
        if raw_data is None and plugin_json.exists():
            try:
                with open(plugin_json, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                manifest_type = 'json'
            except Exception as e:
                self.debugger.error("discovery", "Failed to load plugin.json", 
                                  dir=plugin_dir.name, error=str(e))
        
        # No manifest found
        if raw_data is None:
            self.debugger.debug("discovery", "Skipping directory (no plugin manifest)", 
                              dir=plugin_dir.name)
            return None
        
        # Validate with Pydantic
        try:
            manifest = PluginManifest(**raw_data)
            validated = manifest.model_dump()
            validated['_path'] = str(plugin_dir)
            validated['_manifest_type'] = manifest_type
            validated['_validated'] = True
            return validated
        except ValidationError as e:
            self.debugger.error("discovery", "Invalid plugin manifest", 
                              dir=plugin_dir.name, errors=str(e))
            return None
    
    def get_by_category(self, category: str) -> Dict[str, Dict[str, Any]]:
        """Get plugins filtered by category (input/output)"""
        all_plugins = self.discover()
        return {
            name: meta
            for name, meta in all_plugins.items()
            if meta.get('category') == category
        }
    
    def get_input_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get all input plugins"""
        return self.get_by_category('input')
    
    def get_output_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get all output plugins"""
        return self.get_by_category('output')
