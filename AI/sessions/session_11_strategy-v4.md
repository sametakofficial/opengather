# SESSION 11 STRATEGY v4 - PLUGIN FREEDOM ARCHITECTURE

```yaml
date: 2025-11-28
type: strategy
status: draft
previous_session: 11-v3
focus: Category-Free Plugins, Global Matches State, Universal Response Requirement
analyst: Strategy Chat + Industry Research
```

---

## ENDÜSTRİ ARAŞTIRMASI

### Referans Sistemler

| Sistem | Terminoloji | Öğrendiklerimiz |
|--------|-------------|-----------------|
| **Apache Airflow** | DAG, Task, Task Instance, Operator | Task states: `none`, `scheduled`, `queued`, `running`, `success`, `failed`, `skipped`, `upstream_failed` |
| **Temporal.io** | Workflow, Activity, Task Queue, Worker | Task Queue naming best practices, worker polling pattern |
| **XState** | State Machine, State, Event, Action, Guard | Naming: States=nouns, Events=verbs, Actions=verb phrases |
| **Netflix Maestro** | Workflow, Job, Execution | Millions of daily executions, job orchestration |

### Standart Terminoloji Karşılaştırması

| Bizim (v3) | Endüstri Standardı | v4 Önerisi |
|------------|-------------------|------------|
| `execution` | ✅ Workflow Execution (Temporal) | `run` veya `execution` (her ikisi de valid) |
| `match` | ⚠️ Belirsiz | `job` (Airflow/Maestro) veya `item` |
| `depends_on` | ❌ Fazlalık | KALDIRILDI - `requires` yeterli |
| `expects` | ⚠️ Belirsiz | `requires` (daha açık) |
| `not_supported` | ❌ Endüstri dışı | `skipped` (Airflow standardı) |
| `success`/`failed` | ✅ Standart | Korunuyor |
| `executed_plugins` | ⚠️ Uzun | `completed` |
| `failed_plugins` | ⚠️ Uzun | `failed` |

---

## v3 → v4 DEĞİŞİKLİK TABLOSU

| Konu | v3 | v4 |
|------|----|----|
| **Plugin kategorisi** | `input`/`output` zorunlu | Kategori YOK - servisler belirler |
| **Bağımlılık alanı** | `depends_on` + `expects` | Sadece `requires` |
| **Plugin data yapısı** | `movie: {...}` | `tmdb: {...}`, `tvdb: {...}` |
| **Output task organizasyonu** | `tasks: [{type: "print"}]` | `tasks: [{type: "print"}]` (type indexed) |
| **Match oluşturma** | Input plugin zorunlu | Herhangi bir plugin match oluşturabilir |
| **Plugin response** | Optional | Tüm pluginler response vermeli (`skipped` dahil) |
| **not_supported** | Var | `skipped` olarak değişti |
| **Match hedefleme** | Sistem atar | Plugin seçer (global matches state) |

---

## YENİ PLUGIN SİSTEMİ

### Temel Felsefe

```
ESKİ: Pluginler kategorilere ayrılır, sistem onları sırayla çağırır
YENİ: Pluginler özgürdür, hangi matche ne göndereceğine kendileri karar verir
```

### Plugin Manifest v4

```yaml
# Örnek: scanner/manifest.yml
name: scanner
version: 1.0.0
description: Scans filesystem for media files

# KALDIRILDI: category (input/output yok artık)
# KALDIRILDI: depends_on

# YENİ: Sadece requires - bu plugin çalışmadan önce kimin bitmesi gerekiyor?
requires: []  # Boş = herhangi bir dependency yok

# Plugin hangi medya türlerini destekliyor (optional, documentation amaçlı)
supports:
  - movie
  - show
```

```yaml
# Örnek: tmdb/manifest.yml
name: tmdb
version: 1.0.0
description: Fetches metadata from TMDB API

requires:
  - renamer  # renamer'ın parse ettiği veri lazım

supports:
  - movie
  - show
```

```yaml
# Örnek: renamer/manifest.yml
name: renamer
version: 1.0.0
description: Parses media file names to extract metadata

requires: []  # Bağımsız - her matche bakabilir

supports:
  - movie
  - show
```

### Plugin Servisleri (SDK Yerine)

Plugin geliştiricileri iki servis kullanabilir:

