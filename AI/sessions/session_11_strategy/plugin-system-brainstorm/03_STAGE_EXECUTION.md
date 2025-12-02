# STAGE EXECUTION

```yaml
tarih: 2025-12-02
durum: final
```

---

## 1. CURRENT

```yaml
# Mevcut sistem
category: input | output    # 2 kategori
# Siralama: depends_on ile
```

Sorunlar:
- Sadece 2 kategori
- Metadata vs Output ayrimi yok
- per_job vs per_run ayrimi yok

---

## 2. FEATURE

```yaml
# 4 Stage sistemi
stage: input | extract | enrich | output
mode: per_job | per_run
```

---

## 3. WHY

### Endustri Karsilastirmasi

```
SISTEM              STAGE/PHASE SAYISI
--------------------------------------------------
FlexGet             5 (input, filter, output,
                       metadata, modification)
                       
Home Assistant      6+ (hub, device, entity,
                        helper, service, system)
                        
Airflow             N (user-defined DAG)

Jenkins             N (pipeline stages)
```

### Archiverr Karari

```
+----------------------------------------------------------+
|                    4 STAGE SISTEMI                        |
+----------------------------------------------------------+
|                                                           |
|  INPUT                                                    |
|  - Job olusturur                                         |
|  - Genelde per_run                                       |
|  - Ornek: scanner, file-reader                           |
|                                                           |
|  EXTRACT                                                  |
|  - Input'tan veri cikarir                                |
|  - Genelde per_job                                       |
|  - Ornek: renamer, ffprobe                               |
|                                                           |
|  ENRICH                                                   |
|  - External data ile zenginlestirir                      |
|  - Genelde per_job                                       |
|  - Ornek: tmdb, tvdb                                     |
|                                                           |
|  OUTPUT                                                   |
|  - Cikti uretir                                          |
|  - per_job veya per_run                                  |
|  - Ornek: tasker, rclone                                 |
|                                                           |
+----------------------------------------------------------+
```

### Neden 4? Neden 6 Degil?

```
REDDEDILEN: 6 stage (v1-v5 strategy)
  input -> parse -> metadata -> modify -> finalize -> output

KABUL EDILEN: 4 stage
  input -> extract -> enrich -> output

GEREKCE:
  - modify ve finalize nadiren kullanilir
  - requires ile ayni is yapilabilir (after yok)
  - Fazla stage = fazla complexity
  - FlexGet benzer yaklasim (5 stage ama 3 ana)
  
ISIM SECIMI:
  - parse -> extract (daha net: veri cikarmak)
  - metadata -> enrich (daha net: zenginlestirmek)
```

---

## 4. SCHEMA

### Stage Execution Flow

```
                    ORCHESTRATOR
                         |
                         v
+----------------------------------------------------------+
|                    STAGE LOOP                             |
|                                                           |
|  for stage in [INPUT, PARSE, METADATA, OUTPUT]:          |
|      plugins = get_plugins_by_stage(stage)               |
|      sorted = topological_sort(plugins)                  |
|      execute_stage(sorted)                               |
|                                                           |
+----------------------------------------------------------+
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
    +-------+        +--------+        +-------+
    | INPUT |        | EXTRACT|        |ENRICH |
    +-------+        +--------+        +-------+
        |                |                |
        v                v                v
    per_run          per_job           per_job
    scanner          renamer           tmdb,tvdb
        |                |                |
        v                v                v
    job.created      data.parsed      http.response
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

### Stage Icinde Siralama

```
                STAGE INTERNAL ORDERING

+----------------------------------------------------------+
|                    METADATA STAGE                         |
|                                                           |
|  Plugins: [tmdb, tvdb, ffprobe]                          |
|                                                           |
|  Step 1: after check                                     |
|    tmdb.after = []                                       |
|    tvdb.after = []                                       |
|    ffprobe.after = []                                    |
|    --> Hepsi paralel calisabilir                         |
|                                                           |
|  Step 2: requires check                                  |
|    tmdb.requires = [data.parsed]                         |
|    tvdb.requires = [data.parsed]                         |
|    ffprobe.requires = [job.created]                      |
|    --> Hepsi satisfied, paralel calis                    |
|                                                           |
|  Sonuc: [[tmdb, tvdb, ffprobe]] (tek grup, paralel)      |
|                                                           |
+----------------------------------------------------------+

