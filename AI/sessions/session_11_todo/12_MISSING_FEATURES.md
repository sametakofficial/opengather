# MISSING FEATURES - Strategy Requirements Not Implemented

```yaml
created: 2025-12-04
priority: P1-P2
status: analysis_complete
source: session_11_strategy/*.md, FINAL_DATASETS.yml
```

---

## 1. CONFIG SYSTEM

### 1.1 !include Directive NOT Working
**Strategy Says**:
```yaml
tasker:
  tasks: !include ./tasks/
```

**Current**: YAML tag registered but directory loading broken
**Fix Required**:
```python
# config_loader.py needs:
def include_constructor(loader, node):
    path = loader.construct_scalar(node)
    if os.path.isdir(path):
        # Load all .yml files in directory
        result = []
        for f in sorted(os.listdir(path)):
            if f.endswith('.yml'):
                with open(os.path.join(path, f)) as fp:
                    result.extend(yaml.safe_load(fp) or [])
        return result
    else:
        # Load single file
        with open(path) as f:
            return yaml.safe_load(f)
```

### 1.2 Cross-Reference in Config/Manifest NOT Working
**Strategy Says**:
```yaml
# In manifest, reference config value:
provides:
  - fs.write:{{config.tasker.save_path}}

# In config, reference other config:
archive_path: /srv/archive
tmdb:
  base_path: "{{config.archive_path}}"
```

**Current**: Not implemented
**Fix**: Add Jinja2 rendering to config loading phase

### 1.3 Alias Resolution NOT Complete
**Strategy Says**:
```yaml
aliases:
  m: job.plugins.tmdb.movie
  p: job.plugins.renamer.parsed
```

**Current**: Aliases defined but resolution only works in tasker
**Fix**: Centralize alias resolution in template context builder

---

## 2. PLUGIN SYSTEM

### 2.1 Provides Registry NOT Implemented
**Strategy Says**:
```python
# Track which plugins have provided what
provides_registry = {
    'http.request': ['tmdb'],
    'fs.write': ['tasker'],
    'state.update': ['renamer', 'tmdb']
}
```

**Current**: Manifests declare provides but no registry tracks completion
**Impact**: `requires: [provides.http.request]` doesn't work

### 2.2 Requires Prefix Validation Incomplete
**Strategy Says**:
| PREFIX | SOURCE | SEMANTIK |
|--------|--------|----------|
| job.* | GlobalState | Path dolu olana kadar bekle |
| provides.* | ProvideRegistry | Provide tamamlanana kadar bekle |
| events.* | EventBus | Event emit edilene kadar bekle |

**Current**: Only `job.*` partially works
**Fix**: Implement full RequiresValidator with all prefixes

### 2.3 Lockable Provides Conflict Detection NOT Implemented
**Strategy Says**:
```yaml
# In manifest:
provides:
  - fs.write:/data/archive  # Lockable with path

# Conflict detection at startup:
# If two plugins provide fs.write to same path → ERROR/WARNING
```

**Current**: Not implemented
**File**: `core/validation/conflict_detector.py` (needs creation)

### 2.4 Input/Output Plugin Responsibility
**Strategy Says**:
```
INPUT plugin → fills job.input.value, job.input.data
OUTPUT plugin → fills job.output.values, job.output.data
```

**Current**: Scanner partially fills, tasker doesn't fill output.values
**Fix**:
```python
# In tasker, after tasks complete:
job.output.values = [r['destination'] for r in results if r.get('type') == 'save']
job.output.data = {'tasks': {r['name']: r for r in results}}
```

---

## 3. EXECUTION FLOW

### 3.1 Parallel Execution NOT Implemented
**Strategy Says**:
```python
# Stage içi paralel execution:
await asyncio.gather(*[
    p.execute(job, services)
    for p in group
])
```

**Current**: Sequential only
**Impact**: Slow execution for DATA stage with multiple plugins

### 3.2 Mixed Mode for OUTPUT Stage
**Strategy Says**:
```
OUTPUT STAGE (mixed):
  for job in jobs:
      tasker.execute(job, services)  # per_job
  rclone.execute_run(services)       # per_run
```

**Current**: Partially implemented in stage_executor._execute_mixed()
**Issue**: Only checks manifest for `execution_mode`, not robust

---

## 4. API SYSTEM

### 4.1 New Endpoints NOT Created
**Strategy Says**:
```
/api/v1/runs (was: /executions)
/api/v1/jobs (was: /matches)
/api/v1/plugins (NEW)
/api/v1/config (NEW)
```

**Current**: Only legacy endpoints exist
**Files to Create**:
- `api/v1/runs/router.py`
- `api/v1/jobs/router.py`
- `api/v1/plugins/router.py`
- `api/v1/config/router.py`

### 4.2 Plugin Endpoint Missing
**Strategy Says**:
```
GET /jobs/{job_id}/plugins → Return plugin data for job
GET /plugins → List all plugin results with filters
```

**Current**: Plugin data buried in job response
**Reason**: Strategy requires plugins in separate collection for memory management

---

## 5. PERSISTENCE

### 5.1 Plugins Collection NOT Separate
**Strategy Says**:
```
MongoDB collections:
  runs       → Run state
  jobs       → Job state (no plugins!)
  plugins    → Plugin data (separate for memory management)
```

**Current**: Plugin data in job.plugins dict
**Impact**: No hot/cold tiering, no lazy loading
**Fix**: Create PluginRepository, update persistence layer

### 5.2 Memory Management NOT Implemented
**Strategy Says**:
```
hot_cold_tiering:
  hot: RAM içindeki aktif plugin verileri
  cold: MongoDB'deki persist edilmiş veriler
  eviction: completed jobs first
  lazy_load: ihtiyaç halinde MongoDB'den yükle
```

**Current**: All data in memory
**File**: `core/memory/plugin_cache.py` (needs creation)

---

## 6. IMPLEMENTATION PRIORITY

### P0 - Immediate
- [ ] Alias resolution in template context
- [ ] Tasker fills output.values

### P1 - High
- [ ] !include directive working
- [ ] Provides registry
- [ ] API endpoint rename

### P2 - Medium
- [ ] Plugins separate collection
- [ ] Parallel execution
- [ ] Conflict detection

### P3 - Low
- [ ] Memory management
- [ ] Lazy loading
