"""
Infrastructure Module

Technical implementations for database, external services, and repositories.
Following Clean Architecture principles.

Submodules:
    - database: Database backends (Mock, MongoDB)
    - repositories: Repository pattern implementations
"""

from .database import (
    PersistenceInterface,
    MockPersistence,
    DatabaseConnection,
    MONGODB_AVAILABLE
)

__all__ = [
    'PersistenceInterface',
    'MockPersistence', 
    'DatabaseConnection',
    'MONGODB_AVAILABLE'
]
