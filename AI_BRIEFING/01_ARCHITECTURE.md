# ARCHITECTURE - COMPLETE TECHNICAL SPECIFICATION

## CORE PRINCIPLE: PLUGIN-AGNOSTIC SYSTEM

### ABSOLUTE RULES (NEVER VIOLATE)

```python
# ❌ FORBIDDEN IN CORE
if plugin_name == 'tmdb':
    handle_tmdb()

from plugins.tmdb import TMDbPlugin

result['tmdb_data'] = get_tmdb()

# ✅ ALLOWED IN CORE
if 'category' in plugin_result:
    result['input']['category'] = plugin_result['category']

plugin_class = getattr(module, class_name)  # Dynamic import

for plugin_name, plugin_data in match_data.items():
    if isinstance(plugin_data, dict):
        process_generic(plugin_data)
```

**Core NEVER knows:**
- Plugin names (tmdb, tvdb, omdb, etc.)
- Plugin data structures (movie, show, episode, season)
- Plugin-specific logic
- Media types (movies vs shows)

**Core ONLY knows:**
- Plugin category (input/output) from plugin.json
- Generic patterns (dict, list, string)
- Dependency graph from plugin.json
- Expected data keys from plugin.json

---

## DIRECTORY STRUCTURE (COMPLETE)

