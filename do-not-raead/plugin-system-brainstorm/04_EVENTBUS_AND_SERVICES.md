# EVENTBUS AND PLUGIN SERVICES

```yaml
date: 2025-12-02
type: technical-spec
status: final
```

---

## 1. CURRENT STATE

### 1.1 EventBus (events/bus.py - 286 lines)

```python
# EXISTING - Working correctly
class Events:
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    MATCH_STARTED = "match.started"
    MATCH_COMPLETED = "match.completed"
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    # ... etc

class EventBus:
    def subscribe(self, event_name: str, handler: Callable)
    def emit(self, event_name: str, data: Dict)
```

### 1.2 ExecutionContext (sdk/context.py)

```python
# EXISTING - Partially used
class ExecutionContext:
    execution_id: str
    match_index: int
    config: Dict
    debugger: Debugger
    event_bus: EventBus
    task_manager: TaskManager
```

**Problems:**
- Plugins don't consistently use context
- Services scattered across context
- No clear service interface

---

## 2. PROPOSED SERVICE ARCHITECTURE

```
+------------------------------------------------------------------+
|                      PLUGIN SERVICES                              |
+------------------------------------------------------------------+
|                                                                   |
|  class PluginServices:                                           |
|      """Single access point for all plugin runtime needs"""      |
|                                                                   |
|      state: StateService      # Job/Run access                   |
|      events: EventService     # Event emission                   |
|      logger: LogService       # Logging                          |
|      config: ConfigService    # Config access                    |
|                                                                   |
+------------------------------------------------------------------+
            |
            v
+------------------------------------------------------------------+
|                      SERVICE INTERFACES                           |
+------------------------------------------------------------------+
|                                                                   |
|  StateService:                                                   |
|    - get_job(job_id) -> Job                                      |
|    - get_jobs() -> List[Job]                                     |
|    - get_run() -> Run                                            |
|                                                                   |
|  EventService:                                                   |
|    - emit(event: str, data: Dict)                                |
|    - subscribe(event: str, handler: Callable)                    |
|                                                                   |
|  LogService:                                                     |
|    - debug(msg, **kwargs)                                        |
|    - info(msg, **kwargs)                                         |
|    - warn(msg, **kwargs)                                         |
|    - error(msg, **kwargs)                                        |
|                                                                   |
|  ConfigService:                                                  |
|    - get(key: str, default=None) -> Any                          |
|    - get_plugin_config(plugin_name: str) -> Dict                 |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 3. EVENT NAMING CONVENTION

```
FORMAT: {domain}.{action}

DOMAIN          ACTIONS                 EXAMPLE
--------------------------------------------------------------------
run             started, completed,     run.started
                failed                  run.completed

job             started, completed,     job.started
                failed, skipped         job.completed

stage           started, completed      stage.started

plugin          started, completed,     plugin.completed
                failed, skipped         plugin.failed

state           changed                 state.changed

capability      provided                capability.provided
```

---

## 4. SYSTEM EVENTS SCHEMA

```
+------------------------------------------------------------------+
|                      SYSTEM EVENTS                                |
+------------------------------------------------------------------+
|                                                                   |
|  RUN LIFECYCLE:                                                  |
|                                                                   |
|    run.started -----> stage.started (input)                      |
|                            |                                      |
|                            v                                      |
|                       job.started                                |
|                            |                                      |
|                            v                                      |
|                       plugin.started --> plugin.completed         |
|                            |                    |                 |
|                            v                    v                 |
|                       capability.provided                        |
|                            |                                      |
|                            v                                      |
|                       job.completed                              |
|                            |                                      |
|                            v                                      |
|                       stage.completed                            |
|                            |                                      |
|                            v                                      |
|    run.completed <----- (repeat for each stage)                  |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 5. EVENT PAYLOADS

```python
# run.started
{
    "run_id": "abc123",
    "config": {...},
    "timestamp": "2025-12-02T14:30:00Z"
}

# run.completed
{
    "run_id": "abc123",
    "success": True,
    "total_jobs": 10,
    "completed_jobs": 10,
    "failed_jobs": 0,
    "duration_ms": 45000
}

# job.started
{
    "run_id": "abc123",
    "job_id": "job_abc123_0",
    "index": 0,
    "input_path": "/media/file.mkv"
}

# job.completed
{
    "run_id": "abc123",
    "job_id": "job_abc123_0",
    "index": 0,
    "success": True,
    "executed_plugins": ["scanner", "renamer", "tmdb"],
    "failed_plugins": [],
    "duration_ms": 2500
}

# plugin.completed
{
    "run_id": "abc123",
    "job_id": "job_abc123_0",
    "plugin_name": "tmdb",
    "success": True,
    "provides": ["data.metadata"],
    "duration_ms": 800
}

# capability.provided
{
    "run_id": "abc123",
    "job_id": "job_abc123_0",
    "plugin_name": "tmdb",
    "capabilities": ["data.metadata", "network.api"]
}

# stage.started
{
    "run_id": "abc123",
    "stage": "metadata",
    "job_count": 10
}

# stage.completed
{
    "run_id": "abc123",
    "stage": "metadata",
    "duration_ms": 15000,
    "jobs_processed": 10
}
```

---

## 6. SERVICES IMPLEMENTATION

