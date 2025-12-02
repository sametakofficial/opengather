# SESSION 8 STRATEGY

```yaml
date: 2025-11-27
type: strategy
status: ready_for_execution
previous_session: 7
```

---

## EXECUTIVE SUMMARY

Session 7 created SDK components but failed to integrate them. The "SDK" was incorrectly placed as a plugin subfolder and no actual plugins use the SDK classes. This session focuses on proper integration using industry-standard patterns.

### Session 7 Incomplete Items

| Item | Status | Issue |
|------|--------|-------|
| EventBus DI Refactor | Partial | Done but untested |
| Plugin SDK Structure | Created | NOT INTEGRATED - plugins don't use it |
| Subprocess Removal | Structure only | Workers created but not wired to API |

### Critical Problems Found

1. **SDK Not Integrated**: `plugins/sdk/` exists but zero plugins use `PluginManifest`, `PluginResult`, or `ExecutionContext`
2. **SDK Wrong Location**: SDK is infrastructure, not a plugin. Should not be under `plugins/`
3. **Duplicate Base Classes**: `plugins/base.py` and `plugins/sdk/base.py` are nearly identical
4. **Inconsistent Inheritance**: ScannerPlugin, RenamerPlugin, FFProbePlugin don't inherit from base classes
5. **No Manifest Validation**: `PluginDiscovery` loads JSON but doesn't validate with Pydantic
6. **Workers Not Wired**: Task queue ready but API still uses subprocess
7. **No Per-Plugin Task Emission**: Tasks execute only after ALL plugins finish; plugins cannot emit tasks individually
8. **ExecutionContext Not Passed**: Plugins don't receive ExecutionContext, can't use `emit_progress()` or events

---

## INDUSTRY RESEARCH SUMMARY

### Pattern Analysis

| System | Discovery | Validation | Lifecycle | Best For |
|--------|-----------|------------|-----------|----------|
| **Stevedore** | Entry points | Runtime | None | pip-distributed plugins |
| **Pluggy** | Register | Hook specs | Hook calls | Extensibility hooks |
| **MkDocs** | Entry points | config_scheme | Event hooks | Build pipelines |
| **Home Assistant** | manifest.json | JSON Schema | Setup/unload | Device integrations |
| **Stremio SDK** | manifest.json | Schema | defineHandler | Media addons |

### Recommended Pattern for Archiverr

**Hybrid: MkDocs + Home Assistant**

- **From MkDocs**: BasePlugin class with config validation, lifecycle events
- **From Home Assistant**: manifest.json per plugin, strict typing, setup/teardown
- **From Pluggy**: Hook specifications for extensibility points

### Key Principles

1. **Manifest-Driven**: All plugin metadata in plugin.json (validated at load time)
2. **Base Class Required**: All plugins MUST inherit from InputPlugin or OutputPlugin
3. **Result Standardization**: All plugins return PluginResult (not raw dicts)
4. **Lifecycle Hooks**: setup(), execute(), teardown() methods
5. **Schema Validation**: Pydantic validates both manifest and plugin config

---

## ARCHITECTURE DECISIONS

### Decision 1: SDK Location

**MOVE** `plugins/sdk/` to `core/plugin_sdk/`

```
BEFORE: src/archiverr/plugins/sdk/
AFTER:  src/archiverr/core/plugin_sdk/
```

**Rationale**: SDK is core infrastructure, not a plugin. Prevents confusion and aligns with architecture principles.

### Decision 2: Mandatory Base Class Inheritance

All plugins MUST inherit from SDK base classes:

```python
# Input plugins
from archiverr.core.plugin_sdk import InputPlugin

class ScannerPlugin(InputPlugin):
    def execute(self) -> List[PluginResult]: ...

# Output plugins
from archiverr.core.plugin_sdk import OutputPlugin

class TMDbPlugin(OutputPlugin):
    def execute(self, match_data: Dict) -> PluginResult: ...
```

### Decision 3: Remove Duplicate base.py

**DELETE** `plugins/base.py` after migration. Only SDK base classes should exist.

### Decision 4: Manifest Validation at Discovery

```python
# core/plugins/discovery.py
from archiverr.core.plugin_sdk import PluginManifest
from pydantic import ValidationError

def _load_plugin_metadata(self, plugin_dir: Path):
    data = json.load(plugin_json)
    manifest = PluginManifest(**data)  # Validates with Pydantic
    return manifest.model_dump()
```

### Decision 5: Standardized Result Format

All plugin execute() methods return PluginResult:

```python
from archiverr.core.plugin_sdk import PluginResult
from datetime import datetime

def execute(self, match_data):
    start = datetime.now()
    # ... plugin logic ...
    return PluginResult(
        success=True,
        data={"movie": {...}},
        started_at=start,
        finished_at=datetime.now()
    )
```

