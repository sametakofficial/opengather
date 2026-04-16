"""
Persistence Interface

Abstract base class for persistence backends.
Supports MongoDB persistence implementations.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


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
    def save_run(self, run: dict[str, Any]) -> None:
        """
        Save or update run state (replaces save_execution).
        
        Args:
            run: RunState.to_dict() output
        """
        pass

    @abstractmethod
    def save_job(self, job: dict[str, Any]) -> None:
        """
        Save or update job state (replaces save_match).
        
        Args:
            job: JobState.to_dict() output
        """
        pass

    @abstractmethod
    def save_plugin(self, plugin: dict[str, Any]) -> None:
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
    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """
        Get run by ID.
        
        Args:
            run_id: Run ID (format: run_abc123)
            
        Returns:
            Run dict or None if not found
        """
        pass

    @abstractmethod
    def get_jobs(self, run_id: str) -> list[dict[str, Any]]:
        """
        Get all jobs for a run.
        
        Args:
            run_id: Run ID
            
        Returns:
            List of job dicts sorted by index
        """
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID (format: job_run_abc123_0)
            
        Returns:
            Job dict or None if not found
        """
        pass

    @abstractmethod
    def get_plugins(self, job_id: str) -> list[dict[str, Any]]:
        """
        Get all plugin data for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            List of plugin data dicts
        """
        pass

    @abstractmethod
    def get_plugin(self, job_id: str, plugin_name: str) -> dict[str, Any] | None:
        """
        Get specific plugin data for a job.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            
        Returns:
            Plugin data dict or None if not found
        """
        pass

    # ------------------------------------------------------------------
    # Plugin execution records (recovery surface)
    # ------------------------------------------------------------------
    # Per dataset `11-recovery.yml`, we persist each plugin's terminal (or
    # non-terminal, if interrupted) state so a later startup scan can
    # identify crashed attempts. Implementations may be no-op.

    def save_plugin_execution(
        self,
        run_id: str,
        job_id: str,
        plugin_name: str,
        state: str,
        attempt: int = 1,
        error: str | None = None,
        timestamp: Any = None,
    ) -> None:
        """
        Record a plugin execution state transition.

        States: ``started``, ``completed``, ``failed``, ``skipped``, ``crashed``.

        Default implementation is a no-op; implementations that care about
        recovery override this.
        """
        return None

    def get_unfinished_plugin_executions(
        self, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Return plugin execution records whose state is non-terminal
        (``started`` / ``running``). Used by the startup recovery scan in
        ``mode=full``.

        Args:
            run_id: Optional run filter; all runs if None.

        Returns:
            List of execution dicts. Empty list if the backend does not
            track executions.
        """
        return []

    def get_statistics(self) -> dict[str, Any]:
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
