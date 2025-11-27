# EXECUTION FLOW - STEP-BY-STEP PROCESSING

## COMPLETE EXECUTION SEQUENCE

### Phase 0: Startup (Pre-execution)
```python
# __main__.py: main()

# 1. Record timestamp
start_time = datetime.now()  # Single source of truth

# 2. Load config
config_path = Path("config.yml")
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 3. Extract options
debug = config.get('options', {}).get('debug', False)
dry_run = config.get('options', {}).get('dry_run', True)

# 4. Initialize debug system
debugger = init_debugger(enabled=debug)
```

**Duration:** <50ms  
**Output:** Config dict, debugger singleton

---

### Phase 1: Plugin Discovery
```python
# __main__.py: lines 57-61

discovery = PluginDiscovery()
all_plugins = discovery.discover()

# discovery.discover() implementation:
def discover(self) -> Dict[str, Dict]:
    plugins_dir = Path(__file__).parent.parent / 'plugins'
    all_plugins = {}
    
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue
        
        manifest = plugin_dir / 'plugin.json'
        if not manifest.exists():
            continue
        
        with open(manifest) as f:
            metadata = json.load(f)
            all_plugins[metadata['name']] = metadata
    
    return all_plugins
```

**Input:** `src/archiverr/plugins/*/plugin.json`  
**Output:**
```python
{
    'scanner': {
        'name': 'scanner',
        'version': '1.0.0',
        'category': 'input',
        'class_name': 'ScannerPlugin',
        'depends_on': [],
        'expects': [],
        'categories': []
    },
    'tmdb': {
        'name': 'tmdb',
        'version': '1.0.0',
        'category': 'output',
        'class_name': 'TMDbPlugin',
        'depends_on': ['renamer'],
        'expects': ['renamer.parsed'],
        'categories': ['movie', 'show']
    },
    # ... all 8 plugins
}
```

**Duration:** <10ms

---

### Phase 2: Plugin Loading
```python
# __main__.py: lines 64-68

loader = PluginLoader(all_plugins, config)
input_plugins = loader.load_by_category('input')
output_plugins = loader.load_by_category('output')

# loader.load_by_category('input') implementation:
def load_by_category(self, category: str) -> Dict[str, BasePlugin]:
    loaded = {}
    
    for name, metadata in self.all_plugins.items():
        if metadata.get('category') != category:
            continue
        
        # Check enabled
        plugin_config = self.config.get('plugins', {}).get(name, {})
        if not plugin_config.get('enabled', False):
            continue
        
        # Dynamic import
        class_name = metadata.get('class_name') or self._derive_class_name(name)
        module_path = f'archiverr.plugins.{name}.client'
        
        module = importlib.import_module(module_path)
        plugin_class = getattr(module, class_name)
        
        # Instantiate
        plugin_instance = plugin_class(plugin_config)
        loaded[name] = plugin_instance
    
    return loaded
```

**Input:** Plugin metadata + config  
**Output:**
```python
input_plugins = {
    'scanner': <ScannerPlugin instance>
}

output_plugins = {
    'ffprobe': <FFProbePlugin instance>,
    'renamer': <RenamerPlugin instance>,
    'tmdb': <TMDbPlugin instance>,
    'tvdb': <TVDbPlugin instance>,
    'omdb': <OMDbPlugin instance>
}
```

**Duration:** <50ms  
**Note:** Only enabled plugins loaded

---

