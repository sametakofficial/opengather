"""
FS Lock System - 

Provides file system locking with:
- Static path validation (no variables allowed)
- Startup validation
- Lock acquisition and release
- Conflict detection
"""

from .manager import FSLockManager
from .validator import FSLockValidator

__all__ = ['FSLockManager', 'FSLockValidator']
