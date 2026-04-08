"""Plugin Loader - Load and instantiate plugins with config validation"""
import importlib
import importlib.util
from typing import Any

from archiverr.core.exceptions import ValidationError
from archiverr.core.plugins.sdk.validators import validate_plugin_config
from archiverr.utils.debug import get_debugger


class PluginLoader:
    """Loads plugin classes from discovered metadata with config validation"""

    def __init__(self, plugin_metadata: dict[str, dict[str, Any]], config: dict[str, Any]):
        self.plugin_metadata = plugin_metadata
        self.config = config
        self.loaded_plugins = {}
        self.validation_errors: dict[str, list] = {}  # Track validation errors per plugin
        self.debugger = get_debugger()

    def load_plugin(self, plugin_name: str) -> Any | None:
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
            self.debugger.debug("loader", "Plugin not found in metadata", plugin=plugin_name)
            return None

        # Check if enabled in config - support both formats
        # 1. Normalized format: _plugins (from config_normalizer)
        # 2. Legacy format: plugins wrapper
        # 3. FlexGet format: top-level key
        plugin_config = self._get_plugin_config(plugin_name)
        if not self._is_plugin_enabled(plugin_name, plugin_config):
            self.debugger.debug("loader", "Plugin disabled", plugin=plugin_name)
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
                self._store_validated_config(plugin_name, plugin_config)
                self.debugger.debug("loader", "Config validation passed", plugin=plugin_name)

        try:
            self.debugger.debug("loader", "Loading plugin", plugin=plugin_name)

            # Get entry_point from metadata (default: client.py)
            entry_point = metadata.get('entry_point', 'client.py')
            # Remove .py extension to get module name
            module_name = entry_point.replace('.py', '')

            # Import plugin module
            module_path = f"archiverr.plugins.{plugin_name}.{module_name}"
            module = importlib.import_module(module_path)

            # Get class name from metadata or use convention
            class_name = metadata.get('class_name')

            if not class_name:
                # Convention: {Name}Plugin
                # Convert plugin_name to PascalCase
                parts = plugin_name.split('_')
                class_name = ''.join(part.capitalize() for part in parts) + 'Plugin'

            plugin_class = getattr(module, class_name, None)
            if not plugin_class:
                self.debugger.error("loader", "Plugin class not found", plugin=plugin_name, class_name=class_name)
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
            self.debugger.info("loader", "Plugin loaded successfully", plugin=plugin_name)
            return instance

        except (ImportError, ModuleNotFoundError) as e:
            self.debugger.error("loader", "Failed to import plugin module", plugin=plugin_name, error=str(e))
            return None
        except ValidationError as e:
            self.debugger.error("loader", "Plugin config validation failed", plugin=plugin_name, error=str(e))
            return None
        except Exception as e:
            self.debugger.error("loader", "Unexpected error loading plugin", plugin=plugin_name, error=str(e))
            return None

    def _store_validated_config(self, plugin_name: str, validated_config: dict[str, Any]) -> None:
        if '_plugins' in self.config and isinstance(self.config.get('_plugins'), dict):
            existing = self.config['_plugins'].get(plugin_name, {})
            if not isinstance(existing, dict):
                existing = {}
            internal = {k: v for k, v in existing.items() if isinstance(k, str) and k.startswith('_')}
            merged = {**internal, **{k: v for k, v in validated_config.items() if not str(k).startswith('_')}}
            self.config['_plugins'][plugin_name] = merged

    def load_all(self) -> dict[str, Any]:
        """Load all enabled plugins"""
        plugins = {}

        for plugin_name in self.plugin_metadata:
            plugin = self.load_plugin(plugin_name)
            if plugin:
                plugins[plugin_name] = plugin

        return plugins

    def load_by_category(self, category: str) -> dict[str, Any]:
        """
        Load all plugins of a specific category.
        
        Supports legacy category → stage mapping:
        - 'input' → input stage
        - 'output' → parse, data, output stages (backward compat)
        """
        plugins = {}

        # Map legacy categories to new stages
        stage_groups = {
            'input': ['input'],
            'output': ['parse', 'data', 'output'],  # All non-input stages
        }

        target_stages = stage_groups.get(category, [category])

        for plugin_name, metadata in self.plugin_metadata.items():
            # Get stage (prefer stage over category)
            plugin_stage = metadata.get('stage') or metadata.get('category', 'output')

            # Map legacy category to stage if needed
            if plugin_stage == 'output' and metadata.get('stage') is None:
                # Legacy output plugin - default to data stage
                plugin_stage = 'data'

            if plugin_stage in target_stages:
                plugin = self.load_plugin(plugin_name)
                if plugin:
                    plugins[plugin_name] = plugin

        return plugins

    def load_by_stage(self, stage: str) -> dict[str, Any]:
        """Load all plugins of a specific stage (new system)"""
        plugins = {}

        for plugin_name, metadata in self.plugin_metadata.items():
            plugin_stage = metadata.get('stage') or metadata.get('category')
            if plugin_stage != stage:
                continue

            plugin = self.load_plugin(plugin_name)
            if plugin:
                plugins[plugin_name] = plugin

        return plugins

    def _get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """
        Get plugin config from config - supports all formats.
        
        Priority:
        1. Normalized _plugins (from config_normalizer)
        2. Legacy plugins: wrapper
        3. FlexGet top-level key
        """
        # 1. Check normalized format
        if '_plugins' in self.config:
            plugin_conf = self.config['_plugins'].get(plugin_name, {})
            # Return config without internal keys
            return {k: v for k, v in plugin_conf.items() if not k.startswith('_')}

        # 2. Check legacy format
        if 'plugins' in self.config:
            plugin_conf = self.config['plugins'].get(plugin_name, {})
            if isinstance(plugin_conf, dict):
                return plugin_conf
            return {}

        # 3. Check FlexGet format (top-level key)
        plugin_conf = self.config.get(plugin_name, {})
        if isinstance(plugin_conf, dict):
            return plugin_conf

        return {}

    def _is_plugin_enabled(self, plugin_name: str, plugin_config: dict[str, Any]) -> bool:
        """
        Check if plugin is enabled - supports all formats.
        """
        # 1. Check normalized _enabled_plugins list
        if '_enabled_plugins' in self.config:
            return plugin_name in self.config['_enabled_plugins']

        # 2. Check normalized _plugins _enabled flag
        if '_plugins' in self.config:
            plugin_conf = self.config['_plugins'].get(plugin_name, {})
            return plugin_conf.get('_enabled', False)

        # 3. Check legacy format
        if 'plugins' in self.config:
            plugin_conf = self.config['plugins'].get(plugin_name)
            if plugin_conf is False:
                return False
            if isinstance(plugin_conf, dict):
                return plugin_conf.get('enabled', False)
            return bool(plugin_conf)

        # 4. Check FlexGet format
        plugin_conf = self.config.get(plugin_name)
        if plugin_conf is False:
            return False
        if isinstance(plugin_conf, dict):
            return plugin_conf.get('enabled', True)  # Default enabled if config exists

        return False
