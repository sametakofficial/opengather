"""
Memory Usage Tracking - Session 11 Phase 9

Tracks plugin data memory usage and determines when eviction is needed.
"""

import sys
import gc
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_mb: float
    plugins_mb: float
    jobs_mb: float
    threshold_mb: float
    should_evict: bool
    tracked_jobs: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "total_mb": round(self.total_mb, 2),
            "plugins_mb": round(self.plugins_mb, 2),
            "jobs_mb": round(self.jobs_mb, 2),
            "threshold_mb": self.threshold_mb,
            "should_evict": self.should_evict,
            "tracked_jobs": self.tracked_jobs
        }


class MemoryTracker:
    """
    Track memory usage and determine when to evict.
    
    Uses sys.getsizeof for rough estimation.
    For production, consider tracemalloc or memory_profiler.
    
    Usage:
        tracker = MemoryTracker(threshold_mb=500)
        tracker.register_plugin_data(job_id, plugin_name, data)
        
        if tracker.should_evict():
            candidates = tracker.get_eviction_candidates(completed_jobs)
    """
    
    def __init__(self, threshold_mb: float = 500.0):
        """
        Initialize tracker.
        
        Args:
            threshold_mb: Memory threshold in MB before eviction triggers
        """
        self._threshold_mb = threshold_mb
        self._plugin_cache: Dict[str, Dict[str, Any]] = {}
        self._size_cache: Dict[str, int] = {}  # job_id -> estimated size in bytes
    
    def register_plugin_data(self, job_id: str, plugin_name: str, data: Any) -> None:
        """
        Register plugin data for tracking.
        
        Args:
            job_id: Job ID
            plugin_name: Plugin name
            data: Plugin data to track
        """
        if job_id not in self._plugin_cache:
            self._plugin_cache[job_id] = {}
        
        self._plugin_cache[job_id][plugin_name] = data
        
        # Update size estimation
        self._size_cache[job_id] = self._estimate_size(self._plugin_cache[job_id])
    
    def unregister_job(self, job_id: str) -> None:
        """
        Remove job from tracking (after eviction).
        
        Args:
            job_id: Job ID to remove
        """
        self._plugin_cache.pop(job_id, None)
        self._size_cache.pop(job_id, None)
    
    def get_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        plugins_bytes = sum(self._size_cache.values())
        plugins_mb = plugins_bytes / (1024 * 1024)
        
        return MemoryStats(
            total_mb=self._get_process_memory_mb(),
            plugins_mb=plugins_mb,
            jobs_mb=0,  # TODO: Track jobs separately if needed
            threshold_mb=self._threshold_mb,
            should_evict=plugins_mb > self._threshold_mb,
            tracked_jobs=len(self._plugin_cache)
        )
    
    def should_evict(self) -> bool:
        """Check if eviction is needed."""
        stats = self.get_stats()
        return stats.should_evict
    
    def get_eviction_candidates(self, completed_job_ids: List[str]) -> List[str]:
        """
        Get jobs to evict, prioritized by size (largest first).
        
        Args:
            completed_job_ids: List of completed job IDs
            
        Returns:
            List of job IDs to evict, sorted by size descending
        """
        # Filter to only jobs we're tracking
        candidates = [
            job_id for job_id in completed_job_ids
            if job_id in self._plugin_cache
        ]
        
        # Sort by size (largest first for max memory recovery)
        candidates.sort(key=lambda jid: self._size_cache.get(jid, 0), reverse=True)
        
        return candidates
    
    def get_job_size_mb(self, job_id: str) -> float:
        """Get estimated size of a job's plugin data in MB."""
        size_bytes = self._size_cache.get(job_id, 0)
        return size_bytes / (1024 * 1024)
    
    def _estimate_size(self, obj: Any, seen: set = None) -> int:
        """
        Estimate object size in bytes recursively.
        
        Args:
            obj: Object to measure
            seen: Set of already seen object IDs (for cycle detection)
            
        Returns:
            Estimated size in bytes
        """
        if seen is None:
            seen = set()
        
        obj_id = id(obj)
        if obj_id in seen:
            return 0
        seen.add(obj_id)
        
        try:
            if isinstance(obj, dict):
                return sum(
                    self._estimate_size(k, seen) + self._estimate_size(v, seen)
                    for k, v in obj.items()
                ) + sys.getsizeof(obj)
            elif isinstance(obj, (list, tuple, set, frozenset)):
                return sum(
                    self._estimate_size(item, seen) for item in obj
                ) + sys.getsizeof(obj)
            elif isinstance(obj, str):
                return len(obj.encode('utf-8', errors='replace'))
            elif isinstance(obj, bytes):
                return len(obj)
            else:
                return sys.getsizeof(obj)
        except Exception:
            return 100  # Default estimate for problematic objects
    
    def _get_process_memory_mb(self) -> float:
        """Get current process memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            # Fallback: rough estimate from tracked data
            tracked_bytes = sum(self._size_cache.values())
            # Assume tracked data is ~10% of total (rough heuristic)
            return (tracked_bytes * 10) / (1024 * 1024)
        except Exception:
            return 0.0
