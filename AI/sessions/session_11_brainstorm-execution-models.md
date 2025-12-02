# BRAINSTORM: Plugin Execution Model Seçimi

```yaml
date: 2025-11-29
type: brainstorm
focus: Run-Based vs Job-Based vs Hybrid Execution
```

---

## SORU 1: Plugin Health Check Kimin Sorumluluğunda?

### Endüstri Örnekleri

| Sistem | Health Check | Sorumlu |
|--------|--------------|---------|
| **Kubernetes** | Liveness/Readiness Probes | Orchestrator (kubelet) |
| **Microservices** | Health Endpoint Pattern | Her servis kendi endpoint'ini sunar |
| **Dagster** | Asset Health Checks | Orchestrator + Per-asset |
| **Airflow** | Task Instance Validation | Scheduler |

### Analiz

**Endüstri Standardı:** Health check **Orchestrator** sorumluluğunda, ama her component kendi health bilgisini sunar.

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                              │
│  - Plugin'leri keşfet                                        │
│  - Manifest'leri validate et (PluginValidator kullanarak)   │
│  - Dependency graph'ı validate et                            │
│  - Execution possibility check                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  PLUGIN VALIDATOR                            │
│  (Ayrı bir utility class - Plugin System'ın parçası değil)  │
│  - Manifest schema validation                                │
│  - Provides/Requires format check                            │
│  - Circular dependency detection                             │
│  - Missing requirement detection                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   EACH PLUGIN                                │
│  - Kendi config'ini validate eder                            │
│  - is_ready() metodu ile hazır olup olmadığını bildirir     │
└─────────────────────────────────────────────────────────────┘
```

**Öneri:** `PluginSystemHealth` → `PluginValidator` olarak ayrı bir utility class olsun, Plugin System'ın içinde değil.

---

## SORU 2: Execution Model Seçimi

### Model A: RUN-BASED (Özgür/Kaotik)

```
RUN BAŞLA
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  TÜM PLUGİNLER BİR KERE ÇALIŞIR                              │
│                                                              │
│  for plugin in sorted_by_requires(plugins):                  │
│      plugin.execute()  // Plugin kendi job'larını yönetir   │
│                                                              │
│  Plugin içinde:                                              │
│    - jobs.create_job()     → istediği kadar                 │
│    - jobs.add_input()      → istediği job'a                 │
│    - jobs.add_output()     → istediği job'a                 │
│    - jobs.get_all_jobs()   → tüm job'lara erişim            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
TASK'LARI ÇALIŞTIR (tüm job'lar için)
    │
    ▼
RUN BİTTİ
```

**ARTILARI:**
| # | Avantaj | Açıklama |
|---|---------|----------|
| 1 | **Maksimum Esneklik** | Plugin istediği anda job oluşturabilir |
| 2 | **Batch Processing** | Plugin tüm job'ları tek seferde işleyebilir (verimli API calls) |
| 3 | **Cross-Job Logic** | Plugin job'lar arası mantık kurabilir (duplicate detection, grouping) |
| 4 | **Late Job Creation** | Son dakikada bile yeni job oluşturulabilir |
| 5 | **Plugin Autonomy** | Plugin kendi execution logic'ini belirler |

**EKSİLERİ:**
| # | Dezavantaj | Açıklama |
|---|------------|----------|
| 1 | **Kaos Potansiyeli** | Hangi plugin ne zaman ne yapar? Debug zor |
| 2 | **Memory Pressure** | Tüm job'lar hafızada tutulmalı |
| 3 | **Conflict Risk** | İki plugin aynı job'a aynı anda erişebilir |
| 4 | **No Per-Job Isolation** | Bir job fail olursa diğerlerini etkiler mi? |
| 5 | **Ordering Complexity** | requires graph'ı karmaşıklaşabilir |
| 6 | **Plugin Developer Burden** | Her plugin kendi job iteration'ını yazmalı |

---

### Model B: JOB-BASED (Düzenli/Sıralı)

```
RUN BAŞLA
    │
    ▼
