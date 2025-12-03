# PHASE 1: STATE MODELS

```yaml
öncelik: P1 (EN YÜKSEK)
tahmini_süre: 4-6 saat
bağımlılık: Yok (başlangıç noktası)
hedef: Yeni state modelleri, eski modeller korunur
risk: DÜŞÜK (yeni dosya, mevcut etkilenmez)
```

---

## MEVCUT DURUM ANALİZİ

### state/models.py

```python
# MEVCUT
class ExecutionStatus(Enum): ...
class ExecutionState: ...     # → RunState olacak
class PluginResult: ...       # → KALACAK (değişiklik az)
class MatchState: ...         # → JobState olacak
```

### state/manager.py

```python
# MEVCUT API
state.start_execution(config) → execution_id
state.register_match(index, input_path) → MatchState
state.update_plugin_result(match_index, plugin_name, result)
state.complete_match(match_index)
state.complete_execution()

# HEDEF API (aynı, sadece isim değişikliği)
state.start_run(config) → run_id
state.create_job(index, input_value, input_data) → JobState
state.update_plugin_result(job_index, plugin_name, result)
state.complete_job(job_index)
state.complete_run()
```

---

## TASK LİSTESİ

### 1.1 YENİ ENUM: RunStatus ve JobStatus

**Dosya:** `state/models.py`

**Nerede:** `ExecutionStatus` class'ından sonra

**Ne yapılacak:**

```
1. RunStatus enum ekle (ExecutionStatus'un kopyası)
2. JobStatus enum ekle (aynı değerler)
3. ExecutionStatus'u RunStatus'a alias yap
```

**Kabul Kriteri:**

```python
# Her ikisi de çalışmalı
from archiverr.state.models import ExecutionStatus  # ESKİ
from archiverr.state.models import RunStatus        # YENİ
assert ExecutionStatus.RUNNING == RunStatus.RUNNING
```

**Test:** `tests/unit/state/test_models.py`

---

### 1.2 InputData Dataclass

**Dosya:** `state/models.py`

**Nerede:** Enum'lardan sonra, state class'larından önce

**Ne yapılacak:**

```
InputData dataclass oluştur:
- value: str          # input.value (eski: input_path)
- data: Dict[str,Any] # input.data (YENİ)
```

**FINAL_DATASETS.yml Referansı:**

```yaml
input:
  value: /data/movies/Movie.Name.2024.1080p.mkv
  data:
    filename: Movie.Name.2024.1080p.mkv
    extension: mkv
    size_bytes: 5368709120
```

**Kabul Kriteri:**

```python
inp = InputData(value="/path/file.mkv", data={"ext": "mkv"})
assert inp.value == "/path/file.mkv"
assert inp.data["ext"] == "mkv"
```

---

### 1.3 OutputData Dataclass

**Dosya:** `state/models.py`

**Nerede:** InputData'dan sonra

**Ne yapılacak:**

```
OutputData dataclass oluştur:
- values: List[str]   # output.values (eski: - , yok)
- data: Dict[str,Any] # output.data (YENİ)
```

**FINAL_DATASETS.yml Referansı:**

```yaml
output:
  values:
    - /srv/archive/Movie (2024)/Movie.mkv
    - /srv/archive/Movie (2024)/Movie.nfo
  data:
    tasks:
      save_movie:
        type: save
        output: /srv/archive/Movie (2024)/Movie.mkv
```

**Kabul Kriteri:**

```python
out = OutputData(values=["/a.mkv"], data={"tasks": {}})
assert len(out.values) == 1
```

---

### 1.4 JobStatus Dataclass

**Dosya:** `state/models.py`

**Nerede:** OutputData'dan sonra

**Ne yapılacak:**

```
JobStatus dataclass oluştur:
- state: str           # "pending", "running", "completed", "failed"
- success: bool
- executed: List[str]  # executed plugin names
- failed: List[str]    # failed plugin names
- skipped: List[str]   # skipped plugin names
- started_at: datetime
- finished_at: datetime
- duration_ms: int
```

**FINAL_DATASETS.yml Referansı:**

```yaml
status:
  state: completed
  success: true
  executed: [scanner, renamer, tmdb, ffprobe, tasker]
  failed: []
  skipped: [tvdb]
```

**Kabul Kriteri:**

```python
status = JobStatus(state="running", success=True)
assert status.state == "running"
```

---

### 1.5 JobState Dataclass (YENİ)

**Dosya:** `state/models.py`

**Nerede:** JobStatus'tan sonra

**Ne yapılacak:**

```
JobState dataclass oluştur:
- index: int
- id: str              # "job_{run_id}_{index}"
- run_id: str
- input: InputData
- output: OutputData
- status: JobStatus
- plugins: Dict[str, Dict]  # Plugin data (ayrı collection'a taşınacak)

Metodlar:
- to_dict() → Dict
- from_dict(data) → JobState (classmethod)
```

**FINAL_DATASETS.yml Referansı:**

```yaml
job:
  index: 0
  id: job_run_abc123_0
  run_id: run_abc123
  input: ...
  output: ...
  status: ...
```

**Kabul Kriteri:**

```python
job = JobState(index=0, id="job_xxx_0", run_id="xxx", ...)
d = job.to_dict()
job2 = JobState.from_dict(d)
assert job.id == job2.id
```

---

### 1.6 RunStatus Dataclass

**Dosya:** `state/models.py`

**Nerede:** JobState'ten sonra

**Ne yapılacak:**

