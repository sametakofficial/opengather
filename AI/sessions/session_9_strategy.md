# SESSION 9 STRATEGY

```yaml
date: 2025-11-27
type: strategy
status: ready_for_execution
previous_session: 8
focus: Industrial-Grade Plugin System Refactoring
```

---

## EXECUTIVE SUMMARY

Session 7-8 yaptığı iddia edilen işlerin %80'i **YAPILMAMIŞ**. SDK dosyaları oluşturulmuş, import'lar değiştirilmiş ama **gerçek entegrasyon sıfır**. Pluginler ExecutionContext kullanmıyor, emit_task() çağrılmıyor, PluginResult kullanılmıyor.

### Gerçek Durum Analizi

| Söylenen | Gerçek |
|----------|--------|
| ExecutionContext entegre edildi | ❌ Pluginler `self.context` kullanmıyor |
| emit_task() eklendi | ❌ Hiçbir plugin çağırmıyor |
| PluginResult standardize edildi | ❌ Hala raw dict döndürülüyor |
| Lifecycle hooks var | ❌ Sadece execute() var, setup/teardown yok |
| SDK integrated | ⚠️ Sadece import değişti, actual usage yok |

### Kod Kanıtları

```python
# tmdb/client.py - Line 29
self.debugger = get_debugger()  # ❌ Should use self.context.debugger

# ffprobe/client.py - Line 17
self.debugger = get_debugger()  # ❌ Should use self.context.debugger

# scanner/client.py - Line 14
self.debugger = get_debugger()  # ❌ Should use self.context.debugger
```

**Hiçbir plugin `self.context` veya `self.emit_task()` kullanmıyor!**

---

## INDUSTRY RESEARCH

### 1. Jellyfin Plugin System

**Strengths:**
- Interface-based design (IMetadataProvider, IScheduledTask, etc.)
- Automatic dependency injection via constructor
- Plugin versioning tied to server version
- Hot reload support
- Configuration UI schema

**Key Pattern:**
```csharp
// Plugin implements interface, server auto-discovers
public class MyPlugin : IServerEntryPoint, IMetadataProvider
{
    // Dependencies injected via constructor
    public MyPlugin(ILogger logger, IHttpClient client)
    {
        _logger = logger;
        _client = client;
    }
}
```

### 2. Stremio Addon SDK

**Strengths:**
- Manifest-driven (everything declared upfront)
- Handler-based (defineStreamHandler, defineCatalogHandler)
- Standardized response format
- Built-in catalog/stream/meta types
- Remote addon support (HTTP API)

**Key Pattern:**
```javascript
const builder = new addonBuilder({
    id: 'org.addon',
    version: '1.0.0',
    resources: ['stream', 'meta'],  // Capabilities declared
    types: ['movie', 'series'],
    catalogs: [...]
});

builder.defineStreamHandler(async ({type, id}) => {
    return { streams: [...] };  // Standardized response
});
```

### 3. Home Assistant Integrations

**Strengths:**
- Strict manifest.json schema with Pydantic
- Dependency declaration (dependencies, after_dependencies)
- Requirements auto-installation
- Config flow for UI setup
- Quality scale rating

**Key Pattern:**
```json
{
    "domain": "hue",
    "name": "Philips Hue",
    "version": "1.0.0",
    "dependencies": ["mqtt"],
    "after_dependencies": ["http"],
    "requirements": ["aiohue==1.9.1"],
    "config_flow": true
}
```

### 4. OpenStack Stevedore

**Strengths:**
- Entry points for discovery (pip-integrated)
- Namespace isolation (driver, hook, extension namespaces)
- Strict API enforcement via ABC
- Multiple loading patterns (driver, hook, extension)
- Lazy loading support

**Key Pattern:**
```python
from stevedore import driver

mgr = driver.DriverManager(
    namespace='myapp.drivers',
    name='my_driver',
    invoke_on_load=True,
    invoke_args=(config,)
)
mgr.driver.do_something()
```

### 5. MkDocs Plugin System

**Strengths:**
- config_scheme for typed configuration
- Event hooks (on_config, on_pre_build, on_post_build)
- Plugin priority system
- Config validation with Pydantic
- Lifecycle management

