# ARCHIVERR - UPDATED ACTION PLAN

**Date:** December 10, 2024  
**Based on:** User feedback + corrected analysis  
**Timeline:** 5-6 weeks (can be done incrementally)

---

## PHILOSOPHY SHIFT

### OLD THINKING

- "System inspects plugin results to determine success/fail"
- "Access control prevents plugins from breaking things"
- "Legacy code for backward compatibility"
- "Remove executed/failed/skipped tracking"

### NEW THINKING

- **Plugin self-reporting** - Plugins report their own status via update_status()
- **Mode + dependency execution** - per_run vs per_job KEPT, dependency resolution within modes
- **Minimal restrictions** - Plugins can access all state, create jobs freely
- **No legacy before v1.0** - Clean slate
- **Keep indexing data** - executed/failed/skipped lists KEPT for MongoDB indexing

---

## PHASE 1: IMMEDIATE CLEANUP (Week 1)

### 1.1 Delete Dead Code

**What:** Remove code that serves no purpose

**Files to delete:**

```bash
# Complete folders
rm -rf src/archiverr/core/memory/          # 644 lines - v2 feature
rm -rf src/archiverr/core/workers/         # 189 lines - unused Celery
rm -rf src/archiverr/reports/              # Empty folder
rm -rf src/archiverr/core/reports/         # Empty folder

# Individual files
rm src/archiverr/infrastructure/database/mock.py  # MockPersistence
```

**MongoDB collections to drop:**

```javascript
// Legacy collections (duplicate writes)
db.executions.drop(); // Same as runs
db.matches.drop(); // Same as jobs
db.plugin_results.drop(); // Same as plugins

// Unused versioning
db.commits.drop(); // Created but never queried

// Optional: Simplify branches
// Keep only as metadata, remove head_commit_id reference
db.branches.updateMany({}, { $unset: { head_commit_id: 1 } });
```

**Code modifications:**

```python
# state/manager.py
# DELETE: _create_commit() method (lines 261-301)
# DELETE: create_commit() call in complete_run()

# infrastructure/database/*.py
# DELETE: create_commit(), get_commit(), list_commits() methods
# DELETE: checkout_commit() method

# api/v1/versioning/
# DELETE: commit endpoints
```

**Estimated lines deleted:** ~1,333

**Risk:** ⭐ Very Low (code not used)  
**Effort:** 1-2 days  
**Benefit:** Immediate clarity, -20% codebase size

---

### 1.2 Clean Up Imports & References

**Update all imports:**

```python
# FIND & REPLACE across codebase
from archiverr.infrastructure.database.mock import MockPersistence
# → DELETE (no replacement needed)

from archiverr.core.memory import MemoryTracker
# → DELETE (no replacement needed)

from archiverr.core.workers import TaskBroker
# → DELETE (no replacement needed)
```

**Update DatabaseConnection:**

```python
# infrastructure/database/connection.py
class DatabaseConnection:
    @staticmethod
    def from_env() -> PersistenceInterface:
        # DELETE MockPersistence fallback
        if mongo_uri:
            return PyMongoPersistence(mongo_uri)
        else:
            raise ValueError("MONGO_URI required")

        # ❌ REMOVED: return MockPersistence()
```

**Risk:** ⭐ Very Low  
**Effort:** 2-3 hours

---

## PHASE 2: STATE NORMALIZATION (Weeks 2-3)

### 2.1 Design New State Structure

**Current (6 objects):**

```python
class GlobalStateManager:
    _run: RunState
    _config: Dict
    _current_job: JobState      # ← Duplicate
    _jobs: List[JobState]       # ← Contains _current_job
    _current_plugins: Dict      # ← Duplicate
    _all_plugins: List[Dict]    # ← Contains _current_plugins
```

**New (3 objects):**

```python
class GlobalStateManager:
    _run: RunState
    _config: Dict
    _context: ExecutionContext  # ← Unified

class ExecutionContext:
    """Unified execution context"""
    _current_job: JobState = None
    _jobs: List[JobState] = []
    _current_plugins: Dict = {}
    _all_plugins: List[Dict] = []

    @property
    def job(self) -> JobState:
        """Current job (read-write)"""
        if not self._current_job:
            raise RuntimeError("No active job")
        return self._current_job

    @property
    def jobs(self) -> List[JobState]:
        """All jobs (read-only)"""
        return self._jobs

    @property
    def plugin(self) -> Dict:
        """Current job's plugins (read-write)"""
        return self._current_plugins

    @property
    def plugins(self) -> List[Dict]:
        """All jobs' plugins (read-only)"""
        return self._all_plugins
```

**Risk:** ⭐⭐⭐ Medium  
**Effort:** 3-4 days  
**Benefit:** Single source of truth, clearer boundaries

