# Plugin Communication System - Refactor Brainstorm

## 🎯 Hedef

Plugin-agnostic, esnek, ID-based iletişim sistemi. Her plugin her metodu kullanabilir, veri ekleme konusunda tam özgürlük.

---

## 📊 1. YENİ PLUGIN DATA YAPISI

### 1.1. Status ve Data Ayrımı

**ÖNCEDEN:**

```python
plugins.tmdb.status = {state, success, duration_ms}
plugins.tmdb.data = {movie: {...}, show: {...}}
```

**YENİ:**

```python
# Status → Job/Run içine taşındı
job.status.plugins.tmdb = {state, success, started_at, finished_at, duration_ms}
run.status.plugins.scanner = {state, success, started_at, finished_at, duration_ms}

# Data → Bir üst seviyeye çıktı (dağınık)
plugins.tmdb = {movie: {...}, show: {...}}  # Artık .data wrapper yok
```

**Mantık:**

- **Status** = Sistem tracking → Job/Run içinde tutulur (sistem yönetir)
- **Data** = Plugin özgür data → Plugins içinde tutulur (plugin yönetir)

---

### 1.2. Per Run vs Per Job Plugin Data

**Seçenek A - Alt Grup (ÖNERİLEN):**

```python
# MongoDB/State Structure
{
  "plugins": {
    "run": {
      "scanner": {
        "count": 10,
        "targets": [...]
      }
    },
    "job": {
      "tmdb": {
        "movie": {...},
        "show": {...}
      },
      "renamer": {
        "parsed": {...}
      }
    }
  }
}

# Config erişimi
m.title  →  plugins.job.tmdb.movie.title
s.count  →  plugins.run.scanner.count
```

**Seçenek B - Job ID Prefix (REDDEDILDI - Erişim zor):**

```python
plugins: {
  "job_abc123_0_tmdb": {...},  # ❌ Config'den erişim zor
  "job_abc123_0_renamer": {...},
  "run_scanner": {...}
}
```

**KARAR: Seçenek A (Alt Grup)**

**Sebep:**

- ✅ Config alias erişimi kolay (`m.title`, `r.name`)
- ✅ API/JSON query kolay (`plugins.job.tmdb`, `plugins.run.scanner`)
- ✅ Scope açık ve net (run vs job ayrımı)

---

## 🔌 2. PLUGIN-AGNOSTIC İLETİŞİM SİSTEMİ

### 2.1. Temel Prensipler

#### ❌ Şu Anki Sorunlar

```python
# updatePlugin → Sadece current plugin'e yazıyor, ID yok
services.updatePlugin(data)  # Hangi job? Hangi plugin?

# updateJob → Job ID yok
services.updateJob("output.values", [])  # Hangi job?

# Per run plugin per job data ekleyemiyor
scanner_plugin.execute_run(services)  # Job'a nasıl veri eklesin?
```

#### ✅ Yeni Tasarım: Tam ID Kontrolü

**Her iletişim metodu şunları belirtir:**

1. **Target ID** (job_id veya run_id)
2. **Target Type** (job, run, plugin)
3. **Data Path** (dot notation)

---

### 2.2. Yeni İletişim Metodları

