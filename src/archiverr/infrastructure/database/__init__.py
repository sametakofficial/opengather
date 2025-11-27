"""
Database Module

Persistence layer implementations following Repository Pattern.

Backends:
    - MockPersistence: JSON file-based (development/testing)
    - PyMongoPersistence: MongoDB with PyMongo sync driver (CLI)
    - Motor: Async MongoDB driver (FastAPI/API)

Usage:
    # Sync persistence (CLI)
    from archiverr.infrastructure.database import MockPersistence
    persistence = MockPersistence(base_path="./mock_db")
    persistence.connect()
    
    # Async Motor (API)
    from archiverr.infrastructure.database import mongodb_lifespan, MongoDB
    app = FastAPI(lifespan=mongodb_lifespan)
"""

from .interface import PersistenceInterface
from .mock import MockPersistence
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

# Motor async driver (for FastAPI)
try:
    from .motor import MongoDB, mongodb_lifespan, get_database
    MOTOR_AVAILABLE = True
except ImportError:
    MongoDB = None
    mongodb_lifespan = None
    get_database = None
    MOTOR_AVAILABLE = False

__all__ = [
    # Interfaces
    'PersistenceInterface',
    # Sync backends
    'MockPersistence',
    'PyMongoPersistence',  # NEW: Recommended for CLI
    'MongoDBPersistence',   # DEPRECATED: Use PyMongoPersistence
    # Async Motor
    'MongoDB',
    'mongodb_lifespan',
    'get_database',
    # Connection management
    'DatabaseConnection',
    'DatabaseConfig',
    # Availability flags
    'PYMONGO_AVAILABLE',
    'MONGODB_AVAILABLE',  # DEPRECATED
    'MOTOR_AVAILABLE',
]
