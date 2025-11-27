"""
FastAPI Dependencies - Dependency Injection

Provides:
- Database connection management (sync PyMongo for reads)
- Common dependencies for routes
- Request context

Note: Uses sync PyMongo instead of async Motor to avoid event loop conflicts.
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global database connections
_pymongo_client = None
_pymongo_db = None

# Legacy - kept for compatibility
_motor_client = None
_motor_db = None
_persistence = None


def get_sync_db():
    """
    Get sync MongoDB connection using PyMongo.
    
    This avoids event loop conflicts with FastAPI.
    Safe to use in both sync and async endpoints.
    """
    global _pymongo_client, _pymongo_db
    
    if _pymongo_db is not None:
        return _pymongo_db
    
    backend = os.getenv("ARCHIVERR_DB_BACKEND", "mongodb")
    
    if backend == "mongodb":
        try:
            from pymongo import MongoClient
            
            uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            database = os.getenv("MONGODB_DATABASE", "archiverr")
            
            _pymongo_client = MongoClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=10
            )
            _pymongo_db = _pymongo_client[database]
            
            # Verify connection
            _pymongo_db.command('ping')
            
            logger.info(f"Connected to MongoDB (sync): {database}")
            return _pymongo_db
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            return None
    
    return None


def close_sync_db():
    """Close sync database connection"""
    global _pymongo_client, _pymongo_db
    
    if _pymongo_client is not None:
        _pymongo_client.close()
        _pymongo_client = None
        _pymongo_db = None
        logger.info("MongoDB sync connection closed")


async def get_db_connection():
    """
    Get or create async database connection for FastAPI.
    
    Uses Motor directly for async MongoDB access.
    
    Environment variables:
        - ARCHIVERR_DB_BACKEND: "mock" or "mongodb"
        - MONGODB_URI: MongoDB connection string
        - MONGODB_DATABASE: Database name
    """
    global _motor_client, _motor_db, _persistence
    
    if _motor_db is not None:
        return _motor_db
    
    backend = os.getenv("ARCHIVERR_DB_BACKEND", "mongodb")
    
    if backend == "mongodb":
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            
            uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            database = os.getenv("MONGODB_DATABASE", "archiverr")
            
            _motor_client = AsyncIOMotorClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=10,
                minPoolSize=1
            )
            _motor_db = _motor_client[database]
            
            # Verify connection
            await _motor_db.command('ping')
            
            logger.info(f"Connected to MongoDB: {database}")
            return _motor_db
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            # Fall through to mock
    
    # Mock persistence (sync, for development)
    from archiverr.infrastructure.database import DatabaseConnection
    _db_connection = DatabaseConnection.from_env()
    _persistence = _db_connection.connect()
    logger.info("Using mock persistence")
    
    return None


async def close_db_connection():
    """Close database connection on shutdown"""
    global _motor_client, _motor_db, _persistence
    
    if _motor_client is not None:
        _motor_client.close()
        _motor_client = None
        _motor_db = None
        logger.info("MongoDB connection closed")
    
    if _persistence is not None:
        _persistence = None
        logger.info("Mock persistence cleared")


async def get_persistence():
    """
    Dependency injection for persistence layer.
    
    Returns a wrapper that provides sync-like interface over async MongoDB.
    
    Usage in routes:
        @router.get("/")
        async def get_items(persistence = Depends(get_persistence)):
            ...
    """
    global _motor_db, _persistence
    
    if _motor_db is not None:
        # Return AsyncPersistenceWrapper for MongoDB
        return AsyncPersistenceWrapper(_motor_db)
    
    if _persistence is not None:
        return _persistence
    
    # Try to connect
    await get_db_connection()
    
    if _motor_db is not None:
        return AsyncPersistenceWrapper(_motor_db)
    
    return _persistence


async def get_db():
    """
    Get raw MongoDB database instance for direct queries.
    
    Returns Motor database object for async operations.
    """
    global _motor_db
    
    if _motor_db is None:
        await get_db_connection()
    
    return _motor_db


class AsyncPersistenceWrapper:
    """
    Wrapper to provide persistence interface over async Motor database.
    
    Mimics the sync PersistenceInterface for compatibility.
    """
    
    def __init__(self, db):
        self._db = db
    
    def get_statistics(self):
        """Get database statistics (sync wrapper for info endpoint)"""
        # This will be called in sync context, so we can't await
        # Return basic info that doesn't require DB calls
        return {
            "backend": "MongoDBPersistence",
            "database": self._db.name,
            "executions": "async",
            "matches": "async",
            "plugin_results": "async"
        }
    
    async def get_statistics_async(self):
        """Get database statistics asynchronously"""
        return {
            "backend": "MongoDBPersistence",
            "database": self._db.name,
            "executions": await self._db["executions"].count_documents({}),
            "matches": await self._db["matches"].count_documents({}),
            "plugin_results": await self._db["plugin_results"].count_documents({})
        }
    
    def get_recent_executions(self, limit: int = 10):
        """Sync wrapper - returns empty for now, use async version"""
        return []
    
    async def get_recent_executions_async(self, limit: int = 10):
        """Get recent executions asynchronously"""
        cursor = self._db["executions"].find().sort("started_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    def get_execution(self, execution_id: str):
        """Sync wrapper - returns None, use async version"""
        return None
    
    async def get_execution_async(self, execution_id: str):
        """Get execution by ID asynchronously"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        return await self._db["executions"].find_one({"_id": exec_id})
    
    def get_matches(self, execution_id: str):
        """Sync wrapper"""
        return []
    
    async def get_matches_async(self, execution_id: str):
        """Get matches for execution asynchronously"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        cursor = self._db["matches"].find({"execution_id": exec_id})
        return await cursor.to_list(length=None)
    
    def delete_execution(self, execution_id: str):
        """Sync wrapper"""
        return False
    
    async def delete_execution_async(self, execution_id: str):
        """Delete execution and related data asynchronously"""
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        
        # Delete plugin results
        await self._db["plugin_results"].delete_many({"execution_id": exec_id})
        
        # Delete matches
        await self._db["matches"].delete_many({"execution_id": exec_id})
        
        # Delete execution
        result = await self._db["executions"].delete_one({"_id": exec_id})
        
        return result.deleted_count > 0
    
    # ==================== BRANCH METHODS ====================
    
    async def _list_branches_async(self):
        """List all branches asynchronously"""
        cursor = self._db["branches"].find().sort("created_at", -1)
        return await cursor.to_list(length=None)
    
    def list_branches(self):
        """Sync wrapper - returns empty list, use async version"""
        return []
    
    async def _create_branch_async(self, name: str, description: str = "", is_default: bool = False):
        """Create a new branch asynchronously"""
        from datetime import datetime
        from uuid import uuid4
        
        # Check if name exists
        existing = await self._db["branches"].find_one({"name": name})
        if existing:
            raise ValueError(f"Branch '{name}' already exists")
        
        # If setting as default, unset others
        if is_default:
            await self._db["branches"].update_many({}, {"$set": {"is_default": False}})
        
        branch = {
            "_id": f"branch_{uuid4().hex[:8]}",
            "name": name,
            "description": description,
            "is_default": is_default,
            "head_commit_id": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        await self._db["branches"].insert_one(branch)
        return branch
    
    async def _get_branch_async(self, branch_id: str = None, name: str = None):
        """Get branch by ID or name asynchronously"""
        if branch_id:
            return await self._db["branches"].find_one({"_id": branch_id})
        elif name:
            return await self._db["branches"].find_one({"name": name})
        return None
    
    async def _delete_branch_async(self, branch_id: str):
        """Delete a branch asynchronously"""
        branch = await self._db["branches"].find_one({"_id": branch_id})
        if not branch:
            return False
        
        if branch.get("is_default"):
            raise ValueError("Cannot delete default branch")
        
        # Delete commits for this branch
        await self._db["commits"].delete_many({"branch_id": branch_id})
        
        # Delete branch
        result = await self._db["branches"].delete_one({"_id": branch_id})
        return result.deleted_count > 0
    
    # ==================== COMMIT METHODS ====================
    
    async def _list_commits_async(self, branch_id: str = None, limit: int = 50):
        """List commits asynchronously"""
        query = {}
        if branch_id:
            query["branch_id"] = branch_id
        
        cursor = self._db["commits"].find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def _create_commit_async(self, execution_id: str, branch_id: str = None, 
                                    message: str = "", metadata: dict = None):
        """Create a commit asynchronously"""
        from datetime import datetime
        from uuid import uuid4
        
        # Get or create default branch if not specified
        if not branch_id:
            default_branch = await self._db["branches"].find_one({"is_default": True})
            if not default_branch:
                # Create default branch
                default_branch = await self._create_branch_async("main", "Default branch", True)
            branch_id = default_branch["_id"]
        
        # Get branch
        branch = await self._db["branches"].find_one({"_id": branch_id})
        if not branch:
            raise ValueError(f"Branch {branch_id} not found")
        
        # Get execution summary
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        execution = await self._db["executions"].find_one({"_id": exec_id})
        
        execution_summary = {
            "total_matches": 0,
            "successful_matches": 0,
            "failed_matches": 0
        }
        if execution:
            execution_summary = {
                "total_matches": execution.get("total_matches", 0),
                "successful_matches": execution.get("completed_matches", 0),
                "failed_matches": execution.get("failed_matches", 0)
            }
        
        commit = {
            "_id": f"commit_{uuid4().hex[:8]}",
            "branch_id": branch_id,
            "execution_id": exec_id,
            "parent_commit_id": branch.get("head_commit_id"),
            "message": message or f"Execution {execution_id}",
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
            "execution_summary": execution_summary
        }
        
        await self._db["commits"].insert_one(commit)
        
        # Update branch head
        await self._db["branches"].update_one(
            {"_id": branch_id},
            {"$set": {"head_commit_id": commit["_id"], "updated_at": datetime.utcnow().isoformat()}}
        )
        
        return commit
    
    async def _get_commit_async(self, commit_id: str):
        """Get commit by ID asynchronously"""
        return await self._db["commits"].find_one({"_id": commit_id})
    
    async def _get_commit_history_async(self, commit_id: str, limit: int = 50):
        """Get commit history (ancestors) asynchronously"""
        history = []
        current_id = commit_id
        
        while current_id and len(history) < limit:
            commit = await self._db["commits"].find_one({"_id": current_id})
            if not commit:
                break
            history.append(commit)
            current_id = commit.get("parent_commit_id")
        
        return history
    
    async def _checkout_commit_async(self, commit_id: str):
        """Checkout a commit - get full data asynchronously"""
        commit = await self._db["commits"].find_one({"_id": commit_id})
        if not commit:
            raise ValueError(f"Commit {commit_id} not found")
        
        execution = await self._db["executions"].find_one({"_id": commit["execution_id"]})
        
        matches_cursor = self._db["matches"].find({"execution_id": commit["execution_id"]})
        matches = await matches_cursor.to_list(length=None)
        
        plugin_results_cursor = self._db["plugin_results"].find({"execution_id": commit["execution_id"]})
        plugin_results = await plugin_results_cursor.to_list(length=None)
        
        return {
            "commit": commit,
            "execution": execution,
            "matches": matches,
            "plugin_results": plugin_results
        }
