# PHASE 3: CONFIG SYSTEM

```yaml
öncelik: P2
tahmini_süre: 2-3 saat
bağımlılık: Phase 1 (models için), Phase 2 opsiyonel
hedef: FlexGet-style config, alias sistemi
risk: DÜŞÜK (additive değişiklikler)
```

---

## MEVCUT DURUM ANALİZİ

### utils/config_loader.py

```python
# MEVCUT FONKSİYONLAR
load_config(path) → Dict
load_config_with_tracking(path) → Dict  # env var tracking
create_config_snapshot(config, original) → Dict
get_tracked_original() → Dict
```

### MEVCUT CONFIG YAPISI

```yaml
# config.yml (mevcut)
options:
  debug: true
  dry_run: false

plugins: # ← Bu wrapper var
  scanner:
    targets: [/downloads]
  tmdb:
    api_key: xxx
```

### HEDEF CONFIG YAPISI (FlexGet style)

```yaml
# config.yml (hedef)
options:
  debug: true
  dry_run: false
  memory:
    max_plugins_mb: 500

aliases: # ← YENİ top-level
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show

scanner: # ← plugins wrapper YOK
  targets: [/downloads]

tmdb:
  api_key: ${TMDB_API_KEY}
```

---

## TASK LİSTESİ

### 3.1 Alias Parser Utility

**Dosya:** `utils/alias_parser.py` (YENİ)

**Ne yapılacak:**

```
AliasParser class:
- __init__(aliases: Dict[str, str])
- resolve(path: str) → str
- expand_all(template: str) → str

Örnek:
  aliases = {"m": "job.plugins.tmdb.movie"}
  parser = AliasParser(aliases)
  parser.resolve("m.title") → "job.plugins.tmdb.movie.title"
```

**FINAL_DATASETS.yml Referansı:**

```yaml
default_aliases:
  system:
    run: run state
    job: current job state
    config: frozen config snapshot
  user: config.aliases
```

**Kabul Kriteri:**

```python
parser = AliasParser({"m": "job.plugins.tmdb.movie"})
assert parser.resolve("m.title") == "job.plugins.tmdb.movie.title"
assert parser.resolve("job.input.value") == "job.input.value"  # no alias
```

---

### 3.2 System Alias Defaults

**Dosya:** `utils/alias_parser.py`

**Nerede:** AliasParser class içinde veya module constant

**Ne yapılacak:**

```python
SYSTEM_ALIASES = {
    "run": "run",
    "job": "job",
    "jobs": "jobs",
    "plugins": "job.plugins",
    "config": "config",
    "options": "config.options",
}

class AliasParser:
    def __init__(self, user_aliases=None):
        self.aliases = {**SYSTEM_ALIASES}
        if user_aliases:
            self.aliases.update(user_aliases)  # user overrides system
```

---

### 3.3 Config Normalizer

**Dosya:** `utils/config_loader.py`

**Nerede:** Yeni fonksiyon

**Ne yapılacak:**

```python
def normalize_config(config: Dict) -> Dict:
    """
    Hem eski (plugins wrapper) hem yeni (flat) formatı destekle.

    ESKİ:
      plugins:
        tmdb: {api_key: x}

    YENİ:
      tmdb: {api_key: x}

    Return: Normalized (flat) config
    """
    # plugins wrapper varsa, içeriği dışarı çıkar
    if 'plugins' in config:
        plugins = config.pop('plugins')
        for name, cfg in plugins.items():
            if name not in config:
                config[name] = cfg
    return config
```

**Kabul Kriteri:**

```python
# Eski format
old = {"plugins": {"tmdb": {"key": "x"}}}
normalized = normalize_config(old)
assert "tmdb" in normalized
assert "plugins" not in normalized

# Yeni format (değişmez)
new = {"tmdb": {"key": "x"}}
normalized = normalize_config(new)
assert "tmdb" in normalized
```

---

### 3.4 Include Directive Handler

**Dosya:** `utils/config_loader.py`

**Nerede:** Yeni fonksiyon veya class

**Ne yapılacak:**

```python
def process_includes(config: Dict, base_path: Path) -> Dict:
    """
    !include directive'lerini işle.

    Syntax:
      tasks: !include ./tasks/movie_tasks.yml
      tasks: !include ./tasks/  # dizin ise tüm yml'leri merge et
    """
    # Recursive walk through config
    # Find !include tags
    # Load and merge
```

