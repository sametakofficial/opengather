# SESSION 11 STRATEGY v7 - FINAL DECISIONS & MEMORY MANAGEMENT

```yaml
date: 2025-11-30
type: strategy
status: in_progress
previous_version: v6 + brainstorm-v2
focus: 
  - Final Execution Model Decisions
  - Memory Management Research
  - Run/Runs State Architecture
analyst: Strategy Chat
```

---

## PART 1: SESSION 11 SON KARARLAR ÖZETİ

### 1.1 Evolution Timeline

| Version | Focus | Status |
|---------|-------|--------|
| v1 | Alias sistemi, explicit paths | ❌ Fazla karmaşık |
| v2 | Nested state yapısı, match/execution refactor | ⚠️ Kısmi kabul |
| v3 | 3 sistem alias (execution, match, matches) | ⚠️ Terminoloji tartışması |
| v4 | Category-free plugins, run/job terminology | ❌ HALÜSİNASYON - mevcut sistemler görmezden gelindi |
| v5 | Mevcut sistem analizi, halüsinasyon tespiti | ✅ Kritik bulgular |
| v6 | SDK sorgulaması, Orchestrator eksikliği, Free Plugin | ⚠️ Derinlemesine analiz |
| brainstorm-v1 | Run-based vs Job-based vs Hybrid model | ⚠️ Model karşılaştırması |
| brainstorm-v2 | FlexGet-inspired Phase system | ✅ **ONAYLANDI** |
| **v7** | Final kararlar + Memory Management | 🔄 **ŞU AN** |

---

### 1.2 ONAYLANAN EXECUTION MODEL: 5-PHASE SYSTEM

```
┌─────────────────────────────────────────────────────────────┐
│                    ARCHIVERR EXECUTION PHASES                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              GENERAL CATEGORY: INPUT                     ││
│  │                                                          ││
│  │  PHASE 1: INPUT                                          ││
│  │  ├── provides: [input]                                   ││
│  │  ├── Job'lar oluşturulur                                 ││
│  │  └── Scanner, FileReader                                 ││
│  │                                                          ││
│  │  PHASE 2: PARSE                                          ││
│  │  ├── provides: [parse]                                   ││
│  │  ├── Job input'ları parse edilir                         ││
│  │  └── Renamer (filename → metadata)                       ││
│  │                                                          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              GENERAL CATEGORY: OUTPUT                    ││
│  │                                                          ││
│  │  PHASE 3: METADATA                                       ││
│  │  ├── provides: [metadata]                                ││
│  │  ├── External API'lerden veri çekilir                    ││
│  │  ├── BATCH veya PER-JOB seçilebilir!                     ││
│  │  └── TMDb, TVDb, OMDb, FFProbe                           ││
│  │                                                          ││
│  │  PHASE 4: MODIFY (Optional)                              ││
│  │  ├── provides: [modify]                                  ││
│  │  ├── Job'lar değiştirilir, yeni job'lar oluşturulabilir  ││
│  │  └── Splitter, DuplicateDetector, Grouper                ││
│  │                                                          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         PHASE 5: OUTPUT (AYRI ALAN - TASK'LARA AİT)     ││
│  │  ├── Plugin sistemi DIŞINDA                              ││
│  │  ├── Core tarafından yönetilir                           ││
│  │  ├── Task'lar çalıştırılır (print, save)                 ││
│  │  └── config.yml'deki tasks tanımları                     ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 KATEGORİ YAPISI

```
Plugin Categories:
├── INPUT (Genel Kategori)
│   ├── input (Phase 1) - Job oluşturur
│   └── parse (Phase 2) - Job'ları parse eder
│
└── OUTPUT (Genel Kategori)  
    ├── metadata (Phase 3) - External data çeker
    └── modify (Phase 4) - Job'ları değiştirir

Task System (AYRI):
└── output (Phase 5) - Plugin DEĞİL, Core'un işi
```

---

### 1.4 STATE YAPISI: RUN + RUNS

```python
# State tutma stratejisi
class RunState:
    """Tek bir execution'ın durumu"""
    id: str
    status: str  # pending, running, success, failed
    config: Dict
    jobs: List[Job]  # Bu run'daki job'lar
    timing: Timing

class StateManager:
    """Global state yöneticisi"""
    
    # Aktif run (şu an çalışan)
    current_run: RunState
    
    # Tüm run'lar (memory'de veya MongoDB'de)
    runs: Dict[str, RunState]  # run_id -> RunState