```
/home/samet/Workspace/archiverr/
├── config.yml                           # User configuration (YAML)
├── config.schema.json                   # JSON Schema for config validation
├── .env                                 # Environment variables (API keys)
├── .env.example                         # Template for .env
├── requirements.txt                     # Python dependencies
├── setup.py                             # Package setup
│
├── src/archiverr/
│   ├── __init__.py                      # Package init
│   ├── __main__.py                      # Entry point (main execution)
│   │
│   ├── core/
│   │   ├── config_validator.py          # ConfigValidator class
│   │   │
│   │   ├── plugins/                     # Plugin system (NO _system suffix)
│   │   │   ├── __init__.py              # Exports: PluginDiscovery, PluginLoader, DependencyResolver, PluginExecutor
│   │   │   ├── discovery.py             # PluginDiscovery: Scan plugins/*/plugin.json
│   │   │   ├── loader.py                # PluginLoader: Dynamic import, load_by_category()
│   │   │   ├── resolver.py              # DependencyResolver: Topological sort, check_expects()
│   │   │   └── executor.py              # PluginExecutor: execute_input_plugins(), execute_output_pipeline()
│   │   │
│   │   ├── tasks/                       # Task system (NO _system suffix)
│   │   │   ├── __init__.py              # Exports: TemplateManager, TaskManager
│   │   │   ├── template_manager.py      # TemplateManager: Jinja2 rendering, variable resolution
│   │   │   └── task_manager.py          # TaskManager: execute_tasks(), handle print/save
│   │   │
│   │   └── reports/                     # Response simplification
│   │       ├── __init__.py              # Exports: generate_dual_reports
│   │       ├── response_simplifier.py   # ResponseSimplifier: Type-based simplification
│   │       └── report_generator.py      # generate_dual_reports(): Full + compact JSON
│   │
│   ├── models/
│   │   ├── __init__.py                  # Exports: APIResponseBuilder
│   │   └── response_builder.py          # APIResponseBuilder: build(), _build_summary()
│   │
│   ├── plugins/                         # ALL plugins (flat structure)
│   │   ├── __init__.py
│   │   ├── base.py                      # BasePlugin, InputPlugin, OutputPlugin, ValidationResult
│   │   │
│   │   ├── scanner/                     # INPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=input, expects=[]
│   │   │   └── client.py                # ScannerPlugin: execute() -> List[match]
│   │   │
│   │   ├── file-reader/                 # INPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=input, expects=[]
│   │   │   └── client.py                # FileReaderPlugin: execute() -> List[match]
│   │   │
│   │   ├── ffprobe/                     # OUTPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=output, expects=["input"]
│   │   │   ├── client.py                # FFProbePlugin: execute() -> {video, audio, container}
│   │   │   └── ffprobe_wrapper.py       # FFProbe wrapper class
│   │   │
│   │   ├── renamer/                     # OUTPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=output, expects=["input"]
│   │   │   ├── client.py                # RenamerPlugin: execute() -> {parsed, category}
│   │   │   └── parser.py                # Parsing logic (movie/show detection)
│   │   │
│   │   ├── tmdb/                        # OUTPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=output, expects=["renamer.parsed"]
│   │   │   ├── client.py                # TMDbPlugin: execute() -> {movie, episode, season, show}
│   │   │   ├── extras.py                # Extra API calls (credits, images, keywords, videos)
│   │   │   └── api/                     # API wrapper
│   │   │       └── tmdb_api.py
│   │   │
│   │   ├── tvdb/                        # OUTPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=output, expects=["renamer.parsed"]
│   │   │   ├── client.py                # TVDbPlugin: execute()
│   │   │   ├── extras.py                # Extended metadata
│   │   │   └── api/
│   │   │       └── tvdb_api.py
│   │   │
│   │   ├── tvmaze/                      # OUTPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=output, expects=["renamer.parsed"]
│   │   │   ├── client.py                # TVMazePlugin: execute()
│   │   │   ├── extras.py                # Cast, crew, episodes, images
│   │   │   └── api/
│   │   │       └── tvmaze_api.py
│   │   │
│   │   ├── omdb/                        # OUTPUT PLUGIN
│   │   │   ├── plugin.json              # Manifest: category=output, expects=["renamer.parsed"]
│   │   │   ├── client.py                # OMDbPlugin: execute()
│   │   │   └── api/
│   │   │       └── omdb_api.py
│   │   │
│   │   └── mock_test/                   # TEST PLUGIN
│   │       ├── plugin.json
│   │       └── client.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── debug.py                     # Debugger: init_debugger(), get_debugger()
│   │   ├── filters.py                   # Jinja2 custom filters
│   │   └── templates.py                 # Template utilities
│   │
│   ├── backend/                         # FUTURE: MongoDB backend
│   │   └── (empty - Phase 7)
│   │
│   └── reports/                         # FUTURE: Report templates
│       └── (empty)
│
├── tasks/                               # External task YAML files
│   ├── metadata-checker.yml
│   └── api-response-dump.yml
│
├── tests/
│   └── targets.txt                      # Test file list
│
├── reports/                             # Generated JSON reports
│   ├── api_response_full_*.json
│   └── api_response_compact_*.json
│
├── logs/                                # Future: Log files
├── memory-bank/                         # Project documentation
│   ├── projectbrief.md
│   ├── productContext.md
│   ├── activeContext.md
│   ├── systemPatterns.md
│   ├── techContext.md
│   └── progress.md
│
├── AI_BRIEFING/                         # THIS DOCUMENTATION
│   ├── 01_ARCHITECTURE.md
│   ├── 02_CORE_SYSTEM.md
│   ├── 03_PLUGINS.md
│   ├── 04_API_RESPONSE.md
│   ├── 05_MONGODB_DESIGN.md
│   ├── 06_EXECUTION_FLOW.md
│   └── 07_CODE_REFERENCE.md
│
├── SESSION_TODOLIST.md                  # Phase tracking (Phase 1-6.6 ✅, Phase 7-10 ⏳)
├── MONGODB_STRUCTURE.md                 # MongoDB architecture plan
└── AGENT.MD                             # AI memory bank instructions
```

---

## CORE COMPONENTS (DETAILED)

### 1. Plugin Discovery (`core/plugins/discovery.py`)

**Class:** `PluginDiscovery`

**Purpose:** Scan all plugin.json files, build metadata dict

**Key Method:**
```python
def discover(self) -> Dict[str, Dict[str, Any]]:
    """
    Returns:
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
        ...
    }
    """
    # Scans: src/archiverr/plugins/*/plugin.json
    # Returns: Dict[plugin_name, metadata]
```

