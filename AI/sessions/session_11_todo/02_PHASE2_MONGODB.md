# PHASE 2: MONGODB & PERSISTENCE

```yaml
phase: 2
öncelik: 🔴 KRİTİK
tahmini_süre: 4-6 saat
bağımlılık: P1 (State Models)
strateji_belgesi: 06_mongodb_and_persistence.md
test_türü: integration
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P1 tamamlandı (RunState, JobState mevcut)
- [ ] Unit testler PASS
- [ ] to_dict() metodları çalışıyor

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Dosyalar

```
src/archiverr/infrastructure/
├── database.py              # DatabaseConnection
└── persistence/
    ├── __init__.py
    ├── interface.py         # PersistenceInterface
    ├── mock.py              # MockPersistence
    └── pymongo_impl.py      # PyMongoPersistence
```

### 1.2 Mevcut Collection Yapısı

```javascript
// executions collection
{
    _id: "exec_abc123",
    id: "abc123",
    started_at: ISODate,
    finished_at: ISODate,
    duration_ms: 60000,
    success: true,
    status: "completed",
    summary: {
        total_matches: 10,
        completed_matches: 10,
        failed_matches: 0
    },
    config_snapshot: {...}
}

// matches collection
{
    _id: "match_0_abc123",
    execution_id: "exec_abc123",
    index: 0,
    input_path: "/path/to/file.mkv",
    success: true,
    status: "completed",
    executed_plugins: ["scanner", "renamer"],
    failed_plugins: [],
    not_supported_plugins: ["tvdb"],
    started_at: ISODate,
    finished_at: ISODate,
    duration_ms: 4000,
    tasks: [...]
}

// plugin_results collection (job içinde embedded)
// Şu an ayrı collection YOK - plugins dict job içinde
```

---

## 2. HEDEF YAPI

### 2.1 Yeni Collection Yapıları

#### runs Collection (eski: executions)

```javascript
{
    _id: ObjectId,
    id: "run_abc123",                    // Yeni format

    status: {                            // Nested status object
        state: "completed",              // pending|running|completed|failed
        success: true,
        total_jobs: 10,                  // Eski: total_matches
        completed: 10,                   // Eski: completed_matches
        failed: 0,                       // Eski: failed_matches
        started_at: ISODate,
        finished_at: ISODate,
        duration_ms: 60000
    },

    config: {                            // Eski: config_snapshot
        options: {debug: true, dry_run: false},
        aliases: {}
    },

    created_at: ISODate,
    updated_at: ISODate
}

// Indexes
db.runs.createIndex({ "id": 1 }, { unique: true })
db.runs.createIndex({ "created_at": -1 })
db.runs.createIndex({ "status.state": 1 })
```

#### jobs Collection (eski: matches)

```javascript
{
    _id: ObjectId,
    run_id: "run_abc123",               // Eski: execution_id
    index: 0,
    id: "job_run_abc123_0",             // YENİ: Unique job ID

    input: {                            // Eski: input_path → nested
        value: "/path/to/file.mkv",     // Eski: path → value
        data: {
            filename: "file.mkv",
            extension: "mkv",
            size_bytes: 5368709120,
            modified_at: ISODate,
            source: "filesystem"
        }
    },

    output: {                           // YENİ
        values: ["/srv/archive/Movie.mkv"],
        data: {
            tasks: {
                save_movie: {type: "save", success: true}
            }
        }
    },

    status: {                           // Nested status object
        state: "completed",
        success: true,
        executed: ["scanner", "renamer"],  // Eski: executed_plugins
        failed: [],                        // Eski: failed_plugins
        skipped: ["tvdb"],                 // Eski: not_supported_plugins
        started_at: ISODate,
        finished_at: ISODate,
        duration_ms: 4000
    },

    created_at: ISODate,
    updated_at: ISODate
}

// Indexes
db.jobs.createIndex({ "run_id": 1, "index": 1 }, { unique: true })
db.jobs.createIndex({ "id": 1 }, { unique: true })
db.jobs.createIndex({ "run_id": 1 })
db.jobs.createIndex({ "input.value": 1 })
```

#### plugins Collection (YENİ - ayrı)

```javascript
{
    _id: ObjectId,
    run_id: "run_abc123",
    job_id: "job_run_abc123_0",
    job_index: 0,
    plugin_name: "tmdb",
    stage: "data",                      // input|parse|data|output

    status: {
        success: true,
        started_at: ISODate,
        finished_at: ISODate,
        duration_ms: 800,
        error: null
    },

    data: {                             // Plugin-specific data
        movie: {
            id: 12345,
            title: "Movie",
            release_date: "2024-01-15"
        }
    },

    created_at: ISODate
}

