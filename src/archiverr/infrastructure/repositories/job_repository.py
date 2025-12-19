"""
Job Repository

Repository for JobState persistence operations.
"""

from typing import Any

from ..database.interface import PersistenceInterface
from .base import BaseRepository


class JobRepository(BaseRepository):
    """
    Repository for job data access.
    
    Wraps PersistenceInterface for job-specific operations.
    """

    def __init__(self, persistence: PersistenceInterface):
        """
        Initialize repository.
        
        Args:
            persistence: Persistence backend
        """
        self._persistence = persistence

    def save(self, job) -> None:
        """
        Save job state.
        
        Args:
            job: JobState object
        """
        self._persistence.save_job(job)

    def get_by_id(self, job_id: str) -> dict[str, Any] | None:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job dict or None
        """
        return self._persistence.get_job(job_id)

    def get_all(self) -> list[dict[str, Any]]:
        """
        Get all jobs.
        
        Note: This is expensive for large datasets. 
        Use get_by_run() instead.
        
        Returns:
            List of job dicts
        """
        return []

    def delete(self, job_id: str) -> bool:
        """
        Delete job.
        
        Note: This should also delete related plugin results.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if deleted
        """
        # Not implemented for current backends
        return False

    def get_by_run(self, run_id: str) -> list[dict[str, Any]]:
        """
        Get all jobs for a run.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of job dicts
        """
        return self._persistence.get_jobs(run_id)

    def get_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get jobs by category (movie, show, etc.).
        
        Args:
            category: Category filter
            
        Returns:
            List of job dicts
        """
        all_jobs = self.get_all()
        return [j for j in all_jobs if j.get("category") == category]

    def get_failed(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """
        Get failed jobs.
        
        Args:
            run_id: Optional run ID filter
            
        Returns:
            List of failed job dicts
        """
        jobs = self.get_by_run(run_id) if run_id else self.get_all()
        return [j for j in jobs if not j.get("success", True)]


# Backward compatibility alias
MatchRepository = JobRepository
