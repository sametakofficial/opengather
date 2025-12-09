# ARCHIVERR - ACTIONABLE REFACTORING PLAN

**Based on comprehensive architecture analysis**  
**Priority: High-impact, low-risk changes first**

---

## CRITICAL DECISION: COMMITS

### ❌ REMOVE COMMITS SYSTEM

**Verdict:** Commits are **write-only dead weight**. MongoDB branches exist, commits are created but NEVER used.

**Industry Standard:** Similar projects (Beets, FlexGet, MediaCMS) use simple run history with timestamps.

**Action:**

1. Simplify branches to tags (just strings: "main", "staging", "experiment")
2. Add `branch` field to `runs` collection
3. Delete `commits` collection and all related code (~500 lines)

**Benefit:** -30% storage, 2-3x faster queries, much simpler code.

**See:** `COMMITS_DECISION.md` for full analysis.

---

## PHASE 1: QUICK WINS (Week 1)

**Deletions - No functionality lost**

### 1.1 Delete Dead Code

```bash
# Remove these entire folders:
rm -rf src/archiverr/core/memory/
rm -rf src/archiverr/core/workers/
rm -rf src/archiverr/reports/

# Remove empty folders:
rm -rf src/archiverr/core/reports/
```

**Files deleted:**

- `core/memory/` - 644 lines (premature optimization)
- `core/workers/` - 189 lines (Celery integration, unused)
- `reports/` - Empty folder
- `core/reports/` - Empty `__init__.py`

**Total:** ~833 lines deleted

**Risk:** ⭐ None (code not used anywhere)

### 1.2 Delete Commits Code

**Files to modify:**

```python
# src/archiverr/state/manager.py
- Remove _create_commit() method (40 lines)
- Remove create_commit call in complete_run()

# src/archiverr/infrastructure/database/mongodb.py
- Remove create_commit() method (65 lines)
- Remove get_commit(), list_commits(), checkout_commit() (200 lines)
- Remove commit indexes creation (5 lines)

# src/archiverr/infrastructure/database/pymongo_persistence.py
- Same deletions as above

# src/archiverr/api/v1/versioning/router.py
- Remove commit endpoints (100 lines)
```

**Total:** ~500 lines deleted

**Database:**

```javascript
db.commits.drop();
```

**Risk:** ⭐⭐ Low (commits not used, but check API callers first)

### 1.3 Summary - Week 1

**Deleted:** 1,333 lines  
**Benefit:** Simpler codebase, less confusion  
**Risk:** ⭐ Very Low  
**Effort:** 1-2 days

---

## PHASE 2: CONSOLIDATION (Weeks 2-3)

**Merge redundant components**

### 2.1 Merge Plugin Layers

**Current (5 layers):**

```
PluginDiscovery → PluginLoader → PluginRegistry → PluginExecutor → StageExecutor
```

**Target (2 layers):**

```
PluginRegistry → StageExecutor
```

**Changes:**

**Merge:** `PluginDiscovery` + `PluginLoader` → `PluginRegistry`

```python
# New: src/archiverr/plugins/registry.py
class PluginRegistry:
    """Single class for discovery, loading, and organization"""

    def discover_and_load(self) -> None:
        """Discover plugins and load enabled ones"""
        # Merge logic from PluginDiscovery + PluginLoader

    def get_plugins_by_stage(self, stage: Stage) -> Dict[str, Any]:
        """Get plugins for a stage"""
```

**Delete:**

- `core/plugins/discovery.py` (200 lines)
- `core/plugins/loader.py` (250 lines)

**Move:**

- `core/plugins/registry.py` → `plugins/registry.py`
- `core/plugins/executor.py` → `plugins/executor.py`
- `core/plugins/stage_executor.py` → `plugins/stage_executor.py`

**Risk:** ⭐⭐⭐ Medium (plugin system is central)  
**Effort:** 3-4 days

### 2.2 Simplify Config System

**Current (4 steps):**

```
load_yaml_with_includes → expand_env_vars → normalize_config → resolve_aliases
```

**Target (2 steps):**

```
load_yaml → expand_env_vars
```

