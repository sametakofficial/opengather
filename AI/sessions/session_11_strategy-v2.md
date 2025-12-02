# SESSION 11 STRATEGY v2 - STATE RESTRUCTURE

```yaml
date: 2025-11-28
type: strategy
status: completed
previous_session: 10
focus: Unified State Structure + Direct Access (No Alias Complexity)
analyst: Strategy Chat
```

---

## ARAŞTIRMA SONUÇLARI

### Endüstri Standartları: Nested vs Flat

| Kaynak | Sonuç |
|--------|-------|
| StackOverflow | **Nested tercih edilir** - Type-safe, okunabilir, statik dillerde kolay deserialize |
| GraphQL | **Nested** - Response structure query structure'ı yansıtır |
| Terraform | **Nested** - `module.vpc.subnet_id`, `var.api_key`, `local.tags` |
| Kubernetes | **Nested** - `spec.containers[0].image`, `metadata.labels` |
| REST API Best Practices | **Nested** - İlişkili veriyi bir arada tut, network call azalt |

**Sonuç:** Senin dediğin doğru. `match.plugins.tmdb.movie` şeklinde nested yapı profesyonel standarttır.

### Mevcut Yapının Sorunları

#### Sorun 1: İki Farklı Template Context

```python
# state/manager.py - İKİ FARKLI FONKSİYON VAR (SAÇMALIK!)

build_template_context()      # → Jinja2 için
build_api_response_for_templates()  # → API response için
```

**Neden iki tane?** Çünkü eski kod spaghetti. İkisi de aynı şeyi yapmalı.

#### Sorun 2: Çirkin Flat İsimler

```python
# MEVCUT (ÇİRKİN)
{
    'globals': {...},           # Execution globals
    'match_globals': {...},     # Match globals - WTF?
    'index': 0,                 # Orphan field
    'execution': {...},         # Duplicate of globals?
    'match': {...},             # Partial match data
    'tmdb': {...},              # MAGIC - plugin flat olarak root'ta
    'renamer': {...},           # MAGIC - plugin flat olarak root'ta
}
```

**Sorunlar:**
- `globals` vs `match_globals` - İsim çakışması kabusu
- `tmdb`, `renamer` root'ta - Magic, explicit değil
- `index` orphan - Nereye ait belli değil
- `execution` vs `globals` - Duplicate

#### Sorun 3: MongoDB Yapısı da Aynı Kaos

```javascript
// MEVCUT MONGODB (ÇİRKİN)
{
  globals: {status, summary, config},
  matches: [
    {
      globals: {          // ← GLOBALS YİNE!
        index, input_path, status, output
      },
      plugins: {
        scanner: {globals: {status}, ...},  // ← HER PLUGİN'DE GLOBALS!
        tmdb: {globals: {status}, ...},     // ← TEKRAR GLOBALS!
      }
    }
  ]
}
```

**Sorun:** `globals` kelimesi 4 farklı yerde, 4 farklı anlam.

---

## YENİ YAPI: NESTED & EXPLICIT

### Prensip: Her Şey Yerinde

```
execution.status      → Execution durumu
execution.config      → Config snapshot
match.index           → Match index
match.input           → Input bilgisi
match.plugins.tmdb    → TMDb sonuçları
match.plugins.renamer → Renamer sonuçları
```

**Hiçbir şey root'ta değil. Her şey doğru namespace'de.**

---

## YENİ STATE YAPISI

### Template Context (TEK YAPIDA)

```python
# YENİ YAPI - NESTED & CLEAN
{
    # Execution seviyesi
    'execution': {
        'id': 'abc123',
        'status': {
            'success': True,
            'total_matches': 2,
            'completed': 2,
            'failed': 0,
            'started_at': '2025-11-28T12:00:00',
            'finished_at': '2025-11-28T12:01:00',
            'duration_ms': 60000
        },
        'config': {
            'options': {'debug': True, 'dry_run': True},
            'plugins': {...},
            'tasks': [...]
        }
    },
    
    # Current match (template rendering sırasında aktif match)
    'match': {
        'index': 0,
        'input': {
            'path': '/path/to/file.mkv',
            'category': 'movie',
            'virtual': False
        },
        'status': {
            'success': True,
            'executed_plugins': ['scanner', 'ffprobe', 'renamer', 'tmdb'],
            'failed_plugins': [],
            'started_at': '...',
            'duration_ms': 2500
        },
        'output': {
            'tasks': [
                {'name': 'print_header', 'success': True, 'rendered': '...'}
            ]
        },
        'plugins': {
            'scanner': {
                'status': {'success': True, 'duration_ms': 10},
                'input': '/path/to/file.mkv',
                'category': 'movie'
            },
            'ffprobe': {
                'status': {'success': True, 'duration_ms': 50},
                'video': {'codec': 'hevc', 'width': 1920, 'height': 1080},
                'audio': [{'codec': 'eac3', 'channels': 6}],
                'container': {'format': 'mkv', 'duration': 7200}
            },
            'renamer': {
                'status': {'success': True, 'duration_ms': 5},
                'parsed': {
                    'movie': {'name': 'Mr. & Mrs. Smith', 'year': 2005},
                    'show': None
                },
                'category': 'movie'
            },
            'tmdb': {
                'status': {'success': True, 'duration_ms': 800},
                'movie': {
                    'id': 1234,
                    'title': {'primary': 'Bay ve Bayan Smith', 'original': 'Mr. & Mrs. Smith'},
                    'year': 2005,
                    'genres': ['Action', 'Comedy'],
                    'people': {'directors': [...], 'cast': [...]}
                },
                'show': None,
                'episode': None
            }
        }
    },
    
    # Tüm match'lere erişim (indexed access için)
    'matches': [
        {...},  # match[0]
        {...}   # match[1]
    ]
}
```

