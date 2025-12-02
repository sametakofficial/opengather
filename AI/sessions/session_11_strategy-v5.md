# SESSION 11 STRATEGY v5 - COMPREHENSIVE ANALYSIS & ARCHITECTURE REVIEW

```yaml
date: 2025-11-28
type: strategy
status: draft
previous_session: 11-v4
focus: Deep Analysis, Hallucination Detection, Job ID vs Index Resolution
analyst: Strategy Chat + Industry Research + Full Codebase Analysis
```

---

## PART 1: MEVCUT SİSTEM ANALİZİ

### 1.1 Event Bus - ZATEN MEVCUT ✅

v4 strateji dosyası **event bus sistemi yokmuş gibi** davranmış. Bu **HALÜSİNASYON**.

**Gerçek Durum:**
```
src/archiverr/events/
├── __init__.py          # EventBus, Events, handlers export
├── bus.py               # 286 satır - TAM İŞLEVSEL EventBus
└── handlers.py          # 221 satır - DebugHandler, ProgressHandler, StatisticsHandler
```

**bus.py'de Mevcut Özellikler:**
```python
class Events:
    # Execution lifecycle
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    
    # Match lifecycle
    MATCH_STARTED = "match.started"
    MATCH_COMPLETED = "match.completed"
    MATCH_FAILED = "match.failed"
    
    # Plugin lifecycle
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_SKIPPED = "plugin.skipped"
    PLUGIN_PROGRESS = "plugin.progress"
    
    # Task lifecycle
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # State & DB
    STATE_CHANGED = "state.changed"
    DB_CONNECTED = "db.connected"
    DB_SYNCED = "db.synced"
    DB_ERROR = "db.error"
```

**EventBus Özellikleri:**
- Thread-safe (Lock kullanıyor)
- Wildcard subscription ("*")
- Event history (1000 event)
- Error isolation (handler hataları sistemi çökertmez)
- Dependency injection ready

**SONUÇ:** v4'ün "Event Bus Tasarımı" bölümü **GEREKSIZ** - zaten var!

---

### 1.2 State Manager - ZATEN MEVCUT ✅

**Konum:** `src/archiverr/state/manager.py` (594 satır)

**Mevcut Özellikler:**
```python
class StateManager:
    # Dependency Injection
    def __init__(self, persistence=None, debugger=None, event_bus=None)
    
    # Execution lifecycle
    def start_execution(config) -> str  # Returns execution_id
    def complete_execution(branch_name="main")
    
    # Match management
    def register_match(index, input_path) -> MatchState
    def complete_match(match_index)
    def update_plugin_result(match_index, plugin_name, result)
    
    # Template context building
    def build_template_context(match_index) -> Dict
    def build_api_response_for_templates() -> Dict
```

**Event Emission ZATEN VAR:**
```python
# state/manager.py line 95-98
def _emit(self, event_name: str, data: Dict = None, source: str = "state"):
    """Emit event if event bus is configured"""
    if self._event_bus:
        self._event_bus.emit(event_name, data or {}, source)
```

---

### 1.3 __main__.py Akış Analizi

**Mevcut Akış (ÇALIŞIYOR):**
```python
# 1. Event bus oluştur
event_bus = EventBus(debugger=debugger)

# 2. Handler'ları kaydet
progress_handler = ProgressHandler()
stats_handler = StatisticsHandler()
event_bus.subscribe(Events.MATCH_COMPLETED, progress_handler)
event_bus.subscribe("*", stats_handler)

# 3. State manager'ı configure et
state = GlobalStateManager()
state.configure(persistence=persistence, debugger=debugger, event_bus=event_bus)

# 4. Execution başlat
execution_id = state.start_execution(config)

# 5. Her match için:
for index, match in enumerate(input_matches):
    state_match = state.register_match(index, input_path)
    # ... plugin execution ...
    state.complete_match(index)

# 6. Execution tamamla
state.complete_execution()
```

---

## PART 2: JOB ID vs INDEX PARADOKSU ÇÖZÜMÜ

### 2.1 Endüstri Araştırması

