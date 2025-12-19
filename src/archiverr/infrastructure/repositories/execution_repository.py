"""
Run Repository

Repository for RunState persistence operations.
"""

from typing import List, Optional, Dict, Any

from ..database.interface import PersistenceInterface
from .base import BaseRepository


class ExecutionRepository(BaseRepository):
    """
    Repository for execution data access.
    
    Wraps PersistenceInterface for execution-specific operations.
    """
    
    def __init__(self, persistence: PersistenceInterface):
        """
        Initialize repository.
        
        Args:
            persistence: Persistence backend
        """
        self._persistence = persistence
    
    def save(self, execution) -> None:
        """
        Save execution state.
        
        Args:
            execution: RunState object
        """
        self._persistence.save_run(execution)
    
    def get_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution by ID.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution dict or None
        """
        return self._persistence.get_run(execution_id)
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all executions.
        
        Note: For MongoDB, this may be expensive. Consider using
        get_recent() with pagination instead.
        
        Returns:
            List of execution dicts
        """
        # Listing all runs is not implemented for this repository.
        # Prefer using dedicated query endpoints or a DB-level query layer.
        return []
    
    def delete(self, execution_id: str) -> bool:
        """
        Delete execution.
        
        Note: This should also delete related matches and plugin results.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            True if deleted, False if not found
        """
        if hasattr(self._persistence, 'delete_run'):
            return self._persistence.delete_run(execution_id)
        return False
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent executions.
        
        Args:
            limit: Maximum number of executions to return
            
        Returns:
            List of execution dicts, ordered by start time (newest first)
        """
        # Not implemented: requires DB-level query support.
        return []
    
    def get_failed(self) -> List[Dict[str, Any]]:
        """
        Get failed executions.
        
        Returns:
            List of failed execution dicts
        """
        # Not implemented: requires DB-level query support.
        return []
