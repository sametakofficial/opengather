"""
Tests for Runs API - Session 11 Phase 8

Tests the /v1/runs endpoints.
"""

import pytest
from datetime import datetime, timezone
from archiverr.api.v1.runs.schemas import (
    RunResponse,
    RunCreate,
    RunListResponse,
    RunStatus,
    StateEnum,
    InputData,
    OutputData
)


class TestRunSchemas:
    """Test Run Pydantic schemas."""
    
    def test_state_enum_values(self):
        """Test StateEnum has all expected values."""
        assert StateEnum.PENDING.value == "pending"
        assert StateEnum.RUNNING.value == "running"
        assert StateEnum.SUCCESS.value == "success"
        assert StateEnum.FAILED.value == "failed"
        assert StateEnum.PARTIAL.value == "partial"
        assert StateEnum.CANCELLED.value == "cancelled"
    
    def test_run_status_defaults(self):
        """Test RunStatus default values."""
        status = RunStatus()
        assert status.state == StateEnum.PENDING
        assert status.success is True
        assert status.total_jobs == 0
        assert status.completed == 0
        assert status.failed == 0
        assert status.duration_ms == 0
        assert status.error is None
    
    def test_run_status_custom(self):
        """Test RunStatus with custom values."""
        status = RunStatus(
            state=StateEnum.SUCCESS,
            success=True,
            total_jobs=10,
            completed=8,
            failed=2,
            duration_ms=5000
        )
        assert status.state == StateEnum.SUCCESS
        assert status.total_jobs == 10
        assert status.completed == 8
        assert status.failed == 2
    
    def test_input_data_defaults(self):
        """Test InputData defaults."""
        data = InputData()
        assert data.value == ""
        assert data.data == {}
    
    def test_output_data_defaults(self):
        """Test OutputData defaults."""
        data = OutputData()
        assert data.values == {}
        assert data.data == {}
    
    def test_run_create_defaults(self):
        """Test RunCreate defaults."""
        create = RunCreate()
        assert create.config is None
        assert create.dry_run is True
    
    def test_run_create_with_config(self):
        """Test RunCreate with config."""
        create = RunCreate(
            config={"plugins": {"scanner": {"enabled": True}}},
            dry_run=False
        )
        assert create.config is not None
        assert create.dry_run is False
    
    def test_run_response_minimal(self):
        """Test RunResponse with minimal data."""
        response = RunResponse(
            id="run_123",
            created_at=datetime.now(timezone.utc)
        )
        assert response.id == "run_123"
        assert response.status.state == StateEnum.PENDING
        assert response.jobs == []
    
    def test_run_response_full(self):
        """Test RunResponse with full data."""
        now = datetime.now(timezone.utc)
        response = RunResponse(
            id="run_test_001",
            status=RunStatus(
                state=StateEnum.SUCCESS,
                total_jobs=5,
                completed=5
            ),
            input=InputData(value="/path/to/input"),
            output=OutputData(values={"result": "ok"}),
            jobs=["job_1", "job_2", "job_3"],
            config={"debug": True},
            options={"dry_run": False},
            created_at=now,
            completed_at=now
        )
        assert response.id == "run_test_001"
        assert response.status.state == StateEnum.SUCCESS
        assert len(response.jobs) == 3
        assert response.config["debug"] is True
    
    def test_run_list_response(self):
        """Test RunListResponse."""
        response = RunListResponse(
            items=[
                RunResponse(id="run_1", created_at=datetime.now()),
                RunResponse(id="run_2", created_at=datetime.now())
            ],
            total=10,
            page=1,
            page_size=20
        )
        assert len(response.items) == 2
        assert response.total == 10
        assert response.page == 1


class TestRunResponseConversion:
    """Test MongoDB document to RunResponse conversion."""
    
    def test_doc_to_run_response_new_format(self):
        """Test conversion of new format document."""
        from archiverr.api.v1.runs.router import _doc_to_run_response
        
        doc = {
            "id": "run_20231204_abc",
            "status": {
                "state": "success",
                "success": True,
                "total_jobs": 5,
                "completed": 5,
                "failed": 0,
                "duration_ms": 1234
            },
            "input": {"value": "/test"},
            "output": {"values": {"key": "value"}},
            "jobs": ["job_1", "job_2"],
            "config": {"debug": True},
            "created_at": datetime.now(timezone.utc)
        }
        
        response = _doc_to_run_response(doc)
        
        assert response.id == "run_20231204_abc"
        assert response.status.state == StateEnum.SUCCESS
        assert response.status.total_jobs == 5
        assert len(response.jobs) == 2
    
    def test_doc_to_run_response_legacy_format(self):
        """Test conversion of legacy format document."""
        from archiverr.api.v1.runs.router import _doc_to_run_response
        
        doc = {
            "_id": "exec_20231204_abc",
            "status": "running",
            "summary": {
                "total_matches": 10,
                "completed_matches": 5,
                "failed_matches": 1
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config_snapshot": {"key": "value"},
            "match_ids": ["match_1", "match_2"]
        }
        
        response = _doc_to_run_response(doc)
        
        # ID should be converted from exec_ to run_
        assert response.id == "run_20231204_abc"
        # Jobs should come from match_ids
        assert len(response.jobs) == 2