**Key Pattern:**
```python
class MyPlugin(BasePlugin):
    config_scheme = (
        ('enabled', config_options.Type(bool, default=True)),
        ('api_key', config_options.Type(str, required=True)),
    )
    
    def on_config(self, config):
        # Called after config loaded
        return config
    
    def on_pre_build(self, config):
        # Called before build starts
        pass
```

---

## ARCHITECTURE DECISIONS

### Decision 1: Capability-Based System (Stremio-inspired)

**Current Problem:** Core bilmiyor plugin ne yapabilir

**Solution:** Plugin manifest'te capabilities declare et

```yaml
# plugin.yml
name: tmdb
version: 1.0.0
category: output

capabilities:
  - metadata.movie
  - metadata.show
  - metadata.episode
  - validation.duration

provides:
  - movie
  - show
  - episode
  - season
  - extras
  - normalized

expects:
  - renamer.parsed
```

### Decision 2: Lifecycle Hooks (MkDocs-inspired)

**Current Problem:** Sadece execute() var

**Solution:** Full lifecycle support

```python
class BasePlugin(ABC):
    async def on_load(self, context: ExecutionContext):
        """Called when plugin is loaded (once)"""
        pass
    
    async def on_config(self, config: Dict) -> Dict:
        """Called after config loaded, can modify config"""
        return config
    
    async def on_before_execute(self, match_data: Dict) -> Dict:
        """Called before each execute"""
        return match_data
    
    @abstractmethod
    async def execute(self, match_data: Dict) -> PluginResult:
        """Main execution"""
        pass
    
    async def on_after_execute(self, result: PluginResult) -> PluginResult:
        """Called after execute, can modify result"""
        return result
    
    async def on_unload(self):
        """Called when plugin is unloaded (cleanup)"""
        pass
```

### Decision 3: Mandatory PluginResult (Standardization)

**Current Problem:** Her plugin farklı dict format döndürüyor

**Solution:** PluginResult mandatory

```python
from archiverr.core.plugin_sdk import PluginResult, OutputPlugin

class TMDbPlugin(OutputPlugin):
    async def execute(self, match_data: Dict) -> PluginResult:
        # Do work...
        return PluginResult(
            success=True,
            data={
                'movie': {...},
                'normalized': {...}
            },
            metadata={
                'api_calls': 3,
                'cache_hits': 1
            }
        )
```

### Decision 4: Context-First Design (DI Pattern)

**Current Problem:** Pluginler kendi debugger'ını alıyor

**Solution:** Her şey context'ten gelir

```python
class TMDbPlugin(OutputPlugin):
    async def execute(self, match_data: Dict) -> PluginResult:
        # ✅ CORRECT - Use context
        self.context.log("info", "tmdb", "Searching...")
        self.context.emit_progress(50, "Fetching metadata")
        
        # Access config via context
        api_key = self.context.config.get('api_key')
        
        # Emit task during execution
        self.emit_task({
            "type": "print",
            "template": "Found: {{ data.movie.title }}"
        })
        
        return PluginResult(success=True, data={...})
```

### Decision 5: Plugin Events/Hooks (Jellyfin-inspired)

**Current Problem:** Pluginler birbirleriyle konuşamıyor

**Solution:** Event hook sistemi

```python
class TMDbPlugin(OutputPlugin):
    hooks = ['metadata.found', 'movie.matched']
    
    async def execute(self, match_data: Dict) -> PluginResult:
        movie = await self._search_movie(...)
        
        # Emit event - other plugins can listen
        await self.context.emit_event('metadata.found', {
            'plugin': 'tmdb',
            'type': 'movie',
            'data': movie
        })
        
        return PluginResult(...)

class ValidationPlugin(OutputPlugin):
    listens_to = ['metadata.found']
    
    async def on_event(self, event: str, data: Dict):
        if event == 'metadata.found':
            # Validate duration against ffprobe
            pass
```

### Decision 6: Config Schema Validation (Home Assistant-inspired)

**Current Problem:** Plugin config'leri validate edilmiyor

**Solution:** Her plugin kendi schema'sını tanımlar