```python
# src/archiverr/plugins/services.py

class InputService:
    """Service for plugins that produce matches"""
    
    def create_job(self, path: str, metadata: dict = None) -> Job:
        """
        Create a new job (match) in the global state.
        
        Args:
            path: File/directory path
            metadata: Optional initial metadata
            
        Returns:
            Created Job object with unique index
        """
        pass
    
    def get_jobs(self, filter: dict = None) -> List[Job]:
        """
        Get all jobs, optionally filtered.
        
        Args:
            filter: Optional filter criteria
            
        Returns:
            List of Job objects
        """
        pass


class OutputService:
    """Service for plugins that produce output"""
    
    def emit(self, job_index: int, task_type: str, content: str, metadata: dict = None):
        """
        Emit output for a specific job.
        
        Args:
            job_index: Target job index
            task_type: 'print', 'save', 'notify', etc.
            content: Rendered content
            metadata: Optional task metadata
        """
        pass
    
    def emit_batch(self, tasks: List[dict]):
        """Emit multiple outputs at once"""
        pass
```

### Plugin Base Class v4

```python
# src/archiverr/plugins/base.py

from abc import ABC, abstractmethod
from typing import List, Optional
from .services import InputService, OutputService

class PluginResponse:
    """Standard response from plugin execution"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Airflow standardı
    
    def __init__(self, status: str, data: dict = None, reason: str = None):
        self.status = status
        self.data = data or {}
        self.reason = reason  # skipped ise neden


class BasePlugin(ABC):
    """
    Base class for all plugins.
    
    NO CATEGORIES - plugins use services as needed.
    ALL plugins MUST respond to ALL jobs (at least with 'skipped').
    """
    
    def __init__(self):
        self.input_service: Optional[InputService] = None
        self.output_service: Optional[OutputService] = None
        self._manifest: dict = {}
    
    @property
    def name(self) -> str:
        return self._manifest.get('name', self.__class__.__name__)
    
    @property
    def requires(self) -> List[str]:
        """Dependencies - plugins that must complete before this one"""
        return self._manifest.get('requires', [])
    
    @abstractmethod
    def process(self, job: 'Job') -> PluginResponse:
        """
        Process a single job.
        
        MUST return one of:
        - PluginResponse(SUCCESS, data={...})
        - PluginResponse(FAILED, reason="...")
        - PluginResponse(SKIPPED, reason="not a movie")
        
        NEVER return None or raise without catching.
        """
        pass
    
    def process_all(self, jobs: List['Job']) -> List[PluginResponse]:
        """
        Process all jobs. Default: iterate and call process().
        Override for batch operations.
        """
        return [self.process(job) for job in jobs]
```

---

## YENİ TERMİNOLOJİ

### v4 İsimlendirme Standardı

| Kavram | v3 İsmi | v4 İsmi | Gerekçe |
|--------|---------|---------|---------|
| Tek çalışma | `execution` | `run` | Daha kısa, Airflow'da "DAG Run" |
| Tek iş birimi | `match` | `job` | Airflow/Netflix standardı |
| Tüm işler | `matches` | `jobs` | Tutarlılık |
| Bağımlılık | `depends_on` / `expects` | `requires` | Tek alan, net anlam |
| Desteklenmiyor | `not_supported` | `skipped` | Airflow standardı |
| Çalıştırılan | `executed_plugins` | `completed` | Kısa |
| Başarısız | `failed_plugins` | `failed` | Kısa |
| Plugin verisi | `plugins.tmdb.movie` | `plugins.tmdb` | Plugin adı = namespace |

### State Terimleri (Airflow Uyumlu)

```python
class JobStatus:
    """Job lifecycle states - Airflow compatible"""
    NONE = "none"           # Henüz kuyruğa alınmadı
    SCHEDULED = "scheduled" # Scheduler onayladı
    QUEUED = "queued"       # Worker bekliyor
    RUNNING = "running"     # İşleniyor
    SUCCESS = "success"     # Başarılı bitti
    FAILED = "failed"       # Hata ile bitti
    SKIPPED = "skipped"     # Atlandı (branch, filter, vb.)
    UPSTREAM_FAILED = "upstream_failed"  # Dependency başarısız


class RunStatus:
    """Run lifecycle states"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"     # Tüm leaf job'lar success/skipped
    FAILED = "failed"       # Herhangi bir leaf job failed
    CANCELLED = "cancelled"
```