```
RunStatusData dataclass oluştur (enum ile karışmasın):
- state: str           # "pending", "running", "completed", "failed"
- success: bool
- total_jobs: int
- completed: int
- failed: int
- started_at: datetime
- finished_at: datetime
- duration_ms: int
```

**FINAL_DATASETS.yml Referansı:**

```yaml
status:
  state: completed
  success: true
  total_jobs: 10
  completed: 10
  failed: 0
```

---

### 1.7 RunState Dataclass (YENİ)

**Dosya:** `state/models.py`

**Nerede:** RunStatus'tan sonra

**Ne yapılacak:**

```
RunState dataclass oluştur:
- id: str              # "run_{uuid}"
- status: RunStatusData
- config: Dict[str,Any]  # Frozen config snapshot

Metodlar:
- to_dict() → Dict
- from_dict(data) → RunState (classmethod)
```

**Kabul Kriteri:**

```python
run = RunState(id="run_abc", status=..., config={})
d = run.to_dict()
run2 = RunState.from_dict(d)
assert run.id == run2.id
```

---

### 1.8 Backward Compatibility Aliases

**Dosya:** `state/models.py`

**Nerede:** Dosya sonunda

**Ne yapılacak:**

```python
# BACKWARD COMPATIBILITY
# Eski isimler hala çalışsın
ExecutionState = RunState
MatchState = JobState
```

**Kabul Kriteri:**

```python
# ESKİ kod hala çalışmalı
from archiverr.state.models import ExecutionState, MatchState
exec = ExecutionState(id="run_x", ...)  # RunState döner
match = MatchState(index=0, ...)        # JobState döner
```

---

### 1.9 StateManager API Genişletme

**Dosya:** `state/manager.py`

**Nerede:** Mevcut metodların yanına

**Ne yapılacak:**

```
Yeni metodlar EKLE (eskiler KALSIN):

# YENİ (wrapper)
start_run(config) → str
  └─ içinde: start_execution(config) çağırır

create_job(index, input_value, input_data=None) → JobState
  └─ içinde: register_match(index, input_value) çağırır
  └─ input_data'yı job.input.data'ya yazar

complete_job(job_index)
  └─ içinde: complete_match(job_index) çağırır

complete_run()
  └─ içinde: complete_execution() çağırır
```

**Kabul Kriteri:**

```python
# YENİ API
run_id = state.start_run(config)
job = state.create_job(0, "/path/file.mkv", {"ext": "mkv"})
state.complete_job(0)
state.complete_run()

# ESKİ API hala çalışmalı
exec_id = state.start_execution(config)
```

---

### 1.10 Job ID Generation

**Dosya:** `state/manager.py`

**Nerede:** `_generate_id` metodunun yanına

**Ne yapılacak:**

```
_generate_job_id(run_id, index) → str
  return f"job_{run_id}_{index}"
```

**FINAL_DATASETS.yml Referansı:**

```yaml
job:
  id: job_run_abc123_0
```

**Kabul Kriteri:**

```python
job_id = state._generate_job_id("run_abc123", 0)
assert job_id == "job_run_abc123_0"
```

---

### 1.11 input.data ve output.data Desteği

**Dosya:** `state/manager.py`

**Nerede:** `register_match` veya yeni `create_job` içinde

**Ne yapılacak:**

```
create_job metodunda:
1. InputData objesi oluştur
2. OutputData objesi oluştur (boş values, boş data)
3. JobState'e ata
```

**Kabul Kriteri:**

```python
job = state.create_job(0, "/path", {"filename": "test.mkv"})
assert job.input.data["filename"] == "test.mkv"
assert job.output.values == []
```

---

### 1.12 Unit Tests

**Dosya:** `tests/unit/state/test_new_models.py` (YENİ)

**Ne yapılacak:**

```
Test cases:
1. test_input_data_creation
2. test_output_data_creation
3. test_job_status_defaults
4. test_job_state_to_dict
5. test_job_state_from_dict
6. test_run_state_to_dict
7. test_backward_compat_execution_state
8. test_backward_compat_match_state
9. test_state_manager_new_api
10. test_state_manager_old_api_still_works
```

**Kabul Kriteri:**

```bash
pytest tests/unit/state/test_new_models.py -v
# ALL PASS
```

---

## BAĞIMLILIK GRAFİ

```
1.1 RunStatus/JobStatus enum
     │
     ├──→ 1.2 InputData
     │
     ├──→ 1.3 OutputData
     │
     └──→ 1.4 JobStatus dataclass
              │
              └──→ 1.5 JobState
                       │
                       └──→ 1.8 Backward Compat

1.6 RunStatusData
     │
     └──→ 1.7 RunState
              │
              └──→ 1.8 Backward Compat

1.5 + 1.7 ──→ 1.9 StateManager API
                   │
                   └──→ 1.10 Job ID
                            │
                            └──→ 1.11 input/output data
                                      │
                                      └──→ 1.12 Tests
```

---

## TAMAMLAMA KRİTERİ

Phase 1 TAMAMLANDI sayılır eğer:

- [ ] Tüm yeni dataclass'lar oluşturuldu
- [ ] Backward compatibility alias'ları çalışıyor
- [ ] StateManager yeni API'yi destekliyor
- [ ] Eski API hala çalışıyor
- [ ] Tüm unit testler geçiyor
- [ ] Mevcut `__main__.py` HALA çalışıyor (hiçbir şey kırılmadı)

---

**SONRAKİ PHASE:** `02_PHASE2_MANIFEST.md`
