"""
Tests for Jobs API - Session 11 Phase 8

Tests the /v1/jobs endpoints.
"""

import pytest
from datetime import datetime, timezone
from archiverr.api.v1.jobs.schemas import (
    JobResponse,
    JobListResponse,
    JobStatus,
    JobPluginResponse,
    StateEnum,
    InputData,
    OutputData
)


class TestJobSchemas:
    """Test Job Pydantic schemas."""
    
    def test_job_state_enum_values(self):
        """Test StateEnum has all expected values."""
        assert StateEnum.PENDING.value == "pending"
        assert StateEnum.RUNNING.value == "running"
        assert StateEnum.SUCCESS.value == "success"
        assert StateEnum.FAILED.value == "failed"
        assert StateEnum.SKIPPED.value == "skipped"
    
    def test_job_status_defaults(self):
        """Test JobStatus default values."""
        status = JobStatus()
        assert status.state == StateEnum.PENDING
        assert status.success is True
        assert status.executed == []
        assert status.failed == []
        assert status.skipped == []
        assert status.duration_ms == 0
        assert status.error is None
    
    def test_job_status_with_plugins(self):
        """Test JobStatus with plugin lists."""
        status = JobStatus(
            state=StateEnum.SUCCESS,
            executed=["scanner", "renamer", "tmdb"],
            failed=["tvdb"],
            skipped=["tasker"]
        )
        assert len(status.executed) == 3
        assert "tmdb" in status.executed
        assert "tvdb" in status.failed
    
    def test_job_response_minimal(self):
        """Test JobResponse with minimal data."""
        response = JobResponse(
            id="job_run1_0",
            created_at=datetime.now(timezone.utc)
        )
        assert response.id == "job_run1_0"
        assert response.run_id == ""
        assert response.index == 0
        assert response.plugins == {}
    
    def test_job_response_full(self):
        """Test JobResponse with full data."""
        response = JobResponse(
            id="job_run_test_5",
            run_id="run_test",
            index=5,
            status=JobStatus(
                state=StateEnum.SUCCESS,
                executed=["scanner", "renamer"]
            ),
            input=InputData(value="/path/to/file.mkv"),
            output=OutputData(values={"title": "Test Movie"}),
            plugins={
                "scanner": {"size": 1024},
                "renamer": {"parsed": {"movie": {"title": "Test"}}}
            },
            created_at=datetime.now(timezone.utc)
        )
        assert response.id == "job_run_test_5"
        assert response.run_id == "run_test"
        assert response.index == 5
        assert "scanner" in response.plugins
        assert "renamer" in response.plugins
    
    def test_job_list_response(self):
        """Test JobListResponse."""
        response = JobListResponse(
            items=[
                JobResponse(id="job_1", created_at=datetime.now()),
                JobResponse(id="job_2", created_at=datetime.now())
            ],
            total=50,
            page=2,
            page_size=20
        )
        assert len(response.items) == 2
        assert response.total == 50
        assert response.page == 2
    
    def test_job_plugin_response(self):
        """Test JobPluginResponse."""
        response = JobPluginResponse(
            job_id="job_run1_0",
            plugin_name="tmdb",
            stage="data",
            data={"movie": {"id": 12345, "title": "Test Movie"}},
            status={"success": True}
        )
        assert response.job_id == "job_run1_0"
        assert response.plugin_name == "tmdb"
        assert response.stage == "data"
        assert response.data["movie"]["id"] == 12345


class TestJobResponseConversion:
    """Test MongoDB document to JobResponse conversion."""
    
    def test_doc_to_job_response_new_format(self):
        """Test conversion of new format document."""
        from archiverr.api.v1.jobs.router import _doc_to_job_response
        
        doc = {
            "id": "job_run1_5",
            "run_id": "run_test",
            "index": 5,
            "status": {
                "state": "success",
                "success": True,
                "executed": ["scanner", "renamer"],
                "failed": [],
                "skipped": []
            },
            "input": {"value": "/test/file.mkv"},
            "output": {"values": {}},
            "plugins": {"scanner": {"size": 1024}},
            "created_at": datetime.now(timezone.utc)
        }
        
        response = _doc_to_job_response(doc)
        
        assert response.id == "job_run1_5"
        assert response.run_id == "run_test"
        assert response.index == 5
        assert response.status.state == StateEnum.SUCCESS
        assert "scanner" in response.status.executed
    
    def test_doc_to_job_response_legacy_format(self):
        """Test conversion of legacy format document."""
        from archiverr.api.v1.jobs.router import _doc_to_job_response
        
        doc = {
            "_id": "match_123",
            "execution_id": "exec_test",
            "index": 3,
            "input": {"path": "/test"},
            "plugins": {"renamer": {"parsed": {}}}
        }
        
        response = _doc_to_job_response(doc)
        
        # run_id should be converted from execution_id
        assert response.run_id == "run_test"
        assert response.index == 3