---

## YENİ STATE YAPISI

### Global Context (v4)

```python
{
    # 1. RUN - Mevcut çalışma
    'run': {
        'id': 'abc123',
        'status': 'running',  # pending, running, success, failed, cancelled
        'stats': {
            'total_jobs': 2,
            'completed': 1,
            'failed': 0,
            'skipped': 0
        },
        'timing': {
            'started_at': '2025-11-28T12:00:00',
            'finished_at': None,
            'duration_ms': None
        },
        'config': {
            'options': {'debug': True, 'dry_run': True},
            'plugins': {...},
            'tasks': [...]
        }
    },
    
    # 2. JOB - Şu an işlenen job (varsa)
    'job': {
        'index': 0,
        'status': 'running',  # none, scheduled, queued, running, success, failed, skipped
        'input': {
            'path': '/path/to/file.mkv',
            'type': 'movie',  # movie, show, unknown
            'virtual': False
        },
        'timing': {
            'started_at': '...',
            'finished_at': None,
            'duration_ms': None
        },
        'output': {
            'tasks': [
                {
                    'name': 'print_header',
                    'type': 'print',  # print, save, notify, etc.
                    'status': 'success',
                    'content': '...'
                }
            ]
        },
        'plugins': {
            # Her plugin kendi namespace'inde
            'scanner': {
                'status': 'success',
                'data': {
                    'files': [...],
                    'size_bytes': 1234567
                }
            },
            'renamer': {
                'status': 'success',
                'data': {
                    'title': 'Mr. & Mrs. Smith',
                    'year': 2005,
                    'quality': '1080p'
                }
            },
            'tmdb': {
                'status': 'success',
                'data': {
                    'id': 1234,
                    'title': 'Mr. & Mrs. Smith',
                    'genres': ['Action', 'Comedy'],
                    'poster_path': '/...'
                }
            },
            'tvdb': {
                'status': 'skipped',
                'reason': 'not a TV show'
            }
        }
    },
    
    # 3. JOBS - Tüm job'lar (summary için)
    'jobs': [
        {'index': 0, 'status': 'success', ...},
        {'index': 1, 'status': 'running', ...}
    ]
}
```

### Template Kullanımı (v4)

```jinja2
{# Run bilgisi #}
{{ run.id }}
{{ run.stats.total_jobs }}
{{ run.config.options.debug }}

{# Current job #}
{{ job.index }}
{{ job.input.path }}
{{ job.input.type }}

{# Plugin verileri - HER ZAMAN plugin adı ile #}
{{ job.plugins.tmdb.data.title }}
{{ job.plugins.renamer.data.year }}
{{ job.plugins.scanner.data.files | length }}

{# Skipped plugin kontrolü #}
{% if job.plugins.tvdb.status == 'skipped' %}
  TVDB skipped: {{ job.plugins.tvdb.reason }}
{% endif %}

{# Summary task - tüm job'lara erişim #}
{% for j in jobs %}
  Job {{ j.index }}: {{ j.plugins.renamer.data.title }}
{% endfor %}

{# Filter by status #}
{% for j in jobs if j.status == 'success' %}
  ✓ {{ j.plugins.renamer.data.title }}
{% endfor %}
```

---

## PLUGIN EXECUTION FLOW (v4)

### Yeni Akış

```
┌─────────────────────────────────────────────────────────────────┐
│                         RUN BAŞLAT                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. TÜM ENABLEd PLUGINLERİ YÜKLE                                │
│     - requires grafiği oluştur (dependency graph)               │
│     - topological sort ile execution order belirle              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. GLOBAL JOBS STATE OLUŞTUR (boş başlar)                      │
│     jobs = []                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. PLUGINLERİ SIRAYLA ÇALIŞTIR                                 │
│                                                                 │
│     for plugin in sorted_plugins:                               │
│         # Plugin tüm mevcut job'ları görebilir                  │
│         # İsterse yeni job oluşturabilir (InputService)         │
│         # İsterse mevcut job'lara veri ekleyebilir              │
│         # İsterse output üretebilir (OutputService)             │
│                                                                 │
│         for job in jobs:                                        │
│             response = plugin.process(job)                      │
│             # response MUTLAKA olmalı (success/failed/skipped)  │
│             job.plugins[plugin.name] = response                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. JOB COMPLETION KONTROLÜ                                     │
│                                                                 │
│     for job in jobs:                                            │
│         # Tüm enabled pluginler response verdi mi?              │
│         if all_plugins_responded(job):                          │
│             job.status = calculate_final_status(job)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. RUN COMPLETION                                              │
│                                                                 │
│     if all_jobs_terminal(jobs):                                 │
│         run.status = 'success' if all_success else 'failed'     │
└─────────────────────────────────────────────────────────────────┘
```