### Template Kullanımı

```jinja2
{# Execution bilgisi #}
{{ execution.status.total_matches }}
{{ execution.config.options.debug }}

{# Current match #}
{{ match.index }}
{{ match.input.path }}
{{ match.input.category }}

{# Plugin data - EXPLICIT PATH #}
{{ match.plugins.tmdb.movie.title.primary }}
{{ match.plugins.renamer.parsed.movie.name }}
{{ match.plugins.ffprobe.video.codec }}

{# Indexed access (başka match'e erişim) #}
{{ matches[0].plugins.tmdb.movie.title.primary }}
```

---

## YENİ MONGODB YAPISI

### Collection: executions

```javascript
{
  _id: ObjectId("..."),
  id: "abc123",
  branch_id: ObjectId("..."),
  
  status: {
    success: true,
    total_matches: 2,
    completed: 2,
    failed: 0,
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 60000
  },
  
  config: {
    options: {debug: true, dry_run: true, hardlink: true},
    plugins: {
      scanner: {enabled: true, targets: [...]},
      tmdb: {enabled: true, api_key: "***", language: "tr-TR"}
    },
    tasks: [
      {name: "print_header", type: "print", template: "..."}
    ]
  },
  
  created_at: ISODate("...")
}
```

### Collection: matches

```javascript
{
  _id: ObjectId("..."),
  execution_id: "abc123",
  index: 0,
  
  input: {
    path: "/path/to/file.mkv",
    category: "movie",
    virtual: false
  },
  
  status: {
    success: true,
    executed_plugins: ["scanner", "ffprobe", "renamer", "tmdb"],
    failed_plugins: [],
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 2500
  },
  
  output: {
    tasks: [
      {name: "print_header", success: true, rendered: "..."}
    ]
  },
  
  // Plugin sonuçları ayrı collection'da (büyük data)
  created_at: ISODate("...")
}
```

### Collection: plugin_results

```javascript
{
  _id: ObjectId("..."),
  execution_id: "abc123",
  match_index: 0,
  plugin_name: "tmdb",
  
  status: {
    success: true,
    started_at: ISODate("..."),
    finished_at: ISODate("..."),
    duration_ms: 800
  },
  
  // Plugin-specific data (opaque to core)
  data: {
    movie: {
      id: 1234,
      title: {primary: "Bay ve Bayan Smith", original: "Mr. & Mrs. Smith"},
      year: 2005,
      genres: ["Action", "Comedy"],
      people: {directors: [...], cast: [...]}
    },
    show: null,
    episode: null
  },
  
  created_at: ISODate("...")
}
```

---

## KARŞILAŞTIRMA TABLOSU

| Aspect | Eski Yapı | Yeni Yapı |
|--------|-----------|-----------|
| Root'ta plugin | ✅ `tmdb.movie` | ❌ `match.plugins.tmdb.movie` |
| globals tekrarı | 4 farklı yerde | ❌ Yok, sadece `status` |
| match_globals | ✅ Var (çirkin) | ❌ Yok, sadece `match` |
| Explicit path | ❌ Magic | ✅ Her şey explicit |
| Template context | 2 farklı fonksiyon | 1 fonksiyon |
| MongoDB tutarlılık | ❌ Farklı yapılar | ✅ Aynı yapı |
| Namespace conflict | ✅ Olabilir | ❌ İmkansız |

---

## ALIAS SİSTEMİ: HYBRID YAKLAŞIM

### Kararım: Alias Resolver KALDIRMIYORUZ, Sadeleştiriyoruz

Senin dediğin doğru: `tmdb.movie` yazmak güzel. Ama magic olmamalı.

