"""
API v1 Main Router

Aggregates all domain routers:
- /run - Execute archiverr (subprocess based)
- /executions - Execution history
- /matches - Match data access
- /versioning - Branch management
- /system - Health and status
"""

from fastapi import APIRouter

from .run.router import router as run_router
from .executions.router import router as executions_router
from .matches.router import router as matches_router
from .versioning.router import router as versioning_router

router = APIRouter()

# Main endpoints
router.include_router(run_router, prefix="/run", tags=["Run"])
router.include_router(executions_router, prefix="/executions", tags=["Executions"])
router.include_router(matches_router, prefix="/matches", tags=["Matches"])
router.include_router(versioning_router, prefix="/versioning", tags=["Versioning"])


# Health endpoint
@router.get("/system/health", tags=["System"])
def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}
