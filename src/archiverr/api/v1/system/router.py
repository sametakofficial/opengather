"""
System Router - Health, Status, Diagnostics

Endpoints:
- GET /health - Health check (for load balancers)
- GET /status - Detailed system status
- GET /version - Version information
- GET /diagnostics - Recent diagnostics logs
"""

from datetime import datetime, timezone
from typing import Optional
import platform
import os

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from archiverr.api.dependencies import get_persistence, get_db


router = APIRouter()


# ==================== SCHEMAS ====================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str  # "healthy" | "unhealthy"
    timestamp: str
    
    
class DatabaseStatus(BaseModel):
    """Database connection status"""
    connected: bool
    backend: str
    database: Optional[str] = None
    collections: Optional[dict] = None


class SystemStatus(BaseModel):
    """Detailed system status"""
    status: str
    timestamp: str
    uptime_seconds: Optional[float] = None
    database: DatabaseStatus
    system: dict
    

class VersionResponse(BaseModel):
    """Version information"""
    name: str
    version: str
    python_version: str
    platform: str


class DiagnosticsEntry(BaseModel):
    """Single diagnostics log entry"""
    timestamp: str
    level: str
    component: str
    message: str
    fields: dict = {}


class DiagnosticsResponse(BaseModel):
    """Diagnostics logs response"""
    total_entries: int
    entries: list[DiagnosticsEntry]


# ==================== ENDPOINTS ====================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Used by load balancers and monitoring systems.
    Returns 200 if service is healthy.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/status", response_model=SystemStatus)
async def system_status(persistence = Depends(get_persistence)):
    """
    Detailed system status.
    
    Returns:
    - Database connection status
    - System information
    - Collection statistics
    """
    # Database status
    try:
        # Use async method if available
        if persistence and hasattr(persistence, 'get_statistics_async'):
            stats = await persistence.get_statistics_async()
        elif persistence:
            stats = persistence.get_statistics()
        else:
            stats = {}
            
        db_status = DatabaseStatus(
            connected=True,
            backend=stats.get("backend", "unknown"),
            database=stats.get("database", None),
            collections={
                "executions": stats.get("executions", 0),
                "matches": stats.get("matches", 0),
                "plugin_results": stats.get("plugin_results", 0)
            }
        )
    except Exception as e:
        db_status = DatabaseStatus(
            connected=False,
            backend="error",
            database=str(e)
        )
    
    return SystemStatus(
        status="healthy" if db_status.connected else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_status,
        system={
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "platform_version": platform.release(),
            "hostname": platform.node()
        }
    )


@router.get("/version", response_model=VersionResponse)
async def version_info():
    """
    Version information.
    
    Returns application and runtime versions.
    """
    return VersionResponse(
        name="Archiverr",
        version="1.0.0",
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.release()}"
    )


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics(
    limit: int = Query(default=100, le=1000, description="Max entries to return"),
    level: Optional[str] = Query(default=None, description="Filter by log level"),
    component: Optional[str] = Query(default=None, description="Filter by component"),
    db = Depends(get_db)
):
    """
    Get recent diagnostics logs.
    
    Retrieves structured logs from MongoDB diagnostics collection.
    Supports filtering by level and component.
    """
    # Check if diagnostics collection exists
    if db is None:
        return DiagnosticsResponse(total_entries=0, entries=[])
    
    try:
        # Build query filter
        query = {}
        if level:
            query["level"] = level.upper()
        if component:
            query["component"] = component
        
        # Query MongoDB
        if hasattr(db, '__getitem__'):  # MongoDB database
            cursor = db["diagnostics"].find(query).sort("timestamp", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            
            entries = [
                DiagnosticsEntry(
                    timestamp=doc.get("timestamp", ""),
                    level=doc.get("level", ""),
                    component=doc.get("component", ""),
                    message=doc.get("message", ""),
                    fields=doc.get("fields", {})
                )
                for doc in docs
            ]
            
            # Get total count
            total = await db["diagnostics"].count_documents(query)
            
            return DiagnosticsResponse(total_entries=total, entries=entries)
        else:
            # Mock database - return empty for now
            return DiagnosticsResponse(total_entries=0, entries=[])
            
    except Exception as e:
        # Collection doesn't exist yet
        return DiagnosticsResponse(total_entries=0, entries=[])
