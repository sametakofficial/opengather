# SESSION 17 - DEEP ANALYSIS & REFACTORING (COMPLETED)

## 1. EXPLICIT ISSUES FROM USER (TO FIX NOW)

### 1.1. Branches Collection Still Created
**Location:** `infrastructure/database/pymongo_persistence.py`
**Issue:** `BRANCHES = "branches"` constant and related methods (`create_branch`, `get_branch`, `list_branches`, `delete_branch`) still exist.
**Status:** DEPRECATED - should be removed.

```python
# Lines to remove:
BRANCHES = "branches"  # Line 68
_db[self.BRANCHES].create_index(...)  # Lines 159-161
create_branch()  # Lines 323-354
get_branch()  # Lines 356-367
list_branches()  # Lines 369-372
delete_branch()  # Lines 374-385
```

### 1.2. jobs_count in Output Dump
**Location:** `core/orchestrator.py` line 546
**Issue:** `"jobs_count": len(jobs_list)` is redundant.
**Fix:** Remove this line.

### 1.3. Plugin Data Structure (.status/.data still exists)
**Location:** `state/models.py` - `PluginState` class
**Current:**
```python
plugins.tmdb = {
    "status": {"state": "completed", ...},
    "data": {"movie": {...}}
}
```
**Target (SESSION_16):**
```python
plugins["job_xxx"]["tmdb"] = {"movie": {...}}  # Flat, no status/data wrapper
job.status.plugins["tmdb"] = {"state": "completed", ...}  # Status in job
```

### 1.4. job.status.plugins Missing
**Location:** `state/models.py` - `JobStatus` class
**Issue:** `JobStatus` has `executed`, `failed`, `skipped` lists but no `plugins` dict for per-plugin status.
**Fix:** Add `plugins: Dict[str, Dict] = field(default_factory=dict)` to `JobStatus`.

### 1.5. Scanner Not Using update_plugin
**Location:** `plugins/scanner/client.py`
**Issue:** Scanner returns data but doesn't call `services.update_plugin(run_id, "scanner", data)` to store run-level data.
**Fix:** Add `services.update_plugin(services.run_id, "scanner", {"count": created_jobs, "targets": targets})` at end of `execute_run`.

### 1.6. _plugins Appearing Twice in Config
**Location:** `utils/config_normalizer.py`
**Issue:** Config has both top-level plugin keys (scanner, tmdb, etc.) AND `_plugins` dict with same data.
**Root cause:** `normalize_config()` creates `_plugins` but original keys also remain.
**Note:** This is by design for FlexGet compatibility - `_plugins` is internal normalized format. But check if both are being dumped to output.

### 1.7. Manifest.yml Not Merged Into Config
**Issue:** Plugin manifests (with config_schema defaults) should be merged into config but aren't.
**Location:** `core/plugins/discovery.py` and `core/plugins/loader.py`
**Expectation:** manifest.yml defaults should appear at top of plugin config.

---

## 2. SESSION_16 IMPLEMENTATION STATUS

| Feature | Planned | Implemented | Notes |
|---------|---------|-------------|-------|
| snake_case API | Yes | ✅ Partial | `create_job`, `update_job`, `update_plugin` exist with backward aliases |
| target_id parameter | Yes | ✅ Yes | `update_plugin(target_id, plugin_name, data)` |
| Flat plugin data | Yes | ❌ No | Still uses `{status: {}, data: {}}` wrapper |
| job.status.plugins | Yes | ❌ No | Status still in plugin.status |
| run.status.plugins | Yes | ❌ No | Not implemented |
| Key-based plugins dict | Yes | ❌ Partial | Jobs still list-based |
| Remove branches | Yes | ❌ No | Still in pymongo_persistence.py |
| Per-run plugin data | Yes | ❌ No | Scanner doesn't save run-level data |

---

## 3. DETECTED ISSUES (ASK USER BEFORE FIXING)

### 3.1. Duplicate get_plugin_data Methods
**Location:** `state/manager.py`
**Issue:** `get_plugin_data` is defined twice (lines 432-454 and 497-507). The second one shadows the first.

### 3.2. _jobs vs _context._jobs Inconsistency
**Location:** `state/manager.py`
**Issue:** Code references `self._jobs` (line 422, 633) but actual storage is `self._context._jobs`. This will cause AttributeError.

### 3.3. Legacy _plugins_storage Still Used
**Location:** `state/manager.py`
**Issue:** `_plugins_storage: Dict[str, Dict[str, PluginState]]` still exists (line 56) and is used for storing plugin data. SESSION_16 wanted to remove this dual storage.

### 3.4. PluginData Model Still Has Status
**Location:** `state/models.py` lines 314-345
**Issue:** `PluginData` dataclass still includes `status` field which should be removed per SESSION_16.

