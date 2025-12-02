# BRAINSTORM v2: Plugin Execution Model - Derin Analiz

```yaml
date: 2025-11-29
type: brainstorm
focus: Hybrid Sistemin Sorunları ve Çözümleri
feedback: Kullanıcı geri bildirimleri dahil
```

---

## KULLANİCİ GERİ BİLDİRİMLERİ (ÖNEMLİ!)

### Hybrid Model A+B Karışımının Sorunları:

1. **TMDb Dizi Problemi:**
   - Dizi bölümleri tek tek geliyor
   - TMDb `provides: [job.create]` eklerse run başında çalışır
   - Ama input plugin'lerden job'ların gelmesini beklemesi gerek
   - **Sonuç:** Input bitene kadar output başlamasın mantığı bozulur

2. **RAM Sorunu:**
   - Model A: Tüm job'lar run boyunca RAM'de birikir
   - Model B'nin avantajı (per-job memory) kaybolur

3. **Job Erişim Kısıtlaması:**
   - `provides: [job.create]` demeyenler tüm job'lara erişemez
   - RAM'de tutulan job'lara yok yere erişilmez kılınıyor
   - Erişmek isteyen job oluşturmak zorunda kalıyor

4. **Kullanıcı Önerisi:**
   > "Model A + Job Informer - her job başladığında plugin'lere event gönderilsin"

5. **Eski Sistemle Barışık Olma:**
   > "Eski sisteme düşmanlık yapmanın anlamı yok, overengineering sevmem"

---

## ENDÜSTRİ ÖRNEKLERİ - DERİN ANALİZ

### 1. FlexGet - 7 Kategori Sistemi

```
┌─────────────────────────────────────────────────────────────┐
│                    FLEXGET PLUGIN PHASES                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. INPUT      → Entry'ler üretir (RSS, filesystem, API)    │
│  2. METAINFO   → Entry'lere metadata ekler (title parse)    │
│  3. FILTER     → Entry'leri accept/reject eder              │
│  4. METADATA   → Dış API'lerden veri çeker (TMDb, TVDb)     │
│  5. MODIFICATION → Entry'leri değiştirir (manipulate)       │
│  6. OUTPUT     → Accepted entry'lerle işlem yapar           │
│  7. EXIT       → Cleanup, summary                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**FlexGet Execution Flow:**
```python
# FlexGet'in gerçek execution sırası (task.py'den)
def execute(self):
    # Phase 1: Input - Entry'ler oluşturulur
    self.run_phase('input')
    
    # Phase 2: Metainfo - Title parsing, basic metadata
    self.run_phase('metainfo')
    
    # Phase 3: Filter - Accept/Reject
    self.run_phase('filter')
    
    # Phase 4: Metadata - External API lookups
    self.run_phase('metadata')
    
    # Phase 5: Modification - Entry manipulation
    self.run_phase('modification')
    
    # Phase 6: Output - Actions on accepted entries
    self.run_phase('output')
    
    # Phase 7: Exit - Cleanup
    self.run_phase('exit')
```

**FlexGet'in Önemli Özelliği:**
- Her phase'de TÜM plugin'ler çalışır (o phase'e kayıtlı olanlar)
- Plugin'ler TÜM entry'lere erişir (per-entry değil!)
- Entry'ler her phase'de zenginleşir

**Archiverr'a Uygulanabilirlik:**
- ✅ Birden fazla kategori (7 yerine 5-6)
- ✅ Phase-based execution
- ⚠️ FlexGet entry-centric, Archiverr job-centric

---

### 2. Stremio - Resource-Based Routing

```
┌─────────────────────────────────────────────────────────────┐
│                    STREMIO RESOURCE FLOW                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Action → Request Type → Addon Filtering → Response    │
│                                                              │
│  1. Browse Board/Discover                                    │
│     → Request: /catalog/{type}/{id}                         │
│     → Filter: manifest.resources includes "catalog"         │
│     → Response: Meta Preview objects                         │
│                                                              │
│  2. Click on Item                                            │
│     → Request: /meta/{type}/{id}                            │
│     → Filter: manifest.resources includes "meta"            │
│     → Response: Full Meta object with Videos                 │
│                                                              │
│  3. Click on Video/Episode                                   │
│     → Request: /stream/{type}/{id}                          │
│     → Filter: manifest.resources includes "stream"          │
│     → Response: Stream objects                               │
│                                                              │
│  Key: Addons declare what they CAN provide (resources)       │
│       System requests WHEN it needs that resource            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Stremio'nun Kritik Farkı:**
- **On-Demand Execution:** Plugin'ler "istek üzerine" çalışır
- **Filtering:** System hangi addon'dan istek yapacağına karar verir
- **No Central Orchestration:** Her addon bağımsız HTTP server