**Changes:**

1. **Remove alias system** (too fragile)

   - Delete `core/config/alias_resolver.py` (120 lines)
   - Remove `resolve_aliases()` call from config loader

2. **Remove format normalization** (pick ONE format)

   - Delete `utils/config_normalizer.py` (200 lines)
   - Update docs: config format is fixed

3. **Keep or remove !include?** (decide based on usage)
   - Check: Is !include actually used in configs?
   - If no: Delete `utils/yaml_loader.py` (150 lines)
   - If yes: Keep it (useful feature)

**Simplified loader:**

```python
def load_config(path: str) -> Dict[str, Any]:
    """Load and process config"""
    with open(path) as f:
        config = yaml.safe_load(f)

    # Only env var expansion
    config = expand_env_vars(config)

    return config
```

**Risk:** ⭐⭐⭐ Medium (config is critical)  
**Effort:** 2-3 days

### 2.3 Move Files to Correct Locations

```bash
# Move CLI entry point
mv src/archiverr/cli/main.py src/archiverr/__main__.py
rmdir src/archiverr/cli/

# Move reports to API
mv src/archiverr/core/reports/report_generator.py \
   src/archiverr/api/formatters.py
mv src/archiverr/core/reports/response_simplifier.py \
   src/archiverr/api/formatters_legacy.py

# Merge models folder
mv src/archiverr/models/response_builder.py \
   src/archiverr/api/responses.py
rmdir src/archiverr/models/

# Move plugins/ out of core/
mv src/archiverr/core/plugins/* src/archiverr/plugins/
rmdir src/archiverr/core/plugins/
```

**Risk:** ⭐⭐ Low (just moving files)  
**Effort:** 1 day

### 2.4 Summary - Weeks 2-3

**Merged/Moved:** 3 major components  
**Benefit:** Clearer structure, easier navigation  
**Risk:** ⭐⭐⭐ Medium  
**Effort:** 6-8 days

---

## PHASE 3: STANDARDIZATION (Weeks 4-5)

**Fix naming, schemas, patterns**

### 3.1 Rename: execution → run, match → job

**Code changes (global find-replace):**

```python
# Remove all legacy aliases
class GlobalStateManager:
    # DELETE these:
    def start_execution()  → DELETE (use start_run)
    def complete_execution() → DELETE (use complete_run)
    @property execution → DELETE (use run)

    def register_match() → DELETE (use create_job)
    @property _matches → DELETE (use _jobs)
    def get_match() → DELETE (use get_job)
```

**Database migration:**

```javascript
// Rename collections
db.executions.renameCollection("runs_old_backup");
db.matches.renameCollection("jobs_old_backup");
db.plugin_results.renameCollection("plugins_old_backup");

// New collections already exist (runs, jobs, plugins)
// After verification, drop old collections:
db.runs_old_backup.drop();
db.jobs_old_backup.drop();
db.plugins_old_backup.drop();
```

**API changes:**

```python
# Update all endpoint paths
/api/v1/executions → /api/v1/runs
/api/v1/matches → /api/v1/jobs

# Keep old endpoints as deprecated aliases (1 version)
@router.get("/executions", deprecated=True)
def list_executions_deprecated():
    return list_runs()
```

**Risk:** ⭐⭐⭐⭐ High (breaking change for API users)  
**Effort:** 3-4 days

### 3.2 Simplify Branches

**Current:**

```javascript
branches: {
  _id: "branch_abc",
  name: "main",
  is_default: true,
  head_commit_id: "commit_xyz",
  created_at: ISODate(...),
  updated_at: ISODate(...)
}
```

**Target:**

```javascript
// Just use string tags on runs
runs: {
  _id: "run_abc",
  branch: "main",  // Simple string!
  // ... rest of run data
}

// Optional: Keep branches as metadata only
branches: {
  name: "main",
  description: "Production runs",
  created_at: ISODate(...)
}
```

**Migration:**