### 3.5. MongoDB Indexes Still Reference Old Schema
**Location:** `infrastructure/database/pymongo_persistence.py`
**Issue:** Plugins collection still uses `(run_id, job_id, plugin_name)` composite index instead of just `target_id` as _id.

---

## 4. ARCHITECTURAL COMPARISON WITH INDUSTRY PROJECTS

### 4.1. FlexGet Patterns
- **Config:** Plugin as top-level key (adopted ✅)
- **Plugin discovery:** Directory scan with manifest (adopted ✅)
- **Execution:** Task-based with phases (similar to stages ✅)
- **State:** In-memory with optional DB persistence (similar ✅)

### 4.2. Apache Airflow Patterns
- **DAG concept:** Archiverr's Job/Run is similar
- **Operators:** Like plugins with execute() method
- **XCom:** Cross-task communication (similar to plugin data sharing)
- **Separation:** Task definition vs execution (good pattern)

### 4.3. Recommendations
1. **Cleaner separation:** Plugin should not know about persistence
2. **Event-driven:** More events for plugin lifecycle
3. **Immutable state snapshots:** Instead of mutable state objects
4. **Configuration validation:** Stronger schema enforcement at startup

---

## 5. REFACTORING PROPOSALS (ASK USER)

### 5.1. Jobs as Key-Based Dict (User Requested)
**Current:**
```python
jobs = [JobState(...), JobState(...)]
```
**Proposed:**
```python
jobs = {
    "job_abc_0": JobState(...),
    "job_abc_1": JobState(...)
}
```
**Impact:** Changes to StateManager, API responses, MongoDB schema

### 5.2. Unified State Container
**Current:** Multiple dicts (`_run`, `_jobs`, `_plugins`, `_plugins_storage`)
**Proposed:** Single state container with clear boundaries

### 5.3. Plugin Result vs Plugin State
**Recommendation:** Remove PluginState/PluginData duplication, use single format

---

## 6. FILES TO MODIFY FOR SESSION 17 FIXES

### Explicit Fixes (Do Now):
1. `infrastructure/database/pymongo_persistence.py` - Remove branches
2. `core/orchestrator.py` - Remove jobs_count
3. `state/models.py` - Add plugins dict to JobStatus, remove PluginState status wrapper
4. `state/manager.py` - Update plugin handling for flat structure
5. `plugins/scanner/client.py` - Add update_plugin call for run-level data

### Ask User First:
1. Jobs key-based structure change
2. MongoDB schema migration
3. API response format changes
4. Removal of backward compatibility aliases

---

## 7. PRIORITY ORDER

1. ✅ Remove branches from MongoDB (deprecated) - **DONE**
2. ✅ Remove jobs_count from dump - **DONE**
3. ✅ Fix scanner to use update_plugin - **DONE**
4. ✅ Add job.status.plugins dict - **DONE**
5. ✅ Add run.status.plugins dict - **DONE**
6. ✅ Flatten plugin data structure - **DONE**
7. ✅ Jobs key-based (like plugins) - **DONE**
8. ⚠️ Manifest merging into config - **PENDING** (needs investigation)

---

## 8. CHANGES MADE IN SESSION 17

### 8.1. Files Modified

| File | Changes |
|------|---------|
| `infrastructure/database/pymongo_persistence.py` | Removed BRANCHES constant and all branch-related methods |
| `core/orchestrator.py` | Removed jobs_count, changed jobs from list to dict in dump |
| `plugins/scanner/client.py` | Added update_plugin call for run-level data |
| `state/models.py` | Added `plugins` dict to JobStatus and RunStatus |
| `state/manager.py` | Updated update_plugin for flat structure, fixed self._jobs references |
| `state/context.py` | Changed _jobs from List to Dict (key-based) |

### 8.2. New Data Structure

**Before:**
```json
{
  "jobs": [
    {"id": "job_xxx_0", ...},
    {"id": "job_xxx_1", ...}
  ],
  "plugins": {
    "job_xxx_0": {
      "tmdb": {"status": {...}, "data": {...}}
    }
  }
}
```

**After:**
```json
{
  "jobs": {
    "job_xxx_0": {"id": "job_xxx_0", "status": {"plugins": {...}}, ...},
    "job_xxx_1": {"id": "job_xxx_1", "status": {"plugins": {...}}, ...}
  },
  "plugins": {
    "job_xxx_0": {
      "tmdb": {"movie": {...}}
    },
    "run_xxx": {
      "scanner": {"count": 1, "targets": [...]}
    }
  }
}
```

### 8.3. Breaking Changes

1. **jobs is now a dict** - API responses and MongoDB queries may need adjustment
2. **Plugin data is flat** - No more `.status` and `.data` wrappers
3. **Plugin status moved** - Now in `job.status.plugins` or `run.status.plugins`

### 8.4. Backward Compatibility

- `context.jobs` property still returns `List[JobState]` for backward compat
- `context.jobs_dict` returns the new `Dict[str, JobState]`
- API endpoints should work with both formats
