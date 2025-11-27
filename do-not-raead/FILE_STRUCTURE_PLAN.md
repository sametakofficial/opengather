# Dosya/Klasör Yapısı Analiz ve Yeniden Yapılandırma Planı

> **Tarih**: 2025-11-27  
> **Amaç**: Mevcut dosya yapısını endüstri standartlarına göre analiz etmek ve yeniden yapılandırmak

---

## 1. Mevcut Yapı Analizi

### 1.1 Sorunlu Dosya/Klasör Tespitleri

| Dosya/Klasör | Sorun | Önem | Çözüm |
|--------------|-------|------|-------|
| `api/database.py` | `infrastructure/database/` ile çakışıyor | 🔴 KRİTİK | `infrastructure/database/motor.py`'ye taşı |
| `api/dependencies.py` | 438 satır, çok büyük, birden fazla sorumluluk | 🔴 KRİTİK | Böl: `deps/db.py`, `deps/auth.py`, `deps/common.py` |
| `api/process_executor.py` | API klasöründe olmamalı | 🟠 YÜKSEK | `core/services/process_executor.py`'ye taşı |
| `models/response_builder.py` | Tek dosya, `core/` altında olmalı | 🟡 ORTA | `core/response/builder.py`'ye taşı |
| `persistence/` | Boş klasör, `infrastructure/` ile çakışıyor | 🟡 ORTA | Sil |
| `backend/` | Boş klasör | 🟢 DÜŞÜK | Sil |
| `reports/` | `src/` içinde olmamalı | 🟢 DÜŞÜK | Proje kökünde kalmalı |
| `cli/` | Sadece 2 dosya | 🟢 DÜŞÜK | İyi konumda |

### 1.2 API Modül Yapısı - Tutarsızlıklar

```
api/v1/
├── executions/
│   ├── router.py     ✅
│   └── schemas.py    ✅  <-- Var
├── matches/
│   └── router.py     ❌ schemas.py YOK
├── versioning/
│   ├── router.py     ✅
│   └── schemas.py    ✅  <-- Var
├── run/
│   └── router.py     ❌ schemas.py YOK
└── system/
    └── router.py     ❌ schemas.py YOK
```

**Problem:** Bazı modüllerde schemas.py var, bazılarında yok. Tutarsız.

### 1.3 Infrastructure Değerlendirmesi

```
infrastructure/
├── database/              ✅ İyi yapı
│   ├── connection.py      ✅ Bağlantı factory
│   ├── diagnostics.py     ❓ Burası doğru yer mi?
│   ├── interface.py       ✅ Abstract interface
│   ├── mock.py            ✅ Mock implementation
│   └── mongodb.py         ✅ MongoDB implementation
└── repositories/          ✅ İyi yapı
    ├── base.py            ✅ Abstract repository
    ├── execution_repository.py  ✅
    ├── match_repository.py      ✅
    └── plugin_result_repository.py  ✅
```

**Sorun:** `api/database.py` Motor kullanıyor ama `infrastructure/database/mongodb.py` PyMongo kullanıyor. İKİ FARKLI SİSTEM!

### 1.4 Test Yapısı Analizi

```
tests/
├── conftest.py                  ✅ Global fixtures
├── test_api.py                  ⚠️ Genel, bölünmeli
├── test_execution_service.py    ✅ 
├── test_full_pipeline.py        ⚠️ Plugin bağımlı
├── test_integration.py          ⚠️ Plugin bağımlı
├── test_persistence.py          ✅
├── test_real_api.py             ⚠️ E2E, ayrı klasörde olmalı
└── test_state_management.py     ✅
```

---

## 2. Yeni Yapı Planı

### 2.1 Ana Yapı (Hedef)

```
src/archiverr/
├── __init__.py
├── __main__.py
│
├── api/                           # FastAPI API Layer
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory
│   ├── deps/                      # 🆕 Dependencies klasörü
│   │   ├── __init__.py
│   │   ├── database.py            # DB dependency (get_db)
│   │   └── common.py              # Common deps
│   ├── middleware/
│   │   └── rate_limit.py
│   └── v1/
│       ├── __init__.py
│       ├── router.py
│       ├── executions/
│       │   ├── router.py
│       │   └── schemas.py
│       ├── matches/
│       │   ├── router.py
│       │   └── schemas.py         # 🆕 Eksik, eklenecek
│       ├── run/
│       │   ├── router.py
│       │   └── schemas.py         # 🆕 Eksik, eklenecek
│       ├── system/
│       │   ├── router.py
│       │   └── schemas.py         # 🆕 Eksik, eklenecek
│       └── versioning/
│           ├── router.py
│           └── schemas.py
│
├── cli/                           # CLI Entry points
│   └── ...
│
├── core/                          # Business Logic
│   ├── __init__.py
│   ├── config_validator.py
│   ├── plugins/                   # Plugin system
│   │   └── ...
│   ├── services/                  # Business services
│   │   ├── execution_service.py
│   │   └── process_executor.py    # 🔄 api/'den taşınacak
│   ├── tasks/
│   │   └── ...
│   └── response/                  # 🆕 Response building
│       ├── __init__.py
│       └── builder.py             # 🔄 models/'den taşınacak
│
├── events/                        # Event system
│   ├── bus.py
│   └── handlers.py
│
├── infrastructure/                # External services & DB
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── interface.py           # Abstract interface
│   │   ├── connection.py          # Connection factory
│   │   ├── motor.py               # 🆕 Async Motor driver (api/database.py'den)
│   │   ├── mongodb.py             # Sync PyMongo
│   │   ├── mock.py                # Mock persistence
│   │   └── diagnostics.py
│   └── repositories/
│       ├── base.py
│       ├── execution_repository.py
│       ├── match_repository.py
│       └── plugin_result_repository.py
│
├── state/                         # State management
│   ├── manager.py
│   └── models.py
│
├── plugins/                       # Domain plugins
│   ├── base.py
│   ├── scanner/
│   ├── renamer/
│   ├── tmdb/
│   └── ...
│
└── utils/                         # Utilities
    ├── config_loader.py
    ├── debug.py
    ├── filters.py
    └── templates.py

tests/
├── conftest.py
├── unit/                          # 🆕 Unit tests
│   ├── core/
│   │   ├── test_plugin_discovery.py
│   │   └── test_plugin_loader.py
│   ├── state/
│   │   └── test_manager.py
│   └── api/
│       └── test_endpoints.py
├── integration/                   # 🆕 Integration tests
│   ├── test_execution_service.py
│   └── test_persistence.py
└── e2e/                           # 🆕 End-to-end tests
    ├── test_cli.py
    └── test_api_server.py

# 🗑️ SİLİNECEK BOŞ KLASÖRLER:
# - src/archiverr/backend/
# - src/archiverr/persistence/
# - src/archiverr/reports/
```