```python
@dataclass
class PluginServices:
    """Services injected into plugins during execution"""
    
    state: 'StateService'
    events: 'EventService'
    logger: 'LogService'
    config: 'ConfigService'
    
    @classmethod
    def build(cls, state: StateManager, event_bus: EventBus, 
              debugger: Debugger, config: Dict) -> 'PluginServices':
        return cls(
            state=StateService(state),
            events=EventService(event_bus),
            logger=LogService(debugger),
            config=ConfigService(config)
        )


class StateService:
    """Job and run state access for plugins"""
    
    def __init__(self, state_manager: StateManager):
        self._state = state_manager
    
    def get_current_job(self) -> Optional[Job]:
        """Get current job (set by executor)"""
        return self._current_job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get specific job by ID"""
        return self._state.get_job_by_id(job_id)
    
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs in current run"""
        return self._state.get_all_jobs()
    
    def get_run(self) -> Run:
        """Get current run state"""
        return self._state.get_current_run()


class EventService:
    """Event emission for plugins"""
    
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
    
    def emit(self, event: str, data: Dict = None):
        """Emit an event"""
        self._bus.emit(event, data or {})
    
    # Note: Plugins should NOT subscribe to events
    # Subscription is for orchestrator/handlers only


class LogService:
    """Logging for plugins"""
    
    def __init__(self, debugger: Debugger, plugin_name: str = "plugin"):
        self._debugger = debugger
        self._plugin_name = plugin_name
    
    def debug(self, msg: str, **kwargs):
        self._debugger.debug(self._plugin_name, msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        self._debugger.info(self._plugin_name, msg, **kwargs)
    
    def warn(self, msg: str, **kwargs):
        self._debugger.warn(self._plugin_name, msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        self._debugger.error(self._plugin_name, msg, **kwargs)


class ConfigService:
    """Config access for plugins"""
    
    def __init__(self, config: Dict):
        self._config = config
    
    def get(self, key: str, default=None):
        """Get config value by dot-notation key"""
        parts = key.split('.')
        value = self._config
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
    
    def get_options(self) -> Dict:
        """Get options section"""
        return self._config.get('options', {})
```

---

## 7. PLUGIN USAGE PATTERN

```python
class TMDbPlugin(OutputPlugin):
    def execute(self, job: Job, services: PluginServices) -> PluginResult:
        # Logging
        services.logger.info("Starting TMDb lookup", 
                           title=job.parsed.movie.name)
        
        # Config access
        api_key = services.config.get('plugins.tmdb.api_key')
        language = services.config.get('plugins.tmdb.language', 'en-US')
        
        # State access (if needed)
        all_jobs = services.state.get_all_jobs()
        
        # API call
        result = self._search_movie(api_key, job.parsed.movie)
        
        # Event emission (optional)
        services.events.emit('tmdb.movie.found', {
            'job_id': job.id,
            'movie_id': result['id']
        })
        
        return PluginResult.success(
            data={'movie': result},
            provides=['data.metadata']
        )
```

---

## 8. EXECUTOR INTEGRATION

```
+------------------------------------------------------------------+
|                   EXECUTOR FLOW                                   |
+------------------------------------------------------------------+
|                                                                   |
|  for job in jobs:                                                |
|      services = PluginServices.build(                            |
|          state=state_manager,                                    |
|          event_bus=event_bus,                                    |
|          debugger=debugger,                                      |
|          config=config                                           |
|      )                                                           |
|      services.state._current_job = job                           |
|      services.logger._plugin_name = plugin.name                  |
|                                                                   |
|      event_bus.emit('plugin.started', {                          |
|          'job_id': job.id,                                       |
|          'plugin_name': plugin.name                              |
|      })                                                          |
|                                                                   |
|      try:                                                        |
|          result = plugin.execute(job, services)                  |
|          event_bus.emit('plugin.completed', {                    |
|              'job_id': job.id,                                   |
|              'plugin_name': plugin.name,                         |
|              'success': result.success,                          |
|              'provides': result.provides                         |
|          })                                                      |
|      except Exception as e:                                      |
|          event_bus.emit('plugin.failed', {                       |
|              'job_id': job.id,                                   |
|              'plugin_name': plugin.name,                         |
|              'error': str(e)                                     |
|          })                                                      |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 9. MIGRATION FROM EXECUTIONCONTEXT

```
CURRENT (ExecutionContext):
    execution_id: str
    match_index: int
    total_matches: int
    config: Dict
    dry_run: bool
    debug: bool
    debugger: Debugger
    event_bus: EventBus
    task_manager: TaskManager
    api_response: Dict
    previous_results: Dict

PROPOSED (PluginServices):
    state: StateService         # replaces match_index, total_matches, api_response
    events: EventService        # replaces event_bus
    logger: LogService          # replaces debugger
    config: ConfigService       # replaces config, dry_run, debug

MIGRATION:
    1. Keep ExecutionContext for backward compatibility
    2. Add PluginServices as preferred interface
    3. Deprecate ExecutionContext in future version
```

---

## CHANGELOG

```
- Added: PluginServices as single injection point
- Added: StateService, EventService, LogService, ConfigService
- Added: Standardized event payloads
- Added: capability.provided event
- Deprecated: Direct ExecutionContext usage
```

---

**Status: FINAL - Ready for implementation**
