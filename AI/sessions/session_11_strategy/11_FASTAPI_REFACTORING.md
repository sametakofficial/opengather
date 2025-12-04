# FASTAPI REFACTORING - SESSION 11 BRAINSTORM

```yaml
tarih: 2025-12-04
durum: brainstorm
kaynak:
  - FINAL_DATASETS.yml (TRUTH SOURCE)
  - session_11_strategy/*.md (tüm strateji dosyaları)
  - src/archiverr/api/ (mevcut kod)
  - src/archiverr/state/models.py (mevcut modeller)
```

---

## YÖNETİCİ ÖZETİ

### Temel Değişiklikler

| Kategori         | MEVCUT                              | YENİ                       |
| ---------------- | ----------------------------------- | -------------------------- |
| **Terminoloji**  | execution, match                    | run, job                   |
| **Endpoints**    | /executions, /matches               | /runs, /jobs, /plugins     |
| **Collections**  | executions, matches, plugin_results | runs, jobs, plugins        |
| **State Models** | ExecutionState, MatchState          | RunState, JobState         |
| **Input**        | input_path                          | input.value, input.data    |
| **Output**       | tasks[]                             | output.values, output.data |

---

## 1. MEVCUT API YAPISI ANALİZİ

### 1.1 Endpoint Yapısı (Şu An)

```
/api/v1/
├── /run                    # POST: Subprocess ile çalıştır
│   └── POST /              # Sync subprocess execution
│
├── /executions             # Execution CRUD
│   ├── GET /               # List executions
│   ├── GET /{id}           # Get execution details
│   ├── GET /{id}/status    # Polling endpoint
│   └── GET /{id}/matches   # Get matches for execution
│
├── /matches                # Match queries
│   ├── GET /               # List matches
│   ├── GET /{id}           # Get match details
│   └── GET /{id}/plugins   # Get plugin results
│
├── /versioning/branches    # Git-like versioning
│   ├── GET /               # List branches
│   ├── POST /              # Create branch
│   └── GET /{name}         # Get branch
│
└── /system/health          # Health check
```

### 1.2 Mevcut Sorunlar

1. **Terminoloji Tutarsızlığı**: `execution/match` vs strateji `run/job`
2. **Subprocess Yaklaşımı**: `/run` endpoint subprocess kullanıyor
3. **Schema Uyumsuzluğu**: Pydantic modeller eski yapıda
4. **Collection İsimleri**: `executions`, `matches`, `plugin_results`
5. **Response Yapısı**: `globals` wrapper, `input_path` vs `input.value`

### 1.3 Mevcut Pydantic Modeller

```python
# MEVCUT (executions/schemas.py)
class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionSummary(BaseModel):
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0

class ExecutionResponse(BaseModel):
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    success: bool
    summary: ExecutionSummary
    config_snapshot: Optional[Dict[str, Any]]
    websocket_url: Optional[str]
    poll_url: Optional[str]
```

---

## 2. YENİ API YAPISI (HEDEF)

### 2.1 Endpoint Yapısı (Yeni)

```
/api/v1/
├── /runs                      # Run management (was: /executions)
│   ├── GET /                  # List runs
│   ├── POST /                 # Start new run
│   ├── GET /{run_id}          # Get run details
│   ├── GET /{run_id}/status   # Polling endpoint
│   ├── GET /{run_id}/jobs     # Get all jobs for run
│   └── GET /{run_id}/plugins  # Get all plugins for run (optional)
│
├── /jobs                      # Job queries (was: /matches)
│   ├── GET /                  # List jobs (with filters)
│   ├── GET /{job_id}          # Get job details
│   ├── GET /{job_id}/plugins  # Get plugin data for job
│   └── GET /{job_id}/output   # Get job output details
│
├── /plugins                   # Plugin data queries (NEW)
│   ├── GET /                  # List plugin results (with filters)
│   └── GET /{id}              # Get specific plugin result
│
├── /config                    # Config endpoints (NEW)
│   ├── GET /                  # Get current config
│   ├── GET /validate          # Validate config
│   └── GET /plugins           # List available plugins
│
├── /versioning/branches       # Keep as-is
│
└── /system                    # System endpoints
    ├── GET /health            # Health check
    ├── GET /status            # System status
    └── GET /metrics           # Prometheus metrics (optional)
```

