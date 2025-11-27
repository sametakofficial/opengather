# CORE SYSTEM - COMPLETE CODE REFERENCE

## ENTRY POINT: `src/archiverr/__main__.py`

**File:** `/home/samet/Workspace/archiverr/src/archiverr/__main__.py`

**Imports:**
```python
import sys
import yaml
from pathlib import Path
from datetime import datetime

from archiverr.core.plugins import (PluginDiscovery, PluginLoader, DependencyResolver, PluginExecutor)
from archiverr.models import APIResponseBuilder
from archiverr.core.tasks import TemplateManager, TaskManager
from archiverr.core.reports import generate_dual_reports
from archiverr.utils.debug import init_debugger, get_debugger
from archiverr.core.config_validator import ConfigValidator
```

**Function:** `main()`

**Execution Steps (209 lines):**

### Step 1: Initialization (lines 22-42)
```python
start_time = datetime.now()  # Single timestamp for entire execution

# Load config.yml
config_path = Path("config.yml")
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)  # Dict

# Extract options
debug = config.get('options', {}).get('debug', False)
dry_run = config.get('options', {}).get('dry_run', True)

# Initialize debug system (singleton)
debugger = init_debugger(enabled=debug)
```

### Step 2: Config Validation (lines 44-53)
```python
validator = ConfigValidator()
if validator.is_available():  # Check if jsonschema installed
    is_valid, error_msg = validator.validate(config)
    if not is_valid:
        debugger.error("config", "Invalid configuration", error=error_msg)
        sys.exit(1)
```

### Step 3: Plugin Discovery (lines 57-61)
```python
discovery = PluginDiscovery()
all_plugins = discovery.discover()
# Returns: Dict[plugin_name, metadata]
# {'scanner': {...}, 'tmdb': {...}, ...}
```

### Step 4: Plugin Loading (lines 64-68)
```python
loader = PluginLoader(all_plugins, config)
input_plugins = loader.load_by_category('input')   # Dict[name, instance]
output_plugins = loader.load_by_category('output')  # Dict[name, instance]
```

### Step 5: Dependency Resolution (lines 71-82)
```python
resolver = DependencyResolver(all_plugins)
enabled_output = list(output_plugins.keys())  # ['ffprobe', 'renamer', 'tmdb', ...]

execution_groups = resolver.resolve(enabled_output)
# Returns: List[List[str]]
# [['ffprobe', 'renamer'], ['tmdb', 'tvdb', 'omdb']]
```

### Step 6: Input Execution (lines 85-93)
```python
executor = PluginExecutor()
input_matches = executor.execute_input_plugins(input_plugins)
# Returns: List[Dict]
# [{'input': {'path': '/path/file.mkv', 'virtual': False}}, ...]

if not input_matches:
    sys.exit(0)
```

### Step 7: Per-Match Processing (lines 95-149)
```python
processed_matches = []
match_task_results = {}

template_manager = TemplateManager()
task_manager = TaskManager(config, template_manager)
builder = APIResponseBuilder()

for index, match in enumerate(input_matches):
    # Execute output plugins
    result = executor.execute_output_pipeline(
        output_plugins,
        execution_groups,
        match,
        resolver
    )
    # result: {'input': {...}, 'ffprobe': {...}, 'renamer': {...}, 'tmdb': {...}}
    
    processed_matches.append(result)
    
    # Check if all plugins finished
    status = result.get('status', {})
    total_plugins_run = len(status.get('success_plugins', [])) + \
                       len(status.get('failed_plugins', [])) + \
                       len(status.get('not_supported_plugins', []))
    
    if total_plugins_run == len(output_plugins):
        # Build incremental API response
        temp_api_response = builder.build(
            processed_matches,
            config=config,
            start_time=start_time,
            loaded_plugins=all_plugins
        )
        
        # Execute tasks for this match
        task_results = task_manager.execute_tasks_for_match(
            temp_api_response,
            index,
            dry_run
        )
        
        match_task_results[index] = task_results
```

### Step 8: Final API Response (lines 152-189)
```python
api_response = builder.build(
    processed_matches,
    config=config,
    start_time=start_time,
    loaded_plugins=all_plugins
)

# Add task results to match.globals.output.tasks
for match_index, task_results_list in match_task_results.items():
    match = api_response['matches'][match_index]
    match_output = match.get('globals', {}).get('output', {})
    
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

# Update task count in globals
api_response['globals']['status']['tasks'] = len(all_task_results)
```

