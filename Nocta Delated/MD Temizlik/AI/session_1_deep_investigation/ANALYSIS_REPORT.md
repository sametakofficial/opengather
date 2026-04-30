# Archiverr Deep Investigation Report
## Session 1 - Comprehensive Architecture & Code Quality Analysis

**Tarih:** 2024-12-19  
**Analiz Türü:** Production-Ready Code Review + Industry Standards Comparison

---

## 1. EXECUTIVE SUMMARY

### 1.1 Proje Genel Durumu

| Kategori | Durum | Puan (1-10) |
|----------|-------|-------------|
| Proje Yapısı | İyi | 7/10 |
| Kod Kalitesi | Orta-İyi | 6.5/10 |
| Plugin Mimarisi | İyi | 7.5/10 |
| Endüstri Standartları | Orta | 6/10 |
| Dokümantasyon | Zayıf | 4/10 |
| Test Coverage | Zayıf | 3/10 |

### 1.2 Kritik Bulgular Özeti

**🔴 Acil Düzeltme Gerektiren:**
- 3 adet `.bak` backup dosyası production kodda mevcut
- Bazı pluginlerde duplicate manifest dosyaları (plugin.json + plugin.yml + manifest.yml)
- SDK klasörü `core/plugins/sdk/` içinde - tutarsız yerleşim

**🟡 İyileştirme Gerektiren:**
- 900+ satırlık dev dosyalar (stage_executor.py: 904 satır)
- Bazı modüllerde SRP (Single Responsibility) ihlali
- Eksik type hints bazı fonksiyonlarda

**🟢 İyi Durumda:**
- Modern Python kullanımı (3.10+, dataclasses, type hints)
- pyproject.toml ile PEP 621 uyumlu yapılandırma
- Event-driven mimari iyi tasarlanmış
- Plugin sistemi modüler ve genişletilebilir

---

## 2. PROJE YAPISI ANALİZİ

### 2.1 Mevcut Klasör Yapısı

```
src/archiverr/
├── __init__.py          # 83 bytes
├── __main__.py          # 5070 bytes - Entry point
├── api/                 # FastAPI endpoints (27 items)
│   ├── main.py         # App factory pattern ✓
│   ├── middleware/     # Rate limiting
│   ├── deps/           # Dependency injection
│   └── v1/             # Versioned API routes
├── cli/                 # CLI interface (2 items)
├── core/                # Core business logic (47 items)
│   ├── orchestrator.py # Main execution coordinator
│   ├── plugins/        # Plugin infrastructure
│   │   ├── sdk/       # ⚠️ SDK burada - tartışmalı konum
│   │   ├── loader.py
│   │   ├── registry.py
│   │   └── stage_executor.py  # 904 satır! ⚠️
│   ├── services/       # Service layer
│   └── triggers/       # Trigger rule system
├── events/              # Event bus system (3 items)
├── infrastructure/      # Database, repositories (14 items)
├── models/              # Response models (2 items)
├── plugins/             # Actual plugins (66 items)
│   ├── tmdb/           # ✓ Güncel
│   ├── scanner/        # ✓ Güncel
│   ├── tasker/         # ✓ Güncel
│   ├── renamer/        # ✓ Güncel
│   ├── ffprobe/        # ⚠️ Eski sistem kalıntısı olabilir
│   ├── tvdb/           # ⚠️ Eski sistem
│   ├── omdb/           # ⚠️ Eski sistem
│   ├── tvmaze/         # ⚠️ Eski sistem
│   └── file-reader/    # ⚠️ Eski sistem
├── state/               # State management (9 items)
└── utils/               # Utilities (7 items)
```

### 2.2 Endüstri Standardı Karşılaştırması

#### The Hitchhiker's Guide to Python Önerisi:
```
sample/
├── __init__.py
├── core.py
└── helpers.py
docs/
tests/
setup.py / pyproject.toml
```

#### Archiverr Durumu:
- ✅ `src/` layout kullanımı (PEP 517/518 uyumlu)
- ✅ `pyproject.toml` modern yapılandırma
- ✅ `tests/` ayrı klasör
- ⚠️ `docs/` yetersiz (sadece PLUGIN_SDK.md)
- ⚠️ Çok fazla nested klasör (core/plugins/sdk/validators.py gibi)

### 2.3 Dosya Boyutu Analizi

**En Büyük Dosyalar (Potansiyel SRP İhlali):**

