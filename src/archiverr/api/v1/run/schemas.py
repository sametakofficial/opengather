"""
Run Schemas - Pydantic Models for Run API

Provides request/response models for execution run endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Request to start a new execution run"""
    config_override: dict[str, Any] | None = Field(
        default=None,
        description="Optional config overrides"
    )
    dry_run: bool | None = Field(
        default=None,
        description="If true, don't persist results"
    )


class RunProgress(BaseModel):
    """Execution progress information"""
    current_match: int = 0
    total_matches: int = 0
    current_plugin: str | None = None
    percent_complete: float = 0.0


class RunSummary(BaseModel):
    """Execution summary statistics"""
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    skipped_matches: int = 0


class RunResponse(BaseModel):
    """Response from starting an execution run"""
    execution_id: str = Field(..., description="Unique execution identifier")
    success: bool = Field(..., description="Whether execution completed successfully")
    status: str = Field(..., description="Execution status")
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    total_matches: int = 0
    summary: RunSummary | None = None
    progress: RunProgress | None = None
    api_response: dict[str, Any] | None = Field(
        default=None,
        description="Full API response with all match data"
    )
    error: str | None = Field(
        default=None,
        description="Error message if execution failed"
    )


class RunStatusResponse(BaseModel):
    """Status response for polling"""
    execution_id: str
    status: str
    success: bool | None = None
    progress: RunProgress | None = None
    updated_at: datetime | None = None