### Dependency Resolution

```python
# src/archiverr/core/orchestrator.py

from typing import List, Dict, Set
from collections import defaultdict

def build_execution_order(plugins: Dict[str, BasePlugin]) -> List[str]:
    """
    Topological sort based on 'requires' field.
    
    Example:
        scanner: requires=[]
        renamer: requires=[]
        tmdb: requires=[renamer]
        output: requires=[tmdb, scanner]
        
    Result: [scanner, renamer, tmdb, output]
    """
    # Build dependency graph
    graph = defaultdict(list)
    in_degree = {name: 0 for name in plugins}
    
    for name, plugin in plugins.items():
        for req in plugin.requires:
            if req in plugins:
                graph[req].append(name)
                in_degree[name] += 1
    
    # Kahn's algorithm
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result = []
    
    while queue:
        # Sort for deterministic order
        queue.sort()
        current = queue.pop(0)
        result.append(current)
        
        for neighbor in graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    if len(result) != len(plugins):
        raise ValueError("Circular dependency detected")
    
    return result
```

### Plugin Response Zorunluluğu

```python
# src/archiverr/core/executor.py

class PluginExecutor:
    """Executes plugins and enforces response requirement"""
    
    def execute_plugin(self, plugin: BasePlugin, job: Job) -> PluginResponse:
        """
        Execute plugin for a job.
        ALWAYS returns a valid response.
        """
        try:
            response = plugin.process(job)
            
            # Validate response
            if response is None:
                return PluginResponse(
                    status=PluginResponse.FAILED,
                    reason=f"Plugin {plugin.name} returned None"
                )
            
            if response.status not in [PluginResponse.SUCCESS, 
                                        PluginResponse.FAILED, 
                                        PluginResponse.SKIPPED]:
                return PluginResponse(
                    status=PluginResponse.FAILED,
                    reason=f"Invalid status: {response.status}"
                )
            
            return response
            
        except Exception as e:
            return PluginResponse(
                status=PluginResponse.FAILED,
                reason=str(e)
            )
    
    def verify_all_responded(self, job: Job, enabled_plugins: List[str]) -> bool:
        """Check if all enabled plugins responded to this job"""
        responded = set(job.plugins.keys())
        required = set(enabled_plugins)
        
        missing = required - responded
        if missing:
            logger.warning(f"Job {job.index} missing responses from: {missing}")
            return False
        
        return True
```

---

## MONGODB YAPISI (v4)

### Collection: `runs` (eski: executions)

```javascript
{
  _id: ObjectId("..."),
  id: "abc123",
  branch_id: ObjectId("..."),
  
  status: "success",  // pending, running, success, failed, cancelled
  
  stats: {
    total_jobs: 2,
    completed: 2,
    failed: 0,
    skipped: 0
  },
  
  timing: {
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 60000
  },
  
  config: {
    options: {debug: true, dry_run: true},
    plugins: {
      scanner: {enabled: true, targets: [...]},
      tmdb: {enabled: true, language: "tr-TR"}
    },
    tasks: [...]
  },
  
  created_at: ISODate("...")
}
```

### Collection: `jobs` (eski: matches)

```javascript
{
  _id: ObjectId("..."),
  run_id: "abc123",
  index: 0,
  
  status: "success",  // none, scheduled, queued, running, success, failed, skipped
  
  input: {
    path: "/path/to/file.mkv",
    type: "movie",  // movie, show, unknown
    virtual: false
  },
  
  timing: {
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 2500
  },
  
  output: {
    tasks: [
      {
        name: "print_header",
        type: "print",
        status: "success",
        content: "..."
      },
      {
        name: "save_nfo",
        type: "save",
        status: "success",
        path: "/path/to/movie.nfo"
      }
    ]
  },
  
  // Aggregated plugin statuses for quick queries
  plugin_summary: {
    completed: ["scanner", "renamer", "tmdb"],
    failed: [],
    skipped: ["tvdb"]
  },
  
  created_at: ISODate("...")
}
```

