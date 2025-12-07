# SESSION 11 - COMPREHENSIVE REFACTORING PLAN
## Gerçek Eksikliklerin Detaylı Analizi ve İyileştirme Planı

```yaml
tarih: 2025-12-04 23:32
durum: COMPREHENSIVE_ANALYSIS
önceki_ai: Yüzeysel çalıştı, kritik özellikleri atladı
bu_plan: Sistemdeki gerçek sorunları tespit et ve düzelt
```

---

## 1. MEVCUT DURUM ANALİZİ (Test Sonuçları)

### ✅ ÇALIŞAN ÖZELLIKLER
```
✓ 4-stage pipeline çalışıyor
✓ Plugin registry ve discovery
✓ Parallel execution (DATA stage)
✓ Debug system
✓ Event bus
✓ Jinja2 template rendering
✓ User aliases (m, p, s, video) - ÇALIŞIYOR
✓ config alias - ÇALIŞIYOR! ({{ config.ffprobe.timeout }} = 15)
✓ ProvidesRegistry - KOD VAR
✓ RequiresValidator - KOD VAR
✓ Conflict detection - KOD VAR (ama runtime'da kullanılmıyor)
```

### ❌ KRİTİK SORUNLAR
```
1. Requires validation uyarıları:
   - Plugin 'tmdb' requires 'job.plugins.renamer.parsed' but it's not provided
   - Plugin 'tasker' requires 'provides.state.update' but it's not provided
   
   NEDEN: provides registry register ediliyor ama completion tracking yok
   NEDEN: requires validator çalışıyor ama "not provided" uyarısı yanlış mantık

2. Provides completion tracking eksik
   - services.provides.complete("http.request") çağrılmıyor
   - Plugin execution sonunda complete_all çağrılmıyor
   
3. trigger_rule full implementation yok
   - Sadece all_success implement
   - one_success, all_done, all_fail, none_fail eksik

4. Lockable provides conflict detection runtime'da kullanılmıyor
   - detect_conflicts() var ama sadece kod seviyesinde
   - Startup validation'da çağrılmıyor

5. !include directive test edilmedi
   - config_loader.py'de PyYAML custom constructor var mı?
   
6. External task sistemi hala var (KALDIRILMALI)
   - config.yml line 136-142: external: true
   - Bu pattern kaldırılıp !include ile değiştirilmeli

7. provides ve events aliases template'e inject edilmiyor
   - TemplateManager'da kod var (_get_provides_dict, _get_events_dict)
   - Ama stage_executor'da template_manager'a provides_registry inject edilmiyor

8. Manifest içinde Jinja2 kullanımı yok
   - requires: {{ alias.x }} çalışmıyor
   - manifest_normalizer.py'de Jinja2 render yok

9. Default config values eksik
   - Manifest'te config_schema.default değerleri merge edilmiyor
   - Plugin config boşsa default'lar otomatik inject edilmeli
```

---

## 2. YAMA KODLARI TESPİTİ (Workarounds)

### 🔴 TESPİT EDİLEN YAMALAR

#### 1. requires_validator.py - Incomplete Validation
```python
# LINE 136: Job path validation eksik
# Sadece plugin_data dict'e bakıyor, gerçek state'e bakmıyor
if prefix == 'job':
    return self._check_job_path(job, parts[1:], plugin_data)
    # ^^^ plugin_data cache'e bakıyor ama gerçek job.plugins'e bakmıyor

# FIX: job.plugins attribute'una da bakmalı
```

#### 2. stage_executor.py - Provides Completion Eksik
```python
# LINE ~500: Plugin execution sonrası provides complete edilmiyor
result = plugin.execute(job, services)
# ^^^ execute bittikten sonra services.provides.complete_all() çağrılmalı

# FIX: Her plugin başarıyla bittikten sonra tüm provides'ları complete et
if result.success:
    provides_registry.complete_all(plugin_name)
else:
    provides_registry.fail_all(plugin_name)
```

#### 3. stage_executor.py - Template Manager'a Registry Inject Edilmiyor
```python
# LINE ~100: Template manager oluşturulurken provides_registry verilmiyor
# template_manager = TemplateManager(config)
# ^^^ provides_registry ve event_bus parametreleri eksik

# FIX: Template manager'a registry'leri inject et
template_manager = TemplateManager(
    config=config,
    provides_registry=provides_registry,
    event_bus=event_bus
)
```

