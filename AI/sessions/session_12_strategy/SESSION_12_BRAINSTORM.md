# SESSION 12 BRAINSTORM

```yaml
tarih: 2024-12-08
durum: critical_decisions
amac: Strategy oncesi temel kararlarin netlesmesi
```

---

## 🔴 KRİTİK KARARLAR

### 1. PLUGIN DATA YAPISI

```yaml
# ❌ YANLIŞ (eski düşünce)
plugin:
  tmdb:
    status: {...}
    movie:           # Direkt kök seviyede
      title: Movie

# ✅ DOĞRU (yeni karar)
plugin:
  tmdb:
    status: {...}
    data:            # HER ŞEY data içinde
      movie:
        title: Movie
```

**SEBEP**:
- Plugin'in kendi eklediği herşey `data` içinde
- `status` gibi sistem alanları ile çakışma riski yok
- Veri yapısı temiz ve güvenli
- Kullanıcı zorlanır ama alias ile çözer

**ERİŞİM**:
```yaml
# Template'de
{{ plugin.tmdb.data.movie.title }}

# Alias ile kolaylaştırma
aliases:
  m: plugin.tmdb.data.movie
# Sonra: {{ m.title }}
```

**ŞEMA**:
```
plugin.{name}
├── status (sistem alanı)
│   ├── state
│   ├── success
│   └── duration_ms
└── data (plugin alanı)
    └── {plugin'in kendi verisi}
```

---

### 2. FS LOCK - SADECE STATİK PATH

```yaml
# ✅ İZİN VERİLEN
fs_lock:
  - /downloads/movies
  - /srv/archive

# ❌ YASAK - Config variable bile yasak
fs_lock:
  - "{{config.archive_path}}"    # YASAK
  - "{{job.input.value}}"        # YASAK
```

**SEBEP**:
- Dependency problemleri çıkar
- Conflict detection karmaşıklaşır
- Şu an için gereksiz
- Validation error ver geç

**KURAL**:
```
FS lock path'te HİÇBİR değişken olamaz.
Sadece hardcoded static path.
İhlal = Validation error at startup.
```

---

### 3. FAIL/SUCCESS SEMANTİĞİ - SADECE PLUGIN BAZLI

```yaml
# 🔴 KRİTİK KARAR
# fail/success SADECE plugin ve plugins için geçerli
# Diğer state'ler (run, job, config) için YASAK
```

**SEBEP - Gerçek Hayat Analizi**:
```
SORUN 1: Run state için fail/success?
- run.status:success kullanılırsa ne olur?
- Run sonuna kadar mı beklenecek?
- Run içindeki bir değer için trigger rule anlamsız

SORUN 2: Job state için fail/success?
- job.output:success kullanılırsa ne olur?
- Job tamamlanana kadar mı beklenecek?
- Job stages arası trigger rule karmaşık

SORUN 3: Config için fail/success?
- Config zaten frozen, fail/success anlamsız
- Değer var ya da yok

ÇÖZÜM:
- fail/success SADECE plugin bazlı
- Plugin = asenkron execution unit
- Trigger rule = plugin bağımlılığı için
- Diğer state'ler = direkt değer kontrolü
```

**İZİN VERİLEN KULLANIM**:

#### 1. Plugin Bazlı (fail/success OK)
```yaml
requires:
  - plugin.tmdb.data.movie:success     # ✅ Plugin için OK
  - plugin.renamer.data.parsed:fail    # ✅ Plugin için OK
  - plugins[0].tmdb.data.movie:success # ✅ Plugins için OK
```

#### 2. Primitive Değer Kontrolü (exact match)
```yaml
requires:
  - run.total_jobs:10                  # ✅ int
  - config.options.debug:true          # ✅ boolean
  - job.input.value:"/path/to/file"    # ✅ string
  - run.status.state:"completed"       # ✅ string
  - job.status.state:"running"         # ✅ string
```

