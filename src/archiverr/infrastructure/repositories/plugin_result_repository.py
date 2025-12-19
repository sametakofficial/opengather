"""
Plugin Result Repository

Repository for plugin result persistence operations.
"""

from typing import Any

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
            persistence: Persistence backend
        """
        self._persistence = persistence

    def save(self, result: dict[str, Any]) -> None:
        """
        Save plugin result.
        
        Args:
            result: Dict with job_id, plugin_name, data (and optional run_id, job_index, stage, status)
        """
        job_id = result.get("job_id")
        plugin_name = result.get("plugin_name")
        data = result.get("data")
        if not job_id or not plugin_name:
            raise ValueError("Plugin result must include 'job_id' and 'plugin_name'")

        plugin_doc = {
            "job_id": job_id,
            "plugin_name": plugin_name,
            "data": data or {},
        }
        if "run_id" in result:
            plugin_doc["run_id"] = result["run_id"]
        if "job_index" in result:
            plugin_doc["job_index"] = result["job_index"]
        if "stage" in result:
            plugin_doc["stage"] = result["stage"]
        if "status" in result:
            plugin_doc["status"] = result["status"]

        self._persistence.save_plugin(plugin_doc)

    def save_result(
        self,
        job_id: str,
        plugin_name: str,
        data: dict[str, Any],
        run_id: str | None = None,
        job_index: int | None = None,
        stage: str | None = None,
        status: dict[str, Any] | None = None
    ) -> None:
        """
        Save plugin result with explicit parameters.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            data: Plugin result data
        """
        doc: dict[str, Any] = {
            "job_id": job_id,
            "plugin_name": plugin_name,
            "data": data,
        }
        if run_id is not None:
            doc["run_id"] = run_id
        if job_index is not None:
            doc["job_index"] = job_index
        if stage is not None:
            doc["stage"] = stage
        if status is not None:
            doc["status"] = status
        self._persistence.save_plugin(doc)

    def get_by_id(self, result_id: str) -> dict[str, Any] | None:
        """
        Get plugin result by ID.
        
        Args:
            result_id: Result ID (format: pr_{plugin_name}_{job_id})
            
        Returns:
            Plugin result dict or None
        """
        if result_id.startswith("pr_"):
            payload = result_id[3:]
            parts = payload.split("_", 1)
            if len(parts) == 2:
                plugin_name, job_id = parts[0], parts[1]
                doc = self._persistence.get_plugin(job_id, plugin_name)
                if doc:
                    return {
                        "_id": result_id,
                        "job_id": job_id,
                        "plugin_name": plugin_name,
                        "data": doc.get("data", {}),
                    }

        return None

    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all plugin results.
        
        Warning: This can be very expensive. Use specific queries instead.
        
        Returns:
            List of plugin result dicts
        """
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
    ) -> dict[str, dict[str, Any]]:
        """
        Get all plugin results for a match.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            
        Returns:
            Dict of plugin_name -> data
        """
        raise NotImplementedError("Use job-based plugin queries instead")

    def get_by_plugin(self, plugin_name: str) -> list[dict[str, Any]]:
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
    ) -> dict[str, Any] | None:
        """
        Get specific plugin data for a match.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None
        """
        raise NotImplementedError("Use job-based plugin queries instead")