### 2.2 Endpoint Detayları

#### 2.2.1 `/runs` Endpoints

```python
# GET /runs
# Query params: limit, offset, status, success
# Response: RunListResponse

# POST /runs
# Body: RunCreateRequest
# Response: RunStartResponse

# GET /runs/{run_id}
# Response: RunResponse (full details with config)

# GET /runs/{run_id}/status
# Response: RunStatusResponse (lightweight for polling)

# GET /runs/{run_id}/jobs
# Query params: limit, offset, status
# Response: JobListResponse
```

#### 2.2.2 `/jobs` Endpoints

```python
# GET /jobs
# Query params: run_id, limit, offset, status, input_value (search)
# Response: JobListResponse

# GET /jobs/{job_id}
# Query params: include_plugins (bool)
# Response: JobResponse

# GET /jobs/{job_id}/plugins
# Response: PluginListResponse

# GET /jobs/{job_id}/output
# Response: JobOutputResponse
```

#### 2.2.3 `/plugins` Endpoints

```python
# GET /plugins
# Query params: run_id, job_id, plugin_name
# Response: PluginListResponse

# GET /plugins/{plugin_id}
# Response: PluginResponse
```

---

## 3. PYDANTIC SCHEMAS (YENİ)

### 3.1 Temel Enums

```python
# api/v1/schemas/enums.py

from enum import Enum

class StateEnum(str, Enum):
    """Run/Job durumu"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class PluginStatusEnum(str, Enum):
    """Plugin execution durumu"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

class StageEnum(str, Enum):
    """Plugin stage'leri"""
    INPUT = "input"
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"
```

### 3.2 Run Schemas

```python
# api/v1/schemas/runs.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RunStatus(BaseModel):
    """Run status detayları - FINAL_DATASETS.yml uyumlu"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

class RunConfig(BaseModel):
    """Run config snapshot"""
    options: Dict[str, Any] = Field(default_factory=dict)
    aliases: Dict[str, str] = Field(default_factory=dict)

class RunResponse(BaseModel):
    """Full run response - FINAL_DATASETS.yml/run uyumlu"""
    id: str = Field(..., description="run_abc123 formatında")
    status: RunStatus
    config: RunConfig

    # API-only fields
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "run_abc123",
                "status": {
                    "state": "completed",
                    "success": True,
                    "total_jobs": 10,
                    "completed": 10,
                    "failed": 0,
                    "started_at": "2024-01-15T12:00:00Z",
                    "finished_at": "2024-01-15T12:01:00Z",
                    "duration_ms": 60000
                },
                "config": {
                    "options": {"debug": True, "dry_run": False},
                    "aliases": {}
                }
            }
        }

class RunListResponse(BaseModel):
    """Paginated run list"""
    total: int
    runs: List[RunResponse]

class RunCreateRequest(BaseModel):
    """New run request"""
    targets: Optional[List[str]] = Field(
        default=None,
        description="Override scanner targets"
    )
    config_override: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Partial config override"
    )
    dry_run: bool = Field(default=False)

class RunStartResponse(BaseModel):
    """Response when run starts"""
    id: str
    status: RunStatus
    websocket_url: str
    poll_url: str
    message: str = "Run started"

class RunStatusResponse(BaseModel):
    """Lightweight status for polling"""
    id: str
    state: StateEnum
    success: bool
    total_jobs: int
    completed: int
    failed: int
    progress_percent: float = Field(default=0.0)
    updated_at: datetime
```

### 3.3 Job Schemas

