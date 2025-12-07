# FILE STRUCTURE AND MODULES

```yaml
tarih: 2024-12-08
durum: strategy
session: 12
konu: Professional file organization and module architecture
```

---

## OVERVIEW

Bu dokümanda Session 12 için önerilen dosya yapısı ve modül organizasyonu yer alır.

**⚠️ ÖNEMLI NOT**: Bu yapı bir **öneri**dir ve mevcut projeye uyarlanmalıdır. Implementation sırasında mevcut dosya yapısı göz önünde bulundurulmalı ve gerekli değişiklikler yapılmalıdır.

---

## PROJECT ROOT STRUCTURE

```
archiverr/
├── src/
│   └── archiverr/              # Main package
│       ├── __init__.py
│       ├── __main__.py         # Entry point (~50 lines)
│       │
│       ├── core/               # Core system
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── exceptions.py
│       │   │
│       │   ├── config/         # Configuration management
│       │   ├── plugins/        # Plugin system
│       │   ├── execution/      # Job execution
│       │   ├── triggers/       # Trigger rule system
│       │   └── locking/        # FS lock system
│       │
│       ├── state/              # State management
│       │   ├── __init__.py
│       │   ├── models.py       # RunState, JobState
│       │   ├── manager.py      # StateManager
│       │   └── queue.py        # Job queue
│       │
│       ├── events/             # Event system
│       │   ├── __init__.py
│       │   ├── bus.py
│       │   └── handlers.py
│       │
│       ├── infrastructure/     # External systems
│       │   ├── __init__.py
│       │   ├── database.py     # MongoDB connection
│       │   └── persistence.py  # Persistence layer
│       │
│       ├── plugins/            # Built-in plugins
│       │   ├── scanner/
│       │   ├── renamer/
│       │   ├── tmdb/
│       │   └── tasker/
│       │
│       ├── utils/              # Utilities
│       │   ├── __init__.py
│       │   ├── config_loader.py
│       │   ├── templates.py    # Jinja2 utilities
│       │   └── debug.py
│       │
│       ├── api/                # FastAPI
│       │   ├── __init__.py
│       │   ├── main.py
│       │   └── routes/
│       │
│       └── cli/                # CLI interface
│           ├── __init__.py
│           └── main.py
│
├── tests/                      # Tests
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── config/                     # Configuration files
│   ├── config.yml
│   └── plugins/
│
├── docs/                       # Documentation
│   ├── api/
│   ├── plugins/
│   └── user-guide/
│
├── AI/                         # AI strategy docs
│   ├── PHILOSOPHY.md
│   └── sessions/
│
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## CORE MODULE ORGANIZATION

### core/orchestrator.py

```
Purpose: Main execution coordinator
Size: ~300 lines
Dependencies: State, EventBus, PluginRegistry, Execution

Responsibilities:
- Run lifecycle management (start → execute → finalize)
- Per-run plugin execution
- Job queue execution coordination
- Error handling and recovery
- Event emission

Classes:
- Orchestrator: Main coordinator
- RunResult: Result data class
- build_orchestrator(): Factory function
```

### core/exceptions.py

```
Purpose: Custom exceptions
Size: ~100 lines
Dependencies: None

Exception Hierarchy:
- ArchiverError (base)
  ├── CriticalError (stops run)
  ├── JobExecutionError (job failed)
  ├── PluginError (plugin failed)
  ├── AccessDenied (state access violation)
  ├── FSLockError (file system lock conflict)
  └── ConfigError (configuration error)
```

---

## CORE/CONFIG MODULE

```
core/config/
├── __init__.py
├── loader.py           # Config file loading
├── merger.py           # Config + manifest merge
├── validator.py        # Schema validation
└── freezer.py          # Config freezing (immutability)
```

### config/loader.py

```python
"""
Config file loading with !include support

Responsibilities:
- Load YAML files
- Process !include directives
- Environment variable substitution
- Validation
"""

def load_config(path: str) -> Dict:
    """Load config with includes"""

def resolve_includes(config: Dict, base_path: str) -> Dict:
    """Resolve !include directives recursively"""

def substitute_env_vars(config: Dict) -> Dict:
    """Substitute ${ENV_VAR} with environment variables"""
