# PLUGIN SYSTEM & SERVICES

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/01, 02, 03, 04, 09, 10
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- always trigger_rule KALDIRILDI (all_done ile ayni)
- trigger_rules: 5 adet (all_success, one_success, all_done, all_fail, none_fail)
- provides: input.value, input.data, output.values, output.data eklendi
- lockable provides: fs.write, fs.delete, fs.move, fs.hardlink, fs.symlink (5 adet)
- non-lockable: fs.copy, fs.mkdir, fs.chmod, state.update, job.create
- provides icinde job.* ve run.* YASAK (validation sirasinda bilinmiyor)
```

---

## 1. STAGE SISTEMI (4 STAGE)

```
+----------------------------------------------------------+
|                    4 STAGE SISTEMI                        |
+----------------------------------------------------------+
|                                                           |
|  STAGE       ACIKLAMA                 ORNEKLER            |
|  -----       --------                 --------            |
|  input       Veri girisi, job olustur scanner, file-reader|
|  parse       Dosya adi cozumle        renamer             |
|  data        External data al         tmdb, tvdb, ffprobe |
|  output      Sonuc uret               tasker, rclone      |
|                                                           |
+----------------------------------------------------------+

WEB UI KATEGORILERI:
  INPUT  = input + parse
  OUTPUT = data + output
```

### Stage Execution Flow

```
                    ORCHESTRATOR
                         |
                         v
+----------------------------------------------------------+
|                    STAGE LOOP                             |
|                                                           |
|  for stage in [INPUT, PARSE, DATA, OUTPUT]:           |
|      plugins = get_plugins_by_stage(stage)               |
|      sorted = topological_sort_by_requires(plugins)      |
|      execute_stage(sorted)                               |
|                                                           |
+----------------------------------------------------------+
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
    +-------+        +--------+        +-------+
    | INPUT |        | PARSE  |        | DATA  |
    +-------+        +--------+        +-------+
        |                |                |
        v                v                v
    per_run          per_job           per_job
    scanner          renamer           tmdb,tvdb
        |                |                |
        v                v                v
    job.create       state.update      http.request
                                       state.update
                                          |
                                          v
                                      +-------+
                                      | OUTPUT|
                                      +-------+
                                          |
                                          v
                                      per_job
                                      tasker
                                          |
                                          v
                                      fs.write
```

---

## 2. MANIFEST SCHEMA

```yaml
# plugins/{name}/manifest.yml
name: string # Unique identifier
version: string # Semver
description: string # Optional

# Stage & Execution
stage: input | parse | data | output
# mode: implicit (per_run for input, per_job for others)

# Dependency (EXPLICIT PREFIX)
requires: List[string] # provides.*, job.*, events.* prefix ZORUNLU
provides: List[string] # Teknik etki bazli (fs.*, http.*, job.*, state.*, process.*)

# Execution behavior
trigger_rule: all_success | one_success | all_done | all_fail | none_fail
# v2: always KALDIRILDI (all_done ile ayni)
reactive: bool # Default: false

# Implementation
class_name: string
entry_point: string # Default: client.py
config_schema: Dict # Optional
```

### Manifest Ornekleri

```yaml
# plugins/scanner/manifest.yml
name: scanner
version: 1.0.0
stage: input
requires: []
provides:
  - job.create
  - fs.read
  - input.value     # v2: eklendi
  - input.data      # v2: eklendi
class_name: ScannerPlugin

# plugins/renamer/manifest.yml
name: renamer
version: 1.0.0
stage: parse
requires: []
provides:
  - state.update
class_name: RenamerPlugin

# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
stage: data
requires:
  - job.plugins.renamer.parsed            # EXPLICIT prefix
provides:
  - http.request
  - state.update
class_name: TMDbPlugin

# plugins/tasker/manifest.yml
name: tasker
version: 1.0.0
stage: output
requires:
  - provides.state.update                 # EXPLICIT prefix
provides:
  - fs.write
  - fs.write:{{config.tasker.save_path}}  # v2: lockable path
  - output.values   # v2: eklendi
  - output.data     # v2: eklendi
