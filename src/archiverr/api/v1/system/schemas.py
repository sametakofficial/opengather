"""
System Schemas - Pydantic Models for System API

Provides request/response models for system endpoints.
Note: These are already defined in router.py but extracted here for consistency.
"""

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status: healthy | unhealthy")
    timestamp: str = Field(..., description="ISO timestamp")


class DatabaseStatus(BaseModel):
    """Database connection status"""
    connected: bool = Field(..., description="Whether DB is connected")
    backend: str = Field(..., description="Database backend type")
    database: str | None = Field(default=None, description="Database name")
    collections: dict[str, int] | None = Field(
        default=None,
        description="Collection document counts"
    )


class SystemInfo(BaseModel):
    """System information"""
    python_version: str
    platform: str
    platform_version: str
    hostname: str


class SystemStatus(BaseModel):
    """Detailed system status"""
    status: str = Field(..., description="Overall status: healthy | degraded")
    timestamp: str
    uptime_seconds: float | None = None
    database: DatabaseStatus
    system: SystemInfo


class VersionResponse(BaseModel):
    """Version information"""
    name: str = Field(default="Archiverr")
    version: str
    python_version: str
    platform: str


# DiagnosticsEntry / DiagnosticsResponse models archived in S37 PASS 4
# (.deleted/s37-diagnostics/) — endpoint never wired, collection never written.

class ConfigResponse(BaseModel):
    """Configuration response (sanitized)"""
    options: dict[str, Any] = Field(default_factory=dict)
    plugins: dict[str, Any] = Field(default_factory=dict)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
