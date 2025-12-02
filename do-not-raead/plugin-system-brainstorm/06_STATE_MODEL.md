# STATE MODEL - RUN AND JOB

```yaml
date: 2025-12-02
type: technical-spec
status: final
```

---

## 1. CURRENT STATE

```python
# state/models.py (existing)
@dataclass
class ExecutionState:
    id: str
    started_at: datetime
    status: ExecutionStatus
    config_snapshot: Dict
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    # ...

@dataclass
class MatchState:
    index: int
    input_path: str
    execution_id: str
    success: bool = True
    # ...
```

**Problems:**
- `ExecutionState` / `MatchState` naming inconsistent with new terminology
- Flat structure, not nested
- No clear separation of input/status/output

---

## 2. PROPOSED TERMINOLOGY

```
OLD           NEW           RATIONALE
--------------------------------------------------------------------
Execution     Run           Shorter, clearer
Match         Job           Industry standard (Jenkins, Airflow)
matches       jobs          Plural form
execution_id  run_id        Consistent
match_index   job_index     Consistent
```

---

## 3. STATE HIERARCHY

```
+------------------------------------------------------------------+
|                        STATE HIERARCHY                            |
+------------------------------------------------------------------+
|                                                                   |
|  Run                                                             |
|    |                                                              |
|    +-- id: str                "run_abc123"                       |
|    +-- status: RunStatus                                         |
|    |     +-- state: enum      running | completed | failed       |
|    |     +-- success: bool                                       |
|    |     +-- started_at: datetime                                |
|    |     +-- finished_at: datetime                               |
|    |     +-- duration_ms: int                                    |
|    +-- stats: RunStats                                           |
|    |     +-- total_jobs: int                                     |
|    |     +-- completed_jobs: int                                 |
|    |     +-- failed_jobs: int                                    |
|    +-- config: Dict          (frozen snapshot)                   |
|    +-- jobs: List[Job]                                           |
|                                                                   |
|  Job                                                             |
|    |                                                              |
|    +-- id: str               "job_abc123_0"                      |
|    +-- run_id: str           (parent reference)                  |
|    +-- index: int            (0-based)                           |
|    +-- input: JobInput                                           |
|    |     +-- path: str                                           |
|    |     +-- category: str   movie | show | unknown              |
|    +-- status: JobStatus                                         |
|    |     +-- state: enum                                         |
|    |     +-- success: bool                                       |
|    |     +-- executed_plugins: List[str]                         |
|    |     +-- failed_plugins: List[str]                           |
|    |     +-- skipped_plugins: List[str]                          |
|    |     +-- started_at: datetime                                |
|    |     +-- finished_at: datetime                               |
|    +-- plugins: Dict[str, PluginData]                            |
|    +-- output: JobOutput                                         |
|          +-- tasks: List[TaskResult]                             |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 4. DATACLASS DEFINITIONS

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class StateEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# RUN STATE
# ============================================================

@dataclass
class RunStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0


@dataclass
class RunStats:
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0


@dataclass
class Run:
    id: str
    status: RunStatus = field(default_factory=RunStatus)
    stats: RunStats = field(default_factory=RunStats)
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'status': {
                'state': self.status.state.value,
                'success': self.status.success,
                'started_at': self.status.started_at.isoformat() if self.status.started_at else None,
                'finished_at': self.status.finished_at.isoformat() if self.status.finished_at else None,
                'duration_ms': self.status.duration_ms,
            },
            'stats': {
                'total_jobs': self.stats.total_jobs,
                'completed_jobs': self.stats.completed_jobs,
                'failed_jobs': self.stats.failed_jobs,
            },
            'config': self.config,
        }


# ============================================================
# JOB STATE
# ============================================================

@dataclass
class JobInput:
    path: str
    category: str = "unknown"


@dataclass
class JobStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed_plugins: List[str] = field(default_factory=list)
    failed_plugins: List[str] = field(default_factory=list)
    skipped_plugins: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0


@dataclass
class TaskResult:
    name: str
    type: str  # print | save
    success: bool
    output: Optional[str] = None  # For print tasks
    destination: Optional[str] = None  # For save tasks
    error: Optional[str] = None


@dataclass
class JobOutput:
    tasks: List[TaskResult] = field(default_factory=list)


@dataclass
class Job:
    id: str
    run_id: str
    index: int
    input: JobInput
    status: JobStatus = field(default_factory=JobStatus)
    plugins: Dict[str, Any] = field(default_factory=dict)
    output: JobOutput = field(default_factory=JobOutput)
    
    @classmethod
    def create(cls, run_id: str, index: int, input_path: str) -> 'Job':
        return cls(
            id=f"job_{run_id}_{index}",
            run_id=run_id,
            index=index,
            input=JobInput(path=input_path)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'run_id': self.run_id,
            'index': self.index,
            'input': {
                'path': self.input.path,
                'category': self.input.category,
            },
            'status': {
                'state': self.status.state.value,
                'success': self.status.success,
                'executed_plugins': self.status.executed_plugins,
                'failed_plugins': self.status.failed_plugins,
                'skipped_plugins': self.status.skipped_plugins,
                'started_at': self.status.started_at.isoformat() if self.status.started_at else None,
                'finished_at': self.status.finished_at.isoformat() if self.status.finished_at else None,
                'duration_ms': self.status.duration_ms,
            },
            'plugins': self.plugins,
            'output': {
                'tasks': [
                    {
                        'name': t.name,
                        'type': t.type,
                        'success': t.success,
                        'output': t.output,
                        'destination': t.destination,
                        'error': t.error,
                    }
                    for t in self.output.tasks
                ]
            }
        }
```

