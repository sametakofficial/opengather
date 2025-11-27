"""
Executions Router - Execution Management

Industry Best Practice: Async endpoints with Motor via Depends() injection.

Endpoints:
- GET / - List all executions
- GET /{id} - Get execution details
- GET /{id}/status - Get execution status
- GET /{id}/matches - Get matches for execution
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from archiverr.api.deps import get_database
from .schemas import (
    ExecutionResponse,
    ExecutionListResponse,
    ExecutionStatus,
    ExecutionSummary
)


router = APIRouter()


def _doc_to_response(doc: dict) -> ExecutionResponse:
    """Convert MongoDB document to ExecutionResponse."""
    exec_id = doc.get("_id", "").replace("exec_", "")
    
    # Handle datetime conversion
    started_at = doc.get("started_at")
    if isinstance(started_at, str):
        started_at = datetime.fromisoformat(started_at)
    elif started_at is None:
        started_at = datetime.now(timezone.utc)
    
    finished_at = doc.get("finished_at")
    if isinstance(finished_at, str):
        finished_at = datetime.fromisoformat(finished_at)
    
    return ExecutionResponse(
        execution_id=exec_id,
        status=ExecutionStatus(doc.get("status", "pending")),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=doc.get("duration_ms"),
        success=doc.get("success", False),
        summary=ExecutionSummary(
            total_matches=doc.get("summary", {}).get("total_matches", 0),
            completed_matches=doc.get("summary", {}).get("completed_matches", 0),
            failed_matches=doc.get("summary", {}).get("failed_matches", 0)
        ),
        config_snapshot=doc.get("config_snapshot"),
        poll_url=f"/api/v1/executions/{exec_id}/status",
        websocket_url=f"/api/v1/executions/{exec_id}/stream"
    )


@router.get("/", response_model=ExecutionListResponse)
async def list_executions(
    db = Depends(get_database),
    limit: int = Query(default=20, le=100, description="Max executions to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    status: Optional[str] = Query(default=None, description="Filter by status")
):
    """
    List all executions.
    
    Returns paginated list of executions, newest first.
    """
    
    try:
        # Async Motor query
        cursor = db["executions"].find().sort("started_at", -1).skip(offset).limit(limit)
        executions = await cursor.to_list(length=limit)
        
        # Filter by status if provided
        if status:
            executions = [e for e in executions if e.get("status") == status]
        
        # Get total count
        total = await db["executions"].count_documents({})
        
        # Convert to response models
        responses = [_doc_to_response(doc) for doc in executions]
        
        return ExecutionListResponse(
            total=total,
            executions=responses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: str, db = Depends(get_database)):
    """
    Get execution details by ID.
    """
    
    try:
        # Try with and without prefix
        doc = await db["executions"].find_one({"_id": f"exec_{execution_id}"})
        if doc is None:
            doc = await db["executions"].find_one({"_id": execution_id})
        
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
        
        return _doc_to_response(doc)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}/status")
async def get_execution_status(execution_id: str, db = Depends(get_database)):
    """
    Get execution status (for polling).
    """
    
    try:
        doc = await db["executions"].find_one({"_id": f"exec_{execution_id}"})
        if doc is None:
            doc = await db["executions"].find_one({"_id": execution_id})
        
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
        
        return {
            "execution_id": execution_id,
            "status": doc.get("status", "unknown"),
            "success": doc.get("success"),
            "progress": doc.get("progress", {}),
            "updated_at": doc.get("updated_at") or doc.get("started_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}/matches")
async def get_execution_matches(
    execution_id: str,
    db = Depends(get_database),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """
    Get matches for an execution.
    """
    
    try:
        # Check execution exists
        exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
        execution = await db["executions"].find_one({"_id": exec_id})
        if execution is None:
            execution = await db["executions"].find_one({"_id": execution_id})
        
        if execution is None:
            raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
        
        # Get matches
        cursor = db["matches"].find({"execution_id": exec_id}).skip(offset).limit(limit)
        matches = await cursor.to_list(length=limit)
        
        # Get total
        total = await db["matches"].count_documents({"execution_id": exec_id})
        
        return {
            "execution_id": execution_id,
            "total": total,
            "matches": matches
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