### Phase 3: Dependency Resolution
```python
# __main__.py: lines 71-82

resolver = DependencyResolver(all_plugins)
enabled_output = list(output_plugins.keys())  # ['ffprobe', 'renamer', 'tmdb', ...]

execution_groups = resolver.resolve(enabled_output)

# resolver.resolve() implementation:
def resolve(self, enabled_plugins: List[str]) -> List[List[str]]:
    # Build dependency graph
    graph = {}
    for plugin in enabled_plugins:
        metadata = self.plugin_metadata[plugin]
        deps = metadata.get('depends_on', [])
        # Only include deps that are enabled
        graph[plugin] = set(d for d in deps if d in enabled_plugins)
    
    # Kahn's algorithm (topological sort)
    execution_groups = []
    
    while graph:
        # Find plugins with no dependencies
        ready = [p for p, deps in graph.items() if not deps]
        
        if not ready:
            raise ValueError("Circular dependency detected")
        
        execution_groups.append(ready)
        
        # Remove ready plugins
        for p in ready:
            del graph[p]
        
        # Remove from other dependencies
        for deps in graph.values():
            deps -= set(ready)
    
    return execution_groups
```

**Input:** `['ffprobe', 'renamer', 'tmdb', 'tvdb', 'omdb']`  
**Output:**
```python
[
    ['ffprobe', 'renamer'],  # Group 0: No dependencies (parallel)
    ['tmdb', 'tvdb', 'omdb'] # Group 1: Depends on renamer (parallel within group)
]
```

**Duration:** <5ms

---

### Phase 4: Input Execution
```python
# __main__.py: lines 85-93

executor = PluginExecutor()
input_matches = executor.execute_input_plugins(input_plugins)

# executor.execute_input_plugins() implementation:
def execute_input_plugins(self, plugins: Dict[str, InputPlugin]) -> List[Dict]:
    all_matches = []
    
    for plugin_name, plugin_instance in plugins.items():
        self.debugger.debug("executor", f"Executing input plugin: {plugin_name}")
        
        matches = plugin_instance.execute()
        
        # Format: wrap in 'input' key
        for match in matches:
            all_matches.append({'input': match})
    
    return all_matches
```

**Example - Scanner Plugin Execution:**
```python
# scanner.execute() returns:
[
    {
        'status': {
            'success': True,
            'started_at': '2025-11-26T16:30:00.100+03:00',
            'finished_at': '2025-11-26T16:30:00.112+03:00',
            'duration_ms': 12
        },
        'input': {
            'path': '/home/samet/torrents/Mr. & Mrs. Smith (2005).mkv',
            'virtual': False
        }
    }
]

# Executor wraps in 'input':
input_matches = [
    {
        'input': {
            'status': {...},
            'input': {
                'path': '/home/samet/torrents/Mr. & Mrs. Smith (2005).mkv',
                'virtual': False
            }
        }
    }
]
```

**Duration:** 10-100ms (depends on file count)  
**Output:** List of initial match dicts

---

### Phase 5: Per-Match Processing (MAIN LOOP)

```python
# __main__.py: lines 95-149

processed_matches = []
match_task_results = {}

template_manager = TemplateManager()
task_manager = TaskManager(config, template_manager)
builder = APIResponseBuilder()

for index, match in enumerate(input_matches):
    # Phase 5.1: Output Pipeline
    result = executor.execute_output_pipeline(
        output_plugins,
        execution_groups,
        match,
        resolver
    )
    
    processed_matches.append(result)
    
    # Phase 5.2: Task Execution
    temp_api_response = builder.build(
        processed_matches,
        config,
        start_time,
        all_plugins
    )
    
    task_results = task_manager.execute_tasks_for_match(
        temp_api_response,
        index,
        dry_run
    )
    
    match_task_results[index] = task_results
```

---

#### Phase 5.1: Output Pipeline (Per Match)

