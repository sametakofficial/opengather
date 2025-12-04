# PROJE YAPISI

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/08_IMPLEMENTATION.md
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- orchestrator.py henuz YOK (current: tum logic __main__.py'de)
- services.py henuz YOK (current: SDK icinde)
- StageExecutor henuz YOK (current: 2 category: input/output)
```

---

## CURRENT vs TARGET

```
CURRENT:                           TARGET:
__main__.py (392 satir)            __main__.py (~50 satir)
                                   orchestrator.py (~200 satir)

core/plugins/executor.py           core/plugins/stage_executor.py
core/plugins/sdk/                   core/plugins/services.py

InputPlugin, OutputPlugin          4-stage base classes
```

---

## 1. DİZİN YAPISI

```
archiverr/
├── src/
│   └── archiverr/
│       ├── __init__.py
│       ├── __main__.py              # Entry point (minimal)
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── orchestrator.py      # Main coordinator
│       │   │
│       │   ├── plugins/
│       │   │   ├── __init__.py
│       │   │   ├── base.py          # BasePlugin, PluginResult
│       │   │   ├── registry.py      # Discovery + Loading
│       │   │   ├── resolver.py      # Dependency resolution
│       │   │   ├── executor.py      # Stage execution
│       │   │   ├── services.py      # PluginServices interface
│       │   │   └── validators.py    # RequiresValidator
│       │   │
│       │   │   # NOT: core/tasks YOK!
│       │   │   # Tasker bir PLUGIN (stage: output)
│       │   │   # Template rendering PluginServices içinde
│       │   │
│       │   └── validation/
│       │       ├── __init__.py
│       │       ├── config.py        # ConfigValidator
│       │       ├── manifest.py      # ManifestValidator
│       │       └── dependency.py    # DependencyValidator
│       │
│       ├── state/
│       │   ├── __init__.py
│       │   ├── models.py            # RunState, JobState, etc.
│       │   └── manager.py           # StateManager
│       │
│       ├── events/
│       │   ├── __init__.py
│       │   └── bus.py               # EventBus
│       │
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── config/
│       │   │   ├── __init__.py
│       │   │   ├── loader.py        # Config loading
│       │   │   └── validator.py     # Config validation
│       │   │
│       │   ├── persistence/
│       │   │   ├── __init__.py
│       │   │   ├── interface.py     # PersistenceInterface
│       │   │   ├── pymongo.py       # Sync MongoDB
│       │   │   ├── motor.py         # Async MongoDB
│       │   │   └── mock.py          # File-based mock
│       │   │
│       │   └── memory/
│       │       ├── __init__.py
│       │       ├── tracker.py       # MemoryTracker
│       │       ├── flush.py         # FlushManager
│       │       └── loader.py        # LazyLoader
│       │
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── debug.py             # Debugger
│       │   └── filters.py           # Jinja2 filters
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py              # FastAPI app
│       │   └── routes/
│       │       ├── runs.py
│       │       └── jobs.py
│       │
│       └── plugins/
│           ├── __init__.py
│           ├── scanner/             # stage: input
│           │   ├── manifest.yml
│           │   └── client.py
│           ├── renamer/             # stage: parse
│           │   ├── manifest.yml
│           │   └── client.py
│           ├── tmdb/                # stage: data
│           │   ├── manifest.yml
│           │   └── client.py
│           ├── tvdb/                # stage: data
│           ├── ffprobe/             # stage: data
│           ├── tasker/              # stage: output (TASK SYSTEM!)
│           │   ├── manifest.yml     # provides: fs.write, output.values
│           │   └── client.py        # save/print tasks
│           └── rclone/              # stage: output
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── unit/
│   │   ├── state/
│   │   ├── core/
│   │   ├── validation/
│   │   └── plugins/
│   ├── integration/
│   └── fixtures/
│
├── AI/
│   ├── WORKFLOW.md
│   ├── 00_CURRENT_STATUS.md
│   ├── 01_CHANGELOG.md
│   ├── 02_TODO.md
│   └── sessions/
│       └── session_11_strategy/
│
├── docs/
│   └── PLUGIN_SDK.md
│
├── config.yml
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 2. MODULE RESPONSIBILITIES

### 2.1 Entry Point

```
__main__.py
├── Parse CLI args
├── Load config
├── Build dependencies
├── Create Orchestrator
└── Run and exit
```

### 2.2 Core

```
core/orchestrator.py
├── Coordinate full run lifecycle
├── Initialize components
├── Execute stages (input → parse → data → output)
└── Handle errors

core/plugins/
├── registry.py    → Discover and load plugins
├── resolver.py    → Resolve dependencies
├── executor.py    → Execute by stage
├── services.py    → PluginServices interface
└── validators.py  → RequiresValidator

core/validation/
├── config.py      → Config validation
├── manifest.py    → Manifest validation
└── dependency.py  → Dependency graph validation

# NOT: core/tasks YOK!
# Task sistemi = tasker plugin (stage: output)
# Template rendering = PluginServices.template içinde
```

### 2.3 State

```
state/models.py
├── RunState, RunStatus
├── JobState, JobInput, JobStatus, JobOutput
└── to_dict(), from_dict()

state/manager.py
├── StateManager
├── Run lifecycle methods
├── Job lifecycle methods
├── Context building
└── Event emission
```

### 2.4 Infrastructure

```
infrastructure/config/
├── loader.py      → YAML + env var resolution
└── validator.py   → Schema validation

infrastructure/persistence/
├── interface.py   → Abstract interface
├── pymongo.py     → Sync implementation
├── motor.py       → Async implementation
└── mock.py        → Testing implementation

infrastructure/memory/
├── tracker.py     → Memory tracking
├── flush.py       → Flush management
└── loader.py      → Lazy loading
```

---

## 3. IMPORT GRAPH

```
__main__.py
    │
    ├── infrastructure.config.loader
    ├── core.orchestrator
    │       │
    │       ├── events.bus
    │       ├── state.manager
    │       │       └── state.models
    │       ├── infrastructure.persistence.*
    │       ├── core.plugins.registry
    │       │       ├── core.plugins.base
    │       │       └── core.plugins.resolver
    │       ├── core.plugins.executor
    │       │       ├── core.plugins.services
    │       │       └── core.plugins.validators
    │       └── core.validation.*
    │
    └── utils.debug

# NOT: core.tasks YOK - tasker bir plugin!
```

---

## 4. PLUGIN STRUCTURE

```
plugins/{name}/
├── manifest.yml        # Required
├── client.py           # Required (default entry)
├── __init__.py         # Optional
└── utils.py            # Optional (plugin-specific)
```

### Example: TMDb Plugin

```
plugins/tmdb/
├── manifest.yml
│   name: tmdb
│   version: 1.0.0
│   phase: metadata
│   execution_mode: batch
│   requires: [renamer.parsed.movie]
│   class_name: TMDbPlugin
│
└── client.py
    class TMDbPlugin(BasePlugin):
        def execute_batch(self, jobs, services):
            # Batch API calls
            return results
```

---

## 5. CONFIG FILES

```
Root Level:
├── config.yml          # User configuration
├── .env                # Environment variables (gitignored)
├── .env.example        # Template for .env
├── pyproject.toml      # Project metadata
├── requirements.txt    # Dependencies
└── pytest.ini          # Test configuration

AI Directory:
├── WORKFLOW.md         # AI workflow guide
├── 00_CURRENT_STATUS.md
├── 01_CHANGELOG.md
└── 02_TODO.md
```

---

## 6. DEPENDENCY FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    DEPENDENCY LAYERS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 0: No dependencies                                    │
│  ├── state/models.py                                         │
│  ├── core/plugins/base.py                                    │
│  └── events/bus.py                                           │
│                                                              │
│  Layer 1: Depends on Layer 0                                 │
│  ├── state/manager.py → models                               │
│  ├── core/plugins/services.py → base                         │
│  └── infrastructure/persistence/* → models                   │
│                                                              │
│  Layer 2: Depends on Layer 1                                 │
│  ├── core/plugins/registry.py → base, services               │
│  ├── core/plugins/executor.py → services, validators         │
│  └── core/validation/* → models                              │
│                                                              │
│  Layer 3: Depends on Layer 2                                 │
│  └── core/orchestrator.py → all                              │
│                                                              │
│  Layer 4: Entry point                                        │
│  └── __main__.py → orchestrator                              │
│                                                              │
│  NOT: core/tasks YOK - tasker plugin olarak çalışır!         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. CIRCULAR IMPORT PREVENTION

```python
# BAD: Circular import
# state/manager.py
from core.orchestrator import Orchestrator  # Circular!

# GOOD: Dependency injection
# state/manager.py
class StateManager:
    def __init__(self, event_bus: EventBus):  # Interface only
        self._event_bus = event_bus

# orchestrator.py
state = StateManager(event_bus)  # Inject at runtime
```

---

## 8. MEVCUT vs YENİ KARŞILAŞTIRMA

### Mevcut

```
src/archiverr/
├── core/
│   ├── plugin_system/      # Mixed responsibilities
│   └── task_system/
├── plugins/
├── state/
├── events/
└── infrastructure/
```

### Yeni

```
src/archiverr/
├── core/
│   ├── orchestrator.py     # NEW: Central coordinator
│   ├── plugins/            # Refactored
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── resolver.py
│   │   ├── executor.py     # Stage-based (4 stage)
│   │   ├── services.py     # NEW: PluginServices
│   │   └── validators.py
│   └── validation/         # NEW: Validation system
│       ├── config.py
│       ├── manifest.py
│       └── dependency.py
├── infrastructure/
│   ├── config/             # NEW: Separate config handling
│   ├── persistence/
│   └── memory/             # NEW: Memory management (optional)
├── state/
├── events/
└── plugins/
    ├── scanner/            # stage: input
    ├── renamer/            # stage: parse
    ├── tmdb/               # stage: data
    ├── tasker/             # stage: output (TASK SYSTEM!)
    └── ...
```

**Key Changes:**

- `orchestrator.py` added (main.py simplified)
- `plugins/executor.py` refactored for 4 stages
- `plugins/services.py` added (SDK replacement)
- `core/validation/` added
- `infrastructure/memory/` added (optional)
- `infrastructure/config/` separated
- **`core/tasks/` KALDIRILDI** → `tasker` plugin olarak taşındı

---

**Son Guncelleme:** 2025-12-02