**Discovery Logic:**
```python
plugins_dir = Path(__file__).parent.parent / 'plugins'
for plugin_dir in plugins_dir.iterdir():
    if plugin_dir.is_dir():
        manifest = plugin_dir / 'plugin.json'
        if manifest.exists():
            with open(manifest) as f:
                metadata = json.load(f)
                all_plugins[metadata['name']] = metadata
```

---

### 2. Plugin Loader (`core/plugins/loader.py`)

**Class:** `PluginLoader`

**Purpose:** Dynamic import, instantiate plugins

**Constructor:**
```python
def __init__(self, all_plugins: Dict[str, Dict], config: Dict):
    self.all_plugins = all_plugins
    self.config = config
    self.debugger = get_debugger()
```

**Key Methods:**

#### `load_by_category(category: str) -> Dict[str, BasePlugin]`
```python
def load_by_category(self, category: str) -> Dict[str, BasePlugin]:
    """
    Load all enabled plugins of specific category
    
    Args:
        category: 'input' or 'output'
    
    Returns:
        {'scanner': <ScannerPlugin instance>, ...}
    """
    loaded = {}
    for name, metadata in self.all_plugins.items():
        if metadata.get('category') != category:
            continue
        
        # Check if enabled in config
        plugin_config = self.config.get('plugins', {}).get(name, {})
        if not plugin_config.get('enabled', False):
            continue
        
        # Dynamic import
        plugin_instance = self._load_plugin(name, metadata, plugin_config)
        if plugin_instance:
            loaded[name] = plugin_instance
    
    return loaded
```

#### `_load_plugin(name, metadata, config) -> BasePlugin`
```python
def _load_plugin(self, name, metadata, config):
    """
    Dynamic import and instantiation
    
    Steps:
    1. Get class_name from metadata (or derive from name)
    2. Import module: plugins.{name}.client
    3. Get class: getattr(module, class_name)
    4. Instantiate: plugin_class(config)
    """
    # Get class name
    class_name = metadata.get('class_name')
    if not class_name:
        # Convention: scanner -> ScannerPlugin
        parts = name.replace('-', '_').split('_')
        class_name = ''.join(p.capitalize() for p in parts) + 'Plugin'
    
    # Dynamic import
    module_path = f'archiverr.plugins.{name}.client'
    module = importlib.import_module(module_path)
    plugin_class = getattr(module, class_name)
    
    # Instantiate
    return plugin_class(config)
```

**NO HARDCODED MAPPINGS - All dynamic via plugin.json**

---

### 3. Dependency Resolver (`core/plugins/resolver.py`)

**Class:** `DependencyResolver`

**Purpose:** Topological sort for execution order, expects validation

**Constructor:**
```python
def __init__(self, plugin_metadata: Dict[str, Dict]):
    self.plugin_metadata = plugin_metadata
    self.debugger = get_debugger()
```

**Key Methods:**

#### `resolve(enabled_plugins: List[str]) -> List[List[str]]`
```python
def resolve(self, enabled_plugins: List[str]) -> List[List[str]]:
    """
    Topological sort with parallelization
    
    Args:
        enabled_plugins: ['ffprobe', 'renamer', 'tmdb', 'omdb']
    
    Returns:
        [
            ['ffprobe', 'renamer'],  # Group 0: No dependencies, parallel
            ['tmdb', 'omdb']          # Group 1: Depends on renamer, parallel
        ]
    """
    # Kahn's algorithm for topological sort
    # Group plugins with no dependencies -> execute in parallel
```

**Algorithm:**
```python
# Build dependency graph
graph = {p: set(metadata[p]['depends_on']) for p in enabled_plugins}

# Find plugins with no dependencies
execution_groups = []
while graph:
    # Plugins with no remaining dependencies
    ready = [p for p, deps in graph.items() if not deps]
    
    if not ready:
        raise ValueError("Circular dependency detected")
    
    execution_groups.append(ready)
    
    # Remove ready plugins from graph
    for p in ready:
        del graph[p]
    
    # Remove ready plugins from other dependencies
    for deps in graph.values():
        deps -= set(ready)

return execution_groups
```

