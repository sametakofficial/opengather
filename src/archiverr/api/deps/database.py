"""
Database Dependencies

Provides database connection dependencies for FastAPI.
Supports both async (PyMongo AsyncMongoClient) and sync (PyMongo MongoClient) connections.

MIGRATION NOTICE (2025-11):
    Motor was deprecated in May 2025 and replaced with PyMongo's native AsyncMongoClient.
    This module now uses PyMongo 4.10+ for all async operations.
    Performance improvement: 20-140% faster than Motor.

Usage:
    from archiverr.api.deps import get_async_db, get_sync_db
    
    @router.get("/")
    async def endpoint(db = Depends(get_async_db)):
        result = await db.collection.find_one({})
"""

import os
import logging
from typing import Optional
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

# Connection state
_pymongo_client = None
_pymongo_db = None
_async_client = None
_async_db = None


# ============================================================================
# ASYNC DATABASE (PyMongo AsyncMongoClient)
# ============================================================================

async def get_async_db():
    """
    Get async MongoDB connection using PyMongo's AsyncMongoClient.
    
    Creates connection on first call, reuses afterwards.
    Best for async endpoints.
    
    Note: Replaces Motor (deprecated May 2025) with PyMongo Async.
    Performance: 20-140% faster than Motor.
    
    Returns:
        AsyncDatabase or None if connection fails
    """
    global _async_client, _async_db
    
    if _async_db is not None:
        return _async_db
    
    backend = os.getenv("ARCHIVERR_DB_BACKEND", "mongodb")
    
    if backend != "mongodb":
        return None
    
    try:
        from pymongo import AsyncMongoClient
        
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        database = os.getenv("MONGODB_DATABASE", "archiverr")
        
        _async_client = AsyncMongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=5,
        )
        _async_db = _async_client[database]
        
        # Verify connection
        await _async_db.command('ping')
        logger.info(f"PyMongo async connection established: {database}")
        
        return _async_db
        
    except Exception as e:
        logger.error(f"PyMongo async connection failed: {e}")
        return None


async def get_database(request: Request):
    """
    FastAPI dependency for database access via app.state.
    
    Prefers app.state.db (set by lifespan), falls back to direct connection.
    
    Usage:
        @router.get("/")
        async def endpoint(db = Depends(get_database)):
            ...
    """
    # First try app.state (set by lifespan)
    db = getattr(request.app.state, 'db', None)
    if db is not None:
        return db
    
    # Fallback to direct connection
    db = await get_async_db()
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
    
    backend = os.getenv("ARCHIVERR_DB_BACKEND", "mongodb")
    
    if backend != "mongodb":
        return None
    
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
        logger.info(f"PyMongo sync connection established: {database}")
        
        return _pymongo_db
        
    except Exception as e:
        logger.error(f"PyMongo connection failed: {e}")
        return None


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

async def close_connections():
    """Close all database connections."""
    global _async_client, _async_db, _pymongo_client, _pymongo_db
    
    if _async_client is not None:
        _async_client.close()
        _async_client = None
        _async_db = None
        logger.info("PyMongo async connection closed")
    
    if _pymongo_client is not None:
        _pymongo_client.close()
        _pymongo_client = None
        _pymongo_db = None
        logger.info("PyMongo sync connection closed")


def reset_connections():
    """Reset connection state (for testing)."""
    global _async_client, _async_db, _pymongo_client, _pymongo_db
    _async_client = None
    _async_db = None
    _pymongo_client = None
    _pymongo_db = None