```

---

## PART 2: MEMORİ YÖNETİMİ PROBLEMİ

### 2.1 Problem Tanımı

**Senaryo:** 10,000 dosya taranan büyük bir media library

```
Run başladı
├── Scanner 10,000 job oluşturdu
├── Renamer her job için parse data ekledi
├── TMDb her job için metadata ekledi
├── ...
└── Memory: 2GB+ (tüm job data'ları RAM'de)
```

**Kullanıcının İstekleri:**

1. **Maksimum memory sınırı** - Örn: 500MB
2. **Otomatik MongoDB flush** - Sınır dolunca kaydet
3. **Akıllı lazy loading** - Plugin 1. job'u isterse MongoDB'den çek
4. **Hem run hem runs tutulsun** - Tek run + run history

---

### 2.2 Çözülmesi Gereken Sorular

| # | Soru | Kararın Etkisi |
|---|------|----------------|
| 1 | Hangi data hot (RAM), hangi cold (MongoDB)? | Memory vs Speed tradeoff |
| 2 | Flush trigger ne? Byte count mu, job count mu? | Implementation complexity |
| 3 | Plugin hangi job'lara erişebilir? | API design |
| 4 | Historical runs ne kadar süre tutulur? | Storage cost |
| 5 | Partial flush mümkün mü? (Sadece tamamlanan job'lar) | Memory efficiency |

---

## PART 3: ENDÜSTRİ ARAŞTIRMASI GEREKLİ

### 3.1 Araştırılacak Konular

1. **Large-scale data processing memory patterns**
   - Apache Spark memory management
   - Pandas chunking strategies
   - Dask lazy evaluation

2. **Message queue / event sourcing patterns**
   - Kafka offset management
   - Redis stream memory limits
   - RabbitMQ message persistence

3. **Database-backed state management**
   - Airflow XCom limitations
   - Temporal.io workflow state
   - Dagster asset materialization

4. **Hot/Cold data tiering**
   - Redis + MongoDB patterns
   - Cache eviction strategies (LRU, LFU)
   - Write-through vs Write-behind caching

5. **Memory-mapped files**
   - SQLite as cache
   - LMDB for fast key-value
   - mmap for large datasets

---

### 3.2 Beklenen Araştırma Çıktıları

```yaml
research_output:
  patterns:
    - name: "Pattern Name"
      source: "Technology/Project"
      how_it_works: "..."
      pros: [...]
      cons: [...]
      archiverr_fit: "high/medium/low"
  
  recommended_approach:
    strategy: "..."
    implementation: "..."
    estimated_effort: "..."
```

---

## PART 4: ÖNCEKİ SESSION'LARDAN ALINAN DERSLER

### 4.1 Halüsinasyon Önleme Kuralları

| # | Kural | Neden |
|---|-------|-------|
| 1 | Kod okumadan plan yapma | v4 mevcut EventBus'ı görmedi |
| 2 | "Oluşturulacak" demeden önce var mı kontrol et | Duplicate code riski |
| 3 | Mevcut sistemleri geliştir, yeniden yazma | Gereksiz breaking change |
| 4 | Test edilmemiş = Tamamlanmamış | Session 7-9 hataları |

### 4.2 Korunacak Mevcut Sistemler

```
✅ KORUNACAK:
├── events/bus.py (EventBus - 286 satır, tam işlevsel)
├── state/manager.py (StateManager - 594 satır)
├── core/plugins/executor.py (Plugin execution)
├── core/plugins/sdk/ (SDK dosyaları)
└── core/tasks/ (Task system)

❌ YENİDEN YAZILMAYACAK:
├── EventBus (zaten var)
├── Orchestrator (executor.py zaten bu işi yapıyor)
└── SDK (sadece terminology değişebilir: SDK → Services)
```

### 4.3 Terminoloji Kararları

| Eski | Yeni | Alias | Status |
|------|------|-------|--------|
| execution | run | execution deprecated | ✅ Onaylı |
| match | job | match deprecated | ✅ Onaylı |
| matches | jobs | matches deprecated | ✅ Onaylı |
| not_supported | skipped | - | ✅ Onaylı |
| SDK | Plugin Services | - | ⚠️ Tartışmalı |

---

## PART 5: ONAYLANAN TEKNIK KARARLAR

### 5.1 Plugin Manifest Yapısı

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
description: Fetches metadata from TMDb

# YENİ: Phase sistemi
phase: metadata          # input | parse | metadata | modify
execution_mode: batch    # batch | per_job

# MEVCUT: Dependency (korunuyor)
requires:
  - renamer.parsed

# MEVCUT: Config schema (korunuyor)
config_schema:
  api_key:
    type: string
    required: true
```

