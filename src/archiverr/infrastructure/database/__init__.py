"""
Database Module

Persistence layer implementations following Repository Pattern.

Backends:
    - MockPersistence: JSON file-based (development/testing)
    - MongoDBPersistence: MongoDB with Motor async driver (production)

Usage:
    from archiverr.infrastructure.database import MockPersistence
    
    persistence = MockPersistence(base_path="./mock_db")
    persistence.connect()
    persistence.save_execution(execution)
    persistence.disconnect()
"""

from .interface import PersistenceInterface
from .mock import MockPersistence
from .connection import DatabaseConnection, DatabaseConfig

# Conditional MongoDB import
try:
    from .mongodb import MongoDBPersistence
    MONGODB_AVAILABLE = True
except ImportError:
    MongoDBPersistence = None
    MONGODB_AVAILABLE = False

__all__ = [
    'PersistenceInterface',
    'MockPersistence',
    'MongoDBPersistence',
    'DatabaseConnection',
    'DatabaseConfig',
    'MONGODB_AVAILABLE'
]
