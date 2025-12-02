# MANIFEST SCHEMA

```yaml
tarih: 2025-12-02
durum: final
```

---

## 1. CURRENT

```yaml
# plugins/tmdb/manifest.yml (mevcut)
name: tmdb
version: 1.0.0
category: output
depends_on: [renamer]
expects: [renamer.parsed]
class_name: TMDbPlugin
```

Sorunlar:
- category sadece 2 deger (input/output)
- depends_on ve expects ayrimi belirsiz
- execution_mode yok

---

## 2. FEATURE

```yaml
# plugins/tmdb/manifest.yml (yeni)
name: tmdb
version: 1.0.0
stage: enrich

requires:
  - metadata.parsed
provides:
  - http.response
  - metadata.movie

class_name: TMDbPlugin
```

---

## 3. WHY

### Endustri Karsilastirmasi

```
SISTEM          SIRALAMA           CAPABILITY
--------------------------------------------------
FlexGet         phase (5 tip)      -
Home Assistant  after_dependencies dependencies
Airflow         upstream/downstream -
Docker          depends_on          -
OSGi            -                  Provide-Capability
Gradle          -                  capabilities
```

### Karar

```
+----------------------------------------------------------+
|                    MANIFEST FIELD KARARLARI               |
+----------------------------------------------------------+
|                                                           |
|  stage          Semantik kategori (4 deger)              |
|                 input | extract | enrich | output         |
|                 Execution grouping icin                   |
|                                                           |
|  mode           Calisma modu (2 deger)                   |
|                 per_job | per_run                         |
|                 Scanner = per_run, TMDb = per_job         |
|                                                           |
|  requires       Implicit parsing                        |
|                 state (job.*), provide, plugin          |
|                 Parser otomatik ayirir                   |
|                                                           |
|  provides       Islem bazli capability                   |
|                 Ne yaptigini declare eder                 |
|                 Ornek: http.response, fs.write            |
|                                                           |
|  REDDEDILEN:                                              |
|    after, waits_for, depends_on, triggers_on             |
|    Hepsi requires icinde birlestirildi                   |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. SCHEMA

### Manifest Resolution Flow

```
                         DISCOVERY
                             |
                             v
+----------------------------------------------------------+
|  1. plugins/*/manifest.yml tara                          |
|  2. YAML parse et                                        |
|  3. Pydantic validation                                  |
+----------------------------------------------------------+
                             |
                             v
+----------------------------------------------------------+
|                    DEPENDENCY GRAPH                       |
|                                                           |
|  scanner ──────> renamer ──────> tmdb ──────> tasker     |
|     |               |              |             |        |
|  provides:      provides:      requires:     requires:    |
|  job.created    metadata.      metadata.     http.        |
|                 parsed         parsed        response     |
|                                provides:     provides:    |
|                                http.response fs.write     |
|                                metadata.movie             |
+----------------------------------------------------------+
                             |
                             v
+----------------------------------------------------------+
|                   TOPOLOGICAL SORT                        |
|                                                           |
|  Stage bazli gruplama:                                   |
|    INPUT   -> [scanner]                                  |
|    EXTRACT -> [renamer, ffprobe]                         |
|    ENRICH  -> [tmdb, tvdb]                               |
|    OUTPUT  -> [tasker]                                   |
|                                                           |
|  Stage icinde siralama:                                  |
|    1. requires/provides DAG'a gore                       |
|    2. trigger_rule'a gore (all_success, one_success)     |
+----------------------------------------------------------+
```

### Pydantic Model

```python
class PluginManifest(BaseModel):
    # Kimlik
    name: str
    version: str
    description: Optional[str] = None
    
    # Stage
    stage: Literal["input", "extract", "enrich", "output"]
    
    # Dependency (implicit parsing)
    requires: List[str] = []           # state, provide, plugin
    provides: List[str] = []           # Standart terimler
    
    # Execution
    trigger_rule: Literal["all_success", "one_success", "always"] = "all_success"
    reactive: bool = False
    
    # Implementation
    class_name: str
    entry_point: str = "client.py"
    config_schema: Optional[Dict[str, Any]] = None
```

---

## 5. ORNEKLER

### Scanner (Input)

```yaml
name: scanner
version: 1.0.0
stage: input
requires: []
provides:
  - job.created
  - fs.read
class_name: ScannerPlugin
```

### Renamer (Extract)

```yaml
name: renamer
version: 1.0.0
stage: extract
requires: []
provides:
  - metadata.parsed
class_name: RenamerPlugin
```

### TMDb (Enrich)

```yaml
name: tmdb
version: 1.0.0
stage: enrich
requires:
  - metadata.parsed
provides:
  - http.response
  - metadata.movie
class_name: TMDbPlugin
```

### Tasker (Output)

```yaml
name: tasker
version: 1.0.0
stage: output
requires:
  - http.response
provides:
  - fs.write
class_name: TaskerPlugin
```

### Watcher (Reactive)

```yaml
name: watcher
version: 1.0.0
stage: output
requires:
  - job.plugins.tmdb.movie
reactive: true
provides:
  - notification.sent
class_name: WatcherPlugin
```

---

## 6. VALIDATION

```
+----------------------------------------------------------+
|                    VALIDATION                             |
+----------------------------------------------------------+
|                                                           |
|  REQUIRED FIELDS                                          |
|  - name: non-empty string                                |
|  - version: semver format                                |
|  - stage: input | extract | enrich | output              |
|  - class_name: valid Python identifier                   |
|                                                           |
|  PROVIDES                                                 |
|  - Standart listeden (bkz: 10_STANDARD_TERMS.md)         |
|  - Custom: custom.* prefix                               |
|                                                           |
|  REQUIRES (implicit parsing)                              |
|  - job.* veya run.* -> state                             |
|  - Provides listesinde -> provide                        |
|  - Plugin adiysa -> plugin                               |
|                                                           |
+----------------------------------------------------------+
```

---

## CHANGELOG

```
2025-12-02 v2:
  - after, mode KALDIRILDI
  - trigger_rule ve reactive eklendi
  - Stage isimleri: extract, enrich
  - Provides: metadata.parsed, metadata.movie
  - Implicit parsing (prefix yok)
```
