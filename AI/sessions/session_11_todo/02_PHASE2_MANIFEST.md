# PHASE 2: MANIFEST SCHEMA

```yaml
öncelik: P2
tahmini_süre: 3-4 saat
bağımlılık: Phase 1 (State Models)
hedef: Yeni manifest alanları, eski alanlar backward compat
risk: ORTA (discovery.py değişecek ama fallback var)
```

---

## MEVCUT DURUM ANALİZİ

### sdk/manifest.py (PluginManifest)

```python
# MEVCUT ALANLAR
name: str
version: str
description: Optional[str]
category: Literal["input", "output"]  # → stage olacak
class_name: Optional[str]
depends_on: List[str]                 # → requires olacak
expects: List[str]                    # → requires içine merge
capabilities: List[str]               # → KALDIRILACAK
provides: List[str]                   # → action-based olacak
hooks: List[str]
listens_to: List[str]
config_schema: Optional[Dict]
```

### HEDEF ALANLAR (FINAL_DATASETS.yml)

```yaml
name: tmdb
version: 1.0.0
description: TMDb metadata provider
stage: data # YENİ (category yerine)
requires: # YENİ (depends_on + expects birleşimi)
  - job.plugins.renamer.parsed
provides: # GÜNCELLENDİ (action-based)
  - http.request
  - state.update
trigger_rule: all_success # YENİ
reactive: false # YENİ
class_name: TMDbPlugin
entry_point: client.py # YENİ
config_schema: ...
```

---

## TASK LİSTESİ

### 2.1 Stage Enum Tanımlama

**Dosya:** `core/plugins/sdk/types.py`

**Nerede:** Dosya içinde yeni enum

**Ne yapılacak:**

```python
class Stage(str, Enum):
    INPUT = "input"
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"
```

**Kabul Kriteri:**

```python
from archiverr.core.plugins.sdk.types import Stage
assert Stage.DATA.value == "data"
```

---

### 2.2 TriggerRule Enum

**Dosya:** `core/plugins/sdk/types.py`

**Nerede:** Stage enum'dan sonra

**Ne yapılacak:**

```python
class TriggerRule(str, Enum):
    ALL_SUCCESS = "all_success"  # default
    ONE_SUCCESS = "one_success"
    ALL_DONE = "all_done"
    ALL_FAIL = "all_fail"
    NONE_FAIL = "none_fail"
```

**FINAL_DATASETS.yml Referansı:**

```yaml
trigger_rules:
  - all_success
  - one_success
  - all_done
  - all_fail
  - none_fail
```

---

### 2.3 PluginManifest Güncelleme - Stage Ekleme

**Dosya:** `core/plugins/sdk/manifest.py`

**Nerede:** Mevcut `category` field yanına

**Ne yapılacak:**

```python
# ESKİ (KALACAK - backward compat)
category: Optional[Literal["input", "output"]] = None

# YENİ
stage: Optional[Literal["input", "parse", "data", "output"]] = None
```

**Kabul Kriteri:**

```python
# Her ikisi de çalışmalı
m1 = PluginManifest(name="x", version="1.0", category="input")
m2 = PluginManifest(name="y", version="1.0", stage="data")
```

---

### 2.4 PluginManifest Güncelleme - Requires Ekleme

**Dosya:** `core/plugins/sdk/manifest.py`

**Nerede:** Mevcut `depends_on` ve `expects` yanına

**Ne yapılacak:**

```python
# ESKİ (KALACAK)
depends_on: List[str] = Field(default_factory=list)
expects: List[str] = Field(default_factory=list)

# YENİ
requires: List[str] = Field(default_factory=list)
```

**Not:** Validation'da `requires` prefix kontrolü YOK (Phase 5'te)

---

### 2.5 PluginManifest Güncelleme - Trigger/Reactive

**Dosya:** `core/plugins/sdk/manifest.py`

**Nerede:** `provides` field'dan sonra

**Ne yapılacak:**

```python
trigger_rule: str = Field(default="all_success")
reactive: bool = Field(default=False)
entry_point: str = Field(default="client.py")
```

---

### 2.6 Computed Property: effective_stage

**Dosya:** `core/plugins/sdk/manifest.py`

**Nerede:** Class sonunda property olarak

**Ne yapılacak:**

```python
@property
def effective_stage(self) -> str:
    """stage varsa stage, yoksa category'den dönüştür"""
    if self.stage:
        return self.stage
    # category → stage mapping
    if self.category == "input":
        return "input"
    elif self.category == "output":
        return "output"  # parse/data bilinmiyor, default output
    return "output"
```

**Kabul Kriteri:**

