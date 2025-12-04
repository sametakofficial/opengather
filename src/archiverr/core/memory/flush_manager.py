"""
Memory Flush Management - Session 11 Phase 9

Manages flushing (evicting) plugin data from memory to MongoDB.
"""

from typing import Set, Optional, Any, List, TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from archiverr.infrastructure.persistence.interface import PersistenceInterface
    from .tracker import MemoryTracker


class FlushManager:
    """
    Manages flushing (evicting) plugin data from memory to MongoDB.
    
    Eviction happens when:
    1. Memory threshold exceeded
    2. Run completed
    3. Manual trigger
    
    Thread-safe: Uses lock for concurrent access.
    
    Usage:
        manager = FlushManager(state, persistence, tracker)
        evicted = manager.check_and_evict()
    """
    
    def __init__(
        self,
        persistence: "PersistenceInterface",
        tracker: "MemoryTracker",
        state_plugin_cache: dict
    ):
        """
        Initialize flush manager.
        
        Args:
            persistence: Persistence interface for MongoDB operations
            tracker: Memory tracker instance
            state_plugin_cache: Reference to state manager's plugin cache
        """
        self._persistence = persistence
        self._tracker = tracker
        self._plugin_cache = state_plugin_cache  # Reference to actual cache
        self._evicted_jobs: Set[str] = set()
        self._lock = threading.Lock()
    
    def check_and_evict(self, completed_job_ids: Optional[List[str]] = None) -> int:
        """
        Check memory and evict if needed.
        
        Args:
            completed_job_ids: Optional list of completed job IDs to consider
            
        Returns:
            Number of jobs evicted
        """
        if not self._tracker.should_evict():
            return 0
        
        if completed_job_ids is None:
            completed_job_ids = []
        
        return self._evict_jobs(completed_job_ids)
    
    def _evict_jobs(self, completed_job_ids: List[str]) -> int:
        """
        Evict completed job plugin data.
        
        Args:
            completed_job_ids: List of completed job IDs
            
        Returns:
            Number of jobs evicted
        """
        with self._lock:
            # Filter out already evicted
            candidates = [
                jid for jid in completed_job_ids
                if jid not in self._evicted_jobs
            ]
            
            # Get prioritized candidates (largest first)
            to_evict = self._tracker.get_eviction_candidates(candidates)
            
            evicted_count = 0
            for job_id in to_evict:
                if self._evict_job(job_id):
                    evicted_count += 1
                
                # Check if we're below threshold now
                if not self._tracker.should_evict():
                    break
            
            return evicted_count
    
    def _evict_job(self, job_id: str) -> bool:
        """
        Evict a single job's plugin data.
        
        Plugin data is already in MongoDB (written on plugin complete).
        We just need to clear the in-memory reference.
        
        Args:
            job_id: Job ID to evict
            
        Returns:
            True if evicted successfully
        """
        try:
            # Clear from plugin cache
            self._plugin_cache.pop(job_id, None)
            
            # Clear from tracker
            self._tracker.unregister_job(job_id)
            
            # Mark as evicted
            self._evicted_jobs.add(job_id)
            
            return True
        except Exception:
            return False
    
    def evict_run(self, run_id: str, job_ids: List[str]) -> int:
        """
        Evict all plugin data for a completed run.
        
        Called when run completes.
        
        Args:
            run_id: Run ID (for logging)
            job_ids: Job IDs in this run
            
        Returns:
            Number of jobs evicted
        """
        with self._lock:
            evicted_count = 0
            for job_id in job_ids:
                if self._evict_job(job_id):
                    evicted_count += 1
            
            return evicted_count
    
    def is_evicted(self, job_id: str) -> bool:
        """Check if job's plugin data was evicted."""
        return job_id in self._evicted_jobs
    
    def get_evicted_count(self) -> int:
        """Get count of evicted jobs."""
        return len(self._evicted_jobs)
    
    def clear_evicted_set(self) -> None:
        """Clear evicted jobs set (for cleanup)."""
        with self._lock:
            self._evicted_jobs.clear()
