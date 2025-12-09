# SESSION 13 - FLOW DIAGRAMS

Mevcut ve hedef sistem akış şemaları.

---

## 1. PLUGIN DATA FLOW - CURRENT (BROKEN)

```
┌─────────────────────────────────────────────────────────────┐
│ StageExecutor._execute_plugin_for_job()                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Create PluginServices                                     │
│    - mode: "per_job"                                         │
│    - current_job_id: "job_abc_0"                            │
│    - current_plugin_name: "tmdb"                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Call plugin.execute(job, services)                       │
│    ┌─────────────────────────────────────────────────┐     │
│    │ TMDbPlugin.execute()                            │     │
│    │  - Fetch from API                               │     │
│    │  - result = {movie: {...}, extras: {...}}      │     │
│    │  - data = {movie: ..., extras: ...}  (FULL)    │     │
│    │  - services.updatePlugin(data=data)  ✅        │     │
│    │  - return PluginResult(data=data)              │     │
│    └─────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                          ↓
          ┌───────────────┴───────────────┐
          ↓                               ↓
┌─────────────────────┐     ┌─────────────────────────────┐
│ services.updatePlugin│     │ PluginResult returned       │
│ (data=FULL)         │     │ (data=FULL in object)       │
└─────────────────────┘     └─────────────────────────────┘
          ↓                               ↓
┌─────────────────────┐     ┌─────────────────────────────┐
│ StateManager        │     │ StageExecutor receives      │
│ .update_plugin()    │     │ result object               │
│                     │     │                             │
│ _plugins_storage    │     │ result_data = result.data   │
│  [job_id]['tmdb']   │     │ (FULL DATA)                 │
│    = PluginState(   │     │                             │
│      data=FULL ✅   │     │ job.plugins['tmdb'] = {     │
│    )                │     │   status: {...},            │
│                     │     │   data: result_data ✅      │
│ job.plugins['tmdb'] │     │ }                           │
│  = {status, FULL}✅ │     │                             │
└─────────────────────┘     └─────────────────────────────┘
          ↓                               ↓
          └───────────────┬───────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. After plugin execution                                    │
│    job.plugins['tmdb'] should have FULL data                │
│                                                              │
│    EXPECTED:                                                 │
│    {                                                         │
│      status: {success: true, ...},                          │
│      data: {                                                 │
│        movie: {title, year, overview, ...},  // FULL        │
│        extras: {...},                                        │
│        normalized: {...}                                     │
│      }                                                       │
│    }                                                         │
│                                                              │
│    ACTUAL (in output JSON):                                 │
│    {                                                         │
│      type: "movie",                                          │
│      title: "Matrix",                                        │
│      year: null,                                             │
│      tmdb_id: null                                           │
│    }  ❌ WHERE IS THE FULL DATA?                            │
└─────────────────────────────────────────────────────────────┘
```

**PROBLEM**: Full data kayboluyorAMA nerede kaybolyor? Tasker'a gelene kadar mi, yoksa StageExecutor'dan sonra mı?

---

## 2. TASKER DATA EXTRACTION FLOW

```
┌─────────────────────────────────────────────────────────────┐
│ TaskerPlugin.execute(job, services)                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Get plugins data from job.plugins                        │
│    plugins_data = dict(job.plugins)                         │
│                                                              │
│    Expected structure:                                       │
│    {                                                         │
│      'renamer': {status: {...}, data: {parsed: ...}},      │
│      'tmdb': {status: {...}, data: {movie: ...}}           │
│    }                                                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Build job context                                         │
│    plugin_context = {}                                       │
│    for plugin_name, plugin_info in plugins_data.items():    │
│      if 'data' in plugin_info:                              │
│        plugin_context[plugin_name] = plugin_info  ✅        │
│        plugin_shortcuts[plugin_name] = plugin_info['data']  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Execute tasks (print, save)                              │
│    Template context:                                         │
│    {                                                         │
│      plugin: {tmdb: {status: ..., data: {...}}},           │
│      tmdb: {...},  // shortcut to plugin.tmdb.data         │
│      config: {...}                                           │
│    }                                                         │
│                                                              │
│    Task template: "{{ tmdb.movie.title }}"                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Track run output for JSON                                │
│    _track_run_output(job, result, plugins_data)            │
│                                                              │
│    calls _extract_plugin_summary(plugins_data)              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ _extract_plugin_summary() PROBLEM HERE!                     │
│                                                              │
│    if plugin_name == 'tmdb':                                │
│      movie = data.get('movie', {})  ❌                      │
│      summary['tmdb'] = {                                    │
│        'type': 'movie',                                      │
│        'title': movie.get('title', {}).get('primary'),  ❌  │
│        'year': movie.get('year'),                           │
│        'tmdb_id': movie.get('tmdb_id')                      │
│      }                                                       │
│                                                              │
│    SORUN: movie None veya empty dict dönüyor!               │
│    Çünkü data.get('movie') bulamıyor                        │
└─────────────────────────────────────────────────────────────┘
```

**ROOT CAUSE**: `job.plugins['tmdb']` içinde `data.movie` yok!

Ya:
1. TMDb plugin `services.updatePlugin()` çağrısında movie koymadı
2. StageExecutor job.plugins'i override etti
3. State manager düzgün kaydetmedi

---

## 3. EXPECTED FLOW (SESSION 12 STRATEGY)

