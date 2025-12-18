"""
MongoDB Persistence (DEPRECATED)

.. deprecated:: 2.2.0
    This module uses Motor with run_until_complete() which can cause event loop
    issues. Use PyMongoPersistence instead, which uses pure synchronous PyMongo.

    Migration:
        # OLD (deprecated)
        from archiverr.infrastructure.database import MongoDBPersistence
        
        # NEW (recommended)
        from archiverr.infrastructure.database import PyMongoPersistence

This module is kept for backward compatibility only.

Requirements:
    pip install motor

Collections:
    - executions: Execution metadata and config snapshots
    - matches: Match data and task results
    - plugin_results: Plugin-specific data (TTL enabled)
    
    Git-like versioning collections:
    - branches: Named branches for execution history
    - commits: Immutable snapshots linked to branches
"""

import warnings
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import asyncio
import atexit
import logging

# Emit deprecation warning on import
warnings.warn(
    "MongoDBPersistence is deprecated. Use PyMongoPersistence instead. "
    "MongoDBPersistence uses Motor + run_until_complete() which can cause "
    "event loop issues in async contexts.",
    DeprecationWarning,
    stacklevel=2
)

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    from pymongo.errors import (
        ConnectionFailure, 
        ServerSelectionTimeoutError,
        OperationFailure,
        DuplicateKeyError
    )
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    AsyncIOMotorClient = None
    AsyncIOMotorDatabase = None
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    OperationFailure = Exception
    DuplicateKeyError = Exception

logger = logging.getLogger(__name__)

from .interface import PersistenceInterface


