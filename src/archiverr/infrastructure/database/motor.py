"""
Motor Async MongoDB Driver Module

Industry best practice implementation for async MongoDB with FastAPI.
Uses Motor driver with Lifespan pattern for connection management.

This module provides:
- MongoDB: Singleton connection manager
- mongodb_lifespan: FastAPI lifespan context manager
- get_database: Dependency for route injection

Usage:
    from archiverr.infrastructure.database.motor import mongodb_lifespan, MongoDB
    
    app = FastAPI(lifespan=mongodb_lifespan)
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class MongoDB:
    """
    MongoDB connection manager using Motor async driver.
    
    Implements singleton pattern for connection pooling.
    Thread-safe and async-compatible.
    
    Class Attributes:
        client: AsyncIOMotorClient instance
        db: AsyncIOMotorDatabase instance
    
    Usage:
        # In lifespan
        db = await MongoDB.connect()
        app.state.db = db
        
        # In routes
        db = MongoDB.get_db()
        result = await db.collection.find_one({})
    """
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls) -> AsyncIOMotorDatabase:
        """
        Connect to MongoDB.
        
        Reads configuration from environment variables:
        - MONGODB_URI: Connection string (default: mongodb://localhost:27017)
        - MONGODB_DATABASE: Database name (default: archiverr)
        
        Returns:
            AsyncIOMotorDatabase instance
        
        Raises:
            Exception: If connection fails
        """
        if cls.client is not None:
            return cls.db
        
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        database = os.getenv("MONGODB_DATABASE", "archiverr")
        
        logger.info(f"Connecting to MongoDB: {database}")
        
        cls.client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=5,
        )
        cls.db = cls.client[database]
        
        # Verify connection
        await cls.db.command("ping")
        logger.info(f"Connected to MongoDB: {database}")
        
        return cls.db
    
    @classmethod
    async def disconnect(cls) -> None:
        """Close MongoDB connection and cleanup resources."""
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """
        Get database instance.
        
        Must be called after connect().
        
        Returns:
            AsyncIOMotorDatabase instance
        
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
    
    Environment:
        ARCHIVERR_DB_BACKEND: "mongodb" or "mock"
    """
    # Startup
    backend = os.getenv("ARCHIVERR_DB_BACKEND", "mongodb")
    
    if backend == "mongodb":
        try:
            db = await MongoDB.connect()
            app.state.db = db
            logger.info("MongoDB ready in app.state.db")
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e}")
            app.state.db = None
    else:
        app.state.db = None
        logger.info("Using mock persistence (ARCHIVERR_DB_BACKEND != mongodb)")
    
    yield
    
    # Shutdown
    await MongoDB.disconnect()


async def get_database(request) -> AsyncIOMotorDatabase:
    """
    Dependency for getting database from request.
    
    Retrieves database from app.state (set by lifespan).
    
    Usage:
        from fastapi import Depends
        from archiverr.infrastructure.database.motor import get_database
        
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
