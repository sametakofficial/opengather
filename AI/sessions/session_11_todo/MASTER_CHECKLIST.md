# SESSION 11 - MASTER CHECKLIST

```yaml
tarih: 2025-12-04
son_güncelleme: 2025-12-04
toplam_phase: 9
tahmini_toplam_süre: 42-58 saat
```

---

## 📋 KULLANIM KILAVUZU

Bu dosya tüm phase'lerin checklist'lerini içerir. Her yapay zeka oturumunda:

1. İlgili phase bölümünü bul
2. Tamamlanan maddeleri `[x]` olarak işaretle
3. Kalan maddeleri incele
4. İlgili phase dosyasını (`01_PHASE1_*.md`) referans al

**⚠️ Her maddeyi işaretlemeden önce gerçekten tamamlandığını doğrula!**

---

## 🔴 PHASE 1: STATE MODELS & TERMİNOLOJİ

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `01_PHASE1_STATE_MODELS.md`

### Checklist

#### 1.1 Enum ve Yardımcı Dataclass'lar

- [ ] `StateEnum` (eski ExecutionStatus) oluşturuldu
- [ ] `InputData` dataclass oluşturuldu
- [ ] `OutputData` dataclass oluşturuldu
- [ ] Unit testler yazıldı

#### 1.2 Status Dataclass'lar

- [ ] `JobStatus` dataclass oluşturuldu
- [ ] `RunStatus` dataclass oluşturuldu
- [ ] Default değerler test edildi

#### 1.3 Ana State Dataclass'lar

- [ ] `JobState` (eski MatchState) oluşturuldu
- [ ] `RunState` (eski ExecutionState) oluşturuldu
- [ ] `__post_init__` ile job_id oluşturuluyor
- [ ] Nested yapılar (input, output, status) çalışıyor

#### 1.4 Serialization

- [ ] `to_dict()` metodları güncellendi
- [ ] MongoDB format'ı doğru
- [ ] API format'ı uyumlu

#### 1.5 Backward Compatibility

- [ ] `ExecutionState = RunState` alias eklendi
- [ ] `MatchState = JobState` alias eklendi
- [ ] `ExecutionStatus = StateEnum` alias eklendi
- [ ] Mevcut import'lar çalışıyor

#### 1.6 Test

- [ ] Unit testler yazıldı
- [ ] Unit testler PASS
- [ ] Regression testler PASS
- [ ] Mevcut kod hala çalışıyor

#### 1.7 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase1`

---

## 🔴 PHASE 2: MONGODB & PERSISTENCE

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `02_PHASE2_MONGODB.md`

**Ön Koşul:** Phase 1 tamamlanmış olmalı ✅

### Checklist

#### 2.1 PersistenceInterface

- [ ] `save_run()` metodu eklendi
- [ ] `save_job()` metodu eklendi
- [ ] `save_plugin()` metodu eklendi
- [ ] `get_run()` metodu eklendi
- [ ] `get_jobs()` metodu eklendi
- [ ] `get_plugins()` metodu eklendi

#### 2.2 MockPersistence

- [ ] `_runs` dict eklendi
- [ ] `_jobs` dict eklendi
- [ ] `_plugins` dict eklendi
- [ ] Yeni metodlar implemente edildi
- [ ] Backward compat wrapper'lar eklendi

#### 2.3 PyMongoPersistence

- [ ] `runs` collection referansı eklendi
- [ ] `jobs` collection referansı eklendi
- [ ] `plugins` collection referansı eklendi
- [ ] Document format dönüşümü yapıldı
- [ ] `ensure_indexes()` metodu eklendi

#### 2.4 Index Tanımları

- [ ] runs: `{id: 1}` unique
- [ ] runs: `{created_at: -1}`
- [ ] runs: `{status.state: 1}`
- [ ] jobs: `{run_id: 1, index: 1}` unique
- [ ] jobs: `{id: 1}` unique
- [ ] plugins: `{job_id: 1, plugin_name: 1}` unique

#### 2.5 StateManager Entegrasyonu

- [ ] `_persist_run()` güncellendi
- [ ] `_persist_job()` güncellendi
- [ ] `_persist_plugin()` eklendi

#### 2.6 Test

- [ ] MockPersistence unit testleri PASS
- [ ] MongoDB integration testleri PASS
- [ ] Backward compat testleri PASS

#### 2.7 Migration (Opsiyonel)

- [ ] Migration script yazıldı
- [ ] Dry-run test edildi
- [ ] Production migration yapıldı (gerekirse)

#### 2.8 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase2`

---

## 🟠 PHASE 3: PLUGIN SERVICES

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `03_PHASE3_PLUGIN_SERVICES.md`

**Ön Koşul:** Phase 1 ve 2 tamamlanmış olmalı ✅

### Checklist

#### 3.1 Protocol Tanımları