**YASAK KULLANIM**:
```yaml
requires:
  - run.status:success                 # ❌ Run için fail/success yok
  - job.status:success                 # ❌ Job için fail/success yok
  - job.output:success                 # ❌ Job alt field için yok
  - jobs[0]:success                    # ❌ Job için fail/success yok
  - run:success                        # ❌ Run için fail/success yok
```

**PLUGIN LIFECYCLE (success/fail aktif)**:
```
┌─────────────────────────────────────────────────┐
│  PLUGIN LIFECYCLE & VALUE STATE                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  PENDING → value = null (henüz başlamadı)      │
│     ↓                                           │
│  RUNNING → value = null (çalışıyor)            │
│     ↓                                           │
│  ┌─────────┬──────────┬──────────┐             │
│  ↓         ↓          ↓          ↓              │
│ SUCCESS  FAILED   SKIPPED   (states)            │
│ value=X  value=∅  value=∅                       │
│  :success :fail    :fail                        │
│                                                 │
│  :success = plugin.status.success == true       │
│  :fail    = plugin.status.success == false      │
│           = (failed OR skipped OR stage bitti)  │
└─────────────────────────────────────────────────┘
```

**TRIGGER RULE MANTIĞI**:
```python
def evaluate_requirement(path: str, expected: str):
    """
    path = "plugin.tmdb.data.movie"
    expected = "success" OR "fail" OR actual_value
    """
    
    # 1. Check if it's a plugin path
    if path.startswith("plugin.") or path.startswith("plugins"):
        # Plugin bazlı - success/fail allowed
        
        if expected == "success":
            # Check plugin status
            plugin_status = get_plugin_status(path)
            if plugin_status.state == "pending":
                return WAIT
            if plugin_status.success == False:
                return FAIL
            # Check value
            value = resolve_path(path)
            return SUCCESS if value else FAIL
        
        elif expected == "fail":
            plugin_status = get_plugin_status(path)
            if plugin_status.state == "pending":
                return WAIT
            return SUCCESS if plugin_status.success == False else FAIL
        
        else:
            # Exact value match
            value = resolve_path(path)
            return SUCCESS if value == expected else FAIL
    
    else:
        # Non-plugin path - ONLY exact value match
        if expected in ["success", "fail"]:
            raise ValidationError(
                f"success/fail only allowed for plugin paths: {path}"
            )
        
        # Primitive value check
        value = resolve_path(path)
        return SUCCESS if value == expected else FAIL
```

**ÖZET KURAL**:
```
┌──────────────────────────────────────────────────┐
│ TRIGGER RULE VALUE TYPES                         │
├──────────────────────────────────────────────────┤
│                                                  │
│ plugin.* veya plugins.*:                         │
│   ├── :success  ✅ (plugin execution success)   │
│   ├── :fail     ✅ (plugin execution failed)    │
│   └── :value    ✅ (exact match)                 │
│                                                  │
│ run.*, job.*, jobs.*, config.*:                  │
│   ├── :success  ❌ YASAK                        │
│   ├── :fail     ❌ YASAK                        │
│   └── :value    ✅ (exact match only)            │
│                                                  │
│ Allowed primitives:                              │
│   ├── int       (run.total_jobs:10)             │
│   ├── boolean   (config.debug:true)             │
│   ├── string    (job.input.value:"/path")       │
│   └── object    (jobs[0].status:{...})          │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

### 4. ALIAS TANIMI - HER YERDE

```yaml
# Config root
aliases:
  m: plugin.tmdb.data.movie

# Herhangi bir wrapper içinde
tmdb:
  aliases:
    movie: plugin.tmdb.data.movie
  api_key: xxx

# Boş satırda bile
scanner:
  targets: [/movies]

aliases:
  scanned: plugin.scanner.data.files

renamer:
  media_type: auto
