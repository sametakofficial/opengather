"""
Persistence Interface

Abstract base class for persistence backends.
Supports both sync (Mock) and async (MongoDB) implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class PersistenceInterface(ABC):
    """
    Abstract persistence interface.
    
    All persistence backends must implement these methods.
    This allows swapping between mock and MongoDB without code changes.
    
    Note: MongoDB implementation uses async versions of these methods.
    The sync interface is maintained for backward compatibility with Mock.
    """
    
    @abstractmethod
    def connect(self) -> None:
        """Connect to persistence backend"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from persistence backend"""
        pass
    
    @abstractmethod
    def save_execution(self, execution) -> None:
        """
        Save or update execution state.
        
        Args:
            execution: ExecutionState object with to_dict() method
        """
        pass
    
    @abstractmethod
    def save_match(self, match) -> None:
        """
        Save or update match state.
        
        Args:
            match: MatchState object with to_dict() method
        """
        pass
    
    @abstractmethod
    def save_plugin_result(
        self, 
        execution_id: str, 
        match_index: int, 
        plugin_name: str, 
        result: Dict[str, Any]
    ) -> None:
        """
        Save plugin result.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            plugin_name: Plugin name
            result: Plugin result dict (plugin-specific, opaque to core)
        """
        pass
    
    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution by ID.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution dict or None if not found
        """
        pass
    
    @abstractmethod
    def get_matches(self, execution_id: str) -> List[Dict[str, Any]]:
        """
        Get all matches for execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            List of match dicts
        """
        pass
    
    @abstractmethod
    def get_plugin_results(
        self, 
        execution_id: str, 
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all plugin results for a match.
        
        Args:
            execution_id: Execution ID
            match_index: Match index
            
        Returns:
            Dict of plugin_name -> result data
        """
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dict with collection counts and metadata
        """
        return {
            "backend": self.__class__.__name__,
            "executions": 0,
            "matches": 0,
            "plugin_results": 0
        }