```python
# executor.execute_output_pipeline() implementation:

def execute_output_pipeline(
    self,
    plugins: Dict[str, OutputPlugin],
    execution_groups: List[List[str]],
    match_data: Dict,
    resolver: DependencyResolver
) -> Dict:
    result = match_data.copy()
    
    for group in execution_groups:
        # Step 1: Extract available data
        available_data = self._extract_available_data(result)
        # available_data = {'input', 'input.path', ...}
        
        # Step 2: Filter by expects
        ready_plugins = []
        pending_plugins = []
        
        for plugin_name in group:
            if resolver.check_expects(plugin_name, available_data):
                ready_plugins.append(plugin_name)
            else:
                pending_plugins.append(plugin_name)
        
        # Step 3: Execute ready plugins
        for plugin_name in ready_plugins:
            plugin_instance = plugins[plugin_name]
            
            try:
                plugin_result = plugin_instance.execute(result)
                result[plugin_name] = plugin_result
                
                # Generic category propagation
                if 'category' in plugin_result and 'input' in result:
                    result['input']['category'] = plugin_result['category']
            
            except Exception as e:
                self.debugger.error("executor", f"Plugin {plugin_name} failed", error=str(e))
                result[plugin_name] = {
                    'status': {'success': False, 'error': str(e)}
                }
    
    return result
```

**Example - Match 0 Processing:**

**Initial State:**
```python
match_data = {
    'input': {
        'path': '/home/samet/torrents/Mr. & Mrs. Smith (2005).mkv',
        'virtual': False
    }
}
```

**Group 0 Execution (ffprobe, renamer):**

1. **Available Data Check:**
   ```python
   available_data = {'input', 'input.path', 'input.virtual'}
   ```

2. **Expects Check:**
   ```python
   # ffprobe expects: ['input'] ✅
   # renamer expects: ['input'] ✅
   ready_plugins = ['ffprobe', 'renamer']
   ```

3. **Execute ffprobe:**
   ```python
   ffprobe_result = ffprobe.execute(match_data)
   match_data['ffprobe'] = ffprobe_result
   # match_data now has: {'input': {...}, 'ffprobe': {...}}
   ```

4. **Execute renamer:**
   ```python
   renamer_result = renamer.execute(match_data)
   match_data['renamer'] = renamer_result
   
   # Category propagation
   if renamer_result['category'] == 'movie':
       match_data['input']['category'] = 'movie'
   
   # match_data now has: {'input': {..., 'category': 'movie'}, 'ffprobe': {...}, 'renamer': {...}}
   ```

**Group 1 Execution (tmdb, tvdb, omdb):**

1. **Available Data Check:**
   ```python
   available_data = {
       'input',
       'input.path',
       'input.category',
       'ffprobe',
       'ffprobe.video',
       'ffprobe.container',
       'renamer',
       'renamer.parsed',
       'renamer.category'
   }
   ```

2. **Expects Check:**
   ```python
   # tmdb expects: ['renamer.parsed'] ✅
   # tvdb expects: ['renamer.parsed'] ✅
   # omdb expects: ['renamer.parsed'] ✅
   ready_plugins = ['tmdb', 'tvdb', 'omdb']
   ```

3. **Execute all (parallel):**
   ```python
   tmdb_result = tmdb.execute(match_data)
   match_data['tmdb'] = tmdb_result
   
   tvdb_result = tvdb.execute(match_data)
   match_data['tvdb'] = tvdb_result
   
   omdb_result = omdb.execute(match_data)
   match_data['omdb'] = omdb_result
   ```

**Final Result:**
```python
result = {
    'input': {
        'path': '/home/samet/torrents/Mr. & Mrs. Smith (2005).mkv',
        'virtual': False,
        'category': 'movie'
    },
    'ffprobe': {
        'status': {...},
        'video': {...},
        'audio': [...],
        'container': {...}
    },
    'renamer': {
        'status': {...},
        'parsed': {
            'movie': {'name': 'Mr. & Mrs. Smith', 'year': 2005},
            'show': None
        },
        'category': 'movie'
    },
    'tmdb': {
        'status': {...},
        'movie': {...},
        'validation': {...}
    },
    'tvdb': {...},
    'omdb': {...}
}
```

**Duration:** 1-3 seconds (API calls dominate)

---

#### Phase 5.2: Task Execution (Per Match)

