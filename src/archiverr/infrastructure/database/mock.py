"""
Mock Persistence

Single JSON file persistence for development and testing.
MongoDB-like collection structure with ID references.

File Structure:
    mock_db/archiverr_state.json
    
JSON Structure:
    {
        "_meta": {...},
        "executions": [...],      # Legacy (deprecated)
        "matches": [...],         # Legacy (deprecated)
        "plugin_results": [...],  # Legacy (deprecated)
        "runs": [...],            # New: RunState data
        "jobs": [...],            # New: JobState data
        "plugins": [...]          # New: PluginData (separate collection)
    }
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from threading import Lock
from copy import deepcopy

from .interface import PersistenceInterface

logger = logging.getLogger(__name__)


class MockPersistence(PersistenceInterface):
    """
    JSON file-based mock persistence.
    
    Features:
    - Single file (atomic writes)
    - MongoDB-like collection structure
    - ID-based references between documents
    - Thread-safe with locking
    
    Usage:
        persistence = MockPersistence(base_path="./mock_db")
        persistence.connect()
        persistence.save_execution(execution)
        persistence.disconnect()
    """
    
    def __init__(self, base_path: str = "./mock_db"):
        """
        Initialize mock persistence.
        
        Args:
            base_path: Directory for mock database file
        """
        self._base_path = Path(base_path)
        self._db_file = self._base_path / "archiverr_state.json"
        self._lock = Lock()
        self._data: Dict[str, Any] = {}
        self._connected = False
    
    def connect(self) -> None:
        """Initialize persistence - create directory and load existing data"""
        self._base_path.mkdir(parents=True, exist_ok=True)
        
        if self._db_file.exists():
            try:
                with open(self._db_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = self._create_empty_db()
        else:
            self._data = self._create_empty_db()
            self._save()
        
        self._connected = True
    
    def disconnect(self) -> None:
        """Save and close - ensure final state is persisted"""
        if self._connected:
            self._save()
            self._connected = False
    
    def save_execution(self, execution) -> None:
        """Save or update execution. Accepts dict or object with to_dict()."""
        with self._lock:
            # Support both dict and object with to_dict()
            if hasattr(execution, 'to_dict'):
                exec_dict = execution.to_dict()
            else:
                exec_dict = dict(execution)
            exec_id = exec_dict["_id"]
            
            executions = self._data.get("executions", [])
            found = False
            for i, e in enumerate(executions):
                if e.get("_id") == exec_id:
                    executions[i] = exec_dict
                    found = True
                    break
            
            if not found:
                executions.append(exec_dict)
            
            self._data["executions"] = executions
            self._update_meta()
            self._save()
    
    def save_match(self, match) -> None:
        """Save or update match. Accepts dict or object with to_dict()."""
        with self._lock:
            # Support both dict and object with to_dict()
            if hasattr(match, 'to_dict'):
                match_dict = match.to_dict()
            else:
                match_dict = dict(match)
            match_id = match_dict["_id"]
            
            matches = self._data.get("matches", [])
            found = False
            for i, m in enumerate(matches):
                if m.get("_id") == match_id:
                    matches[i] = match_dict
                    found = True
                    break
            
            if not found:
                matches.append(match_dict)
            
            self._data["matches"] = matches
            self._update_meta()
            self._save()
    
    def save_plugin_result(
        self, 
        execution_id: str, 
        match_index: int, 
        plugin_name: str, 
        result: Dict[str, Any]
    ) -> None:
        """Save plugin result"""
        with self._lock:
            result_id = f"pr_{plugin_name}_{match_index}_{execution_id}"
            
            result_doc = {
                "_id": result_id,
                "execution_id": f"exec_{execution_id}",
                "match_id": f"match_{match_index}_{execution_id}",
                "match_index": match_index,
                "plugin_name": plugin_name,
                "data": result,
                "created_at": datetime.now().isoformat()
            }
            
            plugin_results = self._data.get("plugin_results", [])
            found = False
            for i, pr in enumerate(plugin_results):
                if pr.get("_id") == result_id:
                    plugin_results[i] = result_doc
                    found = True
                    break
            
            if not found:
                plugin_results.append(result_doc)
            
            self._data["plugin_results"] = plugin_results
            self._update_meta()
            self._save()
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution by ID"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        for e in self._data.get("executions", []):
            if e.get("_id") == exec_id:
                return e
        return None
    
    def get_matches(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all matches for execution"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        return [
            m for m in self._data.get("matches", [])
            if m.get("execution_id") == exec_id
        ]
    
    def get_plugin_results(
        self, 
        execution_id: str, 
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """Get all plugin results for a match"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        results = {}
        for pr in self._data.get("plugin_results", []):
            if pr.get("execution_id") == exec_id and pr.get("match_index") == match_index:
                results[pr["plugin_name"]] = pr["data"]
        
        return results
    
    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent executions ordered by start time."""
        executions = self._data.get("executions", [])
        # Sort by started_at descending
        sorted_execs = sorted(
            executions,
            key=lambda x: x.get("started_at", ""),
            reverse=True
        )
        return sorted_execs[:limit]
    
    def delete_execution(self, execution_id: str) -> bool:
        """Delete execution and related data."""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        with self._lock:
            executions = self._data.get("executions", [])
            original_len = len(executions)
            
            # Remove execution
            self._data["executions"] = [e for e in executions if e.get("_id") != exec_id]
            
            # Remove related matches
            self._data["matches"] = [
                m for m in self._data.get("matches", [])
                if m.get("execution_id") != exec_id
            ]
            
            # Remove related plugin results
            self._data["plugin_results"] = [
                pr for pr in self._data.get("plugin_results", [])
                if pr.get("execution_id") != exec_id
            ]
            
            self._update_meta()
            self._save()
            
            return len(self._data["executions"]) < original_len
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            "backend": "MockPersistence",
            "db_file": str(self._db_file),
            # Legacy collections
            "executions": len(self._data.get("executions", [])),
            "matches": len(self._data.get("matches", [])),
            "plugin_results": len(self._data.get("plugin_results", [])),
            # New collections (Session 11)
            "runs": len(self._data.get("runs", [])),
            "jobs": len(self._data.get("jobs", [])),
            "plugins": len(self._data.get("plugins", [])),
            "last_modified": self._data.get("_meta", {}).get("last_modified")
        }
    
    def get_all_data(self) -> Dict[str, Any]:
        """Get entire database (for debugging)"""
        return self._data.copy()
    
    def clear(self) -> None:
        """Clear all data (for testing)"""
        with self._lock:
            self._data = self._create_empty_db()
            self._save()
    
    # =========================================================================
    # NEW METHODS (Session 11 - FINAL_DATASETS.yml compliant)
    # =========================================================================
    
    def save_run(self, run: Dict[str, Any]) -> None:
        """
        Save or update run state.
        
        Args:
            run: RunState.to_dict() output or dict with 'id' field
        """
        with self._lock:
            # Support both dict and object with to_dict()
            if hasattr(run, 'to_dict'):
                run_dict = run.to_dict()
            else:
                run_dict = dict(run)
            
            run_id = run_dict.get("id", "")
            if not run_id:
                raise ValueError("Run must have 'id' field")
            
            runs = self._data.get("runs", [])
            found = False
            for i, r in enumerate(runs):
                if r.get("id") == run_id:
                    runs[i] = run_dict
                    found = True
                    break
            
            if not found:
                runs.append(run_dict)
            
            self._data["runs"] = runs
            self._update_meta()
            self._save()
    
    def save_job(self, job: Dict[str, Any]) -> None:
        """
        Save or update job state.
        
        Args:
            job: JobState.to_dict() output or dict with 'id' field
        """
        with self._lock:
            # Support both dict and object with to_dict()
            if hasattr(job, 'to_dict'):
                job_dict = job.to_dict()
            else:
                job_dict = dict(job)
            
            job_id = job_dict.get("id", "")
            if not job_id:
                raise ValueError("Job must have 'id' field")
            
            jobs = self._data.get("jobs", [])
            found = False
            for i, j in enumerate(jobs):
                if j.get("id") == job_id:
                    jobs[i] = job_dict
                    found = True
                    break
            
            if not found:
                jobs.append(job_dict)
            
            self._data["jobs"] = jobs
            self._update_meta()
            self._save()
    
    def save_plugin(self, plugin: Dict[str, Any]) -> None:
        """
        Save plugin data to separate collection.
        
        Args:
            plugin: PluginData.to_dict() output or dict with job_id and plugin_name
        """
        with self._lock:
            # Support both dict and object with to_dict()
            if hasattr(plugin, 'to_dict'):
                plugin_dict = plugin.to_dict()
            else:
                plugin_dict = dict(plugin)
            
            job_id = plugin_dict.get("job_id", "")
            plugin_name = plugin_dict.get("plugin_name", "")
            
            if not job_id or not plugin_name:
                raise ValueError("Plugin must have 'job_id' and 'plugin_name' fields")
            
            # Use composite key for identification
            plugins = self._data.get("plugins", [])
            found = False
            for i, p in enumerate(plugins):
                if p.get("job_id") == job_id and p.get("plugin_name") == plugin_name:
                    plugins[i] = plugin_dict
                    found = True
                    break
            
            if not found:
                plugins.append(plugin_dict)
            
            self._data["plugins"] = plugins
            self._update_meta()
            self._save()
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run by ID.
        
        Args:
            run_id: Run ID (format: run_abc123)
            
        Returns:
            Run dict or None if not found
        """
        for r in self._data.get("runs", []):
            if r.get("id") == run_id:
                return deepcopy(r)
        return None
    
    def get_jobs(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all jobs for a run, sorted by index.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of job dicts sorted by index
        """
        jobs = [
            deepcopy(j) for j in self._data.get("jobs", [])
            if j.get("run_id") == run_id
        ]
        return sorted(jobs, key=lambda x: x.get("index", 0))
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID (format: job_run_abc123_0)
            
        Returns:
            Job dict or None if not found
        """
        for j in self._data.get("jobs", []):
            if j.get("id") == job_id:
                return deepcopy(j)
        return None
    
    def get_plugins(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all plugin data for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of plugin data dicts
        """
        return [
            deepcopy(p) for p in self._data.get("plugins", [])
            if p.get("job_id") == job_id
        ]
    
    def get_plugin(self, job_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific plugin data for a job.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None if not found
        """
        for p in self._data.get("plugins", []):
            if p.get("job_id") == job_id and p.get("plugin_name") == plugin_name:
                return deepcopy(p)
        return None
    
    def get_plugins_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all plugin data for a run.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of all plugin data dicts for the run
        """
        return [
            deepcopy(p) for p in self._data.get("plugins", [])
            if p.get("run_id") == run_id
        ]
    
    def save_plugin_data(self, plugin_data) -> None:
        """
        Save plugin data to plugins collection (Session 11 API).
        
        Args:
            plugin_data: PluginData object or dict
        """
        self.save_plugin(plugin_data)
    
    def delete_run(self, run_id: str) -> bool:
        """
        Delete run and all related data (jobs, plugins).
        
        Args:
            run_id: Run ID
            
        Returns:
            True if run was deleted, False if not found
        """
        with self._lock:
            runs = self._data.get("runs", [])
            original_len = len(runs)
            
            # Remove run
            self._data["runs"] = [r for r in runs if r.get("id") != run_id]
            
            # Remove related jobs
            self._data["jobs"] = [
                j for j in self._data.get("jobs", [])
                if j.get("run_id") != run_id
            ]
            
            # Remove related plugins
            self._data["plugins"] = [
                p for p in self._data.get("plugins", [])
                if p.get("run_id") != run_id
            ]
            
            self._update_meta()
            self._save()
            
            return len(self._data["runs"]) < original_len
    
    # ==================== PRIVATE HELPERS ====================
    
    def _create_empty_db(self) -> Dict[str, Any]:
        """Create empty database structure"""
        return {
            "_meta": {
                "version": "2.0.0",  # Bumped for Session 11
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat()
            },
            # Legacy collections (deprecated)
            "executions": [],
            "matches": [],
            "plugin_results": [],
            # New collections (Session 11)
            "runs": [],
            "jobs": [],
            "plugins": []
        }
    
    def _update_meta(self) -> None:
        """Update metadata timestamp"""
        if "_meta" not in self._data:
            self._data["_meta"] = {}
        self._data["_meta"]["last_modified"] = datetime.now().isoformat()
    
    def _save(self) -> None:
        """Save to file"""
        try:
            with open(self._db_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False, default=str)
        except IOError as e:
            logger.warning("Failed to save mock database: %s", e)
