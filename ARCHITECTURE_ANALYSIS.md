# ARCHIVERR - COMPREHENSIVE ARCHITECTURE ANALYSIS

**Date:** December 9, 2024  
**Analysis Type:** Full System Architecture Review  
**Focus:** Industry Standards Compliance, Execution Flows, Data Model Issues

---

## EXECUTIVE SUMMARY

This is a **ruthless, unfiltered analysis** of Archiverr's architecture based on code review (NO .md files read), industry research, and comparison with similar open-source Python projects (beets, MediaCMS).

### Critical Findings (Priority Order)

1. **COMMITS NOT USED** - MongoDB branches exist but commits are created but never utilized
2. **RUNS vs COMMITS confusion** - unclear versioning strategy
3. **Over-engineered state management** - 6 global state objects with complex interactions
4. **Plugin system fragmentation** - multiple discovery/loading/registry layers
5. **File structure issues** - mixing concerns, unclear boundaries
6. **Database schema duplication** - legacy + new collections coexist

---

## PART 1: EXECUTION FLOW DIAGRAMS

### 1.1 COMPLETE SYSTEM FLOW (High-Level)

```
┌─────────────────────────────────────────────────────────────┐
│                    USER STARTS ARCHIVERR                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  __main__.py - Entry Point                                   │
│  • CLI mode (default) or API mode (serve)                   │
│  • Load config.yml with env var expansion                   │
│  • Initialize debugger based on log_level                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  build_orchestrator() - Dependency Injection                 │
│  ├─ EventBus (debugger)                                     │
│  ├─ GlobalStateManager()                                    │
│  ├─ DatabaseConnection.from_env()                           │
│  │   └─ PyMongoPersistence OR MockPersistence              │
│  ├─ PluginRegistry(config, debugger)                        │
│  └─ Orchestrator(all dependencies)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator.run() - Main Execution Loop                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
            ┌────────────┴────────────┐
            │                         │
            ▼                         ▼
    ┌──────────────┐        ┌──────────────┐
    │ _initialize()│        │ _execute_    │
    │              │   →    │ per_run_     │
    │              │        │ plugins()    │
    └──────────────┘        └──────┬───────┘
            │                      │
            │                      ▼
            │            ┌─────────────────┐
            │            │ Scanner Plugin  │
            │            │ (INPUT/per_run) │
            │            │ • Creates Jobs  │
            │            └─────────────────┘
            │
            ▼
    ┌─────────────────────────────────┐
    │ _execute_stages()               │
    │ LOOP: [PARSE, DATA, OUTPUT]     │
    └─────────┬───────────────────────┘
              │
              ▼
    ┌─────────────────────────────────┐
    │ StageExecutor.execute_stage()   │
    │ • Get plugins for stage         │
    │ • Get all jobs from state       │
    │ • LOOP each job:                │
    │   └─ Execute plugins for job    │
    └─────────┬───────────────────────┘
              │
              ▼
    ┌─────────────────────────────────┐
    │ PluginExecutor.execute()        │
    │ • Create PluginServices context │
    │ • Call plugin.execute_job()     │
    │ • Handle result/errors          │
    └─────────┬───────────────────────┘
              │
              ▼
    ┌─────────────────────────────────┐
    │ _finalize()                     │
    │ • Save JSON output (tasker)     │
    │ • Complete run in state         │
    │ • Create commit (versioning)    │
    │ • Emit run.completed event      │
    └─────────────────────────────────┘
```

### 1.2 CONFIG LOADING FLOW