// Indexes
db.plugins.createIndex({ "run_id": 1, "job_index": 1, "plugin_name": 1 }, { unique: true })
db.plugins.createIndex({ "job_id": 1, "plugin_name": 1 }, { unique: true })
db.plugins.createIndex({ "run_id": 1 })
db.plugins.createIndex({ "job_id": 1 })
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: PersistenceInterface Güncelle

**Dosya:** `src/archiverr/infrastructure/persistence/interface.py`

**Değişiklikler:**

```python
class PersistenceInterface(ABC):
    # Eski metodlar (DEPRECATED ama geçici olarak korunacak)
    @abstractmethod
    def save_execution(self, execution: dict) -> None: ...

    @abstractmethod
    def save_match(self, match: dict) -> None: ...

    # Yeni metodlar
    @abstractmethod
    def save_run(self, run: dict) -> None: ...

    @abstractmethod
    def save_job(self, job: dict) -> None: ...

    @abstractmethod
    def save_plugin(self, plugin: dict) -> None: ...

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[dict]: ...

    @abstractmethod
    def get_jobs(self, run_id: str) -> List[dict]: ...

    @abstractmethod
    def get_plugins(self, job_id: str) -> List[dict]: ...
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Mevcut interface metodlarını incele, yeni metodları eklerken uyumluluğu koru
- Geçiş döneminde eski metodları wrapper olarak tut

---

### ADIM 2: MockPersistence Güncelle

**Dosya:** `src/archiverr/infrastructure/persistence/mock.py`

**İş:**

1. Yeni collection dict'leri ekle: `_runs`, `_jobs`, `_plugins`
2. Yeni metodları implemente et
3. Eski metodları wrapper olarak tut (backward compat)

```python
class MockPersistence(PersistenceInterface):
    def __init__(self):
        self._runs: Dict[str, dict] = {}
        self._jobs: Dict[str, dict] = {}
        self._plugins: Dict[str, dict] = {}
        # Backward compat
        self._executions = self._runs  # Alias
        self._matches = self._jobs     # Alias

    def save_run(self, run: dict) -> None:
        run_id = run.get("id", "")
        self._runs[run_id] = run

    def save_job(self, job: dict) -> None:
        job_id = job.get("id", "")
        self._jobs[job_id] = job

    def save_plugin(self, plugin: dict) -> None:
        key = f"{plugin['job_id']}_{plugin['plugin_name']}"
        self._plugins[key] = plugin

    # Backward compat wrappers
    def save_execution(self, execution: dict) -> None:
        # Map old format to new
        run = self._convert_execution_to_run(execution)
        self.save_run(run)
```

**Test:**

```python
def test_mock_save_run():
    mock = MockPersistence()
    mock.save_run({"id": "run_abc123", "status": {"state": "pending"}})
    assert "run_abc123" in mock._runs

def test_mock_backward_compat():
    mock = MockPersistence()
    mock.save_execution({"id": "abc123", "status": "pending"})
    assert "run_abc123" in mock._runs or "abc123" in mock._runs