### Step 9: Report Generation (lines 191-204)
```python
timestamp = start_time.strftime("%Y%m%d_%H%M%S")
report_paths = generate_dual_reports(api_response, timestamp, debugger=debugger)
# Returns: {'full': 'path/to/full.json', 'compact': 'path/to/compact.json', 'debug_log': '...'}
```

---

## DEBUG SYSTEM: `src/archiverr/utils/debug.py`

**Purpose:** Singleton debugger, structured logging

**Imports:**
```python
from datetime import datetime
import sys
from typing import Optional
```

**Global State:**
```python
_debugger_instance: Optional['Debugger'] = None
```

### Class: `Debugger`

**Constructor:**
```python
def __init__(self, enabled: bool = False):
    self.enabled = enabled
    self.start_time = datetime.now()
```

**Methods:**

#### `_log(level: str, component: str, message: str, **kwargs)`
```python
def _log(self, level: str, component: str, message: str, **kwargs):
    """
    Format: TIMESTAMP  LEVEL  COMPONENT  [key=value] message
    
    Example:
    2025-11-26T16:30:00.123+03:00  INFO   tmdb       [id=787] Movie found
    """
    if not self.enabled and level not in ['ERROR', 'WARN']:
        return
    
    timestamp = datetime.now().isoformat()
    
    # Format kwargs
    context = ""
    if kwargs:
        pairs = [f"{k}={v}" for k, v in kwargs.items()]
        context = f"[{' '.join(pairs)}] "
    
    output = f"{timestamp}  {level:6s}  {component:10s}  {context}{message}"
    
    # Write to stderr
    print(output, file=sys.stderr)
```

#### Public Methods
```python
def debug(self, component: str, message: str, **kwargs):
    self._log("DEBUG", component, message, **kwargs)

def info(self, component: str, message: str, **kwargs):
    self._log("INFO", component, message, **kwargs)

def warn(self, component: str, message: str, **kwargs):
    self._log("WARN", component, message, **kwargs)

def error(self, component: str, message: str, **kwargs):
    self._log("ERROR", component, message, **kwargs)
```

### Functions:

#### `init_debugger(enabled: bool) -> Debugger`
```python
def init_debugger(enabled: bool = False) -> Debugger:
    """Initialize singleton debugger"""
    global _debugger_instance
    _debugger_instance = Debugger(enabled=enabled)
    return _debugger_instance
```

#### `get_debugger() -> Debugger`
```python
def get_debugger() -> Debugger:
    """Get debugger instance (returns dummy if not initialized)"""
    global _debugger_instance
    if _debugger_instance is None:
        _debugger_instance = Debugger(enabled=False)
    return _debugger_instance
```

**Usage Pattern (Every Component):**
```python
from archiverr.utils.debug import get_debugger

class MyClass:
    def __init__(self):
        self.debugger = get_debugger()
    
    def process(self):
        self.debugger.debug("component", "Starting", param=value)
        # ... work ...
        self.debugger.info("component", "Complete", result=data)
```

---

## CONFIG VALIDATOR: `src/archiverr/core/config_validator.py`

**File:** `/home/samet/Workspace/archiverr/src/archiverr/core/config_validator.py`

**Purpose:** JSON Schema validation for config.yml

**Imports:**
```python
from pathlib import Path
import json
from typing import Tuple, Dict, Any

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
```

### Class: `ConfigValidator`

**Constructor:**
```python
def __init__(self, schema_path: Path = None):
    if schema_path is None:
        # Default: config.schema.json in project root
        schema_path = Path(__file__).parent.parent.parent.parent / 'config.schema.json'
    
    self.schema_path = schema_path
    self.schema = None
    
    if JSONSCHEMA_AVAILABLE and self.schema_path.exists():
        with open(self.schema_path) as f:
            self.schema = json.load(f)
```

**Methods:**

#### `is_available() -> bool`
```python
def is_available(self) -> bool:
    """Check if validation is available"""
    return JSONSCHEMA_AVAILABLE and self.schema is not None
```