| Dosya | Satır | Durum |
|-------|-------|-------|
| `core/plugins/stage_executor.py` | 904 | 🔴 Çok büyük, bölünmeli |
| `infrastructure/database/mongodb.py` | 526 | 🟡 Kabul edilebilir |
| `core/orchestrator.py` | 469 | 🟡 Kabul edilebilir |
| `plugins/tasker/plugin.py` | 451 | 🟡 Kabul edilebilir |
| `core/plugins/sdk/validators.py` | 431 | 🟡 Kabul edilebilir |

**Önerilen Maksimum:** 300-400 satır/dosya

### 2.4 Kullanılmayan/Gereksiz Dosyalar

**Backup Dosyaları (SİLİNMELİ):**
```
plugins/tmdb/client.py.bak      # 17254 bytes
plugins/tvdb/client.py.bak      # 19984 bytes
plugins/tvmaze/client.py.bak    # Mevcut
```

**Duplicate Manifest Dosyaları:**

| Plugin | Dosyalar | Sorun |
|--------|----------|-------|
| tmdb | plugin.json, plugin.yml, manifest.yml | 3 farklı format! |
| renamer | plugin.json, plugin.yml, manifest.yml | 3 farklı format! |
| ffprobe | plugin.json, plugin.yml, manifest.yml | 3 farklı format! |
| scanner | manifest.yml | ✓ Tek format |
| tasker | manifest.yml | ✓ Tek format |

**Öneri:** Tek bir manifest formatına geçiş (manifest.yml tercih edilmeli)

---

## 3. KOD KALİTESİ ANALİZİ

### 3.1 Python Best Practices Uyumu

#### ✅ İyi Uygulamalar:
- **Type Hints:** Yaygın kullanım (`dict[str, Any]`, `list[str]`, `| None`)
- **Dataclasses:** State modellerde kullanılıyor (models.py)
- **Enums:** StateEnum, Stage gibi type-safe enumlar
- **ABC/Protocol:** Plugin base classes ve service protocols
- **Factory Pattern:** `build_orchestrator()`, `create_app()`
- **Dependency Injection:** Services aracılığıyla

#### ⚠️ İyileştirme Gereken:
- **Magic Strings:** Bazı yerlerde hardcoded stringler
  ```python
  # Örnek: stage_executor.py
  mode = manifest.get('execution_mode', 'per_job')  # 'per_job' magic string
  ```
- **Any Type Overuse:** Bazı yerlerde `Any` fazla kullanılmış
- **Exception Handling:** Çok geniş except blokları var

### 3.2 SOLID Prensipleri Analizi

#### S - Single Responsibility:
| Dosya | SRP Uyumu | Not |
|-------|-----------|-----|
| orchestrator.py | ✅ | İyi bölünmüş, delegate pattern |
| stage_executor.py | ⚠️ | Çok fazla sorumluluk, 904 satır |
| manager.py (state) | ✅ | Delegate pattern ile bölünmüş |
| tasker/plugin.py | ⚠️ | Template + Task + JSON output karışık |

#### O - Open/Closed:
- ✅ Plugin sistemi genişlemeye açık
- ✅ Service protocols ile abstraction

#### L - Liskov Substitution:
- ✅ BasePlugin → InputPlugin/OutputPlugin inheritance doğru

#### I - Interface Segregation:
- ✅ protocols.py küçük, odaklı interfaceler

#### D - Dependency Inversion:
- ✅ Services dependency injection
- ⚠️ Bazı yerlerde direkt import var

### 3.3 Plugin Agnostik Sistem Analizi

**Hardcoded Plugin Referansları:**

```python
# stage_executor.py - İYİ: Plugin-agnostik
for plugin in plugins:
    plugin_name = self._get_plugin_name(plugin)
    
# tasker/plugin.py - KÖTÜ: Hardcoded referans
if 'renamer' in plugins_data:
    renamer_data = plugins_data['renamer']
```

**Bulunan Hardcoded Referanslar:**
1. `tasker/plugin.py` - renamer shortcuts (line 185-196)
2. `tmdb/client.py` - renamer dependency (line 92-102)

### 3.4 Error Handling Analizi

**İyi Örnek:**
```python
# orchestrator.py
except CriticalError as e:
    self._log("error", f"Critical error: {e}")
    self._emit_error(e, critical=True)
    self._finalize(success=False)
    return self._build_result(success=False, error=str(e))
```

**İyileştirme Gereken:**
```python
# stage_executor.py - Çok geniş except
except Exception as e:
    # Tüm exception'lar aynı şekilde handle ediliyor
```

