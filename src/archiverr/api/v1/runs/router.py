"""Runs API Router."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from archiverr.api.deps import DatabaseDep

# Import PyMongo exceptions for specific error handling
# AGENT.md §5: no silent failures. Mongo connectivity errors (network,
# AutoReconnect, NetworkTimeout, ConnectionFailure, ServerSelectionTimeoutError)
# all inherit from PyMongoError. OperationFailure means DB up but query bad.
try:
    from pymongo.errors import (
        ConnectionFailure,
        OperationFailure,
        PyMongoError,
        ServerSelectionTimeoutError,
    )
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    OperationFailure = Exception
    PyMongoError = Exception

from .schemas import (
    InputData,
    OutputData,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunStatus,
    StateEnum,
)

router = APIRouter()


def _doc_to_run_response(doc: dict) -> RunResponse:
    """Convert MongoDB document to RunResponse."""
    # Handle ID - support both new 'id' and legacy '_id'
    run_id = doc.get("id") or doc.get("_id", "")
    if run_id.startswith("exec_"):
        run_id = run_id.replace("exec_", "run_")

    # Handle datetime conversion
    created_at = doc.get("created_at") or doc.get("started_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    elif created_at is None:
        created_at = datetime.now(timezone.utc)

    completed_at = doc.get("completed_at") or doc.get("finished_at")
    if isinstance(completed_at, str):
        completed_at = datetime.fromisoformat(completed_at)

    # Build status from various legacy formats
    status_data = doc.get("status", {})
    if isinstance(status_data, str):
        # Legacy: status was a string
        status = RunStatus(state=StateEnum(status_data) if status_data in StateEnum.__members__.values() else StateEnum.PENDING)
    elif isinstance(status_data, dict):
        status = RunStatus(
            state=StateEnum(status_data.get("state", "pending")),
            success=status_data.get("success", True),
            total_jobs=status_data.get("total_jobs", doc.get("summary", {}).get("total_matches", 0)),
            completed=status_data.get("completed", doc.get("summary", {}).get("completed_matches", 0)),
            failed=status_data.get("failed", doc.get("summary", {}).get("failed_matches", 0)),
            duration_ms=status_data.get("duration_ms", doc.get("duration_ms", 0)),
            error=status_data.get("error")
        )
    else:
        status = RunStatus()

    # Input/Output
    input_data = doc.get("input", {})
    output_data = doc.get("output", {})

    if isinstance(output_data, dict):
        values = output_data.get("values")
        if isinstance(values, dict):
            output_data = {**output_data, "values": list(values.values())}

    return RunResponse(
        id=run_id,
        status=status,
        input=InputData(**input_data) if isinstance(input_data, dict) else InputData(),
        output=OutputData(**output_data) if isinstance(output_data, dict) else OutputData(),
        jobs=doc.get("jobs", doc.get("match_ids", [])),
        config=doc.get("config", doc.get("config_snapshot", {})),
        options=doc.get("options", {}),
        created_at=created_at,
        completed_at=completed_at
    )


@router.get("", response_model=RunListResponse)
async def list_runs(
    db: DatabaseDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    state: StateEnum | None = Query(default=None, description="Filter by state")
):
    """
    List all runs with pagination and optional filtering.
    
    Returns newest runs first.
    """
    try:
        # Build query
        query = {}
        if state:
            query["status.state"] = state.value

        # Calculate skip
        skip = (page - 1) * page_size

        # Canonical collection: 'runs' (legacy 'executions' fallback dropped in S36 PASS 6.C)
        cursor = db["runs"].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        total = await db["runs"].count_documents(query)

        return RunListResponse(
            items=[_doc_to_run_response(doc) for doc in docs],
            total=total,
            page=page,
            page_size=page_size
        )

    except OperationFailure as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, db: DatabaseDep):
    """
    Get a specific run by ID.
    
    Supports both new 'run_' and legacy 'exec_' ID formats.
    """
    try:
        # Canonical: 'runs' collection, 'id' field. Allow bare-id input
        # (without 'run_' prefix) for convenience.
        ids_to_try = [run_id]
        if not run_id.startswith("run_"):
            ids_to_try.append(f"run_{run_id}")

        doc = None
        for id_variant in ids_to_try:
            doc = await db["runs"].find_one({"id": id_variant})
            if doc:
                break

        if not doc:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

        return _doc_to_run_response(doc)

    except HTTPException:
        raise
    except OperationFailure as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(body: RunCreate, db: DatabaseDep):
    """
    Create and trigger a new run.
    
    This starts an asynchronous run process.
    """
    try:
        from fastapi.concurrency import run_in_threadpool

        from archiverr.core.orchestrator import build_orchestrator
        from archiverr.utils.config_loader import load_config_with_tracking

        # Load config
        config = body.config or load_config_with_tracking("config.yml")

        # Override dry_run
        config.setdefault('options', {})['dry_run'] = body.dry_run

        # Build and run orchestrator in thread pool to avoid blocking event loop
        def _run_orchestrator():
            orchestrator = build_orchestrator(config)
            return orchestrator.run()

        result = await run_in_threadpool(_run_orchestrator)

        # Get run from canonical 'runs' collection
        doc = await db["runs"].find_one({"id": result.run_id})

        if doc:
            return _doc_to_run_response(doc)

        # Fallback: create response from result
        return RunResponse(
            id=result.run_id,
            status=RunStatus(
                state=StateEnum.SUCCESS if result.success else StateEnum.FAILED,
                success=result.success,
                total_jobs=result.total_jobs,
                completed=result.completed,
                failed=result.failed,
                duration_ms=result.duration_ms,
                error=result.error
            ),
            created_at=datetime.now(timezone.utc)
        )

    except OperationFailure as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{run_id}", status_code=204)
async def delete_run(run_id: str, db: DatabaseDep):
    """
    Delete a run and its associated data.
    """
    try:
        # Find the run by id (canonical 'runs' collection)
        ids_to_try = [run_id]
        if not run_id.startswith("run_"):
            ids_to_try.append(f"run_{run_id}")

        doc = None
        actual_id = run_id
        for id_variant in ids_to_try:
            doc = await db["runs"].find_one({"id": id_variant})
            if doc:
                actual_id = id_variant
                break

        if not doc:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

        # Cascade delete on canonical collections (no-delete policy: caller must
        # ensure prod backup; this is the API surface for run lifecycle removal)
        await db["jobs"].delete_many({"run_id": actual_id})
        await db["plugins"].delete_many({"run_id": actual_id})
        await db["plugin_executions"].delete_many({"run_id": actual_id})
        await db["runs"].delete_one({"id": actual_id})

    except HTTPException:
        raise
    except OperationFailure as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/status")
async def get_run_status(run_id: str, db: DatabaseDep):
    """
    Get run status (for polling).
    """
    run = await get_run(run_id, db)
    return {
        "id": run.id,
        "state": run.status.state.value,
        "success": run.status.success,
        "total_jobs": run.status.total_jobs,
        "completed": run.status.completed,
        "failed": run.status.failed,
        "duration_ms": run.status.duration_ms
    }


@router.get("/{run_id}/jobs")
async def get_run_jobs(
    run_id: str,
    db: DatabaseDep,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """
    Get jobs for a specific run.
    """
    try:
        # Canonical: 'jobs' collection, 'run_id' field. Allow bare-id input.
        run_id_variants = [run_id]
        if not run_id.startswith("run_"):
            run_id_variants.append(f"run_{run_id}")

        jobs = []
        total = 0
        for variant in run_id_variants:
            cursor = db["jobs"].find({"run_id": variant}).skip(offset).limit(limit)
            jobs = await cursor.to_list(length=limit)
            if jobs:
                total = await db["jobs"].count_documents({"run_id": variant})
                break

        # Drop Mongo's internal ObjectId (not JSON-serializable by FastAPI's
        # default encoder). Canonical 'id' field is preserved.
        for job in jobs:
            job.pop("_id", None)

        return {
            "run_id": run_id,
            "total": total,
            "jobs": jobs
        }

    except OperationFailure as e:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {e}")
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