```python
# task_manager.execute_tasks_for_match() implementation:

def execute_tasks_for_match(
    self,
    api_response: Dict,
    match_index: int,
    dry_run: bool
) -> List[Dict]:
    tasks = self.config.get('tasks', [])
    task_results = []
    
    # Build context
    context = self.template_manager.build_context(api_response, match_index)
    
    for task in tasks:
        # Check condition
        if not self._check_condition(task, context):
            continue
        
        # Execute by type
        if task.get('external'):
            result = self._execute_external_task(task, context, dry_run)
        elif task['type'] == 'print':
            result = self._execute_print_task(task, context)
        elif task['type'] == 'save':
            result = self._execute_save_task(task, context, dry_run)
        
        task_results.append(result)
    
    return task_results
```

**Example - Match 0 Tasks:**

**Context Building:**
```python
context = {
    'globals': api_response['globals'],
    'matches': api_response['matches'],
    'index': 0,
    'tmdb': api_response['matches'][0]['plugins']['tmdb'],
    'ffprobe': api_response['matches'][0]['plugins']['ffprobe'],
    'renamer': api_response['matches'][0]['plugins']['renamer'],
    '0': api_response['matches'][0]
}
```

**Task 1: print_match_header**
```python
task = {
    'name': 'print_match_header',
    'type': 'print',
    'template': '========== MATCH {{ index }} =========='
}

# Render
rendered = "========== MATCH 0 =========="

# Print to stdout
print(rendered)

# Result
task_result = {
    'task_name': 'print_match_header',
    'type': 'print',
    'success': True,
    'output': '========== MATCH 0 =========='
}
```

**Task 2: save_nfo (external)**
```python
task = {
    'external': True,
    'name': 'save_nfo',
    'path': 'tasks/save_nfo.yml'
}

# Load external YAML
with open('tasks/save_nfo.yml') as f:
    external_task = yaml.safe_load(f)
    # {
    #   'type': 'save',
    #   'destination': '{{ tmdb.movie.title }}.nfo',
    #   'template': '{{ tmdb.movie | tojson }}'
    # }

# Render destination
destination = "Mr. & Mrs. Smith.nfo"

# Render content
content = json.dumps(context['tmdb']['movie'], indent=2)

# Save file (if not dry_run)
if not dry_run:
    with open(destination, 'w') as f:
        f.write(content)

# Result
task_result = {
    'task_name': 'save_nfo',
    'type': 'save',
    'success': True,
    'destination': 'Mr. & Mrs. Smith.nfo',
    'dry_run': dry_run
}
```

**Task 3: print_summary (conditional)**
```python
task = {
    'name': 'print_summary',
    'type': 'print',
    'condition': '{{ index == (globals.status.matches - 1) }}',  # Last match only
    'template': 'Total: {{ globals.status.matches }}'
}

# Check condition
# index=0, matches=2 -> 0 == 1? No
# SKIP (condition not met)
```

**Task Results:**
```python
task_results = [
    {
        'task_name': 'print_match_header',
        'type': 'print',
        'success': True,
        'output': '========== MATCH 0 =========='
    },
    {
        'task_name': 'save_nfo',
        'type': 'save',
        'success': True,
        'destination': 'Mr. & Mrs. Smith.nfo',
        'dry_run': True
    }
]

match_task_results[0] = task_results
```

**Duration:** 10-50ms per match

---

### Phase 6: Final API Response Building

```python
# __main__.py: lines 152-189

# Build final response
api_response = builder.build(
    processed_matches,
    config,
    start_time,
    all_plugins
)

# Add task results to matches
for match_index, task_results_list in match_task_results.items():
    match = api_response['matches'][match_index]
    match_output = match.get('globals', {}).get('output', {})
    
    # Format tasks
    formatted_tasks = []
    for task_result in task_results_list:
        task_entry = {
            'name': task_result.get('task_name'),
            'type': task_result.get('type'),
            'success': task_result.get('success', True)
        }
        
        if task_result.get('type') == 'print':
            task_entry['rendered'] = task_result.get('output')
        elif task_result.get('type') == 'save':
            task_entry['destination'] = task_result.get('destination')
        
        formatted_tasks.append(task_entry)
    
    match_output['tasks'] = formatted_tasks

# Update task count
api_response['globals']['status']['tasks'] = len(all_task_results)
```

