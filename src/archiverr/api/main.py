"""
FastAPI Application - Main Entry Point

Industry-standard FastAPI setup with:
- CORS middleware
- Lifespan management (startup/shutdown)
- MongoDB connection via Motor (async)
- Router includes
- OpenAPI documentation

Best Practice: Uses lifespan pattern for database connection management.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from archiverr.infrastructure.database import mongodb_lifespan

from .middleware import RateLimiter, RateLimitMiddleware
from .v1.router import router as v1_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application factory pattern.
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Archiverr API",
        description="""
## Archiverr - Config-Driven Media Organizer API

A plugin-based media processing system with real-time execution monitoring
and git-like versioning for execution history.

### Core Features

- **Execution Management**: Start, monitor, and manage media processing pipelines
- **Real-time Updates**: WebSocket support for live progress streaming
- **Plugin System**: Extensible architecture with configurable plugin execution
- **Task Templates**: Jinja2-based output formatting and file operations

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/v1/run` | Subprocess CLI proxy (blackbox trigger; full-process isolation) |
| `/api/v1/runs` | RESTful CRUD over runs (in-process orchestrator) |
| `/api/v1/jobs` | Read jobs by run / by id |
| `/api/v1/plugins` | Cross-job plugin output query |
| `/api/v1/system` | Health, version, diagnostics |
        """,
        version="1.0.0",
        lifespan=mongodb_lifespan,  # Industry best practice
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # CORS - allow all origins in development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    if os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true":
        limiter = RateLimiter()  # Uses default config
        app.add_middleware(RateLimitMiddleware, limiter=limiter)

    # Include routers
    app.include_router(v1_router, prefix="/api/v1")

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """API information and links to documentation."""
        return {
            "name": "Archiverr API",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }

    return app


# Create app instance
app = create_app()
