"""Schemas for config read + playground render."""

from typing import Any

from pydantic import BaseModel, Field


class ConfigResponse(BaseModel):
    path: str = "config.yml"
    writable: bool = False
    config: dict[str, Any] = Field(default_factory=dict)
    text: str = ""


class RenderRequest(BaseModel):
    template: str = Field(..., min_length=1, max_length=8000)
    run_id: str
    job_id: str | None = None
    job_index: int | None = None


class RenderResponse(BaseModel):
    rendered: str
    run_id: str
    job_id: str
    job_index: int
    error: bool = False
