# IMPLEMENTATION PATTERNS

```yaml
tarih: 2024-12-08
durum: strategy
session: 12
konu: Implementation patterns, best practices, and code examples
```

---

## OVERVIEW

Bu dokümanda Session 12 implementation'ı için kullanılabilecek pattern'ler, best practice'ler ve mantık örnekleri yer alır.

**⚠️ ÖNEMLI**: Kod örnekleri mantığı göstermek içindir, direkt kopyalanmaz. Mevcut codebase'e uyarlanmalıdır.

---

## DEPENDENCY INJECTION PATTERN

### Constructor Injection

```python
class Orchestrator:
    """
    All dependencies injected via constructor
    Makes testing easy and dependencies explicit
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        state: StateManager,
        persistence: PersistenceInterface,
        plugin_registry: PluginRegistry,
        config: Dict[str, Any],
        logger: Logger
    ):
        self._event_bus = event_bus
        self._state = state
        self._persistence = persistence
        self._plugin_registry = plugin_registry
        self._config = config
        self._logger = logger
```

### Factory Pattern

```python
def build_orchestrator(config: Dict) -> Orchestrator:
    """
    Factory function for dependency wiring
    
    Centralizes object creation and dependency management
    """
    # Create logger
    logger = create_logger(config.get("options", {}).get("debug", False))
    
    # Create event bus
    event_bus = EventBus(logger=logger)
    
    # Create state manager
    state = StateManager(event_bus=event_bus, logger=logger)
    
    # Create persistence
    persistence = create_persistence(config)
    
    # Create plugin registry
    plugin_registry = PluginRegistry(
        config=config,
        logger=logger
    )
    
    # Wire orchestrator
    return Orchestrator(
        event_bus=event_bus,
        state=state,
        persistence=persistence,
        plugin_registry=plugin_registry,
        config=config,
        logger=logger
    )
```

---

## STATE MANAGEMENT PATTERNS

### Immutable State Updates

```python
class StateManager:
    """
    State updates create new objects, never mutate existing
    
    Benefits:
    - Thread-safe
    - History tracking possible
    - Debugging easier
    """
    
    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """
        Update job state (internal method)
        Called by PluginServices.updateJob(key, value)
        PluginServices provides job_id internally
        """
        # Get current job
        job = self._jobs[job_id]
        
        # Create updated job (copy + update)
        updated_job = self._deep_copy_job(job)
        self._set_nested_value(updated_job, key, value)
        
        # Replace in state
        self._jobs[job_id] = updated_job
        
        # Emit event
        self._event_bus.emit("job.updated", {
            "job_id": job_id,
            "key": key,
            "value": value
        })
```

### State Snapshot Pattern

```python
class StateManager:
    """
    Capture state snapshots for rollback or debugging
    """
    
    def __init__(self):
        self._current_state = {}
        self._snapshots = []
    
    def create_snapshot(self, label: str) -> str:
        """Create labeled snapshot of current state"""
        snapshot_id = generate_id()
        
        self._snapshots.append({
            "id": snapshot_id,
            "label": label,
            "timestamp": datetime.now(),
            "state": deepcopy(self._current_state)
        })
        
        return snapshot_id
    
    def restore_snapshot(self, snapshot_id: str) -> None:
        """Restore state from snapshot"""
        snapshot = next(
            (s for s in self._snapshots if s["id"] == snapshot_id),
            None
        )
        
        if snapshot:
            self._current_state = deepcopy(snapshot["state"])
```

---

## PLUGIN EXECUTION PATTERNS

### Template Method Pattern

```python
class BasePlugin(ABC):
    """
    Template method defines algorithm structure
    Subclasses fill in specific steps
    """
    
    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        """
        Template method - defines execution flow
        
        1. Validate
        2. Process
        3. Update state
        4. Return result
        """
        try:
            # Step 1: Validate
            if not self.validate(job, services):
                return PluginResult.skipped("Validation failed")
            
            # Step 2: Process (implemented by subclass)
            data = self.process(job, services)
            
            # Step 3: Update state
            self.update_state(job, services, data)
            
            # Step 4: Return result
            return PluginResult.success(data)
            
        except Exception as e:
            return PluginResult.failed(str(e))
    
    def validate(self, job: JobState, services: PluginServices) -> bool:
        """Hook method - can be overridden"""
        return True
    
    @abstractmethod
    def process(self, job: JobState, services: PluginServices) -> Dict:
        """Abstract method - must be implemented"""
        pass
    
    def update_state(
        self, 
        job: JobState, 
        services: PluginServices,
        data: Dict
    ) -> None:
        """Hook method - default implementation"""
        services.updatePlugin(data)  # 🔴 Name yok, current plugin
```

