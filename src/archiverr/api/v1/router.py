"""API v1 Main Router."""

from fastapi import APIRouter

from .jobs.router import router as jobs_router
from .plugins.router import router as plugins_router
from .run.router import router as run_router
from .runs.router import router as runs_router
from .system.router import router as system_router

router = APIRouter()

# Core endpoints
router.include_router(runs_router, prefix="/runs", tags=["Runs"])
router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
router.include_router(plugins_router, prefix="/plugins", tags=["Plugins"])
router.include_router(run_router, prefix="/run", tags=["Run"])
router.include_router(system_router, prefix="/system", tags=["System"])
# system_router exposes /system/{health,status,version,diagnostics}.
# Inline /system/health and /system/info defined here previously were
# redundant and shadowed the richer system_router endpoints. Removed in
# S36 PASS 6.D after audit found system/router.py was never included.