#### 4. plugin_registry.py - Manifest Default Config Merge Yok
```python
# Plugin config yüklenirken manifest.config_schema.default merge edilmiyor
# Örnek: ffprobe.timeout belirtilmezse manifest'teki default kullanılmalı

# FIX: config_schema.default değerlerini plugin config'e merge et
```

#### 5. config_loader.py - !include Directive Test Edilmedi
```python
# PyYAML custom constructor !include için var mı kontrol et
# Yoksa ekle

# FIX: !include_list ve !include_merge kaldırıldı (v2)
# Sadece !include kalsın (file veya dir)
```

---

## 3. İYİLEŞTİRME PLANI (Öncelik Sırasıyla)

### 🔴 P0 - KRİTİK (Bu Session'da Yapılacak)

#### P0.1: Provides Completion System (30 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/stage_executor.py

Değişiklikler:
1. Plugin execution sonrası provides completion
2. Success: provides_registry.complete_all(plugin_name)
3. Failure: provides_registry.fail_all(plugin_name)
4. Early completion desteği: services.provides.complete("http.request")

Test:
- provides.state.update completion
- tmdb provides: http.request, state.update
```

#### P0.2: Template Manager Registry Injection (20 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/stage_executor.py
- src/archiverr/core/tasks/template_manager.py

Değişiklikler:
1. TemplateManager init'e provides_registry inject
2. TemplateManager init'e event_bus inject
3. Template context'e provides alias ekleme
4. Template context'e events alias ekleme

Test:
- {{ provides.http.request.tmdb }} → "completed"
- {{ events.plugin.completed | length }}
```

#### P0.3: Requires Validation Fix (30 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/requires_validator.py
- src/archiverr/core/plugins/stage_executor.py

Değişiklikler:
1. _check_job_path: gerçek job.plugins attribute'una bak
2. _check_plugin_path: cache + job state merge
3. Validation sonrası doğru skip logic

Test:
- tmdb requires job.plugins.renamer.parsed → uyarı kalkmalı
- tasker requires provides.state.update → uyarı kalkmalı
```

#### P0.4: Startup Conflict Detection (15 dk)
```python
Dosyalar:
- src/archiverr/core/validation/__init__.py
- src/archiverr/core/orchestrator.py

Değişiklikler:
1. validate_at_startup: provides_registry.detect_conflicts()
2. Conflict varsa ValidationError ekle
3. Orchestrator'da conflict log

Test:
- İki plugin aynı path'e fs.write → conflict error
```

---

### 🟡 P1 - YÜKSEK ÖNCELİK (Bu Session'da Yapılabilir)

#### P1.1: trigger_rule Full Implementation (45 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/stage_executor.py
- src/archiverr/core/plugins/requires_validator.py

Yeni trigger_rule'lar:
- one_success: En az 1 require başarılı
- all_done: Tüm requires tamamlandı (fail olsa bile)
- all_fail: Tüm requires fail
- none_fail: Hiçbir require fail değil
- always: Requires'a bakmadan çalıştır

Test:
- tasker trigger_rule: all_done → data plugin fail olsa da çalışmalı
```

#### P1.2: Manifest Config Schema Default Merge (30 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/loader.py
- src/archiverr/core/plugins/manifest_normalizer.py

Değişiklikler:
1. manifest.config_schema.default al
2. Plugin config'e merge et (user > default)
3. required field validation

Test:
- ffprobe timeout belirtilmezse manifest default kullanılmalı
```

#### P1.3: !include Directive Implementation (45 dk)
```python
Dosyalar:
- src/archiverr/utils/yaml_loader.py
- src/archiverr/utils/config_loader.py

Değişiklikler:
1. PyYAML custom constructor: !include
2. File load: !include ./tasks/common.yml
3. Dir load: !include ./tasks/ → merge all .yml
4. Circular include detection

Test:
- tasker.tasks: !include ./tasks/ → load all tasks
```

#### P1.4: External Task System Removal (20 dk)
```python
Dosyalar:
- config.yml (remove external: true)
- src/archiverr/core/tasks/task_manager.py (external logic kaldır)

Değişiklikler:
1. config.yml: external: true → sil
2. TaskManager: external task logic kaldır
3. Docs: !include kullanımını göster

Test:
- config.yml external tasks yerine !include
```

---

### 🟢 P2 - ORTA ÖNCELİK (Sonraki Session)

#### P2.1: Manifest içinde Jinja2 (60 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/manifest_normalizer.py

Değişiklikler:
1. Manifest load sonrası Jinja2 render
2. requires: {{ alias.renamer_parsed }} support
3. Context: config, system aliases

Test:
- manifest.yml: requires: {{ config.parser_plugin }}.parsed
```