---

### 2.2 Update PluginServices

**Remove mode-based restrictions:**

```python
# OLD (restrictive)
class PluginServices:
    def __init__(self, mode: str, current_job_id: str, ...):
        self._mode = mode  # per_run | per_job
        self._current_job_id = current_job_id

    def get_current_job(self):
        self._check_per_job_access("get_current_job")  # ← Restriction
        return self._state.job

# NEW (open)
class PluginServices:
    def __init__(self, state, event_bus, logger, config):
        self._state = state
        self._event_bus = event_bus
        self._logger = logger
        self._config = config

    def get_context(self) -> ExecutionContext:
        """Get current execution context (no restrictions!)"""
        return self._state.context

    def get_run(self) -> RunState:
        """Get run state (no restrictions!)"""
        return self._state.run

    def get_config(self) -> Dict:
        """Get config (no restrictions!)"""
        return self._state.config
```

**Remove access control methods:**

```python
# DELETE
def _check_per_job_access(self, method_name: str):
    if self._mode != "per_job":
        raise PermissionError(...)

# All plugins can now:
# - Read all state
# - Create jobs
# - Update jobs
# - Update plugins
```

**Risk:** ⭐⭐⭐ Medium  
**Effort:** 2-3 days

---

### 2.3 Update Job & Plugin State

**Add metadata tracking, keep indexing fields:**

```python
# OLD
class JobState:
    id: str
    run_id: str
    input: {...}
    output: {...}
    status:
        executed: []
        failed: []
        skipped: []

# NEW
class JobState:
    id: str
    run_id: str  # KEPT: Required for MongoDB queries
    input:
        value: str
        data: Dict
        metadata:  # NEW: Track which plugin filled this
            filled_by: str
            filled_at: datetime
    output:
        values: List[str]
        data: Dict
        metadata:  # NEW: Track which plugin filled this
            filled_by: str
            filled_at: datetime
    status:
        state: str
        success: bool
        executed: []  # KEPT: For MongoDB indexing, quick lookup
        failed: []    # KEPT: For MongoDB indexing, quick lookup
        skipped: []   # KEPT: For MongoDB indexing, quick lookup
        started_at: datetime
        finished_at: datetime
        duration_ms: int
```

**Remove duplicate config:**

```python
# OLD
class RunState:
    id: str
    config: Dict  # ← DUPLICATE (already in GlobalStateManager._config)
    status: {...}

# NEW
class RunState:
    id: str
    branch: str  # Simple tag
    status: {...}
    # config removed (use GlobalStateManager._config)
```

**Risk:** ⭐⭐⭐ Medium  
**Effort:** 2-3 days

---

## PHASE 3: PLUGIN AUTONOMY (Weeks 3-4)

### 3.1 Add update_status() Method

**New PluginServices method:**

```python
def update_status(
    self,
    state: str,  # pending | running | completed | failed | skipped
    success: bool,
    message: str = "",
    error: Optional[str] = None
) -> None:
    """
    Plugin reports its own status.

    Args:
        state: Current plugin state
        success: Whether plugin succeeded
        message: Human-readable message
        error: Error message if failed

    Example:
        services.update_status(
            state="completed",
            success=True,
            message="Fetched 10 movies from TMDB"
        )
    """
    plugin_name = self._get_current_plugin_name()
    job_id = self._state.context.job.id

    self._state.update_plugin_status(
        job_id=job_id,
        plugin_name=plugin_name,
        status={
            "state": state,
            "success": success,
            "message": message,
            "error": error,
            "updated_at": datetime.utcnow()
        }
    )

    # Emit event
    self._event_bus.emit(f"plugin.{state}", {
        "plugin": plugin_name,
        "job_id": job_id,
        "success": success,
        "message": message
    })
```

**Risk:** ⭐⭐ Low  
**Effort:** 1 day

---

### 3.2 Update All Plugins

**Update each plugin to use update_status():**

```python
# Example: tmdb plugin
class TMDbPlugin:
    def execute_job(self, services):
        # Report start
        services.update_status("running", True, "Fetching movie data")

        try:
            # Do work
            movie_data = self.fetch_movie(...)

            # Save data
            services.update_plugin({"movie": movie_data})

            # Report success
            services.update_status(
                "completed",
                True,
                f"Fetched {movie_data['title']}"
            )

        except Exception as e:
            # Report failure
            services.update_status(
                "failed",
                False,
                "Failed to fetch movie data",
                error=str(e)
            )
            raise
```

**Update manifest with status_reporting:**

```yaml
# manifest.yml
name: tmdb
version: 1.0.0
stage: data
status_reporting:
  auto_start: true # System sets state=running
  auto_complete: false # Plugin must call update_status()
  timeout_ms: 30000 # Fail if no update in 30s
```