### Collection: `plugins` (değişiklik yok, sadece içerik)

```javascript
{
  _id: ObjectId("..."),
  run_id: "abc123",
  job_index: 0,
  plugin_name: "tmdb",
  
  status: "success",  // success, failed, skipped
  reason: null,       // skipped/failed ise neden
  
  timing: {
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 800
  },
  
  // Plugin-specific data
  data: {
    id: 1234,
    title: "Mr. & Mrs. Smith",
    year: 2005,
    genres: ["Action", "Comedy"],
    poster_path: "/abc123.jpg"
  },
  
  created_at: ISODate("...")
}

// Skipped plugin örneği
{
  _id: ObjectId("..."),
  run_id: "abc123",
  job_index: 0,
  plugin_name: "tvdb",
  
  status: "skipped",
  reason: "Input type is movie, TVDB only supports TV shows",
  
  timing: {
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 5
  },
  
  data: {},  // Boş
  
  created_at: ISODate("...")
}
```

### Indexes

```javascript
// runs collection
db.runs.createIndex({ "id": 1 }, { unique: true })
db.runs.createIndex({ "status": 1, "created_at": -1 })
db.runs.createIndex({ "branch_id": 1, "created_at": -1 })

// jobs collection
db.jobs.createIndex({ "run_id": 1, "index": 1 }, { unique: true })
db.jobs.createIndex({ "run_id": 1, "status": 1 })
db.jobs.createIndex({ "output.tasks.type": 1 })  // Task type'a göre query

// plugins collection
db.plugins.createIndex({ "run_id": 1, "job_index": 1, "plugin_name": 1 }, { unique: true })
db.plugins.createIndex({ "run_id": 1, "status": 1 })
db.plugins.createIndex({ "plugin_name": 1, "status": 1 })
```

---

## OUTPUT TASK ORGANİZASYONU

### Seçenek Analizi

**Seçenek A: Single Array with Type Field (ÖNERİLEN)**
```javascript
output: {
  tasks: [
    {name: "header", type: "print", status: "success", content: "..."},
    {name: "nfo", type: "save", status: "success", path: "..."},
    {name: "slack", type: "notify", status: "success", target: "..."}
  ]
}
```

**Avantajlar:**
- Tek index: `output.tasks.type`
- Yeni task type eklemek schema değişikliği gerektirmez
- Tüm task'ları tek sorguda çekebilirsin

**Dezavantajlar:**
- Type'a göre filtreleme gerekli

---

**Seçenek B: Separate Arrays by Type**
```javascript
output: {
  print: [
    {name: "header", status: "success", content: "..."}
  ],
  save: [
    {name: "nfo", status: "success", path: "..."}
  ],
  notify: [
    {name: "slack", status: "success", target: "..."}
  ]
}
```

**Avantajlar:**
- Doğrudan erişim: `output.print[0]`
- Type filtreleme gerekmiyor

**Dezavantajlar:**
- Yeni type = schema değişikliği
- Her type için ayrı index gerekebilir
- Boş array'ler yer kaplar

---

### Karar: Seçenek A (Single Array)

**Gerekçe:**
1. **Endüstri standardı:** Airflow, Temporal hep single array + type kullanır
2. **Esneklik:** Yeni task type eklemek kolay
3. **MongoDB için optimize:** Tek compound index yeterli
4. **Query örneği:**
   ```javascript
   // Tüm print task'ları
   db.jobs.find({ "output.tasks.type": "print" })
   
   // Belirli job'un save task'ları
   db.jobs.aggregate([
     { $match: { run_id: "abc123", index: 0 } },
     { $project: {
         saves: {
           $filter: {
             input: "$output.tasks",
             as: "task",
             cond: { $eq: ["$$task.type", "save"] }
           }
         }
       }
     }
   ])
   ```

---

## EVENT BUS TASARIMI

### Job Completion Tracking