### 2.2 Silinen/Taşınan Dosyalar

| Kaynak | Hedef | Aksiyon |
|--------|-------|---------|
| `api/database.py` | `infrastructure/database/motor.py` | TAŞI |
| `api/dependencies.py` | `api/deps/` (böl) | BÖLE VE TAŞI |
| `api/process_executor.py` | `core/services/process_executor.py` | TAŞI |
| `models/response_builder.py` | `core/response/builder.py` | TAŞI |
| `models/` klasörü | - | SİL (boşalınca) |
| `backend/` klasörü | - | SİL |
| `persistence/` klasörü | - | SİL |

---

## 3. Aksiyon Planı

### Faz 1: Kritik Taşımalar (Şimdi)

- [ ] **1.1** `api/database.py` → `infrastructure/database/motor.py`
- [ ] **1.2** `api/dependencies.py` → `api/deps/` (bölme)
- [ ] **1.3** Import'ları güncelle

### Faz 2: Yapısal İyileştirmeler

- [ ] **2.1** `api/process_executor.py` → `core/services/`
- [ ] **2.2** `models/response_builder.py` → `core/response/`
- [ ] **2.3** Boş klasörleri sil

### Faz 3: Eksik Dosyaları Ekle

- [ ] **3.1** `api/v1/matches/schemas.py` oluştur
- [ ] **3.2** `api/v1/run/schemas.py` oluştur
- [ ] **3.3** `api/v1/system/schemas.py` oluştur

### Faz 4: Test Refactor

- [ ] **4.1** `tests/unit/` klasör yapısı oluştur
- [ ] **4.2** `tests/integration/` klasör yapısı oluştur
- [ ] **4.3** `tests/e2e/` klasör yapısı oluştur
- [ ] **4.4** Testleri yeni yapıya taşı

---

## 4. Tamamlanan Aksiyonlar

### ✅ Faz 1: Kritik Taşımalar (TAMAMLANDI)

1. ✅ `api/deps/` klasörü oluşturuldu
2. ✅ `api/deps/__init__.py` - export'lar
3. ✅ `api/deps/database.py` - DB dependency'ler (Motor + PyMongo)
4. ✅ `api/deps/common.py` - AsyncPersistenceWrapper + get_persistence
5. ✅ `infrastructure/database/motor.py` - Motor modülü (api/database.py'den)
6. ✅ `infrastructure/database/__init__.py` - Motor export'ları eklendi
7. ✅ `api/database.py` - Deprecation re-export'a dönüştürüldü
8. ✅ `api/dependencies.py` - Deprecation re-export'a dönüştürüldü
9. ✅ `api/main.py` - Import güncellendi
10. ✅ `api/v1/executions/router.py` - Depends(get_database) kullanıyor
11. ✅ `api/v1/matches/router.py` - Depends(get_database) kullanıyor
12. ✅ `api/v1/versioning/router.py` - Depends(get_database) kullanıyor
13. ✅ `api/v1/system/router.py` - Import güncellendi
14. ✅ Boş klasörler silindi (backend/, persistence/)

### ✅ Faz 2: Eksik Schema Dosyaları (TAMAMLANDI)

15. ✅ `api/v1/matches/schemas.py` oluşturuldu
16. ✅ `api/v1/run/schemas.py` oluşturuldu
17. ✅ `api/v1/system/schemas.py` oluşturuldu

### ✅ Faz 3: Test Dizin Yapısı (TAMAMLANDI)

18. ✅ `tests/unit/` klasörü oluşturuldu
19. ✅ `tests/unit/core/` klasörü oluşturuldu
20. ✅ `tests/unit/state/` klasörü oluşturuldu
21. ✅ `tests/unit/api/` klasörü oluşturuldu
22. ✅ `tests/integration/` klasörü oluşturuldu
23. ✅ `tests/e2e/` klasörü oluşturuldu

### ✅ Faz 4: Test Dosyaları (TAMAMLANDI)

24. ✅ `tests/unit/core/test_plugin_discovery.py` oluşturuldu (10 test)
25. ✅ `tests/unit/state/test_state_manager.py` oluşturuldu (17 test)
26. ✅ `tests/unit/api/test_endpoints.py` oluşturuldu (18 test)

### 📊 Test Özeti

| Kategori | Test Sayısı | Durum |
|----------|-------------|-------|
| `tests/unit/` | 45 test | ✅ Tümü geçti |
| `tests/test_api.py` | 16 test | ✅ Tümü geçti |
| `tests/test_state_management.py` | 26 test | ✅ Tümü geçti |

**Toplam:** 87+ test başarılı

---

*Son güncelleme: 2025-11-27*