**Temporal.io Yaklaşımı:**
- **Workflow ID**: Application-level, business identifier (user-generated)
- **Run ID**: Platform-level, system-generated (globally unique)
- Workflow ID + Run ID = Unique execution

**Airflow Yaklaşımı:**
- **Task Instance ID**: `dag_id + task_id + execution_date`
- Composite key - index KULLANMIYOR
- Her instance unique

**MongoDB Best Practices:**
- ObjectID: 12-byte, timestamp + random + counter
- UUID: 128-bit, application-level generation
- **Önerilen**: ObjectID for system IDs, application-generated for business IDs

### 2.2 Archiverr İçin Çözüm: HYBRID ID SYSTEM

```python
class JobIdentifier:
    """
    Two-level identification:
    - index: In-memory position (0, 1, 2...) for array access
    - job_id: Persistent unique ID for MongoDB/API references
    """
    
    # Index: Execution içinde sıra numarası (local scope)
    index: int  # 0, 1, 2, ...
    
    # Job ID: Global unique identifier
    job_id: str  # "job_{execution_id}_{index}" veya ObjectId
```

**Neden İki Seviyeli?**

| Seviye | Kullanım Alanı | Avantaj |
|--------|----------------|---------|
| `index` | In-memory arrays, loops, template iteration | Hızlı, O(1) access |
| `job_id` | MongoDB, API, logs, debugging | Globally unique, traceable |

### 2.3 Önerilen Uygulama

```python
# state/models.py - GÜNCELLENMİŞ MatchState
@dataclass
class MatchState:
    # Dual identification
    index: int                    # Local: array position
    job_id: str                   # Global: "job_{exec_id}_{index}"
    
    execution_id: str
    input_path: str
    # ... rest of fields
    
    @staticmethod
    def generate_job_id(execution_id: str, index: int) -> str:
        """Generate predictable job_id from execution_id and index"""
        return f"job_{execution_id}_{index}"
```

**MongoDB Document:**
```javascript
{
  _id: ObjectId("..."),           // MongoDB's own ID
  job_id: "job_abc123_0",         // Our predictable ID
  run_id: "abc123",               // Execution reference
  index: 0,                       // Array position
  // ... rest
}
```

### 2.4 Plugin Erişim Patterns

```python
# InputService - Job oluşturma
class InputService:
    def create_job(self, path: str, metadata: dict = None) -> Job:
        index = len(self._jobs)
        job_id = f"job_{self._execution_id}_{index}"
        
        job = Job(
            index=index,
            job_id=job_id,
            input={'path': path},
            metadata=metadata
        )
        
        self._jobs.append(job)
        
        # MongoDB'ye yaz (job_id ile)
        self._persistence.save_job(job)
        
        return job
    
    def get_job(self, index: int) -> Job:
        """Fast O(1) access by index"""
        return self._jobs[index]
    
    def get_job_by_id(self, job_id: str) -> Job:
        """Lookup by job_id (for API/external references)"""
        # MongoDB query or in-memory search
        pass
```

### 2.5 KARAR

**State = Source of Truth, MongoDB = Persistence Layer**

```
┌─────────────────────┐
│   In-Memory State   │ ◄── index-based access (FAST)
│   (Dict[int, Job])  │
└─────────┬───────────┘
          │ Write-through
          ▼
┌─────────────────────┐
│      MongoDB        │ ◄── job_id-based queries (PERSISTENT)
│   (jobs collection) │
└─────────────────────┘
```

**İlk Başta Kim Oluşturuyor?**
1. State `register_match(index, path)` çağırır
2. State `job_id = f"job_{execution_id}_{index}"` generate eder
3. State MongoDB'ye yazar
4. MongoDB kendi `_id: ObjectId` ekler (ama biz job_id kullanırız)

