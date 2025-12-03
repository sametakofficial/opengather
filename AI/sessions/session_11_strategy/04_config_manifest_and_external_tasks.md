# CONFIG SYSTEM

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/05_CONFIG_SYSTEM.md, 07_ALIAS_SYSTEM.md
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- !include_list KALDIRILDI
- !include_merge KALDIRILDI
- sadece !include ./path kullanilir
- dizin verilirse tum yml dosyalari yuklenir
- tekil dosya verilirse o dosya yuklenir
- config > manifest (override)
- immutable: name, version, stage, class_name, entry_point
- mutable: requires, provides, trigger_rule, reactive, config_schema
- list merge = replace (extend degil)
```

---

## 1. FLEXGET STYLE CONFIG

```
+----------------------------------------------------------+
|              FLEXGET STYLE CONFIG                         |
+----------------------------------------------------------+
|                                                           |
|  MEVCUT:                                                  |
|  plugins:                                                 |
|    tmdb:                                                  |
|      enabled: true                                       |
|      api_key: xxx                                        |
|                                                           |
|  YENI:                                                    |
|  tmdb:                                                    |
|    api_key: xxx                                          |
|                                                           |
|  NEDEN:                                                   |
|  - Daha temiz                                            |
|  - Daha az nesting                                       |
|  - enabled = key varsa true                              |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. CONFIG.YML YAPISI

```yaml
# config.yml (TAM ORNEK)

# Options
options:
  debug: true
  dry_run: false

# Aliases
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  p: job.plugins.renamer.parsed

# Plugins (FlexGet style - no wrapper)
scanner:
  targets:
    - /downloads/movies
    - /downloads/shows
  recursive: true

renamer:
  media_type: auto

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

ffprobe:
  timeout: 30

tasker:
  tasks: !include ./tasks/ # v2: !include_list kaldirildi, sadece !include

# Disabled plugin
tvdb: false
```

---

## 3. ENABLED LOGIC

```
+----------------------------------------------------------+
|              PLUGIN ENABLED DETECTION                     |
+----------------------------------------------------------+
|                                                           |
|  KURAL 1: Key varsa enabled                              |
|  tmdb:                                                    |
|    api_key: xxx                                          |
|  --> tmdb ENABLED                                        |
|                                                           |
|  KURAL 2: false ise disabled                             |
|  tvdb: false                                             |
|  --> tvdb DISABLED                                       |
|                                                           |
|  KURAL 3: enabled: false ile disabled                    |
|  omdb:                                                    |
|    enabled: false                                        |
|    api_key: xxx                                          |
|  --> omdb DISABLED                                       |
|                                                           |
|  KURAL 4: Key yoksa disabled                             |
|  # ffprobe hic yok                                       |
|  --> ffprobe DISABLED                                    |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. INCLUDE DIRECTIVE

```
              !INCLUDE DIRECTIVE

SYNTAX:
  !include file.yml           # Tek dosya
  !include_list dir/          # Dizin -> list
  !include_merge dir/         # Dizin -> merge

ORNEK:
  # config.yml
  scanner:
    targets:
      - /downloads

  tasker:
    tasks:
      !include_list: ./tasks/

  # ./tasks/movie_print.yml
  - name: movie_print
    type: print
    template: "{{ m.title }}"

  # ./tasks/save_movie.yml
  - name: save_movie
    type: save
    destination: "/media/movies/..."

SONUC:
  tasker:
    tasks:
      - name: movie_print
        type: print
        template: "..."
      - name: save_movie
        type: save
        destination: "..."
```

---

## 5. CONFIG + MANIFEST MERGE

```
              CONFIG LOADING FLOW

+----------------------------------------------------------+
|  1. config.yml yukle                                     |
|     tmdb:                                                |
|       api_key: xxx                                       |
|       language: tr-TR                                    |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  2. Plugin discovery                                     |
|     plugins/tmdb/manifest.yml oku                        |
|     name: tmdb                                           |
|     stage: data                                          |
|     requires: [job.plugins.renamer.parsed]               |
|     provides: [http.request, state.update]               |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  3. Merge (config uzerine manifest)                      |
|     tmdb:                                                |
|       # config.yml'den                                   |
|       api_key: xxx                                       |
|       language: tr-TR                                    |
|       # manifest.yml'den                                 |
|       _stage: data                                       |
|       _requires: [job.plugins.renamer.parsed]            |
|       _provides: [http.request, state.update]            |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  4. Validation                                           |
|     - config_schema kontrolu                             |
|     - required fields kontrolu                           |
|     - type validation                                    |
+----------------------------------------------------------+

MERGE PRIORITY:
  config.yml > manifest.yml defaults
