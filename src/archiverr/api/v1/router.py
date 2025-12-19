"""API v1 Main Router."""

from fastapi import APIRouter

from .runs.router import router as runs_router
from .jobs.router import router as jobs_router
from .plugins.router import router as plugins_router
from .run.router import router as run_router

router = APIRouter()

# Core endpoints
router.include_router(runs_router, prefix="/runs", tags=["Runs"])
router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
router.include_router(plugins_router, prefix="/plugins", tags=["Plugins"])
router.include_router(run_router, prefix="/run", tags=["Run"])


# Health endpoint
@router.get("/system/health", tags=["System"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.1.0"}


@router.get("/system/info", tags=["System"])
def system_info():
    """System information endpoint"""
    return {
        "name": "Archiverr API",
        "version": "1.2.0",
        "api_version": "v1",
        "endpoints": {
            "runs": "/v1/runs",
            "jobs": "/v1/jobs",
            "plugins": "/v1/plugins",
            "execute": "/v1/run",
            "health": "/v1/system/health"
        }
    }
