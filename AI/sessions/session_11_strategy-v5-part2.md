# SESSION 11 STRATEGY v5 - PART 2: DERİN ANALİZ VE SORULARA CEVAPLAR

```yaml
date: 2025-11-28
type: strategy-continuation
parent: session_11_strategy-v5.md
focus: Kullanıcı Sorularına Detaylı Cevaplar
```

---

## 1. `plugins.tmdb.movie` vs `plugins.tmdb` AÇIKLAMASI

### Kullanıcı Sorusu:
> "şunu anlamadım yani ama neyse tmdb.movie sistemini mi kalıracaksın hahaha mal mısın"

### Cevap:

v4 stratejide **YANLIŞ** bir tablo var:

```
| Plugin verisi | `plugins.tmdb.movie` | `plugins.tmdb` | Plugin adı = namespace |
```

Bu tablo şunu ima ediyor: "tmdb.movie kaldırılacak, sadece tmdb olacak"

**Bu YANLIŞ bir yorumlama.** Tablonun demek istediği şuydu:

```javascript
// MEVCUT (ve KORUNACAK):
{
  "plugins": {
    "tmdb": {
      "status": {...},
      "movie": {                    // ◄── Bu KALACAK
        "id": 1234,
        "title": "Mr. & Mrs. Smith"
      }
    }
  }
}

// Template erişimi:
{{ tmdb.movie.title }}              // ◄── Bu ÇALIŞMAYA DEVAM EDECEK
```

**v4'ün kafa karıştıran noktası:**
Tablo "plugin adı = namespace" demiş ama bu plugin'in KENDİ data yapısını değiştirmez. Her plugin kendi data yapısını belirler:

| Plugin | Data Yapısı | Örnek Erişim |
|--------|-------------|--------------|
| tmdb | `movie`, `show`, `season`, `episode` | `tmdb.movie.title` |
| renamer | `parsed.movie`, `parsed.show` | `renamer.parsed.movie.name` |
| ffprobe | `video`, `audio`, `container` | `ffprobe.video.codec` |

**SONUÇ:** `tmdb.movie.title` erişimi **KESİNLİKLE KORUNUYOR**.

---

## 2. JOB DURUMLARI VE EVENT BUS

### Kullanıcı Sorusu:
> "bizim sistemimizde endüstri seviyesi teknolojiler kullanılıyor job durumlarını event bus veya başka birşey tutuyor olsa gerek... state içinde dümdüz mü saklayacaz"

### Cevap:

**Mevcut Sistem Analizi:**

```python
# state/models.py - ExecutionStatus enum
class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# MatchState dataclass
@dataclass
class MatchState:
    status: ExecutionStatus = ExecutionStatus.PENDING
    # ...
```

**Durum Yönetimi Nasıl Çalışıyor?**

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATE YÖNETİM MİMARİSİ                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │  StateManager   │────►│    EventBus     │                   │
│  │  (Source of     │     │  (Notification) │                   │
│  │   Truth)        │     └────────┬────────┘                   │
│  └────────┬────────┘              │                            │
│           │                       │                            │
│           │ Write-through         │ Events                     │
│           ▼                       ▼                            │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │    MongoDB      │     │    Handlers     │                   │
│  │  (Persistence)  │     │ (Side Effects)  │                   │
│  └─────────────────┘     └─────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Airflow Pattern ile Karşılaştırma:**

| Sistem | State Storage | Notification |
|--------|---------------|--------------|
| Airflow | PostgreSQL metadata DB | Event-driven triggers |
| Temporal | Workflow history (append-only) | Events + signals |
| **Archiverr** | StateManager (in-memory) + MongoDB | EventBus |

**Mevcut Event Emission (state/manager.py):**

```python
def register_match(self, index: int, input_path: str) -> MatchState:
    # ... create match ...
    
    # Emit event (line 278-283)
    self._emit("match.started", {
        "index": index,
        "input_path": input_path,
        "execution_id": self._execution.id
    })
    
    return match

def complete_match(self, match_index: int):
    # ... update match ...
    
    # Emit event (line 386-394)
    event_name = "match.completed" if match.success else "match.failed"
    self._emit(event_name, {
        "index": match_index,
        "success": match.success,
        "duration_ms": match.duration_ms
    })
```

