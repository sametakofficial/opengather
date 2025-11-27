# TODO - Kalan Görevler

> **Son Güncelleme**: 2025-11-27 17:30 UTC+3  
> **Öncelik**: 🔴 Kritik | 🟠 Yüksek | 🟡 Orta | 🟢 Düşük  
> **Durum**: ⚠️ KRİTİK SORUN: Motor Deprecated

---

## 🚨 ACİL - MOTOR DEPRECATED

**MongoDB Resmi Duyurusu**:
- Motor Mayıs 2025'te deprecated ilan edildi
- Mayıs 2026: Aktif geliştirme sonu
- Mayıs 2027: TAM DESTEK SONU

**Kaynak**: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/

---

## 📊 GENEL BAKIŞ - SİSTEM KRİTİK SORUNLARI

| # | Sorun | Durum | Çözüm |
|---|-------|-------|-------|
| 1 | **Motor deprecated** | 🔴 KRİTİK | Motor → PyMongo `AsyncMongoClient` migration |
| 2 | State Manager singleton | ⚠️ Anti-pattern | DI + async refactor |
| 3 | Long-running jobs | ❌ Subprocess | ARQ/Celery task queue |
| 4 | Horizontal scaling | ❌ Yok | Task queue + workers |
| 5 | Real-time progress | ❌ Yok | WebSocket/SSE |
| 6 | Plugin-agnostic ihlali | ⚠️ Kısmi | state/manager.py düzelt |

**TEST DURUMU**: 203 test PASSED ✅

**Detaylı eleştiri**: `05_CRITICAL_REVIEW.md`

---

## ✅ TAMAMLANDI - Persistence Birleştirme

### 1. Repository Pattern Implementasyonu
**Durum**: ✅ TAMAMLANDI  
**Tarih**: 2025-11-27

**Çözüm**:
- Yeni `PyMongoPersistence` class oluşturuldu (pure sync PyMongo)
- Eski `MongoDBPersistence` deprecated olarak işaretlendi
- Event loop sorunu çözüldü (`run_until_complete` artık kullanılmıyor)

**Oluşturulan Dosyalar**:
- [x] `infrastructure/database/pymongo_persistence.py` - 262 satır
- [x] `tests/unit/infrastructure/test_pymongo_persistence.py` - 16 test

**Güncellenen Dosyalar**:
- [x] `infrastructure/database/__init__.py` - PyMongoPersistence export
- [x] `infrastructure/database/connection.py` - PyMongoPersistence kullanıyor
- [x] `infrastructure/database/mongodb.py` - DeprecationWarning eklendi

---

### 2. GlobalStateManager Async Dönüşümü
**Durum**: ✅ GEREKMEZ  
**Tarih**: 2025-11-27

**Analiz Sonucu**:
- GlobalStateManager SADECE CLI'dan çağrılıyor (`__main__.py`)
- API subprocess kullanıyor - GlobalStateManager'ı doğrudan çağırmıyor
- PyMongoPersistence pure sync - event loop sorunu yok

**Karar**: Async dönüşüm GEREKLİ DEĞİL çünkü mevcut mimari doğru çalışıyor.

---

### 3. Test Refactor - Plugin-Agnostic
**Durum**: ✅ TAMAMLANDI  
**Tarih**: 2025-11-27

**Oluşturulan Dosyalar**:
- [x] `tests/unit/core/test_plugin_agnostic.py` - 12 test

**Eklenen Fixtures** (`tests/conftest.py`):
- [x] `mock_input_plugin` - Generic input plugin
- [x] `mock_output_plugin` - Generic output plugin
- [x] `mock_plugin_config` - Plugin-agnostic config
- [x] `mock_plugin_metadata` - Mock plugin.json metadata
- [x] `mock_match_data` - Plugin-agnostic match data

