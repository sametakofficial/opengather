"""
DEPRECATED: Motor Async MongoDB Driver Module

⚠️ DEPRECATION NOTICE:
    Motor was deprecated by MongoDB in May 2025.
    Active development ends: May 2026
    Full support ends: May 2027
    
    This module is kept for backward compatibility only.
    Use async_client.py with PyMongo's AsyncMongoClient instead.
    
    Migration guide:
    - OLD: from archiverr.infrastructure.database.motor import MongoDB
    - NEW: from archiverr.infrastructure.database.async_client import AsyncMongoDB

Performance: PyMongo Async is 20-140% faster than Motor.
Source: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/
"""

import warnings

# Issue deprecation warning on import
warnings.warn(
    "motor.py is deprecated. Motor support ends May 2027. "
    "Use 'from archiverr.infrastructure.database.async_client import AsyncMongoDB' instead. "
    "PyMongo Async is 20-140% faster than Motor.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new async_client module for backward compatibility
from .async_client import (
    AsyncMongoDB as MongoDB,  # Alias for backward compatibility
    AsyncMongoDB,
    mongodb_lifespan,
    get_database,
)

__all__ = [
    'MongoDB',           # DEPRECATED alias
    'AsyncMongoDB',      # New name
    'mongodb_lifespan',
    'get_database',
]