```python
# Add branch field to all runs
for run in db.runs.find():
    # Find commit for this run
    commit = db.commits.find_one({"execution_id": f"exec_{run['id']}"})
    if commit:
        branch = db.branches.find_one({"_id": commit["branch_id"]})
        run["branch"] = branch["name"] if branch else "main"
    else:
        run["branch"] = "main"

    db.runs.update_one({"_id": run["_id"]}, {"$set": {"branch": run["branch"]}})
```

**Risk:** ⭐⭐ Low (data migration)  
**Effort:** 1-2 days

### 3.3 Summary - Weeks 4-5

**Standardized:** Naming, schemas  
**Benefit:** Consistent terminology, single source of truth  
**Risk:** ⭐⭐⭐⭐ High (breaking changes)  
**Effort:** 5-7 days

---

## PHASE 4: SIMPLIFICATION (Weeks 6-8)

**Architectural improvements**

### 4.1 Simplify State Management

**Current (6 objects):**

```python
run, config, job, jobs, plugin, plugins
```

**Target (3 objects):**

```python
class ExecutionContext:
    run: RunState          # Current run metadata
    config: Dict           # Frozen config
    current_job: JobState  # Current job being processed

    def get_job(self, index: int) → JobState
    def get_all_jobs(self) → List[JobState]
    def get_plugin_data(self, plugin_name: str) → Dict
```

**Changes:**

- Remove separate `plugin` and `plugins` objects
- Access via `current_job.plugins[name]`
- Simplify PluginServices to just context holder

**Risk:** ⭐⭐⭐⭐ High (core architecture change)  
**Effort:** 5-7 days

### 4.2 Simplify Triggers

**Current (3 files):**

```
triggers/
├── manager.py
├── evaluator.py
└── matcher.py
```

**Target (1 function):**

```python
def check_requirements(
    requirements: List[str],
    state: Dict[str, Any],
    rule: str = "all_success"
) -> Tuple[bool, str]:
    """Check if requirements are met"""

    results = []
    for req in requirements:
        # Parse requirement (e.g., "plugin.tmdb.data:success")
        path, condition = req.split(":")
        value = get_nested_value(state, path)
        results.append(check_condition(value, condition))

    if rule == "all_success":
        return all(results), "All requirements met"
    elif rule == "one_success":
        return any(results), "At least one requirement met"
    else:
        return False, f"Unknown rule: {rule}"
```

**Delete:**

- `core/triggers/` entire folder (400 lines)

**Risk:** ⭐⭐ Low (just simplification)  
**Effort:** 2-3 days

### 4.3 Replace Custom Debugger with logging

**Current:**

```python
from archiverr.utils.debug import init_debugger, get_debugger

debugger = init_debugger(level="DEBUG")
debugger.info("component", "message", key=value)
```

**Target:**

```python
import logging

logger = logging.getLogger(__name__)
logger.info("message", extra={"key": value})
```

**Changes:**

- Delete `utils/debug.py` (200 lines)
- Replace all `debugger.info()` → `logger.info()`
- Configure logging in `__main__.py`

**Risk:** ⭐⭐ Low (standard library)  
**Effort:** 2-3 days

### 4.4 Add CLI Subcommands (Nice to Have)

**Current:**

```bash
python -m archiverr           # Run CLI
python -m archiverr serve     # Start API
```

**Target:**

```bash
archiverr run config.yml           # Execute run
archiverr list runs --limit 10     # List recent runs
archiverr show run abc123          # Show run details
archiverr plugins list             # List plugins
archiverr config validate          # Validate config
archiverr serve                    # Start API
```

**Use Click library:**

```python
import click

@click.group()
def cli():
    """Archiverr CLI"""
    pass

@cli.command()
@click.argument('config_file')
def run(config_file):
    """Execute a run"""
    # ...

@cli.command()
def serve():
    """Start API server"""
    # ...
```

**Risk:** ⭐ Very Low (additive change)  
**Effort:** 2-3 days

### 4.5 Summary - Weeks 6-8

**Simplified:** 3 major components  
**Benefit:** Industry-standard patterns, better UX  
**Risk:** ⭐⭐⭐ Medium-High  
**Effort:** 11-16 days

---

## FINAL SUMMARY

### Total Effort

