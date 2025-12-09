# SESSION 13 - CRITICAL ISSUES DETECTED

```yaml
tarih: 2025-12-09
önceki: session_12 (strategy complete, implementation broken)
durum: CRITICAL - Plugin system not working
hedef: Fix plugin data flow and restore functionality
```

---

## PROBLEM STATEMENT

Session 12 stratejisi koda geçirildi ancak **pluginler düzgün çalışmıyor**:

### 🔴 Kritik Sorunlar

1. **TMDb Plugin Boş Dönüyor**
   - Eski (main): 1000+ satır raw + normalized data
   - Yeni (current): Sadece `{type: "movie", title: "Matrix", year: null, tmdb_id: null}`
   - **Sorun**: Plugin execute oluyor ama data kayboluyoroutput/run_eec982af_20251208_023038.json:
```json
"tmdb": {
  "type": "movie",
  "title": "Matrix",
  "year": null,
  "tmdb_id": null
}
```

2. **Tasker Plugin State Sorunu**
   - Task'lar execute oluyor (print output'lar var)
   - Ama plugin data JSON'a yazılmıyor
   - `_extract_plugin_summary()` metodu data'yı doğru alamıyor

3. **Plugin Data Flow Problemi**
   - `services.updatePlugin(data)` çağrılıyor
   - State manager `update_plugin()` çalışıyor
   - AMA final output'ta data yok veya minimal

---

## MAIN BRANCH vs CURRENT BRANCH

### Main Branch (ÇALIŞAN)

**TMDb Plugin** (`src/archiverr/plugins/tmdb/client.py`):
```python
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    renamer_data = match_data.get('renamer', {})
    parsed_data = renamer_data.get('parsed', {})
    
    result = self.movie_fetcher.fetch(name, year)
    # result = {status, movie, episode, show, extras, normalized, raw}
    
    return result  # Direkt dönüyor
```

**Output Format**:
- `status`: {success, started_at, finished_at, duration_ms}
- `movie`: Full movie data (title, year, overview, genres, runtime, etc.)
- `extras`: Credits, images, videos
- `normalized`: Community standard format
- `raw`: API response (if include-raw: true)

### Current Branch (BOZUK)

**TMDb Plugin** (`src/archiverr/plugins/tmdb/client.py`):
```python
def execute(self, job: Any, services: Any) -> PluginResult:
    # Session 12: Get data from job.plugins
    renamer_data = job.plugins.get('renamer', {})
    renamer_data_content = renamer_data.get('data', {})
    parsed_data = renamer_data_content.get('parsed', {})
    
    result = self.movie_fetcher.fetch(name, year)
    
    # Extract data and call updatePlugin
    data = {k: v for k, v in result.items() if k != 'status'}
    services.updatePlugin(data=data)
    
    return PluginResult.success_result(data=data, started_at=started_at)
```

**Sorun**: `services.updatePlugin()` çağrılıyor ama data final output'a yansımıyor!

---

## STATE FLOW ANALİZİ

### Expected Flow (Session 12)

```
1. Plugin.execute(job, services) called
   ↓
2. Plugin fetches data (e.g., TMDb API)
   ↓
3. Plugin calls services.updatePlugin(data)
   ↓
4. PluginServices.updatePlugin() → StateManager.update_plugin()
   ↓
5. StateManager stores in:
   - _plugins_storage[job_id][plugin_name] = PluginState(data=data)
   - job.plugins[plugin_name] = {status: {...}, data: {...}}
   ↓
6. Tasker reads job.plugins[plugin_name].data
   ↓
7. JSON output includes full plugin data
```

### Actual Flow (BROKEN)

