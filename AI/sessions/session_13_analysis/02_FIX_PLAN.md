# SESSION 13 - FIX PLAN

Detaylı düzeltme planı ve implementasyon adımları.

---

## ROOT CAUSE CONFIRMED

**Problem**: StageExecutor, `services.updatePlugin()` çağrısından SONRA `job.plugins`'i override ediyor.

**File**: `src/archiverr/core/plugins/stage_executor.py:368-381`

```python
# Session 12: Store plugin data in plugin.{name}.data.* format
if result_data:
    # Cache for trigger evaluation
    self._plugin_data_cache.setdefault(job.id, {})[plugin_name] = result_data
    
    # Update job.plugins with Session 12 structure
    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
        # Session 12: plugin.{name}.status and plugin.{name}.data
        job.plugins[plugin_name] = {  # ❌ OVERRIDE BURASI!
            'status': {
                'state': 'completed',
                'success': success
            },
            'data': result_data
        }
```

**Neden Sorun**:
1. Plugin `services.updatePlugin(full_data)` çağırıyor → State'e FULL data yazılıyor
2. Plugin `return PluginResult(data=full_data)` dönüyor
3. StageExecutor `result.data`'yı alıyor ve `job.plugins[name]` OVERRIDE ediyor
4. İlk yazılan FULL data kayboluyorİKİ SEÇENEK:

**Option A**: StageExecutor override yapmasın (sadece status güncellesin)
**Option B**: Plugin PluginResult'a da FULL data koysun ve override sorun olmasın

**Seçim**: **Option A** (Session 12 stratejisine uygun)

---

## FIX #1: StageExecutor - Remove Override

**File**: `src/archiverr/core/plugins/stage_executor.py`
**Method**: `_execute_plugin_for_job()`
**Lines**: 368-388

### Current Code:
```python
# Session 12: Store plugin data in plugin.{name}.data.* format
if result_data:
    # Cache for trigger evaluation
    self._plugin_data_cache.setdefault(job.id, {})[plugin_name] = result_data
    
    # Update job.plugins with Session 12 structure
    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
        # Session 12: plugin.{name}.status and plugin.{name}.data
        job.plugins[plugin_name] = {
            'status': {
                'state': 'completed',
                'success': success
            },
            'data': result_data
        }
    elif hasattr(job, 'plugins'):
        # Legacy MatchState
        try:
            job.plugins[plugin_name] = result_data
        except (TypeError, AttributeError):
            pass
```

### Fixed Code:
```python
# Session 12: Cache result for trigger rules
if result_data:
    self._plugin_data_cache.setdefault(job.id, {})[plugin_name] = result_data

# Session 12: ONLY update status if plugin didn't call updatePlugin()
# If plugin called services.updatePlugin(), data is already in job.plugins
# We only need to ensure status is updated
if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
    if plugin_name in job.plugins:
        # Plugin used updatePlugin() - only update status
        if isinstance(job.plugins[plugin_name], dict):
            if 'status' not in job.plugins[plugin_name]:
                job.plugins[plugin_name]['status'] = {}
            job.plugins[plugin_name]['status'].update({
                'state': 'completed',
                'success': success
            })
    else:
        # Plugin didn't use updatePlugin() - create full structure
        job.plugins[plugin_name] = {
            'status': {
                'state': 'completed',
                'success': success
            },
            'data': result_data
        }
elif hasattr(job, 'plugins'):
    # Legacy MatchState
    try:
        if plugin_name not in job.plugins:
            job.plugins[plugin_name] = result_data
    except (TypeError, AttributeError):
        pass
```

**Logic**:
1. Check if `plugin_name` already in `job.plugins`
2. If YES → Plugin called `updatePlugin()`, only update status
3. If NO → Plugin didn't call `updatePlugin()`, write full data

---

## FIX #2: TMDb Plugin - Ensure Complete Data

**File**: `src/archiverr/plugins/tmdb/client.py`
**Method**: `execute()`