```python
# plugin.yml
name: tmdb
config_schema:
  api_key:
    type: string
    required: true
    secret: true
    description: TMDb API key
  
  language:
    type: string
    default: en-US
    pattern: "^[a-z]{2}-[A-Z]{2}$"
  
  extras:
    type: object
    properties:
      movie_credits:
        type: boolean
        default: false
```

```python
# Validation at load time
from pydantic import create_model_from_schema

class PluginLoader:
    def validate_config(self, plugin_name: str, config: Dict):
        schema = self.manifests[plugin_name].get('config_schema')
        if schema:
            model = create_model_from_schema(schema)
            model(**config)  # Raises ValidationError if invalid
```

---

## IMPLEMENTATION PLAN

### Phase 1: Context-First Refactor (CRITICAL)

**Goal:** Pluginlerin gerçekten context kullanması

**Changes:**

1. **Remove standalone debugger calls:**
```python
# BEFORE (tmdb/client.py)
def __init__(self, config):
    super().__init__(config)
    self.debugger = get_debugger()  # ❌ DELETE

# AFTER
def __init__(self, config):
    super().__init__(config)
    # No debugger - use self.context.debugger
```

2. **Update execute() to use context:**
```python
# BEFORE
def execute(self, match_data):
    self.debugger.info("tmdb", "Processing...")

# AFTER
async def execute(self, match_data) -> PluginResult:
    self.log("info", "Processing...")  # Uses context internally
```

3. **Add convenience methods to BasePlugin:**
```python
class BasePlugin:
    def log(self, level: str, message: str, **kwargs):
        """Convenience logging via context"""
        if self._context:
            self._context.log(level, self.name, message, **kwargs)
    
    def get_previous_result(self, plugin_name: str) -> Optional[Dict]:
        """Get result from previous plugin"""
        if self._context:
            return self._context.get_plugin_result(plugin_name)
        return None
```

**Files to Modify:**
- `plugins/tmdb/client.py` - Remove debugger, use context
- `plugins/scanner/client.py` - Remove debugger, use context
- `plugins/renamer/client.py` - Remove debugger, use context
- `plugins/ffprobe/client.py` - Remove debugger, use context
- `core/plugin_sdk/base.py` - Add convenience methods

### Phase 2: PluginResult Enforcement

**Goal:** Tüm pluginler PluginResult döndürsün

**Changes:**

1. **Update PluginResult model:**
```python
# core/plugin_sdk/result.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class PluginResult(BaseModel):
    """Standardized plugin result format"""
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    
    # Timing
    started_at: datetime
    finished_at: datetime
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def duration_ms(self) -> int:
        return int((self.finished_at - self.started_at).total_seconds() * 1000)
    
    def to_response_dict(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            'status': {
                'success': self.success,
                'started_at': self.started_at.isoformat(),
                'finished_at': self.finished_at.isoformat(),
                'duration_ms': self.duration_ms,
                'error': self.error
            },
            **self.data
        }
    
    @classmethod
    def error_result(cls, error: str) -> 'PluginResult':
        """Factory for error results"""
        now = datetime.now()
        return cls(
            success=False,
            error=error,
            started_at=now,
            finished_at=now
        )
```

2. **Update TMDb plugin to return PluginResult:**
```python
# plugins/tmdb/client.py
async def execute(self, match_data: Dict) -> PluginResult:
    started_at = datetime.now()
    
    try:
        movie = await self._search_movie(...)
        
        return PluginResult(
            success=True,
            data={
                'movie': movie,
                'normalized': self.normalizer.normalize(movie)
            },
            started_at=started_at,
            finished_at=datetime.now(),
            metadata={
                'tmdb_id': movie.get('id'),
                'api_calls': self.api.call_count
            }
        )
    except Exception as e:
        return PluginResult.error_result(str(e))
```

### Phase 3: Lifecycle Hooks

**Goal:** setup/teardown support

**Changes:**

1. **Update BasePlugin:**
```python
# core/plugin_sdk/base.py
class BasePlugin(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._context: Optional[ExecutionContext] = None
        self._initialized = False
    
    async def setup(self) -> None:
        """
        Called once when plugin is loaded.
        Override to initialize resources (API clients, caches, etc.)
        """
        self._initialized = True
    
    async def teardown(self) -> None:
        """
        Called when plugin is unloaded.
        Override to cleanup resources.
        """
        pass
    
    @abstractmethod
    async def execute(self, match_data: Dict[str, Any]) -> PluginResult:
        """Main execution - must be implemented"""
        pass
```