```
1. Plugin.execute(job, services) called ✅
   ↓
2. Plugin fetches data ✅
   ↓
3. Plugin calls services.updatePlugin(data) ✅
   ↓
4. StateManager.update_plugin() çalışıyor ✅
   ↓
5. Data _plugins_storage'a yazılıyor ✅
   ↓
6. AMA job.plugins düzgün güncellenmiyorBEKLENEN:
job.plugins['tmdb'] = {
  'status': {...},
  'data': {
    'movie': {...},  # FULL DATA
    'extras': {...},
    'normalized': {...}
  }
}

GERÇEK:
job.plugins['tmdb'] = {
  'type': 'movie',
  'title': 'Matrix',
  'year': null,
  'tmdb_id': null
}
```

---

## ROOT CAUSE ANALYSIS

### 1️⃣ Tasker'ın Yanlış Data Çıkarması

**Tasker Plugin** (`_extract_plugin_summary`):
```python
def _extract_plugin_summary(self, plugins_data: Dict[str, Any]) -> Dict[str, Any]:
    for plugin_name, plugin_info in plugins_data.items():
        if isinstance(plugin_info, dict):
            if 'data' in plugin_info:
                data = plugin_info['data']  # ✅ Doğru yol
                # ...
                if plugin_name == 'tmdb':
                    movie = data.get('movie', {})  # ❌ movie dict değil None?
                    summary[plugin_name] = {
                        'type': 'movie',
                        'title': movie.get('title', {}).get('primary'),  # ❌ None
                        ...
                    }
```

**Sorun**: `data.get('movie')` None dönüyor çünkü TMDb data düzgün kayıtlı değil!

### 2️⃣ StageExecutor'ın Data Yazma Sorunu

**StageExecutor** (`_execute_plugin_for_job`):
```python
# Session 12: Store plugin data
if result_data:
    # Cache for trigger evaluation
    self._plugin_data_cache[job.id][plugin_name] = result_data
    
    # Update job.plugins
    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
        job.plugins[plugin_name] = {
            'status': {...},
            'data': result_data  # ✅ Doğru format
        }
```

**AMA**: Plugin'in döndüğü `result_data` zaten minimal! Çünkü `PluginResult.success_result(data=data)` dönüyor ve bu data zaten az.

### 3️⃣ PluginResult Dönüşüm Sorunu

**TMDb Plugin**:
```python
# Convert dict result to PluginResult
data = {k: v for k, v in result.items() if k != 'status'}

services.updatePlugin(data=data)  # State'e yazıyor

return PluginResult.success_result(data=data, started_at=started_at)
```

**AMA**: StageExecutor bu dönen PluginResult'ı alıyor:
```python
result = plugin.execute(job, services)

# Extract result data
result_data = {}
if hasattr(result, 'data') and result.data:
    result_data = result.data  # ❌ Bu PluginResult.data
```

**İki farklı data var**:
1. `services.updatePlugin(data)` → State'e yazılan (FULL)
2. `PluginResult.data` → StageExecutor'ın gördüğü (MINIMAL?)

---

## HYPOTHESIS

**Ana sorun**: Plugin iki kez data yazıyor:
1. `services.updatePlugin(data)` → State'e tam data yazıyor
2. `return PluginResult(data)` → StageExecutor'a minimal data dönüyor

StageExecutor, PluginResult'tan aldığı minimal data ile job.plugins'i OVERRIDE ediyor!

```python
# StageExecutor line 368-381
result_data = result.data  # PluginResult'tan alınan MINIMAL data

job.plugins[plugin_name] = {
    'status': {...},
    'data': result_data  # ❌ OVERRIDE ediyor services.updatePlugin()'i!
}
```

---

## ACTION ITEMS

### ✅ Acil Düzeltmeler

1. **StageExecutor**: PluginResult.data yerine state'teki data'yı kullan
2. **TMDb**: PluginResult.data'ya da FULL data koy
3. **Tasker**: Plugin data okuma mantığını düzelt

### 📋 Uzun Vadeli

1. Session 12 stratejisini tam implementasyon ile karşılaştır
2. Plugin → StageExecutor → State → Tasker data flow şeması çıkar
3. Test suite ekle (plugin data persistence validation)

---

**Sonraki Adım**: Kod düzeltmeleri ve detaylı flow şemaları