### Strategy Pattern for Plugin Modes

```python
class PluginExecutionStrategy(ABC):
    """Base strategy for plugin execution"""
    
    @abstractmethod
    def execute(self, plugin: BasePlugin, context: ExecutionContext) -> PluginResult:
        pass


class PerRunStrategy(PluginExecutionStrategy):
    """Strategy for per_run plugins"""
    
    def execute(self, plugin: BasePlugin, context: ExecutionContext) -> PluginResult:
        services = PluginServices(
            state=context.state,
            event_bus=context.event_bus,
            logger=context.logger,
            config=context.config,
            mode="per_run"
        )
        
        return plugin.execute_run(services)


class PerJobStrategy(PluginExecutionStrategy):
    """Strategy for per_job plugins"""
    
    def execute(self, plugin: BasePlugin, context: ExecutionContext) -> PluginResult:
        services = PluginServices(
            state=context.state,
            event_bus=context.event_bus,
            logger=context.logger,
            config=context.config,
            mode="per_job"
        )
        
        return plugin.execute(context.job, services)


class PluginExecutor:
    """Context class using strategies"""
    
    def execute_plugin(
        self,
        plugin: BasePlugin,
        context: ExecutionContext
    ) -> PluginResult:
        # Select strategy based on plugin mode
        strategy = (
            PerRunStrategy() if plugin.mode == "per_run"
            else PerJobStrategy()
        )
        
        return strategy.execute(plugin, context)
```

---

## ERROR HANDLING PATTERNS

### Result Pattern (Railway-Oriented)

```python
from typing import Generic, TypeVar, Union
from dataclasses import dataclass

T = TypeVar('T')
E = TypeVar('E')


@dataclass
class Success(Generic[T]):
    value: T


@dataclass
class Failure(Generic[E]):
    error: E


Result = Union[Success[T], Failure[E]]


def divide(a: int, b: int) -> Result[float, str]:
    """
    Result pattern for explicit error handling
    No exceptions, explicit success/failure
    """
    if b == 0:
        return Failure("Division by zero")
    
    return Success(a / b)


# Usage
result = divide(10, 2)

if isinstance(result, Success):
    print(f"Result: {result.value}")
else:
    print(f"Error: {result.error}")
```

### Error Recovery Pattern

```python
class PluginExecutor:
    """
    Plugin execution with retry and fallback
    """
    
    def execute_with_recovery(
        self,
        plugin: BasePlugin,
        job: JobState,
        services: PluginServices,
        max_retries: int = 3
    ) -> PluginResult:
        """
        Execute plugin with automatic retry
        
        Pattern:
        1. Try execute
        2. If fails, retry with backoff
        3. If all retries fail, use fallback
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = plugin.execute(job, services)
                
                if result.status == "success":
                    return result
                
                last_error = result.error
                
                # Exponential backoff
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                
            except Exception as e:
                last_error = str(e)
                
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # All retries failed, try fallback
        return self._try_fallback(plugin, job, services, last_error)
    
    def _try_fallback(
        self,
        plugin: BasePlugin,
        job: JobState,
        services: PluginServices,
        original_error: str
    ) -> PluginResult:
        """Fallback execution if plugin has one"""
        if hasattr(plugin, 'fallback'):
            try:
                return plugin.fallback(job, services, original_error)
            except:
                pass
        
        return PluginResult.failed(f"All retries failed: {original_error}")
```

---

## CONCURRENCY PATTERNS

### Thread-Safe Lock Manager

