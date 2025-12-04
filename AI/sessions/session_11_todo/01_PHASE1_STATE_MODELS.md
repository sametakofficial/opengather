# PHASE 1: STATE MODELS & TERMİNOLOJİ

```yaml
phase: 1
öncelik: 🔴 KRİTİK
tahmini_süre: 4-6 saat
bağımlılık: yok (temel phase)
strateji_belgesi: 01_state_structure_and_naming.md
test_türü: unit
```

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Dosya: `src/archiverr/state/models.py`

```python
# MEVCUT YAPI (170 satır)

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ExecutionState:
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    success: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MatchState:
    index: int
    input_path: str
    execution_id: str
    success: bool = True
    status: ExecutionStatus = ExecutionStatus.PENDING
    executed_plugins: List[str] = field(default_factory=list)
    failed_plugins: List[str] = field(default_factory=list)
    not_supported_plugins: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    plugins: Dict[str, Dict[str, Any]] = field(default_factory=dict)
```

### 1.2 Kullanım Noktaları (Değişecek)

```
src/archiverr/
├── __main__.py              # state.register_match(), state.start_execution()
├── state/
│   ├── manager.py           # GlobalStateManager (ExecutionState, MatchState kullanır)
│   └── models.py            # ← DEĞİŞECEK
├── api/v1/
│   ├── executions/          # ExecutionState'e bağlı
│   └── matches/             # MatchState'e bağlı
└── infrastructure/
    └── persistence/         # to_dict() kullanır
```

---

## 2. HEDEF YAPI

### 2.1 Yeni State Models (FINAL_DATASETS.yml uyumlu)

```python
# HEDEF YAPI

class StateEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class InputData:
    """Job input verisi"""
    value: str                    # Eski: path → Yeni: value (virtual file desteği)
    data: Dict[str, Any] = field(default_factory=dict)
    # data içeriği:
    #   filename: str
    #   extension: str
    #   size_bytes: int
    #   modified_at: datetime
    #   source: str (filesystem|api|manual)

@dataclass
class OutputData:
    """Job output verisi"""
    values: List[str] = field(default_factory=list)  # Output paths
    data: Dict[str, Any] = field(default_factory=dict)  # Task results

@dataclass
class JobStatus:
    """Job durumu"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: List[str] = field(default_factory=list)   # Eski: executed_plugins
    failed: List[str] = field(default_factory=list)     # Eski: failed_plugins
    skipped: List[str] = field(default_factory=list)    # Eski: not_supported_plugins
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

@dataclass
class JobState:
    """
    Per-job state (Eski: MatchState)

    ÖNEMLİ: plugins bu class'ta YOK!
    - plugins ayrı MongoDB collection'da (memory management)
    - Template context'e 'plugins' alias olarak inject edilir
    - Erişim: services.state.get_plugin_data(job.id, "tmdb")
    """
    index: int
    run_id: str                   # Eski: execution_id
    id: str = ""                  # job_{run_id}_{index}
    input: InputData = field(default_factory=lambda: InputData(""))
    output: OutputData = field(default_factory=OutputData)
    status: JobStatus = field(default_factory=JobStatus)
    # NOT: plugins ayrı collection'da (P2'de) - BURADA YOK!

@dataclass
class RunStatus:
    """Run durumu"""
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    total_jobs: int = 0           # Eski: total_matches
    completed: int = 0            # Eski: completed_matches
    failed: int = 0               # Eski: failed_matches
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0

@dataclass
class RunState:
    """Execution-level state (Eski: ExecutionState)"""
    id: str                       # run_abc123
    status: RunStatus = field(default_factory=RunStatus)
    config: Dict[str, Any] = field(default_factory=dict)
    # NOT: jobs ayrı collection'da (P2'de)
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: Enum ve Yardımcı Dataclass'lar

**Dosya:** `src/archiverr/state/models.py`

**İş:**

1. `ExecutionStatus` → `StateEnum` olarak yeniden adlandır
2. `InputData` dataclass ekle
3. `OutputData` dataclass ekle

**Test:**

```python
def test_input_data_defaults():
    inp = InputData(value="/path/to/file.mkv")
    assert inp.value == "/path/to/file.mkv"
    assert inp.data == {}

