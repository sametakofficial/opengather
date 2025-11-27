# Mimari Referans

> **Amaç**: Yeni AI'ın hızlıca anlayacağı şekilde sistem mimarisi

---

## 🎯 Temel Felsefe: Plugin-Agnostic

**Core sistem plugin'ler hakkında HİÇBİR ŞEY bilmez.**

```
Core Sistem BİLEBİLİR:
✅ Plugin kategorisi (input/output) - plugin.json'dan
✅ Plugin bağımlılıkları (depends_on) - plugin.json'dan
✅ Plugin expects listesi - plugin.json'dan
✅ Generic plugin config yapısı - dict olarak

Core Sistem BİLEMEZ:
❌ Plugin-specific veri yapıları (movie, show, episode, season)
❌ Plugin adları core kodda (tmdb, tvdb, tvmaze, omdb, renamer)
❌ Plugin-specific configuration schemas
❌ Media tipi varsayımları (movies vs shows)
```

### Bu Neden Önemli?

1. **Extensibility**: Yeni plugin eklemek için core koda dokunmaya gerek yok
2. **Maintainability**: Plugin değişiklikleri core'u etkilemez
3. **Testing**: Core testler plugin'lerden bağımsız
4. **Decoupling**: Her plugin kendi domain logic'ini yönetir

### Örnek: YANLIŞ vs DOĞRU

```python
# ❌ YANLIŞ - Core kodda plugin adı kullanmak
if "tmdb" in result["plugins"]:
    movie = result["plugins"]["tmdb"]["movie"]
    print(f"Found movie: {movie['title']}")

# ✅ DOĞRU - Generic pattern
for plugin_name, plugin_data in result["plugins"].items():
    if plugin_data.get("status", {}).get("success"):
        print(f"Plugin {plugin_name} succeeded")
```

---

## 📁 Dizin Yapısı

```
src/archiverr/
│
├── api/                        # FastAPI API Layer
│   ├── __init__.py
│   ├── main.py                 # App factory, lifespan
│   ├── middleware/             # Rate limiting, CORS
│   │   ├── __init__.py
│   │   └── rate_limiter.py
│   ├── deps/                   # 🆕 Dependency Injection
│   │   ├── __init__.py
│   │   ├── database.py         # Motor + PyMongo connections
│   │   └── common.py           # AsyncPersistenceWrapper
│   ├── database.py             # ⚠️ DEPRECATED
│   ├── dependencies.py         # ⚠️ DEPRECATED
│   └── v1/                     # API version 1
│       ├── __init__.py
│       ├── router.py           # Main v1 router
│       ├── executions/
│       │   ├── router.py       # Execution CRUD
│       │   └── schemas.py      # Pydantic models
│       ├── matches/
│       │   ├── router.py       # Match queries
│       │   └── schemas.py      # 🆕
│       ├── run/
│       │   ├── router.py       # Trigger execution
│       │   └── schemas.py      # 🆕
│       ├── system/
│       │   ├── router.py       # Health, status
│       │   └── schemas.py      # 🆕
│       └── versioning/
│           ├── router.py       # Git-like branches/commits
│           └── schemas.py
│
├── cli/                        # CLI entry points
│   ├── __init__.py
│   └── main.py                 # CLI commands
│
├── core/                       # Business Logic
│   ├── __init__.py
│   ├── plugins/                # Plugin system
│   │   ├── __init__.py
│   │   ├── discovery.py        # Scan plugins/*/plugin.json
│   │   ├── loader.py           # Load enabled plugins
│   │   ├── resolver.py         # Dependency resolution (topological sort)
│   │   └── executor.py         # Execute plugins
│   ├── services/               # Application services
│   │   ├── __init__.py
│   │   └── execution_service.py # Main execution orchestration
│   └── tasks/                  # Task execution
│       ├── __init__.py
│       ├── task_manager.py     # Task execution
│       └── template_manager.py # Jinja2 rendering
│
├── events/                     # Event bus system
│   ├── __init__.py
│   └── bus.py                  # EventBus class
│
├── infrastructure/             # External services
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py         # Exports
│   │   ├── interface.py        # PersistenceInterface (abstract)
│   │   ├── motor.py            # 🆕 Async Motor (API)
│   │   ├── mongodb.py          # Sync PyMongo (CLI)
│   │   ├── mock.py             # File-based mock
│   │   └── connection.py       # DatabaseConnection helper
│   └── repositories/           # 🔜 Data access layer (TODO)
│       └── base.py
│
├── state/                      # State management
│   ├── __init__.py
│   ├── manager.py              # GlobalStateManager (singleton)
│   └── models.py               # ExecutionState, MatchState, PluginResult
│
├── plugins/                    # Domain plugins
│   ├── __init__.py
│   ├── base.py                 # BasePlugin, InputPlugin, OutputPlugin
│   ├── scanner/
│   │   ├── plugin.json
│   │   └── client.py
│   ├── file_reader/
│   │   ├── plugin.json
│   │   └── client.py
│   ├── ffprobe/
│   │   ├── plugin.json
│   │   └── client.py
│   ├── renamer/
│   │   ├── plugin.json
│   │   ├── client.py
│   │   └── parser.py
│   ├── tmdb/
│   │   ├── plugin.json
│   │   └── client.py
│   ├── tvdb/
│   │   ├── plugin.json
│   │   └── client.py
│   ├── omdb/
│   │   ├── plugin.json
│   │   └── client.py
│   └── tvmaze/
│       ├── plugin.json
│       └── client.py
│
├── utils/                      # Utilities
│   ├── __init__.py
│   ├── config_loader.py        # YAML + .env loading
│   ├── debug.py                # Live logging (Debugger)
│   ├── filters.py              # Jinja2 filters
│   └── templates.py            # Template rendering utilities
│
└── __main__.py                 # Entry point: python -m archiverr

tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── unit/                       # 🆕 Fast, isolated tests
│   ├── core/
│   ├── state/
│   └── api/
├── integration/                # 🆕 Service-level tests
└── e2e/                        # 🆕 Full system tests
```