2. **Update Executor to call lifecycle:**
```python
# core/plugins/executor.py
class PluginExecutor:
    async def load_plugins(self, plugins: Dict[str, Any]):
        """Load and setup plugins"""
        for name, plugin in plugins.items():
            if hasattr(plugin, 'setup'):
                await plugin.setup()
    
    async def unload_plugins(self, plugins: Dict[str, Any]):
        """Teardown and unload plugins"""
        for name, plugin in plugins.items():
            if hasattr(plugin, 'teardown'):
                await plugin.teardown()
```

### Phase 4: Capability System

**Goal:** Plugin yeteneklerini manifest'te declare et

**Changes:**

1. **Update PluginManifest:**
```python
# core/plugin_sdk/manifest.py
class PluginManifest(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    category: Literal["input", "output"]
    class_name: Optional[str] = None
    
    # Dependencies
    depends_on: List[str] = []
    expects: List[str] = []
    
    # NEW: Capabilities
    capabilities: List[str] = []
    provides: List[str] = []
    
    # NEW: Events
    hooks: List[str] = []  # Events this plugin emits
    listens_to: List[str] = []  # Events this plugin handles
    
    # NEW: Config schema
    config_schema: Optional[Dict[str, Any]] = None
```

2. **Update plugin.yml files:**
```yaml
# plugins/tmdb/plugin.yml
name: tmdb
version: 1.0.0
category: output
class_name: TMDbPlugin

depends_on:
  - renamer

expects:
  - renamer.parsed

capabilities:
  - metadata.movie
  - metadata.show
  - metadata.episode
  - validation.duration

provides:
  - movie
  - show
  - episode
  - season
  - extras
  - normalized
  - validation

hooks:
  - metadata.found
  - movie.matched
  - show.matched

config_schema:
  api_key:
    type: string
    required: true
    secret: true
  language:
    type: string
    default: en-US
  region:
    type: string
    default: TR
```

### Phase 5: Documentation

**Goal:** Plugin geliştirme dokümantasyonu

**Create:** `docs/PLUGIN_SDK.md`

```markdown
# Archiverr Plugin SDK

## Quick Start

\`\`\`python
from archiverr.core.plugin_sdk import OutputPlugin, PluginResult

class MyPlugin(OutputPlugin):
    async def execute(self, match_data: dict) -> PluginResult:
        self.log("info", "Processing...")
        return PluginResult(success=True, data={...})
\`\`\`

## Base Classes

| Class | Purpose |
|-------|---------|
| `InputPlugin` | Collect matches (scanner, file_reader) |
| `OutputPlugin` | Process matches (tmdb, renamer, ffprobe) |

## Context Access

\`\`\`python
# Logging
self.log("info", "message", key=value)
self.log("error", "failed", error=str(e))

# Progress
self.emit_progress(50, "Halfway done")

# Task emission
self.emit_task({"type": "print", "template": "Found: {{ data.movie.title }}"})

# Previous plugin results
renamer_data = self.get_previous_result("renamer")
\`\`\`

## PluginResult

\`\`\`python
return PluginResult(
    success=True,
    data={"movie": {...}},
    started_at=started_at,
    finished_at=datetime.now(),
    metadata={"api_calls": 3}
)
\`\`\`

## Lifecycle Hooks

\`\`\`python
async def setup(self):
    self.api_client = TMDbAPI(self.config['api_key'])

async def execute(self, match_data):
    ...

async def teardown(self):
    await self.api_client.close()
\`\`\`

## Manifest (plugin.yml)

\`\`\`yaml
name: my_plugin
version: 1.0.0
category: output
class_name: MyPlugin

depends_on: [renamer]
expects: [renamer.parsed]

capabilities: [metadata.movie]
provides: [movie, normalized]
\`\`\`
```

---

## SCOPE LIMITATION

### Active Plugins (Modify)
- tmdb (primary focus)
- scanner
- renamer
- ffprobe