class_name: TaskerPlugin
```

---

## 3. PROVIDES SISTEMI

```
+----------------------------------------------------------+
|              PROVIDES FELSEFESI                           |
+----------------------------------------------------------+
|                                                           |
|  PROVIDES = TEKNIK ETKI (gercek sistem etkisi)           |
|                                                           |
|  DOGRU:  fs.write, http.request, job.create              |
|  YANLIS: metadata.movie (kategori, etki yok)             |
|  YANLIS: notification.sent (belirsiz)                    |
|                                                           |
|  KURAL: Disk I/O, Network, Process gibi olculebilir      |
|         teknik etki olmali                               |
|                                                           |
+----------------------------------------------------------+
```

### Standart Provides Listesi

```
+----------------------------------------------------------+
|                 STANDART PROVIDES                         |
+----------------------------------------------------------+
|                                                           |
|  FS (Filesystem - disk etkisi)                           |
|  fs.read            Dosya okudu                          |
|  fs.write           Dosya yazdi                          |
|  fs.delete          Dosya sildi                          |
|  fs.move            Dosya tasidi                         |
|  fs.copy            Dosya kopyaladi                      |
|  fs.hardlink        Hardlink olusturdu                   |
|  fs.symlink         Symlink olusturdu                    |
|  fs.mkdir           Dizin olusturdu                      |
|                                                           |
|  HTTP (Network - bandwidth etkisi)                       |
|  http.request       HTTP istegi yapti                    |
|                                                           |
|  JOB (Job lifecycle)                                     |
|  job.create         Yeni job olusturdu                   |
|                                                           |
|  STATE (State operations)                                |
|  state.update       State guncelledi                     |
|                                                           |
|  PROCESS (External process - CPU etkisi)                 |
|  process.spawn      Dis process calistirdi               |
|  process.exec       Komut execute etti                   |
|                                                           |
+----------------------------------------------------------+

KALDIRILAN (kategori bazli, teknik etki yok):
  - metadata.*        # Sadece state.update kullan
  - notification.*    # Belirsiz, spesifik kullan
  - http.response     # http.request yeterli
  - data.*            # Kategori
```

---

## 4. REQUIRES SISTEMI (UNIFIED)

```
+----------------------------------------------------------+
|              REQUIRES - EXPLICIT PREFIX                   |
+----------------------------------------------------------+
|                                                           |
|  REDDEDILEN ALANLAR:                                      |
|    after, waits_for, depends_on, triggers_on             |
|                                                           |
|  KABUL EDILEN: requires (tek alan)                       |
|                                                           |
|  ZORUNLU PREFIX:                                          |
|    provides.*  -> Provide tamamlansin                    |
|    job.*       -> State path dolu olsun                  |
|    events.*    -> Event emit edilsin                     |
|                                                           |
|  REDDEDILEN: Implicit parsing (belirsizlik yaratir)      |
|                                                           |
+----------------------------------------------------------+
```

### Requires Ornekleri

```yaml
# State bekle (job.* prefix)
requires:
  - job.input.path
  - job.plugins.renamer.parsed

# Provide bekle (provides.* prefix)
requires:
  - provides.http.request
  - provides.fs.write
  - provides.state.update

# Event bekle (events.* prefix)
requires:
  - events.job.created
  - events.run.completed
```

```
YANLIS (prefix yok):
  requires:
    - http.request      # provides.http.request olmali
    - renamer           # job.plugins.renamer olmali
