# MONGODB & PERSISTENCE

```yaml
date: 2025-11-30
sources: v3, v5-part2, memory research
status: final
```

---

## 1. COLLECTION YAPISI

```
MongoDB Database: archiverr
├── runs              # eski: executions
├── jobs              # eski: matches
└── plugins           # eski: plugin_results
```

---

## 2. COLLECTION SCHEMAS

### 2.1 runs

```javascript
{
  _id: ObjectId,
  id: "run_abc123",                    // Application ID
  
  status: {
    state: "completed",                // pending|running|completed|failed
    success: true,
    total_jobs: 10,
    completed: 10,
    failed: 0,
    started_at: ISODate,
    finished_at: ISODate,
    duration_ms: 45000
  },
  
  config: {
    options: {debug: true, dry_run: false},
    plugins: {...},
    tasks: [...]
  },
  
  created_at: ISODate,
  updated_at: ISODate
}

// Indexes
{ id: 1 } unique
{ created_at: -1 }
{ "status.state": 1 }
```

### 2.2 jobs

```javascript
{
  _id: ObjectId,
  run_id: "run_abc123",
  index: 0,
  job_id: "job_run_abc123_0",          // Unique across runs
  
  input: {
    path: "/media/file.mkv",
    category: "movie",
    virtual: false
  },
  
  status: {
    state: "completed",
    success: true,
    executed_plugins: ["scanner", "renamer", "tmdb"],
    failed_plugins: [],
    skipped_plugins: ["tvdb"],
    started_at: ISODate,
    finished_at: ISODate,
    duration_ms: 2500
  },
  
  output: {
    tasks: [
      {name: "print_header", type: "print", success: true},
      {name: "save_file", type: "save", success: true, destination: "..."}
    ]
  },
  
  created_at: ISODate,
  updated_at: ISODate
}

// Indexes
{ run_id: 1, index: 1 } unique
{ job_id: 1 } unique
{ run_id: 1 }
{ "input.path": 1 }
```

### 2.3 plugins

```javascript
{
  _id: ObjectId,
  run_id: "run_abc123",
  job_id: "job_run_abc123_0",
  job_index: 0,
  plugin_name: "tmdb",
  
  status: {
    state: "success",                  // success|failed|skipped
    started_at: ISODate,
    finished_at: ISODate,
    duration_ms: 800,
    error: null
  },
  
  data: {
    movie: {
      id: 1234,
      title: "Mr. & Mrs. Smith",
      release_date: "2005-06-10",
      overview: "...",
      poster_path: "/...",
      genres: ["Action", "Comedy"]
    }
  },
  
  created_at: ISODate
}

// Indexes
{ run_id: 1, job_index: 1, plugin_name: 1 } unique
{ job_id: 1, plugin_name: 1 } unique
{ run_id: 1 }
```

---

## 3. PERSISTENCE INTERFACE

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class PersistenceInterface(ABC):
    """Abstract persistence layer"""
    
    # Run operations
    @abstractmethod
    def save_run(self, run: RunState) -> None: pass
    
    @abstractmethod
    def get_run(self, run_id: str) -> Optional[RunState]: pass
    
    @abstractmethod
    def update_run_status(self, run_id: str, status: Dict) -> None: pass
    
    # Job operations
    @abstractmethod
    def save_job(self, job: JobState) -> None: pass
    
    @abstractmethod
    def get_job(self, job_id: str) -> Optional[JobState]: pass
    
    @abstractmethod
    def get_jobs_by_run(self, run_id: str) -> List[JobState]: pass
    
    @abstractmethod
    def update_job_status(self, job_id: str, status: Dict) -> None: pass
    
    # Plugin operations
    @abstractmethod
    def save_plugin_result(
        self, 
        run_id: str, 
        job_id: str, 
        plugin_name: str, 
        result: PluginResult
    ) -> None: pass
    
    @abstractmethod
    def get_plugin_data(
        self, 
        job_id: str, 
        plugin_name: str
    ) -> Optional[Dict]: pass
    
    # Batch operations
    @abstractmethod
    def flush(self) -> None: pass
