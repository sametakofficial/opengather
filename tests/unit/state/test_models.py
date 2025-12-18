"""
State Models Unit Tests

Tests for Session 11 state models (FINAL_DATASETS.yml compliant).
These models replace the legacy ExecutionState/MatchState with
cleaner, more structured alternatives.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any


class TestStateEnum:
    """StateEnum tests"""
    
    def test_values(self):
        """Test enum values match expected strings"""
        from archiverr.state.models import StateEnum
        
        assert StateEnum.PENDING.value == "pending"
        assert StateEnum.RUNNING.value == "running"
        assert StateEnum.SUCCESS.value == "success"
        assert StateEnum.FAILED.value == "failed"
    
    def test_enum_comparison(self):
        """Test enum comparison works correctly"""
        from archiverr.state.models import StateEnum
        
        assert StateEnum.PENDING == StateEnum.PENDING
        assert StateEnum.PENDING != StateEnum.RUNNING
    
    def test_enum_from_value(self):
        """Test enum can be created from string value"""
        from archiverr.state.models import StateEnum
        
        assert StateEnum("pending") == StateEnum.PENDING
        assert StateEnum("success") == StateEnum.SUCCESS


class TestInputData:
    """InputData dataclass tests"""
    
    def test_basic_creation(self):
        """Test basic InputData creation with just value"""
        from archiverr.state.models import InputData
        
        inp = InputData(value="/path/to/file.mkv")
        
        assert inp.value == "/path/to/file.mkv"
        assert inp.data == {}
    
    def test_creation_with_metadata(self):
        """Test InputData with full metadata"""
        from archiverr.state.models import InputData
        
        inp = InputData(
            value="/data/movies/Movie.Name.2024.1080p.mkv",
            data={
                "filename": "Movie.Name.2024.1080p.mkv",
                "extension": "mkv",
                "size_bytes": 5368709120,
                "source": "filesystem"
            }
        )
        
        assert inp.value == "/data/movies/Movie.Name.2024.1080p.mkv"
        assert inp.data["filename"] == "Movie.Name.2024.1080p.mkv"
        assert inp.data["size_bytes"] == 5368709120
        assert inp.data["source"] == "filesystem"
    
    def test_to_dict(self):
        """Test InputData serialization"""
        from archiverr.state.models import InputData
        
        inp = InputData(
            value="/test.mkv",
            data={"size_bytes": 1024}
        )
        d = inp.to_dict()
        
        assert d["value"] == "/test.mkv"
        assert d["data"]["size_bytes"] == 1024
    
    def test_virtual_input_support(self):
        """Test virtual input (non-filesystem) support"""
        from archiverr.state.models import InputData
        
        inp = InputData(
            value="tmdb://movie/603",
            data={"source": "api"}
        )
        
        assert inp.value == "tmdb://movie/603"
        assert inp.data["source"] == "api"


class TestOutputData:
    """OutputData dataclass tests"""
    
    def test_defaults(self):
        """Test OutputData default values"""
        from archiverr.state.models import OutputData
        
        out = OutputData()
        
        assert out.values == []
        assert out.data == {}
    
    def test_with_values(self):
        """Test OutputData with output paths"""
        from archiverr.state.models import OutputData
        
        out = OutputData(
            values=[
                "/srv/archive/Movie (2024)/Movie.mkv",
                "/srv/archive/Movie (2024)/Movie.nfo"
            ],
            data={
                "tasks": {
                    "save_movie": {"type": "save", "success": True}
                }
            }
        )
        
        assert len(out.values) == 2
        assert out.values[0] == "/srv/archive/Movie (2024)/Movie.mkv"
        assert out.data["tasks"]["save_movie"]["success"] is True
    
    def test_to_dict(self):
        """Test OutputData serialization"""
        from archiverr.state.models import OutputData
        
        out = OutputData(values=["/output/file.mkv"])
        d = out.to_dict()
        
        assert d["values"] == ["/output/file.mkv"]
        assert d["data"] == {}


class TestJobStatus:
    """JobStatus dataclass tests"""
    
    def test_defaults(self):
        """Test JobStatus default values"""
        from archiverr.state.models import JobStatus, StateEnum
        
        status = JobStatus()
        
        assert status.state == StateEnum.PENDING
        assert status.success is True
        assert status.executed == []
        assert status.failed == []
        assert status.skipped == []
        assert status.started_at is None
        assert status.finished_at is None
        assert status.duration_ms == 0
    
    def test_with_plugin_lists(self):
        """Test JobStatus with plugin execution results"""
        from archiverr.state.models import JobStatus, StateEnum
        
        status = JobStatus(
            state=StateEnum.SUCCESS,
            success=True,
            executed=["scanner", "renamer", "tmdb"],
            failed=[],
            skipped=["tvdb"]
        )
        
        assert "scanner" in status.executed
        assert "tvdb" in status.skipped
        assert len(status.failed) == 0
    
    def test_to_dict(self):
        """Test JobStatus serialization"""
        from archiverr.state.models import JobStatus, StateEnum
        
        now = datetime.now()
        status = JobStatus(
            state=StateEnum.RUNNING,
            started_at=now
        )
        d = status.to_dict()
        
        assert d["state"] == "running"
        assert d["success"] is True
        assert d["started_at"] == now.isoformat()


class TestRunStatus:
    """RunStatus dataclass tests"""
    
    def test_defaults(self):
        """Test RunStatus default values"""
        from archiverr.state.models import RunStatus, StateEnum
        
        status = RunStatus()
        
        assert status.state == StateEnum.PENDING
        assert status.success is True
        assert status.total_jobs == 0
        assert status.completed == 0
        assert status.failed == 0
    
    def test_with_job_counts(self):
        """Test RunStatus with job statistics"""
        from archiverr.state.models import RunStatus, StateEnum
        
        status = RunStatus(
            state=StateEnum.SUCCESS,
            total_jobs=10,
            completed=9,
            failed=1,
            success=False
        )
        
        assert status.total_jobs == 10
        assert status.completed == 9
        assert status.failed == 1
        assert status.success is False
    
    def test_to_dict(self):
        """Test RunStatus serialization"""
        from archiverr.state.models import RunStatus
        
        status = RunStatus(total_jobs=5, completed=3, failed=1)
        d = status.to_dict()
        
        assert d["total_jobs"] == 5
        assert d["completed"] == 3
        assert d["failed"] == 1


class TestJobState:
    """JobState dataclass tests"""
    
    def test_id_generation(self):
        """Test automatic job ID generation"""
        from archiverr.state.models import JobState
        
        job = JobState(index=0, run_id="run_abc123")
        
        assert job.id == "job_run_abc123_0"
    
    def test_id_generation_multiple_indices(self):
        """Test job ID generation with different indices"""
        from archiverr.state.models import JobState
        
        job0 = JobState(index=0, run_id="run_test")
        job5 = JobState(index=5, run_id="run_test")
        job99 = JobState(index=99, run_id="run_test")
        
        assert job0.id == "job_run_test_0"
        assert job5.id == "job_run_test_5"
        assert job99.id == "job_run_test_99"
    
    def test_custom_id_preserved(self):
        """Test that custom ID is not overwritten"""
        from archiverr.state.models import JobState
        
        job = JobState(index=0, run_id="run_abc", id="custom_id")
        
        assert job.id == "custom_id"
    
    def test_with_input_data(self):
        """Test JobState with InputData"""
        from archiverr.state.models import JobState, InputData
        
        job = JobState(
            index=0,
            run_id="run_abc123",
            input=InputData(
                value="/path/to/movie.mkv",
                data={"extension": "mkv"}
            )
        )
        
        assert job.input.value == "/path/to/movie.mkv"
        assert job.input.data["extension"] == "mkv"
    
    def test_to_dict(self):
        """Test JobState serialization matches FINAL_DATASETS.yml format"""
        from archiverr.state.models import JobState, InputData
        
        job = JobState(
            index=0,
            run_id="run_abc123",
            input=InputData("/test.mkv")
        )
        d = job.to_dict()
        
        assert d["id"] == "job_run_abc123_0"
        assert d["index"] == 0
        assert d["run_id"] == "run_abc123"
        assert "input" in d
        assert "output" in d
        assert "status" in d
        assert d["input"]["value"] == "/test.mkv"
    
    def test_start_method(self):
        """Test JobState start() sets running state"""
        from archiverr.state.models import JobState, StateEnum
        
        job = JobState(index=0, run_id="run_test")
        job.start()
        
        assert job.status.state == StateEnum.RUNNING
        assert job.status.started_at is not None
    
    def test_complete_method_success(self):
        """Test JobState complete() with success"""
        from archiverr.state.models import JobState, StateEnum
        
        job = JobState(index=0, run_id="run_test")
        job.start()
        job.complete(success=True)
        
        assert job.status.state == StateEnum.SUCCESS
        assert job.status.success is True
        assert job.status.finished_at is not None
        assert job.status.duration_ms >= 0
    
    def test_complete_method_failure(self):
        """Test JobState complete() with failure"""
        from archiverr.state.models import JobState, StateEnum
        
        job = JobState(index=0, run_id="run_test")
        job.start()
        job.complete(success=False)
        
        assert job.status.state == StateEnum.FAILED
        assert job.status.success is False
    
    def test_add_executed(self):
        """Test adding executed plugin"""
        from archiverr.state.models import JobState
        
        job = JobState(index=0, run_id="run_test")
        job.add_executed("tmdb")
        job.add_executed("renamer")
        job.add_executed("tmdb")  # Duplicate - should be ignored
        
        assert "tmdb" in job.status.executed
        assert "renamer" in job.status.executed
        assert len(job.status.executed) == 2
    
    def test_add_failed_sets_success_false(self):
        """Test adding failed plugin sets success to false"""
        from archiverr.state.models import JobState
        
        job = JobState(index=0, run_id="run_test")
        assert job.status.success is True
        
        job.add_failed("broken_plugin")
        
        assert "broken_plugin" in job.status.failed
        assert job.status.success is False
    
    def test_add_skipped(self):
        """Test adding skipped plugin"""
        from archiverr.state.models import JobState
        
        job = JobState(index=0, run_id="run_test")
        job.add_skipped("tvdb")
        
        assert "tvdb" in job.status.skipped
        assert job.status.success is True  # Skipped doesn't affect success


class TestRunState:
    """RunState dataclass tests"""
    
    def test_basic_creation(self):
        """Test basic RunState creation"""
        from archiverr.state.models import RunState
        
        run = RunState(id="run_abc123")
        
        assert run.id == "run_abc123"
        assert run.config == {}
    
    def test_with_config(self):
        """Test RunState with config"""
        from archiverr.state.models import RunState
        
        run = RunState(
            id="run_abc123",
            config={"options": {"debug": True}}
        )
        
        assert run.config["options"]["debug"] is True
    
    def test_to_dict(self):
        """Test RunState serialization matches FINAL_DATASETS.yml format"""
        from archiverr.state.models import RunState
        
        run = RunState(id="run_abc123")
        d = run.to_dict()
        
        assert d["id"] == "run_abc123"
        assert "status" in d
        assert "config" in d
        assert d["status"]["state"] == "pending"
    
    def test_start_method(self):
        """Test RunState start() sets running state"""
        from archiverr.state.models import RunState, StateEnum
        
        run = RunState(id="run_test")
        run.start()
        
        assert run.status.state == StateEnum.RUNNING
        assert run.status.started_at is not None
    
    def test_complete_method_success(self):
        """Test RunState complete() with no failures"""
        from archiverr.state.models import RunState, StateEnum
        
        run = RunState(id="run_test")
        run.start()
        run.status.total_jobs = 5
        run.status.completed = 5
        run.status.failed = 0
        run.complete()
        
        assert run.status.state == StateEnum.SUCCESS
        assert run.status.success is True
    
    def test_complete_method_with_failures(self):
        """Test RunState complete() with failures"""
        from archiverr.state.models import RunState, StateEnum
        
        run = RunState(id="run_test")
        run.start()
        run.status.total_jobs = 5
        run.status.completed = 4
        run.status.failed = 1
        run.complete()
        
        assert run.status.state == StateEnum.FAILED
        assert run.status.success is False
    
    def test_increment_methods(self):
        """Test RunState counter increment methods"""
        from archiverr.state.models import RunState
        
        run = RunState(id="run_test")
        
        run.increment_jobs()
        run.increment_jobs()
        run.increment_completed()
        run.increment_failed()
        
        assert run.status.total_jobs == 2
        assert run.status.completed == 1
        assert run.status.failed == 1


class TestBackwardCompatibility:
    """Backward compatibility tests for legacy imports"""
    
    def test_legacy_imports_work(self):
        """Test legacy model imports still work"""
        from archiverr.state import (
            ExecutionState,
            ExecutionStatus,
            MatchState,
            PluginResult
        )
        
        # Just verify imports work
        assert ExecutionState is not None
        assert ExecutionStatus is not None
        assert MatchState is not None
        assert PluginResult is not None
    
    def test_new_imports_work(self):
        """Test new model imports work"""
        from archiverr.state import (
            StateEnum,
            InputData,
            OutputData,
            JobStatus,
            RunStatus,
            JobState,
            RunState
        )
        
        # Verify new models can be imported
        assert StateEnum is not None
        assert InputData is not None
        assert OutputData is not None
        assert JobStatus is not None
        assert RunStatus is not None
        assert JobState is not None
        assert RunState is not None
    
    def test_state_manager_import(self):
        """Test StateManager and GlobalStateManager imports"""
        from archiverr.state import StateManager, GlobalStateManager
        
        # GlobalStateManager should be an alias for StateManager
        assert StateManager is not None
        assert GlobalStateManager is not None


class TestFinalDatasetsCompliance:
    """Tests verifying FINAL_DATASETS.yml structure compliance"""
    
    def test_job_structure_matches_yaml(self):
        """Test JobState.to_dict() matches FINAL_DATASETS.yml job structure"""
        from archiverr.state.models import JobState, InputData, OutputData, JobStatus, StateEnum
        
        job = JobState(
            index=0,
            run_id="run_abc123",
            input=InputData(
                value="/data/movies/Movie.Name.2024.1080p.mkv",
                data={
                    "filename": "Movie.Name.2024.1080p.mkv",
                    "extension": "mkv",
                    "size_bytes": 5368709120,
                    "source": "filesystem"
                }
            ),
            output=OutputData(
                values=["/srv/archive/Movie (2024)/Movie.mkv"],
                data={"tasks": {}}
            ),
            status=JobStatus(
                state=StateEnum.SUCCESS,
                success=True,
                executed=["scanner", "renamer", "tmdb"],
                skipped=["tvdb"]
            )
        )
        
        d = job.to_dict()
        
        # Structure checks matching FINAL_DATASETS.yml
        assert d["id"] == "job_run_abc123_0"
        assert d["index"] == 0
        assert d["run_id"] == "run_abc123"
        assert d["input"]["value"] == "/data/movies/Movie.Name.2024.1080p.mkv"
        assert d["input"]["data"]["extension"] == "mkv"
        assert d["output"]["values"][0] == "/srv/archive/Movie (2024)/Movie.mkv"
        assert d["status"]["state"] == "success"
        assert "scanner" in d["status"]["executed"]
        assert "tvdb" in d["status"]["skipped"]
    
    def test_run_structure_matches_yaml(self):
        """Test RunState.to_dict() matches FINAL_DATASETS.yml run structure"""
        from archiverr.state.models import RunState, RunStatus, StateEnum
        
        run = RunState(
            id="run_abc123",
            status=RunStatus(
                state=StateEnum.SUCCESS,
                success=True,
                total_jobs=10,
                completed=10,
                failed=0
            ),
            config={"options": {"debug": True}}
        )
        
        d = run.to_dict()
        
        # Structure checks matching FINAL_DATASETS.yml
        assert d["id"] == "run_abc123"
        assert d["status"]["state"] == "success"
        assert d["status"]["total_jobs"] == 10
        assert d["status"]["completed"] == 10
        assert d["config"]["options"]["debug"] is True
