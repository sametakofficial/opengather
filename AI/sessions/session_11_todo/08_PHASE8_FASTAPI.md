# PHASE 8: FASTAPI REFACTORING

```yaml
phase: 8
öncelik: 🟢 DÜŞÜK
tahmini_süre: 6-8 saat
bağımlılık: P1 (State Models), P2 (MongoDB)
strateji_belgesi: 11_FASTAPI_REFACTORING.md
test_türü: api + integration
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P1 tamamlandı (RunState, JobState mevcut)
- [ ] P2 tamamlandı (MongoDB runs/jobs/plugins collections)
- [ ] Pydantic v2 uyumlu modeller hazır
- [ ] API testleri PASS

---

## 1. MEVCUT DURUM

### 1.1 Mevcut API Yapısı

```
src/archiverr/api/
├── main.py                 # FastAPI app
├── __init__.py
└── v1/
    ├── __init__.py
    ├── router.py           # V1 router
    ├── executions/         # Execution endpoints
    │   ├── __init__.py
    │   ├── router.py
    │   └── schemas.py
    ├── matches/            # Match endpoints
    │   ├── __init__.py
    │   ├── router.py
    │   └── schemas.py
    ├── run/                # Run trigger endpoint
    ├── system/             # System info
    └── versioning/         # API versioning
```

### 1.2 Mevcut Endpoint'ler

```
GET  /v1/executions           - List executions
GET  /v1/executions/{id}      - Get execution
POST /v1/executions           - Create execution

GET  /v1/matches              - List matches
GET  /v1/matches/{id}         - Get match
GET  /v1/matches/{id}/plugins/{plugin}  - Get plugin data

POST /v1/run                  - Trigger run
GET  /v1/system/health        - Health check
GET  /v1/system/info          - System info
```

### 1.3 Mevcut Schemas

```python
# MEVCUT - executions/schemas.py
class ExecutionCreate(BaseModel):
    config: Dict[str, Any]

class ExecutionResponse(BaseModel):
    id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    config: Dict[str, Any]
    matches: List[str]  # Match ID'leri

# MEVCUT - matches/schemas.py
class MatchResponse(BaseModel):
    id: str
    execution_id: str
    index: int
    input: Dict[str, Any]
    output: Dict[str, Any]
    plugins: Dict[str, Any]
```

---

## 2. HEDEF YAPI

### 2.1 Yeni API Yapısı

```
src/archiverr/api/
├── main.py
├── __init__.py
└── v1/
    ├── __init__.py
    ├── router.py
    │
    ├── runs/               # YENİ: Run endpoints (eski executions)
    │   ├── __init__.py
    │   ├── router.py
    │   └── schemas.py
    │
    ├── jobs/               # YENİ: Job endpoints (eski matches)
    │   ├── __init__.py
    │   ├── router.py
    │   └── schemas.py
    │
    ├── plugins/            # YENİ: Plugin endpoints
    │   ├── __init__.py
    │   ├── router.py
    │   └── schemas.py
    │
    ├── config/             # YENİ: Config endpoint
    │   ├── __init__.py
    │   └── router.py
    │
    ├── system/
    │
    ├── executions/         # DEPRECATED: Redirect only
    └── matches/            # DEPRECATED: Redirect only
```

### 2.2 Yeni Endpoint'ler

```
# RUNS (eski executions)
GET  /v1/runs               - List runs
GET  /v1/runs/{id}          - Get run
POST /v1/runs               - Create/trigger run
DEL  /v1/runs/{id}          - Delete run

# JOBS (eski matches)
GET  /v1/jobs               - List jobs (with filters)
GET  /v1/jobs/{id}          - Get job
GET  /v1/jobs/run/{run_id}  - Get jobs by run
GET  /v1/jobs/{id}/plugins  - Get all plugin data for job
GET  /v1/jobs/{id}/plugins/{name}  - Get specific plugin data

# PLUGINS (YENİ)
GET  /v1/plugins            - List all plugin data
GET  /v1/plugins/{name}     - Get plugin by name
GET  /v1/plugins/run/{run_id}  - Get plugins by run

# CONFIG (YENİ)
GET  /v1/config             - Get current config
GET  /v1/config/schema      - Get config schema
POST /v1/config/validate    - Validate config

# BACKWARD COMPAT (redirect)
GET  /v1/executions         - 301 → /v1/runs
GET  /v1/matches            - 301 → /v1/jobs
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: Yeni Pydantic Schemas

**Dosya:** `src/archiverr/api/v1/runs/schemas.py` (YENİ)

