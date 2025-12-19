"""
API Dependencies Package

Provides dependency injection for FastAPI routes.
Split into modules for maintainability:
- database.py: Database connections (PyMongo async/sync)
- common.py: Common utilities and wrappers

USAGE (Modern Annotated Pattern - PEP 593):
    from archiverr.api.deps import DatabaseDep, PersistenceDep
    
    @router.get("/")
    async def endpoint(db: DatabaseDep):
        result = await db.collection.find_one({})

This pattern:
- Reduces boilerplate (no need for Depends() in every endpoint)
- Provides better type checking
- Follows FastAPI best practices
"""

from typing import Annotated, Any

from fastapi import Depends

from .common import AsyncPersistenceWrapper, get_persistence
from .database import close_connections, get_async_db, get_database, get_sync_db

# ============================================================================
# ANNOTATED DEPENDENCIES (Modern FastAPI Pattern)
# ============================================================================
# These type aliases reduce boilerplate and improve readability.
# Instead of: async def endpoint(db = Depends(get_database))
# Write:      async def endpoint(db: DatabaseDep)

# Database dependency - for direct MongoDB access
DatabaseDep = Annotated[Any, Depends(get_database)]

# Persistence dependency - for persistence layer access (with wrapper methods)
PersistenceDep = Annotated[AsyncPersistenceWrapper, Depends(get_persistence)]

# Async database dependency - explicit async db access
AsyncDbDep = Annotated[Any, Depends(get_async_db)]

# Sync database dependency - for sync contexts
SyncDbDep = Annotated[Any, Depends(get_sync_db)]


__all__ = [
    # Modern Annotated Dependencies (PREFERRED)
    'DatabaseDep',
    'PersistenceDep',
    'AsyncDbDep',
    'SyncDbDep',
    # Legacy function-based dependencies
    'get_async_db',
    'get_sync_db',
    'get_database',
    'close_connections',
    # Persistence
    'AsyncPersistenceWrapper',
    'get_persistence',
]