```
┌───────────────────────────────────────────────────────┐
│ load_config_with_tracking("config.yml")               │
└────────────────┬──────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 1. load_yaml_with_includes()                           │
│    • Process !include directives                       │
│    • Load tasks/*.yml, plugins/*/config.yml            │
│    • Merge all YAML files                              │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 2. expand_env_vars()                                   │
│    • Replace ${TMDB_API_KEY} with actual value         │
│    • Recursive expansion in dicts/lists                │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 3. normalize_config()                                  │
│    • Detect format: FlexGet-style vs plugins: wrapper  │
│    • Normalize to unified structure                    │
│    • Extract enabled plugins list                      │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 4. resolve_aliases()                                   │
│    • Replace m.title → plugin.tmdb.movie.title         │
│    • Replace movie.name → renamer.parsed.movie.name    │
│    • Template-aware replacement                        │
└────────────────┬───────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│ 5. Store original for snapshot (mask API keys)         │
│    • _original_config = original (with ${VAR} syntax)  │
│    • Return expanded config for runtime use            │
└────────────────────────────────────────────────────────┘

RESULT: Fully expanded, normalized, alias-resolved config
        + Original preserved for safe storage
```

### 1.3 JOB EXECUTION FLOW (Per-Job Plugin)

```
┌──────────────────────────────────────────────────────────┐
│ StageExecutor: For each JOB in JOBS list                 │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│ 1. state.set_current_job(job_id)                         │
│    • Sets GlobalStateManager._current_job                │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│ 2. For each PLUGIN in stage                              │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Create PluginServices                                 │
│    services = PluginServices(                            │
│        state=state,                                      │
│        event_bus=event_bus,                              │
│        logger=debugger,                                  │
│        config=config,                                    │
│        mode="per_job",                                   │
│        current_job_id=job.id,                            │
│        current_plugin_name=plugin_name                   │
│    )                                                     │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│ 4. plugin.execute_job(services)                          │
│    • Plugin accesses:                                    │
│      - services.get_current_job()  → job state           │
│      - services.updatePlugin(data) → write data          │
│      - services.updateJob(key, val)→ update job          │
│      - services.emit(event, data)  → publish event       │
│                                                          │
│    • Plugin CANNOT:                                      │
│      - Directly access GlobalStateManager                │
│      - Modify other jobs                                 │
│      - Create jobs (per_job mode)                        │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│ 5. Result handling                                       │
│    • Success: job.add_executed(plugin_name)              │
│    • Failure: job.add_failed(plugin_name)                │
│    • Emit plugin.completed / plugin.failed               │
│    • Persist plugin data to MongoDB                      │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│ 6. state.clear_current_job()                             │
│    • Clears context for next job                         │
└──────────────────────────────────────────────────────────┘
```

### 1.4 GLOBAL STATE ARCHITECTURE (6 State Objects)

```
┌─────────────────────────────────────────────────────────────┐
│           GlobalStateManager - 6 State Objects              │
└─────────────────────────────────────────────────────────────┘

┌────────────┐  ┌────────────┐  ┌────────────┐
│ 1. run     │  │ 2. config  │  │ 3. job     │
│ (RunState) │  │ (Dict)     │  │ (JobState) │
│ READ-ONLY  │  │ FROZEN     │  │ PER_JOB    │
│ All modes  │  │ READ-ONLY  │  │ ONLY       │
└────────────┘  └────────────┘  └────────────┘

┌────────────┐  ┌────────────┐  ┌────────────┐
│ 4. jobs    │  │ 5. plugin  │  │ 6. plugins │
│ (List)     │  │ (Dict)     │  │ (List)     │
│ READ-ONLY  │  │ PER_JOB    │  │ READ-ONLY  │
│ PER_JOB    │  │ CURRENT    │  │ PER_JOB    │
└────────────┘  └────────────┘  └────────────┘

ACCESS PATTERNS:
• per_run plugins:  read(run, config) + write(createJob)
• per_job plugins:  read(all 6) + write(job, plugin current)
• Orchestrator:     full access (creates/manages all)
```

### 1.5 MONGODB PERSISTENCE FLOW