**Çözüm:** Sadece SHORTCUT alias'lar, path expansion yok.

```yaml
# config.yml
aliases:
  # SHORTCUT - Sadece current match plugins'e erişim
  tmdb: "match.plugins.tmdb"
  renamer: "match.plugins.renamer"
  ffprobe: "match.plugins.ffprobe"
  scanner: "match.plugins.scanner"
  
  # SEMANTIC shortcuts
  movie: "match.plugins.renamer.parsed.movie"
  show: "match.plugins.renamer.parsed.show"
```

**Kullanım:**
```jinja2
{# Bu ikisi aynı şey #}
{{ tmdb.movie.title.primary }}
{{ match.plugins.tmdb.movie.title.primary }}

{# Semantic alias #}
{{ movie.name }} ({{ movie.year }})
```

**Neden bu iyi:**
1. Explicit path HER ZAMAN çalışır
2. Alias SADECE kısaltma, magic değil
3. config.yml'de tanımlı, gizli değil
4. Plugin ismi değişirse alias güncellenir

---

## EKSİK OLAN: DEPRECATION YOK

Yeni yapıya geçince eski yapı ÇALIŞMAYACAK. Breaking change.

**Neden deprecation yok:**
1. Henüz production kullanımı yok
2. Tek kullanıcı sen
3. Clean break daha iyi

---

## EXECUTION PLAN

### Phase 1: State Models Refactor
**Dosya:** `state/models.py`

```python
@dataclass
class ExecutionState:
    id: str
    status: ExecutionStatus  # Nested dataclass
    config: Dict[str, Any]   # Config snapshot

@dataclass  
class MatchState:
    index: int
    input: MatchInput        # Nested dataclass
    status: MatchStatus      # Nested dataclass
    output: MatchOutput      # Nested dataclass
    plugins: Dict[str, Dict[str, Any]]  # Plugin name -> data
```

### Phase 2: State Manager Refactor
**Dosya:** `state/manager.py`

- `build_template_context()` SİL
- `build_api_response_for_templates()` SİL
- YENİ: `get_context(match_index: int) -> Dict` - TEK FONKSİYON

### Phase 3: Template Manager Simplify
**Dosya:** `core/tasks/template_manager.py`

- Magic plugin injection SİL (lines 206-210)
- Yeni context yapısını kullan
- Alias'ları sadece shortcut olarak tut

### Phase 4: MongoDB Schema Update
**Dosyalar:** Persistence layer

- `globals` → `status` + `config`
- `match.globals` → `match.status` + `match.input` + `match.output`
- `plugin.globals.status` → `plugin.status`

### Phase 5: Tests
- Yeni state yapısı testleri
- Template rendering testleri
- MongoDB schema testleri

---

## DOSYA DEĞİŞİKLİKLERİ

| Dosya | Değişiklik |
|-------|------------|
| `state/models.py` | GÜNCELLE - Nested dataclasses |
| `state/manager.py` | GÜNCELLE - Tek context fonksiyonu |
| `core/tasks/template_manager.py` | SİMPLİFY - Magic kaldır |
| `core/plugins/executor.py` | GÜNCELLE - Yeni state yapısı |
| `persistence/*.py` | GÜNCELLE - Yeni MongoDB schema |
| `tests/unit/state/` | YENİ - State testleri |

---

## SONUÇ

### Kullanıcının İstekleri:

1. ✅ **Tek state yapısı** - `build_template_context` ve `build_api_response_for_templates` birleşti
2. ✅ **Nested yapı** - `match.plugins.tmdb.movie` explicit path
3. ✅ **globals/match_globals kaldırıldı** - Sadece `execution.status`, `match.status`
4. ✅ **MongoDB tutarlı** - Aynı yapı
5. ✅ **Alias hybrid** - Explicit path + optional shortcuts

### Template Örneği:

```jinja2
{# YENİ SİSTEM #}
========== MATCH {{ match.index }} ==========
Input: {{ match.input.path }} [{{ match.input.category | upper }}]

{% if match.plugins.renamer.parsed.movie %}
MOVIE: {{ match.plugins.renamer.parsed.movie.name }} ({{ match.plugins.renamer.parsed.movie.year }})
{% endif %}

{% if match.plugins.tmdb.movie %}
TMDb: {{ match.plugins.tmdb.movie.title.primary }}
Genres: {{ match.plugins.tmdb.movie.genres | join(', ') }}
{% endif %}

============================================================
SUMMARY: {{ execution.status.total_matches }} matches processed
```

---

**Tahmini Süre:** 4-5 saat (breaking change, kapsamlı refactor)

**Bu strateji Session 11 Execution Chat için hazırlandı.**
**Tarih:** 2025-11-28