```python
# api/v1/schemas/jobs.py

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class InputData(BaseModel):
    """Job input - FINAL_DATASETS.yml/job.input uyumlu"""
    value: str = Field(..., description="Input path veya virtual file")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="filename, extension, size_bytes, modified_at, source"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "value": "/data/movies/Movie.Name.2024.1080p.mkv",
                "data": {
                    "filename": "Movie.Name.2024.1080p.mkv",
                    "extension": "mkv",
                    "size_bytes": 5368709120,
                    "modified_at": "2024-01-15T10:00:00Z",
                    "source": "filesystem"
                }
            }
        }

class OutputData(BaseModel):
    """Job output - FINAL_DATASETS.yml/job.output uyumlu"""
    values: List[str] = Field(
        default_factory=list,
        description="Output paths"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task results with details"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "values": [
                    "/srv/archive/Movie (2024)/Movie.mkv",
                    "/srv/archive/Movie (2024)/Movie.nfo"
                ],
                "data": {
                    "tasks": {
                        "save_movie": {
                            "type": "save",
                            "output": "/srv/archive/Movie (2024)/Movie.mkv"
                        }
                    }
                }
            }
        }

class JobStatus(BaseModel):
    """Job status - FINAL_DATASETS.yml/job.status uyumlu"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

class JobResponse(BaseModel):
    """Full job response - FINAL_DATASETS.yml/job uyumlu"""
    index: int
    id: str = Field(..., description="job_run_abc123_0 formatında")
    run_id: str
    input: InputData
    output: OutputData
    status: JobStatus

    # Optional: include plugin data
    plugins: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "index": 0,
                "id": "job_run_abc123_0",
                "run_id": "run_abc123",
                "input": {
                    "value": "/data/movies/Movie.Name.2024.1080p.mkv",
                    "data": {"filename": "Movie.Name.2024.1080p.mkv"}
                },
                "output": {
                    "values": ["/srv/archive/Movie (2024)/Movie.mkv"],
                    "data": {}
                },
                "status": {
                    "state": "completed",
                    "success": True,
                    "executed": ["scanner", "renamer", "tmdb"],
                    "failed": [],
                    "skipped": ["tvdb"]
                }
            }
        }

class JobListResponse(BaseModel):
    """Paginated job list"""
    total: int
    jobs: List[JobResponse]

class JobSummaryResponse(BaseModel):
    """Lightweight job summary"""
    index: int
    id: str
    run_id: str
    input_value: str
    success: bool
    state: StateEnum
```

### 3.4 Plugin Schemas

```python
# api/v1/schemas/plugins.py

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class PluginStatus(BaseModel):
    """Plugin execution status"""
    success: bool
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    error: Optional[str] = None

class PluginResponse(BaseModel):
    """Plugin result - FINAL_DATASETS.yml/plugins uyumlu"""
    job_id: str
    job_index: int
    run_id: str
    plugin_name: str
    stage: StageEnum
    status: PluginStatus
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_run_abc123_0",
                "job_index": 0,
                "run_id": "run_abc123",
                "plugin_name": "tmdb",
                "stage": "data",
                "status": {
                    "success": True,
                    "started_at": "2024-01-15T12:00:02Z",
                    "finished_at": "2024-01-15T12:00:03Z",
                    "duration_ms": 800,
                    "error": None
                },
                "data": {
                    "movie": {
                        "id": 12345,
                        "title": "Movie",
                        "release_date": "2024-01-15"
                    }
                }
            }
        }

class PluginListResponse(BaseModel):
    """Plugin results list"""
    total: int
    plugins: List[PluginResponse]
```

---

## 4. MONGODB COLLECTION DEĞİŞİKLİKLERİ

### 4.1 Collection Mapping

```
MEVCUT                  YENİ                    NOTES
─────────────────────────────────────────────────────────────
executions          →   runs                    Terminoloji değişikliği
matches             →   jobs                    Terminoloji değişikliği
plugin_results      →   plugins                 Kısaltma + memory management
branches            →   branches                Değişiklik yok
```

### 4.2 Document Yapıları

#### runs Collection

```javascript
// YENİ: runs collection
{
    _id: ObjectId,
    id: "run_abc123",                     // Application ID

    status: {
        state: "completed",               // pending|running|completed|failed
        success: true,
        total_jobs: 10,
        completed: 10,
        failed: 0,
        started_at: ISODate,
        finished_at: ISODate,
        duration_ms: 60000
    },

    config: {
        options: {debug: true, dry_run: false},
        aliases: {}
    },

    created_at: ISODate,
    updated_at: ISODate
}

// Indexes
{ "id": 1 } unique
{ "created_at": -1 }
{ "status.state": 1 }
```

#### jobs Collection

