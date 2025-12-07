# FASTAPI REFACTORING TODO

```yaml
created: 2025-12-04
priority: P1
status: ready_for_implementation
source: 11_FASTAPI_REFACTORING.md, FINAL_DATASETS.yml
```

---

## 1. ENDPOINT RENAMING

### Current → New

| Current | New | Priority |
|---------|-----|----------|
| POST /api/v1/run | POST /api/v1/runs | P0 |
| GET /api/v1/executions | GET /api/v1/runs | P0 |
| GET /api/v1/executions/{id} | GET /api/v1/runs/{id} | P0 |
| GET /api/v1/matches | GET /api/v1/jobs | P0 |
| GET /api/v1/matches/{id} | GET /api/v1/jobs/{id} | P0 |
| - | GET /api/v1/jobs/{id}/plugins | P1 |
| - | GET /api/v1/plugins | P1 |
| - | GET /api/v1/config | P2 |

---

## 2. PYDANTIC SCHEMAS

### 2.1 Enums Update
```python
# api/v1/schemas/enums.py

class StateEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# REMOVE: ExecutionStatus (use StateEnum)
```

### 2.2 New Schemas Required
```python
# api/v1/schemas/run.py
class RunStatus(BaseModel):
    state: StateEnum
    success: bool
    total_jobs: int
    completed: int
    failed: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: int

class RunResponse(BaseModel):
    id: str
    status: RunStatus
    config: Dict[str, Any]

class RunListResponse(BaseModel):
    runs: List[RunResponse]
    total: int
    limit: int
    offset: int

# api/v1/schemas/job.py
class InputData(BaseModel):
    value: str
    data: Dict[str, Any] = {}

class OutputData(BaseModel):
    values: List[str] = []
    data: Dict[str, Any] = {}

class JobStatus(BaseModel):
    state: StateEnum
    success: bool
    executed: List[str] = []
    failed: List[str] = []
    skipped: List[str] = []

class JobResponse(BaseModel):
    id: str
    index: int
    run_id: str
    input: InputData
    output: OutputData
    status: JobStatus

# api/v1/schemas/plugin.py
class PluginStatus(BaseModel):
    success: bool
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    error: Optional[str]

class PluginResponse(BaseModel):
    job_id: str
    run_id: str
    job_index: int
    plugin_name: str
    stage: str
    status: PluginStatus
    data: Dict[str, Any]
```

---

## 3. ROUTER UPDATES

### 3.1 Runs Router (New)
```python
# api/v1/runs/router.py

from fastapi import APIRouter, Depends, HTTPException
router = APIRouter(prefix="/runs", tags=["runs"])

@router.get("/", response_model=RunListResponse)
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[StateEnum] = None
):
    pass

@router.post("/", response_model=RunStartResponse)
async def start_run(request: RunCreateRequest):
    pass

@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    pass

@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    pass

@router.get("/{run_id}/jobs", response_model=JobListResponse)
async def get_run_jobs(run_id: str):
    pass
```

### 3.2 Jobs Router (New)
```python
# api/v1/jobs/router.py

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    run_id: Optional[str] = None,
    status: Optional[StateEnum] = None
):
    pass

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    pass

@router.get("/{job_id}/plugins", response_model=PluginListResponse)
async def get_job_plugins(job_id: str):
    pass
```

### 3.3 Plugins Router (New)
```python
# api/v1/plugins/router.py

router = APIRouter(prefix="/plugins", tags=["plugins"])

@router.get("/", response_model=PluginListResponse)
async def list_plugins(
    run_id: Optional[str] = None,
    job_id: Optional[str] = None,
    plugin_name: Optional[str] = None
):
    pass
```

---

## 4. DEPRECATION ROUTES (Optional)

```python
# For smooth transition, redirect old endpoints:
@app.get("/api/v1/executions/{id}")
async def deprecated_get_execution(id: str):
    return RedirectResponse(f"/api/v1/runs/{id}")

@app.get("/api/v1/matches/{id}")
async def deprecated_get_match(id: str):
    return RedirectResponse(f"/api/v1/jobs/{id}")
```

---

## 5. RESPONSE COMPARISON

### Current Response (Legacy)
```json
{
  "execution_id": "abc123",
  "status": "completed",
  "summary": {
    "total_matches": 10,
    "completed_matches": 10,
    "failed_matches": 0
  },
  "matches": [
    {
      "index": 0,
      "input_path": "/path/file.mkv",
      "plugins": {...}
    }
  ]
}
```

### New Response (FINAL_DATASETS.yml compliant)
```json
{
  "run": {
    "id": "run_abc123",
    "status": {
      "state": "completed",
      "success": true,
      "total_jobs": 10,
      "completed": 10,
      "failed": 0
    }
  },
  "jobs": [
    {
      "id": "job_run_abc123_0",
      "index": 0,
      "run_id": "run_abc123",
      "input": {
        "value": "/path/file.mkv",
        "data": {...}
      },
      "output": {
        "values": ["/archive/..."],
        "data": {...}
      },
      "status": {...}
    }
  ]
}
```

---

## 6. FILES TO CREATE/UPDATE

### Create
- [ ] `api/v1/runs/router.py`
- [ ] `api/v1/runs/schemas.py`
- [ ] `api/v1/jobs/router.py`
- [ ] `api/v1/jobs/schemas.py`
- [ ] `api/v1/plugins/router.py`
- [ ] `api/v1/plugins/schemas.py`

### Update
- [ ] `api/v1/main.py` - Include new routers
- [ ] `api/v1/schemas/__init__.py` - Export new schemas

### Delete (After Migration)
- [ ] `api/v1/executions/` - Replaced by runs
- [ ] `api/v1/matches/` - Replaced by jobs
- [ ] `api/v1/run/` - Replaced by POST /runs

---

## 7. CHECKLIST

- [ ] Create RunResponse, JobResponse, PluginResponse schemas
- [ ] Create /runs router with all endpoints
- [ ] Create /jobs router with all endpoints
- [ ] Create /plugins router
- [ ] Update main.py to include new routers
- [ ] Test all new endpoints
- [ ] Remove legacy endpoints
- [ ] Update API documentation
