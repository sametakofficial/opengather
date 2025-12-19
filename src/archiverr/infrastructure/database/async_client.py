"""
PyMongo Async MongoDB Driver Module

Industry best practice implementation for async MongoDB with FastAPI.
Uses PyMongo's native AsyncMongoClient (PyMongo 4.10+).

MIGRATION NOTICE:
    Motor was deprecated in May 2025 and support ends in May 2027.
    This module replaces motor.py with PyMongo's native async API.
    
    Motor → PyMongo Async performance improvement: 20-140% faster
    (Source: MongoDB official benchmarks)

This module provides:
- AsyncMongoDB: Singleton connection manager
- mongodb_lifespan: FastAPI lifespan context manager
- get_database: Dependency for route injection

Usage:
    from archiverr.infrastructure.database.async_client import mongodb_lifespan, AsyncMongoDB
    
    app = FastAPI(lifespan=mongodb_lifespan)
"""

import logging
import os
import warnings
from contextlib import asynccontextmanager

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)


class AsyncMongoDB:
    """
    MongoDB connection manager using PyMongo async driver.
    
    Implements singleton pattern for connection pooling.
    Thread-safe and async-compatible.
    
    Replaces Motor's AsyncIOMotorClient with PyMongo's AsyncMongoClient.
    Performance: 20-140% faster than Motor (MongoDB official benchmark).
    
    Class Attributes:
        client: AsyncMongoClient instance
        db: AsyncDatabase instance
    
    Usage:
        # In lifespan
        db = await AsyncMongoDB.connect()
        app.state.db = db
        
        # In routes
        db = AsyncMongoDB.get_db()
        result = await db.collection.find_one({})
    """

    client: AsyncMongoClient | None = None
    db: AsyncDatabase | None = None

    @classmethod
    async def connect(cls) -> AsyncDatabase:
        """
        Connect to MongoDB.
        
        Reads configuration from environment variables:
        - MONGODB_URI: Connection string (default: mongodb://localhost:27017)
        - MONGODB_DATABASE: Database name (default: archiverr)
        
        Returns:
            AsyncDatabase instance
        
        Raises:
            Exception: If connection fails
        """
        if cls.client is not None:
            return cls.db

        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        database = os.getenv("MONGODB_DATABASE", "archiverr")

        logger.info(f"Connecting to MongoDB (PyMongo Async): {database}")

        cls.client = AsyncMongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=5,
        )
        cls.db = cls.client[database]

        # Verify connection
        await cls.db.command("ping")
        logger.info(f"Connected to MongoDB (PyMongo Async): {database}")

        return cls.db

    @classmethod
    async def disconnect(cls) -> None:
        """Close MongoDB connection and cleanup resources."""
        if cls.client is not None:
            await cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed")

    @classmethod
    def get_db(cls) -> AsyncDatabase:
        """
        Get database instance.
        
        Must be called after connect().
        
        Returns:
            AsyncDatabase instance
        
        Raises:
            RuntimeError: If not connected
        """
        if cls.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return cls.db

    @classmethod
    def is_connected(cls) -> bool:
        """Check if database is connected."""
        return cls.client is not None


@asynccontextmanager
async def mongodb_lifespan(app):
    """
    Lifespan context manager for MongoDB connection.
    
    FastAPI-recommended pattern for managing database connections
    that need setup/teardown.
    
    Usage:
        app = FastAPI(lifespan=mongodb_lifespan)
    
    Sets:
        app.state.db: Database instance (or None if connection fails)
    """
    # Startup
    try:
        db = await AsyncMongoDB.connect()
        app.state.db = db
        logger.info("MongoDB ready in app.state.db (PyMongo Async)")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}")
        app.state.db = None

    yield

    # Shutdown
    await AsyncMongoDB.disconnect()


async def get_database(request) -> AsyncDatabase:
    """
    Dependency for getting database from request.
    
    Retrieves database from app.state (set by lifespan).
    
    Usage:
        from fastapi import Depends
        from archiverr.infrastructure.database.async_client import get_database
        
        @router.get("/")
        async def endpoint(db = Depends(get_database)):
            result = await db.collection.find_one({})
    
    Raises:
        HTTPException(503): If database not available
    """
    db = request.app.state.db
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not available")
    return db


# =============================================================================
# BACKWARD COMPATIBILITY - DEPRECATED ALIASES
# =============================================================================

# Alias for backward compatibility with motor.py imports
MongoDB = AsyncMongoDB


def _deprecated_motor_import_warning():
    """Issue deprecation warning for motor imports."""
    warnings.warn(
        "Motor is deprecated (May 2025). Use 'from archiverr.infrastructure.database.async_client "
        "import AsyncMongoDB' instead. Motor support ends May 2027.",
        DeprecationWarning,
        stacklevel=3
    )