```

**ÖNEMLI NOT**:
- Manifest ve external yml → Config'e merge olur
- "Her yerde tanımlanabilir" = Config YAML'inin her yerinde
- Jinja2 {% set %} ayrı bir konu (template içi değişken)

**MERGE AKIŞI**:
```
1. manifest.yml → base config
2. user config.yml → merge
3. external ymls → merge
4. Sonuç: Tek bir config tree
5. Bu tree'nin her yerinde alias tanımlanabilir
```

---

### 5. UPDATE METHODS - ID YOK

```python
# ❌ YANLIŞ (ID ile)
services.updateJob(job_id="abc123", key="output.values", value=[...])
services.updatePlugin(plugin_name="tmdb", data={...})

# ✅ DOĞRU (ID yok, current context)
services.updateJob(key="output.values", value=[...])
services.updatePlugin(data={...})
```

**SEBEP**:
- Update edilen her zaman CURRENT job/plugin
- ID gereksiz ve karışıklık yaratır
- Context zaten belli (services internal'da tutuyor)

**YENİ İMZALAR**:
```python
class PluginServices:
    # Job management
    def createJob(self, input_value: str, input_data: Dict) -> str:
        """Create new job, return job_id"""
    
    def updateJob(self, key: str, value: Any) -> None:
        """Update CURRENT job"""
    
    def updatePlugin(self, data: Dict) -> None:
        """Update CURRENT plugin data"""
```

**CONTEXT**:
```python
# Internal olarak tutuluyor
class PluginServices:
    def __init__(self, ..., current_job: JobState, current_plugin_name: str):
        self._current_job = current_job
        self._current_plugin_name = current_plugin_name
    
    def updateJob(self, key, value):
        # Otomatik current job update
        self._state.update_job(self._current_job.id, key, value)
    
    def updatePlugin(self, data):
        # Otomatik current plugin update
        self._state.update_plugin(
            self._current_job.id,
            self._current_plugin_name,
            data
        )
```

---

### 6. PER_RUN AMACI

```yaml
# ❌ YANLIŞ DÜŞÜNCE
"per_run = input plugins için"

# ✅ DOĞRU AMAÇ
"per_run = run seviyesinde işlem yapan herhangi bir plugin"
```

**USE CASE'LER**:
```yaml
# Input plugin (job creator)
scanner:
  run_mode: per_run
  # createJob() kullanır

# Config loader (system plugin)
config_loader:
  run_mode: per_run
  # Hiçbir state değişikliği yapmaz
  # Sadece okur, hazırlar

# Summary reporter (run-level reporter)
run_summary:
  run_mode: per_run
  # Run sonunda çalışır
  # Job'lara dokunmaz
```

**KURAL**:
```
per_run plugins:
- createJob() kullanabilir (job oluşturma)
- State read-only (run, config)
- updateJob, updatePlugin KULLANAMAZ
```

---

## 📐 DATA STRUCTURE ŞEMALARI

### Global State (6 Object)

```
┌───────────────────────────────────────────────────┐
│ GLOBAL STATE                                      │
├───────────────────────────────────────────────────┤
│                                                   │
│ run          → Run metadata                       │
│ ├── id                                            │
│ ├── status                                        │
│ └── config (snapshot)                             │
│                                                   │
│ config       → Frozen config                      │
│ ├── options                                       │
│ ├── aliases                                       │
│ └── {plugin configs}                              │
│                                                   │
│ job          → Current job                        │
│ ├── id                                            │
│ ├── input                                         │
│ ├── output                                        │
│ └── status                                        │
│                                                   │
│ jobs         → All jobs (array)                   │
│ └── [{job}, {job}, ...]                           │
│                                                   │
│ plugin       → Current job's plugins              │
│ ├── {name}                                        │
│ │   ├── status                                    │
│ │   └── data                                      │
│ └── {name}...                                     │
│                                                   │
│ plugins      → All jobs' plugins (array)          │
│ └── [{job_id, plugins}, ...]                      │
│                                                   │
└───────────────────────────────────────────────────┘
```

### Plugin Data Structure

```yaml
plugin:
  tmdb:
    status:              # Sistem alanı
      state: completed
      success: true
      started_at: "..."
      finished_at: "..."
      duration_ms: 800
      error: null
    
    data:                # Plugin alanı
      movie:
        id: 12345
        title: "Movie"
        release_date: "2024-01-15"
        genres: ["Action"]
  
  renamer:
    status:              # Sistem alanı
      state: completed
      success: true
      duration_ms: 200
    
    data:                # Plugin alanı
      parsed:
        movie:
          name: "Movie Name"
          year: 2024