```python
class PluginServices:
    """Plugin-agnostic communication layer"""

    # ============================================================================
    # JOB İLETİŞİMİ
    # ============================================================================

    def create_job(self, input_value: str, input_data: Dict) -> str:
        """
        Yeni job oluştur (her plugin kullanabilir).

        Returns:
            job_id

        İç İşlemler:
            - ID generation
            - Event bus notification
            - Timestamp ekleme
            - jobs ve job state'lerine ekleme
        """

    def update_job(self, job_id: str, path: str, value: Any) -> None:
        """
        Job içine veri ekle (her plugin kullanabilir).

        Args:
            job_id: Hedef job ID
            path: Dot notation (örn: "output.values", "input.data.filename")
            value: Eklenecek değer

        İç İşlemler:
            - job state güncelle
            - jobs state güncelle (aynı job varsa)
            - Event emit

        Örnek:
            update_job("job_123", "output.values", ["/path1", "/path2"])
            update_job("job_123", "output.data.tasks", {...})
        """

    def get_job(self, job_id: str) -> JobState:
        """Job state'i al"""

    def get_all_jobs(self) -> List[JobState]:
        """Tüm job'ları al"""

    # ============================================================================
    # PLUGIN İLETİŞİMİ
    # ============================================================================

    def update_plugin(
        self,
        job_id: str,           # Hangi job'a ait (run plugin için None)
        plugin_name: str,      # Hangi plugin
        data: Dict,            # Plugin data
        scope: str = "job"     # "job" veya "run"
    ) -> None:
        """
        Plugin data ekle (her plugin kullanabilir).

        Args:
            job_id: Hedef job (per_run plugin için None)
            plugin_name: Hedef plugin adı
            data: Eklenecek data
            scope: "job" veya "run"

        İç İşlemler:
            - plugins.job.{plugin_name} veya plugins.run.{plugin_name} güncelle
            - Event emit

        Örnekler:
            # Per job plugin kendi data'sını ekliyor
            update_plugin("job_123", "tmdb", {...}, scope="job")

            # Per run plugin kendi data'sını ekliyor
            update_plugin(None, "scanner", {...}, scope="run")

            # Per run plugin bir job'a veri ekliyor (ESNEKLİK!)
            update_plugin("job_123", "scanner", {...}, scope="job")
        """

    def get_plugin_data(
        self,
        plugin_name: str,
        job_id: str = None,
        scope: str = "job"
    ) -> Dict:
        """
        Plugin data'sını al.

        Args:
            plugin_name: Plugin adı
            job_id: Job ID (run scope için None)
            scope: "job" veya "run"
        """

    # ============================================================================
    # PLUGIN STATUS TRACKING (SİSTEM YÖNETİR - PLUGIN DOKUNMAZ)
    # ============================================================================

    def mark_plugin_started(
        self,
        job_id: str,        # None for per_run
        plugin_name: str,
        scope: str = "job"  # "job" veya "run"
    ) -> None:
        """
        Plugin başladı olarak işaretle.

        İç İşlemler:
            - job.status.plugins.{plugin_name}.started_at = now
            - job.status.plugins.{plugin_name}.state = "running"
            (veya run.status.plugins.{plugin_name})
        """

    def mark_plugin_completed(
        self,
        job_id: str,
        plugin_name: str,
        scope: str = "job",
        success: bool = True,
        error: str = None
    ) -> None:
        """
        Plugin tamamlandı olarak işaretle.

        İç İşlemler:
            - finished_at, duration_ms hesapla
            - state = "completed"/"failed"
            - success = True/False
        """

    # ============================================================================
    # RUN İLETİŞİMİ
    # ============================================================================

    def update_run(self, path: str, value: Any) -> None:
        """
        Run state güncelle.

        Args:
            path: Dot notation
            value: Değer

        Örnek:
            update_run("status.total_jobs", 10)
        """

    def get_run(self) -> RunState:
        """Current run state"""
```

---

### 2.3. Neden Servis Layer?

#### ❌ Direkt State Access Problemi

```python
# Plugin direkt state'e erişirse:
def execute(self, job, services):
    # ❌ Manuel her yere ekleme
    services.state.job.plugins['tmdb'] = data
    services.state.jobs[job_index].plugins['tmdb'] = data

    # ❌ Event emit unutulabilir
    services.event_bus.emit("plugin.updated", ...)

    # ❌ ID generation manuel
    job_id = f"job_{uuid4()}"

    # ❌ Timestamp manuel
    started_at = datetime.now()
```

#### ✅ Servis Layer Avantajları

```python
# Servis kullanırsa:
def execute(self, job, services):
    # ✅ Tek satır, her yere otomatik eklenir
    services.update_plugin("job_123", "tmdb", data)

    # ✅ Event otomatik
    # ✅ ID otomatik
    # ✅ Timestamp otomatik
    # ✅ job ve jobs sync otomatik
```

**Servis Sorumlulukları:**

1. **ID Management** (UUID generation, format)
2. **Event Bus** (plugin.updated, job.updated, job.created)
3. **Timestamp** (started_at, finished_at, duration_ms)
4. **Dual Update** (hem job hem jobs güncellemesi)
5. **Validation** (job var mı, plugin var mı)

---

## 🔄 3. ÖRNEK SENARYOLAR

### Senaryo 1: Per Job Plugin Kendi Data'sını Ekliyor

