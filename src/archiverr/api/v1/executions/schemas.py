"""
Execution Schemas - Request/Response Models

Pydantic models for execution endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Execution status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfigOverride(BaseModel):
    """Partial config override for execution"""
    options: Optional[Dict[str, Any]] = None
    plugins: Optional[Dict[str, Dict[str, Any]]] = None


class ExecutionCreate(BaseModel):
    """Request to create new execution"""
    targets: Optional[List[str]] = Field(
        default=None, 
        description="List of file/directory paths. If empty, uses config.yml targets."
    )
    config_override: Optional[ConfigOverride] = None
    tasks: Optional[List[str]] = Field(default=None, description="Task names to execute")
    
    class Config:
        json_schema_extra = {
            "example": {
                "targets": ["/media/downloads/Movie.mkv"],
                "config_override": {
                    "options": {"dry_run": True}
                }
            }
        }


class ExecutionSummary(BaseModel):
    """Execution summary statistics"""
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0


class ExecutionResponse(BaseModel):
    """Execution response"""
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    success: bool = False
    
    # Summary
    summary: ExecutionSummary = ExecutionSummary()
    
    # Config snapshot
    config_snapshot: Optional[Dict[str, Any]] = None
    
    # URLs for client
    websocket_url: Optional[str] = None
    poll_url: Optional[str] = None


class ExecutionProgress(BaseModel):
    """Real-time execution progress"""
    execution_id: str
    status: ExecutionStatus
    progress: Dict[str, Any]
    elapsed_ms: int
    estimated_remaining_ms: Optional[int] = None


class ExecutionListResponse(BaseModel):
    """List of executions response"""
    total: int
    executions: List[ExecutionResponse]


class ExecutionStartResponse(BaseModel):
    """Response when starting new execution"""
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    websocket_url: str
    poll_url: str
    message: str = "Execution started"