```javascript
// YENİ: jobs collection
{
    _id: ObjectId,
    run_id: "run_abc123",
    index: 0,
    id: "job_run_abc123_0",              // Unique job ID

    input: {
        value: "/media/file.mkv",        // path → value
        data: {
            filename: "file.mkv",
            extension: "mkv",
            size_bytes: 5368709120,
            modified_at: ISODate,
            source: "filesystem"
        }
    },

    output: {
        values: ["/srv/archive/Movie.mkv"],
        data: {
            tasks: {
                save_movie: {type: "save", success: true}
            }
        }
    },

    status: {
        state: "completed",
        success: true,
        executed: ["scanner", "renamer", "tmdb"],
        failed: [],
        skipped: ["tvdb"],
        started_at: ISODate,
        finished_at: ISODate,
        duration_ms: 4000
    },

    created_at: ISODate,
    updated_at: ISODate
}

// Indexes
{ "run_id": 1, "index": 1 } unique
{ "id": 1 } unique
{ "run_id": 1 }
{ "input.value": 1 }
```

#### plugins Collection

```javascript
// YENİ: plugins collection (ayrı - memory management)
{
    _id: ObjectId,
    run_id: "run_abc123",
    job_id: "job_run_abc123_0",
    job_index: 0,
    plugin_name: "tmdb",
    stage: "data",

    status: {
        success: true,
        started_at: ISODate,
        finished_at: ISODate,
        duration_ms: 800,
        error: null
    },

    data: {
        movie: {
            id: 12345,
            title: "Movie",
            release_date: "2024-01-15",
            // ... full plugin data
        }
    },

    created_at: ISODate
}

// Indexes
{ "run_id": 1, "job_index": 1, "plugin_name": 1 } unique
{ "job_id": 1, "plugin_name": 1 } unique
{ "run_id": 1 }
{ "job_id": 1 }
```

---

## 5. ROUTER YAPISI (YENİ)

### 5.1 Dizin Yapısı

```
src/archiverr/api/
├── __init__.py
├── main.py                    # FastAPI app factory
├── deps/                      # Dependencies (mevcut)
│   ├── __init__.py
│   ├── database.py
│   └── common.py
│
├── v1/
│   ├── __init__.py
│   ├── router.py              # Main v1 router
│   │
│   ├── runs/                  # NEW: was executions
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── jobs/                  # NEW: was matches
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── plugins/               # NEW
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── config/                # NEW
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   ├── versioning/            # Keep as-is
│   │   ├── __init__.py
│   │   ├── router.py
│   │   └── schemas.py
│   │
│   └── system/                # Expand
│       ├── __init__.py
│       ├── router.py
│       └── schemas.py
│
└── schemas/                   # Shared schemas
    ├── __init__.py
    ├── enums.py
    ├── common.py
    └── pagination.py
```

### 5.2 Main Router

```python
# api/v1/router.py

from fastapi import APIRouter

from .runs.router import router as runs_router
from .jobs.router import router as jobs_router
from .plugins.router import router as plugins_router
from .config.router import router as config_router
from .versioning.router import router as versioning_router
from .system.router import router as system_router

router = APIRouter()

# Core endpoints
router.include_router(runs_router, prefix="/runs", tags=["Runs"])
router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
router.include_router(plugins_router, prefix="/plugins", tags=["Plugins"])

# Config & System
router.include_router(config_router, prefix="/config", tags=["Config"])
router.include_router(system_router, prefix="/system", tags=["System"])

# Versioning
router.include_router(versioning_router, prefix="/versioning", tags=["Versioning"])

# Backward Compatibility (DEPRECATED)
# /executions → /runs redirect
# /matches → /jobs redirect
```

---

## 6. RUNS ROUTER IMPLEMENTATION