---

## 4. GÜNCEL PLUGİN ANALİZİ (tmdb, scanner, tasker, renamer)

### 4.1 TMDB Plugin

**Dosyalar:**
- `client.py` (246 satır) - ✅ İyi boyut
- `manifest.yml` (57 satır) - ✅ Kapsamlı
- `extras.py`, `normalize/`, `utils/` - ✅ İyi modülerlik

**Güçlü Yanlar:**
- Async setup method
- Component-based architecture (fetchers, normalizer, extras)
- Config schema validation
- Logging integration

**İyileştirmeler:**
```python
# client.py line 92-102 - Hardcoded renamer dependency
parsed_data = job.plugins.get('renamer', {}).get('parsed', {})
# Öneri: requires validation'a güvenmeli
```

### 4.2 Scanner Plugin

**Dosyalar:**
- `client.py` (116 satır) - ✅ Minimal ve temiz
- `manifest.yml` (51 satır) - ✅ İyi tanımlanmış

**Güçlü Yanlar:**
- Security validation (path traversal check)
- Virtual path support
- Clean job creation

**İyileştirmeler:**
- `execute()` raises NotImplementedError - kafa karıştırıcı olabilir

### 4.3 Tasker Plugin

**Dosyalar:**
- `plugin.py` (451 satır) - ⚠️ Büyük, bölünebilir
- `manifest.yml` (42 satır) - ✅ OK

**Güçlü Yanlar:**
- Jinja2 template support
- Template functions (index:, count:)
- Dry run support

**İyileştirmeler:**
```python
# PluginResult helper class - kendi dosyasına taşınmalı
class PluginResult:
    @staticmethod
    def success_result(...):
```

### 4.4 Renamer Plugin

**Dosyalar:**
- `client.py` (137 satır) - ✅ İyi boyut
- `parser.py` (294 satır) - ✅ Ayrı modül
- `manifest.yml` (31 satır) - ✅ Minimal

**Güçlü Yanlar:**
- Auto media type detection
- Clean separation (client vs parser)

---

## 5. SDK KLASÖRÜ ANALİZİ

### 5.1 Mevcut Konum

```
core/plugins/sdk/
├── __init__.py      # 53 satır - exports
├── base.py          # 241 satır - BasePlugin, InputPlugin, OutputPlugin
├── context.py       # 2538 bytes - ExecutionContext
├── manifest.py      # 4743 bytes - PluginManifest Pydantic model
├── result.py        # 4340 bytes - PluginResult
├── types.py         # 972 bytes - Enums
└── validators.py    # 431 satır - Config validation
```

### 5.2 Kullanım Durumu

**SDK Kullanan Modüller:**
- `plugins/tmdb/client.py` - ✅ Aktif
- `plugins/scanner/client.py` - ✅ Aktif
- `plugins/renamer/client.py` - ✅ Aktif
- `plugins/ffprobe/client.py` - ✅ Aktif
- `core/plugins/loader.py` - ✅ Aktif
- `core/plugins/discovery.py` - ✅ Aktif
- `core/plugins/executor.py` - ✅ Aktif
- `state/__init__.py` - ✅ Aktif

**Sonuç:** SDK AKTİF KULLANILIYOR, kaldırılmamalı!

### 5.3 Konum Tartışması

**Mevcut:** `core/plugins/sdk/`
**Alternatif 1:** `sdk/` (root level)
**Alternatif 2:** `plugins/sdk/` (plugins içinde)

**Endüstri Standardı Önerisi:**
- FastAPI: `app/` içinde her şey
- Flask: `blueprints/` ayrı
- Django: `apps/` içinde

**Öneri:** Mevcut konum kabul edilebilir ama dokümante edilmeli.

---

## 6. ESKİ SİSTEM KALINTILARI

### 6.1 Tespit Edilen Eski Dosyalar

| Dosya/Klasör | Durum | Aksiyon |
|--------------|-------|---------|
| `plugins/ffprobe/` | ⚠️ Belirsiz | Güncel mi kontrol et |
| `plugins/tvdb/` | 🔴 Eski | Güncelle veya kaldır |
| `plugins/omdb/` | 🔴 Eski | Güncelle veya kaldır |
| `plugins/tvmaze/` | 🔴 Eski | Güncelle veya kaldır |
| `plugins/file-reader/` | ⚠️ Belirsiz | Kontrol et |
| `*.bak` dosyaları | 🔴 Gereksiz | Sil |