```

---

## 6. ALIAS SISTEMI

```
+----------------------------------------------------------+
|              ALIAS SISTEMI                                |
+----------------------------------------------------------+
|                                                           |
|  SISTEM INJECT (override edilemez):                       |
|    job, jobs, run, options, index                        |
|                                                           |
|  SHORT ALIAS (sistem):                                    |
|    j -> job, r -> run, o -> options                      |
|                                                           |
|  KULLANICI (config.aliases):                              |
|    m: job.plugins.tmdb.movie                             |
|    s: job.plugins.tmdb.show                              |
|                                                           |
|  INLINE (Jinja2 set):                                     |
|    {% set m = job.plugins.tmdb.movie %}                  |
|                                                           |
|  PRIORITY:                                                |
|    1. Inline (Jinja2 set)     YUKSEK                     |
|    2. User (config.aliases)                              |
|    3. Short (j, r, o)                                    |
|    4. System (job, run, ...)  DUSUK                      |
|                                                           |
+----------------------------------------------------------+
```

### Alias Config

```yaml
# config.yml
aliases:
  # TMDb shortcuts
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show

  # Renamer shortcuts
  p: job.plugins.renamer.parsed
  movie: job.plugins.renamer.parsed.movie
  show: job.plugins.renamer.parsed.show

  # FFProbe shortcuts
  video: job.plugins.ffprobe.video
  audio: job.plugins.ffprobe.audio
```

### Alias Kullanim

```jinja2
{# Uzun yol #}
{{ job.plugins.tmdb.movie.title }}

{# User alias ile #}
{{ m.title }}

{# Inline alias #}
{% set m = job.plugins.tmdb.movie %}
{{ m.title }} ({{ m.release_date[:4] }})
```

---

## 7. ENV VAR RESOLUTION

```
              ENV VAR PATTERNS

SYNTAX:
  ${VAR_NAME}           # Required
  ${VAR_NAME:-default}  # With default

RESOLUTION ORDER:
  1. .env dosyasi
  2. Environment variables
  3. Default value (varsa)

ORNEK:
  tmdb:
    api_key: ${TMDB_API_KEY}
    region: ${TMDB_REGION:-TR}

SONUC (.env'de TMDB_API_KEY=abc123):
  tmdb:
    api_key: abc123
    region: TR
```

---

## 8. MANIFEST SCHEMA (YENI)

```yaml
# plugins/{name}/manifest.yml

# Kimlik (required)
name: string
version: string
description: string # Optional

# Stage (required)
stage: input | parse | data | output

# Dependency (UNIFIED)
requires: List[string] # Implicit parsing
provides: List[string] # Standart terimler

# Execution
trigger_rule: all_success | one_success | always
reactive: bool # Default: false

# Implementation
class_name: string
entry_point: string # Default: client.py
config_schema: Dict # Optional
```

### Manifest Ornegi

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
description: TMDb metadata provider
stage: data
requires:
  - job.plugins.renamer.parsed
provides:
  - http.request
  - state.update
trigger_rule: all_success
reactive: false
class_name: TMDbPlugin
entry_point: client.py
config_schema:
  api_key:
    type: string
    required: true
  language:
    type: string
    default: en-US
```

---

## 9. VALIDATION

```
              CONFIG VALIDATION

+----------------------------------------------------------+
|  STARTUP VALIDATION                                       |
|                                                           |
|  1. YAML syntax kontrolu                                 |
|  2. Required fields kontrolu                             |
|  3. Type validation (config_schema)                      |
|  4. Path validation (targets exist?)                     |
|  5. Secret validation (api_key format)                   |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  RUNTIME VALIDATION                                       |
|                                                           |
|  1. Plugin requires satisfied?                           |
|  2. Template syntax valid?                               |
|  3. Condition syntax valid?                              |
+----------------------------------------------------------+
```

---

## 10. DOSYA YAPISI

```
archiverr/
|-- config.yml                  # Main config (FlexGet style)
|-- .env                        # Environment variables
|
|-- plugins/
|   |-- scanner/
|   |   |-- manifest.yml        # Plugin metadata
|   |   +-- client.py
|   |-- tmdb/
|   |   |-- manifest.yml
|   |   +-- client.py
|   +-- ...
|
+-- tasks/                      # External tasks (optional)
    |-- save_movie.yml
    |-- save_show.yml
    +-- summary_report.yml
```

---

## 11. MEVCUT vs YENI

```
MEVCUT (config.yml):
  plugins:
    tmdb:
      enabled: true
      api_key: xxx

YENI (config.yml):
  tmdb:
    api_key: xxx

DEGISIKLIKLER:
  - plugins: wrapper KALDIRILDI
  - enabled: key varsa true
  - !include directive eklendi
  - aliases: top-level key olarak
  - FlexGet/HA pattern
```

---

**Son Guncelleme:** 2025-12-02
