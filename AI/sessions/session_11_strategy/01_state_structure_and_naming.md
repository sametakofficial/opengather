# STATE MODEL

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/06_STATE_MODEL.md
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- input.path -> input.value (virtual file destegi)
- input.data eklendi (size_bytes, source, etc.)
- output.paths -> output.values
- output.data eklendi (task results)
- jobs:{} run icinden ayrildi, ayri collection
- plugins ayri collection (memory management)
```

---

## 1. TERMINOLOJI

```
+----------------------------------------------------------+
|              TERMINOLOJI KARARLARI                        |
+----------------------------------------------------------+
|                                                           |
|  ESKI              YENI              GEREKCE              |
|  ----              ----              -------              |
|  ExecutionState    RunState          "Run" daha net       |
|  MatchState        JobState          Endustri standardi   |
|  execution         run               Airflow, Jenkins     |
|  match             job               GitLab CI pattern    |
|  execution_id      run_id            Tutarlilik           |
|  not_supported     skipped           Daha aciklayici      |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. STATE HIERARCHY

```
RunState
|
+-- id: str                    "run_abc123"
+-- status: RunStatus
|     +-- state: enum          pending|running|completed|failed
|     +-- success: bool
|     +-- total_jobs: int
|     +-- completed: int
|     +-- failed: int
|     +-- started_at: datetime
|     +-- finished_at: datetime
|     +-- duration_ms: int
+-- config: Dict               Frozen snapshot
|
+-- jobs: Dict[int, JobState]
      |
      +-- [0]: JobState
      |     +-- id: str        "job_abc123_0"
      |     +-- index: int     0
      |     +-- run_id: str    "run_abc123"
      |     +-- input: InputData
      |     |     +-- path: str
      |     |     +-- category: str
      |     +-- plugins: Dict[str, Any]
      |     |     +-- scanner: {...}
                        _state
                        movie
                            title
                            year
                        cast
                        crew
                        etc.
      |     |     +-- renamer: {...}
      |     |     +-- tmdb: {...}
      |     +-- status: JobStatus
      |           +-- state: enum
      |           +-- success: bool
      |           +-- executed: List[str]
      |           +-- failed: List[str]
      |           +-- skipped: List[str]
      |
      +-- [1]: JobState
      +-- [2]: JobState
      ...
```

---

## 3. PLUGINS STRUCTURE

```
+----------------------------------------------------------+
|              PLUGINS STRUCTURE (FLAT)                     |
+----------------------------------------------------------+
|                                                           |
|  REDDEDILEN (Nested by stage):                           |
|  plugins:                                                 |
|    input:                                                |
|      scanner: {...}                                      |
|    parse:                                                |
|      renamer: {...}                                      |
|                                                           |
|  KABUL EDILEN (Flat):                                    |
|  plugins:                                                 |
|    scanner: {...}                                        |
|    renamer: {...}                                        |
|    tmdb: {...}                                           |
|                                                           |
|  GEREKCE:                                                |
|  - Template erisimi kolay: job.plugins.tmdb.movie        |
|  - Stage bilgisi manifest'te, state'te gereksiz          |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. HYBRID ID SISTEMI

```
+----------------------------------------------------------+
|              JOB IDENTIFICATION                           |
+----------------------------------------------------------+
|                                                           |
|  index: int                                               |
|  - Scope: Single run                                     |
|  - Range: 0 to N-1                                       |
|  - Use: In-memory access, iteration                      |
|  - Fast: O(1) dict lookup                                |
|                                                           |
|  job_id: str                                              |
|  - Scope: Global unique                                  |
|  - Format: "job_{run_id}_{index}"                        |
|  - Use: MongoDB, logging, cross-reference                |
|  - Traceable: Her job benzersiz ID'ye sahip              |
|                                                           |
+----------------------------------------------------------+

KULLANIM:
  # In-memory (fast)
  job = state.get_job(index=0)

  # Cross-reference (traceable)
  job = state.get_job_by_id("job_abc123_0")
```

---

## 5. DATACLASS IMPLEMENTATION

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

@dataclass
class InputData:
    # v2: path -> value (virtual file destegi)
    value: str                    # /path veya "The Matrix 1999" veya "tmdb://movie/603"
    data: Dict[str, Any] = field(default_factory=dict)  # v2: eklendi
    # data icerigi:
    #   filename: str
    #   extension: str
    #   size_bytes: int
    #   modified_at: datetime
    #   source: str (filesystem|api|manual)

@dataclass
class JobStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

@dataclass
class OutputData:
    # v2: output yapisi eklendi
    values: List[str] = field(default_factory=list)  # output paths
    data: Dict[str, Any] = field(default_factory=dict)  # task results

@dataclass
class JobState:
    index: int
    run_id: str
    id: str = ""
    input: InputData = field(default_factory=lambda: InputData(""))
    output: OutputData = field(default_factory=OutputData)  # v2: eklendi
    status: JobStatus = field(default_factory=JobStatus)
    # v2: plugins ayri collection'da (memory management)

    def __post_init__(self):
        if not self.id:
            self.id = f"job_{self.run_id}_{self.index}"

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
    id: str
    status: RunStatus = field(default_factory=RunStatus)
    config: Dict[str, Any] = field(default_factory=dict)
    # v2: jobs:{} kaldirildi, ayri collection
    # v2: plugins ayri collection (memory management)
```

