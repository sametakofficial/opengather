# SESSION 12 - EXECUTIVE SUMMARY

```yaml
tarih: 2024-12-08
durum: strategy
onceki_session: session_11 (incomplete, plugin system broken)
hedef: Plugin system refactoring with job queue paradigm
```

---

## PROBLEM STATEMENT

Session 11'deki plugin sistemi yarım kaldı ve sistemin temel felsefesi doğru planlanmadı:
- **Per-run vs per-job** ayrımı kesin değildi
- **Provides/events config erişimi** karmaşıklık yarattı
- **Input stage** mantıksızdı (job içi stage, ama job oluşturan pluginler için)
- **Reflective system** use case daraldı ve gereksiz karmaşıklık ekledi
- **State erişimi** tutarsızdı (plugin.data vs plugin vs plugins)

Sistem çalışmıyor ve **temelden yeniden planlanması gerekiyor**.

---

## SESSION 12 CORE CHANGES

### 1. **Input Stage KALDIRILDI**

```
ESKI: 4 stage (input, parse, data, output)
YENİ: 3 stage (parse, data, output)

SEBEP:
- Input = job oluşturma işlemi
- Job oluşturan pluginler per_run (stage dışı)
- Stage = job içi execution
- Job olmadan stage olamaz
```

**Mantık**: Kum saati analojisi
- Kum saati = Job execution flow (parse → data → output)
- Kum saatine kum dolduran boru = per_run input plugins
- Boru içeride olamaz, dışarıdan kum doldurur

### 2. **Provides ve Events Config Erişimi KALDIRILDI**

```
ESKI: 
  requires:
    - provides.data.parsed
    - events.file.created

YENİ:
  requires:
    - plugin.renamer.data.parsed:success
    - job.input.value:"/path/to/file"
```

**SEBEP**:
- Provides registry gereksiz komplekslik
- Plugin datası direkt state'te erişilebilir
- EventBus zaten var, config'e eklemeye gerek yok
- Trigger rules zaten state-based dependency çözüyor

### 3. **Reflective System KALDIRILDI**

Session 11'de reflective system planlandı ama use case daraldı:
- Sadece çok spesifik senaryolar için
- Karmaşıklık katıyor
- Şu an ihtiyaç yok

### 4. **FS Lock Sistemi (Static Path Only)**

```yaml
fs_lock:
  - /downloads/movies    # ✅ Static path
  - /srv/archive         # ✅ Static path
```

**KURAL**:
- **SADECE static path** (hiç değişken yok)
- `{{config.*}}` YASAK (validation error)
- `{{job.*}}` YASAK (validation error)
- `{{run.*}}` YASAK (validation error)
- Sebep: Dependency problemleri, şu an için gereksiz

### 5. **Satır Bazlı Trigger Rules (Value-based)**

```yaml
# ✅ Plugin için: success/fail kullanılabilir
requires:
  - plugin.renamer.data.parsed:success     # Plugin success
  - plugin.tmdb.data.movie:success         # Plugin success

# ✅ Non-plugin için: sadece exact value
requires:
  - run.total_jobs:10                      # int exact match
  - config.options.debug:true              # boolean exact match
  - job.input.value:"/path"                # string exact match

# ❌ YASAK: Non-plugin için success/fail
# run.status:success     → VALIDATION ERROR
# job.output:success     → VALIDATION ERROR
```

**Semantik**:
- `:success` / `:fail` = SADECE plugin ve plugins için
- Non-plugin paths = Sadece exact value match
- Primitives: int, boolean, string, object

### 6. **Global State: 6 Obje**

```
run      = Run metadata (read-only for all)
config   = Frozen config (read-only for all)
job      = Current job (per_job: read-write, per_run: NO ACCESS)
jobs     = All jobs (per_job: read-only, per_run: NO ACCESS)
plugin   = Current job's plugins (per_job: read-write, per_run: NO ACCESS)
           Plugin data: plugin.{name}.data.*
plugins  = All jobs' plugins (per_job: read-only, per_run: NO ACCESS)
           Plugin data: plugins[i].{name}.data.*
```

**Erişim Kontrolü**:
- **per_run**: Sadece `run` ve `config`
- **per_job**: Hepsine erişim (job, jobs, plugin, plugins, run, config)

### 7. **Plugin Communication: 3 Method (ID Yok)**

```python
# Her iki mod için
createJob(input_value, input_data) -> job_id

# Sadece per_job için (ID YOK, current context)
updateJob(key, value)              # Current job update
updatePlugin(data)                 # Current plugin update
```

**NOT**: ID parametre yok, current context internal'da tutuluyor

