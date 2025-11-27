"""
FastAPI Dependencies - DEPRECATED

⚠️ This module is deprecated. Use the following instead:

    from archiverr.api.deps import get_database, get_persistence, get_async_db, get_sync_db

This file is kept for backward compatibility only.
"""

import warnings

# Re-export from new location for backward compatibility
from archiverr.api.deps.database import (
    get_async_db,
    get_sync_db,
    get_database,
    close_connections,
    reset_connections
)
from archiverr.api.deps.common import (
    AsyncPersistenceWrapper,
    get_persistence
)

# Emit deprecation warning on import
warnings.warn(
    "archiverr.api.dependencies is deprecated. "
    "Use archiverr.api.deps instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy aliases for backward compatibility
get_db = get_database
get_db_connection = get_async_db
close_db_connection = close_connections

__all__ = [
    'get_async_db',
    'get_sync_db',
    'get_database',
    'get_db',
    'get_db_connection',
    'close_connections',
    'close_db_connection',
    'reset_connections',
    'AsyncPersistenceWrapper',
    'get_persistence',
]