**Paradox Çözüldü:** 
- Index = local scope (in-memory, fast)
- job_id = global scope (predictable, not random)
- ObjectId = MongoDB internal (we don't rely on it)

---

## PART 3: DRY_RUN İŞLEVSELLİĞİ

### 3.1 Mevcut Durum

`task_manager.py` line 149:
```python
if not dry_run:
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        success = True
    except Exception:
        success = False
else:
    success = True  # Dry run - pretend success
```

**dry_run SADECE `save` type task'ları etkiliyor.**

### 3.2 Önerilen Genişletme

```python
# task_manager.py - GÜNCELLENMİŞ
def _execute_save(self, task_config, api_response, current_index, dry_run):
    # ... destination render ...
    
    if dry_run:
        self.debugger.info("tasks", f"[DRY-RUN] Would save to: {destination}")
        return {
            'task_name': task_name,
            'type': 'save',
            'destination': destination,
            'success': True,
            'dry_run': True,
            'skipped_reason': 'dry_run enabled'
        }
    
    # Actual save logic...
```

**dry_run'ın Etkilediği Sistemler:**
| Sistem | dry_run=True | dry_run=False |
|--------|--------------|---------------|
| `save` tasks | Skip, log destination | Actually copy/move |
| `print` tasks | Execute | Execute |
| Plugin execution | Execute | Execute |
| MongoDB writes | Execute | Execute |

**Sonuç:** dry_run sadece file I/O'yu engelliyor - doğru davranış!

---

## PART 4: CURRENT JOB STATE

### 4.1 v4'ün Önerisi

v4 şöyle bir yapı önermiş:
```python
context = {
    'run': {...},
    'job': {...},      # ◄── Current job
    'jobs': [...]
}
```

### 4.2 Gerçek Gereksinim Analizi

**Şu an `current_index` kullanan yerler:**

1. **task_manager.py** - `execute_tasks_for_match(api_response, current_index, dry_run)`
2. **template_manager.py** - `render(template, api_response, current_index)`
3. **executor.py** - `execute_output_pipeline(..., match_index=index, ...)`

**Gözlem:** Zaten `current_index` parametre olarak geçiriliyor!

### 4.3 Karar: CURRENT JOB STATE'E GEREK YOK

```python
# ❌ YANLIŞ - Statik "current job" tutmak
state.current_job = job  # Tehlikeli - race condition riski

# ✅ DOĞRU - Her çağrıya index geçirmek
task_manager.execute_tasks_for_match(api_response, current_index=5)
template_manager.render(template, api_response, current_index=5)
```

**Neden?**
1. Thread-safety: Paralel execution'da current_job karışır
2. Simplicity: Zaten parametre geçiriliyor
3. Airflow pattern: Task instance'lar statik "current" tutmuyor

**Template'lerde Erişim:**
```jinja2
{# Zaten çalışıyor - index parametre olarak geçiriliyor #}
{{ matches[index].plugins.tmdb.movie.title }}

{# Veya şu alias ile: #}
{{ match.plugins.tmdb.movie.title }}
```

---

## PART 5: KAPSAMLI SİSTEM ŞEMASI

### 5.1 Tam Mimari Şeması

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              ARCHIVERR SYSTEM ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                           ENTRY POINTS                                   │   │
│  │  ┌──────────────────┐            ┌──────────────────┐                   │   │
│  │  │   __main__.py    │            │   api/main.py    │                   │   │
│  │  │   (CLI Mode)     │            │   (API Mode)     │                   │   │
│  │  └────────┬─────────┘            └────────┬─────────┘                   │   │
│  └───────────┼───────────────────────────────┼─────────────────────────────┘   │
│              │                               │                                  │
│              ▼                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        CONFIG LOADING LAYER                              │   │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                 │   │
│  │  │ config.yml   │ + │    .env      │ → │ Merged Config│                 │   │
│  │  │ (structure)  │   │ (secrets)    │   │ (runtime)    │                 │   │
│  │  └──────────────┘   └──────────────┘   └──────────────┘                 │   │
│  │           ↓                                                              │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │   │
│  │  │ config_loader.py: load_config_with_tracking()                     │   │   │
│  │  │ config_validator.py: ConfigValidator.validate()                   │   │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                      │
│              ┌───────────────────────────┴───────────────────────────┐         │
│              ▼                                                       ▼         │
│  ┌─────────────────────────────────┐       ┌─────────────────────────────────┐ │
│  │        EVENT BUS                │       │       STATE MANAGER             │ │
│  │   src/archiverr/events/         │◄─────►│   src/archiverr/state/          │ │
│  │                                 │       │                                 │ │
│  │  • EventBus (bus.py)            │       │  • GlobalStateManager           │ │
│  │  • Events constants             │       │  • ExecutionState               │ │
│  │  • ProgressHandler              │       │  • MatchState                   │ │
│  │  • StatisticsHandler            │       │  • PluginResult                 │ │
│  │                                 │       │                                 │ │
│  │  Subscriptions:                 │       │  Methods:                       │ │
│  │  - "*" → stats                  │       │  - start_execution()            │ │
│  │  - MATCH_COMPLETED → progress   │       │  - register_match()             │ │
│  │                                 │       │  - update_plugin_result()       │ │
│  └─────────────────────────────────┘       │  - complete_match()             │ │
│              │                             │  - build_template_context()     │ │
│              │                             └─────────────┬───────────────────┘ │
│              │                                           │                      │
│              │                    ┌──────────────────────┘                      │
│              ▼                    ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         PLUGIN SYSTEM                                    │   │
│  │                    core/plugins/                                         │   │
│  │                                                                          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐         │   │
│  │  │ discovery  │→ │  loader    │→ │  resolver  │→ │  executor  │         │   │
│  │  │  .py       │  │   .py      │  │   .py      │  │   .py      │         │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘         │   │
│  │        │                                               │                 │   │
│  │        │ Scan plugins/*/                               │ Execute         │   │
│  │        │ manifest.yml                                  │ with context    │   │
│  │        ▼                                               ▼                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐    │   │
│  │  │                      PLUGIN SDK                                  │    │   │
│  │  │                 core/plugins/sdk/                                │    │   │
│  │  │                                                                  │    │   │
│  │  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │    │   │
│  │  │  │  base.py   │ │ context.py │ │ result.py  │ │validators │   │    │   │
│  │  │  │ BasePlugin │ │ Execution  │ │ PluginRe- │ │   .py      │   │    │   │
│  │  │  │ Input/Out  │ │ Context    │ │  sult     │ │            │   │    │   │
│  │  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                      │
│              ┌───────────────────────────┴───────────────────────────┐         │
│              ▼                                                       ▼         │
│  ┌─────────────────────────────────┐       ┌─────────────────────────────────┐ │
│  │        PLUGINS                  │       │       TASK SYSTEM               │ │
│  │   src/archiverr/plugins/        │       │   core/tasks/                   │ │
│  │                                 │       │                                 │ │
│  │  INPUT:                         │       │  ┌────────────────┐             │ │
│  │  • scanner                      │       │  │ TaskManager    │             │ │
│  │  • file_reader                  │       │  │ - print tasks  │             │ │
│  │                                 │       │  │ - save tasks   │             │ │
│  │  OUTPUT:                        │       │  │ - external     │             │ │
│  │  • renamer                      │       │  └───────┬────────┘             │ │
│  │  • ffprobe                      │       │          │                      │ │
│  │  • tmdb                         │       │  ┌───────▼────────┐             │ │
│  │  • [tvdb, omdb, tvmaze]         │       │  │TemplateManager │             │ │
│  │    (disabled)                   │       │  │ - Jinja2       │             │ │
│  │                                 │       │  │ - $ syntax     │             │ │
│  └─────────────────────────────────┘       │  │ - aliases      │             │ │
│                                            │  └────────────────┘             │ │
│                                            └─────────────────────────────────┘ │
│                                                          │                      │
│                                                          ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      INFRASTRUCTURE LAYER                                │   │
│  │                  infrastructure/database/                                │   │
│  │                                                                          │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │   │
│  │  │ interface.py    │  │   mongodb.py    │  │    mock.py      │          │   │
│  │  │ Persistence     │  │ PyMongoPersist  │  │ MockPersistence │          │   │
│  │  │ Interface       │  │ (sync)          │  │ (file-based)    │          │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘          │   │
│  │                                │                    │                    │   │
│  │                                ▼                    ▼                    │   │
│  │                       ┌─────────────────────────────────────────┐        │   │
│  │                       │           MONGODB                       │        │   │
│  │                       │  Collections:                           │        │   │
│  │                       │  • executions                           │        │   │
│  │                       │  • matches                              │        │   │
│  │                       │  • plugin_results                       │        │   │
│  │                       │  • branches, commits (versioning)       │        │   │
│  │                       └─────────────────────────────────────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Execution Flow Sequence

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Config   │  │ EventBus │  │  State   │  │ Plugins  │  │  Tasks   │
│ Loader   │  │          │  │ Manager  │  │          │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │             │
     │ load()      │             │             │             │
     │─────────────┼─────────────┼─────────────┼─────────────│
     │             │             │             │             │
     │             │◄────────────│ subscribe() │             │
     │             │             │             │             │
     │             │         start_execution() │             │
     │             │◄────────────│─────────────│             │
     │             │   emit(EXECUTION_STARTED) │             │
     │             │             │             │             │
     │             │             │   discover() │             │
     │             │             │─────────────►│             │
     │             │             │   load()     │             │
     │             │             │─────────────►│             │
     │             │             │             │             │
     │             │             │ For each match:           │
     │             │             │─────────────────────────────│
     │             │         register_match()  │             │
     │             │◄────────────│─────────────│             │
     │             │   emit(MATCH_STARTED)     │             │
     │             │             │             │             │
     │             │             │   execute()  │             │
     │             │             │─────────────►│             │
     │             │             │   result     │             │
     │             │             │◄─────────────│             │
     │             │             │             │             │
     │             │  update_plugin_result()   │             │
     │             │◄────────────│─────────────│             │
     │             │   emit(PLUGIN_COMPLETED)  │             │
     │             │             │             │             │
     │             │         complete_match()  │             │
     │             │◄────────────│─────────────│             │
     │             │   emit(MATCH_COMPLETED)   │             │
     │             │             │             │             │
     │             │             │   execute_tasks()         │
     │             │             │────────────────────────────►
     │             │             │             │   result    │
     │             │             │◄────────────────────────────
     │─────────────┼─────────────┼─────────────┼─────────────│
     │             │             │             │             │
     │             │       complete_execution()│             │
     │             │◄────────────│─────────────│             │
     │             │   emit(EXECUTION_COMPLETED│             │
     │             │             │             │             │
```

---

## PART 6: HALÜSİNASYON TESPİT RAPORU

### 6.1 Session 11-v4'teki Hatalar

| # | İddia | Gerçek | Önem |
|---|-------|--------|------|
| 1 | "Event Bus Tasarımı" bölümü - yeni bus önerisi | EventBus ZATEN VAR `events/bus.py` | 🔴 KRİTİK |
| 2 | `core/events.py` oluşturulacak | `events/` klasörü zaten mevcut | 🔴 KRİTİK |
| 3 | `core/orchestrator.py` oluşturulacak | `core/plugins/executor.py` zaten bu işi yapıyor | 🟠 YÜKSEK |
| 4 | `CompletionTracker` implement edilecek | `StatisticsHandler` zaten benzer işlevi yapıyor | 🟠 YÜKSEK |
| 5 | Plugin base class'ları yeniden yazılacak | `core/plugins/sdk/base.py` mevcut ve çalışıyor | 🟡 ORTA |

### 6.2 Session 7-10 Halüsinasyon Özeti

```
Session 7:  50% accuracy - SDK/EventBus "done" denildi, entegrasyon yoktu
Session 8:  60% accuracy - SDK lokasyonu yanlış dokümante edildi
Session 9:  70% accuracy - PluginResult "kullanılıyor" denildi, kullanılmıyordu
Session 10: 95% accuracy - Gerçekten yapıldı, doğrulandı
Session 11-v4: ~40% accuracy - Mevcut sistemler görmezden gelindi
```

### 6.3 Root Cause

**Neden bu hatalar yapıldı?**
1. Projeyi tam okumadan plan yapıldı
2. Mevcut dosyalar kontrol edilmedi
3. "Yeni oluştur" refleksi - mevcut sistemleri geliştirmek yerine

**Çözüm:**
- Her strategy session'da önce `code_search` ve `read_file`
- Mevcut dosyaları listelemeden plan YAPMAMAK
- "Bu dosya var mı?" sorusu sormadan öneri VERMEMEK

---

## PART 7: plugins.tmdb vs tmdb.movie KARARI

### 7.1 v4'ün Önerisi

```javascript
// v4 önerisi - namespace
job.plugins.tmdb.data.title

// Mevcut sistem
matches[index].plugins.tmdb.movie.title
// veya
tmdb.movie.title  (flat access)
```

### 7.2 Analiz

**Mevcut Yapı (state/manager.py line 483-486):**
```python
# Plugin data flat access: {{ renamer.parsed.movie.name }}
for plugin_name, plugin_data in match.plugins.items():
    context[plugin_name] = plugin_data
```

**Şu an çalışan template:**
```jinja2
{{ tmdb.movie.title }}
{{ renamer.parsed.movie.name }}
```

### 7.3 Karar: MEVCUT YAPIYI KORU

**Gerekçe:**
1. Çalışıyor ve test edilmiş
2. Kısa ve okunabilir
3. Template'ler bozulmaz
4. Breaking change gereksiz

**Namespace SADECE API response'da:**
```javascript
// MongoDB/API yapısı (internal)
{
  "plugins": {
    "tmdb": {
      "status": {...},
      "movie": {...}   // data namespace yok, direkt movie
    }
  }
}

// Template context (flat)
{
  "tmdb": {"movie": {...}},
  "renamer": {"parsed": {...}}
}
```

---

## PART 8: ÖNCELİKLENDİRİLMİŞ EYLEM PLANI

### Phase 1: Mevcut Sistemi Stabilize Et (1-2 saat)

| # | Görev | Dosya | Durum |
|---|-------|-------|-------|
| 1 | MatchState'e `job_id` field ekle | `state/models.py` | TODO |
| 2 | `register_match()` job_id generate etsin | `state/manager.py` | TODO |
| 3 | MongoDB'ye job_id yazılsın | `mongodb.py` | TODO |

### Phase 2: Terminology Update (30 dk)

| Eski | Yeni | Alias |
|------|------|-------|
| `execution` | `run` | `execution` deprecated alias |
| `match` | `job` | `match` deprecated alias |
| `not_supported` | `skipped` | hardcoded değişiklik |

**NOT:** Collection rename'ler YAPILMAYACAK - sadece kod terminology

### Phase 3: Plugin Response Standardization (1 saat)

- [ ] `renamer` → PluginResult döndürsün
- [ ] `ffprobe` → PluginResult döndürsün
- [ ] Her plugin `skipped` durumu desteklesin

### Phase 4: Documentation (30 dk)

- [ ] `AI/03_ARCHITECTURE.md` güncelle
- [ ] `PLUGIN_SDK.md` güncelle

---

## PART 9: YAPILMAMASI GEREKENLER

### ❌ Yeni EventBus OLUŞTURMA
Mevcut `events/bus.py` yeterli.

### ❌ core/orchestrator.py OLUŞTURMA
Mevcut `core/plugins/executor.py` bu işi yapıyor.

### ❌ MongoDB collection rename
`executions` → `runs` gibi rename'ler YAPILMAYACAK. Sadece kod terminology değişecek.

### ❌ Breaking template changes
`tmdb.movie.title` → `job.plugins.tmdb.data.title` gibi değişiklikler YAPILMAYACAK.

### ❌ Current job state
State'de "current_job" tutulmayacak - parametre olarak geçirilmeye devam edilecek.

---

## SONUÇ

Session 11-v4 projeyi tam analiz etmeden yazılmış ve mevcut sistemleri görmezden gelmiş.

**Gerçek Durum:**
- ✅ EventBus VAR ve çalışıyor
- ✅ StateManager VAR ve event emit ediyor
- ✅ SDK VAR ve TMDb tarafından kullanılıyor
- ✅ Plugin lifecycle hooks VAR

**Yapılması Gereken:**
1. Mevcut sistemi bozmadan `job_id` ekle
2. Terminology'yi yavaşça değiştir (alias ile)
3. Kalan pluginleri PluginResult'a migrate et
4. Dokümantasyonu güncel tut

**Tahmini Süre:** 4-5 saat (v4'ün 8-10 saat yerine)

---

**Tarih:** 2025-11-28
**Analyst:** Strategy Chat with Deep Codebase Analysis
