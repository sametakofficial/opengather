# FINAL DECISIONS

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/* (tum dosyalar)
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- always trigger_rule KALDIRILDI (5 adet kaldi)
- !include_list, !include_merge KALDIRILDI (sadece !include)
- input.path -> input.value
- input.data, output.values, output.data eklendi
- lockable provides: 5 adet (fs.write, delete, move, hardlink, symlink)
- provides icinde job.* ve run.* YASAK
- runtime validation KALDIRILDI
```

---

## 1. KRITIK KARARLAR OZETI

```
+----------------------------------------------------------+
|                    KRITIK KARARLAR                        |
+----------------------------------------------------------+

1. STAGE SISTEMI: 4 STAGE
   input -> parse -> data -> output
   (6 stage reddedildi: modify, finalize gereksiz)

   WEB UI KATEGORILERI:
     INPUT  = input + parse
     OUTPUT = data + output

2. PROVIDES: ISLEM BAZLI
   http.response, fs.write, metadata.parsed
   (kategori bazli reddedildi: metadata.movie)

3. REQUIRES: UNIFIED
   Tek alan, implicit parsing
   (after, depends_on, waits_for reddedildi)

4. PLUGINSERVICES: TEK INTERFACE
   services.state, services.events, services.logger
   (global get_debugger() reddedildi)

5. CONFIG: FLEXGET STYLE
   Plugin adi = top-level key
   (plugins: wrapper reddedildi)

6. TERMINOLOJI
   match -> job, execution -> run
   (endustri standardi: Airflow, GitLab CI)

+----------------------------------------------------------+
```

---

## 2. STAGE DEGISIKLIKLERI

```
ESKI (6 stage):
  input -> parse -> metadata -> modify -> finalize -> output

YENI (4 stage):
  input -> parse -> data -> output

ISIM DEGISIKLIKLERI:
  input    -> input   (basit, herkes anlar)
  parse    -> parse   (ayni kaldi)
  metadata -> data    (sadece metadata degil: subtitle, artwork vs)

KALDIRILAN:
  modify   (enrich ile birlestirildi)
  finalize (output ile birlestirildi)

DETAY: 11_stage_naming_research.md
```

---

## 3. MANIFEST DEGISIKLIKLERI

```
ESKI manifest.yml:
  name: tmdb
  category: output
  depends_on: [renamer]
  expects: [renamer.parsed.movie]
  class_name: TMDbPlugin

YENI manifest.yml:
  name: tmdb
  stage: data                          # v2: enrich -> data
  requires:
    - job.plugins.renamer.parsed       # v2: explicit prefix
  provides:
    - http.request                     # v2: http.response kaldirildi
    - state.update                     # v2: metadata.movie -> state.update
  trigger_rule: all_success
  class_name: TMDbPlugin

DEGISIKLIKLER:
  - category -> stage (input|parse|data|output)
  - depends_on KALDIRILDI
  - expects -> requires (UNIFIED)
  - +provides
  - +trigger_rule
  - +reactive
```

---

## 4. CONFIG DEGISIKLIKLERI

```
ESKI config.yml:
  plugins:
    tmdb:
      enabled: true
      api_key: xxx

YENI config.yml:
  aliases:
    m: job.plugins.tmdb.movie

  tmdb:
    api_key: xxx

  tasker:
    tasks:
      !include_list: ./tasks/

DEGISIKLIKLER:
  - plugins: wrapper KALDIRILDI
  - enabled: key varsa true
  - +aliases (top-level)
  - +!include directive
```

---

## 5. STATE DEGISIKLIKLERI

```
ESKI:
  ExecutionState, MatchState
  execution_id, match

YENI:
  RunState, JobState
  run_id, job

PLUGINS STRUCTURE:
  ESKI (nested by stage):
    plugins.input.scanner
    plugins.metadata.tmdb

  YENI (flat):
    plugins.scanner
    plugins.tmdb
```

---

## 6. PROVIDES STANDART TERIMLER

```
HTTP
  http.request       Dis API'ye istek yapti
  http.response      Dis API'den cevap aldi

FS (Filesystem)
  fs.read            Dosya/dizin okudu
  fs.write           Dosya yazdi/kopyaladi
  fs.delete          Dosya sildi
  fs.move            Dosya tasidi

JOB
  job.created        Yeni job olusturdu

METADATA
  metadata.parsed    Dosya adi parse edildi
  metadata.movie     Film metadata alindi
  metadata.show      Dizi metadata alindi

NOTIFICATION
  notification.sent  Bildirim gonderildi

CUSTOM
  custom.*           Plugin ozel
```

---

## 7. REQUIRES IMPLICIT PARSING

```
requires alaninda yazilan deger:

1. job.* veya run.* ile basliyorsa -> STATE
   Ornek: job.input.path, run.status

2. Provides listesinde varsa -> PROVIDE
   Ornek: metadata.parsed, http.response

3. Bilinen plugin adiysa -> PLUGIN
   Ornek: renamer, tmdb, scanner
```

---

## 8. TRIGGER RULE

```
RULE          SEMANTIK                      ORNEK
---------------------------------------------------------
all_success   Tum requires SUCCESS          TMDb (parser gerekli)
one_success   En az biri SUCCESS            Fallback chain
all_done      Hepsi DONE (fail dahil)       Summary/report pluginleri
all_fail      Hepsi FAIL                    Error handler
none_fail     Hicbiri FAIL degil            Default safe mode
```

NOTE: "always" v2'de KALDIRILDI - requires bakmadan calistirmak icin reactive: true kullanin

---

## 9. ALIAS PRIORITY

```
PRIORITY (yuksekten dusuge):
  1. Inline (Jinja2 set)     {% set m = ... %}
  2. User (config.aliases)   m: job.plugins.tmdb.movie
  3. Short (sistem)          j -> job, r -> run
  4. System                  job, run, jobs, options
```

---

## 10. IMPLEMENTATION PRIORITY

```
PHASE 1: Core Models (~8h)
  - JobState, RunState dataclasses
  - StateManager API
  - Event emission

PHASE 2: Plugin Services (~6h)
  - PluginServices interface
  - StateService, EventService, LoggerService
  - ConfigService

PHASE 3: Config System (~4h)
  - FlexGet style loader
  - !include directive
  - Alias resolution

PHASE 4: Stage Execution (~8h)
  - StageExecutor
  - Topological sort
  - Parallel execution

PHASE 5: Testing (~6h)
  - Unit tests
  - Integration tests
  - Migration tests
```

---

## 11. ENDUSTRI REFERANSLARI

```
FRAMEWORK         ALINAN PATTERN
---------------------------------------------------------
Airflow           trigger_rule, requires, DAG execution
GitLab CI         job terminolojisi, stage sistemi
FlexGet           Config style, plugin detection
Home Assistant    !include directive, YAML pattern
Celery            per_job/per_run execution mode
```

---

## 12. MIGRATION CHECKLIST

```
[ ] manifest.yml: category -> stage (input|parse|data|output)
[ ] manifest.yml: depends_on -> requires
[ ] manifest.yml: expects -> requires
[ ] manifest.yml: +provides
[ ] config.yml: plugins: wrapper kaldir
[ ] config.yml: +aliases
[ ] state/models.py: MatchState -> JobState
[ ] state/models.py: ExecutionState -> RunState
[ ] core/plugins/executor.py: phase -> stage
[ ] core/plugins/executor.py: STAGES = ['input', 'parse', 'data', 'output']
[ ] tests: yeni terminoloji
```

---

**Son Guncelleme:** 2025-12-02