```python
"""Run schemas (FINAL_DATASETS.yml aligned)"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class StateEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class RunStatus(BaseModel):
    """Run status fields"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


class InputData(BaseModel):
    """Input data structure"""
    value: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class OutputData(BaseModel):
    """Output data structure"""
    values: Dict[str, str] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    """Request body for creating a run"""
    config: Optional[Dict[str, Any]] = None
    dry_run: bool = True


class RunResponse(BaseModel):
    """Run response (aligned with FINAL_DATASETS.yml)"""
    id: str = Field(..., description="Run ID (run_{timestamp}_{hash})")
    status: RunStatus
    input: InputData
    output: OutputData
    jobs: List[str] = Field(default_factory=list, description="Job IDs")
    config: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    """Paginated run list"""
    items: List[RunResponse]
    total: int
    page: int
    page_size: int
```

**Dosya:** `src/archiverr/api/v1/jobs/schemas.py` (YENİ)

```python
"""Job schemas (FINAL_DATASETS.yml aligned)"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class StateEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobStatus(BaseModel):
    """Job status fields"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    error: Optional[str] = None


class InputData(BaseModel):
    """Job input data"""
    value: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)


class OutputData(BaseModel):
    """Job output data"""
    values: Dict[str, str] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Job response (aligned with FINAL_DATASETS.yml)"""
    id: str = Field(..., description="Job ID (job_{run_id}_{index})")
    run_id: str
    index: int
    status: JobStatus
    input: InputData
    output: OutputData
    plugins: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Paginated job list"""
    items: List[JobResponse]
    total: int
    page: int
    page_size: int


class JobPluginResponse(BaseModel):
    """Plugin data for a job"""
    job_id: str
    plugin_name: str
    stage: str
    data: Dict[str, Any]
    status: Dict[str, Any]
```

**Dosya:** `src/archiverr/api/v1/plugins/schemas.py` (YENİ)

```python
"""Plugin schemas"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class PluginInfo(BaseModel):
    """Plugin information from manifest"""
    name: str
    version: str = "1.0.0"
    stage: str
    requires: List[str] = Field(default_factory=list)
    provides: List[str] = Field(default_factory=list)
    trigger_rule: str = "all_success"
    enabled: bool = True


class PluginData(BaseModel):
    """Plugin data entry"""
    id: str
    job_id: str
    run_id: str
    plugin_name: str
    stage: str
    data: Dict[str, Any]
    status: Dict[str, Any]
    created_at: datetime


class PluginListResponse(BaseModel):
    """Plugin list response"""
    items: List[PluginInfo]
    total: int
```

---

### ADIM 2: Runs Router

**Dosya:** `src/archiverr/api/v1/runs/router.py` (YENİ)

```python
"""Runs API router"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime

from .schemas import RunResponse, RunCreate, RunListResponse, StateEnum
from archiverr.infrastructure.persistence import PersistenceInterface
from archiverr.api.dependencies import get_persistence

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunListResponse)
async def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: Optional[StateEnum] = None,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    List all runs with pagination and optional filtering.
    """
    # Build filter
    filter_dict = {}
    if state:
        filter_dict["status.state"] = state.value

    # Get runs from persistence
    runs = persistence.get_runs(
        filter_dict=filter_dict,
        skip=(page - 1) * page_size,
        limit=page_size
    )

    total = persistence.count_runs(filter_dict)

    return RunListResponse(
        items=[_to_run_response(r) for r in runs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Get a specific run by ID.
    """
    run = persistence.get_run(run_id)

    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return _to_run_response(run)


@router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreate,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Create and trigger a new run.
    """
    from archiverr.core.orchestrator import build_orchestrator
    from archiverr.utils.config_loader import load_config_with_tracking

    # Load config (from body or default)
    if body.config:
        config = body.config
    else:
        config = load_config_with_tracking("config.yml")

    # Override dry_run
    config.setdefault('options', {})['dry_run'] = body.dry_run

    # Build and run orchestrator
    orchestrator = build_orchestrator(config)
    result = orchestrator.run()

    # Get run from persistence
    run = persistence.get_run(result.run_id)

    return _to_run_response(run)


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: str,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Delete a run and its associated jobs.
    """
    run = persistence.get_run(run_id)

    if not run:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Delete associated jobs
    persistence.delete_jobs_by_run(run_id)

    # Delete associated plugins
    persistence.delete_plugins_by_run(run_id)

    # Delete run
    persistence.delete_run(run_id)


def _to_run_response(run: dict) -> RunResponse:
    """Convert MongoDB document to RunResponse"""
    return RunResponse(
        id=run.get("id", run.get("_id", "")),
        status=run.get("status", {}),
        input=run.get("input", {}),
        output=run.get("output", {}),
        jobs=run.get("jobs", []),
        config=run.get("config", {}),
        options=run.get("options", {}),
        created_at=run.get("created_at", datetime.now()),
        completed_at=run.get("completed_at")
    )
```

---

