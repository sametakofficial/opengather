# Action Items
## Önceliklendirilmiş Aksiyon Listesi

---

## 🔴 ÖNCELIK 1: ACİL (Bugün/Yarın)

### 1.1 Backup Dosyalarını Sil

```bash
# Komutlar:
rm src/archiverr/plugins/tmdb/client.py.bak
rm src/archiverr/plugins/tvdb/client.py.bak
rm src/archiverr/plugins/tvmaze/client.py.bak
```

**Gerekçe:** Production kodda backup dosyası olmamalı, git zaten version history tutuyor.

### 1.2 Duplicate Manifest Dosyalarını Temizle

Tek format olarak `manifest.yml` kullan. Diğerlerini sil:

```bash
# tmdb
rm src/archiverr/plugins/tmdb/plugin.json
rm src/archiverr/plugins/tmdb/plugin.yml

# renamer
rm src/archiverr/plugins/renamer/plugin.json
rm src/archiverr/plugins/renamer/plugin.yml

# ffprobe
rm src/archiverr/plugins/ffprobe/plugin.json
rm src/archiverr/plugins/ffprobe/plugin.yml

# Eski sistemdeki pluginler (tvdb, omdb, tvmaze, file-reader)
# Önce manifest.yml oluştur, sonra diğerlerini sil
```

### 1.3 Klasör İsimlendirme Düzeltmesi

```bash
# PEP 8 uyumu için
mv src/archiverr/plugins/file-reader src/archiverr/plugins/file_reader

# Import'ları güncelle
# grep -r "file-reader" src/ --include="*.py"
```

---

## 🟡 ÖNCELIK 2: KISA VADELI (1 Hafta)

### 2.1 stage_executor.py Bölme

**Mevcut:** 904 satır, çok fazla sorumluluk

**Hedef Yapı:**
```
core/plugins/execution/
├── __init__.py
├── stage_executor.py      # Ana orchestration (200 satır)
├── per_job_runner.py      # Per-job execution (200 satır)
├── per_run_runner.py      # Per-run execution (100 satır)
├── parallel_executor.py   # Parallel execution (150 satır)
└── validation.py          # Requires/trigger validation (150 satır)
```

### 2.2 Hardcoded Plugin Referanslarını Kaldır

**Dosya: tasker/plugin.py (line 185-196)**

Değiştirilecek:
```python
# ÖNCE
if 'renamer' in plugins_data:
    renamer_data = plugins_data['renamer']
    ...
    context['renamer'] = renamer_data

# SONRA
# Plugin-agnostik: Tüm plugin verilerini context'e ekle
for plugin_name, plugin_data in plugins_data.items():
    context[plugin_name] = plugin_data
```

**Dosya: tmdb/client.py (line 92-102)**

Manifest requires validation'a güven:
```python
# ÖNCE
renamer_data = job.plugins.get('renamer', {})

# SONRA (requires validation zaten çalışıyor)
parsed_data = self._get_required_data(job, 'renamer', 'parsed')
```

### 2.3 Boş __init__.py Dosyalarını Düzelt

```python
# plugins/ffprobe/__init__.py
"""FFProbe Plugin - Media file analysis."""

# plugins/tvdb/__init__.py
"""TVDB Plugin - TV show metadata provider (DEPRECATED)."""
```

### 2.4 Eski Pluginleri İşaretle

```yaml
# plugins/tvdb/manifest.yml - Başına ekle
deprecated: true
deprecated_since: "2024-12"
replacement: "tmdb"
```

---

## 🟢 ÖNCELIK 3: ORTA VADELI (1 Ay)

### 3.1 Dokümantasyon Oluştur

```
docs/
├── README.md              # Proje tanıtımı
├── INSTALLATION.md        # Kurulum rehberi
├── CONFIGURATION.md       # Config dosyası açıklaması
├── PLUGIN_DEVELOPMENT.md  # Plugin geliştirme rehberi
├── API_REFERENCE.md       # FastAPI endpoint'leri
├── ARCHITECTURE.md        # Sistem mimarisi
└── CONTRIBUTING.md        # Katkı rehberi
```

### 3.2 Test Coverage Artır

**Hedef:** %60 minimum coverage

**Kritik test dosyaları:**
```
tests/unit/core/
├── test_orchestrator.py
├── test_stage_executor.py
├── test_plugin_registry.py
└── test_state_manager.py

tests/unit/plugins/
├── test_scanner.py
├── test_renamer.py
├── test_tmdb.py
└── test_tasker.py
```

### 3.3 CI/CD Pipeline Kur

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest --cov
```

### 3.4 Pre-commit Hooks Ekle

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
```

---

## 🔵 ÖNCELIK 4: UZUN VADELI (3 Ay)

### 4.1 Async/Sync Tutarlılığı

Karar ver:
- [ ] Tamamen sync (CLI için optimize)
- [ ] Tamamen async (API için optimize)
- [ ] Hibrit (mevcut, ama dokümante et)

### 4.2 SDK Konumunu Değerlendir

Seçenekler:
1. `core/plugins/sdk/` (mevcut) - Core'a bağımlı
2. `sdk/` (ayrı) - Bağımsız paket olabilir
3. Ayrı PyPI paketi - Plugin geliştiricileri için

### 4.3 Logging Modernizasyonu

```python
# Mevcut custom Debugger → Loguru geçişi
from loguru import logger

logger.bind(component="orchestrator").info("Run started")
```

### 4.4 Database Abstraction

```python
# Repository pattern tam uygulama
class RunRepository(Protocol):
    def save(self, run: RunState) -> None: ...
    def get(self, run_id: str) -> RunState | None: ...
    def list(self, limit: int = 100) -> list[RunState]: ...
```

---

## KONTROL LİSTESİ

### Öncelik 1 (Bugün)
- [ ] `.bak` dosyalarını sil
- [ ] Duplicate manifest'leri sil
- [ ] `file-reader` → `file_reader` rename

### Öncelik 2 (1 Hafta)
- [ ] `stage_executor.py` böl
- [ ] Hardcoded referansları kaldır
- [ ] Boş `__init__.py` düzelt
- [ ] Eski pluginleri deprecated işaretle

### Öncelik 3 (1 Ay)
- [ ] Temel docs/ oluştur
- [ ] Test coverage %60'a çıkar
- [ ] CI/CD pipeline kur
- [ ] Pre-commit hooks ekle

### Öncelik 4 (3 Ay)
- [ ] Async/sync tutarlılık kararı
- [ ] SDK konumu değerlendirmesi
- [ ] Logging modernizasyonu
- [ ] Full repository pattern

---

## NOTLAR

- Her değişiklik için branch aç
- Breaking change'ler için major version
- Backward compatibility önemli
- Test yazmadan merge etme