---

## 🔄 Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXECUTION FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CONFIG LOADING                                                          │
│     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│     │ config.yml  │ + + │   .env      │ = = │   config    │                │
│     └─────────────┘     └─────────────┘     └─────────────┘                │
│                                                                             │
│  2. PLUGIN DISCOVERY                                                        │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  plugins/*/plugin.json  →  metadata dict                │            │
│     │  {scanner: {...}, renamer: {...}, tmdb: {...}}         │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
│  3. PLUGIN LOADING                                                          │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  Filter by config.plugins.*.enabled                     │            │
│     │  Import plugin classes, instantiate                     │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
│  4. DEPENDENCY RESOLUTION                                                   │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  Topological sort by depends_on                         │            │
│     │  → [[scanner], [renamer, ffprobe], [tmdb, omdb]]       │            │
│     │     (parallel groups)                                   │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
│  5. INPUT PLUGIN EXECUTION                                                  │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  scanner.execute(config)                                │            │
│     │  → matches: ["/path/file1.mkv", "/path/file2.mkv"]     │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
│  6. OUTPUT PLUGIN EXECUTION (per match)                                     │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  For each match:                                        │            │
│     │    renamer.execute(match_data)  → parsed title         │            │
│     │    tmdb.execute(match_data)     → metadata             │            │
│     │    ffprobe.execute(match_data)  → media info           │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
│  7. TASK EXECUTION (per match)                                              │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  Jinja2 template rendering                              │            │
│     │  print tasks → stdout                                   │            │
│     │  save tasks  → files                                    │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
│  8. STATE PERSISTENCE                                                       │
│     ┌─────────────────────────────────────────────────────────┐            │
│     │  MongoDB collections:                                   │            │
│     │  - executions (execution state)                         │            │
│     │  - matches (per-match data)                             │            │
│     │  - plugin_results (plugin outputs)                      │            │
│     │  - branches/commits (git-like versioning)               │            │
│     └─────────────────────────────────────────────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ MongoDB Collections

```
archiverr/
│
├── executions                  # Yürütme kayıtları
│   └── Document:
│       {
│         "_id": "exec_abc12345",
│         "status": "completed",        # pending, running, completed, failed
│         "started_at": ISODate,
│         "finished_at": ISODate,
│         "duration_ms": 60000,
│         "success": true,
│         "total_matches": 10,
│         "completed_matches": 8,
│         "failed_matches": 2,
│         "config_snapshot": {...}      # Config at execution time
│       }
│
├── matches                     # Eşleşme kayıtları
│   └── Document:
│       {
│         "_id": "match_abc12345_0",
│         "execution_id": "exec_abc12345",
│         "index": 0,
│         "input_path": "/path/to/file.mkv",
│         "status": "completed",
│         "started_at": ISODate,
│         "finished_at": ISODate,
│         "duration_ms": 5000,
│         "plugins": {                  # Plugin results embedded
│           "scanner": {...},
│           "renamer": {...},
│           "tmdb": {...}
│         }
│       }
│
├── plugin_results              # Plugin sonuçları (opsiyonel, detaylı)
│   └── Document:
│       {
│         "_id": "result_abc123",
│         "execution_id": "exec_abc12345",
│         "match_index": 0,
│         "plugin_name": "tmdb",
│         "success": true,
│         "started_at": ISODate,
│         "finished_at": ISODate,
│         "duration_ms": 1200,
│         "data": {...},                # Plugin-specific data
│         "error": null
│       }
│
├── branches                    # Git-like branches
│   └── Document:
│       {
│         "_id": "branch_abc123",
│         "name": "main",
│         "description": "Default branch",
│         "is_default": true,
│         "head_commit_id": "commit_xyz789",
│         "created_at": ISODate,
│         "updated_at": ISODate
│       }
│
└── commits                     # Git-like commits
    └── Document:
        {
          "_id": "commit_xyz789",
          "branch_id": "branch_abc123",
          "execution_id": "exec_abc12345",
          "parent_commit_id": "commit_prev123",
          "message": "Execution abc12345",
          "created_at": ISODate,
          "execution_summary": {
            "total_matches": 10,
            "successful_matches": 8,
            "failed_matches": 2
          }
        }
```

---

## 🔌 Plugin Yapısı

### plugin.json Format

```json
{
  "name": "plugin_name",
  "version": "1.0.0",
  "description": "Plugin description",
  "category": "input",          // "input" veya "output"
  "class_name": "PluginNamePlugin",
  "depends_on": [],             // Bağımlı plugin listesi
  "expects": [],                // Beklenen veri yolları
  "categories": []              // Desteklenen kategoriler (movie, show)
}
```

### Plugin Class Yapısı

```python
# plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BasePlugin(ABC):
    """Base class for all plugins."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._metadata = {}  # Set by loader
    
    @abstractmethod
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plugin logic."""
        pass
    
    @property
    def name(self) -> str:
        return self._metadata.get("name", self.__class__.__name__)
    
    @property
    def category(self) -> str:
        return self._metadata.get("category", "unknown")


class InputPlugin(BasePlugin):
    """Base class for input plugins (scanner, file_reader)."""
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input plugins return matches.
        
        Returns:
            {
                "status": {"success": True, ...},
                "matches": ["/path/file1.mkv", "/path/file2.mkv"]
            }
        """
        raise NotImplementedError


class OutputPlugin(BasePlugin):
    """Base class for output plugins (renamer, tmdb, ffprobe)."""
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Output plugins process individual matches.
        
        Args:
            data: Match data including previous plugin results
        
        Returns:
            {
                "status": {"success": True, ...},
                "plugin_specific_data": {...}
            }
        """
        raise NotImplementedError
```

### Örnek Plugin: TMDb

```python
# plugins/tmdb/client.py
from archiverr.plugins.base import OutputPlugin

class TMDbPlugin(OutputPlugin):
    """TMDb metadata plugin."""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.language = config.get("lang", "en-US")
    
    def execute(self, data):
        # Get parsed title from renamer
        renamer_data = data.get("renamer", {})
        parsed = renamer_data.get("parsed", {})
        
        movie_data = parsed.get("movie")
        if movie_data:
            return self._search_movie(movie_data)
        
        show_data = parsed.get("show")
        if show_data:
            return self._search_show(show_data)
        
        return {
            "status": {"success": False, "error": "No parsed data"},
        }
    
    def _search_movie(self, movie_data):
        title = movie_data.get("title")
        year = movie_data.get("year")
        
        # TMDb API call...
        result = self._api_search_movie(title, year)
        
        return {
            "status": {
                "success": True,
                "started_at": "...",
                "finished_at": "...",
                "duration_ms": 1200
            },
            "movie": {
                "id": result["id"],
                "title": result["title"],
                "original_title": result["original_title"],
                "release_date": result["release_date"],
                "overview": result["overview"],
                "poster_path": result["poster_path"],
                "backdrop_path": result["backdrop_path"],
                "vote_average": result["vote_average"],
                "genres": result["genres"],
                "runtime": result["runtime"]
            }
        }
```

---

## 🔑 Kritik Dosyalar ve Ne Yaparlar

| Dosya | Ne Yapar | Önem |
|-------|----------|------|
| `api/deps/database.py` | Motor + PyMongo bağlantı yönetimi | 🔴 Kritik |
| `infrastructure/database/motor.py` | Async MongoDB singleton | 🔴 Kritik |
| `state/manager.py` | GlobalStateManager (tüm state burada) | 🔴 Kritik |
| `core/plugins/executor.py` | Plugin execution logic | 🔴 Kritik |
| `core/plugins/resolver.py` | Dependency resolution | 🟠 Yüksek |
| `core/plugins/discovery.py` | Plugin discovery | 🟠 Yüksek |
| `core/tasks/template_manager.py` | Jinja2 rendering | 🟡 Orta |
| `utils/debug.py` | Debugger (live logging) | 🟡 Orta |

---

## ⚙️ Environment Variables

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017     # Connection string
MONGODB_DATABASE=archiverr                # Database name
ARCHIVERR_DB_BACKEND=mongodb              # "mongodb" veya "mock"

# API
RATE_LIMIT_ENABLED=true                   # Rate limiting toggle

# API Keys (.env dosyasında olmalı, config.yml'da OLMAMALI!)
TMDB_API_KEY=your_api_key_here
TVDB_API_KEY=your_api_key_here
OMDB_API_KEY=your_api_key_here
```

---

## 🧪 Test Komutları

```bash
# Tüm unit testleri çalıştır (hızlı)
cd /home/samet/Workspace/archiverr
python -m pytest tests/unit/ -v

# Sadece core testler
python -m pytest tests/unit/core/ -v

# Sadece state testler
python -m pytest tests/unit/state/ -v

# Sadece API testler
python -m pytest tests/unit/api/ -v

# Tüm testler
python -m pytest tests/ -v

# Syntax kontrolü
find src -name "*.py" -exec python -m py_compile {} \;

# Specific test
python -m pytest tests/unit/core/test_plugin_discovery.py::TestDependencyResolver -v
```

---

## 🚨 Bilinen Sorunlar

### 1. İki MongoDB Bağlantı Sistemi
- **API**: Motor (async) → `infrastructure/database/motor.py`
- **CLI**: PyMongo (sync) → `infrastructure/database/mongodb.py`
- **Sorun**: Kod tekrarı, tutarsız davranış riski
- **Çözüm**: Repository Pattern (TODO)

### 2. State Manager Sync
- **Konum**: `state/manager.py`
- **Sorun**: `save_execution()` sync call yapıyor
- **Etki**: API'de blocking I/O
- **Çözüm**: Async metodlar ekle (TODO)

### 3. Response Format Tutarsızlığı
- `items` vs `matches`
- `matchGlobals` vs `match_globals`
- **Çözüm**: Standardize et (TODO)

### 4. Plugin-Dependent Tests
- `test_full_pipeline.py` - Hardcoded plugin names
- `test_integration.py` - Real plugins required
- **Çözüm**: Mock fixtures (TODO)
