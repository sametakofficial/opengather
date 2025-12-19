"""
Repository Module

Repository pattern implementations for data access abstraction.
Provides clean separation between business logic and data storage.
"""

from .base import BaseRepository
from .job_repository import JobRepository, MatchRepository
from .plugin_result_repository import PluginResultRepository
from .run_repository import ExecutionRepository, RunRepository

__all__ = [
    'BaseRepository',
    # New names (preferred)
    'RunRepository',
    'JobRepository',
    # Legacy aliases (backward compatibility)
    'ExecutionRepository',
    'MatchRepository',
    'PluginResultRepository'
]
