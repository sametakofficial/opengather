"""
System Schemas - Pydantic Models for System API

Provides request/response models for system endpoints.
Note: These are already defined in router.py but extracted here for consistency.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status: healthy | unhealthy")
    timestamp: str = Field(..., description="ISO timestamp")


class DatabaseStatus(BaseModel):
    """Database connection status"""
    connected: bool = Field(..., description="Whether DB is connected")
    backend: str = Field(..., description="Database backend type")
    database: Optional[str] = Field(default=None, description="Database name")
    collections: Optional[Dict[str, int]] = Field(
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
    uptime_seconds: Optional[float] = None
    database: DatabaseStatus
    system: SystemInfo


class VersionResponse(BaseModel):
    """Version information"""
    name: str = Field(default="Archiverr")
    version: str
    python_version: str
    platform: str


class DiagnosticsEntry(BaseModel):
    """Single diagnostics log entry"""
    timestamp: str
    level: str = Field(..., description="Log level: DEBUG | INFO | WARNING | ERROR")
    component: str = Field(..., description="Source component")
    message: str
    fields: Dict[str, Any] = Field(default_factory=dict)


class DiagnosticsResponse(BaseModel):
    """Diagnostics logs response"""
    total_entries: int
    entries: List[DiagnosticsEntry] = Field(default_factory=list)


class ConfigResponse(BaseModel):
    """Configuration response (sanitized)"""
    options: Dict[str, Any] = Field(default_factory=dict)
    plugins: Dict[str, Any] = Field(default_factory=dict)
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
