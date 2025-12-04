"""
Lazy Loading for Evicted Plugin Data - Session 11 Phase 9

Loads plugin data from MongoDB on demand when accessed after eviction.
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.infrastructure.persistence.interface import PersistenceInterface


class LazyLoader:
    """
    Lazy load plugin data from MongoDB.
    
    Used when accessing evicted plugin data. Includes a temporary
    cache to avoid repeated database queries for the same data.
    
    Usage:
        loader = LazyLoader(persistence)
        data = loader.load_plugin_data(job_id, plugin_name)
    """
    
    def __init__(self, persistence: "PersistenceInterface"):
        """
        Initialize lazy loader.
        
        Args:
            persistence: Persistence interface for MongoDB operations
        """
        self._persistence = persistence
        self._load_cache: Dict[str, Dict[str, Any]] = {}  # Temporary cache
    
    def load_plugin_data(
        self,
        job_id: str,
        plugin_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load plugin data from MongoDB.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None if not found
        """
        cache_key = f"{job_id}:{plugin_name}"
        
        # Check temporary cache first
        if cache_key in self._load_cache:
            return self._load_cache[cache_key]
        
        # Load from MongoDB
        try:
            plugins = self._persistence.get_plugins(filter_dict={
                "job_id": job_id,
                "plugin_name": plugin_name
            })
            
            if not plugins:
                return None
            
            data = plugins[0].get("data", {})
            
            # Store in temporary cache
            self._load_cache[cache_key] = data
            
            return data
            
        except Exception:
            return None
    
    def load_all_plugins_for_job(self, job_id: str) -> Dict[str, Any]:
        """
        Load all plugin data for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Dict of {plugin_name: data}
        """
        try:
            plugins = self._persistence.get_plugins(filter_dict={"job_id": job_id})
            
            result = {}
            for plugin in plugins:
                name = plugin.get("plugin_name")
                data = plugin.get("data", {})
                
                if name:
                    result[name] = data
                    
                    # Cache it
                    cache_key = f"{job_id}:{name}"
                    self._load_cache[cache_key] = data
            
            return result
            
        except Exception:
            return {}
    
    def batch_load(self, job_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch load plugin data for multiple jobs.
        
        More efficient than individual loads.
        
        Args:
            job_ids: List of job IDs
            
        Returns:
            Dict of {job_id: {plugin_name: data}}
        """
        result: Dict[str, Dict[str, Any]] = {}
        
        try:
            # Query all at once
            plugins = self._persistence.get_plugins(filter_dict={
                "job_id": {"$in": job_ids}
            })
            
            for plugin in plugins:
                job_id = plugin.get("job_id")
                name = plugin.get("plugin_name")
                data = plugin.get("data", {})
                
                if job_id and name:
                    if job_id not in result:
                        result[job_id] = {}
                    result[job_id][name] = data
                    
                    # Cache it
                    cache_key = f"{job_id}:{name}"
                    self._load_cache[cache_key] = data
            
        except Exception:
            pass
        
        return result
    
    def clear_cache(self, job_id: Optional[str] = None) -> None:
        """
        Clear temporary load cache.
        
        Args:
            job_id: If provided, clear only this job's cache.
                   If None, clear entire cache.
        """
        if job_id:
            keys_to_remove = [
                k for k in self._load_cache
                if k.startswith(f"{job_id}:")
            ]
            for key in keys_to_remove:
                del self._load_cache[key]
        else:
            self._load_cache.clear()
    
    def get_cache_size(self) -> int:
        """Get number of cached items."""
        return len(self._load_cache)