### Disabled Plugins (Skip)
- omdb
- tvmaze  
- tvdb

Bu pluginler sadece TMDb ile aynı pattern'i takip ediyor. TMDb düzgün refactor edildikten sonra 1 saatlik iş.

---

## FILE CHANGES SUMMARY

### Create

| File | Purpose |
|------|---------|
| `docs/PLUGIN_SDK.md` | Developer documentation |
| `tests/unit/core/test_plugin_sdk.py` | SDK unit tests |

### Modify (Critical)

| File | Change |
|------|--------|
| `core/plugin_sdk/base.py` | Add lifecycle hooks, convenience methods |
| `core/plugin_sdk/result.py` | Add factory methods, to_response_dict() |
| `core/plugin_sdk/manifest.py` | Add capabilities, provides, config_schema |
| `core/plugins/executor.py` | Add lifecycle calls, enforce PluginResult |
| `plugins/tmdb/client.py` | Full refactor - context, async, PluginResult |
| `plugins/scanner/client.py` | Remove debugger, use context |
| `plugins/renamer/client.py` | Remove debugger, use context |
| `plugins/ffprobe/client.py` | Remove debugger, use context |
| `plugins/tmdb/plugin.yml` | Add capabilities, provides, config_schema |

### Delete

None

---

## EXECUTION ORDER

```
1. Phase 1: Context-First (2 hours)
   - Update BasePlugin with convenience methods
   - Refactor TMDb to use context
   - Refactor other plugins
   - Test logging works through context

2. Phase 2: PluginResult (1 hour)
   - Update PluginResult model
   - Refactor TMDb to return PluginResult
   - Update executor to handle PluginResult

3. Phase 3: Lifecycle (1 hour)
   - Add setup/teardown to BasePlugin
   - Update executor
   - Add setup to TMDb (API client init)

4. Phase 4: Capabilities (1 hour)
   - Update PluginManifest
   - Update TMDb plugin.yml
   - Test capability checking

5. Phase 5: Documentation (30 min)
   - Create PLUGIN_SDK.md
   - Update 03_ARCHITECTURE.md
```

---

## VALIDATION CHECKLIST

```bash
# 1. No standalone debugger imports in plugins
grep -r "get_debugger()" src/archiverr/plugins/
# Should return NOTHING

# 2. All plugins use context
grep -r "self.context" src/archiverr/plugins/*/client.py
# Should return ALL plugins

# 3. TMDb returns PluginResult
python -c "from archiverr.plugins.tmdb.client import TMDbPlugin; print(TMDbPlugin.__annotations__)"

# 4. Lifecycle hooks exist
python -c "from archiverr.core.plugin_sdk import BasePlugin; print(hasattr(BasePlugin, 'setup'))"

# 5. Full execution works
python -m archiverr

# 6. Tests pass
python -m pytest tests/ -v
```

---

## SUCCESS CRITERIA

Session 9 başarılı sayılır eğer:

1. ✅ Hiçbir plugin `get_debugger()` çağırmıyorsa
2. ✅ Tüm pluginler `self.context` üzerinden log yapıyorsa
3. ✅ TMDb plugin `PluginResult` döndürüyorsa
4. ✅ `setup()` ve `teardown()` hook'ları çalışıyorsa
5. ✅ `docs/PLUGIN_SDK.md` mevcut ve doğruysa
6. ✅ `python -m archiverr` hatasız çalışıyorsa

---

## REFERENCES

### Industry Standards Researched
- [Jellyfin Plugin Template](https://github.com/jellyfin/jellyfin-plugin-template)
- [Stremio Addon SDK](https://github.com/Stremio/stremio-addon-sdk)
- [Home Assistant Integration Manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
- [OpenStack Stevedore](https://docs.openstack.org/stevedore/latest/)
- [MkDocs Plugin Guide](https://www.mkdocs.org/dev-guide/plugins/)

### Key Patterns Adopted
1. **Manifest-driven capabilities** (Stremio)
2. **Lifecycle hooks** (MkDocs)
3. **Standardized result format** (Stremio PluginResult)
4. **Config schema validation** (Home Assistant)
5. **Dependency injection** (Jellyfin)
6. **Event hooks** (MkDocs/Jellyfin)