def test_output_data_defaults():
    out = OutputData()
    assert out.values == []
    assert out.data == {}
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Bu dataclass tanımları mevcut `models.py` yapısıyla uyumlu mu kontrol et
- Default değerler senin kullanım senaryonla örtüşüyor mu?

---

### ADIM 2: JobStatus Dataclass

**İş:**

1. `JobStatus` dataclass oluştur
2. `executed/failed/skipped` list'leri ekle

**Test:**

```python
def test_job_status_defaults():
    status = JobStatus()
    assert status.state == StateEnum.PENDING
    assert status.success == True
    assert status.executed == []
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Test kodu örneğini mevcut test yapısına uyarla
- `skipped` kullan (FINAL_DATASETS.yml'de böyle)

---

### ADIM 3: JobState Dataclass (MatchState'i Değiştir)

**İş:**

1. `MatchState` → `JobState` olarak yeniden adlandır
2. `input_path` → `input: InputData` değiştir
3. `execution_id` → `run_id` değiştir
4. `output: OutputData` ekle
5. `status: JobStatus` nested yap
6. `__post_init__` ile job_id oluştur

**Test:**

```python
def test_job_state_id_generation():
    job = JobState(index=0, run_id="run_abc123")
    assert job.id == "job_run_abc123_0"

def test_job_state_input():
    job = JobState(index=0, run_id="test", input=InputData("/path/file.mkv"))
    assert job.input.value == "/path/file.mkv"
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- `__post_init__` metodu mevcut kodda nasıl kullanılıyor kontrol et
- Test örneğini pytest formatına uyarla

---

### ADIM 4: RunStatus ve RunState Dataclass'lar

**İş:**

1. `RunStatus` dataclass oluştur
2. `ExecutionState` → `RunState` olarak yeniden adlandır
3. Nested `status: RunStatus` yap
4. `config_snapshot` → `config` olarak yeniden adlandır

**Test:**

```python
def test_run_state_defaults():
    run = RunState(id="run_abc123")
    assert run.id == "run_abc123"
    assert run.status.state == StateEnum.PENDING
    assert run.status.total_jobs == 0

def test_run_status_counters():
    status = RunStatus(total_jobs=10, completed=5, failed=1)
    assert status.total_jobs == 10
```

---

### ADIM 5: to_dict() Metodları

**İş:**

1. Her dataclass için `to_dict()` metodu güncelle
2. API response yapısına uygun format
3. MongoDB document yapısına uygun format

**Test:**

```python
def test_job_state_to_dict():
    job = JobState(index=0, run_id="run_abc", input=InputData("/test.mkv"))
    d = job.to_dict()
    assert d["index"] == 0
    assert d["run_id"] == "run_abc"
    assert d["input"]["value"] == "/test.mkv"
    assert "id" in d  # job_run_abc_0
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Mevcut `to_dict()` metodunu incele, yeni yapıya adapte et
- FINAL_DATASETS.yml'deki yapıyla karşılaştır

---

### ADIM 6: Backward Compatibility Alias'lar

**Geçici çözüm - migration sırasında:**

```python
# Backward compatibility (DEPRECATED - kaldırılacak)
ExecutionStatus = StateEnum  # Alias
ExecutionState = RunState    # Alias
MatchState = JobState        # Alias
```

**⚠️ Bu alias'lar sadece geçiş dönemi için!**

---

## 4. MANAGER DEĞİŞİKLİKLERİ

### 4.1 GlobalStateManager → StateManager

**Dosya:** `src/archiverr/state/manager.py`

**Değişiklik listesi:**

1. Class adı: `GlobalStateManager` → `StateManager`
2. Method adları:
   - `start_execution()` → `start_run()`
   - `register_match()` → `create_job()`
   - `complete_match()` → `complete_job()`
   - `complete_execution()` → `complete_run()`
3. Field adları:
   - `_execution` → `_run`
   - `_matches` → `_jobs`

**NOT:** Singleton pattern'i koru, sadece method adlarını değiştir. DI pattern P4'te.

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests (Yeni)

```python
# tests/unit/state/test_models.py

class TestStateEnum:
    def test_values(self):
        assert StateEnum.PENDING.value == "pending"
        assert StateEnum.COMPLETED.value == "completed"

