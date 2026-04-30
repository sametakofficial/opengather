"""
Database Dependencies

Provides database connection dependencies for FastAPI.

Architecture (S37 PASS 8):
    - Async path: single source of truth = AsyncMongoDB singleton +
      mongodb_lifespan (infrastructure/database/async_client.py).
      Every request reads request.app.state.db. The previous
      module-globals shadow path (_async_db / _async_client cache,
      env-driven AsyncMongoClient construction) was archived to
      .deleted/s37-async-mongo-globals/ — it duplicated the connection
      pool with no current requirement.
    - Sync path: separate concern. Used by sync endpoints (e.g.
      /api/v1/run subprocess flow) that cannot await. Kept unchanged.

MIGRATION NOTICE (2025-11):
    Motor was deprecated in May 2025 and replaced with PyMongo's native
    AsyncMongoClient. This module uses PyMongo 4.10+ for all async ops.

Usage:
    from archiverr.api.deps import DatabaseDep

    @router.get("/")
    async def endpoint(db: DatabaseDep):
        result = await db.collection.find_one({})
"""

import logging
import os

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Sync connection state (async lives on AsyncMongoDB singleton).
_pymongo_client = None
_pymongo_db = None


# ============================================================================
# ASYNC DATABASE — thin wrapper around AsyncMongoDB singleton
# ============================================================================

async def get_async_db():
    """Return the AsyncMongoDB singleton's db handle, or None if not connected.

    Connection lifecycle is owned by ``mongodb_lifespan`` (FastAPI startup);
    this function never opens its own client. If lifespan failed to connect,
    ``app.state.db`` is None and so is this return value -- callers should
    treat None as "Mongo unavailable" and 503 the request.
    """
    from archiverr.infrastructure.database.async_client import AsyncMongoDB
    return AsyncMongoDB.db  # may be None pre-lifespan or after failed startup


async def get_database(request: Request):
    """FastAPI dependency for async database access via app.state.

    Source of truth: ``request.app.state.db`` (set by mongodb_lifespan).
    503 if Mongo is unavailable.
    """
    db = getattr(request.app.state, 'db', None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


# ============================================================================
# SYNC DATABASE (PyMongo)
# ============================================================================

def get_sync_db():
    """
    Get sync MongoDB connection using PyMongo.
    
    Useful for sync contexts or blocking operations.
    Avoids event loop conflicts.
    
    Returns:
        PyMongo Database or None if connection fails
    """
    global _pymongo_client, _pymongo_db

    if _pymongo_db is not None:
        return _pymongo_db

    # Cache only after successful ping (mirror of get_async_db fix, S36 PASS 6.E).
    client = None
    try:
        from pymongo import MongoClient

        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        database = os.getenv("MONGODB_DATABASE", "archiverr")

        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=10
        )
        db = client[database]

        # Verify connection BEFORE caching
        db.command('ping')
        logger.info(f"PyMongo sync connection established: {database}")

        _pymongo_client = client
        _pymongo_db = db
        return _pymongo_db

    except Exception as e:
        logger.error(f"PyMongo connection failed: {e}")
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        _pymongo_client = None
        _pymongo_db = None
        return None


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

async def close_connections():
    """Close all database connections (sync side; async is owned by lifespan)."""
    global _pymongo_client, _pymongo_db

    if _pymongo_client is not None:
        _pymongo_client.close()
        _pymongo_client = None
        _pymongo_db = None
        logger.info("PyMongo sync connection closed")

    # Async is owned by AsyncMongoDB singleton (mongodb_lifespan); call its
    # disconnect for symmetry when called from non-lifespan teardown.
    from archiverr.infrastructure.database.async_client import AsyncMongoDB
    await AsyncMongoDB.disconnect()


def reset_connections():
    """Reset sync connection state (for testing). Async is reset via
    ``AsyncMongoDB.reset_for_test()``."""
    global _pymongo_client, _pymongo_db
    _pymongo_client = None
    _pymongo_db = None
