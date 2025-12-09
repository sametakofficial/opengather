"""
Infrastructure Module

Technical implementations for database, external services, and repositories.
Following Clean Architecture principles.

Submodules:
    - database: Database backends (MongoDB)
    - repositories: Repository pattern implementations
"""

from .database import (
    PersistenceInterface,
    DatabaseConnection,
    MONGODB_AVAILABLE
)

__all__ = [
    'PersistenceInterface',
    'DatabaseConnection',
    'MONGODB_AVAILABLE'
]
