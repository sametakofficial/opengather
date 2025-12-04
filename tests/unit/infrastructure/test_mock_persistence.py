"""
Mock Persistence Unit Tests

Tests for Session 11 new collection methods (runs, jobs, plugins).
"""

import pytest
import tempfile
import shutil
from pathlib import Path


class TestMockPersistenceNewCollections:
    """Tests for new runs/jobs/plugins collections"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for mock database"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def mock_persistence(self, temp_dir):
        """Create mock persistence with temp directory"""
        from archiverr.infrastructure.database.mock import MockPersistence
        
        persistence = MockPersistence(base_path=temp_dir)
        persistence.connect()
        yield persistence
        persistence.disconnect()
    
    # =========================================================================
    # RUN TESTS
    # =========================================================================
    
    def test_save_and_get_run(self, mock_persistence):
        """Test basic run save and retrieval"""
        run = {
            "id": "run_abc123",
            "status": {"state": "pending", "total_jobs": 0}
        }
        mock_persistence.save_run(run)
        
        result = mock_persistence.get_run("run_abc123")
        assert result is not None
        assert result["id"] == "run_abc123"
        assert result["status"]["state"] == "pending"
    
    def test_run_update(self, mock_persistence):
        """Test run update (upsert behavior)"""
        run = {"id": "run_update", "status": {"state": "pending"}}
        mock_persistence.save_run(run)
        
        # Update state
        run["status"]["state"] = "running"
        mock_persistence.save_run(run)
        
        result = mock_persistence.get_run("run_update")
        assert result["status"]["state"] == "running"
    
    def test_get_run_not_found(self, mock_persistence):
        """Test get_run returns None for non-existent run"""
        result = mock_persistence.get_run("non_existent_run")
        assert result is None
    
    def test_save_run_with_runstate_object(self, mock_persistence):
        """Test save_run with RunState object (has to_dict method)"""
        from archiverr.state.models import RunState
        
        run = RunState(id="run_object_test")
        run.start()
        
        mock_persistence.save_run(run)
        
        result = mock_persistence.get_run("run_object_test")
        assert result is not None
        assert result["id"] == "run_object_test"
        assert result["status"]["state"] == "running"
    
    def test_save_run_requires_id(self, mock_persistence):
        """Test save_run raises error without id field"""
        with pytest.raises(ValueError, match="id"):
            mock_persistence.save_run({"status": {"state": "pending"}})
    
    # =========================================================================
    # JOB TESTS
    # =========================================================================
    
    def test_save_and_get_job(self, mock_persistence):
        """Test basic job save and retrieval"""
        job = {
            "id": "job_run_abc123_0",
            "run_id": "run_abc123",
            "index": 0,
            "input": {"value": "/test.mkv"}
        }
        mock_persistence.save_job(job)
        
        result = mock_persistence.get_job("job_run_abc123_0")
        assert result is not None
        assert result["id"] == "job_run_abc123_0"
        assert result["input"]["value"] == "/test.mkv"
    
    def test_get_jobs_by_run_id(self, mock_persistence):
        """Test get_jobs returns all jobs for a run sorted by index"""
        # Add jobs in non-sequential order
        mock_persistence.save_job({"id": "job_run_test_2", "run_id": "run_test", "index": 2})
        mock_persistence.save_job({"id": "job_run_test_0", "run_id": "run_test", "index": 0})
        mock_persistence.save_job({"id": "job_run_test_1", "run_id": "run_test", "index": 1})
        
        jobs = mock_persistence.get_jobs("run_test")
        
        assert len(jobs) == 3
        assert jobs[0]["index"] == 0
        assert jobs[1]["index"] == 1
        assert jobs[2]["index"] == 2
    
    def test_get_jobs_empty_for_unknown_run(self, mock_persistence):
        """Test get_jobs returns empty list for unknown run"""
        jobs = mock_persistence.get_jobs("non_existent_run")
        assert jobs == []
    
    def test_save_job_with_jobstate_object(self, mock_persistence):
        """Test save_job with JobState object (has to_dict method)"""
        from archiverr.state.models import JobState, InputData
        
        job = JobState(
            index=0,
            run_id="run_object_test",
            input=InputData("/path/to/file.mkv")
        )
        
        mock_persistence.save_job(job)
        
        result = mock_persistence.get_job("job_run_object_test_0")
        assert result is not None
        assert result["input"]["value"] == "/path/to/file.mkv"
    
    def test_job_update(self, mock_persistence):
        """Test job update (upsert behavior)"""
        job = {"id": "job_update_0", "run_id": "run_update", "index": 0, "status": {"state": "pending"}}
        mock_persistence.save_job(job)
        
        job["status"]["state"] = "completed"
        mock_persistence.save_job(job)
        
        result = mock_persistence.get_job("job_update_0")
        assert result["status"]["state"] == "completed"
    
    # =========================================================================
    # PLUGIN TESTS
    # =========================================================================
    
    def test_save_and_get_plugin(self, mock_persistence):
        """Test basic plugin save and retrieval"""
        plugin = {
            "job_id": "job_run_abc123_0",
            "run_id": "run_abc123",
            "job_index": 0,
            "plugin_name": "tmdb",
            "stage": "data",
            "data": {"movie": {"title": "Test Movie"}}
        }
        mock_persistence.save_plugin(plugin)
        
        result = mock_persistence.get_plugin("job_run_abc123_0", "tmdb")
        assert result is not None
        assert result["plugin_name"] == "tmdb"
        assert result["data"]["movie"]["title"] == "Test Movie"
    
    def test_get_plugins_for_job(self, mock_persistence):
        """Test get_plugins returns all plugins for a job"""
        job_id = "job_run_test_0"
        
        mock_persistence.save_plugin({"job_id": job_id, "run_id": "run_test", "job_index": 0, "plugin_name": "scanner", "stage": "input", "data": {}})
        mock_persistence.save_plugin({"job_id": job_id, "run_id": "run_test", "job_index": 0, "plugin_name": "renamer", "stage": "parse", "data": {}})
        mock_persistence.save_plugin({"job_id": job_id, "run_id": "run_test", "job_index": 0, "plugin_name": "tmdb", "stage": "data", "data": {}})
        
        plugins = mock_persistence.get_plugins(job_id)
        
        assert len(plugins) == 3
        plugin_names = {p["plugin_name"] for p in plugins}
        assert plugin_names == {"scanner", "renamer", "tmdb"}
    
    def test_get_plugins_empty_for_unknown_job(self, mock_persistence):
        """Test get_plugins returns empty list for unknown job"""
        plugins = mock_persistence.get_plugins("non_existent_job")
        assert plugins == []
    
    def test_plugin_update(self, mock_persistence):
        """Test plugin update (upsert by job_id + plugin_name)"""
        plugin = {
            "job_id": "job_update_0",
            "run_id": "run_update",
            "job_index": 0,
            "plugin_name": "tmdb",
            "stage": "data",
            "data": {"movie": {"title": "Original"}}
        }
        mock_persistence.save_plugin(plugin)
        
        # Update with new data
        plugin["data"]["movie"]["title"] = "Updated"
        mock_persistence.save_plugin(plugin)
        
        result = mock_persistence.get_plugin("job_update_0", "tmdb")
        assert result["data"]["movie"]["title"] == "Updated"
        
        # Should still be only one plugin entry
        plugins = mock_persistence.get_plugins("job_update_0")
        assert len(plugins) == 1
    
    def test_save_plugin_with_plugindata_object(self, mock_persistence):
        """Test save_plugin with PluginData object (has to_dict method)"""
        from archiverr.state.models import PluginData
        
        plugin = PluginData(
            job_id="job_run_object_test_0",
            run_id="run_object_test",
            job_index=0,
            plugin_name="ffprobe",
            stage="data",
            data={"video": {"codec": "hevc"}}
        )
        
        mock_persistence.save_plugin(plugin)
        
        result = mock_persistence.get_plugin("job_run_object_test_0", "ffprobe")
        assert result is not None
        assert result["data"]["video"]["codec"] == "hevc"
    
    def test_save_plugin_requires_job_id_and_plugin_name(self, mock_persistence):
        """Test save_plugin raises error without required fields"""
        with pytest.raises(ValueError, match="job_id"):
            mock_persistence.save_plugin({"plugin_name": "test"})
        
        with pytest.raises(ValueError, match="plugin_name"):
            mock_persistence.save_plugin({"job_id": "test"})
    
    def test_get_plugins_for_run(self, mock_persistence):
        """Test get_plugins_for_run returns all plugins for a run"""
        run_id = "run_multi_job"
        
        # Job 0 plugins
        mock_persistence.save_plugin({"job_id": "job_run_multi_job_0", "run_id": run_id, "job_index": 0, "plugin_name": "scanner", "stage": "input", "data": {}})
        mock_persistence.save_plugin({"job_id": "job_run_multi_job_0", "run_id": run_id, "job_index": 0, "plugin_name": "tmdb", "stage": "data", "data": {}})
        
        # Job 1 plugins
        mock_persistence.save_plugin({"job_id": "job_run_multi_job_1", "run_id": run_id, "job_index": 1, "plugin_name": "scanner", "stage": "input", "data": {}})
        mock_persistence.save_plugin({"job_id": "job_run_multi_job_1", "run_id": run_id, "job_index": 1, "plugin_name": "tmdb", "stage": "data", "data": {}})
        
        all_plugins = mock_persistence.get_plugins_for_run(run_id)
        
        assert len(all_plugins) == 4
    
    # =========================================================================
    # DELETE TESTS
    # =========================================================================
    
    def test_delete_run_cascades(self, mock_persistence):
        """Test delete_run removes run, jobs, and plugins"""
        run_id = "run_delete_test"
        
        # Create run
        mock_persistence.save_run({"id": run_id, "status": {"state": "completed"}})
        
        # Create jobs
        mock_persistence.save_job({"id": f"job_{run_id}_0", "run_id": run_id, "index": 0})
        mock_persistence.save_job({"id": f"job_{run_id}_1", "run_id": run_id, "index": 1})
        
        # Create plugins
        mock_persistence.save_plugin({"job_id": f"job_{run_id}_0", "run_id": run_id, "job_index": 0, "plugin_name": "tmdb", "stage": "data", "data": {}})
        mock_persistence.save_plugin({"job_id": f"job_{run_id}_1", "run_id": run_id, "job_index": 1, "plugin_name": "tmdb", "stage": "data", "data": {}})
        
        # Verify data exists
        assert mock_persistence.get_run(run_id) is not None
        assert len(mock_persistence.get_jobs(run_id)) == 2
        assert len(mock_persistence.get_plugins_for_run(run_id)) == 2
        
        # Delete run
        result = mock_persistence.delete_run(run_id)
        
        assert result is True
        assert mock_persistence.get_run(run_id) is None
        assert mock_persistence.get_jobs(run_id) == []
        assert mock_persistence.get_plugins_for_run(run_id) == []
    
    def test_delete_run_not_found(self, mock_persistence):
        """Test delete_run returns False for non-existent run"""
        result = mock_persistence.delete_run("non_existent_run")
        assert result is False
    
    # =========================================================================
    # STATISTICS TESTS
    # =========================================================================
    
    def test_statistics_include_new_collections(self, mock_persistence):
        """Test get_statistics includes new collection counts"""
        mock_persistence.save_run({"id": "run_1", "status": {"state": "pending"}})
        mock_persistence.save_run({"id": "run_2", "status": {"state": "pending"}})
        mock_persistence.save_job({"id": "job_1", "run_id": "run_1", "index": 0})
        mock_persistence.save_plugin({"job_id": "job_1", "run_id": "run_1", "job_index": 0, "plugin_name": "test", "stage": "data", "data": {}})
        
        stats = mock_persistence.get_statistics()
        
        assert stats["runs"] == 2
        assert stats["jobs"] == 1
        assert stats["plugins"] == 1
        assert stats["backend"] == "MockPersistence"
    
    # =========================================================================
    # ISOLATION TESTS
    # =========================================================================
    
    def test_data_isolation(self, mock_persistence):
        """Test that returned data is a copy (modifications don't affect storage)"""
        mock_persistence.save_run({"id": "run_isolation", "status": {"state": "pending"}})
        
        result = mock_persistence.get_run("run_isolation")
        result["status"]["state"] = "modified"
        
        # Original should be unchanged
        result2 = mock_persistence.get_run("run_isolation")
        assert result2["status"]["state"] == "pending"
    
    def test_clear_removes_new_collections(self, mock_persistence):
        """Test clear() removes data from new collections"""
        mock_persistence.save_run({"id": "run_clear", "status": {"state": "pending"}})
        mock_persistence.save_job({"id": "job_clear", "run_id": "run_clear", "index": 0})
        mock_persistence.save_plugin({"job_id": "job_clear", "run_id": "run_clear", "job_index": 0, "plugin_name": "test", "stage": "data", "data": {}})
        
        mock_persistence.clear()
        
        stats = mock_persistence.get_statistics()
        assert stats["runs"] == 0
        assert stats["jobs"] == 0
        assert stats["plugins"] == 0


class TestMockPersistenceBackwardCompat:
    """Tests for backward compatibility with legacy methods"""
    
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)
    
    @pytest.fixture
    def mock_persistence(self, temp_dir):
        from archiverr.infrastructure.database.mock import MockPersistence
        
        persistence = MockPersistence(base_path=temp_dir)
        persistence.connect()
        yield persistence
        persistence.disconnect()
    
    def test_legacy_save_execution_still_works(self, mock_persistence):
        """Test legacy save_execution method still works"""
        from archiverr.state.models import ExecutionState, ExecutionStatus
        from datetime import datetime
        
        execution = ExecutionState(
            id="legacy_test",
            started_at=datetime.now(),
            status=ExecutionStatus.RUNNING
        )
        
        # This should not raise
        mock_persistence.save_execution(execution)
        
        # Legacy method should store in executions collection
        result = mock_persistence.get_execution("legacy_test")
        assert result is not None
    
    def test_legacy_save_match_still_works(self, mock_persistence):
        """Test legacy save_match method still works"""
        from archiverr.state.models import MatchState
        
        match = MatchState(
            index=0,
            input_path="/legacy/path.mkv",
            execution_id="legacy_exec"
        )
        
        # This should not raise
        mock_persistence.save_match(match)
        
        # Legacy method should store in matches collection
        matches = mock_persistence.get_matches("legacy_exec")
        assert len(matches) == 1
