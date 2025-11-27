"""
Versioning Schemas

Pydantic models for git-like versioning API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ==================== BRANCH SCHEMAS ====================

class BranchCreate(BaseModel):
    """Request model for creating a branch"""
    name: str = Field(..., min_length=1, max_length=100, description="Branch name (unique)")
    description: str = Field(default="", max_length=500, description="Branch description")
    is_default: bool = Field(default=False, description="Set as default branch")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "production",
                "description": "Production executions",
                "is_default": True
            }
        }


class BranchResponse(BaseModel):
    """Response model for a branch"""
    branch_id: str = Field(..., alias="_id")
    name: str
    description: str
    is_default: bool
    head_commit_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


class BranchListResponse(BaseModel):
    """Response model for listing branches"""
    total: int
    branches: List[BranchResponse]


# ==================== COMMIT SCHEMAS ====================

class CommitCreate(BaseModel):
    """Request model for creating a commit"""
    execution_id: str = Field(..., description="Execution ID to commit")
    branch_id: Optional[str] = Field(None, description="Target branch (default if not specified)")
    message: str = Field(default="", max_length=500, description="Commit message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": "abc12345",
                "message": "Added new media files",
                "metadata": {"tags": ["movies", "2025"]}
            }
        }


class ExecutionSummary(BaseModel):
    """Embedded execution summary in commit"""
    status: Optional[str] = None
    success: Optional[bool] = None
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0


class CommitResponse(BaseModel):
    """Response model for a commit"""
    commit_id: str = Field(..., alias="_id")
    branch_id: str
    execution_id: str
    parent_commit_id: Optional[str] = None
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    execution_summary: ExecutionSummary
    
    class Config:
        populate_by_name = True


class CommitListResponse(BaseModel):
    """Response model for listing commits"""
    total: int
    branch_id: Optional[str] = None
    commits: List[CommitResponse]


class CommitHistoryResponse(BaseModel):
    """Response model for commit history"""
    commit_id: str
    history: List[CommitResponse]


# ==================== CHECKOUT SCHEMAS ====================

class CheckoutResponse(BaseModel):
    """Response model for checkout operation"""
    commit: CommitResponse
    execution: Dict[str, Any]
    matches: List[Dict[str, Any]]
    plugin_results: List[Dict[str, Any]]
    total_matches: int
    total_plugin_results: int
