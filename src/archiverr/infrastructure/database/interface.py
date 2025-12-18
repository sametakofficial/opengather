"""
Persistence Interface

Abstract base class for persistence backends.
Supports MongoDB persistence implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.state.models import RunState, JobState


class PersistenceInterface(ABC):
    """
    Abstract persistence interface.
    
    All persistence backends must implement these methods.
    This allows swapping between MongoDB persistence implementations without code changes.
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
    def save_run(self, run: Dict[str, Any]) -> None:
        """
        Save or update run state (replaces save_execution).
        
        Args:
            run: RunState.to_dict() output
        """
        pass
    
    @abstractmethod
    def save_job(self, job: Dict[str, Any]) -> None:
        """
        Save or update job state (replaces save_match).
        
        Args:
            job: JobState.to_dict() output
        """
        pass
    
    @abstractmethod
    def save_plugin(self, plugin: Dict[str, Any]) -> None:
        """
        Save plugin data to separate collection.
        
        This is the key difference from the old system:
        - Plugins are stored separately for memory management
        - Enables hot/cold tiering for large datasets
        
        Args:
            plugin: Flat plugin data dict
        """
        pass
    
    @abstractmethod
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get run by ID.
        
        Args:
            run_id: Run ID (format: run_abc123)
            
        Returns:
            Run dict or None if not found
        """
        pass
    
    @abstractmethod
    def get_jobs(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all jobs for a run.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of job dicts sorted by index
        """
        pass
    
    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID (format: job_run_abc123_0)
            
        Returns:
            Job dict or None if not found
        """
        pass
    
    @abstractmethod
    def get_plugins(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all plugin data for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of plugin data dicts
        """
        pass
    
    @abstractmethod
    def get_plugin(self, job_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get specific plugin data for a job.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None if not found
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
            "runs": 0,
            "jobs": 0,
            "plugins": 0
        }