#### `validate(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]`
```python
def validate(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate config against schema
    
    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """
    if not self.is_available():
        return (True, None)  # Skip if unavailable
    
    try:
        validate(instance=config, schema=self.schema)
        return (True, None)
    except ValidationError as e:
        return (False, str(e))
```

**Schema Structure (`config.schema.json`):**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["options", "plugins", "tasks"],
  "properties": {
    "options": {
      "type": "object",
      "properties": {
        "debug": {"type": "boolean"},
        "dry_run": {"type": "boolean"},
        "hardlink": {"type": "boolean"}
      }
    },
    "plugins": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "enabled": {"type": "boolean"}
        }
      }
    },
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type"],
        "properties": {
          "name": {"type": "string"},
          "type": {"enum": ["print", "save"]},
          "template": {"type": "string"},
          "destination": {"type": "string"},
          "condition": {"type": "string"},
          "external": {"type": "boolean"},
          "path": {"type": "string"}
        }
      }
    }
  }
}
```

---

## TEMPLATE MANAGER: `src/archiverr/core/tasks/template_manager.py`

**Purpose:** Jinja2 template rendering, variable resolution

**Imports:**
```python
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError
from typing import Dict, Any, Optional
from archiverr.utils.debug import get_debugger
from archiverr.utils.filters import register_filters
```

### Class: `TemplateManager`

**Constructor:**
```python
def __init__(self):
    self.debugger = get_debugger()
    
    # Create Jinja2 environment
    self.env = Environment(loader=BaseLoader())
    
    # Register custom filters
    register_filters(self.env)
    
    # Variable syntax: $ instead of {{}}
    self.env.variable_start_string = '${'
    self.env.variable_end_string = '}'
