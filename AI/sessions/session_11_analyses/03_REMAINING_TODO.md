# SESSION 11: KALAN İŞLER VE İYİLEŞTİRMELER

```yaml
tarih: 2025-12-04
öncelik_skalası: P0 (kritik) → P3 (düşük)
```

---

## ✅ TAMAMLANAN İŞLER (Bu Oturumda)

### 1. Config Alias Sistemi ✅
- [x] `alias_resolver.py`: `config`, `provides`, `events` SYSTEM_ALIASES'a eklendi
- [x] `alias_resolver.py`: `c` short alias eklendi
- [x] `template_manager.py`: `_config` field eklendi
- [x] `template_manager.py`: `config` jinja_context'e inject edildi
- [x] `template_manager.py`: `c` DEFAULT_ALIASES'a eklendi
- [x] `task_manager.py`: Config TemplateManager'a geçiriliyor

**Test Sonucu:**
```python
{{ config.ffprobe.timeout }}  → 15  ✅
{{ config.tmdb.language }}    → tr-TR  ✅
{{ c.ffprobe.timeout }}       → 15  ✅
```

---

## P0: KRİTİK (Fonksiyonel Sorunlar)

### Şu an kritik sorun YOK ✅

---

## P1: YÜKSEK (Strateji Uyumsuzlukları)

### 1.1 Renamer Provides Düzeltmesi ✅ TAMAMLANDI
**Dosya:** `plugins/renamer/manifest.yml`
```yaml
# Güncellendi
provides:
  - state.update    # ✅ Standart
```

**Durum:** ✅ Düzeltildi (2025-12-04)

---

### 1.2 provides/events Alias Inject
**Dosyalar:** `template_manager.py`, `alias_resolver.py`

**Sorun:** `provides` ve `events` alias'ları henüz template context'e inject edilmiyor

**Eylem:**
```python
# template_manager.py render() metoduna ekle:
jinja_context = {
    ...
    'config': self._config,
    'provides': {},  # ProvideRegistry'den doldurulmalı
    'events': {},    # EventBus history'den doldurulmalı
}
```

**Not:** Bu özellik runtime'da provides ve events bilgisine ihtiyaç duyar. Şu an template rendering sırasında bu bilgi mevcut değil.

---

## P2: ORTA (İyileştirmeler)

### 2.1 TemplateManager - AliasResolver Entegrasyonu
**Sorun:** İki ayrı alias sistemi var:
1. `core/config/alias_resolver.py` - SYSTEM_ALIASES, SHORT_ALIASES
2. `core/tasks/template_manager.py` - DEFAULT_ALIASES

**Eylem:** İkisini birleştir, tek kaynak oluştur

---

### 2.2 Legacy Kod Temizliği

#### 2.2.1 ExecutionService (19KB)
**Dosya:** `core/services/execution_service.py`
- Eski execution logic içeriyor
- Yeni Orchestrator ile değiştirildi
- Güvenle kaldırılabilir (API bağımlılığı kontrol edilmeli)

#### 2.2.2 Legacy Aliases (state/models.py)
```python
# Satır 292-311 - Kaldırılabilir
class ExecutionStatus(Enum):
    """Legacy: Use StateEnum instead."""
    ...

MatchState = JobState

class ExecutionState:
    """Legacy: Use RunState instead."""
    ...
```

---

### 2.3 Failing Tests Düzeltmesi
**Mevcut:** 13 failing test (ordering/sorting ile ilgili)

```
FAILED tests/unit/core/test_orchestrator.py::TestOrchestrator::test_run_success
FAILED tests/unit/core/test_orchestrator.py::TestOrchestrator::test_run_emits_events
...
```

**Eylem:** Test assertion'larını incele, sorting logic'i düzelt

---

## P3: DÜŞÜK (Gelecek İyileştirmeler)

### 3.1 Plugin Signature Standardizasyonu
**Strateji:**
```python
# per_job mode
def execute(self, job: JobState, services: PluginServices) -> PluginResult:

# per_run mode
def execute_run(self, services: PluginServices) -> PluginResult:
```

**Mevcut:** Bazı plugin'ler hala eski signature kullanıyor olabilir

**Eylem:** Tüm plugin'leri audit et, yeni signature'a geçir

---

### 3.2 Error Codes Dokümantasyonu
**Mevcut:** `validation/error_codes.py` E001-E023 tanımlı
**Eksik:** Tüm kodların açıklaması dokümante edilmemiş

**Eylem:** Error codes için dokümantasyon oluştur

---

### 3.3 Performance Benchmark'ları
**Strateji:** Memory management için hedef metrikler tanımlı değil
**Eylem:** Benchmark testleri ekle:
- 1000+ dosya senaryosu
- Memory usage tracking
- Plugin data cache hit/miss oranları

---

## ÖZET PRİORİTE TABLOSU

| Öncelik | Konu | Tahmini Süre | Durum |
|---------|------|--------------|-------|
| P1 | Renamer provides düzeltmesi | 5 dk | ✅ |
| P1 | TMDb provides güncelleme | 5 dk | ✅ |
| P1 | provides/events alias | 30 dk | 📋 |
| P2 | Template-Alias entegrasyonu | 1 saat | 📋 |
| P2 | Legacy kod temizliği | 2 saat | 📋 |
| P2 | Failing tests düzeltmesi | 2 saat | 📋 |
| P3 | Plugin signature audit | 1 saat | 📋 |
| P3 | Error codes dokümantasyonu | 30 dk | 📋 |
| P3 | Performance benchmarks | 2 saat | 📋 |

**Toplam Kalan İş: ~9 saat**

---

## SONRAKI ADIMLAR

1. **Hemen Yapılacak (P1):**
   - Renamer provides düzeltmesi
   - provides/events alias inject (opsiyonel, runtime bilgi gerekli)

2. **Bu Hafta (P2):**
   - Template-Alias entegrasyonu
   - Legacy kod temizliği
   - Failing tests düzeltmesi

3. **Gelecek Sprint (P3):**
   - Plugin signature audit
   - Error codes dokümantasyonu
   - Performance benchmarks

---

**Son Güncelleme:** 2025-12-04