```python
import threading
from contextlib import contextmanager


class FSLockManager:
    """
    Thread-safe file system lock manager
    
    Uses context manager for automatic lock release
    """
    
    def __init__(self):
        self._locks: Dict[str, str] = {}
        self._lock = threading.Lock()
    
    @contextmanager
    def acquire(self, path: str, plugin_name: str):
        """
        Context manager for lock acquisition
        
        Usage:
            with lock_manager.acquire("/path", "plugin"):
                # Do file operations
                pass
        """
        # Acquire lock
        with self._lock:
            if path in self._locks:
                raise FSLockError(
                    f"Path {path} already locked by {self._locks[path]}"
                )
            self._locks[path] = plugin_name
        
        try:
            yield
        finally:
            # Release lock
            with self._lock:
                if path in self._locks:
                    del self._locks[path]
```

### Producer-Consumer Pattern (Job Queue)

```python
import queue
import threading


class JobQueue:
    """
    Thread-safe job queue with producer-consumer pattern
    """
    
    def __init__(self, max_size: int = 0):
        self._queue = queue.Queue(maxsize=max_size)
        self._processing = set()
        self._completed = []
        self._failed = []
        self._lock = threading.Lock()
    
    def enqueue(self, job: JobState) -> None:
        """Producer: Add job to queue"""
        self._queue.put(job)
    
    def dequeue(self, timeout: float = None) -> Optional[JobState]:
        """Consumer: Get job from queue"""
        try:
            job = self._queue.get(timeout=timeout)
            
            with self._lock:
                self._processing.add(job.id)
            
            return job
            
        except queue.Empty:
            return None
    
    def mark_completed(self, job: JobState) -> None:
        """Mark job as completed"""
        with self._lock:
            self._processing.discard(job.id)
            self._completed.append(job)
        
        self._queue.task_done()
    
    def mark_failed(self, job: JobState) -> None:
        """Mark job as failed"""
        with self._lock:
            self._processing.discard(job.id)
            self._failed.append(job)
        
        self._queue.task_done()
    
    def wait_all_done(self) -> None:
        """Wait until all jobs are processed"""
        self._queue.join()
```

---

## EVENT PATTERNS

### Observer Pattern (Event Bus)

```python
from typing import Callable, Dict, List


class EventBus:
    """
    Observer pattern for event-driven communication
    
    Loose coupling between components
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[Dict] = []
    
    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe to event"""
        if event not in self._subscribers:
            self._subscribers[event] = []
        
        self._subscribers[event].append(handler)
    
    def emit(self, event: str, data: Dict = None) -> None:
        """Emit event to all subscribers"""
        event_data = {
            "event": event,
            "data": data or {},
            "timestamp": datetime.now()
        }
        
        # Add to history
        self._history.append(event_data)
        
        # Notify subscribers
        if event in self._subscribers:
            for handler in self._subscribers[event]:
                try:
                    handler(event_data)
                except Exception as e:
                    # Log but don't fail
                    print(f"Event handler failed: {e}")
    
    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Unsubscribe from event"""
        if event in self._subscribers:
            self._subscribers[event].remove(handler)


# Usage
event_bus = EventBus()

def on_job_completed(event):
    print(f"Job completed: {event['data']['job_id']}")

event_bus.subscribe("job.completed", on_job_completed)
event_bus.emit("job.completed", {"job_id": "job_123"})
```

### Event Sourcing Pattern (Optional)

```python
class EventStore:
    """
    Store all events for replay and debugging
    
    Can reconstruct state from events
    """
    
    def __init__(self):
        self._events: List[Dict] = []
    
    def append(self, event: Dict) -> None:
        """Append event to store"""
        self._events.append({
            **event,
            "sequence": len(self._events)
        })
    
    def replay(self, from_sequence: int = 0) -> List[Dict]:
        """Get events from sequence number"""
        return [
            e for e in self._events
            if e["sequence"] >= from_sequence
        ]
    
    def reconstruct_state(self, state_builder: 'StateBuilder') -> Any:
        """Reconstruct state by replaying events"""
        for event in self._events:
            state_builder.apply_event(event)
        
        return state_builder.get_state()
```

---

## VALIDATION PATTERNS

### Chain of Responsibility Pattern

