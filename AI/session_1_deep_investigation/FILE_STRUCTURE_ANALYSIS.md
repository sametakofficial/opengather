# File Structure Analysis
## Detaylı Dosya ve Klasör Analizi

---

## 1. DOSYA BOYUT ANALİZİ

### 1.1 En Büyük Python Dosyaları (Satır Sayısına Göre)

| Satır | Dosya | Değerlendirme |
|-------|-------|---------------|
| 904 | `core/plugins/stage_executor.py` | 🔴 Bölünmeli |
| 526 | `infrastructure/database/mongodb.py` | 🟡 Gözden geçir |
| 469 | `core/orchestrator.py` | 🟢 Kabul edilebilir |
| 451 | `plugins/tasker/plugin.py` | 🟡 Değerlendirme gerekli |
| 431 | `core/plugins/sdk/validators.py` | 🟢 Kabul edilebilir |
| 420 | `core/plugins/registry.py` | 🟢 Kabul edilebilir |
| 407 | `core/plugins/executor.py` | 🟢 Kabul edilebilir |
| 398 | `core/provides_registry.py` | 🟢 Kabul edilebilir |
| 393 | `utils/config_loader.py` | 🟢 Kabul edilebilir |
| 363 | `plugins/tmdb/utils/fetchers.py` | 🟢 OK |
| 345 | `infrastructure/database/pymongo_persistence.py` | 🟢 OK |
| 345 | `api/v1/runs/router.py` | 🟢 OK |
| 345 | `events/bus.py` | 🟢 OK |
| 327 | `core/plugins/manifest_normalizer.py` | 🟢 OK |
| 326 | `core/plugins/requires_validator.py` | 🟢 OK |
| 321 | `utils/config_normalizer.py` | 🟢 OK |
| 320 | `api/v1/jobs/router.py` | 🟢 OK |
| 315 | `state/manager.py` | 🟢 OK |
| 310 | `core/services/protocols.py` | 🟢 OK |
| 294 | `plugins/renamer/parser.py` | 🟢 OK |

### 1.2 Endüstri Standardı

**Best Practice:** 200-400 satır/dosya
**Maximum Önerilen:** 500 satır
**Red Flag:** 700+ satır

---

## 2. KLASÖR DERINLIK ANALİZİ

### 2.1 En Derin Yollar

```
src/archiverr/api/v1/jobs/router.py          # 5 seviye
src/archiverr/api/v1/plugins/router.py       # 5 seviye
src/archiverr/core/plugins/sdk/validators.py # 5 seviye
src/archiverr/plugins/tmdb/normalize/        # 5 seviye
src/archiverr/plugins/tmdb/utils/            # 5 seviye
```

**Endüstri Standardı:** Maksimum 4-5 seviye derinlik kabul edilebilir.

### 2.2 Öneri

Mevcut derinlik kabul edilebilir sınırlarda. Daha fazla nested yapı eklenmemeli.

---

## 3. DOSYA İSİMLENDİRME ANALİZİ

### 3.1 PEP 8 Uyumsuzlukları

| Mevcut | Sorun | Önerilen |
|--------|-------|----------|
| `file-reader/` | Tire kullanımı | `file_reader/` |

### 3.2 Tutarsız İsimlendirmeler

| Lokasyon | Dosyalar | Tutarsızlık |
|----------|----------|-------------|
| plugins/ | `client.py`, `plugin.py` | Bazıları client.py, bazıları plugin.py |

**Öneri:** Standart bir isimlendirme belirle:
- `plugin.py` - Ana plugin class
- `client.py` - API client varsa
- `utils/` - Yardımcı fonksiyonlar

---

## 4. MANIFEST DOSYALARI ANALİZİ

### 4.1 Format Tutarsızlığı

| Plugin | plugin.json | plugin.yml | manifest.yml | Sorun |
|--------|-------------|------------|--------------|-------|
| tmdb | ✓ | ✓ | ✓ | 3 format! |
| scanner | ✗ | ✗ | ✓ | ✓ Tek format |
| tasker | ✗ | ✗ | ✓ | ✓ Tek format |
| renamer | ✓ | ✓ | ✓ | 3 format! |
| ffprobe | ✓ | ✓ | ✓ | 3 format! |
| tvdb | ✓ | ✓ | ✗ | 2 format |
| omdb | ✓ | ✓ | ✗ | 2 format |
| tvmaze | ✓ | ✓ | ✗ | 2 format |
| file-reader | ✓ | ✓ | ✗ | 2 format |

### 4.2 Önerilen Standart

**Tek Format:** `manifest.yml`

**Gerekçe:**
1. YAML daha okunabilir
2. Comments destekler
3. Yeni pluginler (scanner, tasker) zaten bu formatı kullanıyor

