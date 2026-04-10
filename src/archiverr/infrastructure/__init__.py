"""
Infrastructure Module

Technical implementations for database, external services, and repositories.
Following Clean Architecture principles.

Submodules:
    - database: Database backends (MongoDB)
    - repositories: Repository pattern implementations
"""

from .database import DatabaseConnection, PersistenceInterface

__all__ = [
    'PersistenceInterface',
    'DatabaseConnection',
]