**builder.build() Implementation:**
```python
def build(self, matches, config, start_time, loaded_plugins):
    end_time = datetime.now()
    
    # Build globals
    globals_obj = {
        'status': self._build_global_status(matches, end_time),
        'summary': self._build_summary(matches),
        'config': {
            'options': config.get('options', {}),
            'plugins': config.get('plugins', {}),
            'tasks': config.get('tasks', [])
        }
    }
    
    # Format matches
    formatted_matches = [self._format_match(m) for m in matches]
    
    return {
        'globals': globals_obj,
        'matches': formatted_matches
    }
```

**Output Structure:**
```javascript
{
  "globals": {
    "status": {
      "success": true,
      "matches": 1,
      "errors": 0,
      "tasks": 2,
      "started_at": "2025-11-26T16:30:00.000+03:00",
      "finished_at": "2025-11-26T16:30:05.000+03:00",
      "duration_ms": 5000
    },
    "summary": {...},
    "config": {...}
  },
  "matches": [{
    "globals": {
      "index": 0,
      "input_path": "/path/file.mkv",
      "status": {...},
      "output": {
        "tasks": [
          {
            "name": "print_match_header",
            "type": "print",
            "success": true,
            "rendered": "========== MATCH 0 =========="
          },
          {
            "name": "save_nfo",
            "type": "save",
            "success": true,
            "destination": "Mr. & Mrs. Smith.nfo"
          }
        ]
      }
    },
    "plugins": {...}
  }]
}
```

**Duration:** <10ms

---

### Phase 7: Report Generation

```python
# __main__.py: lines 191-199

timestamp = start_time.strftime("%Y%m%d_%H%M%S")
report_paths = generate_dual_reports(api_response, timestamp, debugger)

# generate_dual_reports() implementation:
def generate_dual_reports(api_response, timestamp, debugger):
    reports_dir = Path('reports')
    reports_dir.mkdir(exist_ok=True)
    
    # Full report
    full_path = reports_dir / f'api_response_full_{timestamp}.json'
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(api_response, f, indent=2, ensure_ascii=False)
    
    # Compact report
    simplifier = ResponseSimplifier()
    compact_response = simplifier.simplify(api_response)
    
    compact_path = reports_dir / f'api_response_compact_{timestamp}.json'
    with open(compact_path, 'w', encoding='utf-8') as f:
        json.dump(compact_response, f, indent=2, ensure_ascii=False)
    
    return {
        'full': str(full_path),
        'compact': str(compact_path)
    }
```

**Output:**
- `reports/api_response_full_20251126_163000.json` (146 KB)
- `reports/api_response_compact_20251126_163000.json` (9 KB)

**Duration:** 50-200ms

---

## TIMING BREAKDOWN

**Single Match (Mr. & Mrs. Smith):**
```
Startup:              50ms
Plugin Discovery:     10ms
Plugin Loading:       50ms
Dependency Resolve:    5ms
Input Execution:      10ms
├─ Scanner:           10ms

Output Pipeline:    2500ms
├─ Group 0:          800ms
│  ├─ FFProbe:       150ms (subprocess)
│  └─ Renamer:        50ms (parsing)
├─ Group 1:         1700ms
│  ├─ TMDb:         1200ms (API + extras)
│  ├─ TVDb:          300ms (API)
│  └─ OMDb:          200ms (API)

Task Execution:       30ms
├─ print_header:       5ms
├─ save_nfo:          20ms
└─ print_summary:      5ms

Response Build:       10ms
Report Generation:   100ms
────────────────────────
TOTAL:              2765ms (~2.8s)
```

