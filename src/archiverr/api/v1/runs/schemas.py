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


class PersistenceInfo(BaseModel):
    """Persistence visibility (S37 PASS 2).

    Surfaces the persistence_mode contract (11-recovery.yml) so callers can
    distinguish a persisted run from a degraded NullPersistence fallback.
    Without this, a degraded-mode run with Mongo down returns a 201 that
    looks identical to a persisted run -- AGENT.md "no silent failures".
    """
    mode: str = Field(default="degraded", description="Requested mode: full | degraded | off")
    backend: str = Field(default="NullPersistence", description="Active backend class")
    persisted: bool = Field(default=False, description="True iff run was actually persisted to Mongo")

    model_config = {"from_attributes": True}


class RunResponse(BaseModel):
    """Run response (aligned with FINAL_DATASETS.yml)"""
    id: str = Field(..., description="Run ID (run_{timestamp}_{hash})")
    status: RunStatus = Field(default_factory=RunStatus)
    input: InputData = Field(default_factory=InputData)
    output: OutputData = Field(default_factory=OutputData)
    jobs: list[str] = Field(default_factory=list, description="Job IDs")
    config: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Priority-resolved envelope (runs.data). Keys are job-index strings.",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    persistence: PersistenceInfo | None = Field(default=None, description="Persistence visibility (S37)")

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    """Paginated run list"""
    items: list[RunResponse]
    total: int
    page: int = 1
    page_size: int = 20