```
┌──────────────────────────────────────────────────────────────┐
│ STAGE: DATA                                                   │
│ Plugin: tmdb (per_job, requires: renamer.data.parsed)       │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 1. TMDbPlugin.execute(job, services)                         │
│    - Read: job.plugins['renamer']['data']['parsed']         │
│    - Fetch: TMDb API (movie data)                            │
│    - Prepare: data = {                                       │
│        movie: {...full movie data...},                       │
│        extras: {...credits, images...},                      │
│        normalized: {...community format...}                  │
│      }                                                        │
│    - Store: services.updatePlugin(data=data)                 │
│    - Return: PluginResult.success_result(data=data)         │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. StateManager.update_plugin(job_id, 'tmdb', data)         │
│    - _plugins_storage[job_id]['tmdb'].data = data           │
│    - job.plugins['tmdb'] = {                                 │
│        status: {state: 'completed', success: true},         │
│        data: data  // FULL DATA HERE                         │
│      }                                                        │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. StageExecutor reads result                                │
│    result = plugin.execute(job, services)                    │
│    result_data = result.data  // Should be FULL              │
│                                                               │
│    ❌ PROBLEM: Should NOT override job.plugins!              │
│    Because services.updatePlugin() already did it.           │
│                                                               │
│    FIX: Skip override if services.updatePlugin() was called  │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. STAGE: OUTPUT                                              │
│    Plugin: tasker (per_job)                                  │
│                                                               │
│    TaskerPlugin.execute(job, services)                       │
│    - Read: job.plugins['tmdb']['data']['movie']             │
│    - Render: templates with full data                        │
│    - Execute: print/save tasks                               │
│    - Track: _extract_plugin_summary()                        │
│      → movie = data.get('movie', {})  ✅ NOW HAS DATA        │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 5. JSON OUTPUT                                                │
│    {                                                          │
│      plugins: {                                               │
│        tmdb: {                                                │
│          type: "movie",                                       │
│          title: "The Matrix",  ✅                            │
│          year: 1999,           ✅                            │
│          tmdb_id: 603          ✅                            │
│        }                                                      │
│      }                                                        │
│    }                                                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. SESSION 12 STRATEGY vs IMPLEMENTATION

### Strategy (session_12_strategy/03_PLUGIN_SYSTEM_REFACTORING.md)

**Plugin Communication Methods**:
```python
# Per-job plugins
services.updatePlugin(data)  # Update plugin.{name}.data

# No ID needed, uses current context:
# - current_job_id (set by StageExecutor)
# - current_plugin_name (set by StageExecutor)
```

**Global State Structure**:
```yaml
plugin.{name}:
  status:
    state: completed | failed | pending
    success: boolean
    duration_ms: int
  data:
    # Plugin's own data (everything here)
    movie: {...}
    extras: {...}
```

### Implementation (CURRENT)

**PluginServices.updatePlugin()** ✅:
```python
def updatePlugin(self, data: Dict[str, Any]) -> None:
    self._state.update_plugin(
        self._current_job_id, 
        self._current_plugin_name, 
        data
    )
```

**StateManager.update_plugin()** ✅:
```python
def update_plugin(self, job_id: str, plugin_name: str, data: Dict[str, Any]):
    # Update _plugins_storage
    self._plugins_storage[job_id][plugin_name].data = data
    
    # Update job.plugins for backward compat
    job = self.get_job_by_id(job_id)
    if job:
        job.plugins[plugin_name] = self._plugins_storage[job_id][plugin_name].to_dict()
        # to_dict() returns {status: {...}, data: {...}}
```

**StageExecutor._execute_plugin_for_job()** ❌:
```python
# Extract result data
result_data = {}
if hasattr(result, 'data') and result.data:
    result_data = result.data

# Session 12: Store plugin data
if result_data:
    # Update job.plugins with Session 12 structure
    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
        job.plugins[plugin_name] = {
            'status': {...},
            'data': result_data  # ❌ OVERRIDE!
        }
```

**PROBLEM**: StageExecutor overrides `job.plugins[plugin_name]` AFTER `services.updatePlugin()` already set it!

**ÇÖZÜM**: StageExecutor should NOT write to `job.plugins` if plugin used `services.updatePlugin()`.

---

## 5. MAIN BRANCH FLOW (WORKING)

Main branch'te Session 12 yok, eski sistem var:

```
┌──────────────────────────────────────────────────────────────┐
│ 1. PluginExecutor.execute_output_pipeline()                 │
│    - Each plugin: result = plugin.execute(match_data)       │
│    - match_data: {'input': {...}, 'renamer': {...}}        │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. TMDbPlugin.execute(match_data)                            │
│    renamer_data = match_data.get('renamer', {})             │
│    parsed = renamer_data.get('parsed', {})                  │
│                                                               │
│    result = self.movie_fetcher.fetch(name, year)            │
│                                                               │
│    return result  # {status, movie, extras, normalized, raw} │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. PluginExecutor stores result                              │
│    result['tmdb'] = plugin_result                            │
│    # Full dict with all data                                 │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. TaskManager.execute_tasks_for_match()                     │
│    context = build_job_context(match, context)              │
│    # match has all plugin results                            │
│                                                               │
│    Templates can access: {{ tmdb.movie.title }}             │
└──────────────────────────────────────────────────────────────┘
```

**KEY DIFFERENCE**: No `services.updatePlugin()`, plugin return value IS the data!

---

## NEXT STEPS

1. ✅ **Immediate Fix**: Remove StageExecutor override after services.updatePlugin()
2. ✅ **TMDb Fix**: Ensure PluginResult.data has FULL data
3. ✅ **Tasker Fix**: Verify data structure expectations
4. 📋 **Testing**: Add integration test for plugin data persistence
