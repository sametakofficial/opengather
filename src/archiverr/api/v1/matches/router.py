"""
Matches Router - Match Data Access

Industry Best Practice: Async endpoints with Motor via app.state.

Endpoints:
- GET / - List all matches
- GET /{id} - Get match details
- GET /{id}/plugins - Get plugin results for match
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request


router = APIRouter()


def _get_db(request: Request):
    """Get database from app state."""
    db = request.app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


@router.get("/")
async def list_matches(
    request: Request,
    execution_id: Optional[str] = Query(default=None, description="Filter by execution"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """
    List matches, optionally filtered by execution.
    """
    db = _get_db(request)
    
    try:
        query = {}
        if execution_id:
            exec_id = f"exec_{execution_id}" if not execution_id.startswith("exec_") else execution_id
            query["execution_id"] = exec_id
        
        cursor = db["matches"].find(query).sort("created_at", -1).skip(offset).limit(limit)
        matches = await cursor.to_list(length=limit)
        
        total = await db["matches"].count_documents(query)
        
        return {
            "total": total,
            "matches": matches
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{match_id}")
async def get_match(request: Request, match_id: str):
    """
    Get match details by ID.
    """
    db = _get_db(request)
    
    try:
        doc = await db["matches"].find_one({"_id": match_id})
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
        
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{match_id}/plugins")
async def get_match_plugins(request: Request, match_id: str):
    """
    Get plugin results for a match.
    """
    db = _get_db(request)
    
    try:
        # Get match first
        match = await db["matches"].find_one({"_id": match_id})
        if match is None:
            raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
        
        # Get plugin results
        cursor = db["plugin_results"].find({"match_id": match_id})
        results = await cursor.to_list(length=100)
        
        return {
            "match_id": match_id,
            "plugins": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