### Decision 6: Per-Plugin Task Emission (NEW)

**Problem**: Currently tasks execute only after ALL plugins finish for a match. Plugins cannot emit tasks during their execution.

**Solution**: Add `emit_task()` method to `ExecutionContext`:

```python
# core/plugin_sdk/context.py
@dataclass
class ExecutionContext:
    # ... existing fields ...
    task_manager: Optional['TaskManager'] = None
    api_response: Optional[Dict[str, Any]] = None
    
    def emit_task(self, task_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Emit a task for immediate execution.
        
        Allows plugins to trigger tasks at their own pace instead of 
        waiting for all plugins to complete.
        
        Args:
            task_config: Task configuration (same format as config.yml tasks)
                - type: "print" | "save"
                - template: Jinja2 template string
                - destination: For save tasks
                - condition: Optional condition
        
        Returns:
            Task result dict or None if task_manager not available
        
        Example:
            context.emit_task({
                "type": "print",
                "template": "Found movie: {{ tmdb.movie.title }}"
            })
        """
        if self.task_manager and self.api_response:
            return self.task_manager._execute_task(
                task_config, 
                self.api_response, 
                self.match_index,
                self.dry_run
            )
        return None
```

**Changes Required**:

1. **ExecutionContext**: Add `task_manager` and `api_response` fields, add `emit_task()` method
2. **PluginExecutor**: Pass `ExecutionContext` to plugins during execution
3. **__main__.py**: Create and pass context to executor

### Decision 7: ExecutionContext Integration (NEW)

**Problem**: `ExecutionContext` exists in SDK but is never passed to plugins. Plugins can't use events or progress.

**Solution**: Update executor to create and pass context:

```python
# core/plugins/executor.py
from archiverr.core.plugin_sdk import ExecutionContext

async def run_plugin(plugin_name: str):
    plugin = plugins.get(plugin_name)
    
    # Create context for this plugin execution
    context = ExecutionContext(
        execution_id=execution_id,
        match_index=current_index,
        total_matches=total_matches,
        config=config,
        dry_run=dry_run,
        debug=debug,
        debugger=debugger,
        event_bus=event_bus,
        previous_results=match_data,
        task_manager=task_manager,  # NEW
        api_response=api_response   # NEW
    )
    
    # Pass context to plugin
    if hasattr(plugin, 'set_context'):
        plugin.set_context(context)
    
    result = await asyncio.to_thread(plugin.execute, match_data)
```

---

## IMPLEMENTATION PLAN

### Phase 1: SDK Relocation (BLOCKING)

**Goal**: Move SDK to correct location and update imports

**Files to Modify**:
```
1. MOVE: plugins/sdk/* -> core/plugin_sdk/*
2. UPDATE: core/plugin_sdk/__init__.py (fix imports)
3. DELETE: plugins/sdk/ (empty folder)
4. UPDATE: Any file importing from plugins.sdk
```

**Verification**:
```bash
python -c "from archiverr.core.plugin_sdk import PluginManifest, PluginResult, BasePlugin"
```

### Phase 2: Discovery Integration (BLOCKING)

**Goal**: Validate manifests with Pydantic at discovery time

**File**: `core/plugins/discovery.py`

**Changes**:
```python
from archiverr.core.plugin_sdk import PluginManifest

def _load_plugin_metadata(self, plugin_dir: Path):
    # Load JSON/YAML
    data = self._read_manifest_file(plugin_dir)
    
    # Validate with Pydantic
    try:
        manifest = PluginManifest(**data)
        validated = manifest.model_dump()
        validated['_path'] = str(plugin_dir)
        validated['_validated'] = True
        return validated
    except ValidationError as e:
        self.debugger.error("discovery", "Invalid manifest", 
                          dir=plugin_dir.name, errors=str(e))
        return None
```

**Verification**:
```bash
python -c "from archiverr.core.plugins import PluginDiscovery; d = PluginDiscovery(); print(d.discover())"
```

### Phase 3: Plugin Migration (5 plugins)

**Goal**: Update active plugins to use SDK properly

**Order** (by dependency):
1. scanner (input, no deps)
2. file_reader (input, no deps) - if exists
3. renamer (output, depends on input)
4. ffprobe (output, depends on input)
5. tmdb (output, depends on renamer)

**Per-Plugin Changes**:

```python
# BEFORE (scanner/client.py)
class ScannerPlugin:
    def __init__(self, config):
        self.config = config
        self.name = "scanner"
        self.category = "input"

# AFTER
from archiverr.core.plugin_sdk import InputPlugin, PluginResult
from datetime import datetime

class ScannerPlugin(InputPlugin):
    def execute(self) -> List[Dict[str, Any]]:
        # Returns list of matches (input plugin pattern)
        ...
```