```

### config/merger.py

```python
"""
Config and manifest merging

Responsibilities:
- Merge manifest.yml defaults with config.yml overrides
- Deep merge strategy (config wins)
- Immutable field protection
"""

def merge_configs(manifest: Dict, config: Dict) -> Dict:
    """Deep merge config over manifest"""

def validate_immutable_fields(manifest: Dict, config: Dict) -> List[str]:
    """Check if immutable fields are being overridden"""

IMMUTABLE_FIELDS = [
    "name", "version", "run_mode", "stage", 
    "class_name", "entry_point"
]
```

---

## CORE/PLUGINS MODULE

```
core/plugins/
├── __init__.py
├── registry.py         # Plugin discovery and loading
├── base.py             # BasePlugin class
├── services.py         # PluginServices interface
├── loader.py           # Plugin class loading
├── manifest.py         # Manifest schema and validation
└── validators.py       # Plugin validation
```

### plugins/registry.py

```python
"""
Plugin registry for discovery and management

Responsibilities:
- Discover plugins from directories
- Load manifest.yml files
- Validate manifests
- Load plugin classes
- Manage plugin lifecycle
"""

class PluginRegistry:
    def discover_plugins(self, plugin_dir: str) -> None:
        """Scan directory for plugins"""
    
    def load_manifest(self, plugin_path: str) -> Dict:
        """Load and validate manifest.yml"""
    
    def load_plugin_class(self, manifest: Dict, plugin_path: str) -> type:
        """Import and instantiate plugin class"""
    
    def get_plugins_by_stage(self, stage: str) -> List[Plugin]:
        """Get plugins for specific stage"""
    
    def get_per_run_plugins(self) -> List[Plugin]:
        """Get per_run plugins"""
    
    def validate_manifests(self) -> List[str]:
        """Validate all manifests"""
```

### plugins/base.py

```python
"""
Base plugin class and result types

All plugins must inherit from BasePlugin
"""

@dataclass
class PluginResult:
    status: str  # "success", "failed", "skipped"
    data: Optional[Dict] = None
    error: Optional[str] = None
    
    @classmethod
    def success(cls, data: Dict) -> 'PluginResult':
        ...
    
    @classmethod
    def failed(cls, error: str) -> 'PluginResult':
        ...
    
    @classmethod
    def skipped(cls, reason: str = "") -> 'PluginResult':
        ...


class BasePlugin(ABC):
    def __init__(self, name: str, config: Dict):
        ...
    
    def execute_run(self, services: PluginServices) -> PluginResult:
        """For per_run plugins"""
        raise NotImplementedError()
    
    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        """For per_job plugins"""
        raise NotImplementedError()
```

### plugins/services.py

```python
"""
PluginServices interface for plugin-system communication

Provides controlled access to state, events, config, etc.
Enforces access control based on plugin mode
"""

class PluginServices:
    def __init__(
        self,
        state: StateManager,
        event_bus: EventBus,
        logger: Logger,
        config: ConfigManager,
        mode: str  # "per_run" or "per_job"
    ):
        ...
    
    # Job management
    def createJob(self, input_value: str, input_data: Dict) -> str:
        """Create new job (both modes)"""
    
    def updateJob(self, key: str, value: Any) -> None:
        """Update CURRENT job (per_job only) - ID yok"""
    
    def updatePlugin(self, data: Dict) -> None:
        """Update CURRENT plugin data (per_job only) - Name yok"""
    
    # State access
    def get_run(self) -> RunState:
        """Get run state (all modes)"""
    
    def get_current_job(self) -> JobState:
        """Get current job (per_job only)"""
    
    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs (per_job only)"""
    
    # Config access
    def get_config(self, key: str = None, default: Any = None) -> Any:
        """Get config value (all modes)"""
    
    # Event bus
    def emit(self, event: str, data: Dict = None) -> None:
        """Emit event (all modes)"""
    
    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe to event (all modes)"""
    
    # Logging
    @property
    def logger(self) -> Logger:
        """Get logger (all modes)"""
    
    # Access control
    def _check_access(self, required_mode: str, method: str):
        """Check if current plugin mode has access"""