#### `check_expects(plugin_name: str, available_data: Set[str]) -> bool`
```python
def check_expects(self, plugin_name: str, available_data: Set[str]) -> bool:
    """
    Runtime validation: Check if expected data exists
    
    Args:
        plugin_name: 'tmdb'
        available_data: {'input', 'renamer', 'renamer.parsed', 'ffprobe', 'ffprobe.video'}
    
    Returns:
        True if all expects satisfied, False otherwise
    
    Example:
        plugin.json:
        {
            "expects": ["renamer.parsed"]
        }
        
        available_data = {'input', 'renamer', 'renamer.parsed'}
        -> Returns True
        
        available_data = {'input', 'renamer'}
        -> Returns False (renamer.parsed missing)
    """
    metadata = self.plugin_metadata.get(plugin_name, {})
    expects = metadata.get('expects', [])
    
    for expect in expects:
        if expect not in available_data:
            self.debugger.warn("resolver", f"Plugin {plugin_name} expects '{expect}' but not available")
            return False
    
    return True
```

**Expects vs Depends_on:**
- `depends_on`: Static dependency (execution order only)
- `expects`: Runtime validation (actual data check)

Example:
```json
{
  "depends_on": ["renamer"],     // Must run after renamer
  "expects": ["renamer.parsed"]  // Must have renamer.parsed data
}
```

If renamer runs but fails (no parsed data), tmdb won't execute (expects not satisfied).

---

### 4. Plugin Executor (`core/plugins/executor.py`)

**Class:** `PluginExecutor`

**Purpose:** Execute plugins, manage results

**Key Methods:**

#### `execute_input_plugins(plugins: Dict[str, InputPlugin]) -> List[Dict]`
```python
def execute_input_plugins(self, plugins: Dict[str, InputPlugin]) -> List[Dict]:
    """
    Execute all input plugins, collect matches
    
    Args:
        plugins: {'scanner': <ScannerPlugin>, 'file-reader': <FileReaderPlugin>}
    
    Returns:
        [
            {'input': {'path': '/path/file.mkv', 'virtual': False}},
            {'input': {'path': '/path/file2.mkv', 'virtual': False}}
        ]
    
    Logic:
        - Only ONE input plugin should be enabled (scanner OR file-reader)
        - Executes plugin.execute()
        - Returns list of initial match dicts
    """
    all_matches = []
    
    for plugin_name, plugin_instance in plugins.items():
        self.debugger.debug("executor", f"Executing input plugin: {plugin_name}")
        
        try:
            matches = plugin_instance.execute()
            
            # Format matches
            for match in matches:
                formatted = {
                    'input': match  # Store under 'input' key
                }
                all_matches.append(formatted)
        
        except Exception as e:
            self.debugger.error("executor", f"Input plugin {plugin_name} failed", error=str(e))
    
    return all_matches
```

#### `execute_output_pipeline(plugins, execution_groups, match_data, resolver)`
```python
def execute_output_pipeline(
    self,
    plugins: Dict[str, OutputPlugin],
    execution_groups: List[List[str]],
    match_data: Dict,
    resolver: DependencyResolver
) -> Dict:
    """
    Execute output plugins for single match
    
    Args:
        plugins: {'ffprobe': <FFProbe>, 'renamer': <Renamer>, 'tmdb': <TMDb>}
        execution_groups: [['ffprobe', 'renamer'], ['tmdb', 'omdb']]
        match_data: {'input': {'path': '/path/file.mkv'}}
        resolver: DependencyResolver instance
    
    Returns:
        {
            'input': {...},
            'ffprobe': {video: {...}, audio: [...], container: {...}},
            'renamer': {parsed: {...}, category: 'movie'},
            'tmdb': {movie: {...}, globals: {status: {...}, validation: {...}}}
        }
    
    Logic:
        1. Extract available data keys
        2. For each execution group:
           a. Filter plugins by expects (check_expects)
           b. Execute ready plugins in parallel
           c. Update available data
        3. Handle category propagation (generic pattern)
    """
    result = match_data.copy()
    
    for group in execution_groups:
        # Extract available data
        available_data = self._extract_available_data(result)
        
        # Filter by expects
        ready_plugins = [
            p for p in group 
            if resolver.check_expects(p, available_data)
        ]
        
        pending_plugins = [p for p in group if p not in ready_plugins]
        
        if pending_plugins:
            self.debugger.warn("executor", f"Plugins pending (expects not met): {pending_plugins}")
        
        # Execute ready plugins
        for plugin_name in ready_plugins:
            plugin_instance = plugins[plugin_name]
            
            try:
                plugin_result = plugin_instance.execute(result)
                result[plugin_name] = plugin_result
                
                # GENERIC PATTERN: Category propagation
                # Works with ANY plugin that provides 'category'
                if 'category' in plugin_result and 'input' in result:
                    result['input']['category'] = plugin_result['category']
                    self.debugger.debug("executor", "Updated input category",
                                       plugin=plugin_name, 
                                       category=plugin_result['category'])
            
            except Exception as e:
                self.debugger.error("executor", f"Plugin {plugin_name} failed", error=str(e))
                result[plugin_name] = {'status': {'success': False, 'error': str(e)}}
    
    return result
```

