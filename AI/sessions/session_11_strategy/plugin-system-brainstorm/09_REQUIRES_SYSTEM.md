# REQUIRES SYSTEM (UNIFIED)

```yaml
tarih: 2025-12-02
durum: final
kritik: Plugin siralama sisteminin TEK degeri
```

---

## 1. ENDUSTRI ARASTIRMASI

```
+----------------------------------------------------------+
|  SISTEM              DEPENDENCY SYNTAX                    |
+----------------------------------------------------------+
|  Docker Compose      depends_on:                         |
|                        db:                               |
|                          condition: service_healthy      |
|                          restart: true                   |
|                                                           |
|  Airflow             set_upstream() / set_downstream()   |
|                      trigger_rule: all_success           |
|                                                           |
|  FlexGet             Phase based (implicit ordering)     |
|                      No explicit depends_on              |
+----------------------------------------------------------+

Docker Compose conditions:
  - service_started
  - service_healthy  
  - service_completed_successfully

Airflow trigger rules:
  - all_success, one_success, all_done
  - all_failed, one_failed
  - none_failed, always
```

## 2. ARCHIVERR KARARI

```
+----------------------------------------------------------+
|  ONCEKI (AYRI ALANLAR)     YENI (UNIFIED)                |
+----------------------------------------------------------+
|  after: [renamer]          requires:                     |
|  waits_for: [x]              - renamer                   |
|  depends_on: [y]             - job.parsed                |
|  triggers_on: [z]            - http.response             |
|                                                           |
|  4 AYRI ALAN               1 TEK ALAN (prefix yok)       |
+----------------------------------------------------------+
```

## 3. REQUIRES SYNTAX

```yaml
# Syntax: Implicit parsing (FlexGet style)
requires:
  - job.plugins.renamer.parsed       # job. ile basliyorsa -> state
  - http.response                    # provides listesindeyse -> provide
  - renamer                          # plugin adiysa -> plugin

# Parser otomatik ayirir:
#   job.* veya run.* -> state
#   provides registry'de varsa -> provide  
#   plugin adiysa -> plugin
```

```
+----------------------------------------------------------+
|  DEGER TIPI       NASIL ANLASILIR                         |
+----------------------------------------------------------+
|  state            job.* veya run.* ile baslar            |
|  provide          Provides registry'de kayitli           |
|  plugin           Plugin discovery'de mevcut             |
+----------------------------------------------------------+
```

---

## 4. DEFAULT ALIAS LISTESI

```
+----------------------------------------------------------+
|              SISTEM DEFAULT ALIAS'LARI                    |
+----------------------------------------------------------+
|                                                           |
|  ALIAS          SOURCE              READONLY?             |
+----------------------------------------------------------+
|  job            GlobalState.job     NO                   |
|  jobs           GlobalState.jobs    YES                  |
|  run            GlobalState.run     YES                  |
|  provides       ProvideRegistry     YES                  |
|  events         EventBus.history    YES                  |
|  config         ConfigLoader        YES                  |
+----------------------------------------------------------+

KULLANIM:
  {{ job.plugins.tmdb.movie.title }}
  {{ provides.http.response }}
  {{ events.file.created }}
  {{ config.tmdb.language }}
  
KISA ALIAS (kullanici tanimlar):
  aliases:
    m: job.plugins.tmdb.movie
    p: provides
    
  {{ m.title }}
  {{ p.fs.write }}
```

---

## 4. REQUIRES ORNEKLERI

### Scanner (Input Stage)

```yaml
name: scanner
stage: input
requires: []                          # Hicbir sey beklemiyor
provides:
  - job.created
  - fs.read
```

### Renamer (Extract Stage)

```yaml
name: renamer
stage: extract
requires: []                          # Stage sirasi yeterli (extract > input)
provides:
  - metadata.parsed
```

### TMDb (Enrich Stage)

```yaml
name: tmdb
stage: enrich
requires:
  - metadata.parsed                   # provide olarak algilanir
provides:
  - http.response
  - metadata.movie
```

### Tasker (Output Stage)

```yaml
name: tasker
stage: output
requires:
  - http.response                     # provide olarak algilanir
provides:
  - fs.write
```

---

## 5. RESOLUTION FLOW

