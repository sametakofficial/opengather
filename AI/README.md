# 🤖 AI Briefing - Archiverr

> **Bu klasörü oku ve kaldığım yerden devam et.**  
> **Son Güncelleme**: 2025-11-27 17:30 UTC+3  
> **Durum**: ⚠️ KRİTİK: Motor Deprecated - Migration Gerekli

---

## 🚀 HIZLI BAŞLANGIÇ

```bash
cd /home/samet/Workspace/archiverr

# Testleri çalıştır (203 test)
pytest tests/ -v

# Projeyi çalıştır
python -m archiverr

# API'yi başlat
uvicorn archiverr.api.main:app --reload
```

---

## 📂 Dosya Sırası (Bu Sırayla Oku)

| # | Dosya | İçerik |
|---|-------|--------|
| 1 | `00_CURRENT_STATUS.md` | Şu anki durum özeti |
| 2 | `02_TODO.md` | Yapılacaklar (çoğu tamamlandı!) |
| 3 | `03_ARCHITECTURE.md` | Mimari referans |
| 4 | `01_CHANGELOG.md` | Detaylı değişiklik günlüğü |

---

## 🚨 KRİTİK: MOTOR DEPRECATED (2025-11-27)

| Durum | Açıklama |
|-------|----------|
| ⚠️ **Motor deprecated** | Mayıs 2025'te deprecated, 2027'de destek bitiyor |
| ⚠️ **PyMongo Async API** | MongoDB resmi önerisi: `AsyncMongoClient` kullan |
| ⚠️ **Performans** | PyMongo Async, Motor'dan %20-140 daha hızlı |

**Kaynak**: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/

### Mevcut vs Doğru Mimari

```
MEVCUT (SORUNLU):           DOĞRU (ÖNERİLEN):
├─ API: Motor (async)       ├─ API: PyMongo AsyncMongoClient
├─ CLI: PyMongo (sync)      ├─ CLI: PyMongo MongoClient
│       ⚠️ Motor 2027'de    │       ✅ Tek kütüphane
│          destek bitecek   │       ✅ MongoDB desteği devam
```

### Yapılması Gerekenler
1. **Motor → PyMongo Async migration** (Öncelik: KRİTİK)
2. Detaylar: `05_CRITICAL_REVIEW.md`

**SKOR: 5.5/10** - Production-ready değil (detaylar: 05_CRITICAL_REVIEW.md)

---

## 🏗️ MİMARİ ÖZET (GÜNCELLENMELİ)

```
┌───────────────────────────────────────────────────────────┐
│  MEVCUT (Motor - DEPRECATED)     ÖNERİLEN (PyMongo)       │
│  ┌─────────────┐                ┌─────────────┐           │
│  │ Motor       │    ──────>     │ AsyncMongo  │           │
│  │ ⚠️ 2027     │                │ Client      │           │
│  └──────┬──────┘                └──────┬──────┘           │
│         │                              │                   │
│         ▼                              ▼                   │
│  ┌───────────────────────────────────────────────┐        │
│  │              MongoDB                           │        │
│  └───────────────────────────────────────────────┘        │
│                                                            │
│  ⚠️ Motor deprecated (Mayıs 2025)                         │
│  ⚠️ Migration gerekli: Motor → PyMongo AsyncMongoClient   │
│  📄 Detaylar: 05_CRITICAL_REVIEW.md                       │
└───────────────────────────────────────────────────────────┘
```

---

## 📊 KATMAN SKORLARI (GÜNCELLENDİ - Eleştiri Sonrası)

| Katman | Skor | Durum |
|--------|------|-------|
| API Layer | **5/10** | ⚠️ Motor deprecated (2027'de biter) |
| State Manager | **6/10** | ⚠️ Singleton anti-pattern |
| Persistence | **7/10** | ✅ PyMongoPersistence iyi |
| Tests | **7/10** | ✅ Plugin-agnostic ama coverage düşük |
| Long-running Jobs | **4/10** | ❌ Subprocess, scaling yok |
| **GENEL** | **5.5/10** | ⚠️ Production-ready değil |

**Detaylı analiz**: `05_CRITICAL_REVIEW.md`

---

## 🏗️ DOSYA YAPISI

```
src/archiverr/
├── api/                    # FastAPI API
│   ├── deps/               # Dependency Injection
│   │   ├── database.py     # Motor + PyMongo bağlantıları
│   │   └── common.py       # AsyncPersistenceWrapper
│   └── v1/                 # API endpoints
│
├── infrastructure/
│   └── database/
│       ├── pymongo_persistence.py  # ✅ YENİ - Pure sync (CLI için)
│       ├── motor.py                # Async (API için)
│       └── mongodb.py              # ⚠️ DEPRECATED
│
├── state/
│   └── manager.py          # GlobalStateManager (sync, CLI-only)
│
├── plugins/                # TÜM DOMAIN LOGIC BURADA
│
└── __main__.py             # CLI entry point
```

---

## 🔑 KRİTİK KURALLAR

### 1. Plugin-Agnostic Mimari
```python
# ❌ YASAK - Core kodda plugin adı kullanma
if plugin_name == "tmdb":
    ...

# ✅ DOĞRU - Generic pattern kullan
for plugin_name, plugin in plugins.items():
    result = plugin.execute(data)
```

### 2. Backward Compatibility
```python
# Eski import'lar çalışmalı (deprecation warning ile)
from archiverr.api.database import get_motor_db  # Deprecated
from archiverr.api.deps import get_database      # Yeni
```

### 3. Test First
```bash
# Her değişiklik sonrası
pytest tests/unit/ -v
```

---

## 🧪 TEST KOMUTLARI

```bash
cd /home/samet/Workspace/archiverr

# Unit testler (hızlı, plugin-agnostic)
pytest tests/unit/ -v

# Tüm testler
pytest tests/ -v

# Sadece API testleri
pytest tests/test_api.py -v

# Syntax check
find src -name "*.py" -exec python -m py_compile {} \;

# eval() kullanımı kontrolü (güvenlik)
grep -r "eval(" src/
```

---

## ⏸️ BEKLEMEDE (Düşük Öncelik)

- Plugin sistemi refactoru
- pyproject.toml oluşturma
- DI tekrarını azaltma
- Pydantic schema kullanımı

---

## 📚 REFERANSLAR

| Dosya | İçerik |
|-------|--------|
| `03_ARCHITECTURE.md` | Detaylı mimari referans |
| `04_INDUSTRY_STANDARDS_ANALYSIS.md` | Endüstri araştırması |
| `config.schema.json` | Config validation |

---

## ✅ SİSTEM DURUMU

```
203 test PASSED ✅
Sistem stabil
Kritik görevler tamamlandı
```

**Sonraki AI için**: Orta/düşük öncelikli görevlerle devam edebilir veya yeni özellikler ekleyebilirsin.