#### `_extract_available_data(result: Dict) -> Set[str]`
```python
def _extract_available_data(self, result: Dict) -> Set[str]:
    """
    Extract available data keys for expects checking
    
    Args:
        result: {
            'input': {'path': '...'},
            'renamer': {'parsed': {...}, 'category': 'movie'},
            'ffprobe': {'video': {...}, 'audio': [...]}
        }
    
    Returns:
        {
            'input',
            'renamer',
            'renamer.parsed',
            'renamer.category',
            'ffprobe',
            'ffprobe.video',
            'ffprobe.audio'
        }
    
    Logic:
        - Top-level keys (excluding 'status', 'index')
        - Nested dict keys (key.subkey)
    """
    available = set()
    
    for key, value in result.items():
        if key in ['status', 'index']:  # Skip metadata
            continue
        
        available.add(key)
        
        if isinstance(value, dict):
            for subkey in value.keys():
                if subkey != 'status':  # Skip status
                    available.add(f"{key}.{subkey}")
    
    return available
```

---

### 5. Response Builder (`models/response_builder.py`)

**Class:** `APIResponseBuilder`

**Purpose:** Build unified API response from matches

**Constructor:**
```python
def __init__(self, config: Dict, start_time: datetime, loaded_plugins: Dict):
    self.config = config
    self.start_time = start_time
    self.loaded_plugins = loaded_plugins  # {'input': {...}, 'output': {...}}
    self.debugger = get_debugger()
```

**Key Method:**
```python
def build(self, matches: List[Dict]) -> Dict:
    """
    Build complete API response
    
    Args:
        matches: [
            {
                'input': {...},
                'ffprobe': {...},
                'renamer': {...},
                'tmdb': {...},
                'globals': {...}  # Added by __main__.py
            },
            ...
        ]
    
    Returns:
        {
            'globals': {
                'status': {...},
                'summary': {...},
                'config': {...}
            },
            'matches': [...]
        }
    """
    end_time = datetime.now()
    
    # Build globals
    globals_obj = {
        'status': self._build_global_status(matches, end_time),
        'summary': self._build_summary(matches),
        'config': {
            'options': self.config.get('options', {}),
            'plugins': self.config.get('plugins', {}),
            'tasks': self.config.get('tasks', [])
        }
    }
    
    # Format matches
    formatted_matches = [self._format_match(m) for m in matches]
    
    return {
        'globals': globals_obj,
        'matches': formatted_matches
    }
```

#### `_build_global_status(matches, end_time)`
```python
def _build_global_status(self, matches, end_time):
    """
    Returns:
    {
        'success': True,
        'matches': 2,
        'errors': 0,
        'started_at': '2025-11-25T16:30:00.123+03:00',
        'finished_at': '2025-11-25T16:30:05.456+03:00',
        'duration_ms': 5333
    }
    """
    errors = sum(1 for m in matches if not m.get('globals', {}).get('status', {}).get('success', False))
    
    return {
        'success': errors == 0,
        'matches': len(matches),
        'errors': errors,
        'started_at': self.start_time.isoformat(),
        'finished_at': end_time.isoformat(),
        'duration_ms': int((end_time - self.start_time).total_seconds() * 1000)
    }
```