---

## 5. STATE MANAGER API

```
+------------------------------------------------------------------+
|                    STATE MANAGER                                  |
+------------------------------------------------------------------+
|                                                                   |
|  class StateManager:                                             |
|                                                                   |
|      # Run lifecycle                                             |
|      start_run(config: Dict) -> str           # returns run_id   |
|      complete_run() -> Run                    # returns final    |
|      fail_run(error: str) -> Run              # mark as failed   |
|                                                                   |
|      # Job lifecycle                                             |
|      register_job(input_path: str) -> Job     # create job       |
|      complete_job(job_id: str) -> Job         # mark complete    |
|      fail_job(job_id: str, error: str)        # mark failed      |
|                                                                   |
|      # Plugin results                                            |
|      update_plugin(job_id: str, plugin: str, result: Dict)       |
|      skip_plugin(job_id: str, plugin: str, reason: str)          |
|                                                                   |
|      # Task results                                              |
|      add_task_result(job_id: str, result: TaskResult)            |
|                                                                   |
|      # Queries                                                   |
|      get_run() -> Run                                            |
|      get_job(job_id: str) -> Job                                 |
|      get_job_by_index(index: int) -> Job                         |
|      get_all_jobs() -> List[Job]                                 |
|                                                                   |
|      # Template context                                          |
|      build_context(job_id: str) -> Dict                          |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 6. STATE TRANSITIONS

```
RUN STATE TRANSITIONS:

  PENDING ----start_run()----> RUNNING
  RUNNING ----complete_run()-> COMPLETED
  RUNNING ----fail_run()-----> FAILED


JOB STATE TRANSITIONS:

  PENDING ----register_job()--> RUNNING
  RUNNING ----complete_job()--> COMPLETED
  RUNNING ----fail_job()------> FAILED
```

```
+------+     start     +-------+    complete    +-----------+
|PENDING|------------>|RUNNING|--------------->|COMPLETED  |
+------+              +-------+                +-----------+
                          |
                          | fail
                          v
                      +------+
                      |FAILED|
                      +------+
```

---

## 7. TEMPLATE CONTEXT STRUCTURE

```python
def build_context(self, job_id: str) -> Dict:
    """Build Jinja2 template context for a job"""
    job = self.get_job(job_id)
    run = self.get_run()
    
    return {
        # Primary access
        'run': run.to_dict(),
        'job': job.to_dict(),
        'jobs': [j.to_dict() for j in self.get_all_jobs()],
        
        # Short aliases
        'r': run.to_dict(),
        'j': job.to_dict(),
        
        # Options shortcut
        'options': run.config.get('options', {}),
        'o': run.config.get('options', {}),
        
        # Index shortcut
        'index': job.index,
    }
```

Template usage:
```jinja2
{# Full path #}
{{ job.plugins.tmdb.movie.title }}

{# With alias #}
{% set m = job.plugins.tmdb.movie %}
{{ m.title }} ({{ m.release_date[:4] }})

{# Options #}
{{ options.movies_dst }}/{{ m.title }}
```

---

## 8. PERSISTENCE SCHEMA

```
MongoDB Collections:

  runs
    _id: ObjectId
    id: "run_abc123"
    status: {...}
    stats: {...}
    config: {...}
    created_at: ISODate
    updated_at: ISODate

  jobs
    _id: ObjectId
    id: "job_abc123_0"
    run_id: "run_abc123"
    index: 0
    input: {...}
    status: {...}
    plugins: {...}
    output: {...}
    created_at: ISODate
    updated_at: ISODate

Indexes:
  runs: {id: 1} unique
  jobs: {id: 1} unique
  jobs: {run_id: 1, index: 1}
```

---

## 9. BACKWARD COMPATIBILITY

```python
# Aliases for gradual migration

# Old names still work
ExecutionState = Run
MatchState = Job

# StateManager methods
class StateManager:
    # Old API (deprecated)
    def start_execution(self, config):
        return self.start_run(config)
    
    def register_match(self, index, path):
        return self.register_job(path)
    
    def complete_match(self, index):
        job = self.get_job_by_index(index)
        return self.complete_job(job.id)
    
    # New API (preferred)
    def start_run(self, config): ...
    def register_job(self, input_path): ...
    def complete_job(self, job_id): ...
```

---

## CHANGELOG

```
- Renamed: ExecutionState -> Run
- Renamed: MatchState -> Job
- Renamed: execution_id -> run_id
- Renamed: match_index -> job_index (internal)
- Added: Nested dataclasses (RunStatus, JobInput, etc.)
- Added: StateEnum for consistent state values
- Added: Job.create() factory method
- Added: to_dict() methods for serialization
```

---

**Status: FINAL - Ready for implementation**
