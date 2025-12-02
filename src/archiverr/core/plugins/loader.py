"""Plugin Loader - Load and instantiate plugins with config validation"""
import importlib
from typing import Dict, Any, Optional
from archiverr.utils.debug import get_debugger
from archiverr.core.plugins.sdk.validators import validate_plugin_config


class PluginLoader:
    """Loads plugin classes from discovered metadata with config validation"""
    
    def __init__(self, plugin_metadata: Dict[str, Dict[str, Any]], config: Dict[str, Any]):
        self.plugin_metadata = plugin_metadata
        self.config = config
        self.loaded_plugins = {}
        self.validation_errors: Dict[str, list] = {}  # Track validation errors per plugin
        self.debugger = get_debugger()
    
    def load_plugin(self, plugin_name: str) -> Optional[Any]:
        """
        Load and instantiate a single plugin.
        
        Args:
            plugin_name: Name of plugin to load
            
        Returns:
            Plugin instance or None if failed
        """
        if plugin_name in self.loaded_plugins:
            return self.loaded_plugins[plugin_name]
        
        metadata = self.plugin_metadata.get(plugin_name)
        if not metadata:
            self.debugger.debug("loader", f"Plugin not found in metadata", plugin=plugin_name)
            return None
        
        # Check if enabled in config
        plugin_config = self.config.get('plugins', {}).get(plugin_name, {})
        if not plugin_config.get('enabled', False):
            self.debugger.debug("loader", f"Plugin disabled", plugin=plugin_name)
            return None
        
        # Validate plugin config against schema (if defined)
        config_schema = metadata.get('config_schema')
        if config_schema:
            validation_result = validate_plugin_config(plugin_config, config_schema, plugin_name)
            
            if not validation_result.valid:
                # Log validation errors
                self.validation_errors[plugin_name] = validation_result.error_messages()
                for error in validation_result.errors:
                    self.debugger.error("loader", "Config validation failed", 
                                       plugin=plugin_name, error=str(error))
                
                # Don't load plugin with invalid config
                self.debugger.warn("loader", "Plugin skipped due to config errors", plugin=plugin_name)
                return None
            else:
                # Use validated config with defaults applied
                plugin_config = validation_result.config
                self.debugger.debug("loader", "Config validation passed", plugin=plugin_name)
        
        try:
            self.debugger.debug("loader", f"Loading plugin", plugin=plugin_name)
            
            # Import plugin module
            module_path = f"archiverr.plugins.{plugin_name}.client"
            module = importlib.import_module(module_path)
            
            # Get class name from metadata or use convention
            class_name = metadata.get('class_name')
            
            if not class_name:
                # Convention: {Name}Plugin
                # Convert plugin_name to PascalCase: mock_test -> MockTest
                parts = plugin_name.split('_')
                class_name = ''.join(part.capitalize() for part in parts) + 'Plugin'
            
            plugin_class = getattr(module, class_name, None)
            if not plugin_class:
                self.debugger.error("loader", f"Plugin class not found", plugin=plugin_name, class_name=class_name)
                return None
            
            # Instantiate
            instance = plugin_class(plugin_config)
            
            # Set metadata from validated manifest
            instance._metadata = metadata
            instance.name = metadata.get('name', plugin_name)
            instance.category = metadata.get('category', 'unknown')
            
            # Log validation status
            is_validated = metadata.get('_validated', False)
            self.debugger.debug("loader", "Plugin metadata set", 
                              plugin=plugin_name, validated=is_validated)
            
            self.loaded_plugins[plugin_name] = instance
            self.debugger.info("loader", f"Plugin loaded successfully", plugin=plugin_name)
            return instance
            
        except Exception as e:
            self.debugger.error("loader", f"Failed to load plugin", plugin=plugin_name, error=str(e))
            return None
    
    def load_all(self) -> Dict[str, Any]:
        """Load all enabled plugins"""
        plugins = {}
        
        for plugin_name in self.plugin_metadata.keys():
            plugin = self.load_plugin(plugin_name)
            if plugin:
                plugins[plugin_name] = plugin
        
        return plugins
    
    def load_by_category(self, category: str) -> Dict[str, Any]:
        """Load all plugins of a specific category"""
        plugins = {}
        
        for plugin_name, metadata in self.plugin_metadata.items():
            if metadata.get('category') != category:
                continue
            
            plugin = self.load_plugin(plugin_name)
            if plugin:
                plugins[plugin_name] = plugin
        
        return plugins