```python
# api/v1/runs/router.py

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from archiverr.api.deps import DatabaseDep
from .schemas import (
    RunResponse,
    RunListResponse,
    RunCreateRequest,
    RunStartResponse,
    RunStatusResponse,
    RunStatus,
    RunConfig
)
from ..schemas.enums import StateEnum

router = APIRouter()


def _doc_to_run_response(doc: dict) -> RunResponse:
    """MongoDB document → RunResponse"""
    status_doc = doc.get("status", {})
    config_doc = doc.get("config", {})

    return RunResponse(
        id=doc.get("id", ""),
        status=RunStatus(
            state=StateEnum(status_doc.get("state", "pending")),
            success=status_doc.get("success", True),
            total_jobs=status_doc.get("total_jobs", 0),
            completed=status_doc.get("completed", 0),
            failed=status_doc.get("failed", 0),
            started_at=status_doc.get("started_at"),
            finished_at=status_doc.get("finished_at"),
            duration_ms=status_doc.get("duration_ms", 0)
        ),
        config=RunConfig(
            options=config_doc.get("options", {}),
            aliases=config_doc.get("aliases", {})
        ),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at")
    )


@router.get("/", response_model=RunListResponse)
async def list_runs(
    db: DatabaseDep,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    success: Optional[bool] = Query(default=None)
):
    """
    List all runs with pagination and filters.
    """
    query = {}
    if status:
        query["status.state"] = status
    if success is not None:
        query["status.success"] = success

    cursor = db["runs"].find(query).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)
    total = await db["runs"].count_documents(query)

    return RunListResponse(
        total=total,
        runs=[_doc_to_run_response(doc) for doc in docs]
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, db: DatabaseDep):
    """
    Get run details by ID.
    """
    # Normalize ID
    if not run_id.startswith("run_"):
        run_id = f"run_{run_id}"

    doc = await db["runs"].find_one({"id": run_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return _doc_to_run_response(doc)


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str, db: DatabaseDep):
    """
    Lightweight status for polling.
    """
    if not run_id.startswith("run_"):
        run_id = f"run_{run_id}"

    doc = await db["runs"].find_one(
        {"id": run_id},
        {"id": 1, "status": 1, "updated_at": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    status = doc.get("status", {})
    total = status.get("total_jobs", 0)
    completed = status.get("completed", 0)

    return RunStatusResponse(
        id=run_id,
        state=StateEnum(status.get("state", "pending")),
        success=status.get("success", True),
        total_jobs=total,
        completed=completed,
        failed=status.get("failed", 0),
        progress_percent=(completed / total * 100) if total > 0 else 0,
        updated_at=doc.get("updated_at", datetime.now(timezone.utc))
    )


@router.get("/{run_id}/jobs")
async def get_run_jobs(
    run_id: str,
    db: DatabaseDep,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    include_plugins: bool = Query(default=False)
):
    """
    Get all jobs for a run.
    """
    if not run_id.startswith("run_"):
        run_id = f"run_{run_id}"

    # Verify run exists
    run = await db["runs"].find_one({"id": run_id})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Get jobs
    cursor = db["jobs"].find({"run_id": run_id}).sort("index", 1).skip(offset).limit(limit)
    jobs = await cursor.to_list(length=limit)
    total = await db["jobs"].count_documents({"run_id": run_id})

    # Optionally include plugin data
    if include_plugins:
        for job in jobs:
            job_id = job.get("id")
            plugins_cursor = db["plugins"].find({"job_id": job_id})
            plugin_docs = await plugins_cursor.to_list(length=100)
            job["plugins"] = {p["plugin_name"]: p["data"] for p in plugin_docs}

    return {
        "run_id": run_id,
        "total": total,
        "jobs": jobs
    }


@router.post("/", response_model=RunStartResponse)
async def start_run(
    request: RunCreateRequest,
    db: DatabaseDep,
    background_tasks: BackgroundTasks
):
    """
    Start a new run.

    This creates a run record and starts execution in background.
    """
    import uuid

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Create run document
    run_doc = {
        "id": run_id,
        "status": {
            "state": "pending",
            "success": True,
            "total_jobs": 0,
            "completed": 0,
            "failed": 0,
            "started_at": now.isoformat(),
            "finished_at": None,
            "duration_ms": 0
        },
        "config": {
            "options": request.config_override or {},
            "aliases": {}
        },
        "targets": request.targets,
        "dry_run": request.dry_run,
        "created_at": now,
        "updated_at": now
    }

    await db["runs"].insert_one(run_doc)

    # TODO: Start execution in background
    # background_tasks.add_task(execute_run, run_id, request)

    return RunStartResponse(
        id=run_id,
        status=RunStatus(
            state=StateEnum.PENDING,
            started_at=now
        ),
        websocket_url=f"/api/v1/runs/{run_id}/stream",
        poll_url=f"/api/v1/runs/{run_id}/status"
    )
```

