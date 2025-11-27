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
    # BRANCHES (Git-like versioning)
    # ========================================================================
    
    def list_branches(self) -> List[dict]:
        """Sync stub - returns empty list."""
        return []
    
    async def list_branches_async(self) -> List[dict]:
        """List all branches asynchronously."""
        cursor = self._db["branches"].find().sort("created_at", -1)
        return await cursor.to_list(length=None)
    
    async def create_branch_async(
        self, 
        name: str, 
        description: str = "", 
        is_default: bool = False
    ) -> dict:
        """Create a new branch asynchronously."""
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
    
    async def get_branch_async(
        self, 
        branch_id: str = None, 
        name: str = None
    ) -> Optional[dict]:
        """Get branch by ID or name asynchronously."""
        if branch_id:
            return await self._db["branches"].find_one({"_id": branch_id})
        elif name:
            return await self._db["branches"].find_one({"name": name})
        return None
    
    async def delete_branch_async(self, branch_id: str) -> bool:
        """Delete a branch asynchronously."""
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
    
    # ========================================================================
    # COMMITS (Git-like versioning)
    # ========================================================================
    
    async def list_commits_async(
        self, 
        branch_id: str = None, 
        limit: int = 50
    ) -> List[dict]:
        """List commits asynchronously."""
        query = {}
        if branch_id:
            query["branch_id"] = branch_id
        
        cursor = self._db["commits"].find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def create_commit_async(
        self,
        execution_id: str,
        branch_id: str = None,
        message: str = "",
        metadata: dict = None
    ) -> dict:
        """Create a commit asynchronously."""
        # Get or create default branch
        if not branch_id:
            default_branch = await self._db["branches"].find_one({"is_default": True})
            if not default_branch:
                default_branch = await self.create_branch_async("main", "Default branch", True)
            branch_id = default_branch["_id"]
        
        # Get branch
        branch = await self._db["branches"].find_one({"_id": branch_id})
        if not branch:
            raise ValueError(f"Branch {branch_id} not found")
        
        # Get execution summary
        exec_id = self._normalize_exec_id(execution_id)
        execution = await self._db["executions"].find_one({"_id": exec_id})
        
        execution_summary = {
            "total_matches": execution.get("total_matches", 0) if execution else 0,
            "successful_matches": execution.get("completed_matches", 0) if execution else 0,
            "failed_matches": execution.get("failed_matches", 0) if execution else 0
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
            {"$set": {
                "head_commit_id": commit["_id"], 
                "updated_at": datetime.utcnow().isoformat()
            }}
        )
        
        return commit
    
    async def get_commit_async(self, commit_id: str) -> Optional[dict]:
        """Get commit by ID asynchronously."""
        return await self._db["commits"].find_one({"_id": commit_id})
    
    async def get_commit_history_async(
        self, 
        commit_id: str, 
        limit: int = 50
    ) -> List[dict]:
        """Get commit history (ancestors) asynchronously."""
        history = []
        current_id = commit_id
        
        while current_id and len(history) < limit:
            commit = await self._db["commits"].find_one({"_id": current_id})
            if not commit:
                break
            history.append(commit)
            current_id = commit.get("parent_commit_id")
        
        return history
    
    async def checkout_commit_async(self, commit_id: str) -> dict:
        """Checkout a commit - get full data asynchronously."""
        commit = await self._db["commits"].find_one({"_id": commit_id})
        if not commit:
            raise ValueError(f"Commit {commit_id} not found")
        
        execution = await self._db["executions"].find_one({"_id": commit["execution_id"]})
        
        matches = await self._db["matches"].find(
            {"execution_id": commit["execution_id"]}
        ).to_list(length=None)
        
        plugin_results = await self._db["plugin_results"].find(
            {"execution_id": commit["execution_id"]}
        ).to_list(length=None)
        
        return {
            "commit": commit,
            "execution": execution,
            "matches": matches,
            "plugin_results": plugin_results
        }
    
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
    
    # Fallback to mock persistence
    from archiverr.infrastructure.database import DatabaseConnection
    db_connection = DatabaseConnection.from_env()
    return db_connection.connect()