```
┌─────────────────────────────────────────────────────────┐
│ MongoDB Collections (NEW + LEGACY)                      │
└─────────────────────────────────────────────────────────┘

NEW (Session 12):
┌─────────┐  ┌─────────┐  ┌─────────┐
│  runs   │  │  jobs   │  │ plugins │
│ (clean) │  │ (clean) │  │ (clean) │
└─────────┘  └─────────┘  └─────────┘

LEGACY (Old):
┌────────────┐  ┌──────────┐  ┌────────────────┐
│ executions │  │ matches  │  │ plugin_results │
│ (old runs) │  │(old jobs)│  │  (old plugins) │
└────────────┘  └──────────┘  └────────────────┘

VERSIONING (Git-like):
┌──────────┐  ┌──────────┐
│ branches │  │ commits  │
│ (active) │  │(UNUSED!) │
└──────────┘  └──────────┘

WRITE FLOW:
1. state.start_run(config)
   └─> persistence.save_run(run)
   └─> persistence.save_execution(execution)  # Legacy adapter

2. state.create_job(input_value, input_data)
   └─> persistence.save_job(job)
   └─> persistence.save_match(match)  # Legacy adapter

3. state.update_plugin(job_id, plugin_name, data)
   └─> persistence.save_plugin(plugin_data)

4. state.complete_run(branch_name)
   └─> persistence.create_branch("main") if not exists
   └─> persistence.create_commit(run_id, branch_id, message)
   └─> **COMMIT CREATED BUT NEVER USED!**
```

---

## PART 2: CRITICAL ISSUE - COMMITS VS RUNS

### 2.1 Current Implementation

**WHAT EXISTS:**

```python
# manager.py:261-301
def _create_commit(self, branch_name: str = "main"):
    branch = self._persistence.get_branch(name=branch_name)
    if not branch:
        branch = self._persistence.create_branch(name=branch_name, ...)

    commit = self._persistence.create_commit(
        branch_id=branch_id,
        execution_id=self._run.id,
        message=f"Run {self._run.id}: {self._run.status.total_jobs} jobs",
        metadata={...}
    )
```

**PROBLEM:** Commits are created at the end of every run but:

- ❌ NOT used for querying
- ❌ NOT used in API endpoints
- ❌ NOT used for history traversal
- ❌ NOT used for diff/compare operations

### 2.2 MongoDB Versioning Industry Standards

Based on research (MongoDB docs, Stack Overflow patterns):

**Pattern 1: Document Versioning Pattern** (MongoDB Official)

```
currentPolicies collection  → Current version only
policyRevisions collection  → All historical versions

Each document has:
- revision: number
- parent_revision: number (optional)
- created_at: timestamp
```

**Pattern 2: Event Sourcing Pattern**

```
events collection → All state changes as events
snapshots collection → Periodic full state snapshots

Query current: aggregate all events
Query history: replay events up to timestamp
```

**Pattern 3: Git-like Versioning** (What Archiverr attempts)

```
branches collection → Named branches (main, dev, etc.)
commits collection → Immutable snapshots with parent links

Each commit points to:
- branch_id
- parent_commit_id
- execution_id (snapshot reference)
```

### 2.3 Industry Standard Decision

**RECOMMENDATION: ELIMINATE COMMITS, USE RUNS DIRECTLY**

**Rationale:**

1. **Archiverr is NOT a version control system** - it's a media organizer
2. **Commits add complexity without value:**

   - Runs already have timestamps, metadata, status
   - No need for branching (not a collaborative system)
   - No need for merging or diff operations
   - No rollback requirements

3. **Similar projects DON'T use commits:**

   - **beets**: Uses simple database with track history
   - **MediaCMS**: Uses Django ORM with standard audit fields
   - **FlexGet**: Uses execution history without commits

4. **Branches are sufficient:**
   - Keep branches as "tags" or "categories" for runs
   - Example: `main`, `production`, `test`, `experiment`
   - Simpler query: "Get all runs on main branch"

**RECOMMENDED SCHEMA:**

```javascript
// runs collection
{
  _id: "run_abc123",
  branch: "main",  // Simple string, not ObjectId
  created_at: ISODate("2024-12-09T..."),
  status: "success",
  total_jobs: 45,
  config_snapshot: {...},
  metadata: {
    user: "samet",
    hostname: "...",
    version: "1.0.0"
  }
}

// NO commits collection needed!
// Query runs by branch: db.runs.find({branch: "main"})
// Query recent: db.runs.find().sort({created_at: -1}).limit(10)
// Query by date range: db.runs.find({created_at: {$gt: date}})
```