INPUT PLUGINS → Job'ları oluştur
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  HER JOB İÇİN PLUGİNLER SIRAYLA ÇALIŞIR                      │
│                                                              │
│  for job in jobs:                                            │
│      for plugin in sorted_plugins:                           │
│          plugin.execute(job)  // Sadece bu job için         │
│      run_tasks(job)           // Bu job'ın task'ları        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
RUN BİTTİ
```

**ARTILARI:**
| # | Avantaj | Açıklama |
|---|---------|----------|
| 1 | **Predictable Flow** | Her job aynı pipeline'dan geçer |
| 2 | **Memory Efficient** | Bir seferde 1 job hafızada |
| 3 | **Per-Job Isolation** | Bir job fail olursa sadece o job etkilenir |
| 4 | **Easy Debugging** | Hangi job hangi aşamada? Net |
| 5 | **Simple Plugin Dev** | Plugin sadece 1 job'u işler |
| 6 | **Streaming Possible** | Job tamamlandıkça sonuç verir |

**EKSİLERİ:**
| # | Dezavantaj | Açıklama |
|---|------------|----------|
| 1 | **No Cross-Job Logic** | Plugin job'lar arası mantık kuramaz |
| 2 | **API Inefficiency** | TMDb: 100 job = 100 API call (batch değil) |
| 3 | **No Late Job Creation** | Yeni job oluşturmak karmaşık |
| 4 | **Rigid Structure** | Input → Process → Output kalıbına zorlar |
| 5 | **Hybrid Plugin Zor** | Aynı plugin hem input hem output veremez |

---

### Model C: HYBRID (Lambda Architecture Benzeri)

```
RUN BAŞLA
    │
    ├── PHASE 1: JOB CREATION (Run-Based)
    │   │
    │   │  Sadece provides: [job.create] olan pluginler çalışır
    │   │  Her biri istediği kadar job oluşturur
    │   │
    │   └── Jobs listesi oluştu
    │
    ├── PHASE 2: JOB ENRICHMENT (Job-Based)
    │   │
    │   │  for job in jobs:
    │   │      for plugin in data_plugins:  // input/output providers
    │   │          plugin.execute(job)
    │   │
    │   └── Her job zenginleştirildi
    │
    ├── PHASE 3: POST-PROCESSING (Run-Based, Optional)
    │   │
    │   │  Sadece provides: [post.process] olan pluginler çalışır
    │   │  Cross-job logic: duplicate detection, grouping, etc.
    │   │
    │   └── Final düzenlemeler yapıldı
    │
    └── PHASE 4: TASKS (Job-Based)
        │
        │  for job in jobs:
        │      run_tasks(job)
        │
        └── RUN BİTTİ