```

---

## CORE/EXECUTION MODULE

```
core/execution/
├── __init__.py
├── stage_executor.py   # Stage execution logic
├── job_executor.py     # Single job execution
└── queue_executor.py   # Job queue processing
```

### execution/stage_executor.py

```python
"""
Stage execution with plugin orchestration

Responsibilities:
- Execute plugins in a stage
- Check trigger rules
- Handle plugin failures
- Emit stage events
"""

class StageExecutor:
    def __init__(
        self,
        state: StateManager,
        plugin_registry: PluginRegistry,
        trigger_manager: TriggerRuleManager,
        event_bus: EventBus,
        logger: Logger
    ):
        ...
    
    def execute_stage(self, stage: str, job: JobState) -> None:
        """Execute all plugins in stage"""
    
    def _execute_plugin(
        self, 
        plugin: Plugin,
        job: JobState,
        services: PluginServices
    ) -> PluginResult:
        """Execute single plugin with error handling"""
    
    def _check_trigger_rules(self, plugin: Plugin) -> bool:
        """Check if plugin should execute"""
```

### execution/job_executor.py

```python
"""
Single job execution through all stages

Responsibilities:
- Execute parse → data → output stages
- Handle job failures
- Update job status
- Emit job events
"""

class JobExecutor:
    def __init__(
        self,
        stage_executor: StageExecutor,
        state: StateManager,
        event_bus: EventBus,
        logger: Logger
    ):
        ...
    
    def execute(self, job: JobState) -> None:
        """Execute job through all stages"""
    
    def _execute_parse_stage(self, job: JobState) -> None:
        ...
    
    def _execute_data_stage(self, job: JobState) -> None:
        ...
    
    def _execute_output_stage(self, job: JobState) -> None:
        ...
```

### execution/queue_executor.py

```python
"""
Job queue processing

Responsibilities:
- Process job queue
- Manage job execution order
- Handle job failures
- Track execution statistics
"""

class QueueExecutor:
    def __init__(
        self,
        job_executor: JobExecutor,
        state: StateManager,
        event_bus: EventBus,
        logger: Logger
    ):
        ...
    
    def execute_queue(self, queue: JobQueue) -> None:
        """Execute all jobs in queue"""
    
    def _execute_job_safe(self, job: JobState) -> bool:
        """Execute job with error recovery"""
```

---

## CORE/TRIGGERS MODULE

```
core/triggers/
├── __init__.py
├── manager.py          # TriggerRuleManager
├── resolver.py         # StateResolver
├── matcher.py          # ValueMatcher
└── evaluator.py        # RuleEvaluator
```

### triggers/manager.py

```python
"""
Main trigger rule manager

Responsibilities:
- Coordinate trigger rule evaluation
- Check if plugin should execute
- Get unmet requirements for debugging
"""

class TriggerRuleManager:
    def __init__(self, state: StateManager):
        self._resolver = StateResolver(state)
        self._matcher = ValueMatcher()
        self._evaluator = RuleEvaluator(self._resolver, self._matcher)
    
    def should_execute(
        self,
        plugin_manifest: Dict,
        context_type: str = "per_job"
    ) -> bool:
        """Check if plugin should execute"""
    
    def get_unmet_requirements(self, plugin_manifest: Dict) -> List[str]:
        """Get list of unmet requirements"""
```

### triggers/resolver.py

```python
"""
State path resolution

Responsibilities:
- Resolve dot-notation paths to values
- Navigate nested state objects
- Check plugin status
"""

class StateResolver:
    def __init__(self, state: StateManager):
        ...
    
    def resolve_path(self, path: str) -> Any:
        """Resolve state path to value"""
    
    def check_plugin_status(self, plugin_path: str) -> Optional[Dict]:
        """Check if plugin has failed"""
```

### triggers/matcher.py

```python
"""
Value matching for trigger rules

Responsibilities:
- Match exact values
- Check success/fail conditions
- Type conversion
"""