```python
m = PluginManifest(name="x", version="1", category="input")
assert m.effective_stage == "input"

m2 = PluginManifest(name="y", version="1", stage="data")
assert m2.effective_stage == "data"
```

---

### 2.7 Computed Property: effective_requires

**Dosya:** `core/plugins/sdk/manifest.py`

**Nerede:** `effective_stage` property'den sonra

**Ne yapılacak:**

```python
@property
def effective_requires(self) -> List[str]:
    """requires varsa requires, yoksa depends_on + expects birleştir"""
    if self.requires:
        return self.requires
    # Legacy: depends_on + expects → requires
    combined = []
    for dep in self.depends_on:
        combined.append(f"provides.state.update")  # eski format varsayım
    for exp in self.expects:
        combined.append(f"job.{exp}")  # expects → job.* prefix
    return combined
```

---

### 2.8 Discovery.py Güncelleme

**Dosya:** `core/plugins/discovery.py`

**Nerede:** `_load_plugin_metadata` metodu içinde

**Ne yapılacak:**

```
Manifest yüklendikten sonra:
1. effective_stage hesapla
2. effective_requires hesapla
3. metadata'ya ekle:
   metadata['_effective_stage'] = manifest.effective_stage
   metadata['_effective_requires'] = manifest.effective_requires
```

**Kabul Kriteri:**

```python
plugins = discovery.discover()
tmdb = plugins['tmdb']
assert '_effective_stage' in tmdb
```

---

### 2.9 Stage Ordering Utility

**Dosya:** `core/plugins/sdk/types.py`

**Nerede:** Enum'lardan sonra

**Ne yapılacak:**

```python
STAGE_ORDER = {
    "input": 0,
    "parse": 1,
    "data": 2,
    "output": 3
}

def get_stage_order(stage: str) -> int:
    return STAGE_ORDER.get(stage, 99)
```

**Kabul Kriteri:**

```python
assert get_stage_order("input") < get_stage_order("parse")
assert get_stage_order("data") < get_stage_order("output")
```

---

### 2.10 Unit Tests

**Dosya:** `tests/unit/plugins/test_manifest_v2.py` (YENİ)

**Ne yapılacak:**

```
Test cases:
1. test_manifest_with_stage
2. test_manifest_with_category_backward_compat
3. test_effective_stage_from_stage
4. test_effective_stage_from_category
5. test_manifest_with_requires
6. test_effective_requires_from_depends_expects
7. test_trigger_rule_default
8. test_stage_ordering
9. test_discovery_adds_effective_fields
10. test_existing_plugins_still_load
```

**Kabul Kriteri:**

```bash
pytest tests/unit/plugins/test_manifest_v2.py -v
# ALL PASS

# VE mevcut testler de geçmeli
pytest tests/unit/plugins/ -v
# ALL PASS
```

---

## BAĞIMLILIK GRAFİ

```
2.1 Stage enum
     │
     └──→ 2.3 PluginManifest stage field
              │
              └──→ 2.6 effective_stage property

2.2 TriggerRule enum
     │
     └──→ 2.5 trigger_rule field

2.4 requires field
     │
     └──→ 2.7 effective_requires property

2.6 + 2.7 ──→ 2.8 Discovery güncelleme
                   │
                   └──→ 2.9 Stage ordering
                            │
                            └──→ 2.10 Tests
```

---

## MEVCUT PLUGİNLERE ETKİ

### ETKİLENEN PLUGİNLER (sonra migrate edilecek)

| Plugin      | Mevcut category | Hedef stage | Öncelik |
| ----------- | --------------- | ----------- | ------- |
| scanner     | input           | input       | P1      |
| file_reader | input           | input       | P2      |
| renamer     | output          | parse       | P1      |
| tmdb        | output          | data        | P1      |
| tvdb        | output          | data        | P2      |
| ffprobe     | output          | data        | P2      |
| tasker      | output          | output      | P1      |

**NOT:** Bu phase'de pluginler DEĞİŞMİYOR. Sadece manifest schema'sı yeni alanları kabul ediyor.

---

## TAMAMLAMA KRİTERİ

Phase 2 TAMAMLANDI sayılır eğer:

- [ ] Stage ve TriggerRule enum'ları oluşturuldu
- [ ] PluginManifest yeni alanları kabul ediyor
- [ ] effective_stage ve effective_requires çalışıyor
- [ ] Discovery yeni computed alanları ekliyor
- [ ] Mevcut pluginler (category ile) HALA yüklenebiliyor
- [ ] Tüm testler geçiyor

---

**SONRAKİ PHASE:** `03_PHASE3_CONFIG.md`
