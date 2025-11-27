"""
Repository Module

Repository pattern implementations for data access abstraction.
Provides clean separation between business logic and data storage.
"""

from .base import BaseRepository
from .execution_repository import ExecutionRepository
from .match_repository import MatchRepository
from .plugin_result_repository import PluginResultRepository

__all__ = [
    'BaseRepository',
    'ExecutionRepository',
    'MatchRepository',
    'PluginResultRepository'
]