- **Phase 1:** 1-2 days (deletions)
- **Phase 2:** 6-8 days (consolidation)
- **Phase 3:** 5-7 days (standardization)
- **Phase 4:** 11-16 days (simplification)

**Total:** 23-33 days (~5-7 weeks)

### Risk Assessment

- **Low Risk (⭐⭐):** Phases 1-2 (deletions, moves)
- **Medium Risk (⭐⭐⭐):** Config simplification
- **High Risk (⭐⭐⭐⭐):** Naming changes, state refactor

**Recommendation:** Execute Phases 1-2 immediately, delay Phases 3-4 for major version bump.

### Lines of Code Impact

- **Deleted:** ~1,500 lines (dead code)
- **Simplified:** ~800 lines (merged components)
- **Refactored:** ~500 lines (architecture changes)

**Net Result:** -1,800 lines, cleaner architecture

### Before/After Comparison

**Before:**

```
59 Python files in core/
6 state objects
5 plugin layers
4 config processing steps
3 persistence implementations
2 naming conventions (run vs execution)
1,333 lines of dead code
```

**After:**

```
40 Python files in core/
3 state objects
2 plugin layers
2 config processing steps
1 persistence implementation (PyMongo)
1 naming convention (run, job)
0 lines of dead code
```

---

## RECOMMENDED EXECUTION ORDER

### Sprint 1 (Week 1): Quick Wins

- ✅ Delete `core/memory/`, `core/workers/`, empty folders
- ✅ Delete commits collection and code
- ✅ Move files to correct locations

**Deliverable:** Cleaner codebase, 1,333 lines deleted

### Sprint 2 (Weeks 2-3): Consolidation

- ✅ Merge plugin layers (5 → 2)
- ✅ Simplify config system (4 steps → 2)
- ✅ Flatten folder structure

**Deliverable:** Better structure, easier to navigate

### Sprint 3 (Weeks 4-5): Standardization

- ⚠️ Breaking: Rename execution → run, match → job
- ⚠️ Breaking: Update API endpoints
- ✅ Simplify branches to tags
- ✅ Migrate database schema

**Deliverable:** Version 2.0.0 with consistent naming

### Sprint 4 (Weeks 6-8): Modernization

- ✅ Simplify state management (6 → 3)
- ✅ Simplify triggers (3 files → 1)
- ✅ Replace Debugger with logging
- ✅ Add CLI subcommands

**Deliverable:** Industry-standard architecture

---

## SUCCESS METRICS

### Code Quality

- [ ] All TODO/FIXME comments resolved
- [ ] No dead code (0 unreferenced functions)
- [ ] Consistent naming (no execution/match aliases)
- [ ] Single source of truth (no duplicate collections)

### Performance

- [ ] Query speed: 2-3x faster (no JOINs needed)
- [ ] Storage: 30% reduction (no duplicate data)
- [ ] Memory: No custom eviction needed

### Developer Experience

- [ ] New developer onboarding < 1 hour
- [ ] File structure: instantly understandable
- [ ] Testing: all components easily mockable
- [ ] Documentation: code is self-documenting

### User Experience

- [ ] CLI has helpful subcommands
- [ ] API follows REST conventions
- [ ] Error messages are clear
- [ ] Logging uses standard format

---

## MAINTENANCE NOTES

### After Refactoring, AVOID:

1. ❌ Adding features without clear use case (YAGNI)
2. ❌ Creating folders for single files
3. ❌ Supporting multiple formats (pick one)
4. ❌ Building abstractions for "future flexibility"
5. ❌ Copying patterns from different problem domains

### Instead, FOLLOW:

1. ✅ Write the simplest thing that works
2. ✅ Add complexity only when needed
3. ✅ Delete code aggressively
4. ✅ Keep file structure flat
5. ✅ Follow industry patterns for your domain

**Remember:** Archiverr is a **media organizer**, not:

- Not a version control system (no Git-like versioning)
- Not a workflow orchestrator (no complex DAGs)
- Not a distributed system (no message brokers)
- Not an enterprise framework (no over-abstraction)

**Keep it simple. Keep it focused.**

---

**END OF ACTION PLAN**
