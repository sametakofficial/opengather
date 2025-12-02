# STATE STRUCTURE & NAMING

```yaml
date: 2025-11-30
sources: v1, v2, v3, v5, v5-part2
status: final
```

---

## 1. TERMİNOLOJİ KARARLARI

| Eski | Yeni | Kod Değişikliği |
|------|------|-----------------|
| `ExecutionState` | `RunState` | Class rename |
| `MatchState` | `JobState` | Class rename |
| `matches` | `jobs` | Field rename |
| `execution` | `run` | Context key |
| `match` | `job` | Context key |
| `not_supported` | `skipped` | Enum value |

**Not:** Eski terimler tamamen kaldırılıyor. Henüz published
olmadığımız için backward compatibility gereksiz.

---

## 2. NESTED STATE YAPISI

### 2.1 RunState (eski: ExecutionState)

```
RunState
├── id: str                          # "run_abc123"
├── status: RunStatus
│   ├── success: bool
│   ├── total_jobs: int
│   ├── completed: int
│   ├── failed: int
│   ├── started_at: datetime
│   ├── finished_at: datetime
│   └── duration_ms: int
└── config: Dict                     # Frozen config snapshot
```

### 2.2 JobState (eski: MatchState)

```
JobState
├── index: int                       # 0-based, in-memory
├── job_id: str                      # "job_{run_id}_{index}"
├── run_id: str                      # Parent reference
├── input: JobInput
│   ├── path: str
│   ├── category: str                # movie/show/unknown
│   └── virtual: bool
├── status: JobStatus
│   ├── success: bool
│   ├── executed_plugins: List[str]
│   ├── failed_plugins: List[str]
│   ├── skipped_plugins: List[str]   # eski: not_supported
│   ├── started_at: datetime
│   ├── finished_at: datetime
│   └── duration_ms: int
├── output: JobOutput
│   └── tasks: List[TaskResult]
└── plugins: Dict[str, PluginData]   # plugin_name -> data
```

---

## 3. HYBRID ID SİSTEMİ

