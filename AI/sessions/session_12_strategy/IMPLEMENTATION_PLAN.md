# SESSION 12 IMPLEMENTATION PLAN

```yaml
tarih: 2024-12-08 01:15
durum: IMPLEMENTATION_READY
faz: refactoring
hedef: Session 12'ye geçiş
```

---

## 📋 MEVCUT DURUM ANALİZİ

### Çalışan Sistem ✅
```bash
source .venv/bin/activate
python -m archiverr --help  # ✅ Çalışıyor
```

### Mevcut Yapı (Session 11)
```
src/archiverr/
├── core/
│   ├── orchestrator.py          # 4 stage (INPUT, PARSE, DATA, OUTPUT)
│   ├── plugins/
│   │   ├── registry.py          # Stage-based registry
│   │   ├── discovery.py
│   │   ├── loader.py
│   │   └── stage_executor.py
│   ├── provides_registry.py     # ❌ Kaldırılacak
│   └── services/                # Plugin services
├── state/
│   ├── manager.py               # StateManager (RunState, JobState)
│   └── models.py                # State models
├── events/
│   └── bus.py                   # EventBus
└── __main__.py                  # CLI entry point
```

---

## 🎯 SESSION 12 HEDEF YAPI

### Global State (6 Obje)
```python
class GlobalStateManager:
    # Read-only for all
    run: RunState              # Run metadata
    config: Dict[str, Any]     # Frozen config
    
    # per_job only (read-write)
    job: JobState              # Current job
    jobs: List[JobState]       # All jobs
    plugin: Dict[str, Any]     # Current job plugins
    plugins: List[Dict]        # All job plugins
```

### Plugin Services (3 Method)
```python
class PluginServices:
    def createJob(self, input_value: str, input_data: Dict) -> str:
        """Both per_run and per_job"""
    
    def updateJob(self, key: str, value: Any) -> None:
        """per_job only, ID yok"""
    
    def updatePlugin(self, data: Dict) -> None:
        """per_job only, Name yok"""
```

### Stage System (3 Stage)
```python
class Stage(Enum):
    # ❌ INPUT = "input"  # Kaldırıldı
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"
```

### Plugin Data Structure
```python
{
    "plugin": {
        "tmdb": {
            "status": {...},
            "data": {           # 🔴 HER ŞEY data içinde
                "movie": {...}
            }
        }
    }
}
```

---

## 📅 IMPLEMENTATION FAZLARI

### PHASE 1: Core State Refactoring (Öncelik 1)
**Hedef**: 6 global state + plugin.data yapısı

**Dosyalar**:
- `src/archiverr/state/manager.py`
- `src/archiverr/state/models.py`

**Değişiklikler**:
1. ✅ StateManager → GlobalStateManager rename
2. ✅ 6 property ekle (run, config, job, jobs, plugin, plugins)
3. ✅ Plugin data structure: plugin.{name}.data.*
4. ✅ update_job(job_id, key, value) internal method
5. ✅ update_plugin(job_id, plugin_name, data) internal method

**Test**:
```bash
python -m pytest tests/state/test_global_state_manager.py -v
```

---

### PHASE 2: Plugin Services Refactoring (Öncelik 1)
**Hedef**: 3 method + current context

**Dosyalar**:
- `src/archiverr/core/services/plugin_services.py` (yeni)
- `src/archiverr/core/plugins/base.py`

**Değişiklikler**:
1. ✅ PluginServices class oluştur
2. ✅ createJob(input_value, input_data) -> str
3. ✅ updateJob(key, value) - ID yok
4. ✅ updatePlugin(data) - Name yok
5. ✅ Current job/plugin context internal
6. ✅ Access control (per_run vs per_job)

**Test**:
```bash
python -m pytest tests/services/test_plugin_services.py -v
```

---

### PHASE 3: Stage System Refactoring (Öncelik 2)
**Hedef**: 3 stage + INPUT kaldır

**Dosyalar**:
- `src/archiverr/core/plugins/registry.py`
- `src/archiverr/core/orchestrator.py`

**Değişiklikler**:
1. ✅ Stage.INPUT enum kaldır
2. ✅ STAGES = [Stage.PARSE, Stage.DATA, Stage.OUTPUT]
3. ✅ Input plugins → per_run mode
4. ✅ Orchestrator.STAGES güncelle
5. ✅ Stage executor güncelle

**Test**:
```bash
python -m pytest tests/core/test_orchestrator.py -v
```

---

### PHASE 4: Trigger Rule System (Öncelik 2)
**Hedef**: Plugin vs non-plugin validation

