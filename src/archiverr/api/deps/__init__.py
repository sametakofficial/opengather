"""
API Dependencies Package

Provides dependency injection for FastAPI routes.
Split into modules for maintainability:
- database.py: Database connections (Motor async, PyMongo sync)
- common.py: Common utilities and wrappers
"""

from .database import (
    get_async_db,
    get_sync_db,
    get_database,
    close_connections
)
from .common import (
    AsyncPersistenceWrapper,
    get_persistence
)

__all__ = [
    # Database
    'get_async_db',
    'get_sync_db', 
    'get_database',
    'close_connections',
    # Persistence
    'AsyncPersistenceWrapper',
    'get_persistence',
]
