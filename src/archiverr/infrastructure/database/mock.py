"""
Mock Persistence - In-Memory Backend for Testing

Provides a simple in-memory persistence layer that implements PersistenceInterface.
Used when MongoDB is not available or for testing purposes.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .interface import PersistenceInterface


class MockPersistence(PersistenceInterface):
    """
    In-memory persistence for testing without MongoDB.
    
    All data is stored in dictionaries and lost when the process exits.
    """
    
    def __init__(self):
        self._connected = False
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._plugins: Dict[str, Dict[str, Any]] = {}
    
    def connect(self) -> None:
        """Simulate connection."""
        self._connected = True
    
    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected
    
    def save_run(self, run) -> None:
        """Save run state."""
        if hasattr(run, 'to_dict'):
            self._runs[run.id] = run.to_dict()
        elif isinstance(run, dict):
            self._runs[run.get('id', '')] = run
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        return self._runs.get(run_id)
    
    def save_job(self, job) -> None:
        """Save job state."""
        if hasattr(job, 'to_dict'):
            self._jobs[job.id] = job.to_dict()
        elif isinstance(job, dict):
            self._jobs[job.get('id', '')] = job
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def save_plugin(self, plugin_data: Dict[str, Any]) -> None:
        """Save plugin data."""
        job_id = plugin_data.get('job_id', '')
        plugin_name = plugin_data.get('plugin_name', '')
        key = f"{job_id}_{plugin_name}"
        self._plugins[key] = plugin_data
    
    def save_plugin_data(self, plugin_data) -> None:
        """Save plugin data (PluginData model)."""
        if hasattr(plugin_data, 'to_dict'):
            data = plugin_data.to_dict()
        else:
            data = plugin_data
        self.save_plugin(data)
    
    def get_plugin(self, job_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get plugin data."""
        key = f"{job_id}_{plugin_name}"
        return self._plugins.get(key)
    
    def save_plugin_result(self, run_id: str, job_index: int, plugin_name: str, result: Dict[str, Any]) -> None:
        """Save plugin result (legacy method)."""
        key = f"run_{run_id}_job_{job_index}_{plugin_name}"
        self._plugins[key] = {
            'run_id': run_id,
            'job_index': job_index,
            'plugin_name': plugin_name,
            'result': result
        }
    
    def clear(self) -> None:
        """Clear all data."""
        self._runs.clear()
        self._jobs.clear()
        self._plugins.clear()
