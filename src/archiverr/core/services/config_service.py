"""
Config Service Implementation

Provides read-only access to configuration for plugins.
"""

from typing import Any, Dict


class ConfigServiceImpl:
    """
    ConfigService implementation.
    
    Provides read-only access to configuration with dot-notation support.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize config service.
        
        Args:
            config: Full config dictionary
        """
        self._config = config
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value using dot notation.
        
        Examples:
            service.get("options.debug")  # True
            service.get("tmdb.api_key")   # "xxx"
            service.get("missing", 42)    # 42
        
        Args:
            key: Config key (supports dot notation)
            default: Default value if not found
            
        Returns:
            Config value or default
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        
        return value
    
    def get_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get plugin configuration.
        
        Args:
            plugin_name: Plugin name (e.g., "tmdb", "renamer")
            
        Returns:
            Plugin config dict or empty dict
        """
        return self._config.get(plugin_name, {})
    
    def get_option(self, option: str, default: Any = None) -> Any:
        """
        Get from options section.
        
        Shorthand for get(f"options.{option}", default)
        
        Args:
            option: Option name (e.g., "debug", "dry_run")
            default: Default value
            
        Returns:
            Option value or default
        """
        return self._config.get('options', {}).get(option, default)
    
    def get_alias(self, alias: str) -> str:
        """
        Get alias definition.
        
        Args:
            alias: Alias name (e.g., "m", "movie")
            
        Returns:
            Alias path or empty string
        """
        return self._config.get('aliases', {}).get(alias, '')
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get full config dict (read-only copy)."""
        return self._config.copy()
    
    @property
    def options(self) -> Dict[str, Any]:
        """Get options section."""
        return self._config.get('options', {})
    
    @property
    def aliases(self) -> Dict[str, str]:
        """Get aliases section."""
        return self._config.get('aliases', {})