### Current Code (Line 172-187):
```python
# Convert dict result to PluginResult
# Remove status from data (PluginResult handles it)
data = {k: v for k, v in result.items() if k != 'status'}

# Session 12: Update plugin state via services
self.debug("TMDb services check", 
          services_type=str(type(services)),
          has_updatePlugin=hasattr(services, 'updatePlugin'),
          data_keys=list(data.keys()))

if hasattr(services, 'updatePlugin'):
    self.debug("Calling updatePlugin")
    services.updatePlugin(data=data)
    self.info("TMDb data updated via updatePlugin")
else:
    self.warn("Services does not have updatePlugin method")

return PluginResult.success_result(data=data, started_at=started_at)
```

### Analysis:
- ✅ `services.updatePlugin(data=data)` çağrılıyor
- ✅ `data` FULL data içeriyor (movie, extras, normalized, validation)
- ✅ `PluginResult` de FULL data dönüyor

**Problem değil TMDb'de!** State manager veya StageExecutor sorunu.

---

## FIX #3: Tasker - Data Extraction Logic

**File**: `src/archiverr/plugins/tasker/plugin.py`
**Method**: `_extract_plugin_summary()`

### Current Code (Line 520-564):
```python
def _extract_plugin_summary(self, plugins_data: Dict[str, Any]) -> Dict[str, Any]:
    summary = {}
    
    for plugin_name, plugin_info in plugins_data.items():
        if isinstance(plugin_info, dict):
            # Session 12 format
            if 'data' in plugin_info:
                data = plugin_info['data']
                status = plugin_info.get('status', {})
                
                # Extract relevant data based on plugin type
                if plugin_name == 'renamer':
                    summary[plugin_name] = {
                        'category': data.get('category'),
                        'parsed': data.get('parsed')
                    }
                elif plugin_name == 'tmdb':
                    movie = data.get('movie', {})
                    show = data.get('show', {})
                    if movie:
                        summary[plugin_name] = {
                            'type': 'movie',
                            'title': movie.get('title', {}).get('primary'),
                            'year': movie.get('year'),
                            'tmdb_id': movie.get('tmdb_id')
                        }
                    elif show:
                        summary[plugin_name] = {
                            'type': 'show',
                            'title': show.get('title', {}).get('primary'),
                            'year': show.get('year'),
                            'tmdb_id': show.get('tmdb_id')
                        }
                else:
                    # Generic summary
                    summary[plugin_name] = {
                        'success': status.get('success', False),
                        'data_keys': list(data.keys()) if isinstance(data, dict) else []
                    }
            else:
                # Legacy format
                summary[plugin_name] = {'data_keys': list(plugin_info.keys())}
    
    return summary
```

### Analysis:
- ✅ Logic looks correct
- ❌ BUT: `movie.get('title', {}).get('primary')` assumes normalized format
- ❌ Eski main branch'te `movie.get('title')` direkt string

**Decision**: Support both raw and normalized formats

### Fixed Code:
```python
elif plugin_name == 'tmdb':
    movie = data.get('movie', {})
    show = data.get('show', {})
    if movie:
        # Handle both raw and normalized title formats
        title = movie.get('title')
        if isinstance(title, dict):
            # Normalized format
            movie_title = title.get('primary') or title.get('original') or 'Unknown'
        else:
            # Raw format (string)
            movie_title = title or 'Unknown'
        
        # Handle both raw and normalized year formats
        year = movie.get('year')
        if year is None:
            # Try release_date (raw format)
            release_date = movie.get('release_date', '')
            year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
        
        summary[plugin_name] = {
            'type': 'movie',
            'title': movie_title,
            'year': year,
            'tmdb_id': movie.get('tmdb_id') or movie.get('id')
        }
    elif show:
        # Same for show
        name = show.get('name')
        if isinstance(name, dict):
            show_name = name.get('primary') or name.get('original') or 'Unknown'
        else:
            show_name = name or 'Unknown'
        
        summary[plugin_name] = {
            'type': 'show',
            'title': show_name,
            'year': show.get('year') or show.get('first_air_date', '')[:4],
            'tmdb_id': show.get('tmdb_id') or show.get('id')
        }
    else:
        # No movie or show - show data keys for debugging
        summary[plugin_name] = {
            'type': 'unknown',
            'data_keys': list(data.keys()) if isinstance(data, dict) else []
        }
```

