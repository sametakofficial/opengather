"""
Match Repository

Repository for MatchState persistence operations.
"""

from typing import List, Optional, Dict, Any

from ..database.interface import PersistenceInterface
from .base import BaseRepository


class MatchRepository(BaseRepository):
    """
    Repository for match data access.
    
    Wraps PersistenceInterface for match-specific operations.
    """
    
    def __init__(self, persistence: PersistenceInterface):
        """
        Initialize repository.
        
        Args:
            persistence: Persistence backend
        """
        self._persistence = persistence
    
    def save(self, match) -> None:
        """
        Save match state.
        
        Args:
            match: JobState/job dict
        """
        self._persistence.save_job(match)
    
    def get_by_id(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Get match by ID.
        
        Args:
            match_id: Job ID
            
        Returns:
            Match dict or None
        """
        return self._persistence.get_job(match_id)
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all matches.
        
        Note: This is expensive for large datasets. 
        Use get_by_execution() instead.
        
        Returns:
            List of match dicts
        """
        return []
    
    def delete(self, match_id: str) -> bool:
        """
        Delete match.
        
        Note: This should also delete related plugin results.
        
        Args:
            match_id: Job ID
            
        Returns:
            True if deleted
        """
        # Not implemented for current backends
        return False
    
    def get_by_execution(self, execution_id: str) -> List[Dict[str, Any]]:
        """
        Get all matches for an execution.
        
        Args:
            execution_id: Run ID
            
        Returns:
            List of match dicts
        """
        return self._persistence.get_jobs(execution_id)
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get matches by category (movie, show, etc.).
        
        Args:
            category: Category filter
            
        Returns:
            List of match dicts
        """
        all_matches = self.get_all()
        return [m for m in all_matches if m.get("category") == category]
    
    def get_failed(self, execution_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get failed matches.
        
        Args:
            execution_id: Optional execution ID filter
            
        Returns:
            List of failed match dicts
        """
        if execution_id:
            matches = self.get_by_execution(execution_id)
        else:
            matches = self.get_all()
        
        return [m for m in matches if not m.get("success", True)]