- [ ] `core/services/` dizini oluşturuldu
- [ ] `StateService` protocol tanımlandı
- [ ] `EventService` protocol tanımlandı
- [ ] `LoggerService` protocol tanımlandı
- [ ] `ConfigService` protocol tanımlandı

#### 3.2 Service Implementasyonları

- [ ] `StateServiceImpl` yazıldı
- [ ] `EventServiceImpl` yazıldı
- [ ] `LoggerServiceImpl` yazıldı
- [ ] `ConfigServiceImpl` yazıldı

#### 3.3 PluginServices

- [ ] `PluginServices` dataclass oluşturuldu
- [ ] `create_plugin_services()` factory oluşturuldu
- [ ] `services_from_context()` adapter (geçici)

#### 3.4 Plugin Base

- [ ] `PluginStatus` enum oluşturuldu
- [ ] `PluginResult` dataclass oluşturuldu
- [ ] `BasePlugin` ABC güncellendi
- [ ] `execute(job, services)` signature
- [ ] `execute_run(services)` signature

#### 3.5 Backward Compatibility

- [ ] `LegacyPluginAdapter` (gerekirse)
- [ ] Mevcut plugin'ler çalışıyor

#### 3.6 Test

- [ ] StateService unit testleri PASS
- [ ] ConfigService unit testleri PASS
- [ ] EventService unit testleri PASS
- [ ] LoggerService unit testleri PASS
- [ ] PluginServices integration testi PASS

#### 3.7 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase3`

---

## 🟠 PHASE 4: ORCHESTRATOR

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `04_PHASE4_ORCHESTRATOR.md` (oluşturulacak)

**Ön Koşul:** Phase 1, 2, 3 tamamlanmış olmalı ✅

### Checklist

#### 4.1 Orchestrator Class

- [ ] `core/orchestrator.py` oluşturuldu
- [ ] DI constructor (event_bus, state, persistence, executor, config)
- [ ] `run()` metodu
- [ ] `_initialize()` metodu
- [ ] `_execute_stages()` metodu
- [ ] `_finalize()` metodu

#### 4.2 **main**.py Refactoring

- [ ] Logic Orchestrator'a taşındı
- [ ] ~50 satıra indirildi
- [ ] `build_orchestrator()` factory

#### 4.3 Error Handling

- [ ] Plugin error → Job fail değil, skip
- [ ] Stage error → Sonraki stage devam
- [ ] Run error → Sadece critical durumda

#### 4.4 Event Flow

- [ ] `run.started` emit
- [ ] `job.created` emit
- [ ] `plugin.completed` emit
- [ ] `job.completed` emit
- [ ] `run.completed` emit

#### 4.5 Test

- [ ] Orchestrator unit testi PASS
- [ ] Full cycle integration testi PASS
- [ ] Error handling testi PASS

#### 4.6 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase4`

---

## 🟠 PHASE 5: STAGE EXECUTOR (4 Stage)

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `05_PHASE5_STAGE_EXECUTOR.md` (oluşturulacak)

**Ön Koşul:** Phase 4 tamamlanmış olmalı ✅

### Checklist

#### 5.1 Stage Tanımları

- [ ] STAGES = ['input', 'parse', 'data', 'output']
- [ ] Stage enum oluşturuldu
- [ ] category → stage migration

#### 5.2 StageExecutor

- [ ] `execute_stage(stage)` metodu
- [ ] `get_plugins_by_stage(stage)` metodu
- [ ] `topological_sort_by_requires()` metodu

#### 5.3 Execution Modes

- [ ] per_run execution (input stage)
- [ ] per_job execution (parse, data, output)
- [ ] Mixed mode (output stage)

#### 5.4 Parallel Execution

- [ ] Stage içi paralel execution
- [ ] Requires satisfaction kontrolü
- [ ] asyncio.gather kullanımı

#### 5.5 Test

- [ ] 4 stage sıralı execution testi
- [ ] Parallel execution testi
- [ ] Requires validation testi

#### 5.6 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase5`

---

## 🟡 PHASE 6: CONFIG & MANIFEST

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `06_PHASE6_CONFIG_MANIFEST.md` (oluşturulacak)

**Ön Koşul:** Phase 3, 5 tamamlanmış olmalı ✅

### Checklist

#### 6.1 Config Değişiklikleri

- [ ] FlexGet style (plugin = top-level key)
- [ ] `plugins:` wrapper kaldırıldı
- [ ] `aliases:` top-level eklendi
- [ ] `!include` directive çalışıyor

#### 6.2 Manifest Değişiklikleri

- [ ] `category` → `stage`
- [ ] `depends_on` → `requires`
- [ ] `expects` → `requires` (explicit prefix)
- [ ] `provides` eklendi
- [ ] `trigger_rule` eklendi

#### 6.3 Validation

- [ ] Schema güncellemesi
- [ ] Startup validation
- [ ] Config validator güncellendi

