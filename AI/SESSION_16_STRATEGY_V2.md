# SESSION 16 - PLUGIN COMMUNICATION REFACTOR STRATEGY V2

## OZET

Bu dokuman mevcut projenin analizi ve hedef sistemin detayli tasarimini icerir. Tum kararlar mevcut kod yapisi (MongoDB, FastAPI, GlobalState, PluginServices) incelenerek alinmistir.

---

## 1. MEVCUT DURUM ANALIZI

### 1.1. MongoDB Koleksiyonlari

Kaynak: `infrastructure/database/pymongo_persistence.py`

```
Koleksiyonlar:
- runs: Run state
- jobs: Job state  
- plugins: Plugin data (job_id + plugin_name unique)
- branches: Git-like versioning

Index Yapisi:
- plugins: (run_id, job_id, plugin_name) unique
```

### 1.2. State Modelleri

Kaynak: `state/models.py`

```
RunState:
  - id, status, config
  
JobState:
  - id, index, run_id
  - input (value, data)
  - output (values, data)
  - status (state, executed, failed, skipped)
  - plugins: Dict[str, Dict]  # Runtime access

PluginState:
  - status (state, success, started_at, finished_at, duration_ms, error)
  - data: Dict

PluginData (MongoDB):
  - id: plugin_{job_id}_{plugin_name}
  - job_id, run_id, job_index, plugin_name, stage
  - status, data
```

### 1.3. Plugin Services

Kaynak: `core/services/plugin_services.py`

```python
# Mevcut metodlar
createJob(input_value, input_data) -> job_id
updateJob(key, value)      # ID yok, context'ten alinir
updatePlugin(data)         # ID/name yok, context'ten alinir
```

Sorun: ID belirtilmiyor, per_run plugin per_job'a veri ekleyemiyor.

### 1.4. GlobalStateManager

Kaynak: `state/manager.py`

```python
# Internal storage
_run: RunState
_jobs: Dict[index, JobState]
_plugins: Dict[job_id, Dict[plugin_name, data]]
_plugins_storage: Dict[job_id, Dict[plugin_name, PluginState]]
```

Sorun: Ayni veri iki yerde (_plugins ve _plugins_storage), sync problemi.

---

## 2. HEDEF YAPI

### 2.1. Plugins Storage - Key-Based

Karar: Dict with target_id as key

```python
plugins = {
    "run_abc123": {
        "scanner": {"count": 10, "targets": [...]}
    },
    "job_run_abc123_0": {
        "renamer": {"parsed": {...}},
        "tmdb": {"movie": {...}},
        "tasker": {"tasks": {...}}
    },
    "job_run_abc123_1": {
        "renamer": {"parsed": {...}},
        "tmdb": {"show": {...}}
    }
}
```

Avantajlar:
- Direkt erisim: `plugins["job_abc_0"]["tmdb"]`
- Prefix ile tip belirleme: `run_` = run, `job_` = job
- MongoDB'de tek dokuman per target
- Config alias uyumlu

### 2.2. Plugin Status - Job/Run Icinde

Status artik plugin data icinde degil, job/run status icinde:

```python
# Per-job plugin status
job.status.plugins = {
    "renamer": {
        "state": "completed",
        "success": True,
        "started_at": "...",
        "finished_at": "...",
        "duration_ms": 800,
        "error": None
    },
    "tmdb": {...},
    "tasker": {...}
}

# Per-run plugin status
run.status.plugins = {
    "scanner": {
        "state": "completed",
        "success": True,
        "started_at": "...",
        "finished_at": "...",
        "duration_ms": 1200,
        "error": None
    }
}
```

Mantik:
- Status = Sistem tracking (sistem yonetir)
- Data = Plugin ozgur icerik (plugin yonetir)

### 2.3. Plugin Data - Flat Structure

Onceki: `plugins.tmdb.data.movie`
Yeni: `plugins["job_abc_0"]["tmdb"]["movie"]`

Data wrapper kaldirildi, plugin icerigi direkt.

---

## 3. PLUGIN SERVICES API

### 3.1. Isimlendirme

Snake_case:
```python
create_job()      # createJob degil
update_job()      # updateJob degil
update_plugin()   # updatePlugin degil
get_plugin_data()
```

### 3.2. ID Zorunlulugu

Her iletisimde target_id ve plugin_name belirtilmeli:

```python
# YANLIS (mevcut)
services.updatePlugin({"movie": data})  # ID yok

# DOGRU (hedef)
services.update_plugin("job_abc123_0", "tmdb", {"movie": data})
```

### 3.3. Yeni API