### 5.2 Job ID Sistemi

```python
class Job:
    # Dual identification
    index: int              # Local, 0-based, in-memory (fast access)
    job_id: str             # Global unique: "job_{run_id}_{index}"
    
    # MongoDB'deki _id farklı (internal)
    # job_id = Application level unique ID
```

### 5.3 Execution Mode

```python
class BasePlugin:
    # Default: per_job mode
    def execute(self, job: Job) -> PluginResponse:
        """Tek job için çalıştır"""
        raise NotImplementedError
    
    # Optional: batch mode
    def execute_batch(self, jobs: List[Job]) -> Dict[str, PluginResponse]:
        """Tüm job'lar için çalıştır (API efficiency)"""
        results = {}
        for job in jobs:
            results[job.job_id] = self.execute(job)
        return results
```

---

## PART 6: SONRAKI ADIMLAR

### 6.1 Bu Session'da (v7)

1. [x] Session 11 tüm kararları özetle
2. [ ] Memory management endüstri araştırması
3. [ ] Araştırma sonuçlarını dokümante et
4. [ ] Final memory strategy öner

### 6.2 Execution Session'da

1. [ ] Phase system implementasyonu
2. [ ] Plugin manifest migration
3. [ ] Memory management implementasyonu
4. [ ] Test yazımı

---

## PART 7: MEMORY MANAGEMENT ARAŞTIRMA SONUÇLARI

### 7.1 Araştırılan Sistemler ve Patternler

---

#### A. Apache Spark - Disk Spill Pattern

**Kaynak:** Towards Data Science - Memory Management in Apache Spark

**Nasıl Çalışıyor:**
```
┌─────────────────────────────────────────────────────────────┐
│                    SPARK MEMORY MODEL                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  UNIFIED MEMORY REGION                                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  STORAGE MEMORY      │      EXECUTION MEMORY            ││
│  │  (cached data)       │      (computation)               ││
│  │                      │                                   ││
│  │  ◄── Dynamic ──►                                        ││
│  │      sharing                                             ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│                              ▼ (memory full)                 │
│                       ┌─────────────┐                        │
│                       │  DISK SPILL │                        │
│                       │  (overflow) │                        │
│                       └─────────────┘                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key Concepts:**
1. **Dynamic Allocation:** Storage ve Execution memory birbirinden ödünç alabilir
2. **LRU Eviction:** Least Recently Used veri önce atılır
3. **Disk Spill:** Memory dolunca disk'e yaz, tekrar gerektiğinde oku
4. **Partition-based:** Data partitionlara bölünür, partition bazında spill

**Archiverr'a Uygulanabilirlik:** ⭐⭐⭐⭐ (Yüksek)
- Tamamlanan job'lar "cold" data, MongoDB'ye spill edilebilir
- Aktif job'lar "hot" data, RAM'de

---

#### B. Redis - Eviction Policies

**Kaynak:** Redis Documentation - Key Eviction

**Mevcut Politikalar:**

| Policy | Açıklama | Use Case |
|--------|----------|----------|
| `noeviction` | Evict yok, hata döndür | Kritik data |
| `allkeys-lru` | En az kullanılanı at (LRU) | **Genel kullanım - DEFAULT** |
| `allkeys-lfu` | En az sıklıkta kullanılanı at | Sık erişilen data |
| `volatile-lru` | TTL'li anahtarlardan LRU | Cache + persistent mix |
| `volatile-ttl` | En kısa TTL'yi at | Time-based cleanup |

**Configuration:**
```redis
maxmemory 500mb
maxmemory-policy allkeys-lru
```

**Archiverr'a Uygulanabilirlik:** ⭐⭐⭐⭐⭐ (Çok Yüksek)
- `maxmemory` → Archiverr için `max_state_memory` config
- `allkeys-lru` → Tamamlanan job'ları MongoDB'ye flush

---

#### C. Airflow XCom - Inter-task Communication

**Kaynak:** Apache Airflow Documentation

**Limitasyonlar:**
- XCom = **küçük data** için tasarlandı
- Büyük DataFrame'ler için KULLANILMAMALI
- Default backend = Metadata DB (SQL)

**Çözümler:**
```python
# Custom XCom Backend
class ObjectStorageXComBackend(BaseXCom):
    @staticmethod
    def serialize_value(value):
        # Büyük veri → S3/GCS'e yaz, key döndür
        key = upload_to_storage(value)
        return key
    
    @staticmethod
    def deserialize_value(key):
        # Key → Storage'dan oku
        return download_from_storage(key)