**100 Matches (estimated):**
```
Startup:              50ms
Discovery+Loading:   110ms
Dependency:            5ms

Per-Match (x100):  250000ms (250s = 4.2 min)
├─ Avg per match:   2500ms
├─ API calls:      200000ms (80%)
└─ Local:           50000ms (20%)

Response Build:      100ms
Report Generation:   500ms
────────────────────────
TOTAL:            250765ms (~4.2 minutes)
```

**Optimization Targets:**
- API calls: 80% of time
- Parallel API calls possible (future)
- Caching API results (future)
- Async execution (MongoDB Phase 7)

---

## ERROR HANDLING FLOW

### Plugin Failure Scenario

**Setup:**
```python
# Renamer fails (parsing error)
input_matches = [{'input': {'path': 'InvalidFilename.mkv'}}]
```

**Execution:**

1. **Group 0:**
   ```python
   # FFProbe: Success
   match_data['ffprobe'] = {...}
   
   # Renamer: FAIL
   try:
       renamer_result = renamer.execute(match_data)
   except Exception as e:
       match_data['renamer'] = {
           'status': {'success': False, 'error': 'Parse failed'}
       }
   
   # Available data: {'input', 'ffprobe'} (NO renamer.parsed)
   ```

2. **Group 1:**
   ```python
   available_data = {'input', 'ffprobe', 'renamer'}  # NO renamer.parsed
   
   # TMDb expects check
   resolver.check_expects('tmdb', available_data)
   # expects=['renamer.parsed'] but only {'input', 'ffprobe', 'renamer'} available
   # Returns: False
   
   # TMDb SKIPPED (expects not met)
   # TVDb SKIPPED
   # OMDb SKIPPED
   ```

3. **Result:**
   ```javascript
   {
     "globals": {
       "status": {
         "success": false,  // At least one match failed
         "errors": 1
       }
     },
     "matches": [{
       "globals": {
         "status": {
           "success": false,
           "success_plugins": ["ffprobe"],
           "failed_plugins": ["renamer"],
           "not_supported_plugins": ["tmdb", "tvdb", "omdb"]  // Expects not met
         }
       },
       "plugins": {
         "ffprobe": {...},
         "renamer": {
           "status": {"success": false, "error": "Parse failed"}
         }
       }
     }]
   }
   ```

---

## MOCK JSON STRATEGY (Current Implementation)

**Purpose:** Test API responses without actual API calls

**Location:** `tests/` or `reports/` (existing API response files)

**Strategy:**
```python
# Future: Mock mode in config
config:
  options:
    mock_mode: true  # Use saved responses instead of API calls

# Plugin checks:
if self.config.get('mock_mode'):
    # Load from reports/mock_tmdb_response.json
    with open('tests/mocks/tmdb_mr_mrs_smith.json') as f:
        return json.load(f)
else:
    # Real API call
    return self.api.search_movie(...)
```

**Current Workaround:**
- Run once with real APIs → Generate `api_response_full_*.json`
- Use generated JSON for testing/development
- No mock mode in code yet (Phase 8-9)

---

## PARALLEL EXECUTION OPPORTUNITIES

**Current (Sequential within group):**
```python
for plugin_name in ready_plugins:
    result = plugin.execute(match_data)  # One at a time
```

**Future (Parallel):**
```python
import asyncio

async def execute_group_parallel(plugins, match_data):
    tasks = [
        plugin.execute_async(match_data)
        for plugin in plugins
    ]
    results = await asyncio.gather(*tasks)
    return results
```

**Benefit:** Group 1 execution time: 1700ms → 1200ms (max of parallel calls)

---

This completes Execution Flow documentation. Every phase detailed with code, timing, error scenarios, and optimization opportunities.