```python
class PluginServices:
    
    def create_job(self, input_value: str, input_data: dict = None) -> str:
        """
        Yeni job olustur.
        Returns: job_id
        """
    
    def update_job(self, job_id: str, path: str, value: Any) -> None:
        """
        Job state guncelle.
        
        Args:
            job_id: Hedef job
            path: Dot notation ("output.values", "status.state")
            value: Deger
        """
    
    def update_plugin(
        self,
        target_id: str,      # job_id veya run_id
        plugin_name: str,
        data: dict
    ) -> None:
        """
        Plugin data guncelle.
        
        Args:
            target_id: "job_abc123_0" veya "run_abc123"
            plugin_name: "tmdb", "renamer", "scanner"
            data: Plugin datasi
        
        Ornekler:
            update_plugin("job_abc123_0", "tmdb", {"movie": {...}})
            update_plugin("run_abc123", "scanner", {"count": 10})
        """
    
    def get_plugin_data(self, target_id: str, plugin_name: str) -> dict:
        """Plugin data al."""
    
    def get_job(self, job_id: str) -> JobState:
        """Job state al."""
    
    def get_all_jobs(self) -> List[JobState]:
        """Tum job'lari al."""
```

### 3.4. Sistem Metodlari

Plugin cagirmaz, sistem (Orchestrator) cagirir:

```python
def mark_plugin_started(self, target_id: str, plugin_name: str) -> None:
    """
    Plugin basladiginda sistem cagirir.
    
    Islemler:
        - job/run.status.plugins.{name}.started_at = now()
        - job/run.status.plugins.{name}.state = "running"
    """

def mark_plugin_completed(
    self,
    target_id: str,
    plugin_name: str,
    success: bool,
    error: str = None
) -> None:
    """
    Plugin bittiginde sistem cagirir.
    
    Islemler:
        - finished_at = now()
        - duration_ms hesapla
        - state = "completed" / "failed"
        - success = True/False
        - error = hata mesaji
    """
```

---

## 4. MONGODB SEMA DEGISIKLIKLERI

### 4.1. Runs Collection

```javascript
// Mevcut
{
  "id": "run_abc123",
  "status": {
    "state": "completed",
    "total_jobs": 10
  }
}

// Hedef
{
  "id": "run_abc123",
  "status": {
    "state": "completed",
    "total_jobs": 10,
    "plugins": {                    // YENI
      "scanner": {
        "state": "completed",
        "duration_ms": 1200
      }
    }
  }
}
```

### 4.2. Jobs Collection

```javascript
// Mevcut
{
  "id": "job_run_abc123_0",
  "status": {
    "state": "completed",
    "executed": ["renamer", "tmdb"]
  },
  "plugins": {
    "tmdb": {"status": {...}, "data": {...}}  // Status + Data birlikte
  }
}

// Hedef
{
  "id": "job_run_abc123_0",
  "status": {
    "state": "completed",
    "executed": ["renamer", "tmdb"],
    "plugins": {                              // YENI: Status buraya
      "renamer": {"state": "completed", "duration_ms": 800},
      "tmdb": {"state": "completed", "duration_ms": 1200}
    }
  }
  // plugins field kaldirildi, ayri koleksiyonda
}
```

### 4.3. Plugins Collection

```javascript
// Mevcut (her plugin ayri dokuman)
{
  "_id": "plugin_job_run_abc123_0_tmdb",
  "job_id": "job_run_abc123_0",
  "plugin_name": "tmdb",
  "status": {...},
  "data": {"movie": {...}}
}

// Hedef (target bazli tek dokuman)
{
  "_id": "job_run_abc123_0",
  "renamer": {"parsed": {...}},
  "tmdb": {"movie": {...}},
  "tasker": {"tasks": {...}}
}

// Run plugins icin
{
  "_id": "run_abc123",
  "scanner": {"count": 10, "targets": [...]}
}
```

### 4.4. Index Degisiklikleri

```javascript
// Mevcut
plugins.createIndex({run_id: 1, job_id: 1, plugin_name: 1}, {unique: true})

// Hedef
plugins.createIndex({_id: 1})  // Default, target_id unique
```

---

## 5. GLOBALSTATEMANAGER DEGISIKLIKLERI

### 5.1. Internal Storage

```python
# Mevcut
_run: RunState
_jobs: Dict[index, JobState]
_plugins: Dict[job_id, Dict[plugin_name, data]]
_plugins_storage: Dict[job_id, Dict[plugin_name, PluginState]]

# Hedef
_run: RunState
_jobs: Dict[index, JobState]
_plugins: Dict[target_id, Dict[plugin_name, data]]  # Unified
# _plugins_storage kaldirildi
```

### 5.2. Metod Degisiklikleri

```python
# Mevcut
def update_plugin(self, job_id: str, plugin_name: str, data: dict):
    # job_id ve plugin_name PluginServices tarafindan context'ten alinir

# Hedef
def update_plugin(self, target_id: str, plugin_name: str, data: dict):
    """
    target_id: job_run_abc123_0 veya run_abc123
    Prefix'e gore run mi job mi anlasilir
    """
    is_run = target_id.startswith("run_")
    
    if target_id not in self._plugins:
        self._plugins[target_id] = {}
    
    self._plugins[target_id][plugin_name] = data
    
    # MongoDB'ye kaydet
    self._persistence.save_plugin_doc(target_id, self._plugins[target_id])
```

