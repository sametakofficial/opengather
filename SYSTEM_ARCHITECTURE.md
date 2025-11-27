# Archiverr System Architecture

> Technical documentation for the Archiverr media processing system.
> Version: 1.0.0 | Last Updated: 2024

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Directory Structure](#2-directory-structure)
3. [Core Components](#3-core-components)
4. [Execution Flow](#4-execution-flow)
5. [Plugin Architecture](#5-plugin-architecture)
6. [State Management](#6-state-management)
7. [Event System](#7-event-system)
8. [API Layer](#8-api-layer)
9. [Persistence Layer](#9-persistence-layer)
10. [Data Flow Diagrams](#10-data-flow-diagrams)

---

## 1. System Overview

Archiverr is a **plugin-agnostic, config-driven media processing system**. The core system knows nothing about media types, APIs, or domain logic - all domain-specific functionality is provided by plugins.

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Plugin-Agnostic** | Core never imports or references plugin-specific types |
| **Config-Driven** | All behavior controlled via `config.yml` |
| **Write-Through Persistence** | State changes immediately persisted to database |
| **Event-Driven** | Loose coupling via event bus for extensibility |
| **Git-like Versioning** | Executions tracked with branches and commits |

### High-Level Architecture

```
+------------------------------------------------------------------+
|                           Entry Points                            |
|   +----------------+  +----------------+  +--------------------+  |
|   |  CLI (__main__)|  |  API (FastAPI) |  |  Direct Import     |  |
|   +-------+--------+  +-------+--------+  +---------+----------+  |
|           |                   |                     |             |
|           +-------------------+---------------------+             |
|                               |                                   |
|                               v                                   |
|   +----------------------------------------------------------+   |
|   |                   ExecutionService                        |   |
|   |  - Orchestrates full execution pipeline                   |   |
|   |  - Progress callbacks for real-time updates               |   |
|   +---------------------------+------------------------------+   |
|                               |                                   |
+-------------------------------|-----------------------------------+
                                |
+-------------------------------|-----------------------------------+
|                               v                                   |
|   +----------------------------------------------------------+   |
|   |                    Core Systems                           |   |
|   |                                                           |   |
|   |  +------------------+  +------------------+               |   |
|   |  | Plugin System    |  | Task System      |               |   |
|   |  | - Discovery      |  | - TemplateManager|               |   |
|   |  | - Loader         |  | - TaskManager    |               |   |
|   |  | - Resolver       |  +------------------+               |   |
|   |  | - Executor       |                                     |   |
|   |  +------------------+                                     |   |
|   |                                                           |   |
|   +---------------------------+------------------------------+   |
|                               |                                   |
+-------------------------------|-----------------------------------+
                                |
+-------------------------------|-----------------------------------+
|                               v                                   |
|   +----------------------------------------------------------+   |
|   |                Infrastructure Layer                       |   |
|   |                                                           |   |
|   |  +------------------+  +------------------+               |   |
|   |  | State Manager    |  | Event Bus        |               |   |
|   |  | - Singleton      |  | - Pub/Sub        |               |   |
|   |  | - Write-through  |  | - Wildcard subs  |               |   |
|   |  +------------------+  +------------------+               |   |
|   |                                                           |   |
|   |  +------------------+  +------------------+               |   |
|   |  | Persistence      |  | Database         |               |   |
|   |  | - MockPersistence|  | - MongoDB/Motor  |               |   |
|   |  | - MongoDBPersist |  | - Collections    |               |   |
|   |  +------------------+  +------------------+               |   |
|   |                                                           |   |
|   +----------------------------------------------------------+   |
|                                                                   |
+-------------------------------------------------------------------+
```

---

## 2. Directory Structure

```
src/archiverr/
├── __init__.py              # Package initialization
├── __main__.py              # CLI entry point
│
├── api/                     # FastAPI application
│   ├── main.py              # App factory, middleware setup
│   ├── dependencies.py      # Dependency injection (DB, persistence)
│   ├── middleware/          # Rate limiting, CORS
│   └── v1/                  # API version 1 routes
│       ├── router.py        # Main router aggregator
│       ├── executions/      # /executions endpoints
│       ├── matches/         # /matches endpoints
│       ├── run/             # /run endpoints
│       ├── system/          # /system endpoints
│       └── versioning/      # /versioning endpoints
│
├── cli/                     # Command-line interface
│   └── main.py              # CLI argument parsing
│
├── core/                    # Core business logic
│   ├── plugins/             # Plugin orchestration
│   │   ├── discovery.py     # Scan plugins/*/plugin.yml
│   │   ├── loader.py        # Dynamic import & instantiation
│   │   ├── resolver.py      # Dependency graph & topological sort
│   │   └── executor.py      # Parallel execution engine
│   │
│   ├── tasks/               # Task execution system
│   │   ├── task_manager.py  # Print/save task execution
│   │   └── template_manager.py  # Jinja2 template rendering
│   │
│   ├── services/            # Shared services
│   │   └── execution_service.py  # Main execution orchestrator
│   │
│   └── reports/             # Report generation
│       └── report_generator.py
│
├── events/                  # Event bus system
│   ├── bus.py               # EventBus, Event, Events constants
│   └── handlers.py          # Built-in event handlers
│
├── state/                   # State management
│   ├── manager.py           # GlobalStateManager (singleton)
│   └── models.py            # ExecutionState, MatchState, PluginResult
│
├── infrastructure/          # External integrations
│   ├── database/            # Database connections
│   │   ├── connection.py    # DatabaseConnection factory
│   │   ├── interface.py     # PersistenceInterface ABC
│   │   ├── mock.py          # MockPersistence (testing)
│   │   └── mongodb.py       # MongoDBPersistence
│   │
│   └── repositories/        # Data access layer
│       ├── base.py          # BaseRepository
│       └── execution_repository.py
│
├── models/                  # Data models
│   └── response_builder.py  # APIResponseBuilder
│
├── plugins/                 # Plugin implementations
│   ├── base.py              # BasePlugin, InputPlugin, OutputPlugin
│   ├── scanner/             # Input: file system scanner
│   ├── file-reader/         # Input: file list reader
│   ├── ffprobe/             # Output: media metadata
│   ├── renamer/             # Output: filename parsing
│   ├── tmdb/                # Output: TMDB API
│   ├── tvdb/                # Output: TVDB API
│   ├── tvmaze/              # Output: TVMaze API
│   └── omdb/                # Output: OMDB API
│
└── utils/                   # Utilities
    ├── debug.py             # Professional debug logging
    ├── config_loader.py     # YAML config with .env support
    └── filters.py           # Jinja2 template filters
```

---

## 3. Core Components

### 3.1 Plugin System

The plugin system provides dynamic discovery, loading, and execution of plugins.

```
Plugin System Flow
==================

+----------------+     +----------------+     +------------------+
|  PluginDiscovery|---->|  PluginLoader  |---->| DependencyResolver|
|                |     |                |     |                  |
| Scans plugins/ |     | Imports client |     | Topological sort |
| Reads plugin.yml|    | Creates instances|   | Groups parallel  |
+----------------+     +----------------+     +--------+---------+
                                                       |
                                                       v
                                              +------------------+
                                              |  PluginExecutor  |
                                              |                  |
                                              | execute_group()  |
                                              | async parallel   |
                                              +------------------+
```

**Key Files:**
- `core/plugins/discovery.py` - Scans `plugins/*/plugin.yml`
- `core/plugins/loader.py` - Dynamic import via `importlib`
- `core/plugins/resolver.py` - Builds execution DAG
- `core/plugins/executor.py` - Async parallel execution

### 3.2 Task System

Executes print/save tasks after each match completes.

```
Task System Flow
================

config.yml tasks:        TemplateManager            TaskManager
      |                        |                         |
      v                        v                         v
+-------------+     +-------------------+     +------------------+
| tasks:      |     | Jinja2 Environment|     | execute_tasks()  |
| - type: print     | $ variable syntax |     | per-match        |
| - type: save |     | Custom filters    |     | condition eval   |
+-------------+     +-------------------+     +------------------+
```

**Key Files:**
- `core/tasks/template_manager.py` - Jinja2 rendering with `$var` syntax
- `core/tasks/task_manager.py` - Task execution, conditions, external tasks

### 3.3 Execution Service

Central orchestrator for CLI and API execution.

```python
# Usage pattern
service = ExecutionService(persistence=db, debugger=debug)
result = await service.run_execution_async(config, targets)
# result.api_response contains full execution data
```

**Key File:** `core/services/execution_service.py`

---

## 4. Execution Flow

### 4.1 Complete Execution Pipeline

```
                              START
                                |
                                v
                    +------------------------+
                    |   Load config.yml      |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Initialize State     |
                    |   GlobalStateManager   |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Plugin Discovery     |
                    |   Scan plugins/*.yml   |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Plugin Loading       |
                    |   Load enabled plugins |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Dependency Resolution|
                    |   Build execution DAG  |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Execute Input Plugins|
                    |   Collect matches      |
                    +------------------------+
                                |
                                v
              +----------------------------------+
              |     FOR EACH MATCH (parallel)   |
              |                                  |
              |  +----------------------------+  |
              |  | Register match in state   |  |
              |  +----------------------------+  |
              |              |                   |
              |              v                   |
              |  +----------------------------+  |
              |  | Execute output plugins    |  |
              |  | (dependency groups)       |  |
              |  +----------------------------+  |
              |              |                   |
              |              v                   |
              |  +----------------------------+  |
              |  | Update plugin results     |  |
              |  | in state                  |  |
              |  +----------------------------+  |
              |              |                   |
              |              v                   |
              |  +----------------------------+  |
              |  | Execute tasks for match   |  |
              |  | (print, save)             |  |
              |  +----------------------------+  |
              |              |                   |
              |              v                   |
              |  +----------------------------+  |
              |  | Complete match            |  |
              |  +----------------------------+  |
              |                                  |
              +----------------------------------+
                                |
                                v
                    +------------------------+
                    |   Build API Response   |
                    +------------------------+
                                |
                                v
                    +------------------------+
                    |   Complete Execution   |
                    |   Create commit        |
                    +------------------------+
                                |
                                v
                              END
```

### 4.2 Plugin Execution Order (Dependency Graph)

```
Input Plugins (Parallel)
========================
     +----------+     +-------------+
     |  scanner |     | file-reader |
     +----+-----+     +------+------+
          |                  |
          +--------+---------+
                   |
                   v
            [Collect Matches]
                   |
                   v
Output Plugins (Dependency Groups)
==================================

Group 0 (no dependencies):
     +----------+
     |  ffprobe |
     +----+-----+
          |
Group 1 (depends on ffprobe):
     +----------+
     |  renamer |  expects: input
     +----+-----+
          |
Group 2 (depends on renamer):
     +-------+  +------+  +-------+  +------+
     | tmdb  |  | tvdb |  |tvmaze |  | omdb |
     +-------+  +------+  +-------+  +------+
       expects: renamer.parsed
```

---

## 5. Plugin Architecture

### 5.1 Plugin Structure

Each plugin lives in its own directory:

```
plugins/{plugin_name}/
├── plugin.yml           # Plugin manifest (metadata)
├── client.py            # Plugin implementation
└── __init__.py          # Package initialization
```

### 5.2 Plugin Manifest (plugin.yml)

```yaml
name: tmdb
version: "1.0.0"
category: output           # input | output
class_name: TMDbPlugin     # Class in client.py

depends_on:                 # Plugins that must run first
  - renamer

expects:                    # Data that must exist
  - renamer.parsed
  - renamer.parsed.movie    # OR
  - renamer.parsed.show

config_schema:              # Optional config validation
  api_key:
    type: string
    required: true
  language:
    type: string
    default: en
```

### 5.3 Plugin Base Classes

```python
# plugins/base.py

class BasePlugin:
    """Base class for all plugins."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plugin logic."""
        raise NotImplementedError


class InputPlugin(BasePlugin):
    """Input plugins discover and return matches."""
    
    def execute(self) -> List[Dict[str, Any]]:
        """Return list of matches."""
        raise NotImplementedError


class OutputPlugin(BasePlugin):
    """Output plugins process individual matches."""
    
    def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process match and return result."""
        raise NotImplementedError
```

### 5.4 Plugin Data Flow

```
                    Input Plugin
                         |
                         v
              +---------------------+
              |  {                  |
              |    "input": {       |
              |      "path": "...", |
              |      "category": "" |
              |    },               |
              |    "scanner": {...} |
              |  }                  |
              +----------+----------+
                         |
                         v
                   Output Plugin 1
                         |
                         v
              +---------------------+
              |  {                  |
              |    "input": {...},  |
              |    "scanner": {...},|
              |    "ffprobe": {     |
              |      "video": {...},|
              |      "audio": [...] |
              |    }                |
              |  }                  |
              +----------+----------+
                         |
                         v
                   Output Plugin 2
                         |
                         v
              +---------------------+
              |  {                  |
              |    ...previous...,  |
              |    "renamer": {     |
              |      "parsed": {    |
              |        "movie":{...}|
              |      }              |
              |    }                |
              |  }                  |
              +----------+----------+
                         |
                         v
                   Final Match Data
```

---

## 6. State Management

### 6.1 GlobalStateManager (Singleton)

The `GlobalStateManager` provides centralized state with write-through persistence.

```
+---------------------------------------------------------------+
|                     GlobalStateManager                         |
|---------------------------------------------------------------|
| _instance: GlobalStateManager (singleton)                      |
| _execution: ExecutionState                                     |
| _matches: Dict[int, MatchState]                                |
| _persistence: PersistenceInterface                             |
| _event_bus: EventBus                                           |
+---------------------------------------------------------------+
|                                                                |
| Execution Methods:                                             |
| - start_execution(config) -> execution_id                      |
| - complete_execution(branch_name) -> ExecutionState            |
|                                                                |
| Match Methods:                                                 |
| - register_match(index, input_path) -> MatchState              |
| - update_plugin_result(index, plugin_name, result)             |
| - complete_match(index)                                        |
|                                                                |
| Template Context:                                              |
| - build_template_context(match_index) -> Dict                  |
| - build_api_response_for_templates() -> Dict                   |
|                                                                |
+---------------------------------------------------------------+
```

### 6.2 State Models

```python
@dataclass
class ExecutionState:
    id: str
    status: ExecutionStatus  # PENDING, RUNNING, COMPLETED, FAILED
    started_at: datetime
    finished_at: Optional[datetime]
    total_matches: int
    completed_matches: int
    failed_matches: int
    config_snapshot: Dict[str, Any]

@dataclass
class MatchState:
    index: int
    input_path: str
    execution_id: str
    status: ExecutionStatus
    plugins: Dict[str, Dict]      # Plugin results
    executed_plugins: List[str]
    failed_plugins: List[str]
    tasks: List[Dict]

@dataclass
class PluginResult:
    plugin_name: str
    success: bool
    started_at: datetime
    finished_at: datetime
    data: Dict[str, Any]
    error: Optional[str]
```

### 6.3 Write-Through Persistence

```
State Change             Persistence Write
============             =================

start_execution() -----> save_execution()
register_match()  -----> save_match()
update_plugin_result() -> save_plugin_result()
complete_match()  -----> save_match(), save_execution()
complete_execution() --> save_execution(), create_commit()
```

---

## 7. Event System

### 7.1 EventBus Architecture

```
+------------------------------------------------------------------+
|                           EventBus                                |
|------------------------------------------------------------------|
| Singleton pattern - one bus per application                       |
|                                                                   |
|  +------------------+     +------------------+                    |
|  | _handlers        |     | _history         |                    |
|  | Dict[event, list]|     | List[Event]      |                    |
|  +------------------+     +------------------+                    |
|                                                                   |
|  subscribe(event_name, handler)                                   |
|  unsubscribe(event_name, handler)                                 |
|  emit(event_name, data, source) -> Event                          |
|                                                                   |
+------------------------------------------------------------------+
```

### 7.2 Event Types

```python
class Events:
    # Execution lifecycle
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    
    # Match lifecycle
    MATCH_STARTED = "match.started"
    MATCH_COMPLETED = "match.completed"
    MATCH_FAILED = "match.failed"
    
    # Plugin lifecycle
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_SKIPPED = "plugin.skipped"
    
    # Task lifecycle
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # Database
    DB_CONNECTED = "db.connected"
    DB_DISCONNECTED = "db.disconnected"
```

### 7.3 Event Flow

```
GlobalStateManager                    EventBus                     Handlers
       |                                  |                            |
       | start_execution()                |                            |
       |--------------------------------->|                            |
       |                                  | emit("execution.started")  |
       |                                  |--------------------------->|
       |                                  |                            | log_event()
       |                                  |                            | update_ui()
       |                                  |                            |
       | register_match()                 |                            |
       |--------------------------------->|                            |
       |                                  | emit("match.started")      |
       |                                  |--------------------------->|
       |                                  |                            |
```

---

## 8. API Layer

### 8.1 FastAPI Application Structure

```
/api/v1/
├── /run
│   ├── POST /           # Sync execution
│   └── POST /async/     # Async execution with streaming
│
├── /executions
│   ├── GET /            # List executions
│   ├── GET /{id}        # Get execution details
│   └── DELETE /{id}     # Delete execution
│
├── /matches
│   ├── GET /            # List matches
│   └── GET /{id}        # Get match details
│
├── /versioning
│   ├── /branches
│   │   ├── GET /        # List branches
│   │   ├── POST /       # Create branch
│   │   ├── GET /{id}    # Get branch
│   │   └── DELETE /{id} # Delete branch
│   │
│   └── /commits
│       ├── GET /              # List commits
│       ├── POST /             # Create commit
│       ├── GET /{id}          # Get commit
│       ├── GET /{id}/history  # Get commit history
│       └── GET /{id}/checkout # Checkout commit data
│
└── /system
    └── GET /health      # Health check
```

### 8.2 Dependency Injection

```python
# api/dependencies.py

async def get_db_connection():
    """Connect to MongoDB via Motor (async)."""
    ...

async def get_persistence():
    """Get persistence wrapper for routes."""
    return AsyncPersistenceWrapper(db)

# Usage in routes
@router.get("/branches")
async def list_branches(persistence = Depends(get_persistence)):
    branches = await persistence._list_branches_async()
    return {"branches": branches}
```

---

## 9. Persistence Layer

### 9.1 Database Schema (MongoDB)

```
+------------------------------------------------------------------+
|                        MongoDB Collections                        |
+------------------------------------------------------------------+

executions
----------
{
  "_id": "exec_abc12345",
  "status": "completed",
  "started_at": "2024-01-01T00:00:00Z",
  "finished_at": "2024-01-01T00:01:00Z",
  "total_matches": 10,
  "completed_matches": 10,
  "failed_matches": 0,
  "config_snapshot": {...}
}

matches
-------
{
  "_id": "match_0_abc12345",
  "execution_id": "exec_abc12345",
  "index": 0,
  "input_path": "/path/to/file.mkv",
  "status": "completed",
  "started_at": "...",
  "finished_at": "..."
}

plugin_results
--------------
{
  "_id": "result_abc_0_tmdb",
  "execution_id": "exec_abc12345",
  "match_index": 0,
  "plugin_name": "tmdb",
  "success": true,
  "data": {...}
}

branches
--------
{
  "_id": "branch_main",
  "name": "main",
  "description": "Default branch",
  "is_default": true,
  "head_commit_id": "commit_xyz789",
  "created_at": "...",
  "updated_at": "..."
}

commits
-------
{
  "_id": "commit_xyz789",
  "branch_id": "branch_main",
  "execution_id": "exec_abc12345",
  "parent_commit_id": "commit_xyz788",
  "message": "Execution abc12345: 10 matches",
  "metadata": {...},
  "created_at": "..."
}
```

### 9.2 Persistence Interface

```python
class PersistenceInterface(ABC):
    """Abstract interface for persistence backends."""
    
    @abstractmethod
    def save_execution(self, execution: ExecutionState): ...
    
    @abstractmethod
    def save_match(self, match: MatchState): ...
    
    @abstractmethod
    def save_plugin_result(self, exec_id, match_idx, plugin, data): ...
    
    @abstractmethod
    def create_branch(self, name, description, is_default): ...
    
    @abstractmethod
    def create_commit(self, branch_id, execution_id, message): ...
```

---

## 10. Data Flow Diagrams

### 10.1 Complete Request Flow (API)

```
Client                    API                   Service                State
  |                        |                       |                     |
  | POST /run              |                       |                     |
  |----------------------->|                       |                     |
  |                        | run_execution_async() |                     |
  |                        |---------------------->|                     |
  |                        |                       | start_execution()   |
  |                        |                       |-------------------->|
  |                        |                       |                     |
  |                        |                       | [Plugin Discovery]  |
  |                        |                       | [Plugin Loading]    |
  |                        |                       | [Execute Inputs]    |
  |                        |                       |                     |
  |                        |                       | FOR EACH MATCH:     |
  |                        |                       |   register_match()  |
  |                        |                       |------------------>  |
  |                        |                       |   [Execute Outputs] |
  |                        |                       |   update_plugin()   |
  |                        |                       |------------------>  |
  |                        |                       |   [Execute Tasks]   |
  |                        |                       |   complete_match()  |
  |                        |                       |------------------>  |
  |                        |                       |                     |
  |                        |                       | complete_execution()|
  |                        |                       |-------------------->|
  |                        |                       |                     |
  |                        | <--ExecutionResult--- |                     |
  |                        |                       |                     |
  | <--JSON Response-------|                       |                     |
  |                        |                       |                     |
```

### 10.2 Template Variable Resolution

```
Template: "{{ renamer.parsed.movie.title }} ({{ renamer.parsed.movie.year }})"

                    TemplateManager
                          |
                          v
            +---------------------------+
            | build_template_context()  |
            +---------------------------+
                          |
                          v
            +---------------------------+
            | context = {               |
            |   "globals": {...},       |
            |   "match_globals": {...}, |
            |   "index": 0,             |
            |   "renamer": {            | <-- Plugin data flattened
            |     "parsed": {           |
            |       "movie": {          |
            |         "title": "...",   |
            |         "year": 2024      |
            |       }                   |
            |     }                     |
            |   },                      |
            |   "tmdb": {...}           |
            | }                         |
            +---------------------------+
                          |
                          v
            +---------------------------+
            | Jinja2.render(template,   |
            |               context)    |
            +---------------------------+
                          |
                          v
            "Movie Title (2024)"
```

---

## Appendix A: Configuration Reference

### config.yml Structure

```yaml
options:
  debug: false          # Enable debug logging
  dry_run: true         # Don't modify files

plugins:
  scanner:
    enabled: true
    targets:
      - /path/to/media
    recursive: true
  
  ffprobe:
    enabled: true
    timeout: 30
  
  renamer:
    enabled: true
  
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}  # Environment variable
    language: en

tasks:
  - name: print_info
    type: print
    template: "{{ renamer.parsed.movie.title }}"
  
  - name: save_file
    type: save
    destination: "/output/{{ renamer.parsed.movie.title }}.mkv"
    condition: "renamer.parsed.movie"
```

---

## Appendix B: Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_api.py -v

# Run specific test class
pytest tests/test_api.py::TestHealthEndpoints -v
```

### Test Structure

```
tests/
├── test_api.py           # API endpoint tests
├── test_plugins.py       # Plugin unit tests
├── test_state.py         # State manager tests
└── conftest.py           # Shared fixtures
```

---

## Appendix C: Common Patterns

### Adding a New Plugin

1. Create plugin directory: `plugins/{name}/`
2. Create `plugin.yml` manifest
3. Implement `client.py` with plugin class
4. Add to `config.yml` plugins section

### Adding a New API Endpoint

1. Create router in `api/v1/{resource}/router.py`
2. Create schemas in `api/v1/{resource}/schemas.py`
3. Register in `api/v1/router.py`

### Adding Event Handlers

```python
from archiverr.events import EventBus, Events

bus = EventBus()
bus.subscribe(Events.MATCH_COMPLETED, my_handler)
```

---

## Appendix D: Code Quality Standards

### Coding Standards

| Standard | Status |
|----------|--------|
| No bare `except:` clauses | Verified |
| No `eval()` on external input | Verified |
| API keys via environment variables | Verified |
| Type hints on public functions | Verified |
| Docstrings on public functions | Verified |
| English comments only | Verified |
| Logging instead of print() | Verified |

### Recent Audit Fixes (2024-11)

1. **parser.py**: Added comprehensive docstrings, type hints, translated Turkish comments
2. **mock.py**: Replaced `print()` with proper `logging.warning()`
3. **executions/router.py**: Changed TODO to NOTE for intentional limitation
4. **api/main.py**: Removed emojis from OpenAPI documentation
5. **test_api.py**: Added `MockPersistence` class for proper test isolation

### File Size Guidelines

Large files that may need refactoring in future:

| File | Lines | Recommendation |
|------|-------|----------------|
| `infrastructure/database/mongodb.py` | 699 | Consider splitting CRUD ops |
| `state/manager.py` | 576 | Consider extracting template context |
| `api/v1/versioning/router.py` | 455 | OK - single responsibility |

### Acceptable Patterns

These patterns are intentional and acceptable:

- `pass` in abstract method bodies (`interface.py`, `base.py`)
- `pass` after exception logging (silencing expected errors)
- `print()` in CLI entry points (`__main__.py`)
- `print()` in task execution (user-facing output)

---

*Document generated for Archiverr v1.0.0*
