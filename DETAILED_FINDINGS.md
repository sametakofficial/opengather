# ARCHIVERR - DETAILED COMPONENT ANALYSIS

**Comprehensive breakdown of every component with industry standard assessment**

---

## COMPONENT INVENTORY & STATUS

### ✅ GOOD COMPONENTS (Industry Standard)

#### 1. **API Structure** (`src/archiverr/api/`)

```
api/
├── v1/               # Versioned API (✓ best practice)
├── deps/             # Dependency injection (✓ testable)
├── middleware/       # Reusable middleware (✓ separation of concerns)
└── main.py           # FastAPI app (✓ modern framework)
```

**Assessment:** **EXCELLENT** - Follows FastAPI best practices, versioned endpoints, proper DI.

**Comparison:** Similar to Django REST Framework structure, better than Flask blueprints.

#### 2. **Database Layer** (`src/archiverr/infrastructure/database/`)

```
database/
├── interface.py       # Protocol/ABC (✓ DIP compliance)
├── mongodb.py         # Production impl
├── pymongo_persistence.py  # Alternative impl
├── mock.py            # Testing impl
└── connection.py      # Factory pattern
```

**Assessment:** **SOLID** - Good abstraction, testable, swappable implementations.

**Issue:** Too many implementations (3), should pick one for production.

#### 3. **Event Bus** (`src/archiverr/events/bus.py`)

```python
class EventBus:
    def subscribe(event, handler)
    def emit(event, data)
    def get_history()
```

**Assessment:** **GOOD DESIGN** - Thread-safe, history tracking, wildcard support.

**Issue:** Under-utilized (only 2 handlers in entire codebase).

---

### ⚠️ QUESTIONABLE COMPONENTS (Over-engineered or Unused)

#### 4. **Memory Management** (`src/archiverr/core/memory/`)

**Files:**

- `tracker.py` - Memory usage tracking
- `flush_manager.py` - Eviction manager
- `lazy_loader.py` - Lazy loading

**Purpose:** Prevent OOM by evicting completed job data.

**Assessment:** **PREMATURE OPTIMIZATION**

**Evidence:**

```python
# tracker.py:50
def __init__(self, threshold_mb: float = 500.0):
    """Threshold before eviction triggers"""
```

**Problems:**

1. **Not needed for CLI tool** - processes run once and exit
2. **No user reports of memory issues** - solving imaginary problem
3. **Adds complexity** - 184 lines of size estimation code
4. **psutil dependency** - adds external dep for questionable feature

**Industry Standard:** Beets, FlexGet, MediaCMS - NONE have memory eviction.

**Recommendation:** **DELETE** entire `memory/` folder. If memory is an issue, use Python's built-in `del` statement.

#### 5. **Workers System** (`src/archiverr/core/workers/`)

**Files:**

- `broker.py` - Message broker abstraction
- `tasks.py` - Celery-style task definitions

```python
# tasks.py:1
"""Background task execution with Celery"""
```

**Assessment:** **DEAD CODE**

**Evidence:**

- Not imported anywhere in codebase
- No Celery in requirements.txt
- No async task execution in current flow

**Industry Standard:** Only needed for:

- Web apps with long-running operations
- Multi-user systems
- API servers processing requests

Archiverr is a **single-user CLI tool** - no need for background workers.

**Recommendation:** **DELETE** entire `workers/` folder.

#### 6. **Triggers System** (`src/archiverr/core/triggers/`)

**Files:**

- `manager.py` - Trigger rule evaluation
- `evaluator.py` - Rule logic
- `matcher.py` - Value matching

**Purpose:** Conditional plugin execution with rules like "all_success", "one_success".

**Assessment:** **OVER-ENGINEERED**

**Current Usage:** Only used in `requires_validator.py` for dependency checking.

**Alternative:** Simple boolean checks.

```python
# Current (complex):
manager = TriggerRuleManager()
should_run, reason = manager.should_execute(
    "all_success",
    ["plugin.tmdb.data:success"],
    state
)

# Industry Standard (simple):
if all(plugin.status.success for plugin in dependencies):
    run_plugin()
```

**Comparison:**