```python
class TMDbPlugin:
    def execute(self, job, services):
        # Fetch data
        movie_data = self.fetch_movie(...)

        # ✅ YENİ: ID belirt, scope belirt
        services.update_plugin(
            job_id=job.id,
            plugin_name="tmdb",
            data={"movie": movie_data},
            scope="job"
        )

        # Sonuç:
        # plugins.job.tmdb = {movie: {...}}
        # job.status.plugins.tmdb = {state: "completed", ...}  # Sistem ekler
```

### Senaryo 2: Per Run Plugin Bir Job'a Veri Ekliyor

```python
class ScannerPlugin:
    def execute_run(self, services):
        # Her dosya için job oluştur
        for file in files:
            job_id = services.create_job(
                input_value=str(file),
                input_data={"source": "scanner", "filename": file.name}
            )

            # ✅ ESNEKLİK: Per run plugin job'a veri ekleyebiliyor!
            services.update_plugin(
                job_id=job_id,
                plugin_name="scanner",
                data={"scanned_at": now()},
                scope="job"  # Bu job'a özel veri
            )

        # Kendi run-level data'sını ekle
        services.update_plugin(
            job_id=None,
            plugin_name="scanner",
            data={"total_files": len(files)},
            scope="run"  # Tüm run için veri
        )
```

### Senaryo 3: Tasker Plugin Job ve Plugin Güncelliyor

```python
class TaskerPlugin:
    def execute(self, job, services):
        # Task'leri işle
        task_results = self.process_tasks(...)
        output_values = self.collect_outputs(...)

        # ✅ Job output güncelle
        services.update_job(
            job_id=job.id,
            path="output.data.tasks",
            value=task_results
        )

        services.update_job(
            job_id=job.id,
            path="output.values",
            value=output_values
        )

        # ✅ Plugin data güncelle
        services.update_plugin(
            job_id=job.id,
            plugin_name="tasker",
            data={
                "tasks": task_results,
                "output_values": output_values
            },
            scope="job"
        )

        # Sonuç:
        # job.output.data.tasks = {...}
        # job.output.values = [...]
        # plugins.job.tasker = {tasks: {...}, output_values: [...]}
        # job.status.plugins.tasker = {state: "completed", ...}  # Sistem
```

---

## 📐 4. NİHAİ STATE YAPISI

```python
{
  "run": {
    "id": "run_abc123",
    "status": {
      "state": "running",
      "plugins": {
        "scanner": {  # Per run plugin status
          "state": "completed",
          "success": True,
          "started_at": "...",
          "finished_at": "...",
          "duration_ms": 1200
        }
      }
    }
  },

  "job": {  # Current job
    "id": "job_abc123_0",
    "input": {...},
    "output": {...},
    "status": {
      "state": "running",
      "plugins": {
        "tmdb": {  # Per job plugin status
          "state": "completed",
          "success": True,
          "started_at": "...",
          "finished_at": "...",
          "duration_ms": 800
        },
        "renamer": {...},
        "tasker": {...}
      }
    }
  },

  "jobs": [  # All jobs
    {
      "id": "job_abc123_0",
      "status": {
        "plugins": {...}  # Same as job.status.plugins
      }
    }
  ],

  "plugins": {
    "run": {
      "scanner": {  # Per run plugin data (run boyunca 1 kere)
        "count": 10,
        "targets": [...]
      }
    },
    "job": {
      "tmdb": {  # Per job plugin data (her job için)
        "movie": {...},
        "show": {...}
      },
      "renamer": {
        "parsed": {...}
      },
      "tasker": {
        "tasks": {...},
        "output_values": [...]
      }
    }
  }
}
```

---

## 🏗️ 5. MİGRASYON PLANI

### 5.1. İsimlendirme Değişiklikleri

**Snake_case Migration:**

```python
# ÖNCEDEN (camelCase)
services.updatePlugin(data)
services.updateJob(key, value)
services.createJob(...)

# YENİ (snake_case)
services.update_plugin(job_id, plugin_name, data, scope)
services.update_job(job_id, path, value)
services.create_job(input_value, input_data)
```

### 5.2. Plugin Update Pattern

**ÖNCEDEN:**

```python
# Tasker plugin
services.updatePlugin({
    "tasks": task_results,
    "output_values": output_values
})
# ❌ Hangi job? Hangi plugin? Belirsiz!
```