### 6.2 Legacy Code Patterns

```python
# stage_executor.py - Legacy support
if hasattr(plugin, 'get_matches'):
    # Legacy: input plugins use get_matches
    allow_legacy = bool(self._config.get('options', {}).get('allow_legacy_get_matches', False))
```

**Öneri:** Legacy flag'leri dokümante et ve deprecation timeline belirle.

---

## 7. ENDÜSTRİ STANDARTLARI KARŞILAŞTIRMASI

### 7.1 PEP Uyumluluk

| PEP | Konu | Uyumluluk |
|-----|------|-----------|
| PEP 8 | Style Guide | ✅ (ruff kullanımı) |
| PEP 257 | Docstrings | ⚠️ Kısmi |
| PEP 484 | Type Hints | ✅ |
| PEP 517/518 | Build System | ✅ pyproject.toml |
| PEP 621 | Project Metadata | ✅ |

### 7.2 Modern Python Özellikleri

| Özellik | Kullanım | Not |
|---------|----------|-----|
| Dataclasses | ✅ | state/models.py |
| Type Hints (3.10+) | ✅ | `dict[str, Any]`, `X \| None` |
| Pattern Matching | ❌ | Kullanılmıyor |
| asyncio | ⚠️ Kısmi | Executor'da var |
| Pathlib | ⚠️ Kısmi | os.path hala var |

### 7.3 Eksik Endüstri Standartları

1. **README.md** - Yok veya yetersiz
2. **CONTRIBUTING.md** - Yok
3. **CHANGELOG.md** - Yok
4. **Comprehensive docs/** - Sadece PLUGIN_SDK.md
5. **CI/CD Pipeline** - Görünmüyor
6. **Pre-commit hooks** - Yapılandırılmamış

---

## 8. DOSYA/KLASÖR YENİDEN YAPILANDIRMA ÖNERİLERİ

### 8.1 Acil Yapılması Gerekenler

```bash
# 1. Backup dosyalarını sil
rm src/archiverr/plugins/tmdb/client.py.bak
rm src/archiverr/plugins/tvdb/client.py.bak
rm src/archiverr/plugins/tvmaze/client.py.bak

# 2. Duplicate manifest'leri temizle
# Her plugin için tek manifest.yml bırak, diğerlerini sil
```

### 8.2 Klasör İsimlendirme Önerileri

| Mevcut | Öneri | Sebep |
|--------|-------|-------|
| `file-reader` | `file_reader` | Python package naming (PEP 8) |
| `core/plugins/sdk` | Aynı kalabilir | Konum mantıklı |
| `infrastructure` | Aynı kalabilir | DDD standardı |

### 8.3 stage_executor.py Bölme Önerisi

```
core/plugins/
├── stage_executor/
│   ├── __init__.py          # Public exports
│   ├── executor.py          # Main StageExecutor class
│   ├── parallel.py          # Parallel execution logic
│   ├── validation.py        # Requires validation
│   └── job_processor.py     # Per-job execution
```

---

## 9. AKSİYON PLANI

### 9.1 Öncelik 1 (Acil)

- [ ] Backup dosyalarını sil (.bak)
- [ ] Duplicate manifest'leri temizle
- [ ] stage_executor.py'yi böl

### 9.2 Öncelik 2 (Kısa Vadeli)

- [ ] Hardcoded plugin referanslarını kaldır
- [ ] Eski pluginleri güncelle veya deprecated olarak işaretle
- [ ] README.md oluştur

### 9.3 Öncelik 3 (Orta Vadeli)

- [ ] Comprehensive documentation
- [ ] Test coverage artır
- [ ] CI/CD pipeline kur
- [ ] Pre-commit hooks ekle

---

## 10. SONUÇ

Archiverr, modern Python pratiklerini büyük ölçüde takip eden, iyi tasarlanmış bir plugin mimarisine sahip bir proje. Temel yapı sağlam, ancak:

1. **Temizlik gerekiyor** - Backup dosyaları, duplicate manifestler
2. **Büyük dosyalar bölünmeli** - stage_executor.py
3. **Dokümantasyon eksik** - Production için kritik
4. **Test coverage düşük** - Güvenilirlik için artırılmalı

Genel olarak proje **production-ready olmaya yakın** ancak yukarıdaki iyileştirmeler yapılmalı.

---

*Bu rapor AI analizi sonucu oluşturulmuştur. Manuel review önerilir.*
