"""Job Schemas - Pydantic models for jobs."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StateEnum(str, Enum):
    """Job state values"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobStatus(BaseModel):
    """Job status fields"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None

    model_config = {"from_attributes": True}


class InputData(BaseModel):
    """Job input data"""
    value: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class OutputData(BaseModel):
    """Job output data"""
    values: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    """Job response (aligned with FINAL_DATASETS.yml)"""
    id: str = Field(..., description="Job ID (job_{run_id}_{index})")
    run_id: str = ""
    index: int = 0
    status: JobStatus = Field(default_factory=JobStatus)
    input: InputData = Field(default_factory=InputData)
    output: OutputData = Field(default_factory=OutputData)
    plugins: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """Paginated job list"""
    items: list[JobResponse]
    total: int
    page: int = 1
    page_size: int = 20


class JobPluginResponse(BaseModel):
    """Plugin data for a job"""
    job_id: str
    plugin_name: str
    stage: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    status: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
