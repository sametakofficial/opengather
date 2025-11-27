"""
Persistence Module (DEPRECATED)

This module is maintained for backward compatibility.
New code should import from archiverr.infrastructure.database instead.

Example:
    # Old (deprecated)
    from archiverr.persistence import MockPersistence
    
    # New (recommended)
    from archiverr.infrastructure.database import MockPersistence
"""

# Re-export from infrastructure for backward compatibility
from archiverr.infrastructure.database import (
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