```

### Access Patterns

```jinja2
{# Direkt erişim (uzun) #}
{{ plugin.tmdb.data.movie.title }}

{# Alias ile (kısa) #}
{% set m = plugin.tmdb.data.movie %}
{{ m.title }}

{# Config'de tanımlı alias #}
aliases:
  m: plugin.tmdb.data.movie
  
{# Template'de kullan #}
{{ m.title }}
```

---

## 🔄 EXECUTION FLOW

### Job Lifecycle

```
┌──────────────────────────────────────────────────┐
│ JOB LIFECYCLE                                    │
└──────────────────────────────────────────────────┘

1. PER_RUN PLUGINS
   ↓
   scanner.execute_run(services)
   ├── createJob("/movie1.mkv", {size: 5GB})
   ├── createJob("/movie2.mkv", {size: 3GB})
   └── createJob("/movie3.mkv", {size: 2GB})
   ↓
   3 jobs created

2. JOB QUEUE
   ↓
   [Job1] [Job2] [Job3]
   ↓
   Process each job...

3. JOB EXECUTION (for each job)
   ↓
   ┌─────────────────┐
   │  PARSE STAGE    │
   │  - renamer      │
   └─────────────────┘
   ↓
   ┌─────────────────┐
   │  DATA STAGE     │
   │  - tmdb         │
   │  - ffprobe      │
   └─────────────────┘
   ↓
   ┌─────────────────┐
   │  OUTPUT STAGE   │
   │  - tasker       │
   └─────────────────┘
   ↓
   Job completed

4. NEXT JOB
   ↓
   Continue until queue empty
```

### Plugin Update Flow

```python
# Parse stage: Renamer
def execute(self, job, services):
    parsed = parse_filename(job.input.value)
    
    # Update plugin data
    services.updatePlugin(data={
        "parsed": parsed
    })
    
    # Şimdi state'te:
    # plugin.renamer.data.parsed = {...}

# Data stage: TMDb
def execute(self, job, services):
    # Önceki plugin'den oku
    parsed = job.plugins["renamer"]["data"]["parsed"]
    
    # API call
    movie = fetch_movie(parsed["movie"]["name"])
    
    # Update plugin data
    services.updatePlugin(data={
        "movie": movie
    })
    
    # Şimdi state'te:
    # plugin.tmdb.data.movie = {...}
```

---

## 🎯 TRIGGER RULE MANTIĞI

### State-based Check

```yaml
requires:
  - plugin.tmdb.data.movie:success
```

**Evaluation**:
```python
def check_requirement(path, expected):
    # Parse path: plugin.tmdb.data.movie
    plugin_name = "tmdb"
    value_path = "data.movie"
    
    # Get plugin status
    plugin_status = state.get_plugin_status(plugin_name)
    
    # 1. Check if plugin completed
    if plugin_status.state == "pending":
        return WAIT  # Henüz çalışmadı
    
    # 2. Check if plugin failed
    if plugin_status.success == False:
        return FAIL  # Artık dolmayacak
    
    # 3. Check if value exists
    value = state.get_plugin_value(plugin_name, value_path)
    if value is None:
        return FAIL  # Değer yok
    
    # 4. Success
    if expected == "success":
        return SUCCESS
    elif expected == "fail":
        return FAIL
    else:
        # Exact value match
        return SUCCESS if value == expected else FAIL
```

### Decision Tree - Plugin vs Non-Plugin

```
                    Parse Requirement
                          ↓
          ┌───────────────┴───────────────┐
          ↓                               ↓
    PLUGIN PATH                    NON-PLUGIN PATH
 (plugin.* or plugins.*)         (run.*, job.*, config.*)
          ↓                               ↓
    ┌─────┴─────┐                  Check expected value
    ↓           ↓                         ↓
:success     :fail                ┌───────┴───────┐
    ↓           ↓                 ↓               ↓
Check Plugin                :success/:fail    :actual_value
  Status                            ↓               ↓
    ↓                         VALIDATION        Exact Match
┌───┴───┐                       ERROR              ↓
↓       ↓                                    ┌─────┴─────┐
PENDING OTHER                               ↓           ↓
↓       ↓                                 MATCH      NO MATCH
WAIT    ↓                                   ↓           ↓
    ┌───┴────┐                           SUCCESS      FAIL
    ↓        ↓
success=F  success=T
    ↓        ↓
   FAIL   Check Value
            ↓
       ┌────┴────┐
       ↓         ↓
    value=X   value=∅
       ↓         ↓
    SUCCESS    FAIL
```

**Kritik Fark**:
- **Plugin paths**: success/fail kontrol eder (asenkron execution)
- **Non-plugin paths**: Sadece exact value match (senkron değer)

---

## 📋 IMPLEMENTATION CHECKLİST

### Phase 1: Core Refactoring

- [ ] StateManager: 6 global state
- [ ] Plugin data structure: `plugin.{name}.data.*`
- [ ] PluginServices: ID'siz update methods
- [ ] BasePlugin: Template method pattern

### Phase 2: Trigger System

- [ ] Fail semantiği: pending vs fail
- [ ] State resolver with plugin status check
- [ ] Value matcher: success/fail/exact
- [ ] Trigger rule evaluator

### Phase 3: Validation

- [ ] FS lock: Static path only (no variables)
- [ ] Config merge: Manifest + user + external
- [ ] Alias system: Config tree'de her yerde
- [ ] Schema validation

### Phase 4: Execution

- [ ] Per-run execution (job creation)
- [ ] Job queue management
- [ ] Stage execution (parse/data/output)
- [ ] Error handling: best effort

---

## 🚨 KRİTİK HATIRLATMALAR

### 1. Plugin Data
```
✅ plugin.{name}.data.{field}
❌ plugin.{name}.{field}
```

### 2. FS Lock
```
✅ /static/path
❌ {{config.path}}
❌ {{job.input}}
```

### 3. Fail Semantiği
```
✅ fail = değer artık dolmayacak (plugin failed/skipped)
❌ fail = değer boş (pending de boş olur)
```

### 4. Update Methods
```
✅ updateJob(key, value)
❌ updateJob(job_id, key, value)
```

### 5. Alias Tanımı
```
✅ Config YAML'inin her yerinde
✅ Manifest'te de (config'e merge olur)
❌ Sadece root seviyede
```

---

## 📊 ÖZET TABLO

| Konu | Eski Düşünce | Yeni Karar |
|------|-------------|-----------|
| Plugin data | `plugin.tmdb.movie` | `plugin.tmdb.data.movie` |
| FS lock | Config variable OK | Sadece static path (no variables) |
| Fail/success scope | Tüm state'ler | SADECE plugin/plugins |
| Non-plugin check | success/fail OK | Sadece exact value (primitives) |
| Update | ID ile | ID yok (current context) |
| Per-run | Input için | Genel amaçlı (run-level plugins) |
| Alias | Root seviyede | Config'in her yerinde |

---

**Status**: Brainstorm tamamlandı, strategy hazırlanabilir
**Next**: Bu kararlara göre strategy dosyalarını gözden geçir
