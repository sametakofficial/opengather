"""
Database Connection Module - Industry Best Practice Implementation

Uses Motor (async MongoDB driver) with FastAPI Lifespan pattern.
This is the recommended approach by FastAPI maintainers.

Pattern:
1. Create Motor client in lifespan
2. Store in app.state
3. Access via dependency injection
4. Auto-cleanup on shutdown
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
    
    Industry standard singleton pattern for database connections.
    """
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect(cls) -> AsyncIOMotorDatabase:
        """
        Connect to MongoDB.
        
        Returns the database instance for use in the application.
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
            maxPoolSize=50,  # Connection pool size
            minPoolSize=5,
        )
        cls.db = cls.client[database]
        
        # Verify connection
        await cls.db.command("ping")
        logger.info(f"Connected to MongoDB: {database}")
        
        return cls.db
    
    @classmethod
    async def disconnect(cls) -> None:
        """Close MongoDB connection."""
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """Get database instance (must be connected first)."""
        if cls.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return cls.db


@asynccontextmanager
async def mongodb_lifespan(app):
    """
    Lifespan context manager for MongoDB connection.
    
    Usage in FastAPI app:
        app = FastAPI(lifespan=mongodb_lifespan)
    
    This is the FastAPI-recommended pattern for managing
    database connections that need setup/teardown.
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
    
    Usage:
        @router.get("/")
        async def endpoint(db: AsyncIOMotorDatabase = Depends(get_database)):
            result = await db.collection.find_one({})
    """
    db = request.app.state.db
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not available")
    return db
