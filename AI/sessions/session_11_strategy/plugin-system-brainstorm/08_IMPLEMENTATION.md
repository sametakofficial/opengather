# IMPLEMENTATION PLAN

```yaml
tarih: 2025-12-02
durum: final
hedef: Execution session icin referans
```

---

## 1. PHASE OVERVIEW

```
              IMPLEMENTATION PHASES

+----------------------------------------------------------+
|  PHASE 1: Core Models (4-6 saat)                         |
|  - state/models.py: JobState, RunState                   |
|  - core/constants.py: Provides, Stages                   |
|  - Manifest migration                                    |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  PHASE 2: Plugin Services (4-6 saat)                     |
|  - core/plugins/services.py: PluginServices              |
|  - BasePlugin update                                     |
|  - Executor refactor                                     |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  PHASE 3: Config System (3-4 saat)                       |
|  - !include directive                                    |
|  - FlexGet style config                                  |
|  - Alias resolver                                        |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  PHASE 4: Stage Execution (4-6 saat)                     |
|  - Orchestrator refactor                                 |
|  - Stage-based execution                                 |
|  - DAG resolution                                        |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  PHASE 5: Testing (4-6 saat)                             |
|  - Unit tests                                            |
|  - Integration tests                                     |
|  - Migration tests                                       |
+----------------------------------------------------------+

TOPLAM: 19-28 saat
```

---

## 2. FILE CHANGES

### Yeni Dosyalar

```
+----------------------------------------------------------+
|  OLUSTURULACAK                                           |
+----------------------------------------------------------+
|                                                           |
|  core/constants.py           (~50 satir)                 |
|  - PROVIDES: set of valid provides                       |
|  - STAGES: list of stages                                |
|  - EVENTS: system events                                 |
|                                                           |
|  core/plugins/services.py    (~150 satir)                |
|  - PluginServices dataclass                              |
|  - StateService                                          |
|  - EventService                                          |
|  - LoggerService                                         |
|  - ConfigService                                         |
|                                                           |
|  core/alias.py               (~80 satir)                 |
|  - AliasResolver                                         |
|                                                           |
|  infrastructure/config/include.py (~60 satir)            |
|  - !include directive handler                            |
|                                                           |
+----------------------------------------------------------+
```

### Guncellenecek Dosyalar

```
+----------------------------------------------------------+
|  GUNCELLENECEK                                           |
+----------------------------------------------------------+
|                                                           |
|  state/models.py                                         |
|  - MatchState -> JobState                                |
|  - ExecutionState -> RunState                            |
|  - Nested dataclasses                                    |
|  Tahmini: +80 satir, -50 satir                          |
|                                                           |
|  state/manager.py                                        |
|  - Yeni JobState API                                     |
|  - Event emission update                                 |
|  Tahmini: +40 satir, -30 satir                          |
|                                                           |
|  core/plugins/executor.py                                |
|  - PluginServices injection                              |
|  - Stage-based execution                                 |
|  Tahmini: +60 satir, -40 satir                          |
|                                                           |
|  core/plugins/resolver.py                                |
|  - provides/after support                                |
|  Tahmini: +50 satir                                     |
|                                                           |
|  core/plugins/sdk/base.py                                |
|  - execute(job, services) signature                      |
|  Tahmini: +20 satir, -10 satir                          |
|                                                           |
|  core/plugins/sdk/manifest.py                            |
|  - stage, mode, provides, after fields                   |
|  Tahmini: +15 satir                                     |
|                                                           |
|  utils/config_loader.py                                  |
|  - !include support                                      |
|  - FlexGet style parsing                                 |
|  Tahmini: +50 satir                                     |
|                                                           |
|  __main__.py                                             |
|  - Orchestrator kullanimi                                |
|  Tahmini: -100 satir (Orchestrator'a tasinacak)         |
|                                                           |
+----------------------------------------------------------+
```

### Manifest Migration

```
+----------------------------------------------------------+
|  MANIFEST MIGRATION                                       |
+----------------------------------------------------------+
|                                                           |
|  plugins/scanner/manifest.yml                            |
|  - category: input -> stage: input                       |
|  - +mode: per_run                                        |
|  - +provides: [job.created, fs.read]                     |
|                                                           |
|  plugins/renamer/manifest.yml                            |
|  - category: output -> stage: parse                      |
|  - +mode: per_job                                        |
|  - +provides: [data.parsed, state.updated]               |
|  - depends_on -> after                                   |
|  - expects -> requires                                   |
|                                                           |
|  plugins/tmdb/manifest.yml                               |
|  - category: output -> stage: metadata                   |
|  - +mode: per_job                                        |
|  - +provides: [http.response, state.updated]             |
|  - depends_on -> after                                   |
|  - expects -> requires                                   |
|                                                           |
|  (Diger plugin'ler ayni pattern)                         |
|                                                           |
+----------------------------------------------------------+
```

---

## 3. EXECUTION ORDER

### Phase 1: Core Models

