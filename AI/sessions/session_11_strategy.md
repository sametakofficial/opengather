# SESSION 11 STRATEGY - TAMAMLANDI

```yaml
date: 2025-11-28
type: strategy
status: completed
previous_session: 10
focus: Direct State Access + Alias System
analyst: Strategy Chat
```

---

## ARAŞTIRMA SONUÇLARI

### 1. Endüstri Standartları Analizi

| Sistem | Yaklaşım | Explicit? |
|--------|----------|-----------|
| **Terraform** | `var.X`, `local.X`, `module.X` prefix'leri | ✅ Evet |
| **Ansible** | `hostvars[host]`, `ansible_facts.eth0.ipv4` | ✅ Evet |
| **Airflow** | `ti.xcom_pull(task_ids='X')` | ✅ Evet |
| **Kubernetes** | `configMapKeyRef.name`, `secretKeyRef.name` | ✅ Evet |

**Sonuç:** Tüm profesyonel sistemler **explicit prefix/namespace** kullanıyor.

**Terraform Örnek:**
```hcl
# EXPLICIT - Kaynak tipi belirtilmek zorunda
var.api_key           # Input variable
local.common_tags     # Local value
module.vpc.subnet_id  # Module output
aws_instance.web.id   # Resource attribute
```

**Ansible Örnek:**
```jinja2
# EXPLICIT - Bracket veya dot notation
{{ hostvars['webserver'].ansible_host }}
{{ ansible_facts.eth0.ipv4.address }}
```

---

### 2. Mevcut State Yapısı

**state/manager.py → `build_template_context()`** döndürüyor:
```python
{
    'globals': {...},           # Execution globals
    'match_globals': {...},     # Current match globals
    'index': 0,
    'execution': {...},
    'match': {...},
    'matches': [...]            # All matches
    # + MAGIC: Her plugin_name direkt root'a ekleniyor
}
```

**state/manager.py → `build_api_response_for_templates()`** döndürüyor:
```python
{
    'globals': {...},
    'matches': [
        {
            'globals': {...},
            'plugins': {'tmdb': {...}, 'renamer': {...}}
        }
    ]
}
```

**SORUN:** `build_template_context()` lines 483-486 plugin'leri MAGIC olarak root'a ekliyor:
```python
for plugin_name, plugin_data in match.plugins.items():
    context[plugin_name] = plugin_data  # ← MAGIC!
```

---

### 3. Template Manager Analizi

**Mevcut Magic Noktaları:**

1. **Lines 206-210:** Plugin isimlerini root context'e inject ediyor
```python
for plugin_name, plugin_data in match_plugins.items():
    jinja_context[plugin_name] = plugin_data  # ← MAGIC!
```

2. **Mevcut Alias Sistemi:** Çalışıyor ama kullanılmıyor
```python
DEFAULT_ALIASES = {
    'e': 'execution',
    'm': 'match',
    'g': 'globals',
}
```

3. **User Aliases:** config.yml'den okunuyor (lines 212-217)

---

### 4. Expects Sistemi Analizi

**executor.py → `_extract_available_data()`**:
```python
def _extract_available_data(self, result: Dict[str, Any]) -> set:
    # 'renamer.parsed' formatında key'ler döndürüyor
    for key, value in result.items():
        available.add(key)
        if isinstance(value, dict):
            for subkey in value.keys():
                available.add(f"{key}.{subkey}")  # ← renamer.parsed
```

**resolver.py → `check_expects()`**:
```python
def check_expects(self, plugin_name: str, available_data: Set[str]) -> bool:
    for expect in expects:
        if expect not in available_data:  # ← Direct match
            return False
```

**Mevcut:** `expects: [renamer.parsed]` → Çalışıyor (magic)

---

## TASARIM KARARLARI

### Karar 1: Alias Tanım Yeri

**Cevap:** `config.yml` + `DEFAULT_ALIASES` (kod içinde)

```yaml
# config.yml
aliases:
  p: "plugins"           # {{ p.tmdb.movie.title }}
  m: "match"             # {{ m.index }}
  g: "globals"           # {{ g.status.matches }}
  movie: "plugins.renamer.parsed.movie"  # {{ movie.name }}
```

**Neden:**
- Tek merkezi tanım
- Plugin'ler kendi alias'larını tanımlayamaz (karmaşıklık önlenir)
- User override imkanı

---

### Karar 2: Default Aliases

| Alias | Hedef | Kullanım |
|-------|-------|----------|
| `p` | `plugins` | `{{ p.tmdb.movie.title }}` |
| `m` | `match` | `{{ m.index }}`, `{{ m.input_path }}` |
| `g` | `globals` | `{{ g.status.matches }}` |
| `e` | `execution` | `{{ e.id }}` |

