"""Plugin Schemas - Pydantic models for plugin information and data."""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime


class PluginInfo(BaseModel):
    """Plugin information from manifest"""
    name: str
    version: str = "1.0.0"
    stage: str = "output"
    requires: List[str] = Field(default_factory=list)
    provides: List[str] = Field(default_factory=list)
    trigger_rule: str = "all_success"
    enabled: bool = True
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PluginData(BaseModel):
    """Plugin data entry (stored per job)"""
    id: str = ""
    job_id: str
    run_id: str = ""
    plugin_name: str
    stage: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    status: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {"from_attributes": True}


class PluginListResponse(BaseModel):
    """Plugin list response"""
    items: List[PluginInfo]
    total: int


class PluginDataListResponse(BaseModel):
    """Plugin data list response"""
    items: List[PluginData]
    total: int
    page: int = 1
    page_size: int = 20