### ADIM 3: Jobs Router

**Dosya:** `src/archiverr/api/v1/jobs/router.py` (YENİ)

```python
"""Jobs API router"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional

from .schemas import JobResponse, JobListResponse, JobPluginResponse, StateEnum
from archiverr.infrastructure.persistence import PersistenceInterface
from archiverr.api.dependencies import get_persistence

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_id: Optional[str] = None,
    state: Optional[StateEnum] = None,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    List all jobs with pagination and filtering.
    """
    filter_dict = {}
    if run_id:
        filter_dict["run_id"] = run_id
    if state:
        filter_dict["status.state"] = state.value

    jobs = persistence.get_jobs(
        filter_dict=filter_dict,
        skip=(page - 1) * page_size,
        limit=page_size
    )

    total = persistence.count_jobs(filter_dict)

    return JobListResponse(
        items=[_to_job_response(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/run/{run_id}", response_model=List[JobResponse])
async def get_jobs_by_run(
    run_id: str,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Get all jobs for a specific run.
    """
    jobs = persistence.get_jobs(filter_dict={"run_id": run_id})

    if not jobs:
        raise HTTPException(status_code=404, detail=f"No jobs found for run: {run_id}")

    return [_to_job_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Get a specific job by ID.
    """
    job = persistence.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return _to_job_response(job)


@router.get("/{job_id}/plugins", response_model=List[JobPluginResponse])
async def get_job_plugins(
    job_id: str,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Get all plugin data for a job.
    """
    plugins = persistence.get_plugins(filter_dict={"job_id": job_id})

    return [
        JobPluginResponse(
            job_id=p.get("job_id"),
            plugin_name=p.get("plugin_name"),
            stage=p.get("stage", ""),
            data=p.get("data", {}),
            status=p.get("status", {})
        )
        for p in plugins
    ]


@router.get("/{job_id}/plugins/{plugin_name}", response_model=JobPluginResponse)
async def get_job_plugin(
    job_id: str,
    plugin_name: str,
    persistence: PersistenceInterface = Depends(get_persistence)
):
    """
    Get specific plugin data for a job.
    """
    plugins = persistence.get_plugins(filter_dict={
        "job_id": job_id,
        "plugin_name": plugin_name
    })

    if not plugins:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin {plugin_name} not found for job {job_id}"
        )

    p = plugins[0]
    return JobPluginResponse(
        job_id=p.get("job_id"),
        plugin_name=p.get("plugin_name"),
        stage=p.get("stage", ""),
        data=p.get("data", {}),
        status=p.get("status", {})
    )


def _to_job_response(job: dict) -> JobResponse:
    """Convert MongoDB document to JobResponse"""
    from datetime import datetime

    return JobResponse(
        id=job.get("id", job.get("_id", "")),
        run_id=job.get("run_id", ""),
        index=job.get("index", 0),
        status=job.get("status", {}),
        input=job.get("input", {}),
        output=job.get("output", {}),
        plugins=job.get("plugins", {}),
        created_at=job.get("created_at", datetime.now()),
        completed_at=job.get("completed_at")
    )
```

---

### ADIM 4: Backward Compatibility Router

**Dosya:** `src/archiverr/api/v1/legacy/router.py` (YENİ)

```python
"""Legacy endpoint redirects for backward compatibility"""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["legacy"])


@router.get("/executions", deprecated=True)
async def legacy_executions():
    """
    DEPRECATED: Use /runs instead.
    Redirects to /v1/runs
    """
    return RedirectResponse(url="/v1/runs", status_code=301)


@router.get("/executions/{execution_id}", deprecated=True)
async def legacy_execution(execution_id: str):
    """
    DEPRECATED: Use /runs/{id} instead.
    """
    return RedirectResponse(url=f"/v1/runs/{execution_id}", status_code=301)


@router.get("/matches", deprecated=True)
async def legacy_matches():
    """
    DEPRECATED: Use /jobs instead.
    """
    return RedirectResponse(url="/v1/jobs", status_code=301)


@router.get("/matches/{match_id}", deprecated=True)
async def legacy_match(match_id: str):
    """
    DEPRECATED: Use /jobs/{id} instead.
    """
    return RedirectResponse(url=f"/v1/jobs/{match_id}", status_code=301)
```

---

### ADIM 5: V1 Router Güncelle

**Dosya:** `src/archiverr/api/v1/router.py` (güncelle)

```python
"""V1 API Router"""

from fastapi import APIRouter

from .runs.router import router as runs_router
from .jobs.router import router as jobs_router
from .plugins.router import router as plugins_router
from .config.router import router as config_router
from .system.router import router as system_router
from .legacy.router import router as legacy_router

router = APIRouter(prefix="/v1")

# New endpoints
router.include_router(runs_router)
router.include_router(jobs_router)
router.include_router(plugins_router)
router.include_router(config_router)
router.include_router(system_router)

# Legacy redirects (backward compat)
router.include_router(legacy_router)
```

