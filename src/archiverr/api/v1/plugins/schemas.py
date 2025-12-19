"""Plugin Schemas - Pydantic models for plugin information and data."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PluginInfo(BaseModel):
    """Plugin information from manifest"""
    name: str
    version: str = "1.0.0"
    stage: str = "output"
    requires: list[str] = Field(default_factory=list)
    provides: list[str] = Field(default_factory=list)
    trigger_rule: str = "all_success"
    enabled: bool = True
    description: str | None = None

    model_config = {"from_attributes": True}


class PluginData(BaseModel):
    """Plugin data entry (stored per job)"""
    id: str = ""
    job_id: str
    run_id: str = ""
    plugin_name: str
    stage: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    status: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {"from_attributes": True}


class PluginListResponse(BaseModel):
    """Plugin list response"""
    items: list[PluginInfo]
    total: int


class PluginDataListResponse(BaseModel):
    """Plugin data list response"""
    items: list[PluginData]
    total: int
    page: int = 1
    page_size: int = 20