- Beets: No trigger system
- FlexGet: Uses simple `if` statements
- Airflow: Has trigger system (but it's a workflow orchestrator, not a CLI tool)

**Recommendation:** **SIMPLIFY** - merge into single function, remove 3-file structure.

#### 7. **Reports System** (`src/archiverr/core/reports/`)

**Files:**

- `report_generator.py` - Generate reports
- `response_simplifier.py` - Simplify API responses

**Assessment:** **UNCLEAR PURPOSE**

**Usage:** Only used in API endpoints to format responses.

**Problem:** Should be in `api/` folder, not `core/`.

**Recommendation:** **MOVE** to `api/formatters/` or merge into `models/response_builder.py`.

#### 8. **Tasks System** (`src/archiverr/core/tasks/`)

**Files:**

- `task_manager.py` - Execute print/save tasks
- `template_manager.py` - Jinja2 template rendering

**Purpose:** Execute tasks defined in config (print output, save files).

**Assessment:** **OKAY but misplaced**

**Problem:** Mixed with core orchestration logic. Should be a plugin.

**Industry Standard:**

- Beets: Tasks are plugins (`beets.plugins.write`, `beets.plugins.scrub`)
- FlexGet: Tasks are first-class config entities

**Recommendation:** **REFACTOR** into `output` plugin or separate `tasker` plugin (already exists!).

**Wait, `tasker` plugin already exists!** So why is there a `core/tasks/` too? **DUPLICATION**.

---

### 🔴 PROBLEM COMPONENTS (Broken or Confusing)

#### 9. **Config System** (4 files, 4 steps!)

**Files:**

- `utils/config_loader.py` - Main loader with 4-step process
- `utils/config_normalizer.py` - Format detection
- `utils/yaml_loader.py` - !include directive
- `core/config/alias_resolver.py` - Alias resolution

**Process:**

```
1. load_yaml_with_includes()   # !include directive
2. expand_env_vars()            # ${ENV_VAR} expansion
3. normalize_config()           # FlexGet vs plugins: wrapper
4. resolve_aliases()            # m.title → plugin.tmdb.movie.title
```

**Assessment:** **OVER-COMPLEX**

**Issues:**

**Issue #1: Alias System is Fragile**

```python
# alias_resolver.py:320
pattern_with_dot = r'(?<![.\w])' + re.escape(alias) + r'\.'
result = re.sub(pattern_with_dot, target + '.', result)
```

**Regex on user strings = bugs waiting to happen.**

**Issue #2: Multiple Format Support**

```python
def detect_config_format(config):
    """Detect: new_format, plugins_wrapper, or flexget_style"""
```

**Supporting 3 config formats = maintenance nightmare.**

**Issue #3: !include Directive Rarely Used**

In practice, users just write one `config.yml` file. The `!include` feature adds complexity for minimal benefit.

**Industry Standard:**

- **Beets:** Single config format, no includes, no aliases. Just YAML + env vars.
- **FlexGet:** Single format, no aliases.
- **Ansible:** Has includes but it's a multi-file automation tool (different use case).

**Recommendation:**

1. **Pick ONE config format** (new format: plugins as keys)
2. **Remove alias system** (too fragile)
3. **Keep !include** only if actually used by community
4. **Simplify to 2 steps:** load → expand env vars → done

#### 10. **Plugin System** (5-Layer Abstraction!)

**Layers:**

```
1. PluginDiscovery  (finds manifest.yml files)
2. PluginLoader     (imports Python modules)
3. PluginRegistry   (organizes by stage)
4. PluginExecutor   (runs single plugin)
5. StageExecutor    (runs stage of plugins)
```

**Assessment:** **OVER-LAYERED**

**Each layer has ~100-300 lines but mostly delegation:**

```python
# registry.py:141
self._all_manifests = self._discovery.discover()
self._all_plugins = self._loader.load_by_category('output')
```

**Problem:** Hard to follow, hard to debug, no clear benefit.

**Industry Standard:**

- **Beets:** 2 layers (PluginLoader + PluginRegistry)
- **FlexGet:** 1 layer (PluginManager)

**Recommendation:** **MERGE** Discovery + Loader into Registry (3 → 1 class).

#### 11. **State Management** (6 Global Objects!)

**Current:**

```python
class GlobalStateManager:
    @property
    def run()      # 1. Current run (read-only)

    @property
    def config()   # 2. Frozen config (read-only)

    @property
    def job()      # 3. Current job (per_job only)

    @property
    def jobs()     # 4. All jobs (per_job read-only)

    @property
    def plugin()   # 5. Current job plugins (per_job only)

    @property
    def plugins()  # 6. All jobs plugins (per_job read-only)
```

**Assessment:** **TOO COMPLEX**

**Problems:**

1. **Confusing names:** `plugin` vs `plugins`, `job` vs `jobs`
2. **Complex access control:** per_run vs per_job enforced via PluginServices
3. **Not actually "global":** Some are per-job context

**Industry Standard:**

- **Beets:** 1 object (`library`)
- **FlexGet:** 2 objects (`task`, `config`)
- **SQLAlchemy (complex ORM):** 2 objects (`session`, `query`)

**Recommendation:** **SIMPLIFY** to 3 objects:

```python
class ExecutionContext:
    run: RunState        # Current run metadata
    config: Dict         # Frozen config
    current: JobState    # Current job being processed
```

#### 12. **Models Folder** (`src/archiverr/models/`)

**Contents:** 1 file (`response_builder.py`)

**Assessment:** **POINTLESS FOLDER**

**Rule:** Don't create a folder for 1 file.

**Recommendation:** **MERGE** into `api/schemas.py` or remove folder.

#### 13. **CLI Folder** (`src/archiverr/cli/`)

**Contents:** 1 file (`main.py`)

**Assessment:** **UNNECESSARY NESTING**

**Standard:** CLI code goes in `__main__.py` at package root.

**Recommendation:** **MOVE** `cli/main.py` → `__main__.py`, delete `cli/` folder.

---

## UNUSED/EMPTY FOLDERS

1. **`core/reports/`** - Empty `__init__.py` only
2. **`reports/`** - Completely empty folder
3. **`plugins/mock_test/`** - Test plugin, shouldn't be in main `plugins/` folder

**Recommendation:** **DELETE** all empty folders, move test plugin to `tests/fixtures/`.

---

## NAMING INCONSISTENCIES (Critical!)

### Problem: Dual Terminology

**Runs vs Executions:**

```python
# manager.py has BOTH:
def start_run()          # New
def start_execution()    # Legacy alias

@property
def run()               # New
@property
def execution()         # Legacy alias
```

**Jobs vs Matches:**

```python
def create_job()        # New
def register_match()    # Legacy alias

# MongoDB:
jobs collection         # New
matches collection      # Legacy (still used!)
```

**Assessment:** **CONFUSING for developers and users.**

**Industry Standard:** Pick ONE term and stick with it.

- Beets: "tracks" and "albums"
- FlexGet: "entries"
- Airflow: "tasks" and "dag runs"

**Recommendation:**

1. Use "run" (not execution)
2. Use "job" (not match)
3. **Remove all legacy aliases**
4. **Rename MongoDB collections** (migration script needed)

---

## DATABASE SCHEMA ISSUES

### Duplication: New + Legacy Collections

**Current MongoDB Collections:**

**NEW (Session 12):**

- `runs` - Clean run data
- `jobs` - Clean job data
- `plugins` - Clean plugin data

**LEGACY (Old):**

- `executions` - Same as runs
- `matches` - Same as jobs
- `plugin_results` - Same as plugins

**VERSIONING:**

- `branches` - Active
- `commits` - **CREATED BUT NEVER USED!**

**Assessment:** **WASTE OF STORAGE**

Every run is written TWICE (once to `runs`, once to `executions`).

**Code Evidence:**

```python
# manager.py:170-174
if hasattr(self._persistence, 'save_run'):
    self._persistence.save_run(self._run)
elif hasattr(self._persistence, 'save_execution'):
    # Legacy persistence adapter
    self._persistence.save_execution(self._run_to_execution())
```

**Problem:** Maintaining parallel schemas is error-prone.

**Recommendation:**

1. **Phase 1:** Write to both (current - for backward compat)
2. **Phase 2:** Migration script to copy old data to new collections
3. **Phase 3:** Drop legacy collections
4. **Phase 4:** Remove adapter code

---

## FILE STRUCTURE RECOMMENDATIONS

### Current (Problematic):

```
src/archiverr/
├── api/              ✓
├── cli/              ❌ 1 file, unnecessary folder
├── core/
│   ├── config/       ✓ Config handling
│   ├── locking/      ✓ FS locks
│   ├── memory/       ❌ DELETE (premature optimization)
│   ├── plugins/      ⚠️ Should be top-level
│   ├── reports/      ❌ Should be in api/
│   ├── services/     ✓ Shared services
│   ├── tasks/        ❌ Duplicate of tasker plugin
│   ├── triggers/     ⚠️ Over-engineered
│   ├── validation/   ✓ Validators
│   └── workers/      ❌ DELETE (dead code)
├── events/           ✓ Event bus
├── infrastructure/   ✓ Database
├── models/           ❌ 1 file, unnecessary folder
├── plugins/          ✓ Plugin implementations
├── state/            ✓ State management
└── utils/            ⚠️ Some should be in core
```

### Recommended (Clean):

```
src/archiverr/
├── __main__.py       # Entry point (move from cli/main.py)
│
├── core/             # CORE LOGIC ONLY
│   ├── orchestrator.py
│   ├── config.py     # Merge config loader + validator
│   ├── state.py      # State manager
│   └── exceptions.py
│
├── plugins/          # PLUGIN SYSTEM + IMPLEMENTATIONS
│   ├── __init__.py
│   ├── registry.py   # Merge discovery + loader + registry
│   ├── executor.py
│   ├── services.py
│   ├── scanner/      # Plugin implementations
│   ├── renamer/
│   ├── tmdb/
│   └── tasker/       # Includes task execution (remove core/tasks/)
│
├── database/         # PERSISTENCE (rename from infrastructure)
│   ├── connection.py
│   ├── mongodb.py    # Choose ONE implementation
│   └── mock.py       # For testing only
│
├── api/              # WEB API
│   ├── v1/
│   ├── deps/
│   ├── middleware/
│   ├── formatters/   # Move reports here
│   └── main.py
│
├── events.py         # Single file (simple event bus)
└── utils.py          # Single file (helpers)
```

**Changes:**

- ✅ Flat structure (less nesting)
- ✅ Clear boundaries (core vs plugins vs api)
- ✅ No unnecessary folders for 1-2 files
- ✅ Logical grouping (database separate from api)

---

## CRITICAL: COMMITS PROBLEM (Extended Analysis)

### What Commits SHOULD Do (Git-like Versioning)

**Theory:**

```
Commit Graph:
  main branch:    A → B → C → D (current)
                      ↓
  experiment branch: E → F
```

**Use Cases:**

1. **Time travel:** "Show me how jobs looked on Dec 1st"
2. **Comparison:** "What changed between commit A and commit C?"
3. **Branching:** Run experiments without affecting main
4. **Rollback:** "Restore state to commit B"

### What Commits ACTUALLY Do in Archiverr

**Reality:**

```python
# manager.py:284-295
commit = self._persistence.create_commit(
    branch_id=branch_id,
    execution_id=self._run.id,
    message=f"Run {self._run.id}: {self._run.status.total_jobs} jobs",
    metadata={...}
)
```

**Then... nothing. Commit is created and ignored.**

**Missing:**

- ❌ No `GET /api/v1/commits/{commit_id}` endpoint returns actual run data
- ❌ No `checkout_commit()` usage in codebase
- ❌ No history traversal via `parent_commit_id`
- ❌ No diff between commits
- ❌ No rollback functionality

**Conclusion:** **Commits are write-only data. DEAD WEIGHT.**

### Why Industry Doesn't Use Commits for This

**MongoDB Official Docs:**

> "The Document Versioning Pattern works best if documents are updated **infrequently** and there are **few documents** that require version tracking."

**Archiverr creates 1 commit per run. If you run daily = 365 commits/year.**

**Industry Pattern:**

**Option A: Simple History (Beets, MediaCMS)**

```
runs table/collection with timestamp
Query: SELECT * FROM runs WHERE timestamp > '2024-12-01'
```

**Option B: Snapshot Pattern (Config management tools)**

```
current_state collection (1 document, updated)
history collection (append-only log)
```

**Option C: Event Sourcing (Kafka, Event Store)**

```
events stream (all state changes)
projections/snapshots for current state
```

**Archiverr doesn't fit any of these.** It's trying to be Git but:

- Not version control (no file diffs)
- Not collaboration tool (single user)
- Not workflow system (no branching logic)

### Decision Matrix: Commits vs Runs

| Feature          | With Commits         | Without Commits    | Winner      |
| ---------------- | -------------------- | ------------------ | ----------- |
| Storage          | 2x (runs + commits)  | 1x (runs only)     | **Without** |
| Query Speed      | Slower (JOIN needed) | Fast (direct)      | **Without** |
| Complexity       | High (3 collections) | Low (1 collection) | **Without** |
| Features         | Branching, history   | Timestamp queries  | **Tie**     |
| Code Maintenance | 200+ lines           | 50 lines           | **Without** |

**Recommendation:** **REMOVE COMMITS.** Keep branches as simple tags.

```yaml
# Simplified schema
runs:
  - id: run_abc123
    branch: "main" # Simple string, not ObjectId
    created_at: "2024-12-09T20:00:00Z"
    # ... rest of run data
```

**Query patterns:**

```javascript
// Recent runs
db.runs.find().sort({ created_at: -1 }).limit(10);

// Runs on main branch
db.runs.find({ branch: "main" });

// Runs in date range
db.runs.find({ created_at: { $gte: startDate, $lt: endDate } });

// "History" = just list of runs sorted by date
```

---

## FINAL ASSESSMENT SUMMARY

### Over-Engineered (Remove or Simplify)

1. ❌ **Memory management system** - DELETE entire `core/memory/`
2. ❌ **Workers/Celery system** - DELETE entire `core/workers/`
3. ❌ **Commits (versioning)** - DELETE commits collection + code
4. ⚠️ **Triggers system** - SIMPLIFY to single function
5. ⚠️ **Plugin layers** - MERGE 5 layers into 2
6. ⚠️ **Config system** - SIMPLIFY 4 steps to 2
7. ⚠️ **State management** - REDUCE 6 objects to 3

### Under-Utilized (Needs Work)

1. 🔶 **Event bus** - Either use fully or remove
2. 🔶 **API versioning** - Good foundation, expand it
3. 🔶 **Plugin SDK** - Good design, but not enforced

### Good (Keep As-Is)

1. ✅ **API structure** - Modern FastAPI, versioned
2. ✅ **Database abstraction** - Clean interface
3. ✅ **Stage-based execution** - Solid design
4. ✅ **Orchestrator pattern** - Clean separation

### Critical Issues

1. 🔴 **Naming inconsistency** - run/execution, job/match
2. 🔴 **Dual schemas** - new + legacy collections
3. 🔴 **Dead code** - workers, memory, unused utils
4. 🔴 **File structure** - too nested, unclear boundaries

---

## RECOMMENDED REFACTORING ORDER

### Phase 1: Deletions (1 week, low risk)

1. Delete `core/memory/` (644 lines)
2. Delete `core/workers/` (189 lines)
3. Delete empty folders (`reports/`, `core/reports/`)
4. Delete commits collection + code (300+ lines)

**Result:** -1,133 lines, simpler codebase

### Phase 2: Consolidation (2 weeks, medium risk)

5. Merge plugin layers (Discovery + Loader → Registry)
6. Simplify config (4 steps → 2 steps, remove aliases)
7. Move files to correct locations (cli → **main**, reports → api)

**Result:** Clearer structure, easier navigation

### Phase 3: Standardization (2 weeks, breaking changes)

8. Remove all "execution" terminology → use "run"
9. Remove all "match" terminology → use "job"
10. Drop legacy MongoDB collections (after migration)

**Result:** Consistent naming, single schema

### Phase 4: Simplification (3 weeks, architectural)

11. Simplify state (6 objects → 3)
12. Simplify triggers (3 files → 1 function)
13. Replace custom Debugger with logging module
14. Add CLI subcommands (click library)

**Result:** Industry-standard patterns, better UX

**Total:** ~8 weeks for complete refactoring

---

**END OF DETAILED ANALYSIS**
