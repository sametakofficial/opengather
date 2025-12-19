"""
Run Repository

Repository for RunState persistence operations.
"""

from typing import Any

from ..database.interface import PersistenceInterface
from .base import BaseRepository


class RunRepository(BaseRepository):
    """
    Repository for run data access.
    
    Wraps PersistenceInterface for run-specific operations.
    """

    def __init__(self, persistence: PersistenceInterface):
        """
        Initialize repository.
        
        Args:
            persistence: Persistence backend
        """
        self._persistence = persistence

    def save(self, run) -> None:
        """
        Save run state.
        
        Args:
            run: RunState object
        """
        self._persistence.save_run(run)

    def get_by_id(self, run_id: str) -> dict[str, Any] | None:
        """
        Get run by ID.
        
        Args:
            run_id: Run ID
            
        Returns:
            Run dict or None
        """
        return self._persistence.get_run(run_id)

    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all runs.
        
        Note: For MongoDB, this may be expensive. Consider using
        get_recent() with pagination instead.
        
        Returns:
            List of run dicts
        """
        # Listing all runs is not implemented for this repository.
        # Prefer using dedicated query endpoints or a DB-level query layer.
        return []

    def delete(self, run_id: str) -> bool:
        """
        Delete run.
        
        Note: This should also delete related jobs and plugin results.
        
        Args:
            run_id: Run ID
            
        Returns:
            True if deleted, False if not found
        """
        if hasattr(self._persistence, 'delete_run'):
            return self._persistence.delete_run(run_id)
        return False

    def get_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent runs.
        
        Args:
            limit: Maximum number of runs to return
            
        Returns:
            List of run dicts, ordered by start time (newest first)
        """
        # Not implemented: requires DB-level query support.
        return []

    def get_failed(self) -> list[dict[str, Any]]:
        """
        Get failed runs.
        
        Returns:
            List of failed run dicts
        """
        # Not implemented: requires DB-level query support.
        return []


# Backward compatibility alias
ExecutionRepository = RunRepository