---

## 7. JOBS ROUTER IMPLEMENTATION

```python
# api/v1/jobs/router.py

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from archiverr.api.deps import DatabaseDep
from .schemas import JobResponse, JobListResponse
from ..schemas.enums import StateEnum

router = APIRouter()


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    db: DatabaseDep,
    run_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    success: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Search input.value"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """
    List jobs with filters.
    """
    query = {}

    if run_id:
        if not run_id.startswith("run_"):
            run_id = f"run_{run_id}"
        query["run_id"] = run_id

    if status:
        query["status.state"] = status

    if success is not None:
        query["status.success"] = success

    if search:
        query["input.value"] = {"$regex": search, "$options": "i"}

    cursor = db["jobs"].find(query).sort("created_at", -1).skip(offset).limit(limit)
    jobs = await cursor.to_list(length=limit)
    total = await db["jobs"].count_documents(query)

    return JobListResponse(
        total=total,
        jobs=jobs
    )


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: DatabaseDep,
    include_plugins: bool = Query(default=True)
):
    """
    Get job details by ID.
    """
    if not job_id.startswith("job_"):
        job_id = f"job_{job_id}"

    job = await db["jobs"].find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if include_plugins:
        plugins_cursor = db["plugins"].find({"job_id": job_id})
        plugin_docs = await plugins_cursor.to_list(length=100)
        job["plugins"] = {p["plugin_name"]: p["data"] for p in plugin_docs}

    return job


@router.get("/{job_id}/plugins")
async def get_job_plugins(job_id: str, db: DatabaseDep):
    """
    Get all plugin results for a job.
    """
    if not job_id.startswith("job_"):
        job_id = f"job_{job_id}"

    # Verify job exists
    job = await db["jobs"].find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    cursor = db["plugins"].find({"job_id": job_id})
    plugins = await cursor.to_list(length=100)

    return {
        "job_id": job_id,
        "total": len(plugins),
        "plugins": plugins
    }


@router.get("/{job_id}/output")
async def get_job_output(job_id: str, db: DatabaseDep):
    """
    Get job output details.
    """
    if not job_id.startswith("job_"):
        job_id = f"job_{job_id}"

    job = await db["jobs"].find_one(
        {"id": job_id},
        {"id": 1, "output": 1, "status": 1}
    )
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": job_id,
        "output": job.get("output", {}),
        "success": job.get("status", {}).get("success", False)
    }
```

---

## 8. STATE MODEL MIGRATION

### 8.1 Mevcut → Yeni Model Mapping

```python
# MEVCUT (state/models.py)
class ExecutionState:
    id: str
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: int
    success: bool
    status: ExecutionStatus
    total_matches: int
    completed_matches: int
    failed_matches: int
    config_snapshot: Dict

# YENİ (state/models.py)
@dataclass
class RunState:
    id: str                              # run_abc123
    status: RunStatus                    # Nested status object
    config: Dict[str, Any]               # Frozen config snapshot

@dataclass
class RunStatus:
    state: StateEnum                     # pending|running|completed|failed
    success: bool
    total_jobs: int                      # was: total_matches
    completed: int                       # was: completed_matches
    failed: int                          # was: failed_matches
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: int
```

```python
# MEVCUT
class MatchState:
    index: int
    input_path: str                      # → input.value
    execution_id: str                    # → run_id
    success: bool
    status: ExecutionStatus
    executed_plugins: List[str]          # → status.executed
    failed_plugins: List[str]            # → status.failed
    not_supported_plugins: List[str]     # → status.skipped
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: int
    tasks: List[Dict]                    # → output.data.tasks
    plugins: Dict[str, Dict]

# YENİ
@dataclass
class JobState:
    index: int
    id: str                              # job_run_abc123_0
    run_id: str
    input: InputData                     # {value, data}
    output: OutputData                   # {values, data}
    status: JobStatus                    # {state, success, executed, failed, skipped, ...}
    # plugins ayrı collection'da (memory management)
```