```

**Methods:**

#### `render(template_str: str, context: Dict[str, Any]) -> Tuple[bool, str]`
```python
def render(self, template_str: str, context: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Render Jinja2 template
    
    Args:
        template_str: Template string with ${var} syntax
        context: Variable context
    
    Returns:
        (True, rendered_output) if success
        (False, error_message) if failed
    
    Example:
        template = "Movie: ${tmdb.movie.title} (${tmdb.movie.release_date | year})"
        context = {'tmdb': {'movie': {'title': 'Movie', 'release_date': '2025-01-01'}}}
        -> (True, "Movie: Movie (2025)")
    """
    try:
        template = self.env.from_string(template_str)
        rendered = template.render(context)
        return (True, rendered)
    
    except TemplateSyntaxError as e:
        error_msg = f"Template syntax error: {e}"
        self.debugger.error("template", error_msg)
        return (False, error_msg)
    
    except UndefinedError as e:
        error_msg = f"Undefined variable: {e}"
        self.debugger.error("template", error_msg)
        return (False, error_msg)
    
    except Exception as e:
        error_msg = f"Template rendering failed: {e}"
        self.debugger.error("template", error_msg)
        return (False, error_msg)
```

#### `build_context(api_response: Dict, match_index: int) -> Dict[str, Any]`
```python
def build_context(self, api_response: Dict, match_index: int) -> Dict[str, Any]:
    """
    Build Jinja2 context for template rendering
    
    Args:
        api_response: Full API response
        match_index: Current match index
    
    Returns:
        {
            'globals': api_response['globals'],              # API-level globals
            'matches': api_response['matches'],              # All matches
            'index': match_index,                            # Current index
            'tmdb': match['plugins']['tmdb'],                # Plugin data (if exists)
            'ffprobe': match['plugins']['ffprobe'],
            ...
            # Special access patterns:
            '0': matches[0],                                 # Index access
            '1': matches[1]
        }
    
    Variable Resolution Examples:
        ${globals.status.matches}           -> API-level globals
        ${index}                            -> Current match index (0, 1, 2)
        ${tmdb.movie.title}                 -> Current match plugin data
        ${0.plugins.tmdb.movie.title}       -> Match 0 plugin data
        ${globals.config.options.debug}     -> Config snapshot
    """
    match = api_response['matches'][match_index]
    
    context = {
        'globals': api_response['globals'],
        'matches': api_response['matches'],
        'index': match_index
    }
    
    # Add current match plugin data (top-level access)
    for plugin_name, plugin_data in match.get('plugins', {}).items():
        context[plugin_name] = plugin_data
    
    # Add indexed match access
    for i, m in enumerate(api_response['matches']):
        context[str(i)] = m
    
    return context
```

---

## TASK MANAGER: `src/archiverr/core/tasks/task_manager.py`

**Purpose:** Task execution (print, save)

**Imports:**
```python
from typing import Dict, Any, List
from pathlib import Path
import shutil
from archiverr.utils.debug import get_debugger
```

### Class: `TaskManager`

**Constructor:**
```python
def __init__(self, config: Dict, template_manager: TemplateManager):
    self.config = config
    self.template_manager = template_manager
    self.debugger = get_debugger()
```

**Methods:**

#### `execute_tasks_for_match(api_response, match_index, dry_run) -> List[Dict]`
```python
def execute_tasks_for_match(
    self,
    api_response: Dict,
    match_index: int,
    dry_run: bool
) -> List[Dict]:
    """
    Execute all tasks for specific match
    
    Args:
        api_response: Full API response
        match_index: Match index (0, 1, 2, ...)
        dry_run: If True, don't write files
    
    Returns:
        [
            {
                'task_name': 'print_match_header',
                'type': 'print',
                'success': True,
                'output': 'Rendered text'
            },
            {
                'task_name': 'save_nfo',
                'type': 'save',
                'success': True,
                'destination': '/path/file.nfo'
            }
        ]
    """
    tasks = self.config.get('tasks', [])
    task_results = []
    
    # Build context for this match
    context = self.template_manager.build_context(api_response, match_index)
    
    for task in tasks:
        # Check condition (if any)
        if not self._check_condition(task, context):
            continue
        
        # Execute task based on type
        if task.get('external'):
            result = self._execute_external_task(task, context, dry_run)
        elif task['type'] == 'print':
            result = self._execute_print_task(task, context)
        elif task['type'] == 'save':
            result = self._execute_save_task(task, context, dry_run)
        else:
            result = {
                'task_name': task.get('name', 'unknown'),
                'type': task['type'],
                'success': False,
                'error': f"Unknown task type: {task['type']}"
            }
        
        task_results.append(result)
    
    return task_results
```

#### `_check_condition(task, context) -> bool`
```python
def _check_condition(self, task: Dict, context: Dict) -> bool:
    """
    Check task condition
    
    Args:
        task: {'condition': '{{ index: == (count:matches - 1) }}'}
        context: Jinja2 context
    
    Returns:
        True if condition met (or no condition), False otherwise
    
    Examples:
        condition: '{{ index: == 0 }}'           -> Run on first match
        condition: '{{ index: == (count:matches - 1) }}'  -> Run on last match
        condition: '{{ tmdb.movie }}'            -> Run if tmdb.movie exists
    """
    if 'condition' not in task:
        return True
    
    condition = task['condition']
    
    # Render condition as template
    success, result = self.template_manager.render(condition, context)
    
    if not success:
        return False
    
    # Check result (truthy/falsy)
    result = result.strip()
    return result.lower() not in ['false', '0', '', 'none']
```

#### `_execute_print_task(task, context) -> Dict`
```python
def _execute_print_task(self, task: Dict, context: Dict) -> Dict:
    """
    Execute print task
    
    Args:
        task: {'name': 'print_header', 'type': 'print', 'template': '...'}
        context: Jinja2 context
    
    Returns:
        {
            'task_name': 'print_header',
            'type': 'print',
            'success': True,
            'output': 'Rendered text'
        }
    
    Side Effect:
        Prints to stdout
    """
    template = task.get('template', '')
    
    success, rendered = self.template_manager.render(template, context)
    
    if success:
        print(rendered)  # Print to stdout
    
    return {
        'task_name': task.get('name', 'unnamed'),
        'type': 'print',
        'success': success,
        'output': rendered if success else f"Error: {rendered}"
    }
```

#### `_execute_save_task(task, context, dry_run) -> Dict`
```python
def _execute_save_task(self, task: Dict, context: Dict, dry_run: bool) -> Dict:
    """
    Execute save task
    
    Args:
        task: {
            'name': 'save_nfo',
            'type': 'save',
            'destination': '/path/${tmdb.movie.title}.nfo',
            'template': '${tmdb.movie | tojson}'
        }
        context: Jinja2 context
        dry_run: If True, don't actually write
    
    Returns:
        {
            'task_name': 'save_nfo',
            'type': 'save',
            'success': True,
            'destination': '/path/Movie.nfo'
        }
    
    Logic:
        1. Render destination path
        2. Render template content
        3. Write to file (if not dry_run)
    """
    # Render destination
    dest_template = task.get('destination', '')
    success_dest, destination = self.template_manager.render(dest_template, context)
    
    if not success_dest:
        return {
            'task_name': task.get('name', 'unnamed'),
            'type': 'save',
            'success': False,
            'error': f"Destination render failed: {destination}"
        }
    
    # Render content
    content_template = task.get('template', '')
    success_content, content = self.template_manager.render(content_template, context)
    
    if not success_content:
        return {
            'task_name': task.get('name', 'unnamed'),
            'type': 'save',
            'success': False,
            'error': f"Content render failed: {content}"
        }
    
    # Write file
    if not dry_run:
        try:
            dest_path = Path(destination)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.debugger.debug("task", f"File saved: {destination}")
        
        except Exception as e:
            return {
                'task_name': task.get('name', 'unnamed'),
                'type': 'save',
                'success': False,
                'error': str(e)
            }
    else:
        self.debugger.debug("task", f"Dry-run: Would save to {destination}")
    
    return {
        'task_name': task.get('name', 'unnamed'),
        'type': 'save',
        'success': True,
        'destination': destination,
        'dry_run': dry_run
    }
```

#### `_execute_external_task(task, context, dry_run) -> Dict`
```python
def _execute_external_task(self, task: Dict, context: Dict, dry_run: bool) -> Dict:
    """
    Execute external task (load YAML and execute)
    
    Args:
        task: {
            'external': True,
            'name': 'detailed_check',
            'path': 'tasks/metadata-checker.yml'
        }
    
    Returns:
        Task result dict
    
    Logic:
        1. Load external YAML file
        2. Treat as inline task
        3. Execute based on type
    """
    import yaml
    
    task_path = Path(task.get('path', ''))
    
    if not task_path.exists():
        return {
            'task_name': task.get('name', 'unnamed'),
            'type': 'external',
            'success': False,
            'error': f"Task file not found: {task_path}"
        }
    
    try:
        with open(task_path, 'r', encoding='utf-8') as f:
            external_task = yaml.safe_load(f)
        
        # Preserve name from config
        external_task['name'] = task.get('name', external_task.get('name', 'unnamed'))
        
        # Execute based on type
        if external_task['type'] == 'print':
            return self._execute_print_task(external_task, context)
        elif external_task['type'] == 'save':
            return self._execute_save_task(external_task, context, dry_run)
        else:
            return {
                'task_name': external_task.get('name'),
                'type': 'external',
                'success': False,
                'error': f"Unknown external task type: {external_task['type']}"
            }
    
    except Exception as e:
        return {
            'task_name': task.get('name', 'unnamed'),
            'type': 'external',
            'success': False,
            'error': str(e)
        }
```

---

## JINJA2 FILTERS: `src/archiverr/utils/filters.py`

**Purpose:** Custom Jinja2 filters

**Function:** `register_filters(env: Environment)`

```python
def register_filters(env):
    """Register custom Jinja2 filters"""
    
    @env.filter
    def year(date_str):
        """Extract year from date string"""
        # "2025-11-26" -> "2025"
        if not date_str:
            return ''
        return date_str.split('-')[0]
    
    @env.filter
    def pad(value, width):
        """Pad number with zeros"""
        # pad(5, 2) -> "05"
        return str(value).zfill(int(width))
    
    @env.filter
    def human_size(bytes):
        """Convert bytes to human readable"""
        # 1536 -> "1.5 KB"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} PB"
    
    @env.filter
    def tojson(obj):
        """Convert to JSON string"""
        import json
        return json.dumps(obj, indent=2, ensure_ascii=False)
```

**Usage:**
```jinja2
${tmdb.movie.release_date | year}        -> "2025"
${renamer.parsed.show.season | pad(2)}   -> "05"
${ffprobe.container.size_bytes | human_size}  -> "1.5 GB"
${tmdb.movie | tojson}                   -> JSON string
```

---

## RESPONSE SIMPLIFIER: `src/archiverr/core/reports/response_simplifier.py`

**Purpose:** Type-based structural simplification

**Imports:**
```python
from typing import Any, Dict, List
from archiverr.utils.debug import get_debugger
```

### Class: `ResponseSimplifier`

**Constructor:**
```python
def __init__(self):
    self.debugger = get_debugger()
```

**Methods:**

#### `simplify(data: Any) -> Any`
```python
def simplify(self, data: Any) -> Any:
    """
    Recursively simplify data structure
    
    Strategy:
        - Keep scalars (str, int, float, bool, None) as-is
        - Simplify dicts recursively
        - Simplify lists (keep 1 example per type)
    
    Examples:
        101 cast members -> 1 example
        16 keywords -> 1 example
        File size: 145 KB -> 9 KB (94% reduction)
    """
    if isinstance(data, dict):
        return self._simplify_dict(data)
    elif isinstance(data, list):
        return self._simplify_list(data)
    else:
        return data  # Scalar
```

#### `_simplify_dict(data: Dict) -> Dict`
```python
def _simplify_dict(self, data: Dict) -> Dict:
    """
    Simplify dict recursively
    
    Logic:
        - Keep all keys
        - Simplify each value
    """
    return {k: self.simplify(v) for k, v in data.items()}
```

#### `_simplify_list(data: List) -> List`
```python
def _simplify_list(self, data: List) -> List:
    """
    Simplify list - keep 1 example per type
    
    Logic:
        1. Identify unique types in list
        2. Keep first example of each type
        3. Simplify examples recursively
    
    Examples:
        [
            {'id': 1, 'name': 'Actor 1'},
            {'id': 2, 'name': 'Actor 2'},
            ...
        ]
        -> [{'id': 1, 'name': 'Actor 1'}]  # Keep 1 object example
        
        ['action', 'drama', 'thriller']
        -> ['action']  # Keep 1 string example
    """
    if not data:
        return data
    
    seen_types = set()
    examples = []
    
    for item in data:
        # Determine type
        if isinstance(item, dict):
            item_type = "object"
        else:
            item_type = type(item).__name__
        
        # Keep first example of each type
        if item_type not in seen_types:
            seen_types.add(item_type)
            examples.append(self.simplify(item))
    
    return examples
```

---

## REPORT GENERATOR: `src/archiverr/core/reports/report_generator.py`

**Purpose:** Generate dual reports (full + compact)

**Imports:**
```python
import json
from pathlib import Path
from typing import Dict
from archiverr.core.reports.response_simplifier import ResponseSimplifier
```

**Function:** `generate_dual_reports(api_response, timestamp, debugger)`

```python
def generate_dual_reports(
    api_response: Dict,
    timestamp: str,
    debugger
) -> Dict[str, str]:
    """
    Generate full + compact JSON reports
    
    Args:
        api_response: Complete API response
        timestamp: "20251126_163000"
        debugger: Debugger instance
    
    Returns:
        {
            'full': 'reports/api_response_full_20251126_163000.json',
            'compact': 'reports/api_response_compact_20251126_163000.json',
            'debug_log': 'logs/debug_20251126_163000.log' (if debug enabled)
        }
    
    Files:
        - Full: Complete API response (all data)
        - Compact: Simplified structure (1 example per type)
    """
    reports_dir = Path('reports')
    reports_dir.mkdir(exist_ok=True)
    
    # Full report
    full_path = reports_dir / f'api_response_full_{timestamp}.json'
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(api_response, f, indent=2, ensure_ascii=False)
    
    debugger.debug("reports", f"Full report saved: {full_path}")
    
    # Compact report
    simplifier = ResponseSimplifier()
    compact_response = simplifier.simplify(api_response)
    
    compact_path = reports_dir / f'api_response_compact_{timestamp}.json'
    with open(compact_path, 'w', encoding='utf-8') as f:
        json.dump(compact_response, f, indent=2, ensure_ascii=False)
    
    debugger.debug("reports", f"Compact report saved: {compact_path}")
    
    return {
        'full': str(full_path),
        'compact': str(compact_path)
    }
```

---

## DEPENDENCIES (`requirements.txt`)

```
# Core
pyyaml>=6.0.1,<7.0.0                # YAML parsing
pydantic>=2.0.0,<3.0.0              # Data validation (future)

# HTTP
requests>=2.31.0,<3.0.0             # HTTP client

# Template
Jinja2>=3.1.0,<4.0.0                # Template engine

# Validation (optional)
jsonschema>=4.0.0,<5.0.0            # JSON Schema validation

# MongoDB (future - Phase 7)
# pymongo>=4.6.0,<5.0.0
# motor>=3.3.0,<4.0.0
# beanie>=1.23.0,<2.0.0

# Testing (future)
# pytest>=7.0.0
# pytest-asyncio>=0.21.0
```

---

## EXECUTION PHASES (DETAILED)

```
Phase 1: Plugin Discovery
  ├─ Scan plugins/*/plugin.json
  ├─ Build metadata dict
  └─ Time: <10ms

Phase 2: Plugin Loading
  ├─ Filter by category (input/output)
  ├─ Check enabled in config
  ├─ Dynamic import
  └─ Time: <50ms

Phase 3: Dependency Resolution
  ├─ Build dependency graph
  ├─ Topological sort (Kahn's algorithm)
  ├─ Group by parallel execution
  └─ Time: <5ms

Phase 4: Input Execution
  ├─ Execute scanner OR file-reader
  ├─ Collect matches
  └─ Time: 10-100ms (depends on file count)

Phase 5: Per-Match Processing (LOOP)
  For each match:
    ├─ Phase 5.1: Output Execution
    │   ├─ Extract available data
    │   ├─ For each execution group:
    │   │   ├─ Filter by expects
    │   │   ├─ Execute ready plugins (parallel)
    │   │   └─ Update available data
    │   └─ Time: 1-3s per match (API calls)
    │
    ├─ Phase 5.2: Task Execution
    │   ├─ Build incremental API response
    │   ├─ Build Jinja2 context
    │   ├─ For each task:
    │   │   ├─ Check condition
    │   │   ├─ Render template
    │   │   └─ Execute (print/save)
    │   └─ Time: 10-50ms per match
    │
    └─ Store results

Phase 6: Final API Response
  ├─ Build complete response
  ├─ Add task results to matches
  ├─ Calculate globals
  └─ Time: <10ms

Phase 7: Report Generation
  ├─ Generate full JSON
  ├─ Generate compact JSON
  └─ Time: 50-200ms (depends on size)

Total Time: 2-10s (depends on match count and API calls)
```

---

## ERROR HANDLING PATTERNS

### Plugin Execution
```python
try:
    result = plugin_instance.execute(match_data)
except Exception as e:
    self.debugger.error("executor", f"Plugin {plugin_name} failed", error=str(e))
    result = {
        'status': {
            'success': False,
            'error': str(e)
        }
    }
```

### Template Rendering
```python
try:
    template = self.env.from_string(template_str)
    rendered = template.render(context)
    return (True, rendered)
except TemplateSyntaxError as e:
    return (False, f"Syntax error: {e}")
except UndefinedError as e:
    return (False, f"Undefined variable: {e}")
```

### File Operations
```python
try:
    with open(path, 'w') as f:
        f.write(content)
except PermissionError:
    return {'success': False, 'error': 'Permission denied'}
except OSError as e:
    return {'success': False, 'error': str(e)}
```

---

## STATE MANAGEMENT

**Single Timestamp:**
```python
start_time = datetime.now()  # ONE timestamp for entire execution
# Used in all status objects
```

**Match State Tracking:**
```python
processed_matches = []         # List[Dict] - Accumulates results
match_task_results = {}        # Dict[int, List] - Task results per match
```

**Incremental API Response:**
```python
# Built DURING execution for task context
temp_api_response = builder.build(processed_matches, config, start_time, all_plugins)

# Used for template rendering
context = template_manager.build_context(temp_api_response, match_index)
```

**Final API Response:**
```python
# Built AFTER all matches processed
api_response = builder.build(processed_matches, config, start_time, all_plugins)

# Enhanced with task results
for match_index, task_results in match_task_results.items():
    api_response['matches'][match_index]['globals']['output']['tasks'] = formatted_tasks
```

---

This completes Core System documentation. All files, functions, logic flows, and state management patterns documented.