```
              REQUIRES RESOLUTION

+----------------------------------------------------------+
|  Plugin: tasker                                          |
|  requires:                                               |
|    - http.response                                       |
|  trigger_rule: all_complete (default)                    |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  STEP 1: Identify type                                   |
|    "http.response"                                       |
|    -> job.* ile baslamiyor -> state DEGIL               |
|    -> ProvideRegistry'de var mi? -> EVET                |
|    -> TYPE = provide                                     |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  STEP 2: Check satisfaction                              |
|    ProvideRegistry.is_complete("http.response")          |
|    -> False (TMDb henuz bitmedi)                         |
|    -> WAIT                                               |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  STEP 3: TMDb completes                                  |
|    services.provides.complete("http.response")           |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  STEP 4: Re-check (trigger_rule: all_complete)           |
|    ProvideRegistry.is_complete("http.response") -> True  |
|    All requires satisfied -> EXECUTE                     |
+----------------------------------------------------------+
```

---

## 6. TRIGGER RULE (Airflow'dan)

```
AIRFLOW TRIGGER RULES:
  all_success   - Tum upstream SUCCESS (default)
  one_success   - En az biri SUCCESS
  all_done      - Hepsi EXECUTED (success/fail)
  always        - Upstream durumuna bakmadan calistir

NOT: Airflow'da bir task'a sadece BIR trigger_rule atanabilir.
Kaynak: https://airflow.apache.org/
```

```
+----------------------------------------------------------+
|  ARCHIVERR TRIGGER RULES                                  |
+----------------------------------------------------------+
|  RULE             SEMANTIK                                |
+----------------------------------------------------------+
|  all_success      Tum requires SUCCESS (default)         |
|  one_success      En az biri SUCCESS                     |
|  always           Stage gelince hemen calistir           |
+----------------------------------------------------------+
```

## 7. REACTIVE MODE (triggers_on yerine)

```
+----------------------------------------------------------+
|  REACTIVE MODE                                            |
+----------------------------------------------------------+
|                                                           |
|  trigger_rule: NE ZAMAN calisir                          |
|  reactive: TEKRAR calisir mi                             |
|                                                           |
|  Ayri alanlar - birlikte kullanilabilir                  |
+----------------------------------------------------------+
```

### Manifest Ornekleri

```yaml
# Normal plugin
name: tasker
requires:
  - http.response
trigger_rule: all_success             # Default
reactive: false                       # Default
```

```yaml
# Reactive plugin (her degisiklikte tekrar calis)
name: watcher
requires:
  - job.plugins.tmdb.movie
reactive: true                        # Degisiklikte tekrar calis
```

```yaml
# Fallback plugin (biri basarili olunca calis)
name: fallback_handler
requires:
  - tmdb
  - tvdb
trigger_rule: one_success             # Biri basarili olunca
```

---

## 8. MANIFEST ORNEKLERI

```yaml
# plugins/scanner/manifest.yml
name: scanner
version: 1.0.0
stage: input
requires: []
provides:
  - job.created
class_name: ScannerPlugin
```

```yaml
# plugins/renamer/manifest.yml
name: renamer
version: 1.0.0
stage: extract
requires: []
provides:
  - metadata.parsed
class_name: RenamerPlugin
```

```yaml
# plugins/tmdb/manifest.yml
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

```yaml
# plugins/tasker/manifest.yml
name: tasker
version: 1.0.0
stage: output
requires:
  - http.response                     # provide
provides:
  - fs.write
class_name: TaskerPlugin
```

```yaml
# plugins/watcher/manifest.yml (REACTIVE)
name: watcher
version: 1.0.0
stage: output
requires:
  - job.plugins.tmdb.movie            # state
reactive: true                        # Her degisiklikte
provides:
  - notification.sent
class_name: WatcherPlugin
```

---

## CHANGELOG

```
2025-12-02 v3:
  - trigger_rule sadeleştirildi: all_success, one_success, always
  - on_change -> reactive: true olarak ayrildi
  - Alias ve Stage konulari kendi dosyalarina tasindi
  - Standart terimler 10_STANDARD_TERMS.md'ye tasindi

2025-12-02 v2:
  - trigger_rule sistemi eklendi (Airflow)
  - Implicit syntax karari

2025-12-02 v1:
  - 4 alan -> 1 alan (requires UNIFIED)
```