### 8.2 Yeni State Models

```python
# state/models.py (YENİ)

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class StateEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class InputData:
    """Job input - FINAL_DATASETS.yml uyumlu"""
    value: str                                    # Path veya virtual file
    data: Dict[str, Any] = field(default_factory=dict)
    # data içeriği:
    #   filename: str
    #   extension: str
    #   size_bytes: int
    #   modified_at: datetime
    #   source: str (filesystem|api|manual)


@dataclass
class OutputData:
    """Job output - FINAL_DATASETS.yml uyumlu"""
    values: List[str] = field(default_factory=list)    # Output paths
    data: Dict[str, Any] = field(default_factory=dict)  # Task results


@dataclass
class JobStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: List[str] = field(default_factory=list)   # was: executed_plugins
    failed: List[str] = field(default_factory=list)     # was: failed_plugins
    skipped: List[str] = field(default_factory=list)    # was: not_supported_plugins
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0


@dataclass
class JobState:
    """Job state - FINAL_DATASETS.yml uyumlu"""
    index: int
    run_id: str
    id: str = ""
    input: InputData = field(default_factory=lambda: InputData(""))
    output: OutputData = field(default_factory=OutputData)
    status: JobStatus = field(default_factory=JobStatus)

    def __post_init__(self):
        if not self.id:
            self.id = f"job_{self.run_id}_{self.index}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "id": self.id,
            "run_id": self.run_id,
            "input": {
                "value": self.input.value,
                "data": self.input.data
            },
            "output": {
                "values": self.output.values,
                "data": self.output.data
            },
            "status": {
                "state": self.status.state.value,
                "success": self.status.success,
                "executed": self.status.executed,
                "failed": self.status.failed,
                "skipped": self.status.skipped,
                "started_at": self.status.started_at.isoformat() if self.status.started_at else None,
                "finished_at": self.status.finished_at.isoformat() if self.status.finished_at else None,
                "duration_ms": self.status.duration_ms
            }
        }


@dataclass
class RunStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0


@dataclass
class RunState:
    """Run state - FINAL_DATASETS.yml uyumlu"""
    id: str
    status: RunStatus = field(default_factory=RunStatus)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": {
                "state": self.status.state.value,
                "success": self.status.success,
                "total_jobs": self.status.total_jobs,
                "completed": self.status.completed,
                "failed": self.status.failed,
                "started_at": self.status.started_at.isoformat() if self.status.started_at else None,
                "finished_at": self.status.finished_at.isoformat() if self.status.finished_at else None,
                "duration_ms": self.status.duration_ms
            },
            "config": self.config
        }
```

---

## 9. BACKWARD COMPATIBILITY

### 9.1 Deprecated Endpoints

```python
# api/v1/compat.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter(
    deprecated=True,
    tags=["Deprecated"]
)


@router.get("/executions")
async def deprecated_list_executions():
    """
    DEPRECATED: Use /runs instead
    """
    return RedirectResponse(url="/api/v1/runs", status_code=301)


@router.get("/executions/{execution_id}")
async def deprecated_get_execution(execution_id: str):
    """
    DEPRECATED: Use /runs/{run_id} instead
    """
    return RedirectResponse(url=f"/api/v1/runs/{execution_id}", status_code=301)


@router.get("/matches")
async def deprecated_list_matches():
    """
    DEPRECATED: Use /jobs instead
    """
    return RedirectResponse(url="/api/v1/jobs", status_code=301)


@router.get("/matches/{match_id}")
async def deprecated_get_match(match_id: str):
    """
    DEPRECATED: Use /jobs/{job_id} instead
    """
    return RedirectResponse(url=f"/api/v1/jobs/{match_id}", status_code=301)
```

### 9.2 Response Adapter