```python
from abc import ABC, abstractmethod


class Validator(ABC):
    """Base validator in chain"""
    
    def __init__(self):
        self._next: Optional[Validator] = None
    
    def set_next(self, validator: 'Validator') -> 'Validator':
        """Set next validator in chain"""
        self._next = validator
        return validator
    
    def validate(self, data: Dict) -> List[str]:
        """Validate and pass to next"""
        errors = self._check(data)
        
        if self._next:
            errors.extend(self._next.validate(data))
        
        return errors
    
    @abstractmethod
    def _check(self, data: Dict) -> List[str]:
        """Actual validation logic"""
        pass


class RequiredFieldsValidator(Validator):
    """Check required fields"""
    
    def __init__(self, required_fields: List[str]):
        super().__init__()
        self._required_fields = required_fields
    
    def _check(self, data: Dict) -> List[str]:
        errors = []
        
        for field in self._required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        return errors


class TypeValidator(Validator):
    """Check field types"""
    
    def __init__(self, type_map: Dict[str, type]):
        super().__init__()
        self._type_map = type_map
    
    def _check(self, data: Dict) -> List[str]:
        errors = []
        
        for field, expected_type in self._type_map.items():
            if field in data and not isinstance(data[field], expected_type):
                errors.append(
                    f"Field {field} must be {expected_type.__name__}"
                )
        
        return errors


# Usage
validator_chain = RequiredFieldsValidator(["name", "version"])
validator_chain.set_next(TypeValidator({"name": str, "version": str}))

errors = validator_chain.validate({"name": "plugin", "version": 1.0})
# Returns: ["Field version must be str"]
```

---

## CONFIGURATION PATTERNS

### Builder Pattern for Config

```python
class ConfigBuilder:
    """
    Builder pattern for complex config construction
    
    Fluent interface for config building
    """
    
    def __init__(self):
        self._config = {}
    
    def with_options(self, **options) -> 'ConfigBuilder':
        """Set options"""
        if "options" not in self._config:
            self._config["options"] = {}
        
        self._config["options"].update(options)
        return self
    
    def with_plugin(self, name: str, config: Dict) -> 'ConfigBuilder':
        """Add plugin config"""
        self._config[name] = config
        return self
    
    def with_aliases(self, **aliases) -> 'ConfigBuilder':
        """Add aliases"""
        if "aliases" not in self._config:
            self._config["aliases"] = {}
        
        self._config["aliases"].update(aliases)
        return self
    
    def merge_from_file(self, path: str) -> 'ConfigBuilder':
        """Merge config from file"""
        file_config = load_yaml(path)
        self._config = deep_merge(self._config, file_config)
        return self
    
    def freeze(self) -> Dict:
        """Build and freeze config"""
        return deepcopy(self._config)


# Usage
config = (
    ConfigBuilder()
    .with_options(debug=True, dry_run=False)
    .with_plugin("tmdb", {"api_key": "xxx"})
    .with_aliases(m="plugin.tmdb.data.movie")  # 🔴 .data eklendi
    .merge_from_file("user-config.yml")
    .freeze()
)
```

### Strategy Pattern for Config Loading

```python
class ConfigLoader(ABC):
    """Base config loader"""
    
    @abstractmethod
    def load(self, source: str) -> Dict:
        pass


class YAMLConfigLoader(ConfigLoader):
    """Load config from YAML"""
    
    def load(self, source: str) -> Dict:
        with open(source) as f:
            return yaml.safe_load(f)


class JSONConfigLoader(ConfigLoader):
    """Load config from JSON"""
    
    def load(self, source: str) -> Dict:
        with open(source) as f:
            return json.load(f)


class ConfigLoaderFactory:
    """Factory for config loaders"""
    
    @staticmethod
    def create(file_path: str) -> ConfigLoader:
        ext = Path(file_path).suffix
        
        if ext in [".yml", ".yaml"]:
            return YAMLConfigLoader()
        elif ext == ".json":
            return JSONConfigLoader()
        else:
            raise ValueError(f"Unsupported config format: {ext}")


# Usage
loader = ConfigLoaderFactory.create("config.yml")
config = loader.load("config.yml")
```

---

## TESTING PATTERNS

### Mock Services for Plugin Testing

