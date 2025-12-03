# SESSION 11 TODO - QUICK CHECKLIST

```yaml
kullanım: Her task sonrası işaretle
format: [x] tamamlandı, [ ] bekliyor, [-] skip
```

---

## PHASE 1: STATE MODELS

```
[ ] 1.1  RunStatus, JobStatus enum
[ ] 1.2  InputData dataclass
[ ] 1.3  OutputData dataclass
[ ] 1.4  JobStatus dataclass
[ ] 1.5  JobState dataclass
[ ] 1.6  RunStatusData dataclass
[ ] 1.7  RunState dataclass
[ ] 1.8  Backward compatibility aliases
[ ] 1.9  StateManager API genişletme
[ ] 1.10 Job ID generation
[ ] 1.11 input.data, output.data desteği
[ ] 1.12 Unit tests

PHASE 1 TAMAMLANDI: [ ]
```

---

## PHASE 2: MANIFEST SCHEMA

```
[ ] 2.1  Stage enum
[ ] 2.2  TriggerRule enum
[ ] 2.3  PluginManifest stage field
[ ] 2.4  PluginManifest requires field
[ ] 2.5  trigger_rule, reactive, entry_point fields
[ ] 2.6  effective_stage property
[ ] 2.7  effective_requires property
[ ] 2.8  Discovery.py güncelleme
[ ] 2.9  Stage ordering utility
[ ] 2.10 Unit tests

PHASE 2 TAMAMLANDI: [ ]
```

---

## PHASE 3: CONFIG SYSTEM

```
[ ] 3.1  AliasParser utility
[ ] 3.2  System alias defaults
[ ] 3.3  Config normalizer
[ ] 3.4  Include directive handler
[ ] 3.5  Alias extraction
[ ] 3.6  Config options defaults
[ ] 3.7  Config loader integration
[ ] 3.8  Unit tests

PHASE 3 TAMAMLANDI: [ ]
```

---

## PHASE 4: STAGE EXECUTOR

```
[ ] 4.1  StageExecutor base class
[ ] 4.2  Plugin stage grouping
[ ] 4.3  Stage execution order
[ ] 4.4  Execute input stage (per_run)
[ ] 4.5  Execute per-job stage
[ ] 4.6  Plugin execution wrapper
[ ] 4.7  Requires checker
[ ] 4.8  Services factory
[ ] 4.9  Full run execution
[ ] 4.10 Event emission
[ ] 4.11 Error handling
[ ] 4.12 Parallel execution support
[ ] 4.13 Integration (standalone test)
[ ] 4.14 Unit tests

PHASE 4 TAMAMLANDI: [ ]
```

---

## PHASE 5: VALIDATION

```
[ ] 5.1  ValidationResult dataclass
[ ] 5.2  Error codes registry
[ ] 5.3  ConflictDetector class
[ ] 5.4  Path overlap algorithm
[ ] 5.5  DynamicVariableChecker
[ ] 5.6  ManifestValidator
[ ] 5.7  RequiresValidator
[ ] 5.8  ValidationPipeline
[ ] 5.9  CLI error display
[ ] 5.10 Unit tests

PHASE 5 TAMAMLANDI: [ ]
```

---

## PHASE 6: MIGRATION

```
[ ] 6.1  Orchestrator skeleton
[ ] 6.2  Component initialization
[ ] 6.3  Plugin discovery integration
[ ] 6.4  Validation integration
[ ] 6.5  Run method
[ ] 6.6  Report generation
[ ] 6.7  Teardown method
[ ] 6.8  Simplified __main__.py
[ ] 6.9  Plugin manifest migration script
[ ] 6.10 Integration tests

PHASE 6 TAMAMLANDI: [ ]
```

---

## GENEL İLERLEME

```
PHASE 1: [____________________] 0/12  = 0%
PHASE 2: [____________________] 0/10  = 0%
PHASE 3: [____________________] 0/8   = 0%
PHASE 4: [____________________] 0/14  = 0%
PHASE 5: [____________________] 0/10  = 0%
PHASE 6: [____________________] 0/10  = 0%
─────────────────────────────────────────
TOPLAM:  [____________________] 0/64  = 0%
```

---

## NOTLAR

### Atlanabilir Tasklar

Aşağıdakiler opsiyonel, gerekirse skip edilebilir:

- 3.4 Include directive (basit implementasyon yeterli)
- 4.12 Parallel execution (ilk aşamada sequential)
- 5.7 RequiresValidator (warning only)

### Kritik Tasklar (Atlanamaz)

- 1.5 JobState (tüm sistem buna bağlı)
- 1.8 Backward compat (breaking change önleme)
- 2.6 effective_stage (discovery için şart)
- 4.6 Plugin execution wrapper (execution için şart)
- 4.11 Error handling (philosophy gereği)

### Test Önceliği

Her phase sonunda ilgili testlerin geçmesi ZORUNLU:

```bash
# Phase 1 sonrası
pytest tests/unit/state/ -v

# Phase 2 sonrası
pytest tests/unit/plugins/ -v

# Phase 4 sonrası
pytest tests/unit/core/ -v

# Phase 6 sonrası
pytest tests/integration/ -v
```

---

## BAŞLAMA KOMUTU

```bash
cd /home/samet/Workspace/archiverr

# Phase 1'e başla
code src/archiverr/state/models.py

# Task 1.1'i implement et
# Test yaz
# Commit et
```

---

**SON GÜNCELLEME:** 2025-12-04
