"""
Plugin Result Repository

Repository for plugin result persistence operations.
"""

from typing import List, Optional, Dict, Any

from ..database.interface import PersistenceInterface
from .base import BaseRepository


class PluginResultRepository(BaseRepository):
    """
    Repository for plugin result data access.
    
    Wraps PersistenceInterface for plugin result operations.
    """
    
    def __init__(self, persistence: PersistenceInterface):
        """
        Initialize repository.
        
        Args:
            persistence: Persistence backend (Mock or MongoDB)
        """
        self._persistence = persistence
    
    def save(self, result: Dict[str, Any]) -> None:
        """
        Save plugin result.
        
        Args:
            result: Dict with execution_id, match_index, plugin_name, data
        """
        self._persistence.save_plugin_result(
            execution_id=result["execution_id"],
            match_index=result["match_index"],
            plugin_name=result["plugin_name"],
            result=result["data"]
        )
    
    def save_result(
        self,
        execution_id: str,
        match_index: int,
        plugin_name: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Save plugin result with explicit parameters.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            plugin_name: Plugin name
            data: Plugin result data
        """
        self._persistence.save_plugin_result(
            execution_id=execution_id,
            match_index=match_index,
            plugin_name=plugin_name,
            result=data
        )
    
    def get_by_id(self, result_id: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin result by ID.
        
        Args:
            result_id: Result ID (format: pr_{plugin}_{match}_{exec})
            
        Returns:
            Plugin result dict or None
        """
        # Parse result_id to get components
        # Format: pr_{plugin}_{match_index}_{execution_id}
        if result_id.startswith("pr_"):
            parts = result_id[3:].rsplit("_", 2)
            if len(parts) >= 3:
                plugin_name = parts[0]
                try:
                    match_index = int(parts[1])
                    execution_id = parts[2]
                    
                    results = self._persistence.get_plugin_results(
                        execution_id, match_index
                    )
                    if plugin_name in results:
                        return {
                            "_id": result_id,
                            "execution_id": execution_id,
                            "match_index": match_index,
                            "plugin_name": plugin_name,
                            "data": results[plugin_name]
                        }
                except ValueError:
                    pass
        
        return None
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all plugin results.
        
        Warning: This can be very expensive. Use specific queries instead.
        
        Returns:
            List of plugin result dicts
        """
        if hasattr(self._persistence, 'get_all_data'):
            data = self._persistence.get_all_data()
            return data.get("plugin_results", [])
        
        return []
    
    def delete(self, result_id: str) -> bool:
        """
        Delete plugin result.
        
        Args:
            result_id: Result ID
            
        Returns:
            True if deleted
        """
        # Not implemented for current backends
        return False
    
    def get_for_match(
        self, 
        execution_id: str, 
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all plugin results for a match.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            
        Returns:
            Dict of plugin_name -> data
        """
        return self._persistence.get_plugin_results(execution_id, match_index)
    
    def get_by_plugin(self, plugin_name: str) -> List[Dict[str, Any]]:
        """
        Get all results for a specific plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            List of plugin result dicts
        """
        all_results = self.get_all()
        return [r for r in all_results if r.get("plugin_name") == plugin_name]
    
    def get_plugin_data(
        self,
        execution_id: str,
        match_index: int,
        plugin_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific plugin data for a match.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None
        """
        results = self.get_for_match(execution_id, match_index)
        return results.get(plugin_name)
