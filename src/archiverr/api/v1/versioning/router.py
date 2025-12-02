"""
Versioning Router - Git-like Branch Management

Industry Best Practice: Async endpoints with Motor via app.state.

Endpoints:
- GET /branches - List all branches
- POST /branches - Create new branch
- GET /branches/{name} - Get branch details
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from archiverr.api.deps import DatabaseDep


router = APIRouter()


class BranchCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class BranchResponse(BaseModel):
    name: str
    description: str
    is_default: bool
    head_commit_id: Optional[str]
    created_at: str


def _to_iso_string(val) -> str:
    """Convert datetime or any value to ISO string."""
    if val is None:
        return ""
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)


@router.get("/branches")
async def list_branches(db: DatabaseDep):
    """
    List all branches.
    """
    
    try:
        cursor = db["branches"].find()
        branches = await cursor.to_list(length=100)
        
        return {
            "total": len(branches),
            "branches": [
                BranchResponse(
                    name=b.get("name", ""),
                    description=b.get("description", ""),
                    is_default=b.get("is_default", False),
                    head_commit_id=b.get("head_commit_id"),
                    created_at=_to_iso_string(b.get("created_at", ""))
                )
                for b in branches
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/branches")
async def create_branch(branch: BranchCreate, db: DatabaseDep):
    """
    Create a new branch.
    """
    
    # Validate name
    if not branch.name or not branch.name.strip():
        raise HTTPException(status_code=400, detail="Branch name cannot be empty")
    
    if not branch.name.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Branch name must be alphanumeric (with - and _ allowed)")
    
    try:
        # Check if exists
        existing = await db["branches"].find_one({"name": branch.name})
        if existing:
            raise HTTPException(status_code=409, detail=f"Branch '{branch.name}' already exists")
        
        # Create branch
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "_id": f"branch_{branch.name}",
            "name": branch.name,
            "description": branch.description or "",
            "is_default": False,
            "head_commit_id": None,
            "created_at": now,
            "updated_at": now
        }
        
        await db["branches"].insert_one(doc)
        
        return BranchResponse(
            name=branch.name,
            description=branch.description or "",
            is_default=False,
            head_commit_id=None,
            created_at=now
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/branches/{branch_name}")
async def get_branch(branch_name: str, db: DatabaseDep):
    """
    Get branch details.
    """
    
    try:
        doc = await db["branches"].find_one({"name": branch_name})
        if doc is None:
            doc = await db["branches"].find_one({"_id": f"branch_{branch_name}"})
        
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Branch '{branch_name}' not found")
        
        return BranchResponse(
            name=doc.get("name", ""),
            description=doc.get("description", ""),
            is_default=doc.get("is_default", False),
            head_commit_id=doc.get("head_commit_id"),
            created_at=_to_iso_string(doc.get("created_at", ""))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