```python
class MockPluginServices(PluginServices):
    """
    Mock services for plugin testing
    
    Captures method calls for assertions
    """
    
    def __init__(self, mode: str = "per_job"):
        self._mode = mode
        self._created_jobs = []
        self._updated_jobs = []
        self._updated_plugins = []
        self._emitted_events = []
        self._mock_state = {}
    
    def create_job(self, input_value: str, input_data: Dict) -> str:
        job_id = f"job_{len(self._created_jobs)}"
        self._created_jobs.append({
            "job_id": job_id,
            "input_value": input_value,
            "input_data": input_data
        })
        return job_id
    
    def updateJob(self, key: str, value: Any) -> None:
        """Update current job (no job_id)"""
        self._updated_jobs.append({
            "key": key,
            "value": value
        })
    
    def updatePlugin(self, data: Dict) -> None:
        """Update current plugin (no plugin_name)"""
        self._updated_plugins.append({
            "data": data
        })
    
    def emit(self, event: str, data: Dict = None) -> None:
        self._emitted_events.append({
            "event": event,
            "data": data
        })
    
    # Assertion helpers
    def assert_job_created(self, input_value: str) -> None:
        assert any(
            j["input_value"] == input_value
            for j in self._created_jobs
        ), f"No job created with input_value={input_value}"
    
    def assert_plugin_updated(self) -> None:
        """Assert that current plugin was updated"""
        assert len(self._updated_plugins) > 0, "Plugin was not updated"


# Usage in test
def test_tmdb_plugin():
    # Arrange
    services = MockPluginServices(mode="per_job")
    plugin = TMDbPlugin("tmdb", {"api_key": "test"})
    
    job = create_test_job(
        input_value="/path/to/Movie.2024.mkv",
        plugins={
            "renamer": {
                "data": {  # 🔴 data eklendi
                    "parsed": {"movie": {"name": "Movie", "year": 2024}}
                }
            }
        }
    )
    
    # Act
    result = plugin.execute(job, services)
    
    # Assert
    assert result.status == "success"
    services.assert_plugin_updated()
    assert "movie" in services._updated_plugins[0]["data"]
```

### Fixture Pattern for Test Data

```python
import pytest


@pytest.fixture
def test_config():
    """Fixture for test config"""
    return {
        "options": {"debug": True, "dry_run": True},
        "tmdb": {"api_key": "test_key"},
        "scanner": {"targets": ["/test/movies"]}
    }


@pytest.fixture
def test_job():
    """Fixture for test job"""
    return JobState(
        index=0,
        id="test_job_0",
        run_id="test_run",
        input={
            "value": "/test/Movie.2024.mkv",
            "data": {"size_bytes": 1000000}
        },
        output={"values": [], "data": {}},
        status={
            "state": "pending",
            "success": False,
            "executed": [],
            "failed": [],
            "skipped": []
        }
    )


@pytest.fixture
def mock_services():
    """Fixture for mock services"""
    return MockPluginServices(mode="per_job")


# Usage
def test_plugin_execution(test_job, mock_services):
    plugin = MyPlugin("test", {})
    result = plugin.execute(test_job, mock_services)
    assert result.status == "success"
```

---

## LOGGING PATTERNS

### Structured Logging

```python
import json
from datetime import datetime


class StructuredLogger:
    """
    Structured logging for better log analysis
    
    Logs as JSON for easy parsing
    """
    
    def __init__(self, component: str, debug: bool = False):
        self._component = component
        self._debug = debug
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal log method"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "component": self._component,
            "message": message,
            **kwargs
        }
        
        print(json.dumps(log_entry))
    
    def debug(self, message: str, **kwargs):
        if self._debug:
            self._log("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)
    
    def warn(self, message: str, **kwargs):
        self._log("WARN", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)


# Usage
logger = StructuredLogger("orchestrator", debug=True)
logger.info("Job started", job_id="job_123", run_id="run_456")
logger.error("Plugin failed", plugin="tmdb", error="API timeout")
```

### Context Manager for Logging

```python
from contextlib import contextmanager
import time


@contextmanager
def log_execution(logger: Logger, operation: str, **context):
    """
    Context manager for automatic execution logging
    
    Usage:
        with log_execution(logger, "job_execution", job_id="123"):
            execute_job(job)
    """
    start_time = time.time()
    
    logger.info(f"{operation} started", **context)
    
    try:
        yield
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"{operation} completed",
            duration_ms=duration_ms,
            **context
        )
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            f"{operation} failed",
            error=str(e),
            duration_ms=duration_ms,
            **context
        )
        raise
```