**Plugins to update:**

- scanner
- renamer
- tmdb
- omdb
- tvdb
- tvmaze
- ffprobe
- tasker
- (any custom plugins)

**Risk:** ⭐⭐⭐ Medium  
**Effort:** 2-3 days  
**Benefit:** Plugin autonomy, system is plugin-agnostic

---

### 3.3 Remove System-Side Status Tracking

**Delete from Orchestrator:**

```python
# orchestrator.py - DELETE these lines
try:
    result = plugin_executor.execute(plugin, job, services)
    if result.success:
        job.add_executed(plugin.name)  # ← DELETE
    else:
        job.add_failed(plugin.name)    # ← DELETE
except Exception as e:
    job.add_failed(plugin.name)        # ← DELETE

# Plugin now reports via updateStatus()
```

**Delete from JobState:**

```python
# state/models.py
class JobState:
    # DELETE these methods
    def add_executed(self, plugin_name: str):  # ← DELETE
    def add_failed(self, plugin_name: str):    # ← DELETE
    def add_skipped(self, plugin_name: str):   # ← DELETE
```

**Risk:** ⭐⭐⭐ Medium  
**Effort:** 1 day

---

## PHASE 4: NAMING CONSISTENCY (Weeks 4-5)

### 4.1 Code Rename (Global Find-Replace)

**Terminology changes:**

```python
# Find: execution
# Replace: run
# Files: *.py, *.yml

# Find: match
# Replace: job
# Files: *.py, *.yml

# Find: debugger
# Replace: logger
# Files: *.py
```

**Specific changes:**

```python
# OLD → NEW
start_execution() → start_run()
complete_execution() → complete_run()
execution_id → run_id
total_matches → total_jobs
register_match() → create_job()
```

**Risk:** ⭐⭐⭐⭐ High (breaking change)  
**Effort:** 1 day  
**Benefit:** Consistent terminology

---

### 4.2 API Endpoint Updates

**Rename endpoints:**

```python
# api/v1/runs/ (renamed from executions/)
@router.get("/runs")
def list_runs(): ...

@router.get("/runs/{run_id}")
def get_run(run_id: str): ...

# api/v1/jobs/ (renamed from matches/)
@router.get("/jobs")
def list_jobs(): ...

@router.get("/jobs/{job_id}")
def get_job(job_id: str): ...
```

**Optional: Keep deprecated aliases for one release:**

```python
@router.get("/executions", deprecated=True)
def list_executions_deprecated():
    """DEPRECATED: Use /runs instead"""
    return list_runs()
```

**Risk:** ⭐⭐⭐⭐ High (breaking change for API users)  
**Effort:** 1 day

---

### 4.3 Database Migration

**Migration script:**

```python
# scripts/migrate_naming.py
def migrate_collections():
    # NOTE: New collections already exist (runs, jobs, plugins)
    # Old collections will be dropped (executions, matches, plugin_results)

    # Ensure all data is in new collections
    runs_count = db.runs.count_documents({})
    executions_count = db.executions.count_documents({})

    if runs_count < executions_count:
        print("⚠️  WARNING: runs collection has fewer documents than executions")
        print("Run data migration first!")
        return

    # Drop old collections
    db.executions.drop()
    db.matches.drop()
    db.plugin_results.drop()

    print(f"✅ Migrated {runs_count} runs")
    print("✅ Dropped legacy collections")
```

**Risk:** ⭐⭐⭐⭐ High (data operation)  
**Effort:** 1-2 days  
**Benefit:** Clean schema

---

## PHASE 5: STANDARDIZATION (Weeks 5-6)

### 5.1 Replace Debugger with Logging

**Remove custom Debugger:**

```bash
# Delete custom debugger
rm src/archiverr/utils/debug.py
```

**Update all files:**

```python
# OLD
from archiverr.utils.debug import init_debugger, get_debugger
debugger = init_debugger(level="DEBUG")
debugger.info("component", "message", key=value)

# NEW
import logging
logger = logging.getLogger(__name__)
logger.info("message", extra={"key": value})
```

**Configure logging:**

```python
# __main__.py
import logging

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("archiverr.log")
        ]
    )

# Usage
setup_logging(config.get("log_level", "INFO"))
```

**Risk:** ⭐⭐ Low  
**Effort:** 2-3 days  
**Benefit:** Industry standard logging

---

### 5.2 Optional: Simplify Plugin Layers

**Current (5 layers):**

- PluginDiscovery (find manifest.yml)
- PluginLoader (import module)
- PluginRegistry (organize by stage)
- PluginExecutor (execute one plugin)
- StageExecutor (execute stage)

**Possible (3 layers):**