```python
# BEFORE (tmdb/client.py)
from archiverr.plugins.base import OutputPlugin

class TMDbPlugin(OutputPlugin):
    def execute(self, match_data):
        return {'status': {...}, 'movie': {...}}

# AFTER
from archiverr.core.plugin_sdk import OutputPlugin, PluginResult
from datetime import datetime

class TMDbPlugin(OutputPlugin):
    def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        start = datetime.now()
        # ... logic ...
        # Can still return dict, PluginResult is optional for gradual migration
        return {
            'status': PluginResult(
                success=True,
                data={...},
                started_at=start,
                finished_at=datetime.now()
            ).to_status_dict(),
            'movie': {...}
        }
```

### Phase 4: Delete Duplicate base.py

**Goal**: Remove `plugins/base.py` after all plugins migrated

**Verification**:
```bash
grep -r "from archiverr.plugins.base" src/
# Should return nothing
```

### Phase 5: Loader Integration

**Goal**: Loader uses manifest data properly

**File**: `core/plugins/loader.py`

**Changes**:
```python
def load_plugin(self, plugin_name: str):
    metadata = self.plugin_metadata.get(plugin_name)
    
    # Use class_name from validated manifest
    class_name = metadata.get('class_name')
    if not class_name:
        # Fallback: Convention-based naming
        class_name = ''.join(p.capitalize() for p in plugin_name.split('_')) + 'Plugin'
    
    # Instantiate and set metadata
    instance = plugin_class(plugin_config)
    instance._metadata = metadata
    instance.name = metadata['name']
    instance.category = metadata['category']
    
    return instance
```

### Phase 6: ExecutionContext Integration (NEW)

**Goal**: Pass ExecutionContext to plugins, enable `emit_task()` and `emit_progress()`

**Files to Modify**:

1. **`core/plugin_sdk/context.py`**:
```python
# Add new fields
task_manager: Optional[Any] = None
api_response: Optional[Dict[str, Any]] = None

# Add emit_task method
def emit_task(self, task_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Emit task for immediate execution"""
    if self.task_manager and self.api_response:
        return self.task_manager._execute_task(
            task_config, self.api_response, self.match_index, self.dry_run
        )
    return None
```

2. **`core/plugin_sdk/base.py`**:
```python
class BasePlugin(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._context: Optional[ExecutionContext] = None
    
    def set_context(self, context: ExecutionContext):
        """Set execution context (called by executor)"""
        self._context = context
    
    @property
    def context(self) -> Optional[ExecutionContext]:
        """Get current execution context"""
        return self._context
    
    def emit_task(self, task_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convenience method for task emission"""
        if self._context:
            return self._context.emit_task(task_config)
        return None
```

3. **`core/plugins/executor.py`**:
```python
# In execute_group_async, create and pass context
from archiverr.core.plugin_sdk import ExecutionContext

context = ExecutionContext(
    execution_id=execution_id,
    match_index=current_index,
    total_matches=total_matches,
    dry_run=dry_run,
    debugger=debugger,
    event_bus=event_bus,
    previous_results=match_data,
    task_manager=task_manager,
    api_response=api_response
)

if hasattr(plugin, 'set_context'):
    plugin.set_context(context)
```

4. **`__main__.py`**:
```python
# Pass task_manager to executor
executor.task_manager = task_manager
executor.api_response_builder = builder
```

**Verification**:
```python
# Test plugin can emit tasks
class TestPlugin(OutputPlugin):
    def execute(self, match_data):
        # Emit task during execution
        self.emit_task({
            "type": "print",
            "template": "Plugin processing: {{ input_path }}"
        })
        return {...}
```

---

## SCOPE LIMITATION

### Active Plugins (Modify)
- scanner
- renamer
- ffprobe
- tmdb

### Disabled Plugins (Skip)
- omdb
- tvmaze
- tvdb
- file_reader (check if exists)

### Not Touching
- Workers/Taskiq (defer to Phase 2)
- API routes
- Task system
- Template system

---

## FILE CHANGES SUMMARY

### Create
None (SDK already exists)

### Move
| From | To |
|------|-----|
| `plugins/sdk/__init__.py` | `core/plugin_sdk/__init__.py` |
| `plugins/sdk/base.py` | `core/plugin_sdk/base.py` |
| `plugins/sdk/manifest.py` | `core/plugin_sdk/manifest.py` |
| `plugins/sdk/result.py` | `core/plugin_sdk/result.py` |
| `plugins/sdk/context.py` | `core/plugin_sdk/context.py` |
| `plugins/sdk/types.py` | `core/plugin_sdk/types.py` |

