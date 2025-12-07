# CRITICAL FIXES - Immediate Action Required

```yaml
created: 2025-12-04
priority: P0 - Critical
status: ready_for_implementation
```

---

## COMPLETED (This Session)

### ✅ Plugin Data Flow Fixed
- **Issue**: Stage executor cached plugin data but didn't update job.plugins
- **Fix**: `stage_executor.py` now updates `job.plugins` when caching
- **File**: `src/archiverr/core/plugins/stage_executor.py`

### ✅ Alias 'p' Undefined Fixed
- **Issue**: Tasker couldn't access renamer's parsed data
- **Fix**: Tasker now properly gets data from job.plugins
- **File**: `src/archiverr/plugins/tasker/plugin.py`

### ✅ NORMALIZED METADATA Box Removed
- **Issue**: Verbose output boxes printed regardless of debug setting
- **Fix**: Disabled external tasks in config.yml, added philosophy principles
- **Files**: `config.yml`, `AI/PHILOSOPHY.md`

---

## PENDING CRITICAL

### 1. State Service Cache Not Shared
**Priority**: P1
**Issue**: Each plugin gets NEW StateServiceImpl with empty cache
**Impact**: Plugins can't access other plugins' cached data via services.state
**Fix Strategy**:
```python
# Option A: Pass shared cache to StateServiceImpl
class StateServiceImpl:
    def __init__(self, state_manager, persistence, shared_cache=None):
        self._plugin_cache = shared_cache or {}

# Option B: Use MatchState.plugins as single source of truth (current fix)
# This works but deviates from "plugins in separate collection" strategy
```

### 2. Legacy MatchState vs New JobState
**Priority**: P1
**Issue**: Code uses MatchState (legacy) instead of JobState (strategy)
**Impact**: Template context, API responses use wrong field names
**Files to Update**:
- `state/manager.py` - Still uses `register_match`, `_matches`
- `state/models.py` - MatchState still active
- `core/plugins/stage_executor.py` - Uses both patterns

**Fix**:
```python
# Replace all MatchState usage with JobState
# Replace register_match() with create_job()
# Replace _matches with _jobs
# Update all callers
```

### 3. Input/Output Structure Not Implemented
**Priority**: P1
**Issue**: Strategy requires `job.input.value`, `job.output.values` but code uses `input_path`
**Strategy Says**:
```yaml
job:
  input:
    value: "/path/file.mkv"
    data: {filename, extension, size_bytes}
  output:
    values: ["/archive/Movie (2024)/Movie.mkv"]
    data: {tasks: {...}}
```

**Current**:
```python
# MatchState uses input_path (flat)
# JobState has InputData but not fully wired
```

### 4. Plugin Data Not Stored in Separate Collection
**Priority**: P2
**Issue**: Strategy says plugins should be in separate MongoDB collection
**Current**: Plugins stored in job.plugins dict
**Impact**: No hot/cold tiering, no lazy loading
**Strategy Says**:
```
plugins AYRI COLLECTION'da saklanır!
- Memory management (hot/cold tiering)
- API: GET /jobs/{id}/plugins
- Template: {{ plugins.tmdb.movie.title }}
```

---

## Testing Required

```bash
# Test plugin data flow
source venv/bin/activate && python -m archiverr

# Expected output (debug off):
# ========== JOB 0 ==========
# MOVIE: Mr & Mrs Smith (2005)
# TMDb: Bay ve Bayan Smith (2005)

# Test with show file:
# Should show: SHOW: Name S01E01
```

---

## Files Changed This Session

| File | Change |
|------|--------|
| `core/plugins/stage_executor.py` | Update job.plugins on cache |
| `plugins/tasker/plugin.py` | Fix plugin data access |
| `config.yml` | Disable verbose tasks, fix templates |
| `AI/PHILOSOPHY.md` | Add logging principles |