```

**ARTILARI:**
| # | Avantaj | Açıklama |
|---|---------|----------|
| 1 | **Best of Both Worlds** | Esneklik + Düzen |
| 2 | **Clear Phases** | Ne zaman ne olur belli |
| 3 | **Batch for APIs** | Job creators batch API call yapabilir |
| 4 | **Per-Job Isolation** | Enrichment phase'de izolasyon |
| 5 | **Cross-Job When Needed** | Post-process phase'de mümkün |
| 6 | **Flexible Plugin Dev** | Plugin ihtiyacına göre phase seçer |

**EKSİLERİ:**
| # | Dezavantaj | Açıklama |
|---|------------|----------|
| 1 | **Complexity** | 4 phase = daha karmaşık sistem |
| 2 | **Phase Restrictions** | Hangi plugin hangi phase'de? Kurallar lazım |
| 3 | **Transition Logic** | Phase'ler arası geçiş yönetimi |
| 4 | **Learning Curve** | Plugin geliştiriciler için |

---

## DETAYLI KARŞILAŞTIRMA TABLOSU

| Kriter | Model A (Run-Based) | Model B (Job-Based) | Model C (Hybrid) |
|--------|---------------------|---------------------|------------------|
| **Esneklik** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Stabilite** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Debug Kolaylığı** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Memory Efficiency** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **API Efficiency** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Plugin Dev Simplicity** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Cross-Job Logic** | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
| **Streaming Support** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Implementation Time** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Future Scalability** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## USE CASE ANALİZİ

### Use Case 1: Scanner - 100 Dosya Taraması

| Model | Davranış | Verimlilik |
|-------|----------|------------|
| A | Scanner bir kere çalışır, 100 job oluşturur | ✅ Optimal |
| B | Scanner 100 kere çalışır mı? Hayır, sadece başta | ✅ Optimal |
| C | Phase 1'de Scanner 100 job oluşturur | ✅ Optimal |

**Sonuç:** Hepsi benzer performans

### Use Case 2: TMDb - 100 Film İçin Metadata

| Model | Davranış | Verimlilik |
|-------|----------|------------|
| A | TMDb bir kere çalışır, 100 job için batch API | ✅ Optimal (tek batch) |
| B | TMDb 100 kere çalışır, her seferinde 1 API call | ❌ 100x API call |
| C | Phase 2'de TMDb 100 kere çalışır | ❌ 100x API call |

**Sonuç:** Model A batch için avantajlı

### Use Case 3: Duplicate Detection (Cross-Job)

| Model | Davranış | Verimlilik |
|-------|----------|------------|
| A | Plugin tüm job'ları görür, duplicate bulur | ✅ Kolay |
| B | Plugin sadece 1 job görür, duplicate bulamaz | ❌ İmkansız |
| C | Phase 3'te tüm job'ları görür | ✅ Kolay |

**Sonuç:** Model A ve C avantajlı

### Use Case 4: Splitter Plugin (Multi-Episode → Multiple Jobs)

| Model | Davranış | Verimlilik |
|-------|----------|------------|
| A | Splitter istediği zaman yeni job oluşturur | ✅ Kolay |
| B | Splitter job-based, yeni job nasıl oluşturur? | ⚠️ Karmaşık |
| C | Splitter Phase 1'de mi Phase 3'te mi? | ⚠️ Phase belirsiz |

**Sonuç:** Model A avantajlı

### Use Case 5: Per-Job Error Isolation

| Model | Davranış | Verimlilik |
|-------|----------|------------|
| A | Bir plugin hata verirse tüm run etkilenir mi? | ⚠️ Tasarıma bağlı |
| B | Bir job hata verirse sadece o job etkilenir | ✅ İzole |
| C | Phase'e bağlı | ⚠️ Karmaşık |

**Sonuç:** Model B avantajlı

---

## ÖNERİM: MODEL C (HYBRID) + BATCH OPTİMİZASYON

### Neden Hybrid?

1. **Archiverr'ın Doğası:** Media file processing = batch-friendly
2. **API Efficiency Önemli:** TMDb, TVDb, OMDb = Rate limited APIs
3. **Cross-Job Logic Gerekli:** Duplicate detection, grouping
4. **Stabilite de Önemli:** Debug edilebilir olmalı

### Önerilen Mimari

```
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION PHASES                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 1: DISCOVERY (Run-Based)                              │
│  ├── provides: [job.create] olan pluginler                   │
│  └── Çıktı: Jobs listesi                                     │
│                                                              │
│  PHASE 2: ENRICHMENT (Hybrid!)                               │
│  ├── provides: [data.input, data.output] olan pluginler      │
│  │                                                           │
│  │   İKİ SEÇENEK:                                            │
│  │   A) plugin.execute_batch(all_jobs) → Batch mode          │
│  │   B) for job: plugin.execute(job)   → Per-job mode        │
│  │                                                           │
│  │   Plugin manifest'te belirtir:                            │
│  │   execution_mode: batch | per_job | auto                  │
│  │                                                           │
│  └── Çıktı: Enriched jobs                                    │
│                                                              │
│  PHASE 3: FINALIZATION (Run-Based, Optional)                 │
│  ├── provides: [post.process] olan pluginler                 │
│  └── Çıktı: Finalized jobs                                   │
│                                                              │
│  PHASE 4: TASKS (Per-Job)                                    │
│  ├── config.yml'den task'lar                                 │
│  └── Çıktı: Executed tasks                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Plugin Manifest'te `execution_mode`

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0

