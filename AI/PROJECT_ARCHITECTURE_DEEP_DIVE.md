# ARCHIVERR - PROJECT ARCHITECTURE & EXECUTION DEEP DIVE
## Comprehensive Analysis of Session 16 V2 & 17 Implementation

**Generated:** 2024-12-18  
**Analysis Scope:** Sessions 16 V2 and 17 decisions vs actual implementation  
**Status:** Complete architectural review with implementation verification

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Session 16 V2 Decisions Analysis](#2-session-16-v2-decisions-analysis)
3. [Session 17 Decisions Analysis](#3-session-17-decisions-analysis)
4. [Implementation Verification Matrix](#4-implementation-verification-matrix)
5. [Core Architecture](#5-core-architecture)
6. [State Management Architecture](#6-state-management-architecture)
7. [Plugin Communication System](#7-plugin-communication-system)
8. [Data Flow & Execution Workflow](#8-data-flow--execution-workflow)
9. [MongoDB Schema & Persistence](#9-mongodb-schema--persistence)
10. [API Layer Architecture](#10-api-layer-architecture)
11. [Critical Findings](#11-critical-findings)
12. [Recommendations](#12-recommendations)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Overview
Archiverr is a plugin-based media archiving and metadata enrichment system built on FastAPI, MongoDB, and a custom plugin architecture. The system underwent significant refactoring in Sessions 16 V2 and 17 to improve plugin communication, state management, and data structures.

### 1.2 Key Findings

**✅ SUCCESSFULLY IMPLEMENTED (70-80%)**
- Snake_case API naming (`create_job`, `update_job`, `update_plugin`)
- Explicit `target_id` and `plugin_name` parameters
- Job and Run status models with `plugins` dict
- Key-based `_jobs` dict (Session 17)
- Scanner plugin using `update_plugin` for run-level data
- ExecutionContext unified state container
- Flat plugin data structure (partial)

**⚠️ PARTIALLY IMPLEMENTED (20-30%)**
- Plugin data still has `.status`/`.data` wrapper in some places
- MongoDB schema not fully migrated to target_id-based
- Branches collection still exists in legacy mongodb.py
- Dual storage (`_plugins` and `_plugins_storage`) not fully unified

**❌ NOT IMPLEMENTED**
- Complete removal of PluginState.status field
- MongoDB single document per target_id
- Full flat plugin data everywhere

### 1.3 Architecture Quality Score: **7.5/10**

**Strengths:**
- Well-structured modular architecture
- Strong separation of concerns
- Comprehensive plugin SDK
- Event-driven design
- Flexible configuration system

**Weaknesses:**
- Legacy code still present
- Incomplete migration to Session 17 decisions
- Some test failures indicate API drift
- Documentation not fully synchronized with code

---

## 2. SESSION 16 V2 DECISIONS ANALYSIS

### 2.1 Decision Summary

Session 16 V2 made 10 major architectural decisions:

| # | Decision | Status | Implementation File |
|---|----------|--------|---------------------|
| 1 | Key-based plugins dict | ✅ Partial | `state/manager.py:294-348` |
| 2 | Plugin status in job/run.status.plugins | ✅ Done | `state/models.py:78-107` |
| 3 | Snake_case API naming | ✅ Done | `core/services/plugin_services.py` |
| 4 | Explicit target_id parameter | ✅ Done | `core/services/plugin_services.py:141-169` |
| 5 | Flat plugin data (no wrapper) | ⚠️ Partial | Mixed implementation |
| 6 | MongoDB target_id based | ❌ Not Done | Still uses (run_id, job_id, plugin_name) |
| 7 | Dual storage removal | ⚠️ Partial | `_plugins_storage` still exists |
| 8 | Per-run/job distinction via prefix | ✅ Done | `state/manager.py:308` |
| 9 | mark_plugin_started/completed | ⚠️ Partial | Not in manager.py |
| 10 | Backward compat aliases | ✅ Done | `createJob`, `updateJob`, `updatePlugin` |

### 2.2 Detailed Decision Analysis

#### Decision 1: Key-Based Plugins Dictionary

**Target Structure:**
```python
plugins = {
    "run_abc123": {
        "scanner": {"count": 10, "targets": [...]}
    },
    "job_run_abc123_0": {
        "renamer": {"parsed": {...}},
        "tmdb": {"movie": {...}}
    }
}
```

**Implementation:** `state/manager.py:294-348`
```python
def update_plugin(self, target_id: str, plugin_name: str, data: Dict[str, Any]) -> None:
    is_run_target = target_id.startswith("run_") or (self._run and target_id == self._run.id)
    
    if is_run_target:
        run_id = target_id if target_id.startswith("run_") else f"run_{target_id}"
        if run_id not in self._plugins_storage:
            self._plugins_storage[run_id] = {}
        self._plugins_storage[run_id][plugin_name] = data
```

**Status:** ✅ **IMPLEMENTED** - Uses `_plugins_storage` dict with target_id keys

**Issues Found:**
- Still has dual storage: `_plugins_storage` (line 56) alongside job.plugins
- Not fully unified as intended

#### Decision 2: Plugin Status in job.status.plugins

**Target:** Move status from `plugin.{name}.status` to `job.status.plugins.{name}`

**Implementation:** `state/models.py:78-107`
```python
@dataclass
class JobStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    plugins: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ✅ Added
```

**Status:** ✅ **IMPLEMENTED** - Field exists in both JobStatus and RunStatus

**Implementation in RunStatus:** `state/models.py:109-137`
```python
@dataclass
class RunStatus:
    plugins: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # ✅ Added
```

#### Decision 3: Snake_case API Naming

**Target:** `create_job`, `update_job`, `update_plugin` instead of camelCase

**Implementation:** `core/services/plugin_services.py:86-169`
```python
def create_job(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
    """Create new job."""
    
def update_job(self, job_id: str = None, key: str = None, value: Any = None) -> None:
    """Update job state."""
    
def update_plugin(self, target_id: str = None, plugin_name: str = None, 
                  data: Dict[str, Any] = None) -> None:
    """Update plugin data."""

# Backward compatibility
def createJob(self, input_value: str, input_data: Dict[str, Any] = None) -> str:
    return self.create_job(input_value, input_data)

def updateJob(self, key: str, value: Any) -> None:
    self.update_job(self._current_job_id, key, value)

def updatePlugin(self, data: Dict[str, Any]) -> None:
    self.update_plugin(self._current_job_id, self._current_plugin_name, data)
```

**Status:** ✅ **FULLY IMPLEMENTED** with backward compatibility

#### Decision 4: Explicit target_id Parameter

**Target:** All methods must specify target_id and plugin_name explicitly

**Implementation:** `core/services/plugin_services.py:141-169`
```python
def update_plugin(self, target_id: str = None, plugin_name: str = None, 
                  data: Dict[str, Any] = None) -> None:
    tid = target_id or self._current_job_id
    pname = plugin_name or self._current_plugin_name
    
    if not tid:
        raise ValueError("No target_id specified and no current context")
    if not pname:
        raise ValueError("No plugin_name specified and no current context")
    
    self._state.update_plugin(tid, pname, data or {})
```

**Status:** ✅ **IMPLEMENTED** with fallback to context

**Plugin Usage Verification:**

Scanner (per_run): `plugins/scanner/client.py:89-100`
```python
services.update_plugin(
    target_id=services.run_id,  # ✅ Explicit run_id
    plugin_name="scanner",      # ✅ Explicit name
    data={"count": created_jobs, "targets": targets}
)
```

Renamer (per_job): `plugins/renamer/client.py:86-87`
```python
if hasattr(services, 'updatePlugin'):
    services.updatePlugin(data=result_data)  # Uses context fallback
```

TMDb (per_job): Uses same pattern as renamer

#### Decision 5: Flat Plugin Data Structure

**Target:** `plugins["job_xxx"]["tmdb"]["movie"]` (no `.data` wrapper)

**Current Implementation:** MIXED

**Evidence of Wrapper Still Exists:**

`state/models.py:303-320` - PluginState still has status/data
```python
@dataclass
class PluginState:
    status: PluginStatus = field(default_factory=PluginStatus)
    data: Dict[str, Any] = field(default_factory=dict)  # ⚠️ Still wrapped
```

`state/models.py:324-353` - PluginData still has status field
```python
@dataclass
class PluginData:
    job_id: str
    run_id: str
    job_index: int
    plugin_name: str
    stage: str
    status: PluginStatus = field(default_factory=PluginStatus)  # ⚠️ Still exists
    data: Dict[str, Any] = field(default_factory=dict)
```

**Status:** ⚠️ **PARTIALLY IMPLEMENTED** - Models still have wrapper structure

**Where It Works:**
- `state/manager.py:331` stores data directly: `self._plugins_storage[job_id][plugin_name] = data`
- `state/manager.py:337` updates job.plugins directly: `job.plugins[plugin_name] = data`

**Where It Doesn't:**
- PluginState and PluginData classes still exist with status/data separation
- Some plugins may still expect wrapped structure

---

## 3. SESSION 17 DECISIONS ANALYSIS

### 3.1 Explicit Issues Fixed

Session 17 document listed 7 explicit issues to fix:

| Issue | Description | Status | Evidence |
|-------|-------------|--------|----------|
| 1.1 | Branches collection still created | ⚠️ Partial | Removed from pymongo_persistence.py, still in mongodb.py |
| 1.2 | jobs_count in output dump | ✅ Fixed | Not in orchestrator.py:532-537 |
| 1.3 | Plugin data .status/.data wrapper | ⚠️ Partial | Models still have it |
| 1.4 | job.status.plugins missing | ✅ Fixed | Added to JobStatus |
| 1.5 | Scanner not using update_plugin | ✅ Fixed | scanner/client.py:89-100 |
| 1.6 | _plugins appearing twice | ✅ Not Issue | By design for FlexGet compat |
| 1.7 | Manifest.yml not merged | ❌ Unknown | Needs investigation |

### 3.2 Jobs as Key-Based Dict (User Requested)

**Decision:** Change jobs from list to dict like plugins

**Target:**
```python
jobs = {
    "job_abc_0": JobState(...),
    "job_abc_1": JobState(...)
}
```

**Implementation:** `state/context.py:16-52`
```python
@dataclass
class ExecutionContext:
    _jobs: Dict[str, JobState] = field(default_factory=dict)  # ✅ Changed from List
    
    @property
    def jobs(self) -> List[JobState]:
        """Backward compat - returns list"""
        return list(self._jobs.values())
    
    @property
    def jobs_dict(self) -> Dict[str, JobState]:
        """New accessor - returns dict"""
        return self._jobs
    
    def add_job(self, job: JobState) -> None:
        """Session 17: key-based"""
        self._jobs[job.id] = job  # ✅ Dict storage
```

**Status:** ✅ **FULLY IMPLEMENTED**

**Orchestrator Output:** `core/orchestrator.py:508-518`
```python
# Session 17: Jobs as key-based dict (like plugins)
jobs_dict = {}
for job in self._state.get_all_jobs():
    job_dict = job.to_dict() if hasattr(job, 'to_dict') else {...}
    jobs_dict[job.id] = job_dict  # ✅ Key-based output
```

### 3.3 Branches Collection Removal

**Decision:** Remove deprecated branches functionality

**PyMongo Implementation:** `infrastructure/database/pymongo_persistence.py:65-67`
```python
RUNS = "runs"
JOBS = "jobs"
PLUGINS = "plugins"
# ✅ NO BRANCHES constant
```

**Legacy MongoDB:** `infrastructure/database/mongodb.py:100` (STILL EXISTS)
```python
BRANCHES = "branches"  # ⚠️ Still defined in legacy file
```

**Status:** ⚠️ **PARTIALLY DONE** - Removed from active persistence, remains in legacy code

---

## 4. IMPLEMENTATION VERIFICATION MATRIX

### 4.1 Complete Feature Matrix

| Component | Session 16 Target | Session 17 Target | Current Status | File Location | Notes |
|-----------|-------------------|-------------------|----------------|---------------|-------|
| **State Models** |
| JobStatus.plugins | Required | Required | ✅ Implemented | models.py:90 | Dict field exists |
| RunStatus.plugins | Required | Required | ✅ Implemented | models.py:121 | Dict field exists |
| PluginState.status | Remove wrapper | Remove wrapper | ❌ Still exists | models.py:313 | Not removed |
| PluginData.status | Remove field | Remove field | ❌ Still exists | models.py:336 | Not removed |
| **State Manager** |
| update_plugin(target_id) | Required | Required | ✅ Implemented | manager.py:294 | Accepts target_id |
| _plugins_storage | Unify with _plugins | Unify | ⚠️ Dual exists | manager.py:56 | Still separate |
| mark_plugin_started | System method | Not in doc | ❌ Not found | N/A | Missing |
| mark_plugin_completed | System method | Not in doc | ❌ Not found | N/A | Missing |
| **Plugin Services** |
| create_job | snake_case | Required | ✅ Implemented | plugin_services.py:86 | With alias |
| update_job | snake_case | Required | ✅ Implemented | plugin_services.py:115 | With alias |
| update_plugin | snake_case + target_id | Required | ✅ Implemented | plugin_services.py:141 | With alias |
| get_plugin_data | Required | Required | ✅ Implemented | plugin_services.py:171 | Exists |
| **Context** |
| _jobs as Dict | Not in 16 | Required | ✅ Implemented | context.py:28 | Dict[str, JobState] |
| jobs property (list) | N/A | Backward compat | ✅ Implemented | context.py:46 | Returns list |
| jobs_dict property | Not in 16 | New accessor | ✅ Implemented | context.py:50 | Returns dict |
| **MongoDB** |
| Plugins index | target_id unique | target_id | ❌ Not changed | pymongo_persistence.py:149 | Still composite |
| Branches removal | N/A | Required | ⚠️ Partial | mongodb.py:100 | Legacy file only |
| Single doc per target | Required | Required | ❌ Not done | N/A | Still per-plugin docs |
| **Plugins** |
| Scanner.update_plugin | Required | Required | ✅ Implemented | scanner/client.py:91 | Saves run data |
| Renamer.updatePlugin | Backward compat | Allowed | ✅ Uses alias | renamer/client.py:87 | Uses old name |
| TMDb.update_plugin | Required | Required | ⚠️ Uses alias | tmdb/client.py | Uses old pattern |

### 4.2 Test Results Analysis

**Unit Tests Run:** `tests/unit/state/`

**Failures Found:**
- `test_start_execution_creates_execution_state` - Method renamed to `start_run`
- `test_register_match_creates_match_state` - Method renamed to `create_job`
- Several tests use old API names (`start_execution` vs `start_run`)

**Root Cause:** Tests not updated after Session 16/17 refactoring

**Impact:** Test suite doesn't validate new architecture

---

## 5. CORE ARCHITECTURE

### 5.1 System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI / API Layer                         │
│         (__main__.py / api/main.py)                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Layer                        │
│  - Run lifecycle management                                  │
│  - Stage execution (PARSE → DATA → OUTPUT)                   │
│  - Per-run plugin execution                                  │
│  - Error handling & recovery                                 │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Plugin       │   │ State        │   │ Event        │
│ Registry     │   │ Manager      │   │ Bus          │
└──────────────┘   └──────────────┘   └──────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Stage        │   │ Context      │   │ Persistence  │
│ Executor     │   │              │   │ (MongoDB)    │
└──────────────┘   └──────────────┘   └──────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Plugin Layer                              │
│  - Scanner (per_run, INPUT)                                 │
│  - Renamer (per_job, PARSE)                                 │
│  - TMDb/TVDb (per_job, DATA)                               │
│  - Tasker (per_job, OUTPUT)                                │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Core Components

#### 5.2.1 Orchestrator (`core/orchestrator.py`)

**Responsibilities:**
- Run lifecycle: initialize → execute stages → finalize
- Per-run plugin execution (before stages)
- Stage execution coordination
- Error handling and recovery
- State persistence

**Key Methods:**
```python
def run(self) -> RunResult:
    self._initialize()           # Setup run state
    self._execute_per_run_plugins()  # Scanner, etc.
    self._execute_stages()       # PARSE → DATA → OUTPUT
    self._finalize()             # Complete & persist
    return RunResult(...)
```

**Stages:**
```python
STAGES = [Stage.PARSE, Stage.DATA, Stage.OUTPUT]
# INPUT stage removed - input plugins run as per_run
```

#### 5.2.2 State Manager (`state/manager.py`)

**Architecture:** Session 14 refactored to 3 global objects

```python
class GlobalStateManager:
    _run: RunState              # Global 1: Read-only for all
    _config: Dict[str, Any]     # Global 2: Frozen config
    _context: ExecutionContext  # Global 3: Unified job/plugin state
    
    # Legacy (to be removed)
    _plugins_storage: Dict[str, Dict[str, PluginState]]
```

**Key Methods:**
```python
# Run management
start_run(config) -> run_id
complete_run() -> RunState

# Job management  
create_job(input_value, input_data) -> job_id
set_current_job(job_id)
get_job_by_id(job_id) -> JobState

# Plugin data
update_plugin(target_id, plugin_name, data)
get_plugin_data(job_id, plugin_name) -> Dict
```

#### 5.2.3 Execution Context (`state/context.py`)

**Purpose:** Unified container for job-level state

```python
@dataclass
class ExecutionContext:
    _current_job: Optional[JobState]           # Current job being processed
    _jobs: Dict[str, JobState]                # Session 17: Key-based dict
    _current_plugins: Dict[str, Dict]         # Current job's plugins
    _all_plugins: Dict[str, Dict]             # All plugins (key-based)
```

**Properties:**
- `job` - Current job (read-write, raises if none)
- `jobs` - All jobs as list (backward compat, read-only)
- `jobs_dict` - All jobs as dict (Session 17, read-only)
- `plugin` - Current job's plugins (read-write)
- `plugins` - All plugins (read-only)

#### 5.2.4 Plugin Services (`core/services/plugin_services.py`)

**Purpose:** Controlled API for plugins to interact with system

**Context Management:**
```python
def __init__(self, state, event_bus, logger, config, mode,
             current_job_id=None, current_plugin_name=None):
    self._mode = mode  # "per_run" or "per_job"
    self._current_job_id = current_job_id
    self._current_plugin_name = current_plugin_name
```

**API Methods:**
```python
# Job operations
create_job(input_value, input_data) -> job_id
update_job(job_id, key, value)
get_current_job() -> JobState
get_all_jobs() -> List[JobState]

# Plugin operations
update_plugin(target_id, plugin_name, data)
get_plugin_data(target_id, plugin_name) -> Dict

# Event operations
emit(event, data)

# Status reporting (Session 14)
update_status(state, success, message, error)
```

---

## 6. STATE MANAGEMENT ARCHITECTURE

### 6.1 State Flow

```
User Config (config.yml)
    │
    ▼
┌─────────────────────┐
│ Orchestrator.run()  │
│ creates RunState    │
└─────────────────────┘
    │
    │ start_run(config)
    ▼
┌──────────────────────────────────────────┐
│ GlobalStateManager                        │
│                                          │
│ _run: RunState (frozen)                  │
│   ├─ id: run_abc123                     │
│   ├─ status                             │
│   │   ├─ state: running                 │
│   │   ├─ plugins: {}  ← Session 17     │
│   │   └─ total_jobs: 0                  │
│   └─ config: {...}                      │
│                                          │
│ _context: ExecutionContext               │
│   ├─ _jobs: Dict[str, JobState]         │
│   │   └─ job_run_abc123_0: JobState     │
│   │       ├─ input: {value, data}       │
│   │       ├─ output: {values, data}     │
│   │       ├─ status                      │
│   │       │   └─ plugins: {} ← S17      │
│   │       └─ plugins: {}  ← Runtime     │
│   │                                      │
│   └─ _all_plugins: Dict[target_id, plugins]│
│       ├─ run_abc123:                     │
│       │   └─ scanner: {count, targets}  │
│       └─ job_run_abc123_0:              │
│           ├─ renamer: {parsed, category}│
│           └─ tmdb: {movie: {...}}       │
└──────────────────────────────────────────┘
```

### 6.2 Data Models

#### 6.2.1 RunState (`state/models.py:234-276`)

```python
@dataclass
class RunState:
    id: str  # Format: run_{uuid8}
    status: RunStatus
    config: Dict[str, Any]
    
class RunStatus:
    state: StateEnum  # PENDING, RUNNING, SUCCESS, FAILED, PARTIAL, CANCELLED
    success: bool
    total_jobs: int
    completed: int
    failed: int
    plugins: Dict[str, Dict[str, Any]]  # ← Session 17: per-run plugin status
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: int
```

**Session 17 Addition:** `plugins` dict for per-run plugin status (e.g., scanner)

#### 6.2.2 JobState (`state/models.py:140-231`)

```python
@dataclass
class JobState:
    index: int
    run_id: str
    id: str  # Format: job_{run_id}_{index}
    input: InputData
    output: OutputData
    status: JobStatus
    plugins: Dict[str, Dict[str, Any]]  # Runtime plugin data access
    
class JobStatus:
    state: StateEnum
    success: bool
    executed: List[str]
    failed: List[str]
    skipped: List[str]
    plugins: Dict[str, Dict[str, Any]]  # ← Session 17: per-plugin status
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: int
```

**Session 17 Addition:** `status.plugins` for per-plugin execution status

**Dual Plugin Storage:**
1. `job.plugins` - Runtime data access (flat)
2. `job.status.plugins` - Execution status tracking

#### 6.2.3 InputData & OutputData (`state/models.py:38-74`)

```python
@dataclass
class InputData:
    value: str  # Path or virtual identifier
    data: Dict[str, Any]  # Plugin-specific metadata
    # Best practice: include 'source' field

@dataclass
class OutputData:
    values: List[str]  # Output paths (array)
    data: Dict[str, Any]  # Output plugin data
```

**Philosophy:** Support virtual paths, not just filesystem paths

### 6.3 Plugin Data Storage

#### Current Implementation (Mixed)

**Method 1: Direct Storage** (`state/manager.py:331-337`)
```python
def update_plugin(self, target_id, plugin_name, data):
    # Store in _plugins_storage
    self._plugins_storage[job_id][plugin_name] = data  # ✅ Flat
    
    # Also update job.plugins
    job.plugins[plugin_name] = data  # ✅ Flat
```

**Method 2: Wrapped Storage** (Legacy, still in PluginState/PluginData models)
```python
# ⚠️ Still exists but not actively used
@dataclass
class PluginState:
    status: PluginStatus
    data: Dict[str, Any]
```

**Access Patterns:**

Per-job plugin (e.g., TMDb):
```python
# Write
services.update_plugin("job_run_abc_0", "tmdb", {"movie": {...}})

# Read
job.plugins["tmdb"]["movie"]  # ✅ Session 17 flat access
```

Per-run plugin (e.g., Scanner):
```python
# Write
services.update_plugin("run_abc123", "scanner", {"count": 10, "targets": [...]})

# Read
# Stored in _plugins_storage["run_abc123"]["scanner"]
```

---

## 7. PLUGIN COMMUNICATION SYSTEM

### 7.1 Plugin Lifecycle

```
1. DISCOVERY (startup)
   └─ PluginDiscovery.discover_all()
       └─ Scans src/archiverr/plugins/*/

2. LOADING (startup)
   └─ PluginLoader.load_plugin(manifest)
       ├─ Import plugin module
       ├─ Validate manifest.yml
       └─ Create plugin instance

3. REGISTRATION (startup)
   └─ PluginRegistry.register(plugin, manifest)
       ├─ Store by stage
       ├─ Build dependency graph
       └─ Validate provides/requires

4. EXECUTION (runtime)
   ├─ Per-run plugins (Scanner)
   │   └─ orchestrator._execute_per_run_plugins()
   │       └─ plugin.execute_run(services)
   │
   └─ Per-job plugins (Renamer, TMDb, Tasker)
       └─ StageExecutor.execute_stage(stage, jobs)
           └─ for each job:
               ├─ Set current job context
               ├─ plugin.execute(job, services)
               └─ Clear context
```

### 7.2 Plugin Services Interface

**Instantiation per Plugin:**
```python
# Per-run plugin
services = PluginServices(
    state=state_manager,
    event_bus=event_bus,
    logger=debugger,
    config=frozen_config,
    mode="per_run"
)

# Per-job plugin
services = PluginServices(
    state=state_manager,
    event_bus=event_bus,
    logger=debugger,
    config=frozen_config,
    mode="per_job",
    current_job_id="job_run_abc_0",
    current_plugin_name="tmdb"
)
```

**API Surface:**

| Method | Per-Run | Per-Job | Description |
|--------|---------|---------|-------------|
| `create_job()` | ✅ | ✅ | Create new job |
| `update_job()` | ❌ | ✅ | Update current job |
| `update_plugin()` | ✅ | ✅ | Save plugin data |
| `get_current_job()` | ❌ | ✅ | Get job being processed |
| `get_all_jobs()` | ✅ | ✅ (read-only) | List all jobs |
| `emit()` | ✅ | ✅ | Emit event |
| `update_status()` | ✅ | ✅ | Report plugin status |

### 7.3 Plugin Execution Patterns

#### Pattern 1: Per-Run Plugin (Scanner)

**File:** `plugins/scanner/client.py:31-105`

```python
class ScannerPlugin(InputPlugin):
    def execute_run(self, services: Any) -> Dict[str, Any]:
        # Discover files
        for target in self.config.get('targets', []):
            files = scan_directory(target)
            
            # Create jobs for each file
            for file in files:
                job_id = services.create_job(
                    input_value=str(file),
                    input_data={
                        'source': 'scanner',
                        'filename': file.name,
                        'size_bytes': file.stat().st_size
                    }
                )
        
        # Session 17: Save run-level data
        services.update_plugin(
            target_id=services.run_id,  # run_abc123
            plugin_name="scanner",
            data={
                "count": len(files),
                "targets": self.config.get('targets')
            }
        )
        
        return {'success': True, 'count': len(files)}
```

**Key Points:**
- Creates multiple jobs via `services.create_job()`
- Saves run-level summary via `update_plugin(run_id, ...)`
- Does NOT process individual jobs

#### Pattern 2: Per-Job Plugin (Renamer)

**File:** `plugins/renamer/client.py:27-97`

```python
class RenamerPlugin(OutputPlugin):
    def execute(self, job: Any, services: Any) -> PluginResult:
        # Parse filename
        input_path = job.input.value
        filename = Path(input_path).stem
        
        parsed = parse_filename(filename)
        
        result_data = {
            'parsed': {
                'show': show_match,
                'movie': movie_match
            },
            'category': 'movie' or 'show'
        }
        
        # Save via services (uses current context)
        services.updatePlugin(data=result_data)  # Backward compat alias
        
        return PluginResult.success_result(data=result_data)
```

**Key Points:**
- Receives single `job` parameter
- Uses `services.updatePlugin()` (no target_id needed, uses context)
- Returns `PluginResult`

#### Pattern 3: Per-Job with Cross-Plugin Dependencies (TMDb)

**File:** `plugins/tmdb/client.py:73-149`

```python
class TMDbPlugin(OutputPlugin):
    def execute(self, job: Any, services: Any) -> PluginResult:
        # Session 17: Get parsed data from plugin.renamer
        parsed_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            renamer_data = job.plugins.get('renamer', {})
            parsed_data = renamer_data.get('parsed', {})  # ✅ Flat access
        
        # Fetch from TMDb API
        if parsed_data.get('movie'):
            movie = self.movie_fetcher.fetch_movie(parsed_data['movie'])
            result = {'movie': movie}
        elif parsed_data.get('show'):
            show = self.show_fetcher.fetch_show(parsed_data['show'])
            result = {'show': show}
        
        # Save (uses context)
        services.updatePlugin(data=result)
        
        return PluginResult.success_result(data=result)
```

**Key Points:**
- Reads other plugin data via `job.plugins.renamer.parsed`
- Session 17 flat access (no `.data` wrapper needed)
- Saves own data via services

---

## 8. DATA FLOW & EXECUTION WORKFLOW

### 8.1 Complete Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    1. STARTUP PHASE                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─ Load config.yml
    ├─ Initialize Debugger
    ├─ Create EventBus
    ├─ Create GlobalStateManager
    ├─ Connect to MongoDB (PyMongoPersistence)
    ├─ Discover plugins (PluginDiscovery)
    ├─ Load plugins (PluginLoader)
    ├─ Register plugins (PluginRegistry)
    ├─ Validate dependencies
    └─ Build Orchestrator

┌─────────────────────────────────────────────────────────────────┐
│                    2. RUN INITIALIZATION                         │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─ orchestrator.run() called
    ├─ state.start_run(config) → creates RunState
    ├─ Emit "run.started" event
    └─ _run_id = "run_abc123"

┌─────────────────────────────────────────────────────────────────┐
│                    3. PER-RUN PLUGIN EXECUTION                   │
│                    (Scanner, File-Reader)                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─ Scanner.execute_run(services)
    │   ├─ Scan filesystem for media files
    │   ├─ For each file:
    │   │   └─ services.create_job(path, metadata)
    │   │       └─ state.create_job() → JobState created
    │   │           └─ job_id = "job_run_abc123_0"
    │   │
    │   └─ services.update_plugin(run_id, "scanner", {count, targets})
    │       └─ Saved to _plugins_storage["run_abc123"]["scanner"]
    │
    └─ Total jobs created: N

┌─────────────────────────────────────────────────────────────────┐
│                    4. STAGE EXECUTION LOOP                       │
│                    For each stage: PARSE → DATA → OUTPUT        │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─ STAGE 1: PARSE
    │   └─ For each job (0..N):
    │       ├─ state.set_current_job(job_id)
    │       ├─ Renamer.execute(job, services)
    │       │   ├─ Parse job.input.value filename
    │       │   ├─ Extract movie/show metadata
    │       │   └─ services.updatePlugin({parsed, category})
    │       │       └─ job.plugins["renamer"] = {parsed, category}
    │       └─ state.clear_current_job()
    │
    ├─ STAGE 2: DATA
    │   └─ For each job (0..N):
    │       ├─ state.set_current_job(job_id)
    │       ├─ FFprobe.execute(job, services) [if enabled]
    │       │   └─ services.updatePlugin({format, streams})
    │       │
    │       ├─ TMDb.execute(job, services)
    │       │   ├─ Read: job.plugins["renamer"]["parsed"]
    │       │   ├─ Fetch metadata from TMDb API
    │       │   └─ services.updatePlugin({movie/show/episode})
    │       │       └─ job.plugins["tmdb"] = {movie: {...}}
    │       │
    │       └─ state.clear_current_job()
    │
    └─ STAGE 3: OUTPUT
        └─ For each job (0..N):
            ├─ state.set_current_job(job_id)
            ├─ Tasker.execute(job, services)
            │   ├─ Process task list from config
            │   ├─ For each task:
            │   │   ├─ Render Jinja2 template
            │   │   ├─ Execute (print/save/copy/hardlink)
            │   │   └─ Store result in job.output.data
            │   │
            │   └─ services.update_job(job_id, "output.values", paths)
            │
            └─ state.clear_current_job()

┌─────────────────────────────────────────────────────────────────┐
│                    5. RUN FINALIZATION                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─ state.complete_run()
    │   ├─ Calculate duration_ms
    │   ├─ Set run.status.state = SUCCESS/FAILED
    │   └─ Emit "execution.completed" event
    │
    ├─ Persist final state to MongoDB
    │   ├─ Save RunState
    │   ├─ Save all JobStates
    │   └─ Save all plugin data
    │
    ├─ Dump state to JSON (output/run_abc123_state.json)
    │
    └─ Return RunResult(run_id, success, stats)
```

### 8.2 Data Transformation Pipeline

**Example: Single Job Flow**

```
INPUT: "/tmp/Breaking.Bad.S01E01.720p.BluRay.x264.mkv"
  │
  │ Scanner creates JobState
  ▼
job.input = {
    value: "/tmp/Breaking.Bad.S01E01.720p.BluRay.x264.mkv",
    data: {
        source: "scanner",
        filename: "Breaking.Bad.S01E01.720p.BluRay.x264.mkv",
        size_bytes: 524288000
    }
}
  │
  │ PARSE Stage: Renamer plugin
  ▼
job.plugins.renamer = {
    parsed: {
        show: {
            name: "Breaking Bad",
            season: 1,
            episode: 1,
            year: null
        },
        movie: null
    },
    category: "show"
}
  │
  │ DATA Stage: TMDb plugin
  ▼
job.plugins.tmdb = {
    show: {
        identifiers: {tmdb_id: 1396, imdb_id: "tt0903747"},
        title: {primary: "Breaking Bad", original: "Breaking Bad"},
        overview: "...",
        ratings: {tmdb: {score: 8.9, votes: 12000}},
        genres: ["Crime", "Drama", "Thriller"],
        people: {cast: [...], crew: [...]},
        ...
    },
    episode: {
        season_number: 1,
        episode_number: 1,
        title: {primary: "Pilot"},
        overview: "...",
        ...
    }
}
  │
  │ OUTPUT Stage: Tasker plugin
  ▼
job.output = {
    values: [
        "/archive/TV Shows/Breaking Bad (2008)/Season 01/Breaking Bad - S01E01 - Pilot.mkv"
    ],
    data: {
        tasks: {
            print_header: {success: true, type: "print"},
            print_tmdb: {success: true, type: "print"},
            save_file: {success: true, type: "save", destination: "..."}
        }
    }
}
```

### 8.3 Template Context Building

**When Tasker renders templates:**

```python
# Built by GlobalStateManager.build_template_context(job_index)
context = {
    # Run info
    "run": {
        "id": "run_abc123",
        "status": {"success": True, "total_jobs": 1, ...},
        "config": {...}
    },
    
    # Current job
    "job": {
        "index": 0,
        "id": "job_run_abc123_0",
        "input": {"value": "/tmp/...", "data": {...}},
        "output": {"values": [...], "data": {...}},
        "status": {"success": True, "executed": ["renamer", "tmdb"], ...},
        "plugins": {
            "renamer": {...},
            "tmdb": {...}
        }
    },
    
    # All jobs (list)
    "jobs": [{"index": 0, ...}],
    
    # Config shortcuts
    "config": {...},
    "options": {...},
    
    # Plugin data shortcuts (for convenience)
    "renamer": {...},  # Same as job.plugins.renamer
    "tmdb": {...}      # Same as job.plugins.tmdb
}
```

**Template Usage:**
```jinja2
{% if job.plugins.tmdb.show %}
  Show: {{ job.plugins.tmdb.show.title.primary }}
  Episode: S{{ '%02d' | format(job.plugins.tmdb.episode.season_number) }}E{{ '%02d' | format(job.plugins.tmdb.episode.episode_number) }}
{% endif %}
```

---

## 9. MONGODB SCHEMA & PERSISTENCE

### 9.1 Current Schema (PyMongoPersistence)

**Collections:**
```python
RUNS = "runs"      # Run-level state
JOBS = "jobs"      # Job-level state  
PLUGINS = "plugins"  # Plugin data (separate documents)
```

**Indexes:**
```python
# runs collection
runs.createIndex({id: 1}, {unique: true})
runs.createIndex({created_at: 1})
runs.createIndex({"status.state": 1})

# jobs collection
jobs.createIndex({id: 1}, {unique: true})
jobs.createIndex({run_id: 1, index: 1}, {unique: true})
jobs.createIndex({run_id: 1})

# plugins collection
plugins.createIndex({run_id: 1, job_id: 1, plugin_name: 1}, {unique: true})
plugins.createIndex({run_id: 1})
plugins.createIndex({job_id: 1})
plugins.createIndex({plugin_name: 1})
plugins.createIndex({stage: 1})
```

### 9.2 Document Structures

#### 9.2.1 Runs Document

```javascript
{
  "_id": ObjectId("..."),
  "id": "run_abc123",
  "status": {
    "state": "success",
    "success": true,
    "total_jobs": 1,
    "completed": 1,
    "failed": 0,
    "plugins": {  // ← Session 17
      "scanner": {
        "state": "completed",
        "success": true,
        "started_at": "2024-12-18T00:00:00",
        "finished_at": "2024-12-18T00:00:01",
        "duration_ms": 1000
      }
    },
    "started_at": "2024-12-18T00:00:00",
    "finished_at": "2024-12-18T00:05:00",
    "duration_ms": 300000
  },
  "config": {
    "scanner": {...},
    "renamer": {...},
    "tmdb": {...},
    "tasker": {...}
  },
  "created_at": ISODate("2024-12-18T00:00:00Z"),
  "updated_at": ISODate("2024-12-18T00:05:00Z")
}
```

#### 9.2.2 Jobs Document

```javascript
{
  "_id": ObjectId("..."),
  "id": "job_run_abc123_0",
  "index": 0,
  "run_id": "run_abc123",
  "input": {
    "value": "/tmp/Breaking.Bad.S01E01.720p.BluRay.x264.mkv",
    "data": {
      "source": "scanner",
      "filename": "Breaking.Bad.S01E01.720p.BluRay.x264.mkv",
      "size_bytes": 524288000
    }
  },
  "output": {
    "values": ["/archive/TV Shows/..."],
    "data": {
      "tasks": {...}
    }
  },
  "status": {
    "state": "success",
    "success": true,
    "executed": ["renamer", "tmdb", "tasker"],
    "failed": [],
    "skipped": [],
    "plugins": {  // ← Session 17
      "renamer": {
        "state": "completed",
        "success": true,
        "duration_ms": 50
      },
      "tmdb": {
        "state": "completed",
        "success": true,
        "duration_ms": 1200
      }
    },
    "started_at": "2024-12-18T00:00:01",
    "finished_at": "2024-12-18T00:00:05",
    "duration_ms": 4000
  },
  "plugins": {  // ← Runtime data (not in Session 17 target)
    "renamer": {...},
    "tmdb": {...}
  },
  "created_at": ISODate("2024-12-18T00:00:01Z"),
  "updated_at": ISODate("2024-12-18T00:00:05Z")
}
```

#### 9.2.3 Plugins Document (Current - NOT Session 17 Target)

```javascript
{
  "_id": ObjectId("..."),
  "job_id": "job_run_abc123_0",
  "run_id": "run_abc123",
  "job_index": 0,
  "plugin_name": "tmdb",
  "stage": "data",
  "status": {  // ⚠️ Session 17 wants this removed
    "state": "completed",
    "success": true,
    "started_at": "2024-12-18T00:00:02",
    "finished_at": "2024-12-18T00:00:03",
    "duration_ms": 1200,
    "error": null
  },
  "data": {  // ⚠️ Session 17 wants data directly at root
    "show": {...},
    "episode": {...}
  }
}
```

**Session 17 Target (Not Implemented):**
```javascript
// One document per target_id with all plugins
{
  "_id": "job_run_abc123_0",  // target_id is _id
  "renamer": {
    "parsed": {...},
    "category": "show"
  },
  "tmdb": {
    "show": {...},
    "episode": {...}
  },
  "tasker": {
    "tasks": {...}
  }
}

// For run-level plugins
{
  "_id": "run_abc123",
  "scanner": {
    "count": 1,
    "targets": ["/tmp/"]
  }
}
```

### 9.3 Persistence Layer (`infrastructure/database/pymongo_persistence.py`)

**Key Methods:**

```python
class PyMongoPersistence:
    def save_run(self, run: Dict[str, Any]) -> None:
        """Upsert run document"""
        
    def save_job(self, job: Dict[str, Any]) -> None:
        """Upsert job document"""
        
    def save_plugin(self, plugin: Dict[str, Any]) -> None:
        """Upsert plugin document (per plugin, not per target)"""
        # ⚠️ NOT Session 17 compliant
        
    def get_run(self, run_id: str) -> Optional[Dict]:
        """Retrieve run"""
        
    def get_jobs(self, run_id: str) -> List[Dict]:
        """Retrieve all jobs for run"""
        
    def get_plugins(self, job_id: str) -> List[Dict]:
        """Retrieve all plugins for job"""
```

**Issues:**
1. Still creates separate document per plugin
2. Plugin documents have status field
3. Not using target_id as _id
4. Composite index instead of simple _id index

---

## 10. API LAYER ARCHITECTURE

### 10.1 FastAPI Structure

**File:** `api/main.py`

```
api/
├── __init__.py
├── main.py                # FastAPI app
├── dependencies.py        # DI functions
├── v1/
│   ├── __init__.py
│   ├── plugins/
│   │   ├── router.py      # Plugin data endpoints
│   │   └── schemas.py     # Pydantic models
│   ├── runs/
│   │   ├── router.py      # Run CRUD
│   │   └── schemas.py
│   └── jobs/
│       ├── router.py      # Job CRUD
│       └── schemas.py
```

### 10.2 Key Endpoints

```python
# Runs
GET    /api/v1/runs                    # List runs
GET    /api/v1/runs/{run_id}           # Get run
POST   /api/v1/runs                    # Start new run
DELETE /api/v1/runs/{run_id}           # Delete run

# Jobs
GET    /api/v1/jobs                    # List jobs (filter by run_id)
GET    /api/v1/jobs/{job_id}           # Get job
GET    /api/v1/runs/{run_id}/jobs      # Get jobs for run

# Plugins (Session 16 target: target_id parameter)
GET    /api/v1/plugins/{target_id}              # All plugins for target
GET    /api/v1/plugins/{target_id}/{plugin_name} # Specific plugin
```

### 10.3 Response Schemas

**Run Response:**
```json
{
  "id": "run_abc123",
  "status": {
    "state": "success",
    "total_jobs": 1,
    "completed": 1,
    "failed": 0,
    "plugins": {
      "scanner": {"state": "completed", "success": true}
    }
  },
  "config": {...},
  "started_at": "2024-12-18T00:00:00",
  "duration_ms": 300000
}
```

**Job Response:**
```json
{
  "id": "job_run_abc123_0",
  "index": 0,
  "run_id": "run_abc123",
  "input": {
    "value": "/tmp/file.mkv",
    "data": {...}
  },
  "output": {
    "values": ["/archive/..."],
    "data": {...}
  },
  "status": {
    "state": "success",
    "executed": ["renamer", "tmdb"],
    "plugins": {
      "renamer": {"state": "completed", "duration_ms": 50}
    }
  },
  "plugins": {
    "renamer": {...},
    "tmdb": {...}
  }
}
```

---

## 11. CRITICAL FINDINGS

### 11.1 Implementation Completeness

**Implemented Features (70-80%):**
1. ✅ Snake_case API (`create_job`, `update_job`, `update_plugin`)
2. ✅ Explicit `target_id` parameter in plugin services
3. ✅ `JobStatus.plugins` and `RunStatus.plugins` dicts
4. ✅ Jobs as key-based dict (`_jobs: Dict[str, JobState]`)
5. ✅ Scanner using `update_plugin` for run-level data
6. ✅ Per-run/job distinction via `target_id.startswith("run_")`
7. ✅ Backward compatibility aliases

**Partially Implemented (20-30%):**
1. ⚠️ Flat plugin data - works in manager but models still have wrapper
2. ⚠️ Dual storage - `_plugins_storage` and `job.plugins` both exist
3. ⚠️ MongoDB schema - still uses composite keys, not target_id

**Not Implemented:**
1. ❌ Complete removal of PluginState.status wrapper
2. ❌ MongoDB single document per target_id
3. ❌ `mark_plugin_started`/`mark_plugin_completed` system methods
4. ❌ Full unification of plugin storage

### 11.2 Architectural Issues

#### Issue 1: Dual Plugin Storage
**Problem:** Plugin data stored in two places
- `_plugins_storage: Dict[str, Dict[str, PluginState]]`
- `job.plugins: Dict[str, Dict]`

**Impact:** Potential sync issues, memory overhead

**Recommendation:** Unify to single storage location (job.plugins)

#### Issue 2: Status/Data Wrapper Not Fully Removed
**Problem:** PluginState and PluginData classes still exist with status/data split

**Files:**
- `state/models.py:303-320` (PluginState)
- `state/models.py:324-353` (PluginData)

**Impact:** 
- Template access inconsistent (sometimes `.data.movie`, sometimes `.movie`)
- Confusion about correct access pattern

**Recommendation:** Remove PluginState/PluginData classes entirely, use flat dict

#### Issue 3: MongoDB Schema Not Migrated
**Problem:** Still uses (run_id, job_id, plugin_name) composite index

**Target:** Use target_id as _id
```javascript
// Current
{_id: ObjectId, job_id: "job_xxx", plugin_name: "tmdb", data: {...}}

// Target
{_id: "job_xxx", tmdb: {...}, renamer: {...}}
```

**Impact:** More database documents, slower queries

**Recommendation:** Implement target_id-based schema migration

#### Issue 4: Test Suite Out of Sync
**Problem:** Tests use old API names (`start_execution`, `register_match`)

**Impact:** Cannot verify new architecture works correctly

**Recommendation:** Update all tests to new API

### 11.3 Code Quality Observations

**Strengths:**
- Excellent separation of concerns
- Well-documented code with docstrings
- Type hints used throughout
- Consistent naming conventions
- Event-driven design allows extensibility

**Weaknesses:**
- Legacy code not fully removed
- Some duplicate method definitions (`get_plugin_data` twice in manager.py)
- Configuration complexity (aliases, FlexGet compat, Jinja2)
- Test coverage gaps

---

## 12. RECOMMENDATIONS

### 12.1 Immediate Actions (High Priority)

1. **Complete Flat Data Structure Migration**
   - Remove `PluginState` and `PluginData` classes
   - Update all plugins to use flat access
   - Update templates in config.yml
   - Update API response schemas

2. **Unify Plugin Storage**
   - Remove `_plugins_storage` dict
   - Use only `job.plugins` and separate run plugins storage
   - Update `update_plugin` to write only to job.plugins

3. **Update Test Suite**
   - Rename `start_execution` → `start_run`
   - Rename `register_match` → `create_job`
   - Add tests for Session 17 features (jobs dict, flat plugin data)

4. **Remove Legacy Code**
   - Delete branches-related code from `infrastructure/database/mongodb.py`
   - Mark MongoDBPersistence as deprecated, remove after migration

### 12.2 Medium Priority

5. **Implement System Plugin Status Methods**
   ```python
   def mark_plugin_started(self, target_id, plugin_name):
       """System calls when plugin starts"""
       
   def mark_plugin_completed(self, target_id, plugin_name, success, error=None):
       """System calls when plugin completes"""
   ```

6. **MongoDB Schema Migration**
   - Create migration script for existing data
   - Implement target_id-based schema
   - Update indexes
   - Update persistence layer

7. **Documentation Updates**
   - Sync PHILOSOPHY.md with actual implementation
   - Update PLUGIN_SDK.md with Session 17 patterns
   - Create migration guide for plugin developers

### 12.3 Low Priority (Future)

8. **Performance Optimization**
   - Profile plugin execution
   - Optimize MongoDB queries
   - Consider caching strategy

9. **Plugin Ecosystem**
   - Update disabled plugins (omdb, tvdb, tvmaze)
   - Create plugin development guide
   - Add plugin testing utilities

10. **API Enhancements**
    - WebSocket support for real-time updates
    - GraphQL endpoint consideration
    - Better error responses

---

## 13. CONCLUSION

### 13.1 Architecture Assessment

The Archiverr project has a **solid architectural foundation** with clear separation of concerns, extensible plugin system, and flexible configuration. The refactoring in Sessions 16 V2 and 17 has been **70-80% successfully implemented**, with the core architectural changes (snake_case API, explicit parameters, status tracking) in place.

### 13.2 Implementation Status

**What Works Well:**
- Plugin discovery and loading system
- State management with unified context
- Event-driven communication
- Backward compatibility maintained
- FastAPI integration clean and RESTful

**What Needs Work:**
- Complete flat data migration
- MongoDB schema alignment
- Test suite updates
- Legacy code removal
- Full documentation sync

### 13.3 Path Forward

To reach 100% compliance with Session 16 V2 and 17 decisions:

1. **Week 1:** Complete flat data structure, remove wrappers
2. **Week 2:** Unify storage, update tests
3. **Week 3:** MongoDB schema migration
4. **Week 4:** Documentation, cleanup, optimization

The project is in a **good position** to complete these remaining items without major architectural changes. The foundation is solid, and the remaining work is primarily cleanup and consistency enforcement.

### 13.4 Final Score

| Category | Score | Notes |
|----------|-------|-------|
| Architecture Design | 9/10 | Excellent separation, extensibility |
| Session 16 V2 Compliance | 7/10 | Core features done, details pending |
| Session 17 Compliance | 7.5/10 | Jobs dict done, plugins partial |
| Code Quality | 8/10 | Clean, typed, documented |
| Test Coverage | 5/10 | Tests not updated after refactor |
| Documentation | 6/10 | Some drift from implementation |
| **Overall** | **7.5/10** | **Solid foundation, needs completion** |

---

**END OF DEEP DIVE ANALYSIS**

Generated: 2024-12-18  
Document Version: 1.0  
Total Sections: 13  
Total Pages: ~50  
Analysis Depth: Complete