**Test Kategorileri**:
```
TestPluginAgnosticExecution      # State manager with mock plugins
TestPluginAgnosticConfiguration  # Config validation
TestPluginAgnosticMetadata       # Plugin metadata
TestPluginAgnosticDiscovery      # DependencyResolver
TestNoHardcodedPluginNames       # Enforces no real plugin names
```

---

### 4. API Response Format Birleştirme
**Durum**: ✅ TAMAMLANDI  
**Tarih**: 2025-11-27

**Yapılan Değişiklikler**:
- [x] `models/response_builder.py` - Hardcoded plugin names kaldırıldı
- [x] Plugin kategorisi artık manifest'ten alınıyor (hardcoded `['scanner', 'file-reader']` yerine)
- [x] snake_case tutarlılığı sağlandı

---

### 5. eval() Güvenlik Açığı
**Durum**: ✅ ZATEN DÜZGÜN  
**Tarih**: 2025-11-27

**Analiz Sonucu**:
ffprobe plugin'inde `parse_fps()` fonksiyonu zaten güvenli şekilde implemente edilmiş.
eval() kullanılmıyor - regex ile parsing yapılıyor.

---

## 🟡 ORTA - Kod Kalitesi (BEKLEMEDE)

### 6. Dependency Injection Tekrarını Azalt
**Durum**: ⚠️ Bekliyor  
**Öncelik**: 🟡 Orta  
**Tahmini Süre**: 1 gün

**Problem**: Her router'da aynı dependency tanımı tekrarlanıyor.
**Çözüm**: `Annotated` ile common dependencies pattern.

---

### 7. pyproject.toml Oluştur
**Durum**: ❌ Bekliyor  
**Öncelik**: � Düşük  
**Tahmini Süre**: 0.5 gün

Eski `setup.py` yerine modern `pyproject.toml` (PEP 621) oluşturulmalı.

---

## 🟢 DÜŞÜK - İyileştirmeler (Sonra)

- Pydantic Schema kullanımı (response_model)
- Async Test Client
- Module-Level Exceptions
- Type Hints

---

## ⏸️ BEKLEMEDE - Plugin Sistemi

> Plugin sistemi refactoru çok uzun sürecek. Core sistem stabil, bu sonra yapılabilir.

---

## 📋 GÜNCEL CHECKLIST

### 🔴 KRİTİK - Motor Migration (Hemen Yapılmalı)
- [ ] PyMongo 4.10+ yükle (`pip install 'pymongo>=4.10'`)
- [ ] `motor` requirements.txt'ten kaldır
- [ ] `infrastructure/database/motor.py` → `async_client.py` yeniden yaz
- [ ] `AsyncIOMotorClient` → `AsyncMongoClient` değiştir
- [ ] `AsyncIOMotorDatabase` → `AsyncDatabase` değiştir
- [ ] API testlerini güncelle
- [ ] Performance benchmark yap (Motor vs PyMongo Async)

### 🟠 YÜKSEK - State Manager Refactor
- [ ] Singleton pattern kaldır
- [ ] Dependency Injection kullan
- [ ] `_get_match_category()` plugin-agnostic yap
- [ ] Async metodlar ekle (opsiyonel)

### 🟡 ORTA - Long-running Jobs (Gelecek)
- [ ] ARQ veya Celery entegrasyonu araştır
- [ ] Redis bağımlılığı ekle
- [ ] Background worker implementasyonu
- [ ] WebSocket progress endpoint

### ✅ TAMAMLANDI (2025-11-27)
- [x] Repository Pattern - PyMongoPersistence
- [x] Test fixtures (mock plugins)
- [x] Response format standardizasyonu
- [x] Kritik inceleme raporu (`05_CRITICAL_REVIEW.md`)

---

## 🔗 İLGİLİ DOKÜMANLAR

- `AI/00_CURRENT_STATUS.md` - Mevcut durum özeti
- `AI/01_CHANGELOG.md` - Değişiklik günlüğü
- `AI/03_ARCHITECTURE.md` - Mimari referans
- `AI/04_INDUSTRY_STANDARDS_ANALYSIS.md` - Endüstri araştırması
