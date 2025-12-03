# VALIDATION PHASES

```yaml
tarih: 2025-12-03
durum: brainstorm
odak: Static vs Dynamic validation, startup vs runtime
```

---

## 1. VALIDATION KATMANLARI

```
+----------------------------------------------------------+
|              VALIDATION TIMELINE                          |
+----------------------------------------------------------+
|                                                           |
|  STARTUP (Config Load)                                   |
|  |                                                       |
|  +-- Config syntax (YAML valid?)                        |
|  +-- Schema validation (required fields?)               |
|  +-- Plugin discovery (manifest.yml valid?)             |
|  +-- Conflict detection (provides cakisma?)             |
|  +-- Dynamic variable check (job.* yasak)               |
|  |                                                       |
|  v                                                       |
|  PRE-EXECUTION (Stage baslangici)                       |
|  |                                                       |
|  +-- Requires satisfaction (bagimliliklar hazir?)       |
|  +-- Plugin initialization (class yuklenebilir?)        |
|  |                                                       |
|  v                                                       |
|  RUNTIME (Plugin execution)                              |
|  |                                                       |
|  +-- Template rendering (Jinja2 valid?)                 |
|  +-- External HTTP response (TMDb, TVDb API 200?)       |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. STARTUP VALIDATION

### 2.1 Config Syntax

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  YAML parse hatasi     FATAL - Exit                      |
|  Encoding hatasi       FATAL - Exit                      |
|  Circular reference    FATAL - Exit                      |
+----------------------------------------------------------+
```

### 2.2 Schema Validation

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  Required field yok    ERROR - Hangi alan eksik?         |
|  Wrong type            ERROR - Beklenen vs gelen tip     |
|  Unknown field         WARNING - Typo olabilir           |
+----------------------------------------------------------+
```

### 2.3 Provides Conflict Detection

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  Ayni path, ayni stage ERROR - Conflict detayi           |
|  Parent-child overlap  WARNING - Potansiyel risk         |
|  Generic provides      INFO - Lock yok, dikkat           |
+----------------------------------------------------------+
```

### 2.4 Dynamic Variable Check

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  {{job.*}} provides    ERROR - Runtime degeri kullanilmaz|
|  {{run.*}} provides    ERROR - Runtime degeri kullanilmaz|
|  {{config.*}} provides OK - Startup'ta cozulebilir       |
+----------------------------------------------------------+
```

---

## 3. DYNAMIC DEGISKEN YASAGI

### 3.1 Neden Yasak?

```
+----------------------------------------------------------+
|              DYNAMIC DEGISKEN PROBLEMI                    |
+----------------------------------------------------------+
|                                                           |
|  SENARYO:                                                 |
|  provides:                                               |
|    - fs.write:{{job.plugins.tmdb.movie.title}}           |
|                                                           |
|  PROBLEM:                                                 |
|  1. Validation STARTUP'ta calisir                        |
|  2. job.plugins.tmdb.movie.title RUNTIME'da olusur       |
|  3. Startup'ta bu deger YOK                              |
|  4. Conflict detection YAPILAMAZ                         |
|                                                           |
|  SONUC: CONFIG ERROR                                      |
|                                                           |
+----------------------------------------------------------+
```

### 3.2 Gecerli vs Gecersiz

```yaml
# GECERLI - config.* startup'ta cozulur
provides:
  - fs.write:{{config.tasker.save_path}}

# GECERSIZ - job.* runtime'da olusur
provides:
  - fs.write:{{job.plugins.tmdb.movie.title}}

# GECERSIZ - run.* runtime'da olusur
provides:
  - fs.write:{{run.id}}
```

### 3.3 Error Mesaji

```
$ archiverr
ERROR: Invalid dynamic variable in provides

  Plugin: tasker
  Provides: fs.write:{{job.plugins.tmdb.movie.title}}

  Runtime variables (job.*, run.*) cannot be used in provides.
  Use static paths or config.* variables instead.

  Valid: fs.write:{{config.tasker.save_path}}
  Valid: fs.write:/data/archive
```

---

## 4. PRE-EXECUTION VALIDATION

### 4.1 Requires Satisfaction

```
+----------------------------------------------------------+
|              REQUIRES CHECK                               |
+----------------------------------------------------------+
|                                                           |
|  KONTROL: Plugin calistirilmadan once                    |
|                                                           |
|  requires:                                               |
|    - provides.http.request     # TMDb tamamlandi mi?     |
|    - job.plugins.renamer.parsed # Renamer verisi var mi? |
|                                                           |
|  AKSIYON:                                                 |
|  - Karsilanmayan requires = Plugin SKIP                  |
|  - trigger_rule'a gore davran                            |
|                                                           |
+----------------------------------------------------------+
```

### 4.2 Plugin Initialization

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  Class bulunamadi      ERROR - Plugin disable            |
|  Import hatasi         ERROR - Plugin disable            |
|  Init exception        ERROR - Plugin disable            |
+----------------------------------------------------------+
```