**SONUÇ:** 
- Durumlar STATE'de saklanıyor ✅
- Değişiklikler EVENT ile notify ediliyor ✅
- Bu **endüstri standardına UYGUN** (Airflow, Temporal aynısını yapıyor)

**Ek Not - Airflow State Transitions:**
```
none → scheduled → queued → running → success/failed/skipped
```

**Archiverr State Transitions:**
```
PENDING → RUNNING → COMPLETED/FAILED
```

v4'ün önerdiği ek state'ler (SCHEDULED, QUEUED, UPSTREAM_FAILED) şu an gereksiz çünkü:
- Single-process execution (queue yok)
- Topological sort ile dependency (upstream_failed pattern gereksiz)

---

## 3. MOTOR vs PYMONGO ASYNC DURUMU

### Kullanıcı Sorusu:
> "bak gene bilgisizlik pymongo async ne gune duruyor olm"

### Cevap:

**Mevcut Durum:**

```python
# infrastructure/database/mongodb.py - DEPRECATED (line 38-44)
warnings.warn(
    "MongoDBPersistence is deprecated. Use PyMongoPersistence instead. "
    "MongoDBPersistence uses Motor + run_until_complete() which can cause "
    "event loop issues in async contexts.",
    DeprecationWarning
)
```

**Dosya Yapısı:**
```
infrastructure/database/
├── interface.py      # PersistenceInterface (abstract)
├── mongodb.py        # Motor-based (DEPRECATED)
├── pymongo.py        # PyMongo sync (CURRENT)
├── motor.py          # Async Motor for API
└── mock.py           # File-based mock
```

**Neden İki Sistem?**

| Sistem | Kullanım | Driver |
|--------|----------|--------|
| CLI (`__main__.py`) | Sync execution | PyMongo (sync) |
| API (`api/main.py`) | Async FastAPI | Motor (async) |

**Motor Async Örneği (motor.py):**
```python
class MotorPersistence:
    """Async persistence for FastAPI"""
    
    async def save_execution(self, execution) -> None:
        await self._db[self.EXECUTIONS].update_one(
            {"_id": exec_id},
            {"$set": exec_dict},
            upsert=True
        )
```

**PyMongo Sync Örneği (pymongo.py):**
```python
class PyMongoPersistence:
    """Sync persistence for CLI"""
    
    def save_execution(self, execution) -> None:
        self._db[self.EXECUTIONS].update_one(
            {"_id": exec_id},
            {"$set": exec_dict},
            upsert=True
        )
```

**SONUÇ:** Sistem **ZATEN** async-ready:
- CLI = PyMongo (sync, basit)
- API = Motor (async, FastAPI uyumlu)

---

## 4. MANIFEST.YML VE CONFIG.YML ALIAS UYUMU

### Kullanıcı Sorusu:
> "manifest.yml ve config.yml aynı altyapıyı kullanmasını tembihlemiştim bu durumda mecbur job aliası manifest.yml ye de gidiyor"

### Cevap:

**Mevcut Durum:**

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
description: Fetches metadata from TMDB API
category: output
class_name: TMDbPlugin
depends_on:
  - renamer
expects:
  - renamer.parsed.movie
  - renamer.parsed.show
```

```yaml
# config.yml
plugins:
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}
    lang: tr-TR
```

**Alias Konusu:**

Template'lerde kullanılan alias'lar (`match`, `job`, `run` vs.) **sadece template rendering sırasında** geçerli:

```python
# core/tasks/template_manager.py
def _build_context(self, api_response, current_index):
    context = {
        # Sistem aliases
        'match': current_match,          # → job alias eklenebilir
        'matches': all_matches,           # → jobs alias eklenebilir
        'execution': execution_data,      # → run alias eklenebilir
        
        # Plugin data (flat)
        'tmdb': plugin_data['tmdb'],
        'renamer': plugin_data['renamer'],
    }
    return context
