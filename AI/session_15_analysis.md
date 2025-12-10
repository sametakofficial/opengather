# ARCHIVERR - PROJE ANALİZİ (SESSION 15)

**Tarih:** 10 Aralık 2024  
**Analiz Türü:** Code-based (MD dosyası okunmadan)  
**Endüstri Karşılaştırması:** FlexGet, Apache Airflow

---

## EXECUTIVE SUMMARY

### Proje Kimliği

- **Adı:** Archiverr
- **Tür:** Config-driven media automation & orchestration framework
- **Dil:** Python 3.x
- **Mimari Paradigma:** Plugin-based workflow orchestration
- **Ana Amaç:** Medya dosyalarını tarama, parsing, metadata fetch, organize etme

### Mimari Kalite Skoru: 7.5/10

**Güçlü Yönler:**

- ✅ Gelişmiş plugin sistemi (stage-based, dependency-aware)
- ✅ Config merge & alias sistemi (flexget-inspired)
- ✅ Event-driven architecture (loose coupling)
- ✅ FastAPI-based REST API

**Zayıf Yönler:**

- ❌ State management karmaşıklığı (6 global object → 3'e indirilmeli)
- ❌ Naming inconsistency (execution/run, match/job)
- ❌ Legacy kod varlığı (pre-release için gereksiz)
- ❌ Tasker plugin job.output'a yazmıyor (BUG - FIX EDİLDİ)

---

## 1. DOSYA YAPISI ANALİZİ

### 1.1 src/archiverr/ Klasör Yapısı

```
src/archiverr/
├── __main__.py              # CLI & API entry point (178 lines)
├── __init__.py              # Package init
├── api/                     # FastAPI REST API (36 files)
│   ├── main.py              # FastAPI app
│   ├── v1/                  # Versioned endpoints
│   │   ├── executions/      # LEGACY: execution endpoints
│   │   ├── runs/            # NEW: run endpoints
│   │   ├── matches/         # LEGACY: match endpoints
│   │   ├── jobs/            # NEW: job endpoints
│   │   ├── plugins/         # Plugin query endpoints
│   │   ├── versioning/      # Git-style versioning (UNUSED)
│   │   └── system/          # System info endpoints
│   └── middleware/          # Rate limiting
├── cli/                     # CLI interface (2 files)
│   └── main.py              # Legacy CLI (UNUSED, moved to __main__)
├── core/                    # Core business logic (48 files)
│   ├── orchestrator.py      # Main coordinator (566 lines)
│   ├── config/              # Config loading & aliasing
│   │   └── alias_resolver.py  # m.title → plugin.tmdb.data.movie.title
│   ├── plugins/             # Plugin system (16 files)
│   │   ├── discovery.py     # Auto-discover plugins
│   │   ├── loader.py        # Dynamic plugin loading
│   │   ├── registry.py      # Plugin registry (Stage enum)
│   │   ├── stage_executor.py  # Stage execution logic (848 lines)
│   │   ├── executor.py      # Single plugin execution
│   │   └── sdk/             # Plugin SDK
│   ├── services/            # Business services (9 files)
│   │   └── plugin_services.py  # Plugin → State communication (336 lines)
│   ├── locking/             # FS lock validation
│   ├── triggers/            # Dependency trigger rules
│   ├── validation/          # Plugin & config validation
│   └── tasks/               # Task system (UNUSED?)
├── state/                   # Global state management (4 files)
│   ├── manager.py           # GlobalStateManager (835 lines)
│   ├── models.py            # State models (353 lines)
│   └── context.py           # ExecutionContext
├── infrastructure/          # Data access layer (14 files)
│   ├── database/            # DB abstraction
│   │   ├── interface.py     # PersistenceInterface
│   │   ├── pymongo.py       # MongoDB implementation
│   │   └── connection.py    # DB connection factory
│   └── repositories/        # Data repositories
├── events/                  # Event bus (3 files)
│   ├── bus.py               # EventBus implementation
│   └── handlers.py          # Event handlers
├── models/                  # Shared models (2 files)
│   └── response_builder.py  # API response builder
├── utils/                   # Utilities (7 files)
│   ├── config_loader.py     # !include, ${ENV}, tracking
│   ├── config_normalizer.py # Multi-format config support
│   ├── debug.py             # Custom debugger (SHOULD BE REPLACED)
│   ├── templates.py         # Jinja2 template utils
│   └── yaml_loader.py       # YAML loading
└── plugins/                 # Built-in plugins (71 files)
    ├── scanner/             # File discovery (per_run)
    ├── renamer/             # Filename parsing (per_job)
    ├── tmdb/                # TMDB metadata (per_job)
    ├── tvdb/                # TVDB metadata (per_job)
    ├── tvmaze/              # TVMaze metadata (per_job)
    ├── omdb/                # OMDB metadata (per_job)
    ├── ffprobe/             # Media file info (per_job)
    ├── tasker/              # Output task executor (per_job) ← BUG FIX EDİLDİ
    ├── file-reader/         # Test plugin
    └── mock_test/           # Mock plugin for testing
```

### 1.2 Toplam Satır Sayıları (Tahmini)

| Katman         | Dosya Sayısı | Tahmini Satır |
| -------------- | ------------ | ------------- |
| Core           | 48           | ~6,000        |
| API            | 36           | ~3,500        |
| State          | 4            | ~1,200        |
| Infrastructure | 14           | ~2,000        |
| Plugins        | 71           | ~8,000        |
| Utils          | 7            | ~2,500        |
| Events         | 3            | ~1,000        |
| **TOPLAM**     | **183**      | **~24,200**   |

---

## 2. MİMARİ PATTERN ANALİZİ

### 2.1 Ana Mimari: Plugin-Based Workflow Orchestration

**Benzerlik:** FlexGet + Apache Airflow hybrid

#### FlexGet Benzerlikleri:

- ✅ Input → Filter → Output pipeline
- ✅ Config-driven execution
- ✅ Plugin discovery & loading
- ✅ YAML-based configuration
- ✅ !include direktifi (config merge)

#### Airflow Benzerlikleri:

- ✅ DAG-style dependency resolution (`requires` + `trigger_rule`)
- ✅ Task parallelization
- ✅ Event-driven notifications
- ✅ Executor pattern (stage-based execution)
- ❌ FARKI: Airflow XCom var, Archiverr'da job.plugins shared state

### 2.2 Plugin Sistemi: 4-Stage Pipeline

```
PARSE → DATA → OUTPUT
 ↓       ↓       ↓
renamer  tmdb   tasker
        tvdb
        omdb
        ffprobe
```

**Not:** INPUT stage kaldırıldı, scanner artık `per_run` mode.

#### Stage Execution Flow:

1. **per_run plugins** execute first (scanner creates jobs)
2. **PARSE stage**: per_job plugins parse filenames
3. **DATA stage**: per_job plugins fetch external metadata
4. **OUTPUT stage**: per_job plugins generate output

**Dependency Resolution:**

```yaml
# manifest.yml
requires:
  - plugin.tmdb.data:success
  - plugin.renamer.data:success

trigger_rule: all_done # all | any | all_done | none_failed
```

### 2.3 State Management: Problematic 6-Object Model

**Current (Session 12):**

```python
GlobalStateManager:
    _run: RunState              # Run-level state
    _config: Dict               # Frozen config
    _current_job: JobState      # ← DUPLICATE
    _jobs: List[JobState]       # ← Contains _current_job
    _current_plugins: Dict      # ← DUPLICATE
    _all_plugins: List[Dict]    # ← Contains _current_plugins
```

**Session 14 Hedefi (Planned):**

```python
GlobalStateManager:
    _run: RunState
    _config: Dict
    _context: ExecutionContext  # Unified
        ├─ _current_job
        ├─ _jobs (read-only)
        ├─ _current_plugins
        └─ _all_plugins (read-only)
```

**Sorun:** Duplicate data, manual context tracking.

### 2.4 Plugin Communication: PluginServices

**API (Session 12 - Current):**

```python
services.createJob(input_value, input_data) → job_id  # Both modes
services.updateJob(key, value)                        # per_job only
services.updatePlugin(data)                           # per_job only
services.update_status(state, success, message)       # Session 14 addition
```

**Access Control:**

- `per_run`: Can only createJob
- `per_job`: Can createJob, updateJob, updatePlugin

**Session 14 Planı:** Tüm kısıtlamaları kaldır, plugin autonomy.

---

## 3. BENZER PROJELERLE KARŞILAŞTIRMA

### 3.1 FlexGet vs Archiverr

| Özellik                  | FlexGet                                    | Archiverr                          | Değerlendirme            |
| ------------------------ | ------------------------------------------ | ---------------------------------- | ------------------------ |
| **Plugin Types**         | Input/Filter/Output/Metadata/Modify/Daemon | per_run/per_job (stage-based)      | Archiverr daha net ayrım |
| **Config Format**        | YAML (complex nesting)                     | YAML + !include + aliases          | Archiverr daha temiz     |
| **Dependency**           | Implicit (plugin order)                    | Explicit (requires + trigger_rule) | ✅ Archiverr üstün       |
| **State Management**     | Task-local only                            | Global shared state                | ⚠️ Trade-off             |
| **Task Parallelization** | Sequential                                 | Parallel (ThreadPoolExecutor)      | ✅ Archiverr üstün       |
| **Event System**         | Plugin callbacks                           | EventBus (pub/sub)                 | ✅ Archiverr üstün       |
| **Caching**              | Built-in (SQLite)                          | Manual                             | ❌ FlexGet üstün         |

**SONUÇ:** Archiverr dependency management ve parallelization'da üstün, ama caching yok.

### 3.2 Apache Airflow vs Archiverr

| Özellik                 | Airflow       | Archiverr                           | Değerlendirme              |
| ----------------------- | ------------- | ----------------------------------- | -------------------------- |
| **DAG Definition**      | Python code   | YAML manifest                       | Trade-off (config vs code) |
| **Task Communication**  | XCom          | Shared state (job.plugins)          | ⚠️ Similar concept         |
| **Scheduling**          | Cron/interval | Single-run (API for scheduling)     | ❌ Airflow üstün           |
| **Worker Distribution** | Celery/K8s    | ThreadPoolExecutor (single machine) | ❌ Airflow daha scalable   |
| **UI Dashboard**        | Rich web UI   | API-only (no UI yet)                | ❌ Airflow üstün           |
| **Retry Mechanism**     | Built-in      | Manual                              | ❌ Airflow üstün           |
| **Backfill**            | Built-in      | N/A                                 | ❌ Airflow üstün           |

**SONUÇ:** Archiverr single-machine için yeterli, distributed execution yok.

### 3.3 Sonarr/Radarr vs Archiverr

| Özellik              | Sonarr/Radarr       | Archiverr         | Değerlendirme               |
| -------------------- | ------------------- | ----------------- | --------------------------- |
| **Language**         | C# (.NET)           | Python            | Trade-off                   |
| **Architecture**     | Monolithic          | Plugin-based      | ✅ Archiverr daha modular   |
| **Configuration**    | UI-based            | Config-file based | Trade-off                   |
| **Media Management** | Download + Organize | Organize only     | ❌ Sonarr daha feature-rich |
| **Extensibility**    | Limited             | Full plugin SDK   | ✅ Archiverr üstün          |
| **Database**         | SQLite              | MongoDB           | Trade-off                   |

**SONUÇ:** Archiverr daha generic, Sonarr/Radarr media-specific.

---

## 4. SESSION 14 STRATEJİSİ İNCELEMESİ

### 4.1 Session 14 Hedefleri (AI/session_14_strategy/)

#### ✅ TAMAMLANAN:

1. **Plugin Autonomy:** `update_status()` eklendi (PluginServices'da mevcut)
2. **Config System:** !include ve alias sistemi çalışıyor
3. **Event Bus:** Tam entegre
4. **Dependency Resolution:** `requires` + `trigger_rule` çalışıyor
5. **FS Lock:** Static path validation yapılıyor

#### ⚠️ KISMEN TAMAMLANAN:

1. **State Normalization:** 6 → 3 object migration BAŞLAMADI
   - ExecutionContext sınıfı mevcut ama kullanılmıyor
   - manager.py hala 6 object kullanıyor
2. **Naming Consistency:** execution/run, match/job ikilemesi devam ediyor
   - API'de hem `/executions` hem `/runs` var
   - Kod içinde karışık kullanım

#### ❌ TAMAMLANMAYAN:

1. **Legacy Code Deletion:**
   - `api/v1/executions/` hala mevcut
   - `api/v1/matches/` hala mevcut
   - `api/v1/versioning/` (unused commits) hala mevcut
   - `core/tasks/` klasörü kullanılmıyor mu? (incele) 
2. **Access Control Removal:** Per_run/per_job kısıtlamaları hala aktif
3. **Debugger → logging:** Custom debugger hala kullanılıyor
4. **MockPersistence:** Kaldırıldı mı? (kontrol et)

### 4.2 Session 14 Tamamlanma Oranı: %40

| Kategori             | Durum      | Oran    |
| -------------------- | ---------- | ------- |
| Plugin Autonomy      | Tamamlandı | 100%    |
| Config System        | Tamamlandı | 100%    |
| Event System         | Tamamlandı | 100%    |
| State Normalization  | Başlanmadı | 0%      |
| Naming Consistency   | Başlanmadı | 0%      |
| Legacy Deletion      | Kısmen     | 30%     |
| Access Control       | Başlanmadı | 0%      |
| Debugger Replacement | Başlanmadı | 0%      |
| **GENEL**            |            | **40%** |

---

## 5. TASKER PLUGIN OUTPUT BUG ANALİZİ

### 5.1 Bug Tanımı

**Sorun:** output/run\_\*.json dosyalarında `output.values` ve `output.data` boş.

**Kök Neden:** Tasker plugin execute() metodunda job.output'a yazmıyor.

### 5.2 Bug Lokasyonu

```python
# plugins/tasker/plugin.py:94-126 (ÖNCE)
def execute(self, job, services):
    # ...
    for task in self.tasks:
        result = self._execute_task(task, context, job)
        if result and result.get('type') == 'save':
            output_values.append(result['destination'])

    # ❌ HATA: Sadece return ediyor, job.output'a yazmıyor
    return {
        'success': True,
        'tasks': task_results,
        'values': output_values  # ← Kaybolur
    }
```

### 5.3 Fix Uygulandı

```python
# plugins/tasker/plugin.py:104-116 (SONRA)
# Write to job.output via services (Session 12 pattern)
if output_values:
    services.updateJob("output.values", output_values)

if task_results:
    services.updateJob("output.data", {"tasks": task_results})

# Also store in plugin data
services.updatePlugin({
    "tasks": task_results,
    "output_values": output_values
})
```

**Status:** ✅ FIX EDİLDİ (Bu session'da)

---

## 6. KULLANILMAYAN/GEREKSİZ DOSYALAR

### 6.1 Kesin Silinmesi Gerekenler

```bash
# Legacy API endpoints (duplicate)
rm -rf src/archiverr/api/v1/executions/     # Duplicate of runs/
rm -rf src/archiverr/api/v1/matches/        # Duplicate of jobs/
rm -rf src/archiverr/api/v1/versioning/     # Git-style commits (unused)

# Legacy CLI
rm src/archiverr/cli/main.py                # Moved to __main__.py

# MockPersistence (test-only, production kullanmıyor)
# KONTROL ET: Hala var mı?
find . -name "mock.py" -path "*/database/*"
```

### 6.2 İncelenmesi Gerekenler

```bash
# Kullanılıyor mu?
src/archiverr/core/tasks/                   # Task system (3 files)
src/archiverr/infrastructure/repositories/  # 5 repository (hepsi kullanılıyor mu?)

# Birleştirilmeli mi?
src/archiverr/plugins/file-reader/          # Test plugin
src/archiverr/plugins/mock_test/            # Mock plugin
```

### 6.3 Küçük Dosyalar (Birleştirme Adayı)

| Dosya                      | Satır | Öneri                           |
| -------------------------- | ----- | ------------------------------- |
| state/context.py           | ~80   | manager.py'ye birleştirilebilir |
| models/response_builder.py | ~300  | api/schemas.py'ye taşınabilir   |
| core/exceptions.py         | ~150  | İyi ayrılmış, tut               |

---

## 7. YAZILIM MİMARİSİ DEĞERLENDİRMESİ

### 7.1 Clean Architecture Uyumu: 7/10

**İyi Yanlar:**

- ✅ Dependency Injection (EventBus, StateManager, Debugger)
- ✅ Interface-based design (PersistenceInterface)
- ✅ Separation of Concerns (API, Core, Infrastructure ayrımı)
- ✅ Plugin isolation (plugin SDK ile plugin'ler core'dan bağımsız)

**İyileştirilebilir:**

- ⚠️ State management core'dan sızdı (plugin.updateJob direkt state'e yazıyor)
- ⚠️ Debugger utility'den core'a coupling (logging'e geçilmeli)
- ⚠️ Config normalization katmanı karmaşık (3 format support)

### 7.2 SOLID Prensipleri: 6/10

**S - Single Responsibility:** ✅ İyi

- Orchestrator: run lifecycle
- StageExecutor: stage execution
- PluginServices: plugin communication

**O - Open/Closed:** ✅ Mükemmel

- Plugin sistemi tam extensible, modification yok

**L - Liskov Substitution:** ✅ İyi

- PersistenceInterface implementation'ları değiştirilebilir

**I - Interface Segregation:** ⚠️ Orta

- PluginServices çok metod var, belki split edilmeli

**D - Dependency Inversion:** ✅ Mükemmel

- Tüm core logic interface'lere bağımlı

### 7.3 Design Patterns Kullanımı

| Pattern             | Kullanım Yeri        | Kalite                     |
| ------------------- | -------------------- | -------------------------- |
| **Factory**         | build_orchestrator() | ✅ Excellent               |
| **Registry**        | PluginRegistry       | ✅ Excellent               |
| **Strategy**        | Plugin execution     | ✅ Excellent               |
| **Observer**        | EventBus             | ✅ Excellent               |
| **Singleton**       | GlobalStateManager   | ⚠️ Implicit (module-level) |
| **Builder**         | Config loading       | ✅ Good                    |
| **Adapter**         | Database interface   | ✅ Good                    |
| **Template Method** | Plugin.execute()     | ✅ Good                    |

---

## 8. PERFORMANSfVE ÖLÇEKLENEBİLİRLİK

### 8.1 Performans Profili

**Güçlü Yönler:**

- ✅ Parallel plugin execution (ThreadPoolExecutor)
- ✅ Dependency-based optimization (skip satisfied plugins)
- ✅ Config caching (!include files cached)

**Darboğazlar:**

- ❌ Single-machine limitation (no distributed workers)
- ❌ No caching for external API calls (TMDB, TVDB her seferinde fetch)
- ❌ MongoDB write-heavy (her plugin sonucu save)

### 8.2 Scalability Analizi

| Boyut               | Current Limit         | Bottleneck          | Fix               |
| ------------------- | --------------------- | ------------------- | ----------------- |
| **Concurrent Jobs** | ThreadPool size (~10) | Python GIL          | Celery workers    |
| **Job Count**       | Memory (~10K jobs)    | In-memory state     | Stream processing |
| **Plugin Count**    | Unlimited             | Plugin loading time | Lazy loading      |
| **Config Size**     | ~1MB                  | YAML parsing        | Binary format     |

**Sonuç:** 1000 job/day için yeterli, 100K+ için refactor gerekli.

---

## 9. ÖNERİLER VE ROADMAP

### 9.1 Kritik Öncelikler (0-2 Hafta)

1. **✅ DONE: Tasker output bug** (Bu session'da düzeltildi)
2. **Legacy endpoint cleanup**
   ```bash
   rm -rf api/v1/executions api/v1/matches api/v1/versioning
   ```
3. **Naming consistency**
   ```python
   # Global find-replace
   execution → run
   match → job
   ```

### 9.2 Orta Öncelikler (2-4 Hafta)

4. **State normalization**
   ```python
   # 6 object → 3 object migration
   GlobalStateManager:
       run, config, context
   ```
5. **Debugger → logging**
   ```python
   # Replace custom debugger with stdlib logging
   import logging
   logger = logging.getLogger(__name__)
   ```
6. **Access control removal**
   ```python
   # Remove per_run/per_job restrictions
   # All plugins can access all state
   ```

### 9.3 Uzun Vadeli (1-3 Ay)

7. **Caching layer** (FlexGet-inspired)
   ```python
   # SQLite cache for TMDB/TVDB responses
   cache.get_or_fetch(tmdb_id, fetch_func)
   ```
8. **UI Dashboard** (Airflow-inspired)
   ```
   - Run visualization
   - Plugin dependency graph
   - Real-time status updates (WebSocket)
   ```
9. **Distributed workers** (Optional)
   ```python
   # Celery integration for scaling
   # Multi-machine job processing
   ```

### 9.4 Session 14 Completion Plan

**Kalan İşler (Session 14 hedeflerinden):**

| Task                   | Effort | Priority |
| ---------------------- | ------ | -------- |
| State normalization    | 5 days | HIGH     |
| Naming consistency     | 2 days | HIGH     |
| Legacy deletion        | 1 day  | HIGH     |
| Access control removal | 3 days | MEDIUM   |
| Debugger replacement   | 2 days | MEDIUM   |

**Tahmini Süre:** 2-3 hafta

---

## 10. ENDÜSTRİ STANDARTLARINA UYUM

### 10.1 Python Best Practices

| Kriter             | Durum                                   | Skor |
| ------------------ | --------------------------------------- | ---- |
| **Type Hints**     | Partial (core'da var, plugin'lerde yok) | 6/10 |
| **Docstrings**     | Good (çoğu function'da var)             | 8/10 |
| **PEP 8**          | Excellent                               | 9/10 |
| **Error Handling** | Good (custom exceptions)                | 8/10 |
| **Testing**        | Exists (tests/ klasörü)                 | ?/10 |

### 10.2 Workflow Orchestration Standards

**FlexGet/Airflow ile Karşılaştırma:**

| Özellik             | Endüstri Standardı | Archiverr                  | Gap      |
| ------------------- | ------------------ | -------------------------- | -------- |
| **Config-driven**   | ✅ YAML            | ✅ YAML + !include         | ✅ Match |
| **Plugin system**   | ✅ Dynamic loading | ✅ Manifest-based          | ✅ Match |
| **Dependency mgmt** | ✅ Explicit deps   | ✅ requires + trigger_rule | ✅ Match |
| **Parallelization** | ✅ Multi-worker    | ⚠️ ThreadPool only         | ❌ Gap   |
| **Retry mechanism** | ✅ Built-in        | ❌ Manual                  | ❌ Gap   |
| **Caching**         | ✅ Built-in        | ❌ None                    | ❌ Gap   |
| **UI Dashboard**    | ✅ Web UI          | ❌ API only                | ❌ Gap   |
| **Scheduling**      | ✅ Cron/interval   | ❌ Single-run              | ❌ Gap   |

**Sonuç:** Core functionality match, ama production features eksik.

---

## 11. SONUÇ VE DEĞERLENDİRME

### 11.1 Proje Maturity Level: **Beta (Pre-1.0)**

**Gerekçe:**

- ✅ Core functionality çalışıyor
- ✅ Plugin sistemi stabil
- ⚠️ Naming inconsistency var
- ⚠️ State management refactor gerekli
- ❌ Production features eksik (caching, retry, scheduling)

### 11.2 1.0 Release İçin Gerekenler

**Must-Have:**

1. ✅ Tasker output bug (Fixed)
2. ❌ Naming consistency (execution → run, match → job)
3. ❌ Legacy endpoint cleanup
4. ❌ State normalization (6 → 3 objects)
5. ❌ Documentation (README, PLUGIN_SDK)

**Nice-to-Have:** 6. ❌ Caching layer 7. ❌ Retry mechanism 8. ❌ Web UI

**Tahmini 1.0 Süresi:** 4-6 hafta

### 11.3 Güçlü Yönler (Korunması Gerekenler)

1. **Plugin Architecture:** Dependency-aware, stage-based execution ✅
2. **Config System:** !include + alias sistemi FlexGet'ten üstün ✅
3. **Event-Driven:** Loose coupling, extensibility ✅
4. **API-First:** FastAPI integration, versioned endpoints ✅
5. **Type Safety:** Dataclasses, type hints (partial) ✅

### 11.4 Zayıf Yönler (Düzeltilmesi Gerekenler)

1. **State Management:** 6 global object complexity ❌
2. **Naming:** execution/run, match/job inconsistency ❌
3. **Custom Debugger:** stdlib logging kullanılmalı ❌
4. **Access Control:** Gereksiz kısıtlamalar ❌
5. **Legacy Code:** Pre-release için backward compat gereksiz ❌

---

## 12. TASKER PLUGIN OUTPUT FIX DETAYI

### 12.1 Fix Lokasyonu

- **Dosya:** `src/archiverr/plugins/tasker/plugin.py`
- **Satırlar:** 104-116 (eklendi)
- **Tarih:** 10 Aralık 2024

### 12.2 Fix Detayı

**Eklenen Kod:**

```python
# Write to job.output via services (Session 12 pattern)
if output_values:
    services.updateJob("output.values", output_values)

if task_results:
    # Store task results in output.data under 'tasks' key
    services.updateJob("output.data", {"tasks": task_results})

# Also store in plugin data (plugin.tasker.data)
services.updatePlugin({
    "tasks": task_results,
    "output_values": output_values
})
```

### 12.3 Beklenen Sonuç

**output/run\_\*.json içinde:**

```json
{
  "jobs": [{
    "output": {
      "values": ["/srv/archive/Friends/s01/Friends s01e02.mkv"],
      "data": {
        "tasks": {
          "save_to_archive": {
            "type": "save",
            "success": true,
            "destination": "/srv/archive/Friends/s01/Friends s01e02.mkv"
          }
        }
      }
    },
    "plugins": {
      "tasker": {
        "status": {...},
        "data": {
          "tasks": {...},
          "output_values": [...]
        }
      }
    }
  }]
}
```

---

**SON GÜNCELLEME:** 10 Aralık 2024  
**ANALİZ EDEN:** AI Session 15  
**SONRAKI ADIM:** Session 14 roadmap tamamlama