```

**Archiverr'a Uygulanabilirlik:** ⭐⭐⭐ (Orta)
- Job data büyük olabilir (TMDb full response, FFProbe data)
- Custom backend pattern = MongoDB'ye serialize/deserialize

---

#### D. Temporal.io - Workflow State Persistence

**Kaynak:** Temporal Documentation

**Yaklaşım:**
- **Her State Transition** → Persistence store'a yazılır
- **Durability:** Zaman limiti yok, crash'den sonra kaldığı yerden devam
- **Continue-As-New:** Büyük workflow'ları böl, fresh state ile devam et

**Pattern:**
```
Workflow Execution:
  T1: Start         → Persist event
  T2: Activity A    → Persist event  
  T3: Activity B    → Persist event
  ...
  TN: Complete      → Persist event
  
  CRASH at T5?
  → Replay T1-T5 from persistence
  → Continue from T5
```

**Archiverr'a Uygulanabilirlik:** ⭐⭐⭐⭐ (Yüksek)
- Her job completion → MongoDB persist (crash recovery)
- Run state = Event sourcing pattern

---

#### E. Caching Patterns - Write Policies

**Kaynak:** Shahriar Tajbakhsh - Understanding Caching Policies

**3 Temel Pattern:**

| Pattern | Nasıl | Avantaj | Dezavantaj |
|---------|-------|---------|------------|
| **Write-Through** | Cache + DB aynı anda | Data safety | Yavaş write |
| **Write-Around** | Sadece DB | Cache flood yok | İlk read yavaş |
| **Write-Back** | Cache önce, DB background | Hızlı write | Data loss riski |

```python
# Write-Through (Önerilen)
def write_through(cache, db, data):
    cache.write(data)      # RAM'e yaz
    db.write(data)         # MongoDB'ye yaz
    return "OK"            # İkisi de bitti

# Write-Back (Performans için)
def write_back(cache, db, data):
    cache.write(data)      # RAM'e yaz
    queue_for_db(data)     # Background flush
    return "OK"            # Cache yetti
```

**Archiverr'a Uygulanabilirlik:** ⭐⭐⭐⭐⭐ (Çok Yüksek)
- **Normal mod:** Write-through (her job MongoDB'ye)
- **High-performance mod:** Write-back + batch flush

---

### 7.2 ÖNERİLEN STRATEJİ: HYBRID MEMORY MANAGEMENT

#### Strateji Özeti

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARCHIVERR MEMORY MANAGEMENT                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CONFIG:                                                                     │
│    max_state_memory: 500MB (configurable)                                    │
│    flush_strategy: write_through | write_back                                │
│    eviction_policy: lru | completed_first                                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         HOT STATE (RAM)                                  ││
│  │                                                                          ││
│  │   current_run: RunState                                                  ││
│  │   ├── id: "run_123"                                                      ││
│  │   ├── status: "running"                                                  ││
│  │   ├── config: {...}                                                      ││
│  │   └── active_jobs: {0: Job, 1: Job, 2: Job}  ← RAM'de                    ││
│  │                                                                          ││
│  │   Memory Tracking:                                                       ││
│  │   ├── current_size: 245MB                                                ││
│  │   ├── max_size: 500MB                                                    ││
│  │   └── jobs_in_memory: 150                                                ││
│  │                                                                          ││
│  └──────────────────────────────────┬──────────────────────────────────────┘│
│                                     │                                        │
│                                     │ Memory > 80% threshold                 │
│                                     │ OR Job completed                       │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      FLUSH TO COLD STORAGE                               ││
│  │                                                                          ││
│  │   1. Tamamlanan job'ları MongoDB'ye yaz                                  ││
│  │   2. RAM'den sil (sadece job_id referansı tut)                           ││
│  │   3. Memory counter güncelle                                             ││
│  │                                                                          ││
│  └──────────────────────────────────┬──────────────────────────────────────┘│
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                       COLD STATE (MongoDB)                               ││
│  │                                                                          ││
│  │   Collections:                                                           ││
│  │   ├── runs: {run_id, status, config, timing, ...}                        ││
│  │   ├── jobs: {run_id, index, job_id, input, status, ...}                  ││
│  │   └── plugins: {run_id, job_index, plugin_name, data, ...}               ││
│  │                                                                          ││
│  │   Indexes:                                                               ││
│  │   ├── jobs: {run_id: 1, index: 1} unique                                 ││
│  │   └── plugins: {run_id: 1, job_index: 1, plugin_name: 1} unique          ││
│  │                                                                          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                     │                                        │
│                                     │ Plugin requests old job data           │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                       LAZY LOADING                                       ││
│  │                                                                          ││
│  │   def get_job(self, job_id: str) -> Job:                                 ││
│  │       # 1. RAM'de var mı?                                                ││
│  │       if job_id in self.active_jobs:                                     ││
│  │           return self.active_jobs[job_id]                                ││
│  │                                                                          ││
│  │       # 2. MongoDB'den yükle                                             ││
│  │       job_data = self.db.jobs.find_one({"job_id": job_id})               ││
│  │       plugin_data = self.db.plugins.find({"job_id": job_id})             ││
│  │                                                                          ││
│  │       # 3. Hydrate et                                                    ││
│  │       job = Job.from_dict(job_data, plugin_data)                         ││
│  │                                                                          ││
│  │       # 4. (Optional) RAM'e cache'le                                     ││
│  │       if self.should_cache(job):                                         ││
│  │           self.active_jobs[job_id] = job                                 ││
│  │                                                                          ││
│  │       return job                                                         ││
│  │                                                                          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 7.3 IMPLEMENTATION DETAYLARI

#### A. Memory Tracking

```python
import sys
from typing import Dict, Optional