```python
# src/archiverr/core/events.py

from enum import Enum
from typing import Callable, Dict, List
from dataclasses import dataclass

class EventType(Enum):
    JOB_CREATED = "job.created"
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_SKIPPED = "job.skipped"
    
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_SKIPPED = "plugin.skipped"
    
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


@dataclass
class Event:
    type: EventType
    run_id: str
    job_index: int = None
    plugin_name: str = None
    data: dict = None


class EventBus:
    """Simple synchronous event bus for tracking execution state"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def emit(self, event: Event):
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            handler(event)


class CompletionTracker:
    """Tracks job completion based on plugin responses"""
    
    def __init__(self, event_bus: EventBus, enabled_plugins: List[str]):
        self._event_bus = event_bus
        self._enabled_plugins = set(enabled_plugins)
        self._job_responses: Dict[int, Dict[str, str]] = {}  # job_index -> {plugin: status}
        
        event_bus.subscribe(EventType.PLUGIN_COMPLETED, self._on_plugin_done)
        event_bus.subscribe(EventType.PLUGIN_FAILED, self._on_plugin_done)
        event_bus.subscribe(EventType.PLUGIN_SKIPPED, self._on_plugin_done)
    
    def _on_plugin_done(self, event: Event):
        job_idx = event.job_index
        plugin = event.plugin_name
        
        if job_idx not in self._job_responses:
            self._job_responses[job_idx] = {}
        
        self._job_responses[job_idx][plugin] = event.type.value.split('.')[-1]
        
        # Check if all plugins responded
        responded = set(self._job_responses[job_idx].keys())
        if responded >= self._enabled_plugins:
            self._emit_job_completion(job_idx)
    
    def _emit_job_completion(self, job_index: int):
        responses = self._job_responses[job_index]
        
        # Determine final status (Airflow logic)
        if any(s == 'failed' for s in responses.values()):
            status = EventType.JOB_FAILED
        elif all(s in ['completed', 'skipped'] for s in responses.values()):
            status = EventType.JOB_COMPLETED
        else:
            status = EventType.JOB_COMPLETED
        
        self._event_bus.emit(Event(
            type=status,
            run_id="...",  # from context
            job_index=job_index,
            data={'plugin_responses': responses}
        ))
```

---

## ÖRNEK PLUGIN: Scanner (v4)

```python
# src/archiverr/plugins/scanner/plugin.py

from pathlib import Path
from typing import List
from ..base import BasePlugin, PluginResponse
from ..services import InputService

class ScannerPlugin(BasePlugin):
    """
    Filesystem scanner plugin.
    
    Creates new jobs for each media file found.
    Uses InputService to create jobs.
    """
    
    def __init__(self):
        super().__init__()
        self._manifest = {
            'name': 'scanner',
            'requires': []  # No dependencies
        }
    
    def initialize(self, config: dict):
        """Called once at start with plugin config"""
        self.targets = config.get('targets', [])
        self.extensions = config.get('extensions', ['.mkv', '.mp4', '.avi'])
    
    def process(self, job: 'Job') -> PluginResponse:
        """
        For scanner, process() is called for EXISTING jobs.
        New jobs are created in scan_and_create().
        
        If job already exists (from another source), just skip.
        """
        # Scanner doesn't process existing jobs, it creates new ones
        return PluginResponse(
            status=PluginResponse.SKIPPED,
            reason="Scanner creates jobs, doesn't process them"
        )
    
    def scan_and_create(self) -> List['Job']:
        """
        Scan targets and create jobs.
        Called by orchestrator before main loop.
        """
        jobs = []
        
        for target in self.targets:
            target_path = Path(target)
            
            if target_path.is_file():
                jobs.append(self._create_job_for_file(target_path))
            elif target_path.is_dir():
                for ext in self.extensions:
                    for file_path in target_path.rglob(f'*{ext}'):
                        jobs.append(self._create_job_for_file(file_path))
        
        return jobs
    
    def _create_job_for_file(self, path: Path) -> 'Job':
        """Create a job using InputService"""
        return self.input_service.create_job(
            path=str(path),
            metadata={
                'source': 'scanner',
                'size_bytes': path.stat().st_size,
                'extension': path.suffix
            }
        )
```

---

## ÖRNEK PLUGIN: Renamer (v4)

