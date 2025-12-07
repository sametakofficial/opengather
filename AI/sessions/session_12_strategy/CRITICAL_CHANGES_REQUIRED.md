# CRITICAL CHANGES REQUIRED

```yaml
tarih: 2024-12-08
durum: URGENT FIX
amaç: Tüm strategy dosyalarında yapılması gereken kritik değişiklikler
```

---

## 🔴 DEĞİŞTİRİLMESİ GEREKEN 4 KRİTİK NOKTA

### 1. PLUGIN DATA YAPISI

**YANLIŞ (tüm dosyalarda):**
```yaml
plugin.tmdb.movie
plugin.renamer.parsed
plugin.ffprobe.video
plugin.tasker.tasks
```

**DOĞRU:**
```yaml
plugin.tmdb.data.movie
plugin.renamer.data.parsed
plugin.ffprobe.data.video
plugin.tasker.data.tasks
```

**ETKİLENEN DOSYALAR:**
- 02_GLOBAL_STATE_ARCHITECTURE.md (çok yer)
- 03_PLUGIN_SYSTEM_REFACTORING.md (çok yer)
- 04_TRIGGER_RULE_SYSTEM.md (çok yer)
- 05_JOB_LIFECYCLE_AND_EXECUTION.md (birkaç yer)
- 07_IMPLEMENTATION_PATTERNS.md (birkaç yer)

---

### 2. TRIGGER RULE: FAIL/SUCCESS SADECE PLUGIN İÇİN

**YANLIŞ:**
```yaml
requires:
  - plugin.tmdb.movie.title:success  # OK
  - run.status:success               # ❌ YANLIŞ
  - job.output:success               # ❌ YANLIŞ
```

**DOĞRU:**
```yaml
requires:
  - plugin.tmdb.data.movie:success   # ✅ Plugin için OK
  - run.total_jobs:10                # ✅ Exact value
  - job.status.state:"completed"     # ✅ Exact value
```

**KURAL:**
- `:success` ve `:fail` SADECE `plugin.*` ve `plugins.*` için
- Diğer state'ler için SADECE exact value match (int/bool/string/object)
- Non-plugin için success/fail = VALIDATION ERROR

**ETKİLENEN DOSYALAR:**
- 01_EXECUTIVE_SUMMARY.md ✅ (güncellendi)
- 04_TRIGGER_RULE_SYSTEM.md (tüm döküman düzeltilmeli)
- FINAL_DATASETS.yml ✅ (güncellendi)

---

### 3. FS LOCK: SADECE STATİK PATH

**YANLIŞ:**
```yaml
fs_lock:
  - "{{config.archive_path}}"   # ❌ YASAK
  - "{{job.input.value}}"       # ❌ YASAK
```

**DOĞRU:**
```yaml
fs_lock:
  - /downloads/movies           # ✅ Static
  - /srv/archive                # ✅ Static
```

**KURAL:**
- HİÇBİR değişken kullanılamaz
- Config variable bile yasak
- Sadece hardcoded static path
- İhlal = Validation error at startup

**ETKİLENEN DOSYALAR:**
- 01_EXECUTIVE_SUMMARY.md ✅ (güncellendi)
- 05_JOB_LIFECYCLE_AND_EXECUTION.md (FS lock örnekleri)
- FINAL_DATASETS.yml ✅ (güncellendi)

---

### 4. UPDATE METHODS: ID YOK

**YANLIŞ:**
```python
services.updateJob(job_id="abc", key="output.values", value=[...])
services.updatePlugin(plugin_name="tmdb", data={...})
```

**DOĞRU:**
```python
services.updateJob(key="output.values", value=[...])
services.updatePlugin(data={...})
```

**SEBEP:**
- Current context internal'da tutuluyor
- ID gereksiz ve karışık
- Services her zaman current job/plugin ile çalışır

**ETKİLENEN DOSYALAR:**
- 02_GLOBAL_STATE_ARCHITECTURE.md (StateManager interface)
- 03_PLUGIN_SYSTEM_REFACTORING.md (PluginServices interface)
- 07_IMPLEMENTATION_PATTERNS.md (kod örnekleri)

---

## 📋 DOSYA BAZLI DEĞİŞİKLİK LİSTESİ

### ✅ TAMAMLANDI
- SESSION_12_BRAINSTORM.md
- FINAL_DATASETS.yml
- 01_EXECUTIVE_SUMMARY.md (çoğu)

### 🔴 ACİL DÜZELTME GEREKİYOR

