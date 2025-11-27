"""
PyMongo Sync Persistence

Production-ready MongoDB persistence using PyMongo sync driver.
NO async wrapping - pure synchronous operations for CLI usage.

This replaces the problematic MongoDBPersistence that used Motor + run_until_complete().

Usage:
    persistence = PyMongoPersistence(
        uri="mongodb://localhost:27017",
        database="archiverr"
    )
    persistence.connect()
    persistence.save_execution(execution)
    persistence.disconnect()
"""

import os
import logging
import atexit
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    from pymongo.database import Database
    from pymongo.errors import (
        ConnectionFailure,
        ServerSelectionTimeoutError,
        OperationFailure,
        DuplicateKeyError
    )
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoClient = None
    Database = None
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    OperationFailure = Exception
    DuplicateKeyError = Exception

from .interface import PersistenceInterface


class PyMongoPersistence(PersistenceInterface):
    """
    MongoDB persistence using PyMongo sync driver.
    
    Features:
    - Pure synchronous operations (no event loop conflicts)
    - Connection pooling
    - Automatic index creation
    - TTL support for plugin_results (90 days default)
    - Write-through for real-time persistence
    
    This is the recommended persistence for CLI usage.
    For API (async context), use Motor directly via get_database dependency.
    """
    
    # Collection names
    EXECUTIONS = "executions"
    MATCHES = "matches"
    PLUGIN_RESULTS = "plugin_results"
    BRANCHES = "branches"
    COMMITS = "commits"
    
    # Default TTL for plugin results (90 days)
    DEFAULT_TTL_DAYS = 90
    
    def __init__(
        self,
        uri: str = None,
        database: str = None,
        ttl_days: int = DEFAULT_TTL_DAYS
    ):
        """
        Initialize PyMongo persistence.
        
        Args:
            uri: MongoDB connection string (default: from MONGODB_URI env)
            database: Database name (default: from MONGODB_DATABASE env)
            ttl_days: Days to keep plugin results before auto-deletion
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "PyMongo is required for MongoDB persistence. "
                "Install with: pip install pymongo"
            )
        
        self._uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self._database_name = database or os.getenv("MONGODB_DATABASE", "archiverr")
        self._ttl_days = ttl_days
        
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._connected = False
    
    def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        try:
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=10,
                minPoolSize=1
            )
            self._db = self._client[self._database_name]
            
            # Verify connection with ping
            self._db.command('ping')
            logger.info(f"PyMongo connected to: {self._database_name}")
            
            # Create indexes
            self._create_indexes()
            self._connected = True
            
            # Register cleanup on exit
            atexit.register(self.disconnect)
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB at {self._uri}: {e}")
            raise ConnectionError(f"MongoDB connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from MongoDB."""
        if self._client is not None and self._connected:
            self._client.close()
            self._client = None
            self._db = None
            self._connected = False
            logger.debug("PyMongo connection closed")
    
    def _create_indexes(self) -> None:
        """Create database indexes."""
        # Executions indexes
        self._db[self.EXECUTIONS].create_index("started_at")
        self._db[self.EXECUTIONS].create_index([("status", 1), ("started_at", -1)])
        
        # Matches indexes
        self._db[self.MATCHES].create_index(
            [("execution_id", 1), ("index", 1)],
            unique=True
        )
        self._db[self.MATCHES].create_index("execution_id")
        self._db[self.MATCHES].create_index("category")
        
        # Plugin results indexes
        self._db[self.PLUGIN_RESULTS].create_index(
            [("execution_id", 1), ("match_index", 1), ("plugin_name", 1)],
            unique=True
        )
        self._db[self.PLUGIN_RESULTS].create_index("match_id")
        self._db[self.PLUGIN_RESULTS].create_index("plugin_name")
        
        # TTL index for plugin results
        self._db[self.PLUGIN_RESULTS].create_index(
            "expires_at",
            expireAfterSeconds=0
        )
        
        # Branches indexes
        self._db[self.BRANCHES].create_index("name", unique=True)
        self._db[self.BRANCHES].create_index("is_default")
        
        # Commits indexes
        self._db[self.COMMITS].create_index("branch_id")
        self._db[self.COMMITS].create_index("execution_id")
        self._db[self.COMMITS].create_index([("branch_id", 1), ("created_at", -1)])
    
    # ==================== EXECUTION OPERATIONS ====================
    
    def save_execution(self, execution) -> None:
        """Save or update execution."""
        try:
            if hasattr(execution, 'to_dict'):
                exec_dict = execution.to_dict()
            else:
                exec_dict = dict(execution)
            exec_id = exec_dict["_id"]
            
            self._db[self.EXECUTIONS].update_one(
                {"_id": exec_id},
                {"$set": exec_dict},
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save execution: {e}")
            raise
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution by ID."""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        return self._db[self.EXECUTIONS].find_one({"_id": exec_id})
    
    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent executions ordered by start time."""
        cursor = self._db[self.EXECUTIONS].find().sort("started_at", -1).limit(limit)
        return list(cursor)
    
    def get_failed_executions(self) -> List[Dict[str, Any]]:
        """Get failed executions."""
        cursor = self._db[self.EXECUTIONS].find({"success": False})
        return list(cursor)
    
    def delete_execution(self, execution_id: str) -> bool:
        """Delete execution and all related data."""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        # Delete plugin results
        self._db[self.PLUGIN_RESULTS].delete_many({"execution_id": exec_id})
        
        # Delete matches
        self._db[self.MATCHES].delete_many({"execution_id": exec_id})
        
        # Delete execution
        result = self._db[self.EXECUTIONS].delete_one({"_id": exec_id})
        return result.deleted_count > 0
    
    # ==================== MATCH OPERATIONS ====================
    
    def save_match(self, match) -> None:
        """Save or update match."""
        try:
            if hasattr(match, 'to_dict'):
                match_dict = match.to_dict()
            else:
                match_dict = dict(match)
            match_id = match_dict["_id"]
            
            self._db[self.MATCHES].update_one(
                {"_id": match_id},
                {"$set": match_dict},
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save match: {e}")
            raise
    
    def get_matches(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all matches for execution."""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        cursor = self._db[self.MATCHES].find({"execution_id": exec_id})
        return list(cursor)
    
    # ==================== PLUGIN RESULT OPERATIONS ====================
    
    def save_plugin_result(
        self,
        execution_id: str,
        match_index: int,
        plugin_name: str,
        result: Dict[str, Any]
    ) -> None:
        """Save plugin result."""
        result_id = f"pr_{plugin_name}_{match_index}_{execution_id}"
        
        try:
            # Extract status from result (if present)
            status = result.pop('status', None) if isinstance(result, dict) else None
            
            if status is None:
                status = {
                    "success": True,
                    "started_at": datetime.utcnow().isoformat(),
                    "finished_at": datetime.utcnow().isoformat(),
                    "duration_ms": 0,
                    "error": None
                }
            
            result_doc = {
                "_id": result_id,
                "execution_id": f"exec_{execution_id}",
                "match_id": f"match_{match_index}_{execution_id}",
                "match_index": match_index,
                "plugin_name": plugin_name,
                "status": status,
                "data": result,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=self._ttl_days)
            }
            
            self._db[self.PLUGIN_RESULTS].update_one(
                {"_id": result_id},
                {"$set": result_doc},
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save plugin result {plugin_name} for match {match_index}: {e}")
            raise
    
    def get_plugin_results(
        self,
        execution_id: str,
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """Get all plugin results for a match."""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        cursor = self._db[self.PLUGIN_RESULTS].find({
            "execution_id": exec_id,
            "match_index": match_index
        })
        
        results = {}
        for doc in cursor:
            results[doc["plugin_name"]] = doc["data"]
        
        return results
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "backend": "PyMongoPersistence",
            "uri": self._uri,
            "database": self._database_name,
            "executions": self._db[self.EXECUTIONS].count_documents({}),
            "matches": self._db[self.MATCHES].count_documents({}),
            "plugin_results": self._db[self.PLUGIN_RESULTS].count_documents({})
        }
    
    # ==================== GIT-LIKE VERSIONING ====================
    
    def create_branch(
        self,
        name: str,
        description: str = "",
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Create a new branch."""
        branch_id = f"branch_{str(uuid4())[:8]}"
        now = datetime.utcnow()
        
        # If this is default branch, unset others
        if is_default:
            self._db[self.BRANCHES].update_many(
                {"is_default": True},
                {"$set": {"is_default": False}}
            )
        
        branch_doc = {
            "_id": branch_id,
            "name": name,
            "description": description,
            "is_default": is_default,
            "head_commit_id": None,
            "created_at": now,
            "updated_at": now
        }
        
        try:
            self._db[self.BRANCHES].insert_one(branch_doc)
            return branch_doc
        except DuplicateKeyError:
            raise ValueError(f"Branch '{name}' already exists")
    
    def get_branch(
        self,
        branch_id: str = None,
        name: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get branch by ID or name."""
        if branch_id:
            return self._db[self.BRANCHES].find_one({"_id": branch_id})
        elif name:
            return self._db[self.BRANCHES].find_one({"name": name})
        else:
            return self._db[self.BRANCHES].find_one({"is_default": True})
    
    def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches."""
        cursor = self._db[self.BRANCHES].find().sort("created_at", -1)
        return list(cursor)
    
    def delete_branch(self, branch_id: str) -> bool:
        """Delete a branch and its commits."""
        branch = self._db[self.BRANCHES].find_one({"_id": branch_id})
        if not branch:
            return False
        
        if branch.get("is_default"):
            raise ValueError("Cannot delete default branch")
        
        # Delete all commits on this branch
        self._db[self.COMMITS].delete_many({"branch_id": branch_id})
        
        # Delete branch
        result = self._db[self.BRANCHES].delete_one({"_id": branch_id})
        return result.deleted_count > 0
    
    def create_commit(
        self,
        execution_id: str,
        branch_id: str = None,
        message: str = "",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a commit linking an execution to a branch."""
        # Get branch (default if not specified)
        if branch_id:
            branch = self._db[self.BRANCHES].find_one({"_id": branch_id})
        else:
            branch = self._db[self.BRANCHES].find_one({"is_default": True})
        
        if not branch:
            raise ValueError("No branch found. Create a branch first.")
        
        branch_id = branch["_id"]
        parent_commit_id = branch.get("head_commit_id")
        
        # Normalize execution ID
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        # Verify execution exists
        execution = self._db[self.EXECUTIONS].find_one({"_id": exec_id})
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        commit_id = f"commit_{str(uuid4())[:8]}"
        now = datetime.utcnow()
        
        commit_doc = {
            "_id": commit_id,
            "branch_id": branch_id,
            "execution_id": exec_id,
            "parent_commit_id": parent_commit_id,
            "message": message or f"Execution {execution_id}",
            "metadata": metadata or {},
            "created_at": now,
            "execution_summary": {
                "status": execution.get("status"),
                "success": execution.get("success"),
                "total_matches": execution.get("summary", {}).get("total_matches", 0),
                "completed_matches": execution.get("summary", {}).get("completed_matches", 0),
                "failed_matches": execution.get("summary", {}).get("failed_matches", 0)
            }
        }
        
        self._db[self.COMMITS].insert_one(commit_doc)
        
        # Update branch head
        self._db[self.BRANCHES].update_one(
            {"_id": branch_id},
            {
                "$set": {
                    "head_commit_id": commit_id,
                    "updated_at": now
                }
            }
        )
        
        return commit_doc
    
    def get_commit(self, commit_id: str) -> Optional[Dict[str, Any]]:
        """Get commit by ID."""
        return self._db[self.COMMITS].find_one({"_id": commit_id})
    
    def list_commits(
        self,
        branch_id: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List commits for a branch."""
        query = {}
        if branch_id:
            query["branch_id"] = branch_id
        
        cursor = self._db[self.COMMITS].find(query).sort("created_at", -1).limit(limit)
        return list(cursor)
    
    def get_commit_history(
        self,
        commit_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get commit history (ancestors)."""
        history = []
        current_id = commit_id
        
        while current_id and len(history) < limit:
            commit = self._db[self.COMMITS].find_one({"_id": current_id})
            if not commit:
                break
            history.append(commit)
            current_id = commit.get("parent_commit_id")
        
        return history
    
    def checkout_commit(self, commit_id: str) -> Dict[str, Any]:
        """Get full execution data for a commit."""
        commit = self._db[self.COMMITS].find_one({"_id": commit_id})
        if not commit:
            raise ValueError(f"Commit {commit_id} not found")
        
        exec_id = commit["execution_id"]
        
        execution = self._db[self.EXECUTIONS].find_one({"_id": exec_id})
        matches = list(self._db[self.MATCHES].find({"execution_id": exec_id}))
        plugin_results = list(self._db[self.PLUGIN_RESULTS].find({"execution_id": exec_id}))
        
        return {
            "commit": commit,
            "execution": execution,
            "matches": matches,
            "plugin_results": plugin_results
        }