class ValueMatcher:
    def match(self, path: str, expected: str, resolver: StateResolver) -> bool:
        """Match value with expected"""
    
    def match_exact(self, path: str, expected: str, resolver: StateResolver) -> bool:
        """Exact value match"""
    
    def match_success(self, path: str, resolver: StateResolver) -> bool:
        """Check if value exists"""
    
    def match_fail(self, path: str, resolver: StateResolver) -> bool:
        """Check if value is empty or failed"""
```

### triggers/evaluator.py

```python
"""
Trigger rule evaluation

Responsibilities:
- Evaluate standard trigger rules (all_success, etc.)
- Evaluate value-based requirements
- Combine evaluations
"""

class RuleEvaluator:
    def __init__(self, resolver: StateResolver, matcher: ValueMatcher):
        ...
    
    def evaluate(
        self,
        requires: List[str],
        trigger_rule: str = "all_success"
    ) -> bool:
        """Evaluate if requirements are satisfied"""
    
    def _all_success(self, requirements: List[str]) -> bool:
        ...
    
    def _one_success(self, requirements: List[str]) -> bool:
        ...
    
    # ... other trigger rules
```

---

## CORE/LOCKING MODULE

```
core/locking/
├── __init__.py
├── fs_lock_manager.py  # File system lock management
├── conflict_detector.py # Conflict detection at startup
└── path_resolver.py    # Lock path resolution
```

### locking/fs_lock_manager.py

```python
"""
File system lock management

Responsibilities:
- Acquire/release FS locks
- Prevent concurrent access to same paths
- Thread-safe locking
"""

class FSLockManager:
    def __init__(self):
        self._locks: Dict[str, str] = {}  # path -> plugin_name
        self._lock = threading.Lock()
    
    def acquire_locks(self, plugins: List[Plugin], job: JobState) -> None:
        """Acquire locks for plugins"""
    
    def release_locks(self, plugins: List[Plugin], job: JobState) -> None:
        """Release locks for plugins"""
    
    def _resolve_lock_path(self, lock_path: str, job: JobState) -> str:
        """Resolve lock path with config variables"""
```

### locking/conflict_detector.py

```python
"""
Startup conflict detection

Responsibilities:
- Detect potential lock conflicts before runtime
- Validate lock paths
- Check for overlapping paths
"""

class ConflictDetector:
    def detect_conflicts(self, plugins: List[Plugin]) -> List[str]:
        """Detect lock conflicts at startup"""
    
    def _check_path_overlap(self, path1: str, path2: str) -> bool:
        """Check if paths overlap"""
```

---

## STATE MODULE

```
state/
├── __init__.py
├── models.py           # State data classes
├── manager.py          # StateManager
└── queue.py            # Job queue
```

### state/models.py

```python
"""
State data classes

Classes:
- RunState: Run metadata and status
- JobState: Job input, output, status
- PluginStatus: Plugin execution status
"""

@dataclass
class RunState:
    id: str
    status: Dict[str, Any]
    config: Dict[str, Any]


@dataclass
class JobState:
    index: int
    id: str
    run_id: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    status: Dict[str, Any]


@dataclass
class PluginStatus:
    state: str  # "pending", "running", "completed", "failed"
    success: bool
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: int
    error: Optional[str]
```

### state/manager.py

```python
"""
Global state manager

Responsibilities:
- Manage 6 global states (run, config, job, jobs, plugin, plugins)
- Enforce access control
- State persistence coordination
"""

class StateManager:
    # Run state
    def start_run(self, config: Dict) -> str:
        ...
    
    def get_run(self) -> RunState:
        ...
    
    def complete_run(self) -> None:
        ...
    
    # Config state
    def set_config(self, config: Dict) -> None:
        ...
    
    def get_config(self) -> Dict:
        ...
    
    # Job state
    def create_job(self, input_value: str, input_data: Dict) -> str:
        ...
    
    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """Internal - called by PluginServices"""
        ...
    
    def get_current_job(self) -> JobState:
        ...
    
    def get_all_jobs(self) -> List[JobState]:
        ...
    
    # Plugin state
    def update_plugin(self, job_id: str, plugin_name: str, data: Dict) -> None:
        """Internal - called by PluginServices"""
        ...
    
    def get_current_plugins(self) -> Dict:
        ...
    
    def get_all_plugins(self) -> List[Dict]:
        ...
    
    # Queue
    def get_job_queue(self) -> JobQueue:
        ...