#### 02_GLOBAL_STATE_ARCHITECTURE.md
- [ ] `plugin.{name}.{field}` → `plugin.{name}.data.{field}` (tüm örnekler)
- [ ] Plugin Data Structure bölümü düzelt
- [ ] Common Paths düzelt
- [ ] StateManager interface: updateJob/updatePlugin ID kaldır
- [ ] MongoDB storage: data field ekle

#### 03_PLUGIN_SYSTEM_REFACTORING.md
- [ ] `plugin.{name}.{field}` → `plugin.{name}.data.{field}` (tüm örnekler)
- [ ] updateJob/updatePlugin signature: ID kaldır
- [ ] PluginServices interface düzelt
- [ ] Plugin execution patterns: data field ekle
- [ ] Tüm kod örneklerini düzelt

#### 04_TRIGGER_RULE_SYSTEM.md
- [ ] **EN KRİTİK DOSYA** - Tüm dokümantasyon düzeltilmeli
- [ ] Fail/success sadece plugin için section ekle
- [ ] Non-plugin için exact value only
- [ ] Validation error examples ekle
- [ ] `plugin.{name}.{field}` → `plugin.{name}.data.{field}`
- [ ] TriggerRuleManager: plugin vs non-plugin ayrımı ekle
- [ ] Decision tree: plugin vs non-plugin

#### 05_JOB_LIFECYCLE_AND_EXECUTION.md
- [ ] `plugin.{name}.{field}` → `plugin.{name}.data.{field}` (birkaç yer)
- [ ] FS lock örnekleri: sadece static path
- [ ] Plugin update flow: data field ekle

#### 06_FILE_STRUCTURE_AND_MODULES.md
- [ ] PluginServices interface: updateJob/updatePlugin signature düzelt

#### 07_IMPLEMENTATION_PATTERNS.md
- [ ] `plugin.{name}.{field}` → `plugin.{name}.data.{field}` (birkaç yer)
- [ ] updateJob/updatePlugin örnekleri: ID kaldır
- [ ] Trigger rule evaluation: plugin vs non-plugin check ekle

---

## 🎯 ÖNCELİK SIRASI

### Priority 1 (Kritik)
1. **04_TRIGGER_RULE_SYSTEM.md** - En kritik, tüm dokümantasyon yanlış
2. **03_PLUGIN_SYSTEM_REFACTORING.md** - Plugin interface'leri yanlış
3. **02_GLOBAL_STATE_ARCHITECTURE.md** - State yapısı yanlış

### Priority 2 (Önemli)
4. **05_JOB_LIFECYCLE_AND_EXECUTION.md** - Execution örnekleri düzelt
5. **07_IMPLEMENTATION_PATTERNS.md** - Kod patterns düzelt

### Priority 3 (Az değişiklik)
6. **06_FILE_STRUCTURE_AND_MODULES.md** - Sadece interface signatures

---

## 🔍 GLOBAL SEARCH & REPLACE

### Plugin Data Paths
```bash
# Find all wrong paths
grep -r "plugin\.tmdb\.movie" AI/sessions/session_12_strategy/
grep -r "plugin\.renamer\.parsed" AI/sessions/session_12_strategy/
grep -r "plugin\.ffprobe\.video" AI/sessions/session_12_strategy/

# Replace pattern:
plugin.{name}.{field} → plugin.{name}.data.{field}
```

### Update Method Signatures
```bash
# Find signatures
grep -r "updateJob(job_id" AI/sessions/session_12_strategy/
grep -r "updatePlugin(plugin_name" AI/sessions/session_12_strategy/
```

### FS Lock Examples
```bash
# Find config variables in fs_lock
grep -r "{{config\." AI/sessions/session_12_strategy/ | grep fs_lock
```

---

## ✅ DOĞRULAMA CHECKLİSTİ

Tüm dosyalar düzeltildikten sonra:

- [ ] Hiçbir yerde `plugin.{name}.{field}` (data olmadan) yok
- [ ] Hiçbir yerde `updateJob(job_id,` yok
- [ ] Hiçbir yerde `updatePlugin(plugin_name,` yok
- [ ] Hiçbir yerde fs_lock içinde variable yok
- [ ] Non-plugin path için `:success` veya `:fail` yok
- [ ] Tüm plugin paths `plugin.{name}.data.*` formatında
- [ ] Tüm alias'lar `plugin.{name}.data.*` formatında

---

**Status**: Kritik değişiklikler belirlendi
**Next**: Dosyaları öncelik sırasına göre düzelt
