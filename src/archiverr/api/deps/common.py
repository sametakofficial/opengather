"""
Common Dependencies and Wrappers

Provides:
- AsyncPersistenceWrapper: Wraps Motor DB with persistence-like interface
- get_persistence: Dependency for persistence layer access
"""

import logging
from typing import Any

from fastapi import HTTPException

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

    def get_statistics(self) -> dict[str, Any]:
        """Sync stub - returns basic info without DB calls."""
        return {
            "backend": "MongoDBPersistence",
            "database": self._db.name if self._db else "unknown",
            "note": "Use get_statistics_async for full stats"
        }

    async def get_statistics_async(self) -> dict[str, Any]:
        """Get database statistics asynchronously."""
        return {
            "backend": "MongoDBPersistence",
            "database": self._db.name,
            "runs": await self._db["runs"].count_documents({}),
            "jobs": await self._db["jobs"].count_documents({}),
            "plugins": await self._db["plugins"].count_documents({})
        }

    # Legacy executions/matches/plugin_results methods removed in S36 PASS 6.C.
    # Canonical surfaces: api/v1/runs/, api/v1/jobs/, api/v1/plugins/ routers
    # operating directly on runs/jobs/plugins collections.


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