#### `_build_summary(matches)`
```python
def _build_summary(self, matches):
    """
    Returns:
    {
        'input_plugin_used': 'scanner',
        'output_plugins_used': ['ffprobe', 'renamer', 'tmdb', 'omdb'],
        'categories': ['movie', 'show'],
        'total_size_bytes': 12345678,
        'total_duration_seconds': 7200
    }
    """
    # Detect input plugin
    input_plugin_used = None
    for plugin_name in self.loaded_plugins.get('input', {}):
        input_plugin_used = plugin_name
        break
    
    # Collect output plugins
    output_plugins_used = list(self.loaded_plugins.get('output', {}).keys())
    
    # Collect categories from plugin.json
    categories = set()
    for plugin_name, metadata in self.loaded_plugins.get('output', {}).items():
        plugin_categories = metadata.get('categories', [])
        categories.update(plugin_categories)
    
    # Aggregate size and duration
    total_size = 0
    total_duration = 0
    for match in matches:
        ffprobe_data = match.get('ffprobe', {})
        if 'container' in ffprobe_data:
            total_size += ffprobe_data['container'].get('size_bytes', 0)
        if 'video' in ffprobe_data:
            total_duration += ffprobe_data['video'].get('duration_seconds', 0)
    
    return {
        'input_plugin_used': input_plugin_used,
        'output_plugins_used': output_plugins_used,
        'categories': sorted(list(categories)),
        'total_size_bytes': total_size,
        'total_duration_seconds': total_duration
    }
```

#### `_format_match(match)`
```python
def _format_match(self, match):
    """
    Convert internal match format to API response format
    
    Input:
    {
        'input': {'path': '...', 'virtual': False, 'category': 'movie'},
        'ffprobe': {...},
        'renamer': {...},
        'tmdb': {...},
        'globals': {
            'index': 0,
            'input_path': '/path/file.mkv',
            'status': {...},
            'output': {'tasks': [...]}
        }
    }
    
    Output:
    {
        'globals': {
            'index': 0,
            'input_path': '/path/file.mkv',
            'status': {...},
            'output': {'tasks': [...]}
        },
        'plugins': {
            'ffprobe': {...},
            'renamer': {...},
            'tmdb': {...}
        }
    }
    """
    # Extract globals (already formatted by __main__.py)
    match_globals = match.get('globals', {})
    
    # Extract plugin results (everything except 'globals' and 'input')
    plugins = {}
    for key, value in match.items():
        if key not in ['globals', 'input']:  # Exclude metadata
            plugins[key] = value
    
    return {
        'globals': match_globals,
        'plugins': plugins
    }
```

---

## PLUGIN.JSON SCHEMA

Every plugin MUST have plugin.json:

```json
{
  "name": "tmdb",
  "version": "1.0.0",
  "category": "output",
  "class_name": "TMDbPlugin",
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed"],
  "categories": ["movie", "show"]
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Plugin identifier (must match folder name) |
| `version` | string | ✅ | Semantic version |
| `category` | string | ✅ | `"input"` or `"output"` |
| `class_name` | string | ❌ | Python class name (default: NamePlugin) |
| `depends_on` | array | ❌ | Static dependencies (execution order) |
| `expects` | array | ❌ | Runtime data validation (data keys) |
| `categories` | array | ❌ | Media categories plugin supports |

**Class Name Convention:**
- If `class_name` present: Use it
- If missing: Derive from name
  - `scanner` → `ScannerPlugin`
  - `file-reader` → `FileReaderPlugin`
  - `mock_test` → `MockTestPlugin`

---

## BASE PLUGIN CLASSES

### `BasePlugin` (`plugins/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class ValidationResult:
    """Plugin validation result"""
    tests_passed: int
    tests_total: int
    details: Dict[str, Any]

class BasePlugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.debugger = get_debugger()
    
    @abstractmethod
    def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute plugin logic"""
        pass
```

### `InputPlugin`

```python
class InputPlugin(BasePlugin):
    """Input plugins return List[Dict]"""
    
    def execute(self, match_data: Dict = None) -> List[Dict]:
        """
        Returns:
            [
                {'path': '/path/file1.mkv', 'virtual': False},
                {'path': '/path/file2.mkv', 'virtual': False}
            ]
        """
        pass
```

### `OutputPlugin`

```python
class OutputPlugin(BasePlugin):
    """Output plugins return Dict"""
    
    def execute(self, match_data: Dict) -> Dict:
        """
        Args:
            match_data: {
                'input': {'path': '...'},
                'renamer': {...},  # If available
                'ffprobe': {...}   # If available
            }
        
        Returns:
            {
                'globals': {
                    'status': {...},
                    'validation': ValidationResult
                },
                'movie': {...},  # Plugin-specific data
                'episode': None
            }
        """
        pass
    
    def _validate_duration(self, actual: int, expected: int, tolerance: int = 600) -> ValidationResult:
        """
        Duration validation helper
        
        Args:
            actual: Actual duration (from ffprobe)
            expected: Expected duration (from API)
            tolerance: Tolerance in seconds (default: 10 minutes)
        
        Returns:
            ValidationResult with pass/fail
        """
        diff = abs(actual - expected)
        passed = diff <= tolerance
        
        return ValidationResult(
            tests_passed=1 if passed else 0,
            tests_total=1,
            details={
                'duration_actual': actual,
                'duration_expected': expected,
                'difference_seconds': diff,
                'tolerance_seconds': tolerance,
                'passed': passed
            }
        )
```

---

## EXECUTION ORDER GUARANTEE

```
Input Phase:
  scanner OR file-reader
  ↓
  [Match 0, Match 1, ...]

Output Phase (per match):
  Group 0 (parallel):
    - ffprobe (expects: ["input"])
    - renamer (expects: ["input"])
  
  Group 1 (parallel):
    - tmdb (expects: ["renamer.parsed"])
    - tvdb (expects: ["renamer.parsed"])
    - tvmaze (expects: ["renamer.parsed"])
    - omdb (expects: ["renamer.parsed"])
  
  Task Execution:
    - Per-match tasks
    - Summary task (last match only)
```

**Parallelization:**
- Plugins in same group execute in parallel (no dependencies between them)
- Expects system ensures data availability before execution
- Groups execute sequentially (Group 1 waits for Group 0)

**Dynamic Skipping:**
- If renamer fails → Group 1 plugins skipped (expects not satisfied)
- If ffprobe fails → tmdb/tvdb/omdb still run (no dependency)

---

## CONFIG.YML STRUCTURE

```yaml
options:
  debug: true                          # Enable debug logging
  dry_run: true                        # Don't write files
  hardlink: true                       # Use hardlinks instead of copy

plugins:
  scanner:
    enabled: true
    targets:
      - /path/to/media
    recursive: false
  
  ffprobe:
    enabled: true
    timeout: 15
  
  renamer:
    enabled: true
    media_type: auto                   # auto, movie, show
  
  tmdb:
    enabled: true
    api_key: "${TMDB_API_KEY}"         # From .env
    language: tr-TR
    include-raw: true                  # Include raw API response
    extras:
      movie_credits: true
      movie_images: true
      movie_keywords: true
      movie_videos: true

tasks:
  - name: print_match_header
    type: print
    template: "========== MATCH {{ index }} =========="
  
  - name: save_nfo
    type: save
    destination: "{{ renamer.parsed.movie.name }}.nfo"
    template: "{{ tmdb.movie | tojson }}"
  
  - name: print_summary
    type: print
    condition: "{{ index: == (count:matches - 1) }}"
    template: "Total: {{ globals.status.matches }}"
  
  - external: true
    name: detailed_check
    path: tasks/metadata-checker.yml
```

**Config Resolution:**
- `${VAR}` → Replaced with environment variable from .env
- Plugin config passed to plugin constructor
- Tasks executed by TaskManager

---

This completes Architecture documentation. All core principles, directory structure, component details, and execution guarantees documented.