class TestInputData:
    def test_basic(self):
        inp = InputData(value="/path/file.mkv")
        assert inp.value == "/path/file.mkv"

    def test_with_data(self):
        inp = InputData(
            value="/path/file.mkv",
            data={"size_bytes": 1024, "source": "filesystem"}
        )
        assert inp.data["size_bytes"] == 1024

class TestJobState:
    def test_id_generation(self):
        job = JobState(index=0, run_id="run_abc123")
        assert job.id == "job_run_abc123_0"

    def test_to_dict(self):
        job = JobState(index=0, run_id="run_abc123")
        d = job.to_dict()
        assert "id" in d
        assert "input" in d
        assert "output" in d
        assert "status" in d

class TestRunState:
    def test_defaults(self):
        run = RunState(id="run_abc123")
        assert run.status.total_jobs == 0

    def test_to_dict(self):
        run = RunState(id="run_abc123")
        d = run.to_dict()
        assert d["id"] == "run_abc123"
```

### 5.2 Regression Tests

```python
# Mevcut davranışın korunduğunu doğrula

def test_backward_compat_alias():
    """ExecutionState alias hala çalışıyor mu?"""
    from archiverr.state.models import ExecutionState, RunState
    assert ExecutionState is RunState

def test_existing_usage_pattern():
    """Mevcut kod paterni hala çalışıyor mu?"""
    from archiverr.state import GlobalStateManager
    state = GlobalStateManager()
    # Eski API hala çalışmalı (geçiş döneminde)
```

---

## 6. PHASE 1 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `StateEnum` enum oluşturuldu
- [ ] `InputData`, `OutputData` dataclass'lar oluşturuldu
- [ ] `JobStatus`, `RunStatus` dataclass'lar oluşturuldu
- [ ] `JobState` (eski MatchState) oluşturuldu
- [ ] `RunState` (eski ExecutionState) oluşturuldu
- [ ] Tüm `to_dict()` metodları çalışıyor
- [ ] Backward compatibility alias'lar eklendi
- [ ] Unit testler yazıldı ve PASS
- [ ] Mevcut testler hala PASS (regression)

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ StateManager refactoring (P2'de)
- ❌ **main**.py değişiklikleri (P4'te)
- ❌ API endpoint değişiklikleri (P8'de)
- ❌ MongoDB collection değişiklikleri (P2'de)

---

## 7. GEÇİŞ PLANI

### Adım 1: Yeni modelleri EKLE (yan yana)

```python
# Eski modeller korunur
class ExecutionState: ...
class MatchState: ...

# Yeni modeller eklenir
class RunState: ...
class JobState: ...
```

### Adım 2: Alias'lar EKLE

```python
# Eski isimler yeni class'lara point eder
ExecutionState = RunState
MatchState = JobState
```

### Adım 3: Manager'ı GÜNCELLE (wrapper methods)

```python
class GlobalStateManager:
    def start_execution(self, config):
        return self.start_run(config)  # Yeni metodu çağır

    def start_run(self, config):
        # Gerçek implementasyon
```

### Adım 4: Test ve VALIDATE

### Adım 5: Eski kodları KALDIR (sonraki phase'lerde)

---

## 8. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                 | Belirti                                        | Çözüm                       |
| --------------------- | ---------------------------------------------- | --------------------------- |
| Import hataları       | `ImportError: cannot import name 'MatchState'` | Alias ekle                  |
| to_dict() uyumsuzluğu | MongoDB/API hataları                           | Eski format'ı da destekle   |
| Test failure          | Mevcut testler FAIL                            | Testleri güncelle           |
| Type hint hataları    | mypy/pylint uyarıları                          | TYPE_CHECKING import kullan |

---

## 9. SONRAKİ PHASE'E GEÇİŞ

Phase 1 tamamlandığında:

1. Git commit: `feat(state): rename ExecutionState→RunState, MatchState→JobState`
2. Git tag: `v0.x.x-phase1`
3. `02_PHASE2_MONGODB.md` dosyasını oku
4. MongoDB collection değişikliklerine başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/state/` çalıştır
- Backward compat alias'ların çalıştığını doğrula
- Mevcut `__main__.py` hala çalışıyor mu test et
