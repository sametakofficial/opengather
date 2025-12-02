# PLUGIN SYSTEM BRAINSTORM

```yaml
tarih: 2025-12-02
tip: brainstorm
durum: taslak
hedef: 01-10 strategy dosyalarına override edilecek
```

---

# 1. MANIFEST YAPISI

## CURRENT

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
category: output
depends_on: [renamer]
expects: [renamer.parsed]
```

## FEATURE

```yaml
name: tmdb
stage: metadata
mode: per_job

requires: [renamer.parsed]     # data path
provides: [http.response]      # işlem bazlı
after: [renamer]               # plugin ismi
```

## WHY

```
Home Assistant: dependencies + after_dependencies
FlexGet: input/filter/output/metadata/modification (5 tip)
Airflow: upstream/downstream
Docker: depends_on

Bizim karar:
- requires = data path (renamer.parsed)
- provides = işlem bazlı (http.response, fs.write)  
- after = plugin ismi (explicit ordering)
- stage = kategori (execution grouping)
```

## SCHEMA

```
                    MANIFEST RESOLUTION
                           |
                           v
+----------------------------------------------------------+
|                    DISCOVERY                              |
|  plugins/*/manifest.yml okur                             |
|  name, stage, mode, requires, provides, after parse      |
+----------------------------------------------------------+
                           |
                           v
+----------------------------------------------------------+
|                    DEPENDENCY GRAPH                       |
|                                                           |
|  scanner ─────────> renamer ─────────> tmdb              |
|     |                  |                  |               |
|  provides:          requires:          requires:          |
|  [job.created]     [job.created]      [renamer.parsed]   |
|                    provides:           provides:          |
|                    [renamer.parsed]   [http.response]    |
|                                                           |
+----------------------------------------------------------+
                           |
                           v
+----------------------------------------------------------+
|                 TOPOLOGICAL SORT                          |
|  Stage içinde sıralama:                                  |
|  1. after değerlerine göre                               |
|  2. requires/provides DAG'a göre                         |
|  Sonuç: [[scanner], [renamer], [tmdb, tvdb], [tasker]]   |
+----------------------------------------------------------+
```

---

# 2. REQUIRES/PROVIDES/AFTER KARARI

## CURRENT

```yaml
depends_on: [renamer]      # plugin ismi
expects: [renamer.parsed]  # data path
```

## FEATURE

```yaml
requires: [renamer.parsed]   # data path VEYA provides değeri
provides: [http.response]    # işlem bazlı capability
after: [renamer]             # explicit plugin ordering
```

## WHY

```
SORU: requires içine ne yazılabilir?
CEVAP: 
  1. Data path: renamer.parsed, tmdb.movie
  2. Provides değeri: http.response, fs.write
  3. Plugin ismi YAZILMAZ - after kullan

SORU: provides neden işlem bazlı?
CEVAP:
  - "metadata" provides değeri YANLIŞ (kategori)
  - "http.response" provides değeri DOĞRU (işlem)
  - Plugin agnostik sistem - tmdb yazamazsın
  
PROVIDES STANDART DEĞERLERİ:
  http.request      HTTP istek yaptı
  http.response     HTTP cevap aldı
  fs.read           Dosya okudu
  fs.write          Dosya yazdı
  fs.delete         Dosya sildi
  fs.move           Dosya taşıdı
  job.created       Job oluşturdu
  job.modified      Job değiştirdi
  state.updated     State güncelledi
```

## SCHEMA

```
              REQUIRES vs AFTER vs PROVIDES
                         |
         +---------------+---------------+
         |               |               |
         v               v               v
    +--------+      +--------+      +----------+
    |requires|      | after  |      | provides |
    +--------+      +--------+      +----------+
         |               |               |
         v               v               v
    data path       plugin ismi      capability
    veya provides                    (işlem bazlı)
         |               |               |
         v               v               v
    "Bu data         "Bu plugin      "Ben bu
     olmadan          bitmeden        işlemi
     başlama"         başlama"        yapıyorum"
```

```
EXECUTION ORDER HESAPLAMA:

  Input:
    scanner.provides = [job.created]
    renamer.requires = [job.created]
    tmdb.requires = [renamer.parsed]
    tmdb.after = [renamer]
    tasker.requires = [http.response]

  Çıktı:
    1. scanner (no requires)
    2. renamer (requires job.created - scanner sağlıyor)
    3. tmdb (requires renamer.parsed + after renamer)
    4. tasker (requires http.response - tmdb sağlıyor)
```

---

# 3. STAGE SİSTEMİ

## CURRENT

```yaml
category: input | output   # sadece 2
```

## FEATURE

```yaml
stage: input | parse | metadata | output   # 4 stage
```

## WHY

```
SORU: Stage neden gerekli?
CEVAP: Kategori bazlı sıralama için.

SORU: provides ile stage aynı işi yapmıyor mu?
CEVAP: 
  - provides = teknik işlem (http.response)
  - stage = semantik kategori (metadata)
  - İkisi farklı amaç

FlexGet: input/filter/output/metadata/modification
Home Assistant: hub/device/entity/helper/service/system

Bizim karar: 4 stage yeterli
  - input: job oluşturur (scanner)
  - parse: job parse eder (renamer)
  - metadata: external data ekler (tmdb)
  - output: çıktı üretir (tasker)
```

## SCHEMA

```
                    STAGE EXECUTION
                         |
    +--------------------+--------------------+
    |                    |                    |
    v                    v                    v
+--------+          +---------+          +--------+
| INPUT  |          |  PARSE  |          |METADATA|
| per_run|          | per_job |          | per_job|
+--------+          +---------+          +--------+
    |                    |                    |
 scanner              renamer             tmdb,tvdb
    |                    |                    |
    v                    v                    v
job.created        renamer.parsed       tmdb.movie
                                             |
                                             v
                                        +--------+
                                        | OUTPUT |
                                        | per_job|
                                        +--------+
                                             |
                                          tasker
```

---

# 4. PROVIDES EARLY COMPLETION

## CURRENT

```
Plugin bitince provides tamamlanmış sayılır
```

## FEATURE

```python
# Plugin içinden:
self.complete_provide('http.response')  # erken tamamla
```

## WHY

```
SORU: Neden erken tamamlama?
CEVAP:
  - Plugin 1dk çalışır, http.response sadece 10sn
  - 10sn'de beklenmeden başka plugin başlayabilir
  - Performans kazancı

ENDÜSTRİ ARAŞTIRMASI:
  - RxJS: Observable complete()
  - Airflow: task dependencies + sensors
  - Kubernetes: readinessProbe
  
Benzer ama aynı değil. Bu özellik opsiyonel kalabilir.
İlk versiyonda eklenmeyebilir.
```

## SCHEMA

```
              PROVIDES LIFECYCLE
                    |
    +---------------+---------------+
    |                               |
    v                               v
IMPLICIT (default)              EXPLICIT (optional)
    |                               |
    v                               v
Plugin.execute()              self.complete_provide()
    |                               |
    v                               v
Plugin bitince                 Çağrıldığı anda
tüm provides                   o provide
complete                       complete
```

---

# 5. PLUGIN İLETİŞİMİ (SERVICES)

## CURRENT

```python
# Mevcut durum (executor.py)
context = ExecutionContext(
    execution_id=...,
    event_bus=...,
    debugger=...,
    task_manager=...,
    config=...,
)
plugin.set_context(context)
```

## FEATURE

```python
class PluginServices:
    state: StateService      # job/run okuma yazma
    events: EventService     # event emit/subscribe
    logger: LogService       # loglama
    config: ConfigService    # config okuma
```

## WHY

```
SORU: Kaç farklı interface var şu an?
CEVAP:
  - ExecutionContext (context.event_bus, context.debugger)
  - get_debugger() global
  - state direkt erişim
  
SORU: Tek interface mi olmalı?
CEVAP: Evet. PluginServices tek giriş noktası.

ENDÜSTRİ:
  - VSCode: vscode.* API namespace
  - Obsidian: Plugin.app
  - Home Assistant: hass object
```

## SCHEMA

```
              PLUGIN <--> CORE İLETİŞİM
                         |
    +--------------------+--------------------+
    |                    |                    |
    v                    v                    v
  STATE               EVENTS              LOGGER
    |                    |                    |
    v                    v                    v
+--------+          +--------+          +--------+
|services|          |services|          |services|
|.state  |          |.events |          |.logger |
+--------+          +--------+          +--------+
    |                    |                    |
    v                    v                    v
get_job()           emit()              info()
update_job()        subscribe()         debug()
get_run()                               error()
```

```
MEVCUT KAOS:

  Plugin
     |
     +---> context.event_bus.emit()
     |
     +---> get_debugger().info()
     |
     +---> state.update()  (direkt?)

ÖNERİLEN TEK INTERFACE:

  Plugin
     |
     +---> services.events.emit()
     |
     +---> services.logger.info()
     |
     +---> services.state.update()
```

---

# 6. CONFIG + MANIFEST BİRLEŞİMİ

## CURRENT

```yaml
# config.yml
plugins:
  tmdb:
    api_key: xxx
    
# plugins/tmdb/manifest.yml
name: tmdb
stage: metadata
```

## FEATURE

```yaml
# config.yml (manifest otomatik merge edilir)
tmdb:
  api_key: xxx
  # stage, provides, requires manifest'ten gelir

# plugins/tmdb/manifest.yml
name: tmdb
stage: metadata
requires: [renamer.parsed]
provides: [http.response]
```

## WHY

```
SORU: Manifest config'e nasıl eklenir?
CEVAP:
  1. Plugin discovery manifest'i okur
  2. config.yml'de plugin adı varsa enabled
  3. Manifest değerleri config'e merge edilir
  4. config.yml değerleri override eder

FlexGet: Aynı mantık, plugin adı = config key
```

## SCHEMA

```
              CONFIG + MANIFEST MERGE
                      |
                      v
+----------------------------------------------------------+
|                    CONFIG LOADING                         |
|                                                           |
|  1. config.yml yükle                                     |
|     tmdb:                                                |
|       api_key: xxx                                       |
|                                                           |
|  2. Plugin discovery                                     |
|     plugins/tmdb/manifest.yml oku                        |
|                                                           |
|  3. Merge                                                |
|     tmdb:                                                |
|       api_key: xxx           <- config.yml               |
|       stage: metadata        <- manifest.yml             |
|       requires: [...]        <- manifest.yml             |
|       provides: [...]        <- manifest.yml             |
|                                                           |
+----------------------------------------------------------+
```

---

# 7. ALIAS SİSTEMİ

## CURRENT

```yaml
# Hardcoded magic paths
{{ tmdb.movie.title }}
```

## FEATURE

```yaml
# config.yml
aliases:
  m: job.plugins.tmdb.movie
  
# Kullanım
{{ m.title }}

# Veya inline
{% set m = job.plugins.tmdb.movie %}
{{ m.title }}
```

## WHY

```
SORU: Default alias olacak mı?
CEVAP: Evet, sistem tanımlı:
  - job = mevcut job state
  - jobs = tüm job'lar
  - run = run state
  - options = config.options

SORU: Magic path olacak mı?
CEVAP: Hayır. Explicit path zorunlu.
  - {{ tmdb.movie }} YANLIŞ
  - {{ job.plugins.tmdb.movie }} DOĞRU
```

## SCHEMA

```
              ALIAS RESOLUTION
                    |
                    v
+----------------------------------------------------------+
|                 TEMPLATE RENDER                           |
|                                                           |
|  Input: "{{ m.title }}"                                  |
|                                                           |
|  1. Alias lookup                                         |
|     m -> job.plugins.tmdb.movie                          |
|                                                           |
|  2. Path resolve                                         |
|     job.plugins.tmdb.movie.title -> "Inception"          |
|                                                           |
|  Output: "Inception"                                     |
|                                                           |
+----------------------------------------------------------+

DEFAULT ALIASES:

  job     -> current job state
  jobs    -> all jobs list
  run     -> run state
  options -> config.options
  index   -> current job index
```

---

# 8. STATE YAPISI

## CURRENT

```python
# state/manager.py
class MatchState:
    index: int
    input_path: str
    plugins: Dict[str, PluginResult]
```

## FEATURE

```python
class JobState:
    id: str
    index: int
    input: InputData
    plugins: Dict[str, Any]  # flat, stage yok
    status: str
```

## WHY

```
SORU: plugins içinde stage var mı?
CEVAP: Hayır. Flat yapı.

SORU: Neden flat?
CEVAP:
  - Template erişimi kolay: job.plugins.tmdb.movie
  - Stage bilgisi manifest'te, state'te gereksiz
  - Endüstri standardı (Home Assistant, FlexGet)

ALTERNATIF (REDDEDİLDİ):
  plugins:
    metadata:
      tmdb: {...}
      tvdb: {...}
    
KABUL EDİLEN:
  plugins:
    tmdb: {...}
    tvdb: {...}
```

## SCHEMA

```
              JOB STATE YAPISI
                    |
                    v
+----------------------------------------------------------+
|  JobState                                                 |
|  |                                                        |
|  +-- id: "job_abc123_0"                                  |
|  +-- index: 0                                            |
|  +-- input:                                              |
|  |     +-- path: "/media/file.mkv"                       |
|  |     +-- category: "movie"                             |
|  +-- plugins:                                            |
|  |     +-- scanner: {...}                                |
|  |     +-- renamer: {...}                                |
|  |     +-- tmdb: {...}                                   |
|  +-- status: "completed"                                 |
|                                                           |
+----------------------------------------------------------+

TEMPLATE ERİŞİMİ:

  {{ job.input.path }}
  {{ job.plugins.tmdb.movie.title }}
  {{ job.plugins.renamer.parsed.name }}
```

---

# 9. PROVIDES STANDART DEĞERLER

## CURRENT (15_final_architecture.md)

```yaml
# REDDEDİLEN - Kategori bazlı
provides:
  - input.files
  - parsed.movie
  - metadata.movie
  - output.moved
```

## FEATURE

```yaml
# KABUL EDİLEN - İşlem bazlı
provides:
  - http.request
  - http.response
  - fs.read
  - fs.write
  - fs.delete
  - fs.move
  - job.created
  - job.modified
  - state.updated
```

## WHY

```
SORU: "metadata.movie" neden yanlış?
CEVAP:
  - Kategori bazlı, işlem değil
  - Plugin agnostik ihlali (movie archiverr-specific)
  
SORU: "http.response" neden doğru?
CEVAP:
  - İşlem bazlı
  - Generic, herhangi bir API çağrısı
  - Plugin bağımsız

ENDÜSTRİ:
  - OSGi: osgi.service, osgi.wiring.package
  - Linux capabilities: CAP_NET_BIND, CAP_SYS_ADMIN
  - AWS IAM: s3:GetObject, ec2:RunInstances
```

## SCHEMA

```
              PROVIDES TAXONOMY
                    |
    +---------------+---------------+
    |               |               |
    v               v               v
   HTTP            FS            STATE
    |               |               |
    v               v               v
http.request    fs.read        job.created
http.response   fs.write       job.modified
                fs.delete      state.updated
                fs.move

ÖRNEK KULLANIM:

  scanner:
    provides: [job.created]
    
  tmdb:
    requires: [renamer.parsed]
    provides: [http.response]
    
  tasker:
    requires: [http.response]
    provides: [fs.write]
    
  rclone:
    after: [tasker]           # fs.write değil, plugin ismi
    requires: [fs.write]      # tasker'ın provides'ı
```

---

# 10. EVENT VS PROVIDES

## CURRENT

```yaml
triggers_on: [file.created]   # event-based
```

## FEATURE

```yaml
on: [file.created]            # event subscription
provides: [fs.write]          # capability declaration
```

## WHY

```
SORU: on vs provides farkı?
CEVAP:
  - on = reactive, her event'te çalış
  - provides = ordering, plugin bitince available

SORU: Hangisi ne zaman kullanılır?
CEVAP:
  - per_job plugin: on kullanabilir
  - per_run plugin: on KULLANIMAZ, after kullan
  
PHILOSOPHY.md §4.2: "on sadece per_job için geçerli"
```

## SCHEMA

```
              EVENT vs PROVIDES
                    |
    +---------------+---------------+
    |                               |
    v                               v
   ON                           PROVIDES
(subscription)                (capability)
    |                               |
    v                               v
"Her fs.write                "Ben fs.write
 event'inde                   yapıyorum"
 çalış"                           |
    |                               v
    v                       DAG ordering
per_job only                requires: [fs.write]
```

---

# ÖZET

```
+----------------------------------------------------------+
|                    MANIFEST SCHEMA                        |
+----------------------------------------------------------+
|                                                           |
|  name: string                                            |
|  version: string                                         |
|  stage: input | parse | metadata | output                |
|  mode: per_job | per_run                                 |
|                                                           |
|  requires: [string]   # data path veya provides değeri   |
|  provides: [string]   # işlem bazlı capability           |
|  after: [string]      # plugin isimleri                  |
|  on: [string]         # event subscription (per_job only)|
|                                                           |
+----------------------------------------------------------+

+----------------------------------------------------------+
|                  PROVIDES DEĞERLER                        |
+----------------------------------------------------------+
|                                                           |
|  http.request   http.response                            |
|  fs.read        fs.write       fs.delete     fs.move     |
|  job.created    job.modified   state.updated             |
|                                                           |
+----------------------------------------------------------+

+----------------------------------------------------------+
|                   PLUGIN SERVICES                         |
+----------------------------------------------------------+
|                                                           |
|  services.state   -> get_job(), update_job()             |
|  services.events  -> emit(), subscribe()                 |
|  services.logger  -> info(), debug(), error()            |
|  services.config  -> get()                               |
|                                                           |
+----------------------------------------------------------+
```

---

# AÇIK SORULAR

1. provides early completion eklenmeli mi? (Phase 2?)
2. on sadece per_job mı olmalı? (PHILOSOPHY.md diyor)
3. requires içinde event yazılabilir mi?

---

# SONRAKI ADIM

Bu brainstorm dosyası 01-10 strategy dosyalarına override edilecek.

---

CHANGELOG:
- 15_final_architecture.md'deki provides değerleri reddedildi
- İşlem bazlı provides sistemi önerildi
- PluginServices tek interface önerildi