```python
# api/v1/adapters.py

def run_to_legacy_execution(run: dict) -> dict:
    """Convert new run format to legacy execution format"""
    status = run.get("status", {})
    return {
        "execution_id": run.get("id", "").replace("run_", ""),
        "status": status.get("state", "pending"),
        "started_at": status.get("started_at"),
        "finished_at": status.get("finished_at"),
        "duration_ms": status.get("duration_ms"),
        "success": status.get("success", False),
        "summary": {
            "total_matches": status.get("total_jobs", 0),
            "completed_matches": status.get("completed", 0),
            "failed_matches": status.get("failed", 0)
        },
        "config_snapshot": run.get("config", {})
    }


def job_to_legacy_match(job: dict) -> dict:
    """Convert new job format to legacy match format"""
    status = job.get("status", {})
    return {
        "_id": f"match_{job.get('index')}_{job.get('run_id')}",
        "execution_id": job.get("run_id"),
        "index": job.get("index"),
        "input_path": job.get("input", {}).get("value"),
        "success": status.get("success", False),
        "status": status.get("state", "pending"),
        "executed_plugins": status.get("executed", []),
        "failed_plugins": status.get("failed", []),
        "not_supported_plugins": status.get("skipped", [])
    }
```

---

## 10. MIGRATION CHECKLIST

### Phase 1: Schema & Model Updates

```
[ ] State Models
    [ ] RunState, RunStatus dataclasses
    [ ] JobState, JobStatus, InputData, OutputData dataclasses
    [ ] to_dict(), from_dict() methods
    [ ] Unit tests

[ ] Pydantic Schemas
    [ ] api/v1/schemas/enums.py
    [ ] api/v1/schemas/runs.py
    [ ] api/v1/schemas/jobs.py
    [ ] api/v1/schemas/plugins.py
    [ ] api/v1/schemas/common.py
```

### Phase 2: API Endpoints

```
[ ] Runs Router
    [ ] GET /runs
    [ ] GET /runs/{run_id}
    [ ] GET /runs/{run_id}/status
    [ ] GET /runs/{run_id}/jobs
    [ ] POST /runs

[ ] Jobs Router
    [ ] GET /jobs
    [ ] GET /jobs/{job_id}
    [ ] GET /jobs/{job_id}/plugins
    [ ] GET /jobs/{job_id}/output

[ ] Plugins Router
    [ ] GET /plugins
    [ ] GET /plugins/{id}

[ ] Config Router
    [ ] GET /config
    [ ] GET /config/validate
```

### Phase 3: Database Migration

```
[ ] Collection Rename
    [ ] executions → runs
    [ ] matches → jobs
    [ ] plugin_results → plugins

[ ] Document Migration Script
    [ ] Field rename (input_path → input.value)
    [ ] Structure change (flat → nested)
    [ ] Index updates
```

### Phase 4: Backward Compatibility

```
[ ] Deprecated Routes
    [ ] /executions → /runs redirect
    [ ] /matches → /jobs redirect

[ ] Legacy Response Adapters
    [ ] run_to_legacy_execution()
    [ ] job_to_legacy_match()
```

### Phase 5: Testing

```
[ ] Unit Tests
    [ ] Schema validation tests
    [ ] Router endpoint tests

[ ] Integration Tests
    [ ] Full run cycle test
    [ ] MongoDB integration test

[ ] E2E Tests
    [ ] API client tests
```

---

## 11. ÖNEM SIRASI

### Kritik (İlk Yapılmalı)

1. **State Models** - Tüm sistemin temeli
2. **Pydantic Schemas** - API contract
3. **Runs Router** - Core functionality
4. **Jobs Router** - Core functionality

### Yüksek Öncelik

5. **Plugins Router** - Data access
6. **MongoDB Collection Migration** - Data persistence
7. **Backward Compatibility** - Mevcut client'lar

### Orta Öncelik

8. **Config Router** - Convenience
9. **System Router Expansion** - Monitoring
10. **WebSocket Support** - Real-time updates

### Düşük Öncelik

11. **Metrics Endpoint** - Observability
12. **API Versioning** - Future-proofing

---

## 12. SONUÇ

Bu FastAPI refactoring planı:

1. **FINAL_DATASETS.yml** ile tam uyumlu veri yapıları
2. **Session 11 stratejisi** ile tutarlı terminoloji (run/job)
3. **Backward compatibility** için deprecated routes
4. **Memory management** için ayrı plugins collection
5. **Clean architecture** ile modüler yapı

sağlamaktadır.

**Tahmini Süre:** 3-4 gün (full implementation)

---

**Son Güncelleme:** 2025-12-04