```
Step 1.1: core/constants.py olustur
  - VALID_PROVIDES set
  - STAGES list
  - SYSTEM_EVENTS list

Step 1.2: state/models.py guncelle
  - JobState, RunState dataclass
  - InputData, JobStatus nested class
  - to_dict() metodlari

Step 1.3: Manifest migration
  - tmdb/manifest.yml
  - scanner/manifest.yml
  - renamer/manifest.yml
  - ffprobe/manifest.yml

Step 1.4: Test
  - test_state_models.py
  - test_manifest_validation.py
```

### Phase 2: Plugin Services

```
Step 2.1: core/plugins/services.py olustur
  - PluginServices dataclass
  - StateService, EventService, LoggerService, ConfigService

Step 2.2: sdk/base.py guncelle
  - execute(job, services) signature
  - Eski context desteği kaldir

Step 2.3: executor.py guncelle
  - services = build_services(plugin)
  - plugin.execute(job, services)

Step 2.4: Plugin migration (sadece tmdb)
  - TMDbPlugin.execute(job, services)
  - get_debugger() -> services.logger

Step 2.5: Test
  - test_plugin_services.py
  - test_tmdb_new_signature.py
```

### Phase 3: Config System

```
Step 3.1: infrastructure/config/include.py olustur
  - !include handler
  - !include_list handler

Step 3.2: utils/config_loader.py guncelle
  - FlexGet style parsing
  - Manifest auto-merge

Step 3.3: core/alias.py olustur
  - AliasResolver class

Step 3.4: TemplateManager guncelle
  - Alias injection

Step 3.5: Test
  - test_include_directive.py
  - test_alias_resolver.py
```

### Phase 4: Stage Execution

```
Step 4.1: resolver.py guncelle
  - provides-based DAG
  - after support

Step 4.2: executor.py guncelle
  - Stage-based loop
  - per_job/per_run handling

Step 4.3: Orchestrator olustur/guncelle
  - Stage coordination
  - Error handling

Step 4.4: __main__.py simplify
  - Orchestrator.run() cagri

Step 4.5: Test
  - test_stage_execution.py
  - test_dag_resolution.py
```

### Phase 5: Testing

```
Step 5.1: Unit tests
  - Her yeni class icin test

Step 5.2: Integration tests
  - Full pipeline test

Step 5.3: Migration tests
  - Eski config ile calis
  - Yeni config ile calis

Step 5.4: Regression tests
  - python -m archiverr calisiyor mu?
```

---

## 4. RISK MITIGATION

```
+----------------------------------------------------------+
|  RISK                    MITIGATION                       |
+----------------------------------------------------------+
|                                                           |
|  Breaking change        Legacy manifest support           |
|                         (category -> stage auto-convert)  |
|                                                           |
|  Plugin migration       Sadece tmdb ile basla            |
|                         Diger plugin'ler Phase 2+        |
|                                                           |
|  Test coverage          Her step'te test yaz             |
|                                                           |
|  Performance            Benchmark before/after           |
|                                                           |
+----------------------------------------------------------+
```

---

## 5. SUCCESS CRITERIA

```
+----------------------------------------------------------+
|  PHASE 1 COMPLETE                                         |
|  [ ] state/models.py JobState/RunState iceriyor          |
|  [ ] core/constants.py VALID_PROVIDES iceriyor           |
|  [ ] tmdb/manifest.yml stage: metadata iceriyor          |
|  [ ] test_state_models.py gecti                          |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  PHASE 2 COMPLETE                                         |
|  [ ] PluginServices class mevcut                         |
|  [ ] TMDbPlugin services kullaniyor                      |
|  [ ] get_debugger() kaldirildi (tmdb icin)               |
|  [ ] test_plugin_services.py gecti                       |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  PHASE 3 COMPLETE                                         |
|  [ ] !include calisiyor                                  |
|  [ ] FlexGet style config calisiyor                      |
|  [ ] Alias resolver calisiyor                            |
|  [ ] test_config.py gecti                                |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  PHASE 4 COMPLETE                                         |
|  [ ] Stage-based execution calisiyor                     |
|  [ ] provides DAG calisiyor                              |
|  [ ] __main__.py < 100 satir                             |
|  [ ] test_execution.py gecti                             |
+----------------------------------------------------------+

+----------------------------------------------------------+
|  PHASE 5 COMPLETE                                         |
|  [ ] python -m archiverr calisiyor                       |
|  [ ] Tum testler gecti                                   |
|  [ ] Eski config ile backward compat                     |
+----------------------------------------------------------+
```

---

## 6. NOTES FOR EXECUTION SESSION

```
+----------------------------------------------------------+
|              EXECUTION SESSION NOTLARI                    |
+----------------------------------------------------------+
|                                                           |
|  1. Her phase sonunda test calistir                      |
|     python -m pytest tests/ -v                           |
|                                                           |
|  2. Syntax check yap                                     |
|     python -m py_compile src/archiverr/...               |
|                                                           |
|  3. Breaking change'lerde once test yaz                  |
|                                                           |
|  4. Sadece aktif plugin'lerle calis                      |
|     (omdb, tvdb, tvmaze dokunma)                         |
|                                                           |
|  5. Kod ornekleri bu strategy'de var ama                 |
|     DIREKT KOPYALAMA! Projenin mevcut durumuna           |
|     gore tekrar yaz.                                     |
|                                                           |
+----------------------------------------------------------+
```