### 2.4 Action Items

**REMOVE:**

- `commits` collection entirely
- `create_commit()` method
- `get_commit()`, `list_commits()`, `checkout_commit()` methods
- API endpoints: `/api/v1/versioning/commits`

**KEEP:**

- `branches` collection (simplified to just names/tags)
- `runs` collection with `branch` field (string)

**SIMPLIFY:**

```python
# Old (complex)
run = complete_run()
branch = get_or_create_branch("main")
commit = create_commit(run_id, branch_id)

# New (simple)
run = complete_run(branch="main")  # Just a string!
```

---

## PART 3: ARCHITECTURE ISSUES

### 3.1 Over-Engineered Components

**❌ GLOBAL STATE MANAGER - TOO COMPLEX**

Current: 6 state objects with complex access control

```python
run, config, job, jobs, plugin, plugins
```

**Industry Standard:** 2-3 objects max

- Beets: `lib` (library) + `config`
- FlexGet: `task` + `config`

**Problem:**

- `plugin` vs `plugins` is confusing
- Access control via PluginServices is over-engineered
- Per-run vs per-job mode should be implicit, not explicit

**Solution:**

```python
# Simpler: 3 objects
class ExecutionContext:
    run: RunState         # Current run (read-only)
    config: Dict          # Frozen config (read-only)
    current: JobState     # Current job being processed (read-write)
```

**❌ PLUGIN SYSTEM - TOO MANY LAYERS**

Current layers:

1. PluginDiscovery (finds manifests)
2. PluginLoader (loads code)
3. PluginRegistry (organizes by stage)
4. PluginExecutor (runs plugins)
5. StageExecutor (runs stages)

**Industry Standard:** 2-3 layers

- Beets: PluginLoader + PluginRegistry
- FlexGet: PluginManager (single class)

**Problem:** Each layer has minimal logic, mostly delegation

**Solution:** Merge PluginDiscovery + PluginLoader into PluginRegistry

---

### 3.2 Under-Engineered Components

**❌ EVENT BUS - NOT FULLY UTILIZED**

Current: Events emitted but handlers barely used

```python
# Only 2 handlers registered in orchestrator.py:
on_job_completed()
on_plugin_completed()
```

**Problem:** Event bus designed for loose coupling but tight coupling still exists via direct state access

**Solution:** Either:

- A) Fully commit to event-driven (all state changes via events)
- B) Remove event bus, use direct calls (simpler for CLI tool)

**❌ CONFIG MERGE - OVERLY COMPLEX**

Current: 4-step process (includes, env vars, normalize, aliases)

**Problem:**

- Alias resolution via regex is fragile
- !include directive rarely used in practice
- Normalization tries to support too many formats

**Solution:** Pick ONE config format, enforce it

---

### 3.3 File/Folder Structure Issues

**CURRENT STRUCTURE ANALYSIS:**

```
src/archiverr/
├── api/              ✓ Good: Clear API separation
│   ├── v1/           ✓ Good: Versioned API
│   ├── deps/         ✓ Good: Dependency injection
│   └── middleware/   ✓ Good: Reusable middleware
│
├── cli/              ❌ BAD: Only 1 file, should be in root
│   └── main.py
│
├── core/             ⚠️  MIXED: Too many concerns
│   ├── config/       ✓ Config handling
│   ├── locking/      ✓ FS lock system
│   ├── memory/       ❓ What is this? Lazy loading?
│   ├── orchestrator.py  ✓ Main coordinator
│   ├── plugins/      ❌ Should be top-level
│   ├── services/     ✓ Shared services
│   ├── tasks/        ❓ Unclear purpose
│   ├── triggers/     ❓ Unclear purpose
│   ├── validation/   ✓ Validators
│   └── workers/      ❓ Unused?
│
├── events/           ✓ Good: Event bus
├── infrastructure/   ✓ Good: Database layer
├── models/           ❌ BAD: Only 1 file (response_builder)
├── plugins/          ✓ Good: Plugin implementations
├── reports/          ❓ Empty folder?
├── state/            ✓ Good: State management
└── utils/            ⚠️  MIXED: Some should be in core
```

