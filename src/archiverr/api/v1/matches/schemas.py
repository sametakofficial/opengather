"""
Match Schemas - Pydantic Models for Matches API

Provides request/response models for match endpoints.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class MatchStatus(BaseModel):
    """Match processing status"""
    success: bool = False
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


class MatchBase(BaseModel):
    """Base match information"""
    index: int = Field(..., description="Match index in execution")
    input_path: str = Field(..., description="Input file path")
    status: str = Field(default="pending", description="Match status")


class MatchResponse(MatchBase):
    """Full match response"""
    id: str = Field(..., alias="_id", description="Match ID")
    execution_id: str = Field(..., description="Parent execution ID")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    plugins: Dict[str, Any] = Field(default_factory=dict, description="Plugin results")
    
    class Config:
        populate_by_name = True


class MatchListResponse(BaseModel):
    """Paginated match list"""
    total: int = Field(..., description="Total number of matches")
    matches: List[MatchResponse] = Field(default_factory=list)


class PluginResultResponse(BaseModel):
    """Plugin result for a match"""
    plugin_name: str
    success: bool
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class MatchPluginsResponse(BaseModel):
    """All plugin results for a match"""
    match_id: str
    plugins: List[PluginResultResponse] = Field(default_factory=list)