### Modify
| File | Change |
|------|--------|
| `core/plugins/discovery.py` | Add Pydantic validation |
| `core/plugins/loader.py` | Use validated manifest data |
| `core/plugins/executor.py` | Create and pass ExecutionContext to plugins |
| `core/plugin_sdk/context.py` | Add task_manager, api_response, emit_task() |
| `core/plugin_sdk/base.py` | Add set_context(), context property, emit_task() |
| `__main__.py` | Wire task_manager to executor |
| `plugins/scanner/client.py` | Inherit from SDK InputPlugin |
| `plugins/renamer/client.py` | Inherit from SDK OutputPlugin |
| `plugins/ffprobe/client.py` | Inherit from SDK OutputPlugin |
| `plugins/tmdb/client.py` | Change import to core.plugin_sdk |

### Delete
| File | Reason |
|------|--------|
| `plugins/base.py` | Duplicate of SDK base.py |
| `plugins/sdk/` | Empty after move |

---

## EXECUTION ORDER

```
1. Phase 1: SDK Relocation
   - Create core/plugin_sdk/ directory
   - Move all SDK files
   - Update __init__.py imports
   - Delete plugins/sdk/

2. Phase 2: Discovery Integration
   - Import PluginManifest in discovery.py
   - Add Pydantic validation
   - Test discovery still works

3. Phase 3: Plugin Migration (one at a time)
   - scanner -> test
   - renamer -> test
   - ffprobe -> test
   - tmdb -> test

4. Phase 4: Cleanup
   - Delete plugins/base.py
   - Verify no broken imports

5. Phase 5: Loader Integration
   - Update loader to use validated metadata
   - Test full pipeline

6. Phase 6: ExecutionContext Integration (NEW)
   - Add emit_task() to ExecutionContext
   - Add set_context() to BasePlugin
   - Update executor to pass context
   - Update __main__.py to wire dependencies
   - Test per-plugin task emission
```

---

## VALIDATION CHECKLIST

After execution, verify:

```bash
# 1. SDK imports work from new location
python -c "from archiverr.core.plugin_sdk import PluginManifest, BasePlugin, InputPlugin, OutputPlugin, PluginResult"

# 2. No imports from old locations
grep -r "from archiverr.plugins.sdk" src/
grep -r "from archiverr.plugins.base" src/
# Both should return nothing

# 3. Plugin discovery works with validation
python -c "from archiverr.core.plugins import PluginDiscovery; d = PluginDiscovery(); plugins = d.discover(); print(f'Found {len(plugins)} plugins')"

# 4. All plugins inherit from base classes
grep -l "class.*Plugin" src/archiverr/plugins/*/client.py | xargs grep -l "InputPlugin\|OutputPlugin"
# Should list all plugin client.py files

# 5. Full execution works
python -m archiverr

# 6. Tests pass
python -m pytest tests/unit/ -v
```

---

## TESTS TO ADD

### Unit Tests for SDK

```python
# tests/unit/core/test_plugin_sdk.py

def test_plugin_manifest_validation():
    """Valid manifest passes validation"""
    data = {
        "name": "test",
        "version": "1.0.0",
        "category": "input",
        "class_name": "TestPlugin"
    }
    manifest = PluginManifest(**data)
    assert manifest.name == "test"
    assert manifest.is_input == True

def test_plugin_manifest_rejects_invalid():
    """Invalid manifest raises ValidationError"""
    with pytest.raises(ValidationError):
        PluginManifest(name="test")  # Missing required fields

def test_plugin_result_duration():
    """PluginResult calculates duration correctly"""
    start = datetime(2024, 1, 1, 12, 0, 0)
    end = datetime(2024, 1, 1, 12, 0, 1, 500000)  # 1.5 seconds later
    result = PluginResult(
        success=True,
        started_at=start,
        finished_at=end
    )
    assert result.duration_ms == 1500
```

---

## DEFERRED TO SESSION 9

1. **Taskiq Integration**: Wire workers to API (replace subprocess)
2. **WebSocket Progress**: Real-time execution updates
3. **Plugin Schema Validation**: Validate plugin output against declared schema
4. **Lifecycle Hooks**: setup(), teardown() for plugins
5. **Disabled Plugin Migration**: omdb, tvmaze, tvdb

---

## REFERENCES

### Industry Standards Researched
- [Stevedore](https://docs.openstack.org/stevedore/latest/) - OpenStack plugin management
- [Pluggy](https://pluggy.readthedocs.io/) - pytest plugin system
- [MkDocs Plugins](https://www.mkdocs.org/dev-guide/plugins/) - Documentation generator plugins
- [Home Assistant Integrations](https://developers.home-assistant.io/docs/architecture_components/) - IoT integrations
- [Stremio Addon SDK](https://github.com/Stremio/stremio-addon-sdk) - Media streaming addons

### Key Patterns Adopted
1. **Manifest validation at load time** (Home Assistant)
2. **Base class with lifecycle methods** (MkDocs)
3. **Standardized result format** (Stremio)
4. **Config validation with Pydantic** (MkDocs 1.4+)