- PluginRegistry (discovery + loading + organization)
- PluginExecutor (execute one plugin)
- StageExecutor (execute stage)

**Decision:** Review with user

- If current structure is clear → Keep it
- If there's confusion → Merge Discovery + Loader into Registry

**Risk:** ⭐⭐⭐ Medium  
**Effort:** 2-3 days  
**Benefit:** Simpler codebase (if actually simpler)

---

### 5.3 Optional: Config Format Simplification

**Current:** Supports 3 config formats (FlexGet-style, plugins wrapper, new format)

**Option 1:** Support only "new format" (plugins as top-level keys)

```yaml
# New format (keep)
scanner:
  targets: [/downloads]
tmdb:
  api_key: ${TMDB_API_KEY}
```

**Option 2:** Keep all formats (current behavior)

**Decision:** Check usage

- If old formats are used → Keep normalization
- If only new format is used → Remove normalization

**Risk:** ⭐⭐ Low (check usage first)  
**Effort:** 1-2 days

---

## TESTING STRATEGY

### After Each Phase

**Unit Tests:**

```bash
pytest tests/unit/
```

**Integration Tests:**

```bash
pytest tests/integration/
```

**E2E Test:**

```bash
python -m archiverr config.test.yml
```

### Critical Test Cases

1. **State Management (Phase 2):**

   - Job creation and retrieval
   - Plugin data storage
   - Context switching between jobs

2. **Plugin Autonomy (Phase 3):**

   - Plugin status self-reporting
   - Multiple plugins updating concurrently
   - Status persistence to MongoDB

3. **Naming (Phase 4):**
   - API endpoints return correct data
   - MongoDB queries work with new names
   - No references to old terminology

---

## ROLLBACK PLAN

**Phase 1 (Deletions):**

- Rollback: `git revert <commit>`
- Risk: Very low (code not used)

**Phase 2 (State):**

- Rollback: `git revert <commit>`
- Risk: Medium (structural change)
- Mitigation: Feature flag for new state management

**Phase 3 (Plugin Autonomy):**

- Rollback: Revert commits, plugins revert to old API
- Risk: Medium (all plugins affected)
- Mitigation: Update plugins incrementally

**Phase 4 (Naming):**

- Rollback: Database migration script (reverse)
- Risk: High (data operation)
- Mitigation: Backup DB before migration

**Phase 5 (Standardization):**

- Rollback: `git revert <commit>`
- Risk: Low (logging is isolated)

---

## SUCCESS CRITERIA

### Code Quality

- [ ] Zero legacy code (no executions, matches, plugin_results)
- [ ] 3 state objects (not 6)
- [ ] Consistent naming (run, job, logger)
- [ ] ~1,500 lines deleted

### Architecture

- [ ] Plugin self-reporting via updateStatus()
- [ ] No access restrictions (plugins read all state)
- [ ] Dependency-based execution clear
- [ ] Single source of truth for data

### Database

- [ ] 3 core collections (runs, jobs, plugins)
- [ ] Optional: branches (simplified)
- [ ] No commits
- [ ] No legacy collections

### Developer Experience

- [ ] Clear execution model documented
- [ ] Plugin autonomy demonstrated
- [ ] Standard logging throughout
- [ ] Easy to add new plugins

---

## ESTIMATED EFFORT

| Phase                  | Risk     | Days        | Lines Changed  |
| ---------------------- | -------- | ----------- | -------------- |
| 1. Deletions           | ⭐       | 2           | -1,333         |
| 2. State Normalization | ⭐⭐⭐   | 7           | ~500           |
| 3. Plugin Autonomy     | ⭐⭐⭐   | 5           | ~300           |
| 4. Naming Consistency  | ⭐⭐⭐⭐ | 5           | ~800           |
| 5. Standardization     | ⭐⭐     | 5           | ~200           |
| **Total**              |          | **24 days** | **-1,033 net** |

**Calendar Time:** 5-6 weeks (with testing and review)

---

## FINAL NOTES

### What Makes This Different From Original Plan

1. **Plugin System:** Keep as-is (well-designed)
2. **Config System:** Keep !include and aliases (well-designed)
3. **Access Control:** Remove restrictions (plugins are autonomous)
4. **State Management:** Still simplify (6 → 3 objects)
5. **Legacy Code:** Delete immediately (no backward compat needed)

### Core Philosophy

> "Trust plugins. Provide interfaces, not restrictions.  
> Execution is dependency-based, not mode-based."

Plugins are autonomous entities that:

- Report their own status
- Access what they need
- Create jobs if they want
- Depend on other plugins explicitly

System is plugin-agnostic:

- Doesn't inspect plugin internals
- Doesn't track plugin status
- Provides clean interfaces
- Resolves dependencies

---

**END OF ACTION PLAN**