```

---

## 4. PYMONGO IMPLEMENTATION

```python
class PyMongoPersistence(PersistenceInterface):
    """Sync MongoDB persistence for CLI"""
    
    RUNS = "runs"
    JOBS = "jobs"
    PLUGINS = "plugins"
    
    def __init__(self, db: Database):
        self._db = db
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        self._db[self.RUNS].create_index("id", unique=True)
        self._db[self.JOBS].create_index([("run_id", 1), ("index", 1)], unique=True)
        self._db[self.JOBS].create_index("job_id", unique=True)
        self._db[self.PLUGINS].create_index(
            [("run_id", 1), ("job_index", 1), ("plugin_name", 1)], 
            unique=True
        )
    
    def save_run(self, run: RunState) -> None:
        self._db[self.RUNS].replace_one(
            {"id": run.id},
            {
                "id": run.id,
                "status": run.status.to_dict(),
                "config": run.config,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            upsert=True
        )
    
    def save_job(self, job: JobState) -> None:
        self._db[self.JOBS].replace_one(
            {"job_id": job.job_id},
            {
                "run_id": job.run_id,
                "index": job.index,
                "job_id": job.job_id,
                "input": job.input.to_dict(),
                "status": job.status.to_dict(),
                "output": job.output.to_dict(),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            upsert=True
        )
    
    def save_plugin_result(
        self, 
        run_id: str, 
        job_id: str, 
        plugin_name: str, 
        result: PluginResult
    ) -> None:
        self._db[self.PLUGINS].replace_one(
            {"job_id": job_id, "plugin_name": plugin_name},
            {
                "run_id": run_id,
                "job_id": job_id,
                "job_index": int(job_id.split('_')[-1]),
                "plugin_name": plugin_name,
                "status": {
                    "state": result.status.value,
                    "error": result.error
                },
                "data": result.data or {},
                "created_at": datetime.utcnow()
            },
            upsert=True
        )
    
    def get_job(self, job_id: str) -> Optional[JobState]:
        doc = self._db[self.JOBS].find_one({"job_id": job_id})
        if not doc:
            return None
        
        # Load plugin data
        plugins = {}
        for pdoc in self._db[self.PLUGINS].find({"job_id": job_id}):
            plugins[pdoc["plugin_name"]] = pdoc["data"]
        
        return JobState.from_dict(doc, plugins)
    
    def flush(self) -> None:
        pass  # PyMongo writes immediately
```

---

## 5. MOTOR IMPLEMENTATION (Async)

```python
class MotorPersistence(PersistenceInterface):
    """Async MongoDB persistence for API"""
    
    RUNS = "runs"
    JOBS = "jobs"
    PLUGINS = "plugins"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
    
    async def save_run(self, run: RunState) -> None:
        await self._db[self.RUNS].replace_one(
            {"id": run.id},
            {
                "id": run.id,
                "status": run.status.to_dict(),
                "config": run.config,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            upsert=True
        )
    
    async def get_job(self, job_id: str) -> Optional[JobState]:
        doc = await self._db[self.JOBS].find_one({"job_id": job_id})
        if not doc:
            return None
        
        plugins = {}
        async for pdoc in self._db[self.PLUGINS].find({"job_id": job_id}):
            plugins[pdoc["plugin_name"]] = pdoc["data"]
        
        return JobState.from_dict(doc, plugins)
```

---

## 6. MOCK PERSISTENCE

```python
class MockPersistence(PersistenceInterface):
    """File-based mock for testing without MongoDB"""
    
    def __init__(self, data_dir: Path):
        self._dir = data_dir
        self._runs: Dict[str, Dict] = {}
        self._jobs: Dict[str, Dict] = {}
        self._plugins: Dict[str, Dict] = {}
    
    def save_run(self, run: RunState) -> None:
        self._runs[run.id] = run.to_dict()
        self._write_file()
    
    def save_job(self, job: JobState) -> None:
        self._jobs[job.job_id] = job.to_dict()
        self._write_file()
    
    def _write_file(self) -> None:
        data = {
            "runs": self._runs,
            "jobs": self._jobs,
            "plugins": self._plugins
        }
        with open(self._dir / "state.json", "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def flush(self) -> None:
        self._write_file()
```

---

## 7. CONNECTION FACTORY

```python
class DatabaseConnection:
    """Factory for database connections"""
    
    @classmethod
    def from_env(cls) -> 'DatabaseConnection':
        return cls(
            uri=os.environ.get('MONGODB_URI', 'mongodb://localhost:27017'),
            database=os.environ.get('MONGODB_DATABASE', 'archiverr')
        )
    
    def __init__(self, uri: str, database: str):
        self._uri = uri
        self._database = database
        self._client = None
    
    def connect_sync(self) -> PyMongoPersistence:
        """For CLI usage"""
        from pymongo import MongoClient
        self._client = MongoClient(self._uri)
        db = self._client[self._database]
        return PyMongoPersistence(db)
    
    async def connect_async(self) -> MotorPersistence:
        """For API usage"""
        from motor.motor_asyncio import AsyncIOMotorClient
        self._client = AsyncIOMotorClient(self._uri)
        db = self._client[self._database]
        return MotorPersistence(db)
    
    def connect_mock(self, data_dir: Path) -> MockPersistence:
        """For testing"""
        return MockPersistence(data_dir)
    
    def disconnect(self) -> None:
        if self._client:
            self._client.close()
```

---

## 8. WRITE STRATEGIES

### 8.1 Write-Through (Default)

```
Operation                MongoDB Write
────────────────────────────────────────
register_job()      →    jobs.insert()
update_plugin()     →    plugins.upsert()
complete_job()      →    jobs.update()
complete_run()      →    runs.update()

Pros: Data safety, crash recovery
Cons: More I/O operations
```

### 8.2 Write-Back (Performance)

```
Operation                Memory          Background
────────────────────────────────────────────────────────
register_job()      →    _jobs[id]       (queue)
update_plugin()     →    _plugins[id]    (queue)
complete_job()      →    _jobs[id]       flush_job()
complete_run()      →    _runs[id]       flush_all()

Pros: Less I/O, faster
Cons: Data loss risk on crash
```

### 8.3 Implementation

```python
class BufferedPersistence:
    """Write-back persistence with buffering"""
    
    def __init__(self, backend: PersistenceInterface, flush_threshold: int = 100):
        self._backend = backend
        self._threshold = flush_threshold
        self._buffer: List[Callable] = []
    
    def save_job(self, job: JobState) -> None:
        self._buffer.append(lambda: self._backend.save_job(job))
        self._maybe_flush()
    
    def _maybe_flush(self) -> None:
        if len(self._buffer) >= self._threshold:
            self.flush()
    
    def flush(self) -> None:
        for op in self._buffer:
            op()
        self._buffer.clear()
```

---

## 9. QUERY EXAMPLES

```python
# Get run with all jobs
def get_run_with_jobs(run_id: str) -> Dict:
    run = db.runs.find_one({"id": run_id})
    jobs = list(db.jobs.find({"run_id": run_id}).sort("index", 1))
    
    for job in jobs:
        plugins = list(db.plugins.find({"job_id": job["job_id"]}))
        job["plugins"] = {p["plugin_name"]: p["data"] for p in plugins}
    
    run["jobs"] = jobs
    return run

# Get recent runs
def get_recent_runs(limit: int = 10) -> List[Dict]:
    return list(
        db.runs
        .find({"status.state": "completed"})
        .sort("created_at", -1)
        .limit(limit)
    )

# Search jobs by path
def search_jobs_by_path(pattern: str) -> List[Dict]:
    return list(
        db.jobs.find({
            "input.path": {"$regex": pattern, "$options": "i"}
        })
    )
```

---

## 10. MEVCUT vs YENİ

### Collection Names

```
Mevcut              Yeni
──────────────────────────
executions      →   runs
matches         →   jobs  
plugin_results  →   plugins
```

### Document Structure

```javascript
// Mevcut (flat)
{
  index: 0,
  input_path: "/file.mkv",
  success: true,
  started_at: "...",
  finished_at: "..."
}

// Yeni (nested)
{
  index: 0,
  input: {
    path: "/file.mkv",
    category: "movie"
  },
  status: {
    success: true,
    started_at: ISODate,
    finished_at: ISODate
  }
}
```

---

**Son Güncelleme:** 2025-11-30