---

## FIX #4: State Manager - Verify update_plugin()

**File**: `src/archiverr/state/manager.py`
**Method**: `update_plugin()`
**Lines**: 426-456

### Current Code:
```python
def update_plugin(self, job_id: str, plugin_name: str, data: Dict[str, Any]) -> None:
    if job_id not in self._plugins_storage:
        self._plugins_storage[job_id] = {}
    
    if plugin_name not in self._plugins_storage[job_id]:
        self._plugins_storage[job_id][plugin_name] = PluginState()
    
    # Update plugin data
    self._plugins_storage[job_id][plugin_name].data = data
    
    # Also update JobState.plugins for backward compatibility
    job = self.get_job_by_id(job_id)
    if job:
        job.plugins[plugin_name] = self._plugins_storage[job_id][plugin_name].to_dict()
    
    self._emit("plugin.updated", {
        "job_id": job_id,
        "plugin_name": plugin_name,
        "data": data
    })
```

### Analysis:
- ✅ `_plugins_storage` updated
- ✅ `job.plugins[plugin_name]` set to `PluginState.to_dict()` which returns `{status: {...}, data: {...}}`
- ✅ Looks correct!

**No fix needed here.**

---

## FIX #5: Add Logging for Debugging

Add debug logs to track data flow:

### StageExecutor:
```python
# After plugin execution
self._log("debug", f"Plugin {plugin_name} returned data with keys: {list(result_data.keys())}")

# Before updating job.plugins
if plugin_name in job.plugins:
    self._log("debug", f"Plugin {plugin_name} already in job.plugins, only updating status")
    existing_data_keys = list(job.plugins[plugin_name].get('data', {}).keys())
    self._log("debug", f"Existing data keys: {existing_data_keys}")
else:
    self._log("debug", f"Plugin {plugin_name} not in job.plugins, creating new entry")
```

### State Manager:
```python
def update_plugin(self, job_id: str, plugin_name: str, data: Dict[str, Any]) -> None:
    # ... existing code ...
    
    self._log("debug", "plugin_data", f"Updated plugin {plugin_name} for job {job_id}",
             data_keys=list(data.keys()),
             data_size=len(str(data)))
```

---

## TESTING PLAN

### Test 1: TMDb Data Persistence
```bash
# Run archiverr with debug mode
python -m archiverr --config config.yml --debug

# Check output JSON
cat output/run_*.json | jq '.jobs[0].plugins.tmdb'

# Expected:
{
  "status": {...},
  "data": {
    "movie": {...},  // FULL data
    "extras": {...},
    "normalized": {...}
  }
}
```

### Test 2: Tasker Summary
```bash
# Check tasker summary in JSON
cat output/run_*.json | jq '.jobs[0].plugins.tmdb'

# Expected:
{
  "type": "movie",
  "title": "The Matrix",  // Not null
  "year": 1999,           // Not null
  "tmdb_id": 603          // Not null
}
```

### Test 3: Print Output
```bash
# Check console output for TMDb print task
# Expected:
✓ TMDb: The Matrix (1999)
```

---

## IMPLEMENTATION ORDER

1. ✅ **FIX #1**: StageExecutor - Remove data override
2. ✅ **FIX #3**: Tasker - Support both raw/normalized
3. ✅ **FIX #5**: Add debug logging
4. 🧪 **TEST**: Run archiverr and verify
5. 📋 **VERIFY**: Compare with main branch output

---

## SUCCESS CRITERIA

- ✅ TMDb plugin returns full data (movie, extras, normalized)
- ✅ job.plugins['tmdb'].data has full data
- ✅ Tasker can access tmdb.movie.title
- ✅ JSON output has complete plugin summaries
- ✅ Print tasks show correct movie titles and years
- ✅ No null values in plugin summaries
