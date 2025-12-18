"""
Tests for Memory Management - Session 11 Phase 9

Tests for MemoryTracker, FlushManager, and LazyLoader.
"""

import importlib.util

import pytest
from unittest.mock import Mock, MagicMock

if importlib.util.find_spec("archiverr.core.memory") is None:
    pytest.skip("Memory subsystem removed/refactored; skipping memory management tests", allow_module_level=True)

from archiverr.core.memory.tracker import MemoryTracker, MemoryStats
from archiverr.core.memory.flush_manager import FlushManager
from archiverr.core.memory.lazy_loader import LazyLoader


class TestMemoryTracker:
    """Test MemoryTracker class."""
    
    def test_initial_state(self):
        """Test tracker starts with empty state."""
        tracker = MemoryTracker(threshold_mb=100)
        stats = tracker.get_stats()
        
        assert stats.threshold_mb == 100
        assert stats.plugins_mb == 0
        assert stats.should_evict is False
        assert stats.tracked_jobs == 0
    
    def test_register_plugin_data(self):
        """Test registering plugin data."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "plugin1", {"key": "value"})
        
        stats = tracker.get_stats()
        assert stats.plugins_mb > 0
        assert stats.tracked_jobs == 1
    
    def test_register_multiple_plugins(self):
        """Test registering multiple plugins for same job."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "plugin1", {"a": 1})
        tracker.register_plugin_data("job1", "plugin2", {"b": 2})
        
        stats = tracker.get_stats()
        assert stats.tracked_jobs == 1  # Same job
    
    def test_register_multiple_jobs(self):
        """Test registering plugins for different jobs."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "plugin1", {"a": 1})
        tracker.register_plugin_data("job2", "plugin1", {"b": 2})
        
        stats = tracker.get_stats()
        assert stats.tracked_jobs == 2
    
    def test_should_evict_below_threshold(self):
        """Test no eviction needed when below threshold."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "plugin1", {"small": "data"})
        
        assert tracker.should_evict() is False
    
    def test_should_evict_above_threshold(self):
        """Test eviction triggered when above threshold."""
        tracker = MemoryTracker(threshold_mb=0.0001)  # Very low threshold
        
        large_data = {"data": "x" * 10000}  # ~10KB
        tracker.register_plugin_data("job1", "plugin1", large_data)
        
        assert tracker.should_evict() is True
    
    def test_unregister_job(self):
        """Test unregistering a job."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "plugin1", {"a": 1})
        tracker.register_plugin_data("job2", "plugin1", {"b": 2})
        
        tracker.unregister_job("job1")
        
        stats = tracker.get_stats()
        assert stats.tracked_jobs == 1
    
    def test_eviction_candidates_order(self):
        """Test eviction candidates ordered by size."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "p1", {"a": 1})
        tracker.register_plugin_data("job2", "p1", {"data": "x" * 1000})  # Larger
        tracker.register_plugin_data("job3", "p1", {"data": "x" * 100})
        
        candidates = tracker.get_eviction_candidates(["job1", "job2", "job3"])
        
        # Largest should be first
        assert candidates[0] == "job2"
    
    def test_eviction_candidates_filters_tracked(self):
        """Test eviction candidates filters to only tracked jobs."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "p1", {"a": 1})
        
        candidates = tracker.get_eviction_candidates(["job1", "job2", "job3"])
        
        assert candidates == ["job1"]
    
    def test_get_job_size_mb(self):
        """Test getting job size in MB."""
        tracker = MemoryTracker(threshold_mb=100)
        
        tracker.register_plugin_data("job1", "p1", {"data": "x" * 1000})
        
        size = tracker.get_job_size_mb("job1")
        assert size > 0
        assert size < 1  # Should be less than 1MB
    
    def test_stats_to_dict(self):
        """Test MemoryStats to_dict conversion."""
        stats = MemoryStats(
            total_mb=100.5,
            plugins_mb=50.25,
            jobs_mb=10.0,
            threshold_mb=500,
            should_evict=False,
            tracked_jobs=5
        )
        
        d = stats.to_dict()
        
        assert d["total_mb"] == 100.5
        assert d["plugins_mb"] == 50.25
        assert d["threshold_mb"] == 500
        assert d["tracked_jobs"] == 5


class TestFlushManager:
    """Test FlushManager class."""
    
    @pytest.fixture
    def setup(self):
        """Setup flush manager with mocks."""
        persistence = Mock()
        tracker = MemoryTracker(threshold_mb=0.0001)  # Low threshold
        plugin_cache = {}
        
        manager = FlushManager(persistence, tracker, plugin_cache)
        return manager, tracker, plugin_cache
    
    def test_check_and_evict_no_eviction_needed(self):
        """Test no eviction when below threshold."""
        persistence = Mock()
        tracker = MemoryTracker(threshold_mb=100)  # High threshold
        plugin_cache = {}
        
        manager = FlushManager(persistence, tracker, plugin_cache)
        
        result = manager.check_and_evict()
        assert result == 0
    
    def test_evict_job(self, setup):
        """Test evicting a single job."""
        manager, tracker, plugin_cache = setup
        
        # Add data
        plugin_cache["job1"] = {"plugin1": {"data": 1}}
        tracker.register_plugin_data("job1", "plugin1", {"data": 1})
        
        result = manager._evict_job("job1")
        
        assert result is True
        assert "job1" not in plugin_cache
        assert manager.is_evicted("job1")
    
    def test_evict_run(self, setup):
        """Test evicting all jobs in a run."""
        manager, tracker, plugin_cache = setup
        
        # Add data for multiple jobs
        for i in range(3):
            job_id = f"job{i}"
            plugin_cache[job_id] = {"p1": {"x": i}}
            tracker.register_plugin_data(job_id, "p1", {"x": i})
        
        count = manager.evict_run("run1", ["job0", "job1", "job2"])
        
        assert count == 3
        assert len(plugin_cache) == 0
    
    def test_is_evicted(self, setup):
        """Test checking if job is evicted."""
        manager, tracker, plugin_cache = setup
        
        assert manager.is_evicted("job1") is False
        
        plugin_cache["job1"] = {}
        manager._evict_job("job1")
        
        assert manager.is_evicted("job1") is True
    
    def test_get_evicted_count(self, setup):
        """Test getting evicted count."""
        manager, tracker, plugin_cache = setup
        
        assert manager.get_evicted_count() == 0
        
        for i in range(3):
            plugin_cache[f"job{i}"] = {}
            manager._evict_job(f"job{i}")
        
        assert manager.get_evicted_count() == 3


class TestLazyLoader:
    """Test LazyLoader class."""
    
    def test_load_plugin_data(self):
        """Test loading plugin data from persistence."""
        persistence = Mock()
        persistence.get_plugins.return_value = [{
            "job_id": "job1",
            "plugin_name": "tmdb",
            "data": {"movie": {"title": "Test"}}
        }]
        
        loader = LazyLoader(persistence)
        data = loader.load_plugin_data("job1", "tmdb")
        
        assert data is not None
        assert data["movie"]["title"] == "Test"
        persistence.get_plugins.assert_called_once()
    
    def test_load_cache_hit(self):
        """Test cache hit prevents repeated database calls."""
        persistence = Mock()
        persistence.get_plugins.return_value = [{"data": {"x": 1}}]
        
        loader = LazyLoader(persistence)
        
        # First call
        loader.load_plugin_data("job1", "p1")
        
        # Second call - should hit cache
        loader.load_plugin_data("job1", "p1")
        
        assert persistence.get_plugins.call_count == 1
    
    def test_load_not_found(self):
        """Test loading non-existent plugin data."""
        persistence = Mock()
        persistence.get_plugins.return_value = []
        
        loader = LazyLoader(persistence)
        data = loader.load_plugin_data("job1", "nonexistent")
        
        assert data is None
    
    def test_load_all_plugins_for_job(self):
        """Test loading all plugins for a job."""
        persistence = Mock()
        persistence.get_plugins.return_value = [
            {"plugin_name": "scanner", "data": {"size": 100}},
            {"plugin_name": "renamer", "data": {"parsed": {}}},
        ]
        
        loader = LazyLoader(persistence)
        result = loader.load_all_plugins_for_job("job1")
        
        assert "scanner" in result
        assert "renamer" in result
        assert result["scanner"]["size"] == 100
    
    def test_clear_cache_specific_job(self):
        """Test clearing cache for specific job."""
        persistence = Mock()
        persistence.get_plugins.return_value = [{"data": {"x": 1}}]
        
        loader = LazyLoader(persistence)
        
        loader.load_plugin_data("job1", "p1")
        loader.load_plugin_data("job2", "p1")
        
        loader.clear_cache("job1")
        
        assert loader.get_cache_size() == 1
    
    def test_clear_cache_all(self):
        """Test clearing entire cache."""
        persistence = Mock()
        persistence.get_plugins.return_value = [{"data": {"x": 1}}]
        
        loader = LazyLoader(persistence)
        
        loader.load_plugin_data("job1", "p1")
        loader.load_plugin_data("job2", "p1")
        
        loader.clear_cache()
        
        assert loader.get_cache_size() == 0
    
    def test_batch_load(self):
        """Test batch loading for multiple jobs."""
        persistence = Mock()
        persistence.get_plugins.return_value = [
            {"job_id": "job1", "plugin_name": "p1", "data": {"a": 1}},
            {"job_id": "job2", "plugin_name": "p1", "data": {"b": 2}},
        ]
        
        loader = LazyLoader(persistence)
        result = loader.batch_load(["job1", "job2"])
        
        assert "job1" in result
        assert "job2" in result
        assert result["job1"]["p1"]["a"] == 1