#### 6.4 Test

- [ ] Config loading testi
- [ ] Manifest parsing testi
- [ ] Validation testi

#### 6.5 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase6`

---

## 🟡 PHASE 7: VALIDATION SYSTEM

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `07_PHASE7_VALIDATION.md` (oluşturulacak)

**Ön Koşul:** Phase 1-6 tamamlanmış olmalı ✅

### Checklist

#### 7.1 Startup Validation

- [ ] Config schema validation
- [ ] Plugin manifest validation
- [ ] Dependency conflict detection
- [ ] Provides conflict detection

#### 7.2 Pre-execution Validation

- [ ] Requires path validation
- [ ] Trigger rule validation
- [ ] Stage assignment validation

#### 7.3 Error Codes

- [ ] E001-E021 error codes tanımlandı
- [ ] W001-W003 warning codes tanımlandı
- [ ] Error messages lokalize edildi

#### 7.4 Test

- [ ] Startup validation testi
- [ ] Pre-execution validation testi
- [ ] Error code testi

#### 7.5 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase7`

---

## 🟡 PHASE 8: FASTAPI REFACTORING

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `08_PHASE8_FASTAPI.md` (oluşturulacak)

**Ön Koşul:** Phase 1, 2, 7 tamamlanmış olmalı ✅

### Checklist

#### 8.1 Endpoint Değişiklikleri

- [ ] `/executions` → `/runs`
- [ ] `/matches` → `/jobs`
- [ ] `/plugins` endpoint eklendi
- [ ] `/config` endpoint eklendi

#### 8.2 Router Yapısı

- [ ] `api/v1/runs/` oluşturuldu
- [ ] `api/v1/jobs/` oluşturuldu
- [ ] `api/v1/plugins/` oluşturuldu
- [ ] `api/v1/config/` oluşturuldu

#### 8.3 Pydantic Schemas

- [ ] RunResponse, RunStatus, RunConfig
- [ ] JobResponse, InputData, OutputData
- [ ] PluginResponse, PluginStatus
- [ ] Pagination schemas

#### 8.4 Backward Compatibility

- [ ] `/executions` → `/runs` redirect
- [ ] `/matches` → `/jobs` redirect
- [ ] DEPRECATED warning header

#### 8.5 Test

- [ ] Endpoint testleri PASS
- [ ] Schema validation testi
- [ ] Backward compat testi

#### 8.6 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase8`

---

## 🟢 PHASE 9: MEMORY MANAGEMENT

**Durum:** ⬜ Başlanmadı | ⏳ Devam Ediyor | ✅ Tamamlandı

**Kaynak:** `09_PHASE9_MEMORY.md` (oluşturulacak)

**Ön Koşul:** Phase 2, 8 tamamlanmış olmalı ✅

### Checklist

#### 9.1 Hot/Cold Tiering

- [ ] Hot tier: Aktif run plugin data
- [ ] Cold tier: Tamamlanmış run data
- [ ] Tier geçiş logic'i

#### 9.2 Eviction Policy

- [ ] `completed_first` policy
- [ ] Memory threshold tanımı
- [ ] Eviction trigger'ları

#### 9.3 plugins Collection Optimization

- [ ] Lazy loading
- [ ] Batch loading
- [ ] Cache invalidation

#### 9.4 Test

- [ ] Memory eviction testi
- [ ] Tier geçiş testi
- [ ] Performance benchmark

#### 9.5 Commit

- [ ] Git commit yapıldı
- [ ] Git tag oluşturuldu: `v0.x.x-phase9`

---

## 📊 ÖZET DURUM

| Phase                 | Durum | İlerleme |
| --------------------- | ----- | -------- |
| P1: State Models      | ⬜    | 0%       |
| P2: MongoDB           | ⬜    | 0%       |
| P3: Plugin Services   | ⬜    | 0%       |
| P4: Orchestrator      | ⬜    | 0%       |
| P5: Stage Executor    | ⬜    | 0%       |
| P6: Config & Manifest | ⬜    | 0%       |
| P7: Validation        | ⬜    | 0%       |
| P8: FastAPI           | ⬜    | 0%       |
| P9: Memory            | ⬜    | 0%       |

**Genel İlerleme:** 0/9 phase tamamlandı (0%)

---

## 📝 NOTLAR

### Session Log

| Tarih      | Session | Yapılan                  | Sonraki    |
| ---------- | ------- | ------------------------ | ---------- |
| 2025-12-04 | 1       | TODO sistemi oluşturuldu | P1'e başla |

### Önemli Kararlar

| Karar | Gerekçe | Tarih |
| ----- | ------- | ----- |
| -     | -       | -     |

### Blokajlar

| Sorun | Çözüm | Durum |
| ----- | ----- | ----- |
| -     | -     | -     |

---

**Son güncelleme:** 2025-12-04