**INDUSTRY STANDARD COMPARISON (beets structure):**

```
beets/
├── __init__.py
├── ui/               # CLI + Web UI
├── library.py        # Core library management
├── plugins/          # Plugin implementations
├── util/             # Utilities
├── db/               # Database layer
└── autotag/          # Auto-tagging logic
```

**RECOMMENDED STRUCTURE:**

```
src/archiverr/
├── __init__.py
├── __main__.py       # Entry point (move cli/main.py here)
│
├── core/             # CORE ONLY (no sub-packages)
│   ├── orchestrator.py
│   ├── config.py     # Merge config loader + validator
│   ├── state.py      # State manager
│   └── exceptions.py
│
├── plugins/          # Plugin system + implementations
│   ├── __init__.py
│   ├── registry.py   # Merge discovery + loader + registry
│   ├── executor.py
│   ├── services.py
│   ├── scanner/
│   ├── renamer/
│   └── tmdb/
│
├── database/         # Rename from infrastructure/database
│   ├── connection.py
│   ├── mongodb.py
│   └── mock.py
│
├── api/              # Keep as is (good structure)
│   └── ...
│
├── events.py         # Single file, not folder
└── utils.py          # Single file with helpers
```

---

## PART 4: CODE QUALITY ISSUES

### 4.1 Naming Inconsistencies

**❌ RUNS vs EXECUTIONS**

```python
# manager.py has BOTH:
def start_run() → RunState
def start_execution() → same thing (legacy alias)

@property
def execution → actually returns run
```

**Solution:** Pick ONE: "run" (shorter, clearer)

**❌ JOBS vs MATCHES**

```python
# Same issue:
def create_job()
def register_match()  # Legacy alias

# MongoDB:
matches collection  # Old
jobs collection     # New
```

**Solution:** Pick ONE: "job" (standard term)

### 4.2 Redundant Code

**DUPLICATE PERSISTENCE ADAPTERS:**

```python
# manager.py:224-259 - Convert RunState → ExecutionState
def _run_to_execution():
    class LegacyExecution:
        def __init__(self, run: RunState):
            self.id = run.id
            # ... 20 lines of mapping
```

**Problem:** Maintaining parallel data structures is error-prone

**Solution:** Remove legacy collections, migrate data once

---

## PART 5: MISSING INDUSTRY STANDARDS

### 5.1 Missing: Plugin Isolation

**Current:** Plugins can crash the entire system
**Standard:** Plugins run in sandboxed contexts with timeouts

**Example from beets:**

```python
try:
    with timeout(seconds=30):
        result = plugin.execute()
except PluginError as e:
    log_error(e)
    continue  # Process next plugin
```

### 5.2 Missing: Dry-Run Mode

**Current:** No way to preview changes
**Standard:** All operations support --dry-run flag

### 5.3 Missing: Proper Logging