```python
# src/archiverr/plugins/renamer/plugin.py

import re
from ..base import BasePlugin, PluginResponse

class RenamerPlugin(BasePlugin):
    """
    Parses media file names to extract metadata.
    
    No dependencies - can run on any job.
    """
    
    def __init__(self):
        super().__init__()
        self._manifest = {
            'name': 'renamer',
            'requires': []
        }
    
    def process(self, job: 'Job') -> PluginResponse:
        """Parse filename and extract metadata"""
        path = job.input.get('path', '')
        
        if not path:
            return PluginResponse(
                status=PluginResponse.SKIPPED,
                reason="No path in job input"
            )
        
        try:
            parsed = self._parse_filename(path)
            
            if not parsed:
                return PluginResponse(
                    status=PluginResponse.SKIPPED,
                    reason="Could not parse filename"
                )
            
            return PluginResponse(
                status=PluginResponse.SUCCESS,
                data=parsed
            )
            
        except Exception as e:
            return PluginResponse(
                status=PluginResponse.FAILED,
                reason=str(e)
            )
    
    def _parse_filename(self, path: str) -> dict:
        """Extract title, year, quality from filename"""
        filename = Path(path).stem
        
        # Pattern: Title (Year) [Quality]
        # Example: "Mr. & Mrs. Smith (2005) [1080p]"
        pattern = r'^(.+?)\s*\((\d{4})\)\s*(?:\[(.+?)\])?'
        match = re.match(pattern, filename)
        
        if match:
            return {
                'title': match.group(1).strip(),
                'year': int(match.group(2)),
                'quality': match.group(3) if match.group(3) else None
            }
        
        # Simpler pattern: Title Year
        pattern2 = r'^(.+?)\s+(\d{4})'
        match2 = re.match(pattern2, filename)
        
        if match2:
            return {
                'title': match2.group(1).strip(),
                'year': int(match2.group(2)),
                'quality': None
            }
        
        return None
```

---

## ÖRNEK PLUGIN: TMDB (v4)

```python
# src/archiverr/plugins/tmdb/plugin.py

from ..base import BasePlugin, PluginResponse

class TMDBPlugin(BasePlugin):
    """
    Fetches movie metadata from TMDB API.
    
    Requires: renamer (needs parsed title/year)
    """
    
    def __init__(self):
        super().__init__()
        self._manifest = {
            'name': 'tmdb',
            'requires': ['renamer']  # Need parsed data first
        }
    
    def initialize(self, config: dict):
        self.api_key = config.get('api_key')
        self.language = config.get('language', 'en-US')
    
    def process(self, job: 'Job') -> PluginResponse:
        """Fetch TMDB data using renamer output"""
        
        # Check if renamer ran successfully
        renamer_result = job.plugins.get('renamer', {})
        if renamer_result.get('status') != 'success':
            return PluginResponse(
                status=PluginResponse.SKIPPED,
                reason="Renamer did not succeed"
            )
        
        # Get parsed data from renamer
        parsed = renamer_result.get('data', {})
        title = parsed.get('title')
        year = parsed.get('year')
        
        if not title:
            return PluginResponse(
                status=PluginResponse.SKIPPED,
                reason="No title from renamer"
            )
        
        # Check job type (if we know it's a TV show, skip)
        if job.input.get('type') == 'show':
            return PluginResponse(
                status=PluginResponse.SKIPPED,
                reason="Job is TV show, use TVDB instead"
            )
        
        try:
            # Search TMDB
            result = self._search_movie(title, year)
            
            if not result:
                return PluginResponse(
                    status=PluginResponse.FAILED,
                    reason=f"No TMDB result for: {title} ({year})"
                )
            
            return PluginResponse(
                status=PluginResponse.SUCCESS,
                data=result
            )
            
        except Exception as e:
            return PluginResponse(
                status=PluginResponse.FAILED,
                reason=str(e)
            )
    
    def _search_movie(self, title: str, year: int = None) -> dict:
        """Search TMDB API for movie"""
        # API call implementation
        pass
```

---

## ŞEYTANIN AVUKATLIĞI

### Endişe 1: "Tüm pluginler tüm job'lara response vermek zorunda - overhead?"

**Analiz:**
- Airflow'da da tüm task'lar tüm DAG Run'lar için state tutar
- `skipped` response çok hafif (sadece status + reason)
- MongoDB'de skip edilen pluginler minimal yer kaplar

**Karar:** KABUL - Endüstri standardına uygun, overhead minimal

---

### Endişe 2: "Plugin kategorileri kaldırıldı - chaos olmaz mı?"

**Analiz:**
- `requires` field dependency'leri açıkça belirtir
- Topological sort doğru execution order garanti eder
- Scanner gibi "job oluşturan" pluginler için `scan_and_create()` ayrı metod