**Uyari:** Ornek kod, direkt kopyalanmaz. Mevcut codebase ile uyumlu sekilde yeniden yazilmalidir.

---

## 6. TEMPLATE CONTEXT

```
+----------------------------------------------------------+
|              TEMPLATE CONTEXT BUILD                       |
+----------------------------------------------------------+
|                                                           |
|  context = {                                             |
|      # State access                                      |
|      'run': run_state.to_dict(),                         |
|      'job': current_job.to_dict(),                       |
|      'jobs': [j.to_dict() for j in all_jobs],            |
|                                                           |
|      # Config access                                     |
|      'options': config.get('options', {}),               |
|                                                           |
|      # Short aliases (sistem tarafindan)                 |
|      'r': run_state.to_dict(),                           |
|      'j': current_job.to_dict(),                         |
|  }                                                       |
|                                                           |
+----------------------------------------------------------+
```

### Template Erisim Ornekleri

```jinja2
{# Run bilgisi #}
{{ run.id }}
{{ run.status.total_jobs }}

{# Job bilgisi #}
{{ job.index }}
{{ job.input.path }}
{{ job.input.category }}

{# Plugin data (flat) #}
{{ job.plugins.tmdb.movie.title }}
{{ job.plugins.renamer.parsed.movie.name }}

{# Kisa alias #}
{{ j.plugins.tmdb.movie.title }}

{# Custom alias (Jinja2 set) #}
{% set m = job.plugins.tmdb.movie %}
{{ m.title }} ({{ m.release_date[:4] }})

{# Tum job'lar #}
{% for j in jobs %}
  {{ j.index }}: {{ j.plugins.tmdb.movie.title }}
{% endfor %}
```

---

## 7. STATE MANAGER API

```python
class StateManager:
    def __init__(self, event_bus, persistence):
        self._event_bus = event_bus
        self._persistence = persistence
        self._run: Optional[RunState] = None
        self._jobs: Dict[int, JobState] = {}

    # Run lifecycle
    def start_run(self, config: Dict) -> str:
        """Yeni run baslat, run_id dondur"""

    def complete_run(self) -> RunState:
        """Run'i tamamla"""

    # Job lifecycle
    def create_job(self, path: str, category: str = "unknown") -> JobState:
        """Yeni job olustur"""

    def get_job(self, index: int) -> Optional[JobState]:
        """Index ile job getir"""

    def get_job_by_id(self, job_id: str) -> Optional[JobState]:
        """ID ile job getir"""

    def get_all_jobs(self) -> List[JobState]:
        """Tum job'lari getir"""

    def complete_job(self, index: int) -> None:
        """Job'u tamamla"""

    # Plugin results
    def update_plugin(self, index: int, plugin: str, data: Dict) -> None:
        """Plugin sonucunu kaydet"""

    # Template context
    def build_context(self, index: int) -> Dict:
        """Template context olustur"""
```

**Uyari:** API referansi, execution session'da mevcut codebase'e gore uyarlanmalidir.

---

## 8. EVENT EMISSION

```
+----------------------------------------------------------+
|  STATE CHANGE              EVENT                          |
+----------------------------------------------------------+
|                                                           |
|  start_run()           --> run.started                   |
|                            {run_id, config_keys}         |
|                                                           |
|  complete_run()        --> run.completed                 |
|                            {run_id, stats}               |
|                                                           |
|  create_job()          --> job.created                   |
|                            {run_id, job_id, index, path} |
|                                                           |
|  complete_job()        --> job.completed                 |
|                            {run_id, job_id, success}     |
|                                                           |
|  update_plugin()       --> plugin.completed              |
|                            {job_id, plugin, success}     |
|                                                           |
+----------------------------------------------------------+
```

---

## 9. MONGODB MAPPING

```
              MONGODB COLLECTIONS

runs
|-- _id: ObjectId
|-- run_id: "run_abc123"
|-- status: {...}
|-- config: {...}
|-- created_at: ISODate
|-- updated_at: ISODate

jobs
|-- _id: ObjectId
|-- job_id: "job_abc123_0"
|-- run_id: "run_abc123"
|-- index: 0
|-- input: {path, category}
|-- status: {...}
|-- created_at: ISODate
|-- updated_at: ISODate

plugin_results
|-- _id: ObjectId
|-- job_id: "job_abc123_0"
|-- plugin: "tmdb"
|-- data: {...}
|-- success: true
|-- duration_ms: 1234
|-- created_at: ISODate
```

---

## 10. MEVCUT vs YENI

```
MEVCUT (state/models.py):
  @dataclass
  class MatchState:
      index: int
      input_path: str
      execution_id: str
      plugins: Dict[str, PluginResult]

YENI:
  @dataclass
  class JobState:
      index: int
      run_id: str
      id: str                    # job_run123_0
      input: InputData           # nested
      plugins: Dict[str, Any]    # flat
      status: JobStatus          # nested

DEGISIKLIKLER:
  - MatchState -> JobState
  - execution_id -> run_id
  - input_path -> input.path (nested)
  - +job_id (unique identifier)
  - Flat plugins structure
```

---

**Son Guncelleme:** 2025-12-02
