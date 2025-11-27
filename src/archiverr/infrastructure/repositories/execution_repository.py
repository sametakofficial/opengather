"""
Execution Repository

Repository for ExecutionState persistence operations.
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
            persistence: Persistence backend (Mock or MongoDB)
        """
        self._persistence = persistence
    
    def save(self, execution) -> None:
        """
        Save execution state.
        
        Args:
            execution: ExecutionState object
        """
        self._persistence.save_execution(execution)
    
    def get_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution by ID.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution dict or None
        """
        return self._persistence.get_execution(execution_id)
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all executions.
        
        Note: For MongoDB, this may be expensive. Consider using
        get_recent() with pagination instead.
        
        Returns:
            List of execution dicts
        """
        # For mock, we need to access internal data
        if hasattr(self._persistence, 'get_all_data'):
            data = self._persistence.get_all_data()
            return data.get("executions", [])
        
        # For MongoDB, use statistics to check count first
        stats = self._persistence.get_statistics()
        if stats.get("executions", 0) > 1000:
            raise RuntimeError(
                "Too many executions. Use get_recent() with pagination."
            )
        
        # MongoDB implementation would need custom method
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
        # MongoDB has delete_execution method
        if hasattr(self._persistence, 'delete_execution'):
            return self._persistence.delete_execution(execution_id)
        
        # Mock doesn't have delete - would need to implement
        return False
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent executions.
        
        Args:
            limit: Maximum number of executions to return
            
        Returns:
            List of execution dicts, ordered by start time (newest first)
        """
        if hasattr(self._persistence, 'get_recent_executions'):
            return self._persistence.get_recent_executions(limit)
        
        # Fallback for mock
        all_execs = self.get_all()
        sorted_execs = sorted(
            all_execs, 
            key=lambda x: x.get("started_at", ""), 
            reverse=True
        )
        return sorted_execs[:limit]
    
    def get_failed(self) -> List[Dict[str, Any]]:
        """
        Get failed executions.
        
        Returns:
            List of failed execution dicts
        """
        if hasattr(self._persistence, 'get_failed_executions'):
            return self._persistence.get_failed_executions()
        
        # Fallback for mock
        all_execs = self.get_all()
        return [e for e in all_execs if not e.get("success", True)]
