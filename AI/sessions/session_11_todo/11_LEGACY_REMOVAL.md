# LEGACY REMOVAL - No Backward Compatibility

```yaml
created: 2025-12-04
priority: P1 - High
status: ready_for_implementation
principle: "Henüz ilk release yapılmadı - legacy gereksiz"
```

---

## PHILOSOPHY

```
+----------------------------------------------------------+
|              LEGACY YASAKTIR                              |
+----------------------------------------------------------+
|  - Refactoring sürecinde legacy kod YOKTUR
|  - Henüz ilk release yapılmadı
|  - Geriye uyumluluk gereksiz
|  - Deprecation warning yok, direkt kaldır
+----------------------------------------------------------+
```

---

## 1. TERMINOLOJI DEĞİŞİKLİKLERİ

### State Models
| LEGACY | YENİ | DOSYALAR |
|--------|------|----------|
| ExecutionState | RunState | state/models.py |
| MatchState | JobState | state/models.py |
| execution_id | run_id | tüm dosyalar |
| match | job | tüm dosyalar |
| input_path | input.value | state/models.py |
| not_supported | skipped | state/models.py |

### State Manager Methods
| LEGACY | YENİ | DOSYA |
|--------|------|-------|
| start_execution() | start_run() | state/manager.py |
| complete_execution() | complete_run() | state/manager.py |
| register_match() | create_job() | state/manager.py |
| get_match() | get_job() | state/manager.py |
| _matches | _jobs | state/manager.py |
| _execution | _run | state/manager.py |

---

## 2. DOSYALAR - LEGACY KALDIRMALAR

### state/models.py
```python
# KALDIRILACAK:
class ExecutionState:  # → RunState kullan
class MatchState:      # → JobState kullan
class ExecutionStatus: # → StateEnum kullan

# KORUNACAK:
class StateEnum
class RunState
class JobState
class PluginData
class InputData
class OutputData
```

### state/manager.py
```python
# KALDIRILACAK metodlar:
register_match()      # → create_job()
get_match()           # → get_job()
get_all_matches()     # → get_all_jobs()
complete_match()      # → complete_job()
build_template_context()  # Eski format

# KALDIRILACAK alanlar:
_matches: Dict        # → _jobs: Dict
GlobalStateManager    # Alias kaldır
```

### core/plugins/stage_executor.py
```python
# KALDIRILACAK:
- get_matches() fallback       # Line ~180
- _job_to_legacy_data()        # Tümüyle kaldır
- Legacy MatchState handling   # JobState kullan

# GÜNCELLENECEk:
- _create_jobs_from_matches()  # → _create_jobs()
```

---

## 3. API LEGACY

### Endpoints Rename
| LEGACY | YENİ |
|--------|------|
| /api/v1/executions | /api/v1/runs |
| /api/v1/matches | /api/v1/jobs |
| /api/v1/run | /api/v1/runs (POST) |

### Response Fields
```python
# LEGACY response:
{
  "execution_id": "...",
  "matches": [...]
}

# YENİ response:
{
  "run_id": "...",
  "jobs": [...]
}
```

---

## 4. CONFIG LEGACY

### Plugin Discovery
```yaml
# LEGACY (plugins wrapper):
plugins:
  tmdb:
    enabled: true
    api_key: xxx

# YENİ (FlexGet style):
tmdb:
  api_key: xxx
```

### Task Definition
```yaml
# LEGACY:
tasks:
  - name: print
    output: "{{ match_globals.input.path }}"

# YENİ:
tasks:
  - name: print
    template: "{{ job.input.value }}"
```

---

## 5. IMPLEMENTATION ORDER

1. **state/models.py** - Sadece yeni modelleri tut
2. **state/manager.py** - Yeni metodlar, eski kaldır
3. **core/plugins/stage_executor.py** - Legacy fallback kaldır
4. **api/\*** - Endpoint isimlerini değiştir
5. **plugins/\*** - execute() signature güncelle
6. **tests/\*** - Yeni terminoloji

---

## 6. GREp KOMUTLARI

```bash
# Legacy terminoloji bul:
grep -r "execution_id" src/
grep -r "MatchState" src/
grep -r "ExecutionState" src/
grep -r "register_match" src/
grep -r "get_match\|_matches" src/
grep -r "input_path" src/

# Legacy API bul:
grep -r "/executions" src/
grep -r "/matches" src/
```

---

## 7. CHECKLIST

- [ ] state/models.py - ExecutionState kaldır
- [ ] state/models.py - MatchState kaldır
- [ ] state/manager.py - Legacy metodları kaldır
- [ ] state/manager.py - _matches → _jobs
- [ ] stage_executor.py - _job_to_legacy_data kaldır
- [ ] api/executions/ → api/runs/ rename
- [ ] api/matches/ → api/jobs/ rename
- [ ] Tüm testleri güncelle
