"""Persistence Delegate - Extracted from GlobalStateManager.

This module handles all persistence operations for state objects.
Follows Single Responsibility Principle by separating persistence from state management.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import JobState, RunState


class PersistenceDelegate:
    """
    Handles persistence operations for runs, jobs, and plugins.
    
    Extracted from GlobalStateManager to follow SRP.
    Wraps the persistence layer with error handling and logging.
    """

    def __init__(
        self,
        persistence=None,
        logger: Callable | None = None
    ):
        """
        Initialize persistence delegate.
        
        Args:
            persistence: Persistence backend (e.g., PyMongoPersistence)
            logger: Optional logging function (level, component, message, **kwargs)
        """
        self._persistence = persistence
        self._log = logger or self._noop_log

    def _noop_log(self, level: str, component: str, message: str, **kwargs):
        """No-op logger when none provided."""
        pass

    def configure(self, persistence=None, logger: Callable = None):
        """Reconfigure persistence backend."""
        if persistence is not None:
            self._persistence = persistence
        if logger is not None:
            self._log = logger

    @property
    def is_available(self) -> bool:
        """Check if persistence backend is available."""
        return self._persistence is not None

    def save_run(self, run: 'RunState') -> bool:
        """
        Save run state to persistence.
        
        Args:
            run: RunState to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self._persistence or not hasattr(self._persistence, 'save_run'):
            return False

        try:
            self._persistence.save_run(run)
            return True
        except (OSError, ConnectionError) as e:
            self._log("error", "persistence", f"Failed to save run: {e}")
            return False
        except Exception as e:
            self._log("error", "persistence", f"Unexpected error saving run: {e}")
            return False

    def save_job(self, job: 'JobState') -> bool:
        """
        Save job state to persistence.
        
        Args:
            job: JobState to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self._persistence or not hasattr(self._persistence, 'save_job'):
            return False

        try:
            self._persistence.save_job(job)
            return True
        except (OSError, ConnectionError) as e:
            self._log("error", "persistence", f"Failed to save job: {e}")
            return False
        except Exception as e:
            self._log("error", "persistence", f"Unexpected error saving job: {e}")
            return False

    def save_plugin(self, plugin_doc: dict[str, Any]) -> bool:
        """
        Save plugin data to persistence.
        
        Args:
            plugin_doc: Plugin document with job_id, plugin_name, data, etc.
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self._persistence or not hasattr(self._persistence, 'save_plugin'):
            return False

        try:
            self._persistence.save_plugin(plugin_doc)
            return True
        except (OSError, ConnectionError) as e:
            self._log("error", "persistence", f"Failed to save plugin: {e}")
            return False
        except Exception as e:
            self._log("error", "persistence", f"Unexpected error saving plugin: {e}")
            return False