---

## 5. RUNTIME VALIDATION

### 5.1 Template Rendering

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  Undefined variable    WARNING - Bos string dondur       |
|  Syntax error          ERROR - Task skip                 |
|  Filter error          ERROR - Task skip                 |
+----------------------------------------------------------+
```

### 5.2 Path Operations

```
+----------------------------------------------------------+
|  KONTROL               AKSIYON                            |
+----------------------------------------------------------+
|  Source path yok       ERROR - Plugin fail               |
|  Dest path yazilmaz    ERROR - Plugin fail               |
|  Disk dolu             ERROR - Plugin fail               |
+----------------------------------------------------------+
```

---

## 6. ERROR SEVIYELERI

```
+----------------------------------------------------------+
|  SEVIYE      NE OLUR                   ORNEK              |
+----------------------------------------------------------+
|                                                           |
|  FATAL       Uygulama kapanir          config.yml yok    |
|                                                           |
|  ERROR       Component disable         Invalid manifest   |
|              Diger componentler devam  Plugin import fail |
|                                                           |
|  WARNING     Log ve devam              Unknown field      |
|                                                           |
|  INFO        Sadece log                Using default      |
|                                                           |
+----------------------------------------------------------+
```

---

## 7. VALIDATION PIPELINE

```
                    archiverr start
                         |
                         v
+----------------------------------------------------------+
|  PHASE 1: Config Load                                    |
|  - YAML parse                                            |
|  - Env var resolution                                    |
|  - !include directive                                    |
+----------------------------------------------------------+
                         |
              +----------+----------+
              |                     |
           SUCCESS               FAIL
              |                     |
              v                     v
+----------------------------------------------------------+
|  PHASE 2: Plugin Discovery                               |
|  - manifest.yml scan                                     |
|  - Manifest validation                                   |
|  - Config merge                                          |
+----------------------------------------------------------+
                         |
              +----------+----------+
              |                     |
           SUCCESS               FAIL
              |                     |
              v                     v
+----------------------------------------------------------+
|  PHASE 3: Static Validation                              |
|  - Schema check                                          |
|  - Dynamic variable check                                |
|  - Conflict detection                                    |
+----------------------------------------------------------+
                         |
              +----------+----------+
              |                     |
        NO CONFLICT            CONFLICT
              |                     |
              v                     v
         Continue              --force?
                                   |
                         +---------+---------+
                         |                   |
                        YES                  NO
                         |                   |
                         v                   v
                    Continue              EXIT
```

---

## 8. VALIDATION RESULT STRUCTURE

```python
@dataclass
class ValidationResult:
    valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationWarning]

    def has_fatal(self) -> bool:
        return any(e.level == 'fatal' for e in self.errors)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

@dataclass
class ValidationError:
    level: str  # fatal, error
    code: str   # E001, E002
    message: str
    location: str  # config.yml:15, manifest.yml:3
    suggestion: Optional[str]

@dataclass
class ValidationWarning:
    code: str   # W001, W002
    message: str
    location: str
```

**Uyari:** Ornek kod, yaklasimi gosterir. Execution session'da mevcut codebase'e uyarlanmalidir.

---

## 9. ERROR CODES

```
+----------------------------------------------------------+
|  CODE      SEVIYE    ACIKLAMA                             |
+----------------------------------------------------------+
|                                                           |
|  E001      FATAL     Config file not found               |
|  E002      FATAL     YAML parse error                    |
|  E003      FATAL     Required field missing              |
|                                                           |
|  E010      ERROR     Invalid manifest                    |
|  E011      ERROR     Plugin class not found              |
|  E012      ERROR     Plugin import failed                |
|                                                           |
|  E020      ERROR     Conflict detected                   |
|  E021      ERROR     Dynamic variable in provides        |
|                                                           |
|  W001      WARNING   Unknown field                       |
|  W002      WARNING   Parent-child path overlap           |
|  W003      WARNING   Generic provides (no path)          |
|                                                           |
+----------------------------------------------------------+
```

---

## 10. SONUC

```
+----------------------------------------------------------+
|              VALIDATION KATMANLARI                        |
+----------------------------------------------------------+
|                                                           |
|  STARTUP:                                                 |
|  - Config/manifest parse                                 |
|  - Schema validation                                     |
|  - Conflict detection                                    |
|  - Dynamic variable check                                |
|  -> Hata = Exit veya component disable                   |
|                                                           |
|  PRE-EXECUTION:                                          |
|  - Requires satisfaction                                 |
|  - Plugin initialization                                 |
|  -> Hata = Plugin skip                                   |
|                                                           |
|  RUNTIME:                                                 |
|  - Template rendering                                    |
|  - File operations                                       |
|  - API calls                                             |
|  -> Hata = Log ve devam (run durmasin)                  |
|                                                           |
+----------------------------------------------------------+
```

---

**Son Guncelleme:** 2025-12-03
