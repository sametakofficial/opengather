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

from .interface import PersistenceInterface
from .connection import DatabaseConnection, DatabaseConfig

# PyMongo sync driver (for CLI) - NEW: Clean sync implementation
try:
    from .pymongo_persistence import PyMongoPersistence
    PYMONGO_AVAILABLE = True
except ImportError:
    PyMongoPersistence = None
    PYMONGO_AVAILABLE = False

# Legacy MongoDB (Motor with run_until_complete) - DEPRECATED
try:
    from .mongodb import MongoDBPersistence
    MONGODB_AVAILABLE = True
except ImportError:
    MongoDBPersistence = None
    MONGODB_AVAILABLE = False

# PyMongo Async driver (for FastAPI) - Replaces Motor (deprecated May 2025)
try:
    from .async_client import AsyncMongoDB, mongodb_lifespan, get_database
    # Backward compatibility alias
    MongoDB = AsyncMongoDB
    ASYNC_PYMONGO_AVAILABLE = True
except ImportError:
    AsyncMongoDB = None
    MongoDB = None
    mongodb_lifespan = None
    get_database = None
    ASYNC_PYMONGO_AVAILABLE = False

# DEPRECATED: Motor support (for backward compatibility only)
# Will show deprecation warning on import
MOTOR_AVAILABLE = ASYNC_PYMONGO_AVAILABLE  # Alias for backward compatibility

__all__ = [
    # Interfaces
    'PersistenceInterface',
    # Sync backends
    'PyMongoPersistence',  # Recommended for CLI
    'MongoDBPersistence',  # DEPRECATED: Use PyMongoPersistence
    # Async PyMongo (FastAPI)
    'AsyncMongoDB',        # PyMongo AsyncMongoClient wrapper
    'MongoDB',             # DEPRECATED alias for AsyncMongoDB
    'mongodb_lifespan',
    'get_database',
    # Connection management
    'DatabaseConnection',
    'DatabaseConfig',
    # Availability flags
    'PYMONGO_AVAILABLE',
    'ASYNC_PYMONGO_AVAILABLE',
    'MONGODB_AVAILABLE',  # DEPRECATED
    'MOTOR_AVAILABLE',    # DEPRECATED: alias for ASYNC_PYMONGO_AVAILABLE
]