**Archiverr'a Uygulanabilirlik:**
- ⚠️ Stremio reactive (request-response), Archiverr proactive (batch processing)
- ✅ `resources` → `provides` konsepti alınabilir
- ❌ On-demand model uygun değil (media batch processing için)

---

### 3. Sonarr/Radarr - Provider Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    SONARR PROCESSING FLOW                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. INDEXERS (Input)                                         │
│     - RSS feeds, API sources                                 │
│     - Torrent/NZB providers                                  │
│                                                              │
│  2. DOWNLOAD CLIENTS (Execution)                             │
│     - SABnzbd, qBittorrent, etc.                            │
│     - Provider pattern: IDownloadClient interface            │
│                                                              │
│  3. NOTIFICATION PROVIDERS (Output)                          │
│     - Email, Slack, Discord                                  │
│     - Triggered on events                                    │
│                                                              │
│  Key: Fixed pipeline, pluggable providers per stage          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Sonarr/Radarr Model:**
- Fixed execution flow (not plugin-controlled)
- Providers implement interfaces
- Core orchestrates everything

**Archiverr'a Uygulanabilirlik:**
- ❌ Çok rigid (esneklik yok)
- ✅ Provider pattern fikri (interface-based plugins)
- ✅ Event-based notifications

---

### 4. Apache Airflow - DAG & Task Model

```
┌─────────────────────────────────────────────────────────────┐
│                    AIRFLOW EXECUTION MODEL                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  DAG (Directed Acyclic Graph)                                │
│  ├── Task A                                                  │
│  │   └── upstream: []                                        │
│  ├── Task B                                                  │
│  │   └── upstream: [A]                                       │
│  ├── Task C                                                  │
│  │   └── upstream: [A]                                       │
│  └── Task D                                                  │
│      └── upstream: [B, C]                                    │
│                                                              │
│  Execution: A → (B, C parallel) → D                          │
│                                                              │
│  Key Features:                                               │
│  - Dependency-based execution order                          │
│  - Tasks can be batch OR per-item                            │
│  - XCom for inter-task communication                         │
│  - Scheduler decides when to run                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Airflow'dan Alınabilecek Konseptler:**
- ✅ Dependency graph (requires → upstream)
- ✅ XCom benzeri inter-plugin communication
- ✅ Parallel execution when no dependency
- ⚠️ Airflow task-centric, Archiverr plugin+job centric

---

### 5. Temporal.io - Workflow + Activity Model

```
┌─────────────────────────────────────────────────────────────┐
│                    TEMPORAL MODEL                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  WORKFLOW (Orchestrator)                                     │
│  ├── Defines execution logic                                 │
│  ├── Handles retries, timeouts                              │
│  └── Maintains state                                         │
│                                                              │
│  ACTIVITIES (Workers)                                        │
│  ├── Actual work units                                       │
│  ├── Stateless                                               │
│  └── Can be distributed                                      │
│                                                              │
│  Workflow calls Activities:                                  │
│  async def process_media(items):                             │
│      for item in items:                                      │
│          parsed = await activity.parse(item)                 │
│          metadata = await activity.fetch_metadata(parsed)    │
│          await activity.rename(item, metadata)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Temporal'dan Alınabilecek:**
- ✅ Workflow = Orchestrator (BAŞKAN)
- ✅ Activities = Plugins
- ✅ Per-item iteration in workflow, not in activity
- ⚠️ Temporal distributed, Archiverr single-process

---

## JOB ID vs INDEX ERİŞİMİ - NETLEŞTİRME

### Mevcut Durum (Codebase'den):

```python
# state/models.py - MatchState
@dataclass
class MatchState:
    index: int              # ← Sadece index var!
    execution_id: str
    input: MatchInput
    status: MatchStatus
    output: MatchOutput
    plugins: Dict[str, Dict[str, Any]]
```