+----------------------------------------------------------+
|                    OUTPUT STAGE                           |
|                                                           |
|  Plugins: [tasker, rclone]                               |
|                                                           |
|  Step 1: after check                                     |
|    tasker.after = []                                     |
|    rclone.after = [tasker]                               |
|    --> rclone tasker'dan sonra                           |
|                                                           |
|  Step 2: requires check                                  |
|    tasker.requires = [http.response]                     |
|    rclone.requires = [fs.write]                          |
|    --> tasker once, rclone sonra                         |
|                                                           |
|  Sonuc: [[tasker], [rclone]] (iki grup, sirali)          |
|                                                           |
+----------------------------------------------------------+
```

---

## 5. MODE SISTEMI

### per_job vs per_run

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
        
  METADATA STAGE (per_job):
    for job in jobs:
        tmdb.execute(job, services)
        tvdb.execute(job, services)
        ffprobe.execute(job, services)
        
  OUTPUT STAGE (mixed):
    for job in jobs:
        tasker.execute(job, services)     # per_job
    rclone.execute_run(services)           # per_run
```

---

## 6. PARALEL EXECUTION

```
                PARALLEL EXECUTION

STAGE ARASI: Sequential (sirali)
  INPUT --> PARSE --> METADATA --> OUTPUT

STAGE ICI: Parallel (ayni grup)
  METADATA: [tmdb, tvdb, ffprobe] --> Paralel
  
JOB ARASI: Configurable
  jobs[0] --> jobs[1] --> jobs[2]  (sequential)
  jobs[0..N]                        (parallel, optional)

+----------------------------------------------------------+
|                EXECUTOR LOGIC                             |
|                                                           |
|  for stage in STAGES:                                    |
|      groups = topological_sort(stage_plugins)            |
|                                                           |
|      for group in groups:                                |
|          if all(p.mode == 'per_run' for p in group):     |
|              # Paralel calistir                          |
|              await asyncio.gather(*[                     |
|                  p.execute_run(services)                 |
|                  for p in group                          |
|              ])                                          |
|          else:                                           |
|              # Job loop                                  |
|              for job in jobs:                            |
|                  await asyncio.gather(*[                 |
|                      p.execute(job, services)            |
|                      for p in group                      |
|                      if p.mode == 'per_job'              |
|                  ])                                      |
|                                                           |
+----------------------------------------------------------+
```

---

## 7. ERROR HANDLING

```
                ERROR PROPAGATION

+----------------------------------------------------------+
|                                                           |
|  PLUGIN ERROR                                             |
|    |                                                      |
|    +--> Job failed olarak isaretle                       |
|    +--> Sonraki plugin'ler skip (bu job icin)            |
|    +--> Diger job'lar etkilenmez                         |
|                                                           |
|  STAGE ERROR                                              |
|    |                                                      |
|    +--> Stage failed olarak isaretle                     |
|    +--> Sonraki stage'ler calisir (best effort)          |
|    +--> Run failed olarak isaretle                       |
|                                                           |
|  CRITICAL ERROR                                           |
|    |                                                      |
|    +--> Run durdurulur                                   |
|    +--> Cleanup calisir                                  |
|    +--> Exit code != 0                                   |
|                                                           |
+----------------------------------------------------------+
```

---

## 8. ORNEK EXECUTION

```
RUN BASLADI
|
v
INPUT STAGE
|  scanner.execute_run(services)
|  --> 3 job olusturuldu
|
v
PARSE STAGE
|  Job 0: renamer.execute(job, services)
|  Job 1: renamer.execute(job, services)
|  Job 2: renamer.execute(job, services)
|
v
METADATA STAGE
|  Job 0:
|    tmdb.execute(job, services)    \
|    tvdb.execute(job, services)     > Paralel
|    ffprobe.execute(job, services) /
|  Job 1: (ayni)
|  Job 2: (ayni)
|
v
OUTPUT STAGE
|  Job 0: tasker.execute(job, services)
|  Job 1: tasker.execute(job, services)
|  Job 2: tasker.execute(job, services)
|  ---
|  rclone.execute_run(services)  # per_run, en son
|
v
RUN TAMAMLANDI
```

---

## 9. STAGE FELSEFESI

```
+----------------------------------------------------------+
|              PHILOSOPHY.md GUNCELLEMESI                   |
+----------------------------------------------------------+
|                                                           |
|  STAGE = Semantik Gruplama                               |
|    - Kategori bazli siralama                             |
|    - 4 sabit deger                                       |
|    - Execution ordering icin                             |
|                                                           |
|  STAGE != Execution Order                                |
|    - Stage icinde siralama = requires/after              |
|    - Stage sadece gruplama                               |
|                                                           |
|  STAGE + MODE                                             |
|    - input genelde per_run                               |
|    - parse/metadata genelde per_job                      |
|    - output mixed olabilir                               |
|                                                           |
+----------------------------------------------------------+
```
