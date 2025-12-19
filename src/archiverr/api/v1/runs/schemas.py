"""Run Schemas - Pydantic models for runs."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StateEnum(str, Enum):
    """Run state values"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class RunStatus(BaseModel):
    """Run status fields"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    duration_ms: int = 0
    error: str | None = None

    model_config = {"from_attributes": True}


class InputData(BaseModel):
    """Input data structure"""
    value: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class OutputData(BaseModel):
    """Output data structure (aligned with state models)"""
    values: list[str] = Field(default_factory=list)  # Fixed: was Dict, now List to match state
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    """Request body for creating a run"""
    config: dict[str, Any] | None = None
    dry_run: bool = True


class RunResponse(BaseModel):
    """Run response (aligned with FINAL_DATASETS.yml)"""
    id: str = Field(..., description="Run ID (run_{timestamp}_{hash})")
    status: RunStatus = Field(default_factory=RunStatus)
    input: InputData = Field(default_factory=InputData)
    output: OutputData = Field(default_factory=OutputData)
    jobs: list[str] = Field(default_factory=list, description="Job IDs")
    config: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    """Paginated run list"""
    items: list[RunResponse]
    total: int
    page: int = 1
    page_size: int = 20