**Dosyalar**:
- `src/archiverr/core/triggers/` (yeni)
  - `manager.py`
  - `evaluator.py`
  - `matcher.py`

**Değişiklikler**:
1. ✅ TriggerRuleManager class
2. ✅ Plugin path validation (success/fail only for plugin.*)
3. ✅ Non-plugin exact value match
4. ✅ Value resolver
5. ✅ Rule evaluator

**Test**:
```bash
python -m pytest tests/triggers/test_trigger_rules.py -v
```

---

### PHASE 5: FS Lock System (Öncelik 3)
**Hedef**: Static path only validation

**Dosyalar**:
- `src/archiverr/core/locking/` (yeni)
  - `fs_lock_manager.py`
  - `validator.py`

**Değişiklikler**:
1. ✅ FSLockManager class
2. ✅ Startup validation (no variables)
3. ✅ Lock acquisition/release
4. ✅ Conflict detection

**Test**:
```bash
python -m pytest tests/locking/test_fs_lock.py -v
```

---

### PHASE 6: Provides Registry Removal (Öncelik 3)
**Hedef**: Provides/events kaldır

**Dosyalar**:
- `src/archiverr/core/provides_registry.py` (sil)
- Tüm plugin manifests (requires güncelle)

**Değişiklikler**:
1. ✅ provides_registry.py sil
2. ✅ requires: [provides.data] → requires: [plugin.data:success]
3. ✅ Config'den provides kaldır
4. ✅ Validation güncelle

---

### PHASE 7: Integration & Testing (Öncelik 4)
**Hedef**: Tüm sistemlerin entegrasyonu

**Test Senaryoları**:
1. Per-run plugin (scanner) job oluşturur
2. Job queue işlenir
3. Per-job plugins sırayla çalışır (parse → data → output)
4. Plugin data .data içinde saklanır
5. Trigger rules çalışır (plugin success check)
6. FS lock çalışır (static path only)
7. State düzgün persist edilir

**Integration Test**:
```bash
python -m pytest tests/integration/test_session_12_flow.py -v
```

---

## 🔧 IMPLEMENTATION SIRALAMA

### Week 1: Core Foundation
- [x] Day 1: GlobalStateManager refactoring
- [x] Day 2: PluginServices implementation
- [x] Day 3: Stage system refactoring
- [ ] Day 4: Testing & bug fixes

### Week 2: Advanced Features
- [ ] Day 5: TriggerRuleManager
- [ ] Day 6: FSLockManager
- [ ] Day 7: Provides registry removal

### Week 3: Integration
- [ ] Day 8-9: Integration testing
- [ ] Day 10: Performance testing
- [ ] Day 11-12: Bug fixes & optimization

---

## ⚠️ MIGRATION CHECKLIST

### Breaking Changes
- [ ] INPUT stage kaldırıldı → Scanner per_run olmalı
- [ ] provides.* paths kaldırıldı → plugin.*.data.* olmalı
- [ ] updateJob/updatePlugin ID kaldırıldı → Current context
- [ ] FS lock variables kaldırıldı → Static path only
- [ ] success/fail non-plugin için yasak → Validation error

### Backward Compatibility
- [ ] Old manifests migration script
- [ ] Old state migration
- [ ] API backward compat layer (gerekirse)

### Documentation
- [ ] README güncelle
- [ ] API docs güncelle
- [ ] Migration guide yaz
- [ ] Examples güncelle

---

## 🧪 TEST STRATEGY

### Unit Tests
```bash
# State
pytest tests/state/ -v

# Services
pytest tests/services/ -v

# Triggers
pytest tests/triggers/ -v

# Locking
pytest tests/locking/ -v
```

### Integration Tests
```bash
pytest tests/integration/ -v
```

### E2E Tests
```bash
# Real config test
python -m archiverr --config tests/fixtures/session_12_config.yml
```

---

## 📊 PROGRESS TRACKING

### Completed ✅
- [x] Strategy documents (11 files)
- [x] BRAINSTORM complete
- [x] FINAL_DATASETS.yml updated
- [x] All critical decisions finalized

### In Progress 🟡
- [ ] Phase 1: GlobalStateManager
- [ ] Phase 2: PluginServices
- [ ] Phase 3: Stage system

### Pending 🔴
- [ ] Phase 4: Trigger rules
- [ ] Phase 5: FS lock
- [ ] Phase 6: Provides removal
- [ ] Phase 7: Integration

---

**Status**: Implementation başlıyor
**Current**: Phase 1 - GlobalStateManager refactoring
**Next**: Core state models ve manager implementation
