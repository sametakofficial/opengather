"""
Jobs API Router - Session 11 Phase 8

Replaces /matches with /jobs terminology.
Async endpoints using Motor MongoDB driver.
"""

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from archiverr.api.deps import DatabaseDep
from .schemas import (
    JobResponse,
    JobListResponse,
    JobStatus,
    JobPluginResponse,
    StateEnum,
    InputData,
    OutputData
)

router = APIRouter()


def _doc_to_job_response(doc: dict) -> JobResponse:
    """Convert MongoDB document to JobResponse."""
    # Handle ID
    job_id = doc.get("id") or doc.get("_id", "")
    
    # Handle run_id (support legacy execution_id)
    run_id = doc.get("run_id") or doc.get("execution_id", "")
    if run_id.startswith("exec_"):
        run_id = run_id.replace("exec_", "run_")
    
    # Handle datetime
    created_at = doc.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    elif created_at is None:
        created_at = datetime.now(timezone.utc)
    
    completed_at = doc.get("completed_at")
    if isinstance(completed_at, str):
        completed_at = datetime.fromisoformat(completed_at)
    
    # Build status
    status_data = doc.get("status", {})
    if isinstance(status_data, dict):
        status = JobStatus(
            state=StateEnum(status_data.get("state", "pending")),
            success=status_data.get("success", True),
            executed=status_data.get("executed", []),
            failed=status_data.get("failed", []),
            skipped=status_data.get("skipped", []),
            duration_ms=status_data.get("duration_ms", 0),
            error=status_data.get("error")
        )
    else:
        status = JobStatus()
    
    # Input/Output
    input_data = doc.get("input", {})
    output_data = doc.get("output", {})
    
    return JobResponse(
        id=job_id,
        run_id=run_id,
        index=doc.get("index", 0),
        status=status,
        input=InputData(**input_data) if isinstance(input_data, dict) else InputData(),
        output=OutputData(**output_data) if isinstance(output_data, dict) else OutputData(),
        plugins=doc.get("plugins", {}),
        created_at=created_at,
        completed_at=completed_at
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: DatabaseDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    run_id: Optional[str] = Query(default=None, description="Filter by run ID"),
    state: Optional[StateEnum] = Query(default=None, description="Filter by state")
):
    """
    List all jobs with pagination and filtering.
    """
    try:
        query = {}
        
        # Handle run_id filter
        if run_id:
            # Support both new and legacy formats
            query["$or"] = [
                {"run_id": run_id},
                {"execution_id": run_id},
                {"run_id": run_id.replace("run_", "exec_")},
                {"execution_id": run_id.replace("run_", "exec_")}
            ]
        
        if state:
            query["status.state"] = state.value
        
        skip = (page - 1) * page_size
        
        # Try jobs collection first, fallback to matches
        collection_name = "jobs"
        count = await db[collection_name].count_documents({})
        if count == 0:
            collection_name = "matches"
        
        cursor = db[collection_name].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        
        total = await db[collection_name].count_documents(query)
        
        return JobListResponse(
            items=[_doc_to_job_response(doc) for doc in docs],
            total=total,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/run/{run_id}", response_model=List[JobResponse])
async def get_jobs_by_run(run_id: str, db: DatabaseDep):
    """
    Get all jobs for a specific run.
    """
    try:
        # Build query for multiple ID formats
        run_id_variants = [run_id]
        if run_id.startswith("run_"):
            run_id_variants.append(run_id.replace("run_", "exec_"))
        elif not run_id.startswith("exec_"):
            run_id_variants.extend([f"run_{run_id}", f"exec_{run_id}"])
        
        jobs = []
        
        # Try jobs collection
        for variant in run_id_variants:
            cursor = db["jobs"].find({"run_id": variant})
            jobs = await cursor.to_list(length=1000)
            if jobs:
                break
        
        # Fallback to matches
        if not jobs:
            for variant in run_id_variants:
                cursor = db["matches"].find({"execution_id": variant})
                jobs = await cursor.to_list(length=1000)
                if jobs:
                    break
        
        return [_doc_to_job_response(doc) for doc in jobs]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: DatabaseDep):
    """
    Get a specific job by ID.
    """
    try:
        doc = None
        
        # Try jobs collection
        doc = await db["jobs"].find_one({"_id": job_id})
        if not doc:
            doc = await db["jobs"].find_one({"id": job_id})
        
        # Fallback to matches
        if not doc:
            doc = await db["matches"].find_one({"_id": job_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        
        return _doc_to_job_response(doc)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/plugins", response_model=List[JobPluginResponse])
async def get_job_plugins(job_id: str, db: DatabaseDep):
    """
    Get all plugin data for a job.
    """
    try:
        # Try plugins collection
        cursor = db["plugins"].find({"job_id": job_id})
        plugins = await cursor.to_list(length=100)
        
        # Fallback to plugin_results
        if not plugins:
            cursor = db["plugin_results"].find({"match_id": job_id})
            plugins = await cursor.to_list(length=100)
        
        # Also check job document itself
        if not plugins:
            job_doc = await db["jobs"].find_one({"_id": job_id})
            if not job_doc:
                job_doc = await db["matches"].find_one({"_id": job_id})
            
            if job_doc and "plugins" in job_doc:
                # Convert embedded plugins to list
                plugins = [
                    {
                        "job_id": job_id,
                        "plugin_name": name,
                        "data": data,
                        "status": {}
                    }
                    for name, data in job_doc.get("plugins", {}).items()
                ]
        
        return [
            JobPluginResponse(
                job_id=p.get("job_id", job_id),
                plugin_name=p.get("plugin_name", p.get("name", "")),
                stage=p.get("stage", ""),
                data=p.get("data", {}),
                status=p.get("status", {})
            )
            for p in plugins
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/plugins/{plugin_name}", response_model=JobPluginResponse)
async def get_job_plugin(job_id: str, plugin_name: str, db: DatabaseDep):
    """
    Get specific plugin data for a job.
    """
    try:
        # Try plugins collection
        doc = await db["plugins"].find_one({
            "job_id": job_id,
            "plugin_name": plugin_name
        })
        
        # Fallback to plugin_results
        if not doc:
            doc = await db["plugin_results"].find_one({
                "match_id": job_id,
                "plugin_name": plugin_name
            })
        
        # Check embedded in job
        if not doc:
            job_doc = await db["jobs"].find_one({"_id": job_id})
            if not job_doc:
                job_doc = await db["matches"].find_one({"_id": job_id})
            
            if job_doc:
                plugin_data = job_doc.get("plugins", {}).get(plugin_name)
                if plugin_data:
                    doc = {
                        "job_id": job_id,
                        "plugin_name": plugin_name,
                        "data": plugin_data,
                        "status": {}
                    }
        
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Plugin {plugin_name} not found for job {job_id}"
            )
        
        return JobPluginResponse(
            job_id=doc.get("job_id", job_id),
            plugin_name=doc.get("plugin_name", plugin_name),
            stage=doc.get("stage", ""),
            data=doc.get("data", {}),
            status=doc.get("status", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