**YENİ:**

```python
# Tasker plugin
services.update_plugin(
    job_id=job.id,
    plugin_name="tasker",
    data={
        "tasks": task_results,
        "output_values": output_values
    },
    scope="job"
)
# ✅ Her şey açık!
```

### 5.3. Adım Adım Migrasyon

1. **Phase 1: Servis metodları ekle (snake_case)**

   - `create_job()`, `update_job()`, `update_plugin()` ekle
   - Eski metodlar deprecated warning versin

2. **Phase 2: Plugin status tracking'i ayır**

   - `job.status.plugins` ve `run.status.plugins` oluştur
   - Sistem otomatik `mark_plugin_started/completed` çağırsın

3. **Phase 3: Plugin data yapısını değiştir**

   - `plugins.job` ve `plugins.run` alt grupları oluştur
   - Eski `plugins.{name}.data` → `plugins.job.{name}` migrate et

4. **Phase 4: Tüm pluginleri güncelle**
   - Her plugin yeni API'yi kullansın
   - ID ve scope parametreleri eklensin

---

## 🎨 6. KARŞILAŞTIRMA: ENDÜSTRI STANDARTLARı

### Apache Airflow XCom

```python
# Airflow
task_instance.xcom_push(key="result", value=data)
other = task_instance.xcom_pull(task_ids="prev", key="result")

# Archiverr (benzer pattern)
services.update_plugin(job_id, "tmdb", data)
tmdb_data = services.get_plugin_data("tmdb", job_id)
```

**Fark:**

- Airflow → Task-centric (task arası iletişim)
- Archiverr → Plugin-centric (plugin arası data sharing)

### Microsoft Agent Framework

```python
# Microsoft - Factory pattern for state isolation
workflow_builder.register_executor(factory_func=CustomExecutor, name="exec_a")

# Archiverr - Scope isolation (run vs job)
services.update_plugin(..., scope="run")  # Run-level isolation
services.update_plugin(..., scope="job")  # Job-level isolation
```

**Benzerlik:** İkisi de state isolation için scope kullanıyor

### Prefect Tasks

```python
# Prefect - Implicit state dependency
@task
def process_data(upstream_result):
    # upstream_result otomatik gelir

# Archiverr - Explicit data access
tmdb_data = services.get_plugin_data("tmdb", job_id)
```

**Fark:**

- Prefect → Implicit dependencies (otomatik)
- Archiverr → Explicit access (manuel ama kontrollü)

---

## ✅ 7. NİHAİ ÖNERİLER

### Data Organizasyonu

**KARAR:** `plugins.run` ve `plugins.job` alt grupları kullan

**Sebep:**

- Config alias kolay (`m.title` → `plugins.job.tmdb.movie.title`)
- API query kolay (`GET /plugins/job/tmdb`)
- Scope ayrımı net

### İletişim Sistemi

**KARAR:** Plugin-agnostic, ID-based servis layer

**Özellikler:**

- ✅ Her plugin her metodu kullanabilir
- ✅ Her iletişimde ID zorunlu (job_id, plugin_name)
- ✅ Scope parameter (`"job"` veya `"run"`)
- ✅ Snake_case isimlendirme
- ✅ Servis layer karmaşık işleri halleder

### Plugin Status Tracking

**KARAR:** Sistem yönetir, plugin dokunmaz

**Konum:**

- Per job → `job.status.plugins.{plugin_name}`
- Per run → `run.status.plugins.{plugin_name}`

**İçerik:**

- `state`, `success`, `started_at`, `finished_at`, `duration_ms`, `error`

### Servis Sorumlulukları

1. ID generation
2. Event bus notifications
3. Timestamp management
4. Dual state update (job + jobs sync)
5. Validation

---

## 🚀 SONUÇ

**Yeni sistem:**

- ✅ **Esnek:** Her plugin her metodu kullanabilir
- ✅ **Açık:** Her iletişimde ID ve scope belirtilir
- ✅ **Güvenli:** Servis layer karmaşık işleri halleder
- ✅ **Profesyonel:** Endüstri standartlarına uygun (Airflow, Prefect, Microsoft)
- ✅ **Bakımı kolay:** Plugin agnostic tasarım, tight coupling yok