**Current:** Custom Debugger class with print statements
**Standard:** Python's logging module with levels

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Run started")
logger.debug("Processing job", extra={"job_id": job.id})
```

### 5.4 Missing: CLI Command Structure

**Current:** Single command: `python -m archiverr`
**Standard:** Subcommands with argparse/click

**Example (beets-style):**

```bash
archiverr run config.yml           # Execute run
archiverr list runs --limit 10     # List recent runs
archiverr show run abc123          # Show run details
archiverr plugins list             # List plugins
archiverr config validate          # Validate config
```

---

## PART 6: RECOMMENDATIONS

### Priority 1: IMMEDIATE FIXES (Breaking Changes OK)

1. **REMOVE COMMITS**

   - Delete commits collection and all related code
   - Simplify branches to just tags/labels for runs
   - Update API to query runs directly

2. **CONSOLIDATE NAMING**

   - Remove all "execution" terminology → use "run"
   - Remove all "match" terminology → use "job"
   - Update MongoDB collections (migration script)

3. **SIMPLIFY STATE**
   - Reduce from 6 to 3 state objects
   - Remove PluginServices access control layer
   - Make mode (per_run vs per_job) implicit

### Priority 2: ARCHITECTURE IMPROVEMENTS

4. **MERGE PLUGIN LAYERS**

   - Combine PluginDiscovery + PluginLoader into PluginRegistry
   - Remove unnecessary abstraction layers

5. **RESTRUCTURE FILES**

   - Move cli/main.py to **main**.py
   - Flatten core/ structure
   - Remove empty/unused folders

6. **FIX PERSISTENCE**
   - Choose ONE: PyMongoPersistence (sync) OR MotorPersistence (async)
   - Remove deprecated MongoDBPersistence
   - Delete legacy collections after migration

### Priority 3: POLISH

7. **ADD MISSING STANDARDS**

   - Replace custom Debugger with logging module
   - Add CLI subcommands (click library)
   - Add --dry-run mode
   - Add plugin sandboxing with timeouts

8. **IMPROVE CONFIG**
   - Choose ONE config format (no normalization)
   - Remove alias system (too fragile)
   - Simplify to: load → expand env vars → done

---

## PART 7: COMPARISON WITH INDUSTRY

### vs. Beets (Most Similar Project)

| Aspect           | Beets                  | Archiverr               | Assessment            |
| ---------------- | ---------------------- | ----------------------- | --------------------- |
| Plugin System    | Simple registry        | Multi-layer (5 classes) | **Over-engineered**   |
| State Management | Library object         | 6 state objects         | **Over-engineered**   |
| Versioning       | None (not needed)      | Branches + commits      | **Over-engineered**   |
| Config           | Simple YAML            | Multi-step merge        | **Over-complex**      |
| CLI              | Click with subcommands | Single command          | **Under-featured**    |
| File Structure   | Flat, clear            | Nested, mixed           | **Needs improvement** |

### vs. FlexGet (Execution Model)

| Aspect  | FlexGet         | Archiverr      | Assessment       |
| ------- | --------------- | -------------- | ---------------- |
| Tasks   | Per-task config | Per-run config | ✓ Similar, good  |
| Plugins | Stage-based     | Stage-based    | ✓ Similar, good  |
| State   | Task context    | Global state   | **Over-complex** |

---

## CONCLUSION

**BRUTAL TRUTH:**

This system is **architecturally sound but over-engineered** for its purpose. It's designed like an enterprise distributed system when it's actually a CLI tool for organizing files.

**CORE ISSUE:** Trying to be too many things:

- Git-like version control (branches, commits)
- Enterprise state management (6 global objects)
- Complex plugin architecture (5 layers)

**WHAT IT SHOULD BE:** A simple, reliable media organizer with a clean plugin system.

**RECOMMENDED PATH:**

1. **Phase 1:** Remove commits, simplify versioning (1 week)
2. **Phase 2:** Consolidate naming, update DB schema (1 week)
3. **Phase 3:** Simplify state management (2 weeks)
4. **Phase 4:** Restructure files, merge layers (1 week)
5. **Phase 5:** Add missing standards (CLI, logging) (2 weeks)

**Total:** ~7 weeks to production-ready, industry-standard architecture

**STRENGTHS TO KEEP:**

- ✓ Stage-based plugin execution (solid design)
- ✓ Event bus (just use it properly)
- ✓ API versioning (forward-thinking)
- ✓ Dependency injection (testable)

**CRITICAL CHANGES NEEDED:**

- ❌ Remove commits (not needed)
- ❌ Simplify state (6 → 3 objects)
- ❌ Merge plugin layers (5 → 2 classes)
- ❌ Standardize naming (no more execution/match)
- ❌ Flatten file structure

---

**END OF ANALYSIS**
