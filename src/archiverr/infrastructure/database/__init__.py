"""
Database Module

Persistence layer implementations following Repository Pattern.

Backends:
    - PyMongoPersistence: MongoDB with PyMongo sync driver (CLI)
    - AsyncMongoDB: Async MongoDB driver (FastAPI/API)

Usage:
    # Sync persistence (CLI)
    from archiverr.infrastructure.database import PyMongoPersistence
    persistence = PyMongoPersistence(uri="mongodb://localhost:27017/archiverr")
    persistence.connect()
    
    # Async (API)
    from archiverr.infrastructure.database import mongodb_lifespan, AsyncMongoDB
    app = FastAPI(lifespan=mongodb_lifespan)
"""

from .connection import DatabaseConfig, DatabaseConnection
from .interface import PersistenceInterface
from .null_persistence import NullPersistence

# PyMongo sync driver (for CLI) - NEW: Clean sync implementation
try:
    from .pymongo_persistence import PyMongoPersistence
    PYMONGO_AVAILABLE = True
except ImportError:
    PyMongoPersistence = None
    PYMONGO_AVAILABLE = False

# PyMongo Async driver (for FastAPI) - Replaces Motor (deprecated May 2025)
try:
    from .async_client import AsyncMongoDB, get_database, mongodb_lifespan
    # Backward compatibility alias
    MongoDB = AsyncMongoDB
    ASYNC_PYMONGO_AVAILABLE = True
except ImportError:
    AsyncMongoDB = None
    MongoDB = None
    mongodb_lifespan = None
    get_database = None
    ASYNC_PYMONGO_AVAILABLE = False

__all__ = [
    # Interfaces
    'PersistenceInterface',
    # Sync backends
    'PyMongoPersistence',  # Recommended for CLI
    # Async PyMongo (FastAPI)
    'AsyncMongoDB',        # PyMongo AsyncMongoClient wrapper
    'MongoDB',             # Alias for AsyncMongoDB
    'mongodb_lifespan',
    'get_database',
    # Connection management
    'DatabaseConnection',
    'DatabaseConfig',
    # Availability flags
    'PYMONGO_AVAILABLE',
    'ASYNC_PYMONGO_AVAILABLE',
    # Null backend
    'NullPersistence',
]