**Akış**:
1. Scanner (per_run): `createJob("/path/to/file", {size: 1GB})`
2. Job ID dönülür, ama input.value henüz yok → Job creation aşaması
3. Scanner: `updateJob(job_id, "input.value", "/path/to/file")`
4. Input.value set edildiğinde → Job created, queue'ya eklenir
5. Job execution başlar: parse → data → output stages

### 8. **Alias Sistemi: Her Yerde Tanımlanabilir**

```yaml
# Root config
aliases:
  m: plugin.tmdb.movie

# Manifest içinde
aliases:
  parsed: plugin.renamer.parsed

# External YAML içinde
aliases:
  show: plugin.tmdb.show
```

**Jinja2 her yerde**:
```jinja2
{% set m = plugin.tmdb.movie %}
{{ m.title }} ({{ m.release_date[:4] }})
```

---

## ARCHITECTURE COMPARISON

### Session 11 (Broken)
```
4 stages: input | parse | data | output
Provides: registry-based dependency
Events: config-based subscription
Reflective: complex use cases
State: inconsistent (plugin.data vs plugins)
Input plugins: stage içinde (mantıksız)
```

### Session 12 (Fixed)
```
3 stages: parse | data | output
Per-run: job creation, stage dışı
Per-job: job processing, stage içi
State: 6 global object (run, config, job, jobs, plugin, plugins)
Trigger rules: state-based + value-based
FS lock: path-based conflict detection
Plugin methods: createJob, updateJob, updatePlugin
```

---

## EXECUTION FLOW

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR START                    │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                  PER-RUN PLUGINS                         │
│  (No stage, runs once per run)                          │
│                                                          │
│  Scanner (per_run):                                      │
│    1. Scan /downloads/movies                            │
│    2. createJob("/path/to/movie1.mkv", {size: 5GB})    │
│    3. createJob("/path/to/movie2.mkv", {size: 3GB})    │
│    4. updateJob(job_id, "input.value", path)           │
│    5. updatePlugin("scanner", {scanned_count: 2})      │
│                                                          │
│  Result: 2 jobs created and queued                      │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              JOB QUEUE (2 jobs pending)                  │
└─────────────────────────────────────────────────────────┘
                           ↓
         ┌─────────────────┴─────────────────┐
         ↓                                    ↓
    Job 1: movie1.mkv                    Job 2: movie2.mkv
         ↓                                    ↓
┌─────────────────────────────────────────────────────────┐
│                    PARSE STAGE                           │
│  (per_job plugins, runs for each job)                   │
│                                                          │
│  Renamer (parse stage):                                 │
│    - Parse filename: "Movie.Name.2024.1080p.mkv"       │
│    - updatePlugin("renamer", {parsed: {movie: {...}}}) │
│                                                          │
│  Trigger Rule Check: No requires → execute immediately  │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                    DATA STAGE                            │
│  (per_job plugins, parallel if no dependencies)         │
│                                                          │
│  TMDb (data stage):                                      │
│    requires: [plugin.renamer.parsed]                    │
│    - Trigger rule: all_success                          │
│    - Fetch metadata from TMDb API                       │
│    - updatePlugin("tmdb", {movie: {...}})               │
│                                                          │
│  FFprobe (data stage):                                   │
│    requires: []                                          │
│    - Parallel with TMDb (no dependency)                 │
│    - Probe video file                                   │
│    - updatePlugin("ffprobe", {video: {...}})            │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                   OUTPUT STAGE                           │
│  (per_job plugins, final stage)                         │
│                                                          │
│  Tasker (output stage):                                  │
│    requires: [plugin.tmdb, plugin.renamer]              │
│    fs_lock: ["{{config.archive_path}}"]                 │
│    - Render templates with plugin data                  │
│    - Execute tasks (save, print, etc.)                  │
│    - updateJob(job_id, "output.values", paths)         │
│    - updatePlugin("tasker", {tasks: {...}})             │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│                   JOB COMPLETED                          │
│  - Update job status: completed                         │
│  - Persist to MongoDB                                   │
│  - Emit job.completed event                             │
└─────────────────────────────────────────────────────────┘
                           ↓
                (Next job in queue)
```

---

## KEY DECISIONS

### 1. Stage Count: 3 (not 4)
Input stage kaldırıldı çünkü job oluşturan pluginler stage dışı (per_run).

### 2. State Access Matrix

| Plugin Type | run | config | job | jobs | plugin | plugins |
|-------------|-----|--------|-----|------|--------|---------|
| per_run     | ✅  | ✅     | ❌  | ❌   | ❌     | ❌      |
| per_job     | ✅  | ✅     | ✅  | ✅   | ✅     | ✅      |

### 3. Plugin Methods

| Method | per_run | per_job | Purpose |
|--------|---------|---------|---------|
| createJob | ✅ | ✅ | Create new job |
| updateJob | ❌ | ✅ | Update job state |
| updatePlugin | ❌ | ✅ | Update plugin data |

### 4. Trigger Rule Types

```yaml
# Standard (Airflow-based)
trigger_rule: all_success | one_success | all_done | all_fail | none_fail