**Karar:** KABUL - Daha esnek, `requires` yeterli kontrol sağlıyor

---

### Endişe 3: "`execution` → `run`, `match` → `job` - breaking change çok büyük"

**Analiz:**
- Tüm template'ler güncellenmeli
- MongoDB collection'ları rename edilmeli
- API response'lar değişmeli

**Alternatif:** Alias desteği eklenebilir:
```python
context = {
    'run': {...},
    'execution': context['run'],  # alias
    'job': {...},
    'match': context['job'],  # alias
    ...
}
```

**Karar:** KABUL with ALIASES - Yeni syntax önerilir, eski syntax deprecated ama çalışır

---

### Endişe 4: "Event bus synchronous - scaling problem?"

**Analiz:**
- Mevcut kullanım: Single process, sequential execution
- Event bus sadece tracking için, async gerekmiyor
- İleride async gerekirse RabbitMQ/Redis eklenebilir

**Karar:** KABUL - Şu anki gereksinim için yeterli

---

### Endişe 5: "Plugin data namespace (tmdb.data) vs flat (tmdb.title)"

**Analiz:**

**Flat style:**
```javascript
plugins: {
  tmdb: {
    status: "success",
    title: "...",  // data ile karışık
    year: 2005
  }
}
```

**Namespaced style (ÖNERİLEN):**
```javascript
plugins: {
  tmdb: {
    status: "success",
    reason: null,
    timing: {...},
    data: {
      title: "...",
      year: 2005
    }
  }
}
```

**Karar:** NAMESPACE KULLAN - Status/meta bilgi ile data karışmasın

---

## MİGRASYON PLANI

### Phase 1: Terminology Update
1. `execution` → `run` (alias koru)
2. `match` → `job` (alias koru)
3. `matches` → `jobs` (alias koru)
4. `not_supported` → `skipped`
5. `depends_on` → KALDIR, sadece `requires` kullan

### Phase 2: Plugin System Refactor
1. Plugin base class güncelle
2. `requires` manifest field ekle
3. PluginResponse standardize et
4. InputService/OutputService implement et

### Phase 3: State Structure Update
1. State models güncelle (nested structure)
2. Plugin data namespace: `plugin.data.X`
3. Task type field ekle: `output.tasks[].type`

### Phase 4: Event Bus
1. EventBus implement et
2. CompletionTracker implement et
3. Job/Run status calculation

### Phase 5: MongoDB Migration
1. Collection rename: `executions` → `runs`, `matches` → `jobs`
2. Document structure update
3. Index oluştur

### Phase 6: Tests & Documentation
1. Unit tests güncelle
2. Integration tests
3. Template migration guide

---

## ÖNEMLİ NOTLAR

1. **3 Sistem Alias:** `run`, `job`, `jobs` - Başka alias YOK (eski olanlar deprecated)
2. **Plugin kategorisi YOK:** Pluginler servisler aracılığıyla ne yaparsa yapar
3. **`requires` TEK BAĞIMLILIK ALANI:** `depends_on` ve `expects` kaldırıldı
4. **Tüm pluginler response ZORUNDA:** En az `skipped` dönmeli
5. **`skipped` standardı:** Airflow terminolojisi
6. **Plugin data namespace:** `job.plugins.tmdb.data.title` (flat değil)
7. **Output task type:** `output.tasks[].type` = `print`, `save`, `notify`, etc.

---

## DOSYA DEĞİŞİKLİKLERİ ÖZETİ

| Dosya | Değişiklik |
|-------|------------|
| `plugins/base.py` | PluginResponse, BasePlugin v4 |
| `plugins/services.py` | YENİ - InputService, OutputService |
| `core/orchestrator.py` | Dependency graph, execution order |
| `core/executor.py` | Response enforcement |
| `core/events.py` | YENİ - EventBus, CompletionTracker |
| `state/models.py` | Run, Job, nested structures |
| `state/manager.py` | get_context() v4 |
| `infrastructure/persistence/*.py` | Collection rename, new schema |
| Plugin manifest'leri | `requires` field, kategori kaldırma |

---

**Tahmini Süre:** 8-10 saat

**Bu strateji v3'ün üzerine inşa edilmiştir.**
**Tarih:** 2025-11-28