---

## 6. FASTAPI DEGISIKLIKLERI

### 6.1. Endpoint Degisiklikleri

```python
# Mevcut
GET /api/v1/plugins/{job_id}
GET /api/v1/plugins/{job_id}/{plugin_name}

# Hedef
GET /api/v1/plugins/{target_id}
GET /api/v1/plugins/{target_id}/{plugin_name}
```

### 6.2. Response Sema

```python
# Mevcut
{
  "job_id": "job_abc_0",
  "plugins": [
    {"plugin_name": "tmdb", "status": {...}, "data": {...}}
  ]
}

# Hedef
{
  "target_id": "job_abc_0",
  "plugins": {
    "tmdb": {"movie": {...}},
    "renamer": {"parsed": {...}}
  }
}
```

---

## 7. MIGRASYON PLANI

### Adim 1: State Modelleri Guncelle

```
state/models.py:
- JobStatus: plugins dict ekle
- RunStatus: plugins dict ekle
- PluginState: status field kaldir (job/run'a tasindi)
- PluginData: status field kaldir
```

### Adim 2: GlobalStateManager Guncelle

```
state/manager.py:
- _plugins_storage kaldir
- update_plugin: target_id parametresi ekle
- mark_plugin_started/completed metodlari ekle
- Dual storage yerine tek _plugins
```

### Adim 3: PluginServices Guncelle

```
core/services/plugin_services.py:
- updateJob -> update_job
- updatePlugin -> update_plugin (target_id, plugin_name parametreleri)
- createJob -> create_job
- get_plugin_data ekle
```

### Adim 4: MongoDB Persistence Guncelle

```
infrastructure/database/pymongo_persistence.py:
- save_plugin: tek dokuman per target_id
- get_plugins: target_id ile query
- Index degisiklikleri
```

### Adim 5: Tum Pluginleri Guncelle

```
plugins/*/client.py veya plugin.py:
- services.updatePlugin(data) 
  -> services.update_plugin(job.id, "plugin_name", data)
- services.updateJob(key, value)
  -> services.update_job(job.id, key, value)
```

### Adim 6: FastAPI Guncelle

```
api/v1/plugins/router.py:
- Endpoint parametreleri: job_id -> target_id
- Response sema guncelle
```

### Adim 7: Tasker Plugin Ozel

```
plugins/tasker/plugin.py:
- _track_run_output: plugins[target_id] formatinda kaydet
- JSON output: yeni yapiya uyumlu
```

---

## 8. ORNEK SENARYOLAR

### Senaryo 1: Per-Run Plugin (Scanner)

```python
class ScannerPlugin:
    def execute_run(self, services):
        files = self.scan_targets()
        
        for file in files:
            job_id = services.create_job(
                input_value=str(file),
                input_data={"source": "scanner"}
            )
        
        # Run-level veri ekle
        services.update_plugin(
            target_id=services.run_id,  # run_abc123
            plugin_name="scanner",
            data={"count": len(files), "targets": self.targets}
        )
```

### Senaryo 2: Per-Job Plugin (TMDb)

```python
class TMDbPlugin:
    def execute(self, job, services):
        movie_data = self.fetch_movie(...)
        
        # Job-level veri ekle
        services.update_plugin(
            target_id=job.id,  # job_run_abc123_0
            plugin_name="tmdb",
            data={"movie": movie_data}
        )
```

### Senaryo 3: Per-Run Plugin Job'a Veri Ekliyor

```python
class ValidatorPlugin:
    def execute_run(self, services):
        for job in services.get_all_jobs():
            validation_result = self.validate(job)
            
            # Per-run plugin per-job'a veri ekliyor
            services.update_plugin(
                target_id=job.id,
                plugin_name="validator",
                data={"valid": validation_result}
            )
```

---

## 9. KARAR OZETI

| Konu | Mevcut | Hedef |
|------|--------|-------|
| Plugins yapisi | Nested (job.plugins.tmdb.data) | Key-based (plugins[target_id][name]) |
| Plugin status | plugin.status icinde | job/run.status.plugins icinde |
| API isimlendirme | camelCase | snake_case |
| ID parametresi | Context'ten alinir | Zorunlu parametre |
| Per-run/job ayrimi | Yok, karisik | Prefix ile (run_ vs job_) |
| MongoDB | Her plugin ayri dokuman | Her target tek dokuman |

---

## 10. SONUC

Bu strateji mevcut projenin tum bilesenleri (MongoDB, FastAPI, GlobalState, PluginServices) incelenerek hazirlanmistir. Key-based yaklasim secilmistir cunku:

1. MongoDB'de verimli query (tek dokuman per target)
2. Direkt erisim (nesting yok)
3. Config alias uyumlu
4. Run/job ayrimi net (prefix ile)
5. Plugin agnostic API (her plugin her metodu kullanabilir)
