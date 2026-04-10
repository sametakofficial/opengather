"""
Database Connection Module - DEPRECATED

⚠️ This module is deprecated. Use the following instead:

    from archiverr.infrastructure.database import mongodb_lifespan, AsyncMongoDB, get_database

Or for dependency injection:

    from archiverr.api.deps import get_database, get_async_db

This file is kept for backward compatibility only.
"""

import warnings

from archiverr.infrastructure.database.async_client import (
    AsyncMongoDB as MongoDB,
    get_database,
    mongodb_lifespan,
)

# Emit deprecation warning on import
warnings.warn(
    "archiverr.api.database is deprecated. "
    "Use archiverr.infrastructure.database or archiverr.api.deps instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['MongoDB', 'mongodb_lifespan', 'get_database']