---

### ADIM 6: Dependencies

**Dosya:** `src/archiverr/api/dependencies.py` (YENİ)

```python
"""FastAPI dependencies"""

from functools import lru_cache
from archiverr.infrastructure.database import DatabaseConnection
from archiverr.infrastructure.persistence import PersistenceInterface


@lru_cache()
def get_db_connection() -> DatabaseConnection:
    """Get cached database connection"""
    return DatabaseConnection.from_env()


def get_persistence() -> PersistenceInterface:
    """Get persistence interface for dependency injection"""
    connection = get_db_connection()
    return connection.connect()
```

---

## 4. MONGODB INDEX'LERİ

```python
# P2'de eklendi, burada doğrulanacak
db.runs.create_index("status.state")
db.runs.create_index("created_at")

db.jobs.create_index("run_id")
db.jobs.create_index([("run_id", 1), ("index", 1)], unique=True)
db.jobs.create_index("status.state")

db.plugins.create_index([("job_id", 1), ("plugin_name", 1)], unique=True)
db.plugins.create_index("run_id")
```

---

## 5. TEST SENARYOLARI

### 5.1 API Tests

```python
# tests/api/test_runs.py

import pytest
from fastapi.testclient import TestClient
from archiverr.api.main import app

client = TestClient(app)


class TestRunsAPI:
    def test_list_runs(self):
        response = client.get("/v1/runs")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_get_run_not_found(self):
        response = client.get("/v1/runs/nonexistent")
        assert response.status_code == 404

    def test_create_run_dry_run(self, mock_config):
        response = client.post("/v1/runs", json={
            "config": mock_config,
            "dry_run": True
        })
        assert response.status_code == 201
        data = response.json()
        assert data["id"].startswith("run_")


class TestJobsAPI:
    def test_list_jobs(self):
        response = client.get("/v1/jobs")
        assert response.status_code == 200

    def test_filter_jobs_by_run(self, existing_run_id):
        response = client.get(f"/v1/jobs?run_id={existing_run_id}")
        assert response.status_code == 200

    def test_get_job_plugins(self, existing_job_id):
        response = client.get(f"/v1/jobs/{existing_job_id}/plugins")
        assert response.status_code == 200


class TestLegacyRedirects:
    def test_executions_redirect(self):
        response = client.get("/v1/executions", follow_redirects=False)
        assert response.status_code == 301
        assert response.headers["location"] == "/v1/runs"

    def test_matches_redirect(self):
        response = client.get("/v1/matches", follow_redirects=False)
        assert response.status_code == 301
        assert response.headers["location"] == "/v1/jobs"
```

---

## 6. PHASE 8 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `RunResponse`, `JobResponse` Pydantic schemas oluşturuldu
- [ ] `/v1/runs` CRUD endpoints çalışıyor
- [ ] `/v1/jobs` endpoints çalışıyor
- [ ] `/v1/jobs/{id}/plugins` endpoint çalışıyor
- [ ] `/v1/plugins` endpoints çalışıyor (opsiyonel)
- [ ] `/v1/config` endpoints çalışıyor (opsiyonel)
- [ ] Legacy redirects çalışıyor (301)
- [ ] Pagination çalışıyor
- [ ] Filtering çalışıyor (state, run_id)
- [ ] API testler PASS
- [ ] OpenAPI docs güncel

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ WebSocket endpoints
- ❌ Real-time progress
- ❌ API authentication

---

## 7. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                  | Belirti             | Çözüm                         |
| ---------------------- | ------------------- | ----------------------------- |
| Pydantic v2 uyumsuzluk | ValidationError     | `from_attributes = True` ekle |
| MongoDB ObjectId       | JSON serialize fail | `str(doc["_id"])` dönüşümü    |
| Empty persistence      | 500 error           | Null check ekle               |
| Legacy redirect loop   | 301 loop            | Path kontrolü                 |
| CORS issues            | Browser block       | CORS middleware ekle          |

---

## 8. SONRAKİ PHASE'E GEÇİŞ

Phase 8 tamamlandığında:

1. Git commit: `feat(api): refactor to runs/jobs endpoints with backward compat`
2. Git tag: `v0.x.x-phase8`
3. `09_PHASE9_MEMORY.md` dosyasını oku (opsiyonel)
4. Memory management tasarımına başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/api/` çalıştır
- `/v1/runs` endpoint test et (Swagger UI)
- `/v1/jobs/{id}/plugins` endpoint test et
- Legacy redirect test et: `curl -I /v1/executions`
- OpenAPI docs kontrol et: `/docs`
