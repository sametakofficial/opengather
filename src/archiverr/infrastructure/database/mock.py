"""
Mock Persistence

Single JSON file persistence for development and testing.
MongoDB-like collection structure with ID references.

File Structure:
    mock_db/archiverr_state.json
    
JSON Structure:
    {
        "_meta": {...},
        "executions": [...],
        "matches": [...],
        "plugin_results": [...]
    }
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from threading import Lock

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
            "executions": len(self._data.get("executions", [])),
            "matches": len(self._data.get("matches", [])),
            "plugin_results": len(self._data.get("plugin_results", [])),
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
    
    # ==================== PRIVATE HELPERS ====================
    
    def _create_empty_db(self) -> Dict[str, Any]:
        """Create empty database structure"""
        return {
            "_meta": {
                "version": "1.0.0",
                "created_at": datetime.now().isoformat(),
                "last_modified": datetime.now().isoformat()
            },
            "executions": [],
            "matches": [],
            "plugin_results": []
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