#### P2.2: Reactive Plugin System (90 dk)
```python
Dosyalar:
- src/archiverr/core/plugins/stage_executor.py
- src/archiverr/core/orchestrator.py

Değişiklikler:
1. reactive: true manifest field
2. State değişiminde plugin re-trigger
3. per_run + reactive kombinasyonu

Test:
- summary plugin: reactive=true, re-run on job complete
```

#### P2.3: state.update Non-Lockable Enforcement (30 dk)
```python
Dosyalar:
- src/archiverr/core/provides_registry.py

Değişiklikler:
1. state.update NON_LOCKABLE'da zaten var
2. Conflict detection'da ignore et
3. Test coverage

Test:
- renamer + tmdb: her ikisi state.update → no conflict
```

---

### ⚪ P3 - DÜŞÜK ÖNCELİK (Uzun Vadeli)

#### P3.1: Memory Management (Hot/Cold Tiering)
```python
Dosyalar:
- src/archiverr/core/memory/manager.py

Değişiklikler:
1. Plugin data eviction policy
2. Hot: RAM, Cold: MongoDB
3. Lazy load on access
```

#### P3.2: PyMongo Real Backend Test
```python
Test MongoDB connection
Plugin data lazy loading
Memory eviction triggers
```

---

## 4. UYGULAMA SIRASI (Bu Session)

```bash
Session 11 Refactoring - Execution Order:
├── 1. P0.1: Provides Completion System (30 dk)
├── 2. P0.2: Template Manager Registry Injection (20 dk)
├── 3. P0.3: Requires Validation Fix (30 dk)
├── 4. P0.4: Startup Conflict Detection (15 dk)
├── 5. P1.1: trigger_rule Full Implementation (45 dk)
├── 6. P1.2: Manifest Config Schema Default Merge (30 dk)
├── 7. P1.3: !include Directive Implementation (45 dk)
├── 8. P1.4: External Task System Removal (20 dk)
└── TOTAL: ~4 saat (1 session)
```

---

## 5. TEST PLAN

### Her Değişiklik Sonrası Test
```bash
# Quick test
PYTHONPATH=src ARCHIVERR_DB_BACKEND=mock python -m archiverr

# Expected output:
# - No "not provided" warnings
# - provides.state.update completed
# - job.plugins.renamer.parsed satisfied
# - 4 stages complete
# - Exit code: 0
```

### Test Checklist
```
□ provides.state.update: tmdb, renamer complete
□ provides.http.request: tmdb complete  
□ requires warnings yok
□ trigger_rule: all_done için tasker çalışıyor
□ config.ffprobe.timeout template'de render oluyor
□ {{ provides.http.request.tmdb }} = "completed"
□ Conflict detection startup'ta çalışıyor
□ !include directive çalışıyor
□ External task system kaldırıldı
```

---

## 6. KESİN OLMAYAN/BELİRSİZ ALANLAR

### Araştırılacak
1. **JobState.plugins attribute var mı?**
   - RequiresValidator job.plugins'e bakıyor
   - Ama JobState'de plugins dict attribute var mı kontrol et

2. **Event bus has_fired() method var mı?**
   - RequiresValidator events.* için has_fired çağırıyor
   - EventBus'ta bu method implement edilmiş mi?

3. **Manifest config_schema format nedir?**
   - Hangi format? JSON Schema? Custom?
   - Default merge mantığı nasıl olmalı?

---

## 7. SONUÇ

Bu plan, önceki AI'ların yüzeysel çalışmasının aksine **gerçek sorunları** tespit ediyor:

1. ✅ Sistem çalışıyor - ama **eksik özelliklerle**
2. ❌ Provides completion **hiç çağrılmıyor**
3. ❌ Requires validation **yanlış implement**
4. ❌ Conflict detection **runtime'da kullanılmıyor**
5. ❌ trigger_rule **sadece all_success var**
6. ❌ !include **test edilmedi**
7. ❌ External task **hala var** (kaldırılmalı)

**Hedef:** Bu plana göre sistematik düzeltme yaparak **gerçek Session 11 vizyonuna** ulaşmak.

---

**Başlangıç:** 2025-12-04 23:32
**Tahmini Süre:** 4 saat (P0 + P1)
**Sonraki Session:** P2 özellikleri