provides:
  - data.output

requires:
  - renamer.parsed

# YENİ: Batch mı per-job mı?
execution_mode: batch  # batch | per_job | auto

# batch: Plugin bir kere çalışır, tüm job'ları işler
# per_job: Plugin her job için ayrı çalışır
# auto: System karar verir (default: per_job)
```

### Plugin Base Class Değişikliği

```python
class BasePlugin(ABC):
    
    # Default: per_job mode
    def execute(self, job: Job) -> PluginResponse:
        """Tek job için çalıştır (per_job mode)"""
        raise NotImplementedError
    
    # Optional: batch mode
    def execute_batch(self, jobs: List[Job]) -> Dict[str, PluginResponse]:
        """Tüm job'lar için çalıştır (batch mode)"""
        # Default implementation: calls execute() for each job
        results = {}
        for job in jobs:
            results[job.job_id] = self.execute(job)
        return results
```

### TMDb Plugin Örneği (Batch Mode)

```python
class TMDbPlugin(BasePlugin):
    
    def execute_batch(self, jobs: List[Job]) -> Dict[str, PluginResponse]:
        """Batch API call ile tüm job'ları işle"""
        
        # 1. Tüm job'lardan query topla
        queries = []
        for job in jobs:
            parsed = job.outputs.get('renamer', {}).get('parsed', {})
            if parsed.get('movie'):
                queries.append({
                    'job_id': job.job_id,
                    'type': 'movie',
                    'title': parsed['movie']['name'],
                    'year': parsed['movie'].get('year')
                })
        
        # 2. Batch API call (TMDb multi-search)
        api_results = self._batch_search(queries)  # 1 API call!
        
        # 3. Sonuçları job'lara eşle
        results = {}
        for job in jobs:
            job_result = api_results.get(job.job_id)
            if job_result:
                self.jobs.add_output(job.job_id, job_result)
                results[job.job_id] = PluginResponse.success()
            else:
                results[job.job_id] = PluginResponse.skipped("No match found")
        
        return results
```

---

## FINAL DECISION MATRIX

| Karar | Seçenek | Gerekçe |
|-------|---------|---------|
| **Execution Model** | Hybrid (Model C) | Esneklik + Stabilite dengesi |
| **Default Mode** | per_job | Basitlik için |
| **Batch Support** | Optional (manifest'te belirt) | API efficiency için |
| **Phase Count** | 4 (Discovery, Enrichment, Finalization, Tasks) | Yeterli ayrım |
| **Health Check** | Orchestrator + PluginValidator | Separation of concerns |

---

## IMPLEMENTATION ROADMAP

```
Week 1: Core Infrastructure
├── Orchestrator (4 phase support)
├── PluginValidator (ayrı utility)
└── Phase routing logic

Week 2: Plugin Services
├── JobService (create, add_input, add_output)
├── BasePlugin (execute + execute_batch)
└── PluginResponse standardization

Week 3: Migration
├── Scanner → Discovery phase
├── Renamer, FFProbe → Enrichment (per_job)
├── TMDb → Enrichment (batch)
└── Tasks → Task phase

Week 4: Testing & Polish
├── Integration tests
├── Performance benchmarks
└── Documentation
```

---

**Tarih:** 2025-11-29
**Analyst:** Brainstorm Session
