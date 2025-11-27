"""
Archiverr FastAPI Application

Industry-standard REST API for Archiverr media organizer.
Provides endpoints for:
- Execution management (start, status, list)
- Match queries
- Plugin management
- Configuration
- System health

Usage:
    python -m archiverr serve
    # or
    uvicorn archiverr.api.main:app --reload
"""

from .main import app, create_app

__all__ = ["app", "create_app"]