**Shortcut Aliases (Optional, config.yml'de tanımlı):**
| Alias | Hedef | Kullanım |
|-------|-------|----------|
| `movie` | `plugins.renamer.parsed.movie` | `{{ movie.name }}` |
| `show` | `plugins.renamer.parsed.show` | `{{ show.name }}` |

---

### Karar 3: Plugin-Specific Aliases

**Kaldırıldı.** Karmaşıklık ekliyor. Sadece user aliases yeterli.

manifest.yml'de alias tanımı DESTEKLENMEYECEK.

---

### Karar 4: Backward Compatibility

**Yaklaşım:** Deprecation warning + 1 major version geçiş süresi

**Phase 1 (v2.x):**
- Magic çalışmaya devam eder
- Yeni alias sistemi paralel çalışır
- Console warning: "Deprecated: Use {{ p.tmdb }} instead of {{ tmdb }}"

**Phase 2 (v3.0):**
- Magic kaldırılır
- Sadece alias sistemi çalışır

**Bu session:** Sadece Phase 1 yapılacak.

---

### Karar 5: expects Syntax

**Mevcut (Magic):**
```yaml
expects:
  - renamer.parsed
```

**Yeni (Explicit):**
```yaml
expects:
  - p.renamer.parsed   # veya plugins.renamer.parsed
```

**Backward Compat:** Her iki syntax de çalışacak (Phase 1)

---

## EXECUTION PLAN

### Phase 1: Alias Resolver Modülü
**Dosya:** `core/tasks/alias_resolver.py` (YENİ)

```python
class AliasResolver:
    DEFAULT_ALIASES = {'p': 'plugins', 'm': 'match', 'g': 'globals', 'e': 'execution'}
    
    def __init__(self, user_aliases: Dict[str, str] = None):
        self.aliases = {**self.DEFAULT_ALIASES, **(user_aliases or {})}
    
    def expand(self, path: str) -> str:
        """
        Expand alias in path.
        
        p.tmdb.movie → plugins.tmdb.movie
        movie.name → plugins.renamer.parsed.movie.name (if 'movie' alias exists)
        """
        parts = path.split('.')
        first = parts[0]
        if first in self.aliases:
            expanded = self.aliases[first]
            return f"{expanded}.{'.'.join(parts[1:])}" if len(parts) > 1 else expanded
        return path
```

### Phase 2: Template Manager Refactor
**Dosya:** `core/tasks/template_manager.py`

**Değişiklikler:**
1. AliasResolver import et
2. Lines 206-210: Magic injection'ı deprecation warning ile koru
3. Alias expansion logic ekle
4. Context yapısını düzelt: `plugins`, `match`, `globals` namespace'leri

**Yeni Context Yapısı:**
```python
jinja_context = {
    # Explicit namespaces
    'plugins': match_plugins,      # {{ plugins.tmdb.movie }}
    'match': match_context,        # {{ match.index }}
    'globals': api_globals,        # {{ globals.status }}
    'execution': exec_context,     # {{ execution.id }}
    'matches': matches,            # {{ matches[0].plugins.tmdb }}
    
    # Aliases (shortcuts)
    'p': match_plugins,            # {{ p.tmdb.movie }}
    'm': match_context,
    'g': api_globals,
    'e': exec_context,
    
    # User aliases (from config)
    # 'movie': resolved_movie_data,
    
    # DEPRECATED (backward compat)
    # 'tmdb': match_plugins['tmdb'],  # + warning
}
```

### Phase 3: Expects System Refactor
**Dosyalar:** `executor.py`, `resolver.py`

**Değişiklikler:**
1. `_extract_available_data()`: `plugins.renamer.parsed` formatında key üret
2. `check_expects()`: AliasResolver kullanarak alias'ları expand et
3. Her iki format da kabul et (backward compat)

### Phase 4: Test ve Dokümantasyon
1. Unit testler: alias_resolver, template_manager
2. Integration test: expects with aliases
3. PLUGIN_SDK.md güncelle

---

## DOSYA DEĞİŞİKLİKLERİ ÖZETİ

| Dosya | Değişiklik |
|-------|------------|
| `core/tasks/alias_resolver.py` | YENİ - Alias engine |
| `core/tasks/template_manager.py` | GÜNCELLE - Alias support |
| `core/plugins/executor.py` | GÜNCELLE - `_extract_available_data()` |
| `core/plugins/resolver.py` | GÜNCELLE - `check_expects()` |
| `tests/unit/core/test_alias_resolver.py` | YENİ - Tests |
| `docs/PLUGIN_SDK.md` | GÜNCELLE - Alias documentation |

---

## KRİTİK NOTLAR

1. **Basit tut** - Overengineering yok
2. **Backward compat** - Magic hala çalışır, deprecation warning
3. **Tek altyapı** - Alias resolver her yerde kullanılır
4. **Test first** - Her değişiklik için test

---

## EXECUTION CHAT İÇİN TALİMATLAR

1. `alias_resolver.py` oluştur
2. `template_manager.py` güncelle (alias support + deprecation)
3. `executor.py` ve `resolver.py` güncelle
4. Unit testler yaz
5. Integration test ile doğrula
6. `python -m pytest tests/ -v` ile 263+ test geçtiğini doğrula

**Tahmini Süre:** 2-3 saat

---

**Bu strateji Session 11 Execution Chat için hazırlandı.**
**Tarih:** 2025-11-28