# Value-based (inline) - Plugin için success/fail
requires:
  - plugin.tmdb.data.movie:success   # ✅ Plugin için OK
  - run.total_jobs:10                # ✅ Exact match (int)
  - config.debug:true                # ✅ Exact match (boolean)
```

### 5. FS Lock Rules

```yaml
# ✅ ALLOWED (static path only)
fs_lock:
  - /data/archive
  - /srv/archive

# ❌ FORBIDDEN (any variables)
fs_lock:
  - "{{config.output_path}}"  # ❌ YASAK
  - "{{job.input.value}}"    # ❌ YASAK
  - "{{plugin.tmdb.id}}"     # ❌ YASAK
```

---

## IMPLEMENTATION PRIORITIES

### Phase 1: Core Refactoring
1. Global state restructure (6 objects)
2. Plugin communication methods (createJob, updateJob, updatePlugin)
3. Stage system (3 stages, per_run outside)
4. Trigger rule manager

### Phase 2: Advanced Features
1. FS lock system with conflict detection
2. Value-based trigger rules (satır bazlı)
3. Parallel execution within stages
4. Job queue management

### Phase 3: Optimization
1. MongoDB persistence optimization
2. Plugin lifecycle management
3. Error handling and recovery
4. Performance monitoring

---

## SESSION 11 vs SESSION 12

| Aspect | Session 11 | Session 12 |
|--------|-----------|-----------|
| Stages | 4 (input, parse, data, output) | 3 (parse, data, output) |
| Input plugins | Stage içinde | per_run, stage dışı |
| Provides | Registry-based | Kaldırıldı |
| Events config | Config-based | Kaldırıldı (EventBus var) |
| Reflective | Planlandı | Kaldırıldı |
| State objects | 4 (run, job, jobs, config) | 6 (run, config, job, jobs, plugin, plugins) |
| Plugin methods | Belirsiz | 3 (createJob, updateJob, updatePlugin) |
| Trigger rules | Standard only | Standard + value-based |
| FS lock | Yok | Path-based with conflict detection |
| Alias system | Sadece root | Her yerde (manifest, external) |

---

## CRITICAL RULES

### ⚠️ Uyulması Gereken Kurallar

1. **Per-run plugins CANNOT access**: job, jobs, plugin, plugins
2. **Input.value set = Job creation**: Job queue'ya eklenir
3. **FS lock**: Sadece static path, HİÇBİR değişken YASAK
4. **Trigger rules success/fail**: SADECE plugin ve plugins için
5. **Trigger rules primitives**: Non-plugin için sadece exact value (int/bool/string/object)
6. **Plugin data location**: `plugin.{name}.data.*` (HER ŞEY data içinde)
7. **Update methods**: ID yok (updateJob(key, value), updatePlugin(data))
8. **Job execution**: Per-run tamamlandıktan SONRA job queue işlenir
9. **Stage sırası**: ALWAYS parse → data → output
10. **Alias tanımı**: Config YAML'inin her yerinde

---

## DOCUMENT STRUCTURE

Bu strategy 7 dosyadan oluşuyor:

1. **01_EXECUTIVE_SUMMARY.md** ← (Bu dosya)
2. **02_GLOBAL_STATE_ARCHITECTURE.md** - 6 global state detayı
3. **03_PLUGIN_SYSTEM_REFACTORING.md** - Plugin communication, methods
4. **04_TRIGGER_RULE_SYSTEM.md** - State-based + value-based trigger rules
5. **05_JOB_LIFECYCLE_AND_EXECUTION.md** - Job queue, stages, execution flow
6. **06_FILE_STRUCTURE_AND_MODULES.md** - Dosya yapısı, modüller, organizasyon
7. **07_IMPLEMENTATION_PATTERNS.md** - Code patterns, best practices

---

## IMPORTANT NOTES

> **BU STRATEGY BİR PLANLAMA DOKÜMANIDIR**
> 
> - Mevcut kodu analiz ederek hazırlandı
> - Implementation sırasında mevcut kod yapısına uyarlanmalı
> - Dosya yapısı ve isimlendirme öneri niteliğinde
> - Kod örnekleri mantığı göstermek içindir, direkt kopyalanmaz
> - Session 11'deki bozuk sistemden öğrenildi, temizlendi

> **SESSION 11 REFERANSI**
> 
> - Session 11 dosyaları sadece mevcut durumu anlamak için
> - Session 12 planına her zaman öncelik ver
> - Session 11'deki plugin sistemi yarım ve broken

---

**Son Güncelleme**: 2024-12-08  
**Status**: Strategy Planning  
**Next**: Implementation başlangıcı
