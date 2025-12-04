"""
Legacy Endpoint Redirects - Session 11 Phase 8

Provides backward compatibility by redirecting old endpoints to new ones.

Redirects:
- /executions → /runs
- /matches → /jobs
"""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["Legacy (Deprecated)"])


# =============================================================================
# EXECUTIONS → RUNS
# =============================================================================

@router.get("/executions", deprecated=True, include_in_schema=True)
async def legacy_list_executions():
    """
    **DEPRECATED**: Use `/runs` instead.
    
    Redirects to `/v1/runs` with 301 Moved Permanently.
    """
    return RedirectResponse(url="/v1/runs", status_code=301)


@router.get("/executions/{execution_id}", deprecated=True, include_in_schema=True)
async def legacy_get_execution(execution_id: str):
    """
    **DEPRECATED**: Use `/runs/{id}` instead.
    
    Redirects to `/v1/runs/{id}` with 301 Moved Permanently.
    """
    # Convert exec_ prefix to run_ if needed
    run_id = execution_id.replace("exec_", "run_") if execution_id.startswith("exec_") else execution_id
    return RedirectResponse(url=f"/v1/runs/{run_id}", status_code=301)


@router.get("/executions/{execution_id}/status", deprecated=True, include_in_schema=True)
async def legacy_execution_status(execution_id: str):
    """
    **DEPRECATED**: Use `/runs/{id}/status` instead.
    """
    run_id = execution_id.replace("exec_", "run_") if execution_id.startswith("exec_") else execution_id
    return RedirectResponse(url=f"/v1/runs/{run_id}/status", status_code=301)


@router.get("/executions/{execution_id}/matches", deprecated=True, include_in_schema=True)
async def legacy_execution_matches(execution_id: str):
    """
    **DEPRECATED**: Use `/runs/{id}/jobs` instead.
    """
    run_id = execution_id.replace("exec_", "run_") if execution_id.startswith("exec_") else execution_id
    return RedirectResponse(url=f"/v1/runs/{run_id}/jobs", status_code=301)


# =============================================================================
# MATCHES → JOBS
# =============================================================================

@router.get("/matches", deprecated=True, include_in_schema=True)
async def legacy_list_matches():
    """
    **DEPRECATED**: Use `/jobs` instead.
    
    Redirects to `/v1/jobs` with 301 Moved Permanently.
    """
    return RedirectResponse(url="/v1/jobs", status_code=301)


@router.get("/matches/{match_id}", deprecated=True, include_in_schema=True)
async def legacy_get_match(match_id: str):
    """
    **DEPRECATED**: Use `/jobs/{id}` instead.
    """
    return RedirectResponse(url=f"/v1/jobs/{match_id}", status_code=301)


@router.get("/matches/{match_id}/plugins", deprecated=True, include_in_schema=True)
async def legacy_match_plugins(match_id: str):
    """
    **DEPRECATED**: Use `/jobs/{id}/plugins` instead.
    """
    return RedirectResponse(url=f"/v1/jobs/{match_id}/plugins", status_code=301)