### Önerilen Hybrid ID Sistemi:

```python
@dataclass
class Job:
    # İki ID sistemi
    index: int              # Local, 0-based, in-memory order
    job_id: str             # Global unique, "job_{run_id}_{index}"
    
    # MongoDB'deki _id farklı!
    # _id = ObjectId (MongoDB internal)
    # job_id = Application level unique ID
```

### Erişim Seçenekleri:

```python
class JobService:
    
    # 1. Index ile erişim (hızlı, per-job execution için)
    def get_job_by_index(self, index: int) -> Job:
        return self._jobs[index]
    
    # 2. Job ID ile erişim (global unique, cross-reference için)
    def get_job_by_id(self, job_id: str) -> Job:
        return self._job_id_map[job_id]
    
    # 3. Tüm job'lara erişim (batch execution için)
    def get_all_jobs(self) -> List[Job]:
        return list(self._jobs)
    
    # 4. Query-based erişim (filtering için)
    def get_jobs_where(self, predicate: Callable[[Job], bool]) -> List[Job]:
        return [j for j in self._jobs if predicate(j)]
```

### Plugin Perspektifinden:

```python
class MyPlugin(BasePlugin):
    def execute(self, current_job: Job):
        # Option 1: Sadece current job ile çalış
        self.add_output(current_job.index, {...})
        
        # Option 2: Başka bir job'a referans ver
        related_job_id = "job_run123_5"
        self.add_output(related_job_id, {...})
        
        # Option 3: Tüm job'lara eriş (batch mode'da)
        all_jobs = self.jobs.get_all_jobs()
```

---

## YENİ MODEL ÖNERİSİ: FLEXGET-INSPIRED PHASE SYSTEM

### Neden FlexGet Benzeri?

1. **Kanıtlanmış:** 10+ yıldır aktif kullanımda
2. **Esneklik:** 7 farklı phase, plugin istediğine kayıt olur
3. **Per-Phase Execution:** Her phase'de tüm plugin'ler tüm job'ları görür
4. **Overengineering Değil:** Basit phase sistemi, karmaşık orchestration yok

### Archiverr İçin Önerilen 5 Phase:

```
┌─────────────────────────────────────────────────────────────┐
│                    ARCHIVERR EXECUTION PHASES                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 1: INPUT                                              │
│  ├── provides: [input]                                       │
│  ├── Job'lar oluşturulur                                     │
│  └── Scanner, FileReader                                     │
│                                                              │
│  PHASE 2: PARSE                                              │
│  ├── provides: [parse]                                       │
│  ├── Job input'ları parse edilir                             │
│  └── Renamer (filename → metadata)                           │
│                                                              │
│  PHASE 3: METADATA                                           │
│  ├── provides: [metadata]                                    │
│  ├── External API'lerden veri çekilir                        │
│  ├── BATCH veya PER-JOB seçilebilir!                         │
│  └── TMDb, TVDb, OMDb, FFProbe                               │
│                                                              │
│  PHASE 4: MODIFY (Optional)                                  │
│  ├── provides: [modify]                                      │
│  ├── Job'lar değiştirilir, yeni job'lar oluşturulabilir      │
│  └── Splitter, DuplicateDetector, Grouper                    │
│                                                              │
│  PHASE 5: OUTPUT                                             │
│  ├── provides: [output]                                      │
│  ├── Task'lar çalıştırılır (print, save)                     │
│  └── Core tarafından yönetilir (plugin değil!)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Phase Execution Logic:

```python
class PhaseExecutor:
    PHASES = ['input', 'parse', 'metadata', 'modify', 'output']
    
    def run(self):
        for phase in self.PHASES:
            self._run_phase(phase)
    
    def _run_phase(self, phase: str):
        plugins = self._get_plugins_for_phase(phase)
        
        if phase == 'input':
            # Input phase: Plugin'ler job oluşturur
            for plugin in plugins:
                new_jobs = plugin.execute()
                self.state.add_jobs(new_jobs)
        
        elif phase in ['parse', 'metadata', 'modify']:
            # Data phases: Plugin manifest'e göre batch veya per-job
            for plugin in plugins:
                if plugin.execution_mode == 'batch':
                    plugin.execute_batch(self.state.get_all_jobs())
                else:
                    for job in self.state.get_all_jobs():
                        plugin.execute(job)
        
        elif phase == 'output':
            # Output phase: Task'lar çalıştırılır (plugin değil!)
            for job in self.state.get_all_jobs():
                self.task_manager.execute_tasks(job)
