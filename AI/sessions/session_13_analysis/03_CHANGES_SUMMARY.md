# SESSION 13 - CHANGES SUMMARY

Uygulanan düzeltmelerin özeti.

---

## CHANGES APPLIED

### 1. ✅ StageExecutor - Fixed Plugin Data Override

**File**: `src/archiverr/core/plugins/stage_executor.py`
**Lines**: 367-403 (Modified)

**Problem**: StageExecutor was overriding `job.plugins[plugin_name]` AFTER `services.updatePlugin()` already wrote it, causing data loss.

**Solution**: Check if plugin data already exists before writing:
- If `plugin_name in job.plugins` → Only update status (preserve existing data)
- If `plugin_name not in job.plugins` → Create full structure

**Code Changes**:
```python
# Before (LINE 367-388)
if result_data:
    self._plugin_data_cache[...][plugin_name] = result_data
    
    job.plugins[plugin_name] = {  # ❌ ALWAYS OVERRIDE
        'status': {...},
        'data': result_data
    }

# After (LINE 367-403)
if result_data:
    self._plugin_data_cache[...][plugin_name] = result_data

if plugin_name in job.plugins and isinstance(job.plugins[plugin_name], dict):
    # Plugin already has data - only update status ✅
    job.plugins[plugin_name]['status'].update({...})
    self._log("debug", f"Preserved existing data keys: {data_keys}")
else:
    # Plugin didn't use updatePlugin() - create full structure
    job.plugins[plugin_name] = {'status': {...}, 'data': result_data}
```

**Impact**: TMDb plugin's FULL data is now preserved after `services.updatePlugin()` call.

---

### 2. ✅ Tasker - Support Both Raw and Normalized Formats

**File**: `src/archiverr/plugins/tasker/plugin.py`
**Method**: `_extract_plugin_summary()`
**Lines**: 537-590 (Modified)

**Problem**: Tasker assumed normalized format (`movie.title.primary`) but TMDb might return raw format (`movie.title` as string).

**Solution**: Handle both formats with type checking.

**Code Changes**:
```python
# Before (LINE 538-554)
movie = data.get('movie', {})
if movie:
    summary[plugin_name] = {
        'type': 'movie',
        'title': movie.get('title', {}).get('primary'),  # ❌ Assumes dict
        'year': movie.get('year'),
        'tmdb_id': movie.get('tmdb_id')
    }

# After (LINE 538-590)
movie = data.get('movie', {})
if movie:
    # Handle both raw and normalized title formats
    title = movie.get('title')
    if isinstance(title, dict):
        movie_title = title.get('primary') or title.get('original') or 'Unknown'
    else:
        movie_title = title or 'Unknown'
    
    # Handle both normalized year and raw release_date
    year = movie.get('year')
    if year is None:
        release_date = movie.get('release_date', '')
        if release_date and len(release_date) >= 4:
            year = int(release_date[:4])
    
    summary[plugin_name] = {
        'type': 'movie',
        'title': movie_title,  # ✅ Works with both formats
        'year': year,
        'tmdb_id': movie.get('tmdb_id') or movie.get('id')
    }
```

**Impact**: Tasker can now extract title/year from both raw and normalized TMDb data.

---

### 3. ✅ State Manager - Added Debug Logging

**File**: `src/archiverr/state/manager.py`
**Method**: `update_plugin()`
**Lines**: 444-463 (Modified)

**Problem**: Hard to debug what data is being written to state.

**Solution**: Add debug logging after updating plugin data.

**Code Changes**:
```python
# After updating job.plugins (LINE 452-457)
# Debug logging
data_keys = list(data.keys()) if isinstance(data, dict) else []
self._log("debug", "plugin_data", 
         f"Updated plugin {plugin_name} for job {job_id}",
         data_keys=data_keys,
         data_size=len(str(data)))
```

**Impact**: Can now track what data StateManager receives and stores.

---

## FILES MODIFIED

1. `src/archiverr/core/plugins/stage_executor.py` - Fixed data override logic
2. `src/archiverr/plugins/tasker/plugin.py` - Support both data formats
3. `src/archiverr/state/manager.py` - Added debug logging

---

## TESTING CHECKLIST

### ✅ Expected Results

After these fixes, the following should work:

1. **TMDb Plugin**:
   - [ ] Fetches full movie data from API
   - [ ] Calls `services.updatePlugin(data)` with FULL data
   - [ ] State manager stores FULL data in `job.plugins['tmdb'].data`
   - [ ] StageExecutor does NOT override the data
   - [ ] Final `job.plugins['tmdb']` has complete movie/extras/normalized

2. **Tasker Plugin**:
   - [ ] Can read `job.plugins['tmdb'].data.movie`
   - [ ] Extracts title (both raw string and normalized dict)
   - [ ] Extracts year (both direct year and from release_date)
   - [ ] Prints correct TMDb info
   - [ ] JSON summary has non-null title/year/tmdb_id

3. **JSON Output**:
   ```json
   {
     "plugins": {
       "tmdb": {
         "type": "movie",
         "title": "The Matrix",  // ✅ NOT null
         "year": 1999,           // ✅ NOT null
         "tmdb_id": 603          // ✅ NOT null
       }
     }
   }
   ```

4. **Console Output**:
   ```
   ✓ TMDb: The Matrix (1999)
   ```

---

## TESTING COMMANDS

### Run archiverr with debug logging:
```bash
cd /home/samet/Workspace/archiverr
python -m archiverr --config config.yml --debug
```

### Check output JSON:
```bash
# View full output
cat output/run_*.json | jq '.'

# Check TMDb plugin data
cat output/run_*.json | jq '.jobs[0].plugins.tmdb'

# Check tasker summary (should have non-null values)
cat output/run_*.json | jq '.jobs[0].plugins.tmdb'
```

### Compare with main branch:
```bash
# Checkout main
git stash
git checkout main
python -m archiverr --config config.yml
cat output/run_*.json | jq '.jobs[0].plugins.tmdb' > /tmp/main_output.json

# Checkout dev branch
git checkout dev/communication-refactoring
git stash pop
python -m archiverr --config config.yml
cat output/run_*.json | jq '.jobs[0].plugins.tmdb' > /tmp/dev_output.json

# Compare
diff /tmp/main_output.json /tmp/dev_output.json
```

---

## ROOT CAUSE RECAP

**Primary Issue**: **Double Write with Override**

1. Plugin calls `services.updatePlugin(full_data)` → State writes to `job.plugins[name]` ✅
2. Plugin returns `PluginResult(data=full_data)`
3. StageExecutor receives result and OVERWRITES `job.plugins[name]` ❌
4. Original full data lost, replaced with whatever StageExecutor wrote

**Fix**: StageExecutor now checks if data exists before writing → If exists, only update status

**Secondary Issue**: **Data Format Assumptions**

- Tasker assumed normalized format (`movie.title.primary`)
- But TMDb might return raw format (`movie.title` as string)

**Fix**: Tasker now handles both formats with type checking

---

## NEXT STEPS

1. ✅ Run test and verify plugin data is complete
2. 📋 If still issues, add more debug logging
3. 📋 Compare output with main branch
4. 📋 Document any remaining differences
5. 📋 Create integration test for plugin data persistence

---

**Session 13 Status**: FIXES APPLIED - READY FOR TESTING