```
┌─────────────────────────────────────────────────────────────┐
│                    JOB IDENTIFICATION                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  index: int                                                  │
│  ├── Scope: Single run                                       │
│  ├── Range: 0 to N-1                                         │
│  ├── Use: In-memory access, iteration                        │
│  └── Example: 0, 1, 2, ...                                   │
│                                                              │
│  job_id: str                                                 │
│  ├── Scope: Global unique                                    │
│  ├── Format: "job_{run_id}_{index}"                          │
│  ├── Use: MongoDB, cross-reference, logging                  │
│  └── Example: "job_run_abc123_0"                             │
│                                                              │
│  MongoDB _id: ObjectId                                       │
│  ├── Scope: Database internal                                │
│  ├── Generated: By MongoDB                                   │
│  └── Use: Never exposed to application                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. TEMPLATE CONTEXT

### 4.1 Context Structure

```python
context = {
    # State access
    'run': RunState.to_dict(),
    'job': current_job.to_dict(),
    'jobs': [j.to_dict() for j in all_jobs],
    
    # Config access
    'options': config.get('options', {}),
    
    # Short aliases
    'r': context['run'],
    'j': context['job'],
    'o': context['options'],
}
```

### 4.2 Template Erişim Örnekleri

```jinja2
{# Run bilgisi #}
{{ run.id }}
{{ run.status.total_jobs }}

{# Current job #}
{{ job.index }}
{{ job.input.path }}
{{ job.plugins.tmdb.movie.title }}

{# Short alias kullanımı #}
{{ j.plugins.renamer.parsed.movie.name }}

{# Custom alias (Jinja2 set) #}
{% set m = job.plugins.tmdb.movie %}
{{ m.title }} ({{ m.release_date[:4] }})

{# All jobs (summary) #}
{% for j in jobs %}
  {{ j.index }}: {{ j.plugins.tmdb.movie.title }}
{% endfor %}
```

---

## 5. STATE MANAGER API

```python
class StateManager:
    _current_run: Optional[RunState]
    _jobs: Dict[int, JobState]       # index -> JobState
    _job_id_map: Dict[str, int]      # job_id -> index
    
    # Run lifecycle
    def start_run(self, config: Dict) -> str:
        """Create new run, return run_id"""
    
    def complete_run(self) -> None:
        """Mark run as completed"""
    
    # Job lifecycle
    def register_job(self, index: int, input_path: str) -> JobState:
        """Create new job, emit event, return state"""
    
    def complete_job(self, index: int) -> None:
        """Mark job completed, emit event"""
    
    # Job access
    def get_job(self, index: int) -> JobState:
        """Get by index (fast, in-memory)"""
    
    def get_job_by_id(self, job_id: str) -> JobState:
        """Get by job_id (lookup)"""
    
    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs (sorted by index)"""
    
    # Plugin results
    def update_plugin(self, index: int, name: str, result: PluginResult):
        """Update plugin result for job"""
    
    # Context
    def get_context(self, job_index: Optional[int] = None) -> Dict:
        """Build template context"""
```

---

## 6. DATACLASS IMPLEMENTATION

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

class JobStatusEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class JobInput:
    path: str
    category: str = "unknown"
    virtual: bool = False

@dataclass
class JobStatus:
    state: JobStatusEnum = JobStatusEnum.PENDING
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
    type: str                        # print, save
    success: bool
    rendered: Optional[str] = None
    destination: Optional[str] = None
    error: Optional[str] = None

@dataclass
class JobOutput:
    tasks: List[TaskResult] = field(default_factory=list)

@dataclass
class JobState:
    index: int
    run_id: str
    job_id: str = ""
    input: JobInput = field(default_factory=lambda: JobInput(""))
    status: JobStatus = field(default_factory=JobStatus)
    output: JobOutput = field(default_factory=JobOutput)
    plugins: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.job_id:
            self.job_id = f"job_{self.run_id}_{self.index}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'job_id': self.job_id,
            'input': {
                'path': self.input.path,
                'category': self.input.category,
                'virtual': self.input.virtual
            },
            'status': {
                'state': self.status.state.value,
                'success': self.status.success,
                'executed_plugins': self.status.executed_plugins,
                'failed_plugins': self.status.failed_plugins,
                'skipped_plugins': self.status.skipped_plugins,
                'started_at': self.status.started_at.isoformat() if self.status.started_at else None,
                'finished_at': self.status.finished_at.isoformat() if self.status.finished_at else None,
                'duration_ms': self.status.duration_ms
            },
            'output': {
                'tasks': [
                    {
                        'name': t.name,
                        'type': t.type,
                        'success': t.success,
                        'rendered': t.rendered,
                        'destination': t.destination,
                        'error': t.error
                    }
                    for t in self.output.tasks
                ]
            },
            'plugins': self.plugins
        }
```

---

## 7. EVENTBUS INTEGRATION

```
State Change           Event Emitted              Payload
────────────────────────────────────────────────────────────
start_run()         → run.started              {run_id, config}
complete_run()      → run.completed            {run_id, stats}
register_job()      → job.started              {run_id, index, job_id, path}
complete_job()      → job.completed/failed     {run_id, index, job_id, success}
update_plugin()     → plugin.completed/failed  {run_id, index, plugin_name}
```

---

## 8. MEVCUT KOD vs YENİ KOD

### Mevcut (state/models.py)

```python
@dataclass
class MatchState:
    index: int
    input_path: str
    execution_id: str
    success: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    # ... flat fields
```

### Yeni

```python
@dataclass
class JobState:
    index: int
    run_id: str
    job_id: str = ""
    input: JobInput = field(default_factory=...)
    status: JobStatus = field(default_factory=...)
    output: JobOutput = field(default_factory=...)
    plugins: Dict[str, Any] = field(default_factory=dict)
```

**Değişiklik Özeti:**
- `input_path: str` → `input: JobInput`
- `success: bool` → `status.success: bool`
- `execution_id` → `run_id`
- `+job_id` field eklendi
- Nested dataclasses

---

## 9. TEST CASES

```python
def test_job_id_generation():
    job = JobState(index=5, run_id="run_abc")
    assert job.job_id == "job_run_abc_5"

def test_to_dict_nested():
    job = JobState(
        index=0,
        run_id="run_123",
        input=JobInput(path="/file.mkv", category="movie")
    )
    d = job.to_dict()
    assert d['input']['path'] == "/file.mkv"
    assert d['input']['category'] == "movie"

def test_state_manager_dual_access():
    sm = StateManager()
    sm.start_run({})
    job = sm.register_job(0, "/file.mkv")
    
    # By index
    assert sm.get_job(0) is job
    
    # By job_id
    assert sm.get_job_by_id(job.job_id) is job
```

---

**Son Güncelleme:** 2025-11-30