```

### Plugin Manifest Örneği:

```yaml
# plugins/scanner/manifest.yml
name: scanner
version: 1.0.0
phase: input              # Hangi phase'de çalışır
execution_mode: run       # run | per_job (input için hep run)

# plugins/renamer/manifest.yml  
name: renamer
version: 1.0.0
phase: parse
execution_mode: per_job   # Her job için ayrı çalışır
requires: []              # Dependency yok

# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
phase: metadata
execution_mode: batch     # Tüm job'lar için bir kere çalışır (API efficiency!)
requires:
  - renamer.parsed        # Renamer'ın çıktısına ihtiyaç var

# plugins/splitter/manifest.yml (hypothetical)
name: splitter
version: 1.0.0
phase: modify             # Modify phase'de yeni job oluşturabilir
execution_mode: batch     # Tüm job'ları görmeli (duplicate detection için)
requires:
  - renamer.parsed
```

---

## KULLANİCİNİN ÖNERİSİ: JOB INFORMER

### Konsept:

> "Model A + her job başladığında plugin'lere event gönderilsin"

```
┌─────────────────────────────────────────────────────────────┐
│                    JOB INFORMER MODEL                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Model A: Tüm plugin'ler 1 kere çalışır                     │
│           +                                                  │
│  Job Events: Her job oluşturulduğunda event emit edilir     │
│                                                              │
│  Plugin seçer:                                               │
│  1. Event'leri dinle → Per-job processing                   │
│  2. Ignore events → Batch processing (sonra tüm job'lar)    │
│                                                              │
│  Event Flow:                                                 │
│  Scanner.execute() → creates Job 0 → emit("job.created", 0) │
│                    → creates Job 1 → emit("job.created", 1) │
│                    → creates Job 2 → emit("job.created", 2) │
│                                                              │
│  TMDb (batch mode):                                          │
│    Ignores job.created events                                │
│    Waits for "input.complete" event                          │
│    Then processes all jobs in batch                          │
│                                                              │
│  Renamer (per-job mode):                                     │
│    Subscribes to job.created                                 │
│    Processes each job as it arrives                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Artıları:

| # | Avantaj |
|---|---------|
| 1 | Plugin kendi execution modelini seçer |
| 2 | Event-driven = reactive, memory efficient |
| 3 | Batch plugin'ler bekleyebilir |
| 4 | Per-job plugin'ler hemen işleyebilir |
| 5 | Mevcut EventBus kullanılabilir |

### Eksileri:

| # | Dezavantaj |
|---|------------|
| 1 | Event ordering karmaşık |
| 2 | Race condition riski |
| 3 | Debugging zor (async flow) |
| 4 | Dependency yönetimi belirsiz |
| 5 | Endüstri standardı değil |

### Risk Analizi:

**Race Condition Senaryosu:**
```
Timeline:
T1: Scanner creates Job 0 → emit("job.created", 0)
T2: Renamer receives event, starts processing Job 0
T3: Scanner creates Job 1 → emit("job.created", 1)
T4: TMDb starts (batch mode), requests all jobs
T5: Gets [Job 0, Job 1] but Job 0 not yet parsed!
```

**Çözüm Gerekli:** Dependency-aware event processing veya phase-based waiting.

---

## KARŞILAŞTIRMA: 4 MODEL

| Kriter | Model A (Run-Based) | Model B (Job-Based) | Model C (Phase-Based) | Model D (Job Informer) |
|--------|---------------------|---------------------|----------------------|------------------------|
| **Esneklik** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Stabilite** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Debug Kolaylığı** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **API Efficiency** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Memory Efficiency** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Plugin Dev Simplicity** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Endüstri Standardı** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (FlexGet) | ⭐⭐ |
| **Implementation Complexity** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

---

## ÖNERİM: MODEL C (PHASE-BASED) + ESKİ SİSTEM UYUMLULUĞU

### Neden Phase-Based?

1. **FlexGet'ten kanıtlanmış** - 10+ yıl production
2. **Overengineering değil** - Basit phase sıralaması
3. **Eski sistemle uyumlu** - input/output ayrımı korunur
4. **Batch support** - execution_mode ile

### Eski Sistemden Korunan Özellikler:

```yaml
# ESKİ SİSTEM (korunacak)
state:
  current_job: {...}      # ✅ Şuanki job
  jobs: [...]             # ✅ Tüm job'lar

# YENİ EKLENTİLER
manifest:
  phase: input | parse | metadata | modify   # Phase seçimi
  execution_mode: batch | per_job            # Execution modu
  provides: [...]                             # Ne sağlıyor (FlexGet benzeri)
  requires: [...]                             # Neye ihtiyaç duyuyor
```

### Phase-Based Model Detayları:

**1. Her phase'de plugin'ler SIRASIZ çalışır (parallel mümkün)**
   - Sadece requires varsa sıralama yapılır
   - Aynı phase'deki requires olmayan plugin'ler parallel

**2. Plugin execution_mode seçer:**
   - `batch`: Tüm job'ları tek seferde al
   - `per_job`: Her job için ayrı çağrıl

**3. State'de hem current_job hem jobs var:**
   - per_job mode: current_job set edilir
   - batch mode: jobs listesi verilir

**4. Yeni job oluşturma sadece modify phase'de:**
   - input phase: İlk job'lar oluşur
   - modify phase: Mevcut job'lar bölünebilir/gruplandırılabilir

---

## IMPLEMENTATION PLAN

### Week 1: Phase System Core

```python
# core/orchestrator.py
class Orchestrator:
    PHASES = ['input', 'parse', 'metadata', 'modify', 'output']
    
    def run(self):
        for phase in self.PHASES:
            self._execute_phase(phase)
    
    def _execute_phase(self, phase: str):
        plugins = self.plugin_registry.get_by_phase(phase)
        sorted_plugins = self.dependency_resolver.sort(plugins)
        
        for plugin in sorted_plugins:
            if plugin.execution_mode == 'batch':
                context = BatchContext(jobs=self.state.jobs)
                plugin.execute(context)
            else:  # per_job
                for job in self.state.jobs:
                    context = JobContext(current_job=job, all_jobs=self.state.jobs)
                    plugin.execute(context)
```

### Week 2: Plugin Manifest Update

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0

# YENİ: Phase ve execution mode
phase: metadata
execution_mode: batch

# MEVCUT: Dependency
requires:
  - renamer.parsed

# MEVCUT: Config schema
config_schema:
  api_key:
    type: string
    required: true
```

### Week 3: Plugin Migration

1. Scanner: phase=input, execution_mode=run
2. FileReader: phase=input, execution_mode=run
3. Renamer: phase=parse, execution_mode=per_job
4. FFProbe: phase=metadata, execution_mode=per_job
5. TMDb: phase=metadata, execution_mode=batch
6. TVDb: phase=metadata, execution_mode=batch

### Week 4: Testing & Polish

- Integration tests per phase
- Benchmark: batch vs per_job performance
- Documentation update

---

## RISK ANALİZİ

### 1. Dependency Across Phases

**Risk:** TMDb (metadata phase) requires renamer.parsed (parse phase)
**Çözüm:** Phase sıralaması dependency'yi garanti eder

### 2. Batch Mode Memory

**Risk:** 1000 job batch mode'da memory spike
**Çözüm:** Batch size limit (config'de)

### 3. Modify Phase Job Creation

**Risk:** Splitter sonsuz job oluşturabilir
**Çözüm:** Max job limit + recursion guard

### 4. Plugin Developer Confusion

**Risk:** Phase seçimi karmaşık gelebilir
**Çözüm:** Default phase assignment (category'den çıkarım)

---

## SONUÇ

**Öneri: Model C (Phase-Based) + Eski Sistem Uyumluluğu**

- FlexGet'ten esinlenmiş 5-phase system
- `execution_mode: batch | per_job` ile esneklik
- Eski state yapısı korunur (current_job + jobs)
- input/output kategorisi phase ile replace edilir
- requires dependency sistemi korunur

**Tahmini Süre:** 4 hafta
**Risk:** Orta (iyi tanımlanmış scope)
**Uyumluluk:** Mevcut plugin'ler minimal değişiklikle migrate edilebilir

---

**Tarih:** 2025-11-29
**Analyst:** Brainstorm v2
