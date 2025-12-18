"""
Common Dependencies and Wrappers

Provides:
- AsyncPersistenceWrapper: Wraps Motor DB with persistence-like interface
- get_persistence: Dependency for persistence layer access
"""

import logging
from datetime import datetime
from uuid import uuid4
from typing import Optional, List, Dict, Any

from .database import get_async_db
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class AsyncPersistenceWrapper:
    """
    Wrapper to provide persistence interface over async Motor database.
    
    Provides both sync stubs and async implementations for compatibility.
    Use async methods (ending with _async) for actual database operations.
    """
    
    def __init__(self, db):
        self._db = db
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Sync stub - returns basic info without DB calls."""
        return {
            "backend": "MongoDBPersistence",
            "database": self._db.name if self._db else "unknown",
            "note": "Use get_statistics_async for full stats"
        }
    
    async def get_statistics_async(self) -> Dict[str, Any]:
        """Get database statistics asynchronously."""
        return {
            "backend": "MongoDBPersistence",
            "database": self._db.name,
            "executions": await self._db["executions"].count_documents({}),
            "matches": await self._db["matches"].count_documents({}),
            "plugin_results": await self._db["plugin_results"].count_documents({})
        }
    
    # ========================================================================
    # EXECUTIONS
    # ========================================================================
    
    def get_recent_executions(self, limit: int = 10) -> List[dict]:
        """Sync stub - returns empty list."""
        return []
    
    async def get_recent_executions_async(self, limit: int = 10) -> List[dict]:
        """Get recent executions asynchronously."""
        cursor = self._db["executions"].find().sort("started_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    def get_execution(self, execution_id: str) -> Optional[dict]:
        """Sync stub - returns None."""
        return None
    
    async def get_execution_async(self, execution_id: str) -> Optional[dict]:
        """Get execution by ID asynchronously."""
        exec_id = self._normalize_exec_id(execution_id)
        return await self._db["executions"].find_one({"_id": exec_id})
    
    def delete_execution(self, execution_id: str) -> bool:
        """Sync stub - returns False."""
        return False
    
    async def delete_execution_async(self, execution_id: str) -> bool:
        """Delete execution and related data asynchronously."""
        exec_id = self._normalize_exec_id(execution_id)
        
        # Delete related data
        await self._db["plugin_results"].delete_many({"execution_id": exec_id})
        await self._db["matches"].delete_many({"execution_id": exec_id})
        
        # Delete execution
        result = await self._db["executions"].delete_one({"_id": exec_id})
        return result.deleted_count > 0
    
    # ========================================================================
    # MATCHES
    # ========================================================================
    
    def get_matches(self, execution_id: str) -> List[dict]:
        """Sync stub - returns empty list."""
        return []
    
    async def get_matches_async(self, execution_id: str) -> List[dict]:
        """Get matches for execution asynchronously."""
        exec_id = self._normalize_exec_id(execution_id)
        cursor = self._db["matches"].find({"execution_id": exec_id})
        return await cursor.to_list(length=None)
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _normalize_exec_id(self, execution_id: str) -> str:
        """Ensure execution ID has correct prefix."""
        if not execution_id.startswith("exec_"):
            return f"exec_{execution_id}"
        return execution_id


async def get_persistence():
    """
    Dependency for persistence layer access.
    
    Returns AsyncPersistenceWrapper for MongoDB operations.
    
    Usage:
        @router.get("/")
        async def endpoint(persistence = Depends(get_persistence)):
            stats = await persistence.get_statistics_async()
    """
    db = await get_async_db()
    
    if db is not None:
        return AsyncPersistenceWrapper(db)

    raise HTTPException(status_code=503, detail="Database not available")