class MongoDBPersistence(PersistenceInterface):
    """
    MongoDB persistence using Motor async driver.
    
    Features:
    - Async operations for optimal performance
    - Connection pooling
    - Automatic index creation
    - TTL support for plugin_results (90 days default)
    - Write-through for real-time persistence
    
    Usage:
        persistence = MongoDBPersistence(
            uri="mongodb://localhost:27017",
            database="archiverr"
        )
        persistence.connect()
        persistence.save_execution(execution)
        persistence.disconnect()
    
    Environment Variables:
        MONGODB_URI: Connection string (default: mongodb://localhost:27017)
        MONGODB_DATABASE: Database name (default: archiverr)
    """
    
    # Collection names
    EXECUTIONS = "executions"
    MATCHES = "matches"
    PLUGIN_RESULTS = "plugin_results"
    
    # Default TTL for plugin results (90 days)
    DEFAULT_TTL_DAYS = 90
    
    def __init__(
        self, 
        uri: str = "mongodb://localhost:27017",
        database: str = "archiverr",
        ttl_days: int = DEFAULT_TTL_DAYS
    ):
        """
        Initialize MongoDB persistence.
        
        Args:
            uri: MongoDB connection string
            database: Database name
            ttl_days: Days to keep plugin results before auto-deletion
        """
        if not MOTOR_AVAILABLE:
            raise ImportError(
                "Motor is required for MongoDB persistence. "
                "Install with: pip install motor"
            )
        
        self._uri = uri
        self._database_name = database
        self._ttl_days = ttl_days
        
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connected = False
    
    def connect(self) -> None:
        """Connect to MongoDB and create indexes"""
        self._loop = self._get_or_create_event_loop()
        
        try:
            # Set shorter timeout for initial connection
            self._client = AsyncIOMotorClient(
                self._uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=5000,
                maxPoolSize=10,
                minPoolSize=1
            )
            self._db = self._client[self._database_name]
            
            # Verify connection with ping
            self._run_async(self._ping())
            
            # Create indexes synchronously
            self._run_async(self._create_indexes())
            self._connected = True
            
            # Register cleanup on exit
            atexit.register(self.disconnect)
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB at {self._uri}: {e}")
            raise ConnectionError(f"MongoDB connection failed: {e}") from e
    
    async def _ping(self) -> bool:
        """Verify MongoDB connection is healthy"""
        try:
            await self._db.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            raise
    
    def disconnect(self) -> None:
        """Disconnect from MongoDB"""
        if self._client is not None and self._connected:
            self._client.close()
            self._client = None
            self._db = None
            self._connected = False
    
    def save_execution(self, execution) -> None:
        """Save or update execution"""
        self._run_async(self._save_execution_async(execution))
    
    def save_match(self, match) -> None:
        """Save or update match"""
        self._run_async(self._save_match_async(match))
    
    def save_plugin_result(
        self, 
        execution_id: str, 
        match_index: int, 
        plugin_name: str, 
        result: Dict[str, Any]
    ) -> None:
        """Save plugin result"""
        self._run_async(
            self._save_plugin_result_async(
                execution_id, match_index, plugin_name, result
            )
        )
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution by ID"""
        return self._run_async(self._get_execution_async(execution_id))
    
    def get_matches(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all matches for execution"""
        return self._run_async(self._get_matches_async(execution_id))
    
    def get_plugin_results(
        self, 
        execution_id: str, 
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """Get all plugin results for a match"""
        return self._run_async(
            self._get_plugin_results_async(execution_id, match_index)
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        return self._run_async(self._get_statistics_async())
    
    # ==================== ASYNC IMPLEMENTATIONS ====================
    
    async def _create_indexes(self) -> None:
        """Create database indexes"""
        # Executions indexes
        await self._db[self.EXECUTIONS].create_index("started_at")
        await self._db[self.EXECUTIONS].create_index([("status", 1), ("started_at", -1)])
        
        
        # TTL index for plugin results
        await self._db[self.PLUGIN_RESULTS].create_index(
            "expires_at",
            expireAfterSeconds=0
        )
    
    async def _save_execution_async(self, execution) -> None:
        """Async save execution with error handling. Accepts dict or object with to_dict()."""
        try:
            # Support both dict and object with to_dict()
            if hasattr(execution, 'to_dict'):
                exec_dict = execution.to_dict()
            else:
                exec_dict = dict(execution)
            exec_id = exec_dict["_id"]
            
            await self._db[self.EXECUTIONS].update_one(
                {"_id": exec_id},
                {"$set": exec_dict},
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save execution {execution.id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving execution: {e}")
            raise
    
    async def _save_match_async(self, match) -> None:
        """Async save match with error handling. Accepts dict or object with to_dict()."""
        try:
            # Support both dict and object with to_dict()
            if hasattr(match, 'to_dict'):
                match_dict = match.to_dict()
            else:
                match_dict = dict(match)
            match_id = match_dict["_id"]
            
            await self._db[self.MATCHES].update_one(
                {"_id": match_id},
                {"$set": match_dict},
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save match {match.index}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving match: {e}")
            raise
    
    async def _save_plugin_result_async(
        self, 
        execution_id: str, 
        match_index: int, 
        plugin_name: str, 
        result: Dict[str, Any]
    ) -> None:
        """Async save plugin result with error handling
        
        Structure:
            - status: Plugin execution status (success, timing, errors)
            - data: Plugin-specific data only (movie, show, parsed, etc.)
        """
        result_id = f"pr_{plugin_name}_{match_index}_{execution_id}"
        
        try:
            # Extract status from result (if present)
            # Status should be at root level, not inside data
            status = result.pop('status', None) if isinstance(result, dict) else None
            
            # Default status if not provided
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
                "status": status,  # Status at root level
                "data": result,    # Only plugin-specific data
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=self._ttl_days)
            }
            
            await self._db[self.PLUGIN_RESULTS].update_one(
                {"_id": result_id},
                {"$set": result_doc},
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save plugin result {plugin_name} for match {match_index}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving plugin result: {e}")
            raise
    
    async def _get_execution_async(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Async get execution"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        doc = await self._db[self.EXECUTIONS].find_one({"_id": exec_id})
        return doc
    
    async def _get_matches_async(self, execution_id: str) -> List[Dict[str, Any]]:
        """Async get matches"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        cursor = self._db[self.MATCHES].find({"execution_id": exec_id})
        return await cursor.to_list(length=None)
    
    async def _get_plugin_results_async(
        self, 
        execution_id: str, 
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """Async get plugin results"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        cursor = self._db[self.PLUGIN_RESULTS].find({
            "execution_id": exec_id,
            "match_index": match_index
        })
        
        results = {}
        async for doc in cursor:
            results[doc["plugin_name"]] = doc["data"]
        
        return results
    
    async def _get_statistics_async(self) -> Dict[str, Any]:
        """Async get statistics"""
        return {
            "backend": "MongoDBPersistence",
            "uri": self._uri,
            "database": self._database_name,
            "executions": await self._db[self.EXECUTIONS].count_documents({}),
            "matches": await self._db[self.MATCHES].count_documents({}),
            "plugin_results": await self._db[self.PLUGIN_RESULTS].count_documents({})
        }
    
    # ==================== HELPER METHODS ====================
    
    def _get_or_create_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get existing event loop or create new one"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    
    def _run_async(self, coro):
        """Run async coroutine synchronously.
        
        Note: This is designed for CLI usage or when called from a thread pool.
        For FastAPI, use run_in_executor to call sync methods from separate thread.
        """
        if self._loop is None:
            self._loop = self._get_or_create_event_loop()
        
        # Handle closed loop
        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        
        return self._loop.run_until_complete(coro)
    
    # ==================== ADDITIONAL QUERY METHODS ====================
    
    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent executions ordered by start time"""
        return self._run_async(self._get_recent_executions_async(limit))
    
    async def _get_recent_executions_async(self, limit: int) -> List[Dict[str, Any]]:
        """Async get recent executions"""
        cursor = self._db[self.EXECUTIONS].find().sort("started_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    def get_failed_executions(self) -> List[Dict[str, Any]]:
        """Get failed executions"""
        return self._run_async(self._get_failed_executions_async())
    
    async def _get_failed_executions_async(self) -> List[Dict[str, Any]]:
        """Async get failed executions"""
        cursor = self._db[self.EXECUTIONS].find({"success": False})
        return await cursor.to_list(length=None)
    
    def delete_execution(self, execution_id: str) -> bool:
        """Delete execution and all related data"""
        return self._run_async(self._delete_execution_async(execution_id))
    
    async def _delete_execution_async(self, execution_id: str) -> bool:
        """Async delete execution"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        # Delete plugin results
        await self._db[self.PLUGIN_RESULTS].delete_many({"execution_id": exec_id})
        
        # Delete matches
        await self._db[self.MATCHES].delete_many({"execution_id": exec_id})
        
        # Delete execution
        result = await self._db[self.EXECUTIONS].delete_one({"_id": exec_id})
        
        return result.deleted_count > 0
    
    # ==================== GIT-LIKE VERSIONING METHODS ====================
    
    def create_branch(self, name: str, description: str = "", is_default: bool = False) -> Dict[str, Any]:
        """Create a new branch"""
        return self._run_async(self._create_branch_async(name, description, is_default))
    
    async def _create_branch_async(
        self, 
        name: str, 
        description: str = "",
        is_default: bool = False
    ) -> Dict[str, Any]:
        """Async create branch"""
        from uuid import uuid4
        
        branch_id = f"branch_{str(uuid4())[:8]}"
        now = datetime.utcnow()
        
        # If this is default branch, unset others
        if is_default:
            await self._db[self.BRANCHES].update_many(
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
            await self._db[self.BRANCHES].insert_one(branch_doc)
            return branch_doc
        except DuplicateKeyError:
            raise ValueError(f"Branch '{name}' already exists")
    
    def get_branch(self, branch_id: str = None, name: str = None) -> Optional[Dict[str, Any]]:
        """Get branch by ID or name"""
        return self._run_async(self._get_branch_async(branch_id, name))
    
    async def _get_branch_async(
        self, 
        branch_id: str = None, 
        name: str = None
    ) -> Optional[Dict[str, Any]]:
        """Async get branch"""
        if branch_id:
            return await self._db[self.BRANCHES].find_one({"_id": branch_id})
        elif name:
            return await self._db[self.BRANCHES].find_one({"name": name})
        else:
            # Return default branch
            return await self._db[self.BRANCHES].find_one({"is_default": True})
    
    def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches"""
        return self._run_async(self._list_branches_async())
    
    async def _list_branches_async(self) -> List[Dict[str, Any]]:
        """Async list branches"""
        cursor = self._db[self.BRANCHES].find().sort("created_at", -1)
        return await cursor.to_list(length=None)
    
    def delete_branch(self, branch_id: str) -> bool:
        """Delete a branch and its commits"""
        return self._run_async(self._delete_branch_async(branch_id))
    
    async def _delete_branch_async(self, branch_id: str) -> bool:
        """Async delete branch"""
        # Check if branch exists
        branch = await self._db[self.BRANCHES].find_one({"_id": branch_id})
        if not branch:
            return False
        
        # Don't allow deleting default branch
        if branch.get("is_default"):
            raise ValueError("Cannot delete default branch")
        
        # Delete branch
        result = await self._db[self.BRANCHES].delete_one({"_id": branch_id})
        return result.deleted_count > 0