---

## PERFORMANCE PATTERNS

### Lazy Loading Pattern

```python
class LazyPluginRegistry:
    """
    Lazy load plugins on first access
    
    Improves startup time
    """
    
    def __init__(self, plugin_dir: str):
        self._plugin_dir = plugin_dir
        self._manifests: Dict[str, Dict] = {}
        self._loaded_plugins: Dict[str, BasePlugin] = {}
    
    def discover_manifests(self) -> None:
        """Only load manifests, not plugin classes"""
        for plugin_path in Path(self._plugin_dir).iterdir():
            if plugin_path.is_dir():
                manifest_path = plugin_path / "manifest.yml"
                if manifest_path.exists():
                    manifest = load_yaml(manifest_path)
                    self._manifests[manifest["name"]] = manifest
    
    def get_plugin(self, name: str) -> BasePlugin:
        """Lazy load plugin on first access"""
        if name not in self._loaded_plugins:
            manifest = self._manifests[name]
            plugin_class = self._load_plugin_class(name, manifest)
            self._loaded_plugins[name] = plugin_class(name, {})
        
        return self._loaded_plugins[name]
```

### Caching Pattern

```python
from functools import lru_cache


class CachedStateResolver:
    """
    Cache state resolution for performance
    
    Invalidate cache on state updates
    """
    
    def __init__(self, state: StateManager):
        self._state = state
        self._cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def resolve_path(self, path: str) -> Any:
        """Resolve with caching"""
        if path in self._cache:
            self._cache_hits += 1
            return self._cache[path]
        
        self._cache_misses += 1
        value = self._resolve_uncached(path)
        self._cache[path] = value
        return value
    
    def invalidate(self, path_prefix: str = None):
        """Invalidate cache after state updates"""
        if path_prefix:
            # Invalidate only matching paths
            keys_to_remove = [
                k for k in self._cache.keys()
                if k.startswith(path_prefix)
            ]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            # Invalidate all
            self._cache.clear()
    
    @property
    def cache_stats(self) -> Dict:
        """Get cache statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
            "size": len(self._cache)
        }
```

---

## SUMMARY

### Key Patterns

| Pattern | Use Case | Benefit |
|---------|----------|---------|
| Dependency Injection | Component wiring | Testability, flexibility |
| Factory | Object creation | Centralized config |
| Template Method | Plugin algorithm | Code reuse |
| Strategy | Plugin modes | Flexibility |
| Observer | Event system | Loose coupling |
| Builder | Config construction | Fluent API |
| Chain of Responsibility | Validation | Extensibility |
| Result | Error handling | Explicit errors |
| Context Manager | Resource management | Automatic cleanup |
| Lazy Loading | Plugin loading | Performance |

### Best Practices

```
1. Prefer composition over inheritance
2. Use dependency injection for testability
3. Make state updates immutable
4. Use context managers for resource cleanup
5. Log structured data for analysis
6. Cache expensive operations
7. Validate at boundaries
8. Handle errors explicitly
9. Use type hints for clarity
10. Write tests with fixtures and mocks
```

### Anti-Patterns to Avoid

```
❌ Global state (use dependency injection)
❌ God objects (split responsibilities)
❌ Magic numbers (use constants)
❌ Mutable defaults (use None, create in function)
❌ Catching all exceptions (catch specific)
❌ Silent failures (log and propagate)
❌ Circular imports (use TYPE_CHECKING)
❌ Premature optimization (profile first)
```

---

**End of Session 12 Strategy Documents**

## Strategy Complete

All 7 strategy documents created:
1. ✅ Executive Summary
2. ✅ Global State Architecture
3. ✅ Plugin System Refactoring
4. ✅ Trigger Rule System
5. ✅ Job Lifecycle and Execution
6. ✅ File Structure and Modules
7. ✅ Implementation Patterns

**FINAL_DATASETS.yml** also updated with new structure.

**Next Step**: Implementation başlangıcı