```

### state/queue.py

```python
"""
Job queue management

Responsibilities:
- Maintain job queue
- Track processing state
- Manage completed/failed jobs
"""

class JobQueue:
    def __init__(self):
        self._queue: List[JobState] = []
        self._processing: Optional[JobState] = None
        self._completed: List[JobState] = []
        self._failed: List[JobState] = []
    
    def enqueue(self, job: JobState) -> None:
        ...
    
    def dequeue(self) -> Optional[JobState]:
        ...
    
    def mark_processing(self, job: JobState) -> None:
        ...
    
    def mark_completed(self, job: JobState) -> None:
        ...
    
    def mark_failed(self, job: JobState) -> None:
        ...
```

---

## NAMING CONVENTIONS

### Files

```
snake_case.py           # Module files
CamelCase               # Class names
SCREAMING_SNAKE_CASE    # Constants
```

### Classes

```
Manager                 # Stateful coordinator (StateManager)
Executor                # Execute logic (JobExecutor)
Resolver                # Resolve/lookup (StateResolver)
Matcher                 # Match/compare (ValueMatcher)
Evaluator               # Evaluate/decide (RuleEvaluator)
Detector                # Detect/check (ConflictDetector)
Builder                 # Build/construct (ResponseBuilder)
Loader                  # Load/import (ConfigLoader)
Registry                # Registry/collection (PluginRegistry)
```

### Methods

```
get_*()                 # Retrieve data
set_*()                 # Set data
create_*()              # Create new entity
update_*()              # Update existing entity
delete_*()              # Delete entity
execute_*()             # Execute action
process_*()             # Process data
validate_*()            # Validation
resolve_*()             # Resolution
check_*()               # Boolean check
```

---

## MODULE DEPENDENCIES

```
┌─────────────────────────────────────┐
│         __main__.py                 │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│         Orchestrator                │
└─────────────────────────────────────┘
                ↓
    ┌───────────┴───────────┐
    ↓                       ↓
┌──────────┐        ┌──────────────┐
│  State   │        │ PluginRegistry│
│ Manager  │        └──────────────┘
└──────────┘                ↓
    ↓                ┌──────────────┐
┌──────────┐        │StageExecutor │
│EventBus  │        └──────────────┘
└──────────┘                ↓
    ↓                ┌──────────────┐
┌──────────┐        │TriggerRule   │
│Persistence│       │  Manager     │
└──────────┘        └──────────────┘
                            ↓
                    ┌──────────────┐
                    │FSLockManager │
                    └──────────────┘
```

---

## IMPORT GUIDELINES

### Absolute Imports

```python
# ✅ GOOD: Absolute imports
from archiverr.state.manager import StateManager
from archiverr.core.orchestrator import Orchestrator
from archiverr.events.bus import EventBus
```

### Relative Imports

```python
# ✅ GOOD: Relative imports within package
from .manager import StateManager
from ..events.bus import EventBus
```

### Circular Import Prevention

```python
# ✅ GOOD: Use TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.state.manager import StateManager

# ❌ BAD: Direct import causing circular dependency
from archiverr.state.manager import StateManager
```

---

## SUMMARY

### Module Structure

```
core/
  ├── orchestrator.py       # Main coordinator
  ├── config/               # Config management
  ├── plugins/              # Plugin system
  ├── execution/            # Job/stage execution
  ├── triggers/             # Trigger rules
  └── locking/              # FS lock

state/
  ├── models.py             # State data classes
  ├── manager.py            # State manager
  └── queue.py              # Job queue

events/
  ├── bus.py                # Event bus
  └── handlers.py           # Event handlers

infrastructure/
  ├── database.py           # MongoDB
  └── persistence.py        # Persistence layer
```

### Key Principles

```
1. Single Responsibility: Each module has one clear purpose
2. Dependency Injection: Use constructor injection
3. Interface Segregation: Small, focused interfaces
4. Loose Coupling: Minimize dependencies
5. High Cohesion: Related code stays together
```

---

**Next Document**: 07_IMPLEMENTATION_PATTERNS.md