**FINAL_DATASETS.yml Referansı:**

```yaml
config_include:
  tasker:
    tasks: "!include ./tasks/"
```

**Not:** Bu task opsiyonel, basit bir implementasyon yeterli.

---

### 3.5 Alias Extraction from Config

**Dosya:** `utils/config_loader.py`

**Nerede:** `load_config_with_tracking` içinde veya sonra

**Ne yapılacak:**

```python
def extract_aliases(config: Dict) -> Dict[str, str]:
    """config.aliases'i çıkar, yoksa boş dict döndür"""
    return config.get('aliases', {})
```

**Kabul Kriteri:**

```python
config = {"aliases": {"m": "job.plugins.tmdb.movie"}, "tmdb": {}}
aliases = extract_aliases(config)
assert aliases["m"] == "job.plugins.tmdb.movie"
```

---

### 3.6 Config Options Defaults

**Dosya:** `utils/config_loader.py`

**Nerede:** Yeni fonksiyon

**Ne yapılacak:**

```python
DEFAULT_OPTIONS = {
    "debug": False,
    "dry_run": True,
    "force_conflicts": False,
    "memory": {
        "max_plugins_mb": 500,
        "flush_threshold": 0.8,
        "eviction_policy": "completed_first",
        "lazy_cache_size": 10
    }
}

def apply_default_options(config: Dict) -> Dict:
    """options'a default değerleri uygula (deep merge)"""
    from copy import deepcopy
    options = deepcopy(DEFAULT_OPTIONS)
    user_options = config.get('options', {})
    # deep merge
    return deep_merge(options, user_options)
```

**FINAL_DATASETS.yml Referansı:**

```yaml
config_example:
  options:
    memory:
      max_plugins_mb: 500
      flush_threshold: 0.8
```

---

### 3.7 Config Loader Integration

**Dosya:** `utils/config_loader.py`

**Nerede:** `load_config_with_tracking` içinde

**Ne yapılacak:**

```
load_config_with_tracking akışı:
1. YAML load
2. Env var resolution (mevcut)
3. !include processing (3.4)
4. normalize_config (3.3)
5. apply_default_options (3.6)
6. Return
```

**Kabul Kriteri:**

```python
config = load_config_with_tracking("config.yml")
# Eski format da yeni format da çalışmalı
# options defaults uygulanmış olmalı
assert "memory" in config.get("options", {})
```

---

### 3.8 Unit Tests

**Dosya:** `tests/unit/utils/test_config_v2.py` (YENİ)

**Ne yapılacak:**

```
Test cases:
1. test_alias_parser_simple
2. test_alias_parser_nested_path
3. test_alias_parser_no_match
4. test_system_aliases_default
5. test_user_aliases_override_system
6. test_normalize_config_old_format
7. test_normalize_config_new_format
8. test_include_directive_file
9. test_include_directive_directory
10. test_default_options_applied
11. test_config_loader_integration
```

---

## BAĞIMLILIK GRAFİ

```
3.1 AliasParser
     │
     └──→ 3.2 System Alias Defaults
              │
              └──→ 3.5 Alias Extraction

3.3 Config Normalizer ─────┐
                           │
3.4 Include Handler ───────┼──→ 3.7 Loader Integration
                           │
3.6 Default Options ───────┘
                           │
                           └──→ 3.8 Tests
```

---

## **MAIN**.PY ETKİSİ

Bu phase'de `__main__.py`'da DEĞİŞİKLİK YOK.

Loader integration otomatik çalışacak:

- Mevcut config.yml'ler (plugins wrapper ile) → normalize edilir
- Yeni config.yml'ler (flat) → direkt çalışır

---

## TAMAMLAMA KRİTERİ

Phase 3 TAMAMLANDI sayılır eğer:

- [ ] AliasParser utility oluşturuldu
- [ ] System aliases tanımlandı
- [ ] Config normalizer eski formatı destekliyor
- [ ] !include directive çalışıyor (basic)
- [ ] Default options uygulanıyor
- [ ] Mevcut config.yml'ler HALA çalışıyor
- [ ] Tüm testler geçiyor

---

**SONRAKİ PHASE:** `04_PHASE4_STAGE_EXECUTOR.md`