### 4.3 Temizlik Aksiyonları

```bash
# Silinecek dosyalar:
rm plugins/tmdb/plugin.json
rm plugins/tmdb/plugin.yml
rm plugins/renamer/plugin.json
rm plugins/renamer/plugin.yml
rm plugins/ffprobe/plugin.json
rm plugins/ffprobe/plugin.yml
rm plugins/tvdb/plugin.json
rm plugins/tvdb/plugin.yml
rm plugins/omdb/plugin.json
rm plugins/omdb/plugin.yml
rm plugins/tvmaze/plugin.json
rm plugins/tvmaze/plugin.yml
rm plugins/file-reader/plugin.json
rm plugins/file-reader/plugin.yml
```

---

## 5. BACKUP DOSYALARI

### 5.1 Tespit Edilen .bak Dosyaları

| Dosya | Boyut | Tarih | Aksiyon |
|-------|-------|-------|---------|
| `plugins/tmdb/client.py.bak` | 17254 bytes | ? | Sil |
| `plugins/tvdb/client.py.bak` | 19984 bytes | ? | Sil |
| `plugins/tvmaze/client.py.bak` | ? | ? | Sil |

### 5.2 Neden Silinmeli?

1. Production kodda backup dosyası olmamalı
2. Git zaten version history tutuyor
3. Kafa karışıklığına neden olur

---

## 6. __PYCACHE__ ve GENERATED FILES

### 6.1 .gitignore Durumu

`.gitignore` dosyasında şunlar olmalı:
```gitignore
__pycache__/
*.pyc
*.pyo
.ruff_cache/
.mypy_cache/
*.egg-info/
dist/
build/
.venv/
venv/
```

---

## 7. MODÜL İHRACAT ANALİZİ (__init__.py)

### 7.1 Eksik/Yetersiz __init__.py Dosyaları

| Klasör | __init__.py | Durum |
|--------|-------------|-------|
| `api/` | 0 bytes | ❌ Boş |
| `plugins/ffprobe/` | 0 bytes | ❌ Boş |
| `plugins/tvdb/` | 0 bytes | ❌ Boş |
| `core/plugins/sdk/` | 53 satır | ✓ İyi |
| `events/` | 417 bytes | ✓ OK |
| `state/` | 1589 bytes | ✓ İyi |

### 7.2 Öneri

Boş `__init__.py` dosyaları ya export eklemeli ya da en azından modül docstring içermeli.

---

## 8. ENDÜSTRİ STANDARDI KLASÖR YAPISI ÖNERİSİ

### 8.1 Önerilen Yapı

```
src/archiverr/
├── __init__.py
├── __main__.py
├── api/
│   ├── __init__.py
│   ├── main.py
│   └── v1/
│       ├── __init__.py
│       └── routes/           # 'router' yerine 'routes'
├── cli/
│   ├── __init__.py
│   └── main.py
├── core/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── config.py             # config_validator.py → config.py
│   ├── exceptions.py
│   └── plugins/
│       ├── __init__.py
│       ├── discovery.py
│       ├── loader.py
│       ├── registry.py
│       └── execution/        # stage_executor.py bölünmüş
│           ├── __init__.py
│           ├── executor.py
│           ├── parallel.py
│           └── validation.py
├── sdk/                      # core/plugins/sdk → sdk (taşınabilir)
│   ├── __init__.py
│   ├── base.py
│   ├── context.py
│   ├── manifest.py
│   ├── result.py
│   └── validators.py
├── plugins/
│   ├── __init__.py
│   ├── scanner/
│   ├── renamer/
│   ├── tmdb/
│   └── tasker/
├── infrastructure/
│   ├── __init__.py
│   └── database/
├── state/
│   ├── __init__.py
│   ├── manager.py
│   └── models.py
├── events/
│   ├── __init__.py
│   └── bus.py
└── utils/
    ├── __init__.py
    ├── config.py             # config_loader + config_normalizer
    ├── templates.py
    └── filters.py
```

---

## 9. SONUÇ

### 9.1 Acil Temizlik (Bugün)

1. `.bak` dosyalarını sil
2. Duplicate manifest dosyalarını sil
3. `file-reader` → `file_reader` rename

### 9.2 Kısa Vadeli İyileştirme (1 Hafta)

1. `stage_executor.py` bölme
2. Boş `__init__.py` dosyalarını düzelt
3. Eski pluginleri deprecated olarak işaretle

### 9.3 Orta Vadeli (1 Ay)

1. SDK konumu değerlendirmesi
2. Kapsamlı docstring ekleme
3. utils/ modüllerini birleştirme değerlendirmesi
