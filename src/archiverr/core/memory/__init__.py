"""
Memory Management - Session 11 Phase 9

Provides hot/cold tiering for plugin data:
- Hot tier: Active run data in memory
- Cold tier: Completed run data in MongoDB

Components:
- MemoryTracker: Track memory usage
- FlushManager: Evict data when threshold exceeded
- LazyLoader: Load evicted data on demand
"""

from .tracker import MemoryTracker, MemoryStats
from .flush_manager import FlushManager
from .lazy_loader import LazyLoader

__all__ = [
    'MemoryTracker',
    'MemoryStats',
    'FlushManager',
    'LazyLoader',
]