```

---

### ADIM 3: PyMongoPersistence Güncelle

**Dosya:** `src/archiverr/infrastructure/persistence/pymongo_impl.py`

**İş:**

1. Collection referanslarını güncelle
2. Document format dönüşümü
3. Index oluşturma

```python
class PyMongoPersistence(PersistenceInterface):
    def __init__(self, db: Database):
        self._db = db
        # Yeni collection referansları
        self._runs = db["runs"]
        self._jobs = db["jobs"]
        self._plugins = db["plugins"]
        # Backward compat (DEPRECATED)
        self._executions = db["executions"]  # Eski
        self._matches = db["matches"]        # Eski

    def save_run(self, run: dict) -> None:
        run_id = run.get("id", "")
        self._runs.update_one(
            {"id": run_id},
            {"$set": run, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )

    def save_job(self, job: dict) -> None:
        job_id = job.get("id", "")
        self._jobs.update_one(
            {"id": job_id},
            {"$set": job, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )

    def save_plugin(self, plugin: dict) -> None:
        job_id = plugin.get("job_id", "")
        plugin_name = plugin.get("plugin_name", "")
        self._plugins.update_one(
            {"job_id": job_id, "plugin_name": plugin_name},
            {"$set": plugin, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )

    def ensure_indexes(self) -> None:
        """Collection index'lerini oluştur"""
        # runs indexes
        self._runs.create_index([("id", 1)], unique=True)
        self._runs.create_index([("created_at", -1)])
        self._runs.create_index([("status.state", 1)])

        # jobs indexes
        self._jobs.create_index([("run_id", 1), ("index", 1)], unique=True)
        self._jobs.create_index([("id", 1)], unique=True)
        self._jobs.create_index([("run_id", 1)])

        # plugins indexes
        self._plugins.create_index(
            [("job_id", 1), ("plugin_name", 1)], unique=True
        )
        self._plugins.create_index([("run_id", 1)])
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Mevcut pymongo kodunu incele, yeni collection'ları aynı pattern'de ekle
- Index'leri startup'ta oluştur (ensure_indexes metodu)

---

### ADIM 4: StateManager Persistence Entegrasyonu

**Dosya:** `src/archiverr/state/manager.py`

**İş:**

1. Persistence metodlarını yeni format'a çevir
2. Plugin data'yı ayrı kaydet

```python
class StateManager:
    def _persist_run(self) -> None:
        """Run state'ini persist et"""
        if self._persistence and self._run:
            self._persistence.save_run(self._run.to_dict())

    def _persist_job(self, job: JobState) -> None:
        """Job state'ini persist et"""
        if self._persistence:
            self._persistence.save_job(job.to_dict())

    def _persist_plugin(self, job_id: str, plugin_name: str, data: dict) -> None:
        """Plugin result'ı ayrı collection'a persist et"""
        if self._persistence:
            plugin_doc = {
                "job_id": job_id,
                "run_id": self._run.id,
                "plugin_name": plugin_name,
                "data": data,
                "created_at": datetime.utcnow()
            }
            self._persistence.save_plugin(plugin_doc)
```

---

### ADIM 5: Migration Script (Opsiyonel)

**Dosya:** `scripts/migrate_collections.py`

```python
"""
Mevcut MongoDB verilerini yeni formata migrate eder.

KULLANIM:
    python scripts/migrate_collections.py --dry-run
    python scripts/migrate_collections.py --execute
"""

def migrate_executions_to_runs(db, dry_run=True):
    """executions → runs migration"""
    for doc in db.executions.find():
        new_doc = {
            "id": f"run_{doc['id']}",
            "status": {
                "state": doc.get("status", "pending"),
                "success": doc.get("success", True),
                "total_jobs": doc.get("summary", {}).get("total_matches", 0),
                "completed": doc.get("summary", {}).get("completed_matches", 0),
                "failed": doc.get("summary", {}).get("failed_matches", 0),
                "started_at": doc.get("started_at"),
                "finished_at": doc.get("finished_at"),
                "duration_ms": doc.get("duration_ms", 0)
            },
            "config": doc.get("config_snapshot", {}),
            "created_at": doc.get("started_at"),
            "updated_at": doc.get("finished_at") or doc.get("started_at")
        }

        if dry_run:
            print(f"Would migrate: {doc['_id']} → {new_doc['id']}")
        else:
            db.runs.insert_one(new_doc)

def migrate_matches_to_jobs(db, dry_run=True):
    """matches → jobs migration"""
    for doc in db.matches.find():
        run_id = doc.get("execution_id", "").replace("exec_", "run_")
        new_doc = {
            "run_id": run_id,
            "index": doc.get("index", 0),
            "id": f"job_{run_id}_{doc.get('index', 0)}",
            "input": {
                "value": doc.get("input_path", ""),
                "data": {}
            },
            "output": {
                "values": [],
                "data": {"tasks": doc.get("tasks", [])}
            },
            "status": {
                "state": doc.get("status", "pending"),
                "success": doc.get("success", True),
                "executed": doc.get("executed_plugins", []),
                "failed": doc.get("failed_plugins", []),
                "skipped": doc.get("not_supported_plugins", []),
                "started_at": doc.get("started_at"),
                "finished_at": doc.get("finished_at"),
                "duration_ms": doc.get("duration_ms", 0)
            },
            "created_at": doc.get("started_at"),
            "updated_at": doc.get("finished_at") or doc.get("started_at")
        }

        if dry_run:
            print(f"Would migrate: {doc['_id']} → {new_doc['id']}")
        else:
            db.jobs.insert_one(new_doc)
```

**NOT:** Migration script opsiyonel. Test verileri varsa kullan, yoksa temiz başla.

---

## 4. TEST SENARYOLARI

### 4.1 Integration Tests

```python
# tests/integration/persistence/test_mongodb.py

import pytest
from archiverr.infrastructure.persistence import PyMongoPersistence

@pytest.fixture
def mongo_persistence(mongodb_client):
    """Test MongoDB instance"""
    db = mongodb_client["archiverr_test"]
    return PyMongoPersistence(db)

class TestRunPersistence:
    def test_save_and_get_run(self, mongo_persistence):
        run = {
            "id": "run_test123",
            "status": {"state": "pending", "total_jobs": 0}
        }
        mongo_persistence.save_run(run)

        result = mongo_persistence.get_run("run_test123")
        assert result is not None
        assert result["id"] == "run_test123"

    def test_run_update(self, mongo_persistence):
        run = {"id": "run_update", "status": {"state": "pending"}}
        mongo_persistence.save_run(run)

        run["status"]["state"] = "running"
        mongo_persistence.save_run(run)

        result = mongo_persistence.get_run("run_update")
        assert result["status"]["state"] == "running"

class TestJobPersistence:
    def test_save_and_get_job(self, mongo_persistence):
        job = {
            "id": "job_run_test_0",
            "run_id": "run_test",
            "index": 0,
            "input": {"value": "/test.mkv"}
        }
        mongo_persistence.save_job(job)

        jobs = mongo_persistence.get_jobs("run_test")
        assert len(jobs) == 1
        assert jobs[0]["id"] == "job_run_test_0"

class TestPluginPersistence:
    def test_save_plugin(self, mongo_persistence):
        plugin = {
            "job_id": "job_run_test_0",
            "run_id": "run_test",
            "plugin_name": "tmdb",
            "data": {"movie": {"title": "Test"}}
        }
        mongo_persistence.save_plugin(plugin)

        plugins = mongo_persistence.get_plugins("job_run_test_0")
        assert len(plugins) == 1
        assert plugins[0]["plugin_name"] == "tmdb"
```

### 4.2 Mock Persistence Tests

```python
# tests/unit/persistence/test_mock.py

def test_mock_isolation():
    """Her test için temiz state"""
    mock = MockPersistence()
    assert len(mock._runs) == 0
    assert len(mock._jobs) == 0
    assert len(mock._plugins) == 0

def test_mock_crud():
    mock = MockPersistence()

    # Create
    mock.save_run({"id": "run_1"})
    mock.save_job({"id": "job_1", "run_id": "run_1"})

    # Read
    assert mock.get_run("run_1") is not None
    assert len(mock.get_jobs("run_1")) == 1
```

---

## 5. PHASE 2 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] PersistenceInterface yeni metodlarla güncellendi
- [ ] MockPersistence yeni collection'ları destekliyor
- [ ] PyMongoPersistence yeni collection'ları destekliyor
- [ ] Collection index'leri tanımlandı
- [ ] Backward compatibility korundu (geçici)
- [ ] Integration testler yazıldı ve PASS
- [ ] StateManager persistence metodları güncellendi

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ Migration script çalıştırma (opsiyonel, gerekirse)
- ❌ API endpoint'leri (P8'de)
- ❌ Memory management optimizasyonları (P9'da)

---

## 6. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                    | Belirti             | Çözüm                       |
| ------------------------ | ------------------- | --------------------------- |
| MongoDB bağlantı hatası  | `ConnectionFailure` | Mock persistence'a fallback |
| Duplicate key hatası     | `DuplicateKeyError` | upsert=True kullan          |
| Eski format bekleyen kod | API hataları        | Converter fonksiyon yaz     |
| Index oluşturma yavaş    | Startup gecikmesi   | Background index creation   |

---

## 7. SONRAKİ PHASE'E GEÇİŞ

Phase 2 tamamlandığında:

1. Git commit: `feat(persistence): add runs/jobs/plugins collections`
2. Git tag: `v0.x.x-phase2`
3. `03_PHASE3_PLUGIN_SERVICES.md` dosyasını oku
4. PluginServices interface tasarımına başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- Mock ve MongoDB aynı davranışı sergiliyor mu test et
- `pytest tests/integration/persistence/` çalıştır
- Mevcut kod hala çalışıyor mu kontrol et