class MemoryTracker:
    """Track state memory usage"""
    
    def __init__(self, max_bytes: int = 500 * 1024 * 1024):  # 500MB default
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self._job_sizes: Dict[str, int] = {}
    
    def track_job(self, job_id: str, job: 'Job'):
        """Track memory usage of a job"""
        size = self._calculate_size(job)
        self._job_sizes[job_id] = size
        self.current_bytes += size
    
    def untrack_job(self, job_id: str):
        """Remove job from tracking (after flush)"""
        if job_id in self._job_sizes:
            self.current_bytes -= self._job_sizes[job_id]
            del self._job_sizes[job_id]
    
    def should_flush(self) -> bool:
        """Check if we should flush to MongoDB"""
        threshold = self.max_bytes * 0.8  # 80% threshold
        return self.current_bytes >= threshold
    
    def _calculate_size(self, obj) -> int:
        """Estimate object size in bytes"""
        return sys.getsizeof(obj)  # Simplified - need deep size calculation
```

#### B. Flush Manager

```python
class FlushManager:
    """Manage flushing jobs to MongoDB"""
    
    def __init__(self, db, memory_tracker: MemoryTracker):
        self.db = db
        self.memory = memory_tracker
        self._pending_flush: List[str] = []  # job_ids to flush
    
    def mark_for_flush(self, job_id: str):
        """Mark a completed job for flushing"""
        self._pending_flush.append(job_id)
    
    def flush_if_needed(self, state: 'StateManager'):
        """Flush jobs if memory threshold exceeded"""
        if not self.memory.should_flush() and not self._pending_flush:
            return
        
        # Strategy: Flush completed jobs first
        jobs_to_flush = self._get_flushable_jobs(state)
        
        for job_id in jobs_to_flush:
            self._flush_job(state, job_id)
    
    def _flush_job(self, state: 'StateManager', job_id: str):
        """Flush single job to MongoDB"""
        job = state.get_job_from_ram(job_id)
        if not job:
            return
        
        # Write job to MongoDB
        self.db.jobs.replace_one(
            {"job_id": job_id},
            job.to_dict(),
            upsert=True
        )
        
        # Write plugin data
        for plugin_name, plugin_data in job.plugins.items():
            self.db.plugins.replace_one(
                {"job_id": job_id, "plugin_name": plugin_name},
                {"job_id": job_id, "plugin_name": plugin_name, "data": plugin_data},
                upsert=True
            )
        
        # Remove from RAM (keep job_id reference)
        state.evict_job_from_ram(job_id)
        self.memory.untrack_job(job_id)
        
        if job_id in self._pending_flush:
            self._pending_flush.remove(job_id)
