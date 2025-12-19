"""
Provides Service Implementation

Provides early completion service for plugins.
"""


from archiverr.core.provides_registry import ProvidesRegistry


class ProvidesServiceImpl:
    """
    Provides service implementation.
    
    Allows plugins to mark individual provides as completed early.
    
    Usage:
        # In plugin execute method
        services.provides.complete("http.request")
    """

    def __init__(self, registry: ProvidesRegistry, plugin_name: str):
        """
        Initialize provides service.
        
        Args:
            registry: Global provides registry
            plugin_name: Name of the plugin using this service
        """
        self._registry = registry
        self._plugin_name = plugin_name

    def complete(self, provide: str) -> None:
        """
        Mark a provide as completed early.
        
        Args:
            provide: Provide value (e.g., "http.request", "fs.write")
        """
        self._registry.complete(self._plugin_name, provide)

    def is_completed(self, provide: str) -> bool:
        """
        Check if a provide is completed (by any plugin).
        
        Args:
            provide: Provide value
            
        Returns:
            True if provide is completed
        """
        return self._registry.is_completed(provide)

    def is_completed_by(self, provide: str, plugin_name: str) -> bool:
        """
        Check if a specific plugin has completed a provide.
        
        Args:
            provide: Provide value
            plugin_name: Plugin name
            
        Returns:
            True if the specific plugin has completed this provide
        """
        return self._registry.is_completed_by(provide, plugin_name)

    def get_status(self, provide: str) -> dict[str, str]:
        """
        Get status of a provide from all plugins.
        
        Args:
            provide: Provide value
            
        Returns:
            Dict of plugin_name -> status
        """
        return self._registry.get_status(provide)

    def get_all(self) -> dict[str, dict[str, str]]:
        """
        Get all provides as dict.
        
        Returns:
            Dict structure for template context
        """
        return self._registry.to_dict()