```

### Trigger Rule

```
+----------------------------------------------------------+
|  TRIGGER RULE (Airflow'dan)                               |
+----------------------------------------------------------+
|  RULE             SEMANTIK                                |
+----------------------------------------------------------+
|  all_success      Tum requires SUCCESS (default)         |
|  one_success      En az biri SUCCESS                     |
|  all_done         Hepsi DONE (success/fail farketmez)    |
|  all_fail         Hepsi FAIL                             |
|  none_fail        Hicbiri FAIL degil                     |
+----------------------------------------------------------+

KAYNAK: Apache Airflow
NOT: Tek trigger_rule atanir, reactive ayri konsept
V2 UPDATE: "always" KALDIRILDI - reactive: true kullanin
```

---

## 5. PLUGIN SERVICES

```
+----------------------------------------------------------+
|              TEK INTERFACE: PluginServices                |
+----------------------------------------------------------+
|                                                           |
|  MEVCUT (karisik):                                        |
|    get_debugger()           # Global                     |
|    context.event_bus        # Context field              |
|    state??                  # Belirsiz                   |
|                                                           |
|  YENI (tek interface):                                    |
|    services.state           # State islemleri            |
|    services.events          # Event emit/subscribe       |
|    services.logger          # Loglama                    |
|    services.config          # Config erisimi             |
|                                                           |
+----------------------------------------------------------+
```

### PluginServices Structure

```
                    PluginServices
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
   StateService    EventService    LoggerService
        |                |                |
        v                v                v
   get_job()         emit()           info()
   update()          subscribe()      debug()
   get_run()                          error()
                                      warn()
        |
        v
   ConfigService
        |
        v
   get()
   get_plugin()
```

### Service Interfaces

```python
@dataclass
class PluginServices:
    state: StateService
    events: EventService
    logger: LoggerService
    config: ConfigService

class StateService:
    def get_current_job(self) -> JobState: ...
    def get_job(self, job_id: str) -> Optional[JobState]: ...
    def get_all_jobs(self) -> List[JobState]: ...
    def update(self, job_id: str, key: str, value: Any) -> None: ...
    def get_run(self) -> RunState: ...

class EventService:
    def emit(self, event: str, data: Dict = None) -> None: ...
    def subscribe(self, event: str, handler: Callable) -> None: ...

class LoggerService:
    def debug(self, message: str, **kwargs) -> None: ...
    def info(self, message: str, **kwargs) -> None: ...
    def warn(self, message: str, **kwargs) -> None: ...
    def error(self, message: str, **kwargs) -> None: ...

class ConfigService:
    def get(self, key: str, default: Any = None) -> Any: ...
    def get_plugin(self, plugin_name: str) -> Dict: ...
```

**Uyari:** Interface referansi, execution session'da mevcut codebase'e gore uyarlanmalidir.

---

## 6. PLUGIN SIGNATURE

### per_job Mode

```python
class TMDbPlugin(BasePlugin):
    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        # Loglama
        services.logger.info("Processing movie", title=job.input.path)

        # Onceki plugin verisine erisim
        parsed = job.plugins.get("renamer", {}).get("parsed", {})

        # API cagri
        movie = self.fetch_movie(parsed.get("movie", {}).get("name"))

        # State guncelle
        services.state.update(job.id, "tmdb.movie", movie)

        # Event emit
        services.events.emit("http.response", {"plugin": "tmdb", "job_id": job.id})

        return PluginResult.success({"movie": movie})
```

### per_run Mode

```python
class ScannerPlugin(BasePlugin):
    def execute_run(self, services: PluginServices) -> PluginResult:
        # Config'den hedefleri al
        targets = services.config.get_plugin("scanner").get("targets", [])

        # Tarama
        files = self.scan(targets)

        # Her dosya icin job olustur
        for path in files:
            job_id = services.state.create_job(path)
            services.logger.debug("Job created", job_id=job_id)

        return PluginResult.success({"count": len(files)})
```

**Uyari:** Ornek kod, direkt kopyalanmaz. Yaklasimi gostermek icin yazilmistir.

---

## 7. PLUGIN RESULT

```python
@dataclass
class PluginResult:
    status: PluginStatus          # SUCCESS, FAILED, SKIPPED
    data: Optional[Dict] = None
    error: Optional[str] = None

    @classmethod
    def success(cls, data: Dict) -> 'PluginResult':
        return cls(status=PluginStatus.SUCCESS, data=data)

    @classmethod
    def failed(cls, error: str) -> 'PluginResult':
        return cls(status=PluginStatus.FAILED, error=error)

    @classmethod
    def skipped(cls, reason: str = "") -> 'PluginResult':
        return cls(status=PluginStatus.SKIPPED, error=reason)

class PluginStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
```

---

## 8. EXECUTION MODE

```
+----------------------------------------------------------+
|                    EXECUTION MODE                         |
+----------------------------------------------------------+
|                                                           |
|  per_job                                                  |
|  - Her job icin bir kez calisir                          |
|  - execute(job, services) signature                      |
|  - Ornek: renamer, tmdb, tasker                          |
|                                                           |
|  per_run                                                  |
|  - Tum run icin bir kez calisir                          |
|  - execute_run(services) signature                       |
|  - Ornek: scanner, rclone, summary                       |
|                                                           |
+----------------------------------------------------------+

EXECUTION PATTERN:

  INPUT STAGE (per_run):
    scanner.execute_run(services)
    --> jobs[] olusturuldu

  PARSE STAGE (per_job):
    for job in jobs:
        renamer.execute(job, services)

  DATA STAGE (per_job):
    for job in jobs:
        tmdb.execute(job, services)
        tvdb.execute(job, services)
        ffprobe.execute(job, services)

  OUTPUT STAGE (mixed):
    for job in jobs:
        tasker.execute(job, services)     # per_job
    rclone.execute_run(services)          # per_run
```

---

## 9. MEVCUT vs YENI

```
MEVCUT (plugin.json):
  {
    "name": "tmdb",
    "category": "output",
    "depends_on": ["renamer"],
    "expects": ["renamer.parsed.movie"]
  }

YENI (manifest.yml):
  name: tmdb
  stage: data
  requires:
    - job.plugins.renamer.parsed         # EXPLICIT prefix
  provides:
    - http.request
    - state.update
  trigger_rule: all_success

DEGISIKLIKLER:
  - category: output -> stage: data (tmdb icin)
  - depends_on KALDIRILDI (requires yeterli)
  - expects -> requires (EXPLICIT PREFIX)
  - stage isimleri: input, parse, data, output
  - +provides (TEKNIK ETKI bazli)
  - +trigger_rule (all_success, one_success, all_done, all_fail, none_fail, always)
  - +reactive (per_run icin)
```

---

**Son Guncelleme:** 2025-12-02