```

#### C. Lazy Loader

```python
class LazyJobLoader:
    """Load jobs from MongoDB on demand"""
    
    def __init__(self, db):
        self.db = db
        self._cache: Dict[str, Job] = {}  # Small in-memory cache
        self._cache_max = 10  # Keep last 10 accessed jobs
    
    def load(self, job_id: str) -> Optional['Job']:
        """Load job from MongoDB"""
        # Check cache first
        if job_id in self._cache:
            return self._cache[job_id]
        
        # Load from MongoDB
        job_doc = self.db.jobs.find_one({"job_id": job_id})
        if not job_doc:
            return None
        
        # Load plugin data
        plugin_docs = list(self.db.plugins.find({"job_id": job_id}))
        plugins = {doc["plugin_name"]: doc["data"] for doc in plugin_docs}
        
        # Hydrate
        job = Job.from_dict(job_doc, plugins)
        
        # LRU cache
        self._cache[job_id] = job
        if len(self._cache) > self._cache_max:
            # Remove oldest
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        
        return job
```

---

### 7.4 CONFIG YAPISI

```yaml
# config.yml - Memory Management Section
options:
  debug: true
  dry_run: false
  
  # YENİ: Memory management
  memory:
    max_state_mb: 500           # Maximum RAM for state (default: 500MB)
    flush_strategy: write_through  # write_through | write_back
    flush_threshold: 0.8        # Flush when 80% full
    eviction_policy: completed_first  # completed_first | lru
    lazy_load_cache_size: 10    # Jobs to keep in lazy load cache
```

---

### 7.5 KARŞILAŞTIRMA: ÖNCEKİ vs YENİ YAKLAŞIM

| Aspect | Önceki (Tüm RAM'de) | Yeni (Hybrid) |
|--------|---------------------|---------------|
| **Memory Usage** | Unbounded (job sayısına bağlı) | Bounded (max_state_mb) |
| **10K Job Senaryosu** | ~2GB+ RAM | ~500MB (config'e bağlı) |
| **Crash Recovery** | ❌ Tüm veri kaybolur | ✅ MongoDB'den restore |
| **Plugin Job Access** | ✅ Hızlı (RAM) | ✅ Hızlı (hot) / ⚠️ Lazy load (cold) |
| **Complexity** | Basit | Orta |
| **MongoDB Load** | Sadece sonunda | Incremental |

---

### 7.6 EDGE CASES VE ÇÖZÜMLER

| Edge Case | Çözüm |
|-----------|-------|
| Plugin eski job'a erişmek istiyor | Lazy loader ile MongoDB'den yükle |
| Flush sırasında crash | Write-through garantisi, MongoDB'de mevcut |
| RAM yetmedi (threshold aşıldı) | Agresif flush + LRU eviction |
| Batch mode plugin tüm job'ları istiyor | Streaming iterator ile MongoDB'den oku |
| Run history çok büyüdü | TTL index veya manual cleanup |

---

## PART 8: SONUÇ VE KARAR

### 8.1 SESSION 11 FİNAL KARARLAR

| # | Karar | Status |
|---|-------|--------|
| 1 | 5-Phase Execution Model (Input, Parse, Metadata, Modify, Output) | ✅ ONAYLANDI |
| 2 | OUTPUT phase = Task system (plugin değil) | ✅ ONAYLANDI |
| 3 | Genel kategoriler: INPUT (input+parse), OUTPUT (metadata+modify) | ✅ ONAYLANDI |
| 4 | State: current_run + runs (history) | ✅ ONAYLANDI |
| 5 | Memory Management: Bounded RAM + MongoDB flush | ✅ ÖNERİLDİ |
| 6 | Eviction Policy: completed_first (tamamlanan job'ları flush) | ✅ ÖNERİLDİ |
| 7 | Lazy Loading: MongoDB'den on-demand job yükleme | ✅ ÖNERİLDİ |

### 8.2 EXECUTION SESSION İÇİN GÖREVLER

| # | Görev | Tahmini Süre |
|---|-------|---------------|
| 1 | Phase system core implementation | 2 saat |
| 2 | Plugin manifest migration (phase, execution_mode) | 1 saat |
| 3 | MemoryTracker implementation | 1 saat |
| 4 | FlushManager implementation | 1.5 saat |
| 5 | LazyJobLoader implementation | 1 saat |
| 6 | StateManager refactor (hybrid state) | 2 saat |
| 7 | Config schema update (memory section) | 30 dk |
| 8 | Tests | 2 saat |

**Toplam Tahmini Süre:** ~11-12 saat (2-3 session)

---

**Tarih:** 2025-11-30
**Status:** ✅ STRATEGY COMPLETE - Ready for Execution
**Analyst:** Strategy Chat
**Research:** Apache Spark, Redis, Airflow, Temporal.io, Caching Patterns