```

**manifest.yml alias gerektirmez çünkü:**
1. `manifest.yml` = Static plugin metadata (load-time)
2. `config.yml` = Dynamic configuration (runtime)
3. Template aliases = Rendering-time context

**Çözüm - Alias'lar SADECE template_manager.py'de:**

```python
# template_manager.py - Alias injection
context = {
    # Primary names (new)
    'job': current_match,
    'jobs': all_matches,
    'run': execution_data,
    
    # Deprecated aliases (backward compat)
    'match': current_match,      # alias → job
    'matches': all_matches,      # alias → jobs
    'execution': execution_data, # alias → run
}
```

**manifest.yml AYNI KALIYOR** - `expects: [renamer.parsed.movie]` değişmez.

---

## 5. KAPSAMLI EXECUTION FLOW ŞEMASI

### Kullanıcı Sorusu:
> "bu şema yetersiz... nerede global stateler nerede event bus nerede workerler nerede execution runner"

### Cevap:

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              FULL EXECUTION FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 0: INITIALIZATION                                                     │   │
│  │                                                                              │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │   │
│  │  │ load_dotenv  │───►│ load_config  │───►│ init_debugger│                   │   │
│  │  │ (.env)       │    │ (config.yml) │    │ (debug.py)   │                   │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘                   │   │
│  │         │                   │                   │                            │   │
│  │         ▼                   ▼                   ▼                            │   │
│  │  ┌────────────────────────────────────────────────────────────────────┐     │   │
│  │  │                    DEPENDENCY INJECTION                             │     │   │
│  │  │                                                                     │     │   │
│  │  │  event_bus = EventBus(debugger=debugger)                           │     │   │
│  │  │  state = GlobalStateManager()                                       │     │   │
│  │  │  persistence = DatabaseConnection.from_env().connect()              │     │   │
│  │  │  state.configure(persistence, debugger, event_bus)                  │     │   │
│  │  │                                                                     │     │   │
│  │  └────────────────────────────────────────────────────────────────────┘     │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 1: EVENT HANDLER REGISTRATION                                        │   │
│  │                                                                              │   │
│  │  event_bus.subscribe(MATCH_COMPLETED, progress_handler)                     │   │
│  │  event_bus.subscribe(MATCH_FAILED, progress_handler)                        │   │
│  │  event_bus.subscribe("*", stats_handler)   ◄── Wildcard: tüm eventler      │   │
│  │                                                                              │   │
│  │  ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  HANDLER REGISTRY                                                    │    │   │
│  │  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │    │   │
│  │  │  │ ProgressHandler  │  │StatisticsHandler │  │  [Future:        │   │    │   │
│  │  │  │ - completed: 0   │  │ - all stats      │  │   WebSocket,     │   │    │   │
│  │  │  │ - failed: 0      │  │ - plugin times   │  │   SignalR]       │   │    │   │
│  │  │  │ - total: N       │  │                  │  │                  │   │    │   │
│  │  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 2: EXECUTION START                                                   │   │
│  │                                                                              │   │
│  │  execution_id = state.start_execution(config)                               │   │
│  │       │                                                                      │   │
│  │       ├─► StateManager creates ExecutionState                               │   │
│  │       ├─► Persistence.save_execution() → MongoDB                            │   │
│  │       └─► EventBus.emit("execution.started")                                │   │
│  │                    │                                                         │   │
│  │                    └─► handlers receive event                               │   │
│  │                                                                              │   │
│  │  ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  EXECUTION STATE (in-memory)                                         │    │   │
│  │  │  {                                                                   │    │   │
│  │  │    id: "abc123",                                                     │    │   │
│  │  │    status: RUNNING,                                                  │    │   │
│  │  │    started_at: datetime,                                             │    │   │
│  │  │    total_matches: 0,                                                 │    │   │
│  │  │    completed_matches: 0,                                             │    │   │
│  │  │    failed_matches: 0,                                                │    │   │
│  │  │    config_snapshot: {...}                                            │    │   │
│  │  │  }                                                                   │    │   │
│  │  └─────────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 3: PLUGIN DISCOVERY & LOADING                                        │   │
│  │                                                                              │   │
│  │  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                 │   │
│  │  │ Discovery    │────►│   Loader     │────►│  Resolver    │                 │   │
│  │  │              │     │              │     │              │                 │   │
│  │  │ Scan:        │     │ Filter by:   │     │ Topological  │                 │   │
│  │  │ plugins/*/   │     │ enabled=true │     │ Sort by      │                 │   │
│  │  │ manifest.yml │     │              │     │ depends_on   │                 │   │
│  │  └──────────────┘     └──────────────┘     └──────────────┘                 │   │
│  │                                                   │                          │   │
│  │                                                   ▼                          │   │
│  │  ┌─────────────────────────────────────────────────────────────────────┐    │   │
│  │  │  EXECUTION GROUPS (parallel-safe)                                    │    │   │
│  │  │  [                                                                   │    │   │
│  │  │    [scanner],              # Group 0: no deps                        │    │   │
│  │  │    [renamer, ffprobe],     # Group 1: can run parallel               │    │   │
│  │  │    [tmdb]                  # Group 2: depends on renamer             │    │   │
│  │  │  ]                                                                   │    │   │
│  │  └─────────────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 4: INPUT PLUGIN EXECUTION                                            │   │
│  │                                                                              │   │
│  │  input_matches = executor.execute_input_plugins(input_plugins)              │   │
│  │                                                                              │   │
│  │  ┌───────────────────────────────────────────────────────────────────┐      │   │
│  │  │  SCANNER PLUGIN                                                    │      │   │
│  │  │                                                                    │      │   │
│  │  │  def execute(self) -> List[Dict]:                                  │      │   │
│  │  │      matches = []                                                  │      │   │
│  │  │      for target in self.config['targets']:                         │      │   │
│  │  │          for file in scan(target):                                 │      │   │
│  │  │              matches.append({                                      │      │   │
│  │  │                  'input': {'path': file, 'virtual': False},       │      │   │
│  │  │                  'status': {'success': True}                       │      │   │
│  │  │              })                                                    │      │   │
│  │  │      return matches                                                │      │   │
│  │  └───────────────────────────────────────────────────────────────────┘      │   │
│  │                                                                              │   │
│  │  Result: input_matches = [                                                  │   │
│  │    {'scanner': {...}, 'input': {'path': '/file1.mkv'}},                    │   │
│  │    {'scanner': {...}, 'input': {'path': '/file2.mkv'}},                    │   │
│  │  ]                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 5: PER-MATCH PROCESSING LOOP                                         │   │
│  │                                                                              │   │
│  │  for index, match in enumerate(input_matches):                              │   │
│  │      ┌───────────────────────────────────────────────────────────────────┐  │   │
│  │      │  5.1 REGISTER MATCH                                                │  │   │
│  │      │                                                                    │  │   │
│  │      │  state_match = state.register_match(index, input_path)            │  │   │
│  │      │       │                                                            │  │   │
│  │      │       ├─► MatchState created (in-memory)                          │  │   │
│  │      │       ├─► Persistence.save_match() → MongoDB                      │  │   │
│  │      │       └─► EventBus.emit("match.started", {index, path})           │  │   │
│  │      └───────────────────────────────────────────────────────────────────┘  │   │
│  │                                          │                                   │   │
│  │      ┌───────────────────────────────────▼───────────────────────────────┐  │   │
│  │      │  5.2 OUTPUT PLUGIN EXECUTION                                       │  │   │
│  │      │                                                                    │  │   │
│  │      │  result = executor.execute_output_pipeline(                       │  │   │
│  │      │      output_plugins,                                               │  │   │
│  │      │      execution_groups,                                             │  │   │
│  │      │      match_data,                                                   │  │   │
│  │      │      resolver,        # For expects checking                       │  │   │
│  │      │      match_index=index,                                            │  │   │
│  │      │      total_matches=len(input_matches)                              │  │   │
│  │      │  )                                                                 │  │   │
│  │      │                                                                    │  │   │
│  │      │  ┌──────────────────────────────────────────────────────────┐     │  │   │
│  │      │  │  PLUGIN EXECUTION FLOW (per group)                        │     │  │   │
│  │      │  │                                                           │     │  │   │
│  │      │  │  for group in execution_groups:                           │     │  │   │
│  │      │  │      # Check expects                                      │     │  │   │
│  │      │  │      ready = [p for p in group if resolver.check_expects] │     │  │   │
│  │      │  │                                                           │     │  │   │
│  │      │  │      # Execute in parallel (asyncio.gather)               │     │  │   │
│  │      │  │      results = await execute_group_async(ready, match)    │     │  │   │
│  │      │  │                                                           │     │  │   │
│  │      │  │      # Each plugin gets ExecutionContext                  │     │  │   │
│  │      │  │      # - debugger                                         │     │  │   │
│  │      │  │      # - event_bus                                        │     │  │   │
│  │      │  │      # - task_manager (for emit_task)                     │     │  │   │
│  │      │  │      # - previous_results                                 │     │  │   │
│  │      │  └──────────────────────────────────────────────────────────┘     │  │   │
│  │      └───────────────────────────────────────────────────────────────────┘  │   │
│  │                                          │                                   │   │
│  │      ┌───────────────────────────────────▼───────────────────────────────┐  │   │
│  │      │  5.3 UPDATE STATE WITH PLUGIN RESULTS                              │  │   │
│  │      │                                                                    │  │   │
│  │      │  for plugin_name in success_plugins:                              │  │   │
│  │      │      plugin_result = PluginResult(success=True, data=...)         │  │   │
│  │      │      state.update_plugin_result(index, plugin_name, plugin_result)│  │   │
│  │      │           │                                                        │  │   │
│  │      │           ├─► MatchState.plugins[plugin_name] updated             │  │   │
│  │      │           ├─► Persistence.save_plugin_result() → MongoDB          │  │   │
│  │      │           └─► EventBus.emit("plugin.completed", {plugin, index})  │  │   │
│  │      │                                                                    │  │   │
│  │      │  for plugin_name in not_supported_plugins:                        │  │   │
│  │      │      state.mark_plugin_not_supported(index, plugin_name)          │  │   │
│  │      │           └─► EventBus.emit("plugin.skipped", {plugin, index})    │  │   │
│  │      └───────────────────────────────────────────────────────────────────┘  │   │
│  │                                          │                                   │   │
│  │      ┌───────────────────────────────────▼───────────────────────────────┐  │   │
│  │      │  5.4 EXECUTE TASKS FOR THIS MATCH                                  │  │   │
│  │      │                                                                    │  │   │
│  │      │  temp_api_response = state.build_api_response_for_templates()     │  │   │
│  │      │  task_results = task_manager.execute_tasks_for_match(             │  │   │
│  │      │      temp_api_response,                                            │  │   │
│  │      │      index,                                                        │  │   │
│  │      │      dry_run                                                       │  │   │
│  │      │  )                                                                 │  │   │
│  │      │                                                                    │  │   │
│  │      │  ┌──────────────────────────────────────────────────────────┐     │  │   │
│  │      │  │  TASK EXECUTION                                           │     │  │   │
│  │      │  │                                                           │     │  │   │
│  │      │  │  for task in config['tasks']:                             │     │  │   │
│  │      │  │      if task.condition and not eval(condition):           │     │  │   │
│  │      │  │          continue                                         │     │  │   │
│  │      │  │                                                           │     │  │   │
│  │      │  │      if task.type == 'print':                             │     │  │   │
│  │      │  │          output = template_manager.render(template, ...)  │     │  │   │
│  │      │  │          print(output)                                    │     │  │   │
│  │      │  │                                                           │     │  │   │
│  │      │  │      if task.type == 'save' and not dry_run:              │     │  │   │
│  │      │  │          dest = template_manager.render(destination, ...) │     │  │   │
│  │      │  │          shutil.copy2(source, dest)                       │     │  │   │
│  │      │  └──────────────────────────────────────────────────────────┘     │  │   │
│  │      └───────────────────────────────────────────────────────────────────┘  │   │
│  │                                          │                                   │   │
│  │      ┌───────────────────────────────────▼───────────────────────────────┐  │   │
│  │      │  5.5 COMPLETE MATCH                                                │  │   │
│  │      │                                                                    │  │   │
│  │      │  state.complete_match(index)                                      │  │   │
│  │      │       │                                                            │  │   │
│  │      │       ├─► MatchState.status = COMPLETED/FAILED                    │  │   │
│  │      │       ├─► MatchState.finished_at = now()                          │  │   │
│  │      │       ├─► ExecutionState.completed_matches++                      │  │   │
│  │      │       ├─► Persistence.save_match() → MongoDB                      │  │   │
│  │      │       └─► EventBus.emit("match.completed/failed", {...})          │  │   │
│  │      │                 │                                                  │  │   │
│  │      │                 └─► ProgressHandler.completed++                   │  │   │
│  │      │                 └─► StatisticsHandler records                     │  │   │
│  │      └───────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                              │   │
│  │  end for                                                                    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                                          ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  PHASE 6: EXECUTION COMPLETION                                              │   │
│  │                                                                              │   │
│  │  state.complete_execution(branch_name="main")                               │   │
│  │       │                                                                      │   │
│  │       ├─► ExecutionState.status = COMPLETED                                 │   │
│  │       ├─► ExecutionState.finished_at = now()                                │   │
│  │       ├─► Create branch if not exists                                       │   │
│  │       ├─► Create commit (git-like versioning)                               │   │
│  │       ├─► Persistence.save_execution() → MongoDB                            │   │
│  │       └─► EventBus.emit("execution.completed", {stats})                     │   │
│  │                                                                              │   │
│  │  db_connection.disconnect()                                                 │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. API RESPONSE STRUCTURE

### Mevcut Yapı (`models/response_builder.py` + `state/manager.py`):

```javascript
{
  // Global bilgiler
  "globals": {
    "status": {
      "success": true,
      "matches": 2,
      "completed": 2,
      "errors": 0,
      "tasks": 4,
      "started_at": "2025-11-28T12:00:00",
      "execution_id": "abc123"
    },
    "config": {
      "options": {"debug": true, "dry_run": true},
      "plugins": {...}
    }
  },
  
  // Her match için
  "matches": [
    {
      // Match-level globals
      "globals": {
        "index": 0,
        "input_path": "/path/to/file.mkv",
        "status": {
          "success": true,
          "success_plugins": ["scanner", "renamer", "tmdb"],
          "failed_plugins": [],
          "not_supported_plugins": ["tvdb"],
          "started_at": "...",
          "finished_at": "...",
          "duration_ms": 2500
        },
        "output": {
          "tasks": [
            {"name": "print_header", "type": "print", "success": true},
            {"name": "save_nfo", "type": "save", "success": true, "destination": "..."}
          ]
        }
      },
      
      // Plugin verileri (flat access için)
      "plugins": {
        "scanner": {
          "status": {"success": true},
          "input": {"path": "/...", "virtual": false}
        },
        "renamer": {
          "status": {"success": true},
          "parsed": {
            "movie": {"name": "Mr. & Mrs. Smith", "year": 2005}
          }
        },
        "tmdb": {
          "status": {"success": true},
          "movie": {
            "id": 1234,
            "title": "Mr. & Mrs. Smith",
            "release_date": "2005-06-10",
            "overview": "...",
            "poster_path": "/...",
            "genres": ["Action", "Comedy"]
          }
        }
      }
    }
  ]
}
```

---

## 7. SONUÇ VE EYLEM ÖĞELERİ

### Yapılması Gerekenler (Öncelik Sırasına Göre):

| # | Görev | Zorluk | Süre |
|---|-------|--------|------|
| 1 | `MatchState`'e `job_id` field ekle | Kolay | 15 dk |
| 2 | Template alias'ları ekle (`job`, `jobs`, `run`) | Kolay | 30 dk |
| 3 | `renamer` → PluginResult migration | Orta | 45 dk |
| 4 | `ffprobe` → PluginResult migration | Orta | 45 dk |
| 5 | Dokümantasyon güncelle | Kolay | 30 dk |

### YAPILMAYACAKLAR:

- ❌ Yeni EventBus oluşturma (MEVCUT)
- ❌ Yeni orchestrator.py oluşturma (executor.py VAR)
- ❌ MongoDB collection rename (gereksiz risk)
- ❌ tmdb.movie yapısını değiştirme (çalışıyor)
- ❌ Current job state tutma (parametre yeterli)

---

**Tarih:** 2025-11-28
**Devam Dosyası:** session_11_strategy-v5.md
