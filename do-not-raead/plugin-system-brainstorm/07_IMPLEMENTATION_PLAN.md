# IMPLEMENTATION PLAN

```yaml
date: 2025-12-02
type: execution-plan
status: final
```

---

## 1. SUMMARY OF CHANGES

```
DOCUMENT                  KEY CHANGES
------------------------------------------------------------------
01_MANIFEST_SCHEMA        stage, mode, provides, requires
02_PROVIDES_SYSTEM        Generic capabilities (data, io, network)
03_STAGE_EXECUTION        4-stage model, StageExecutor
04_EVENTBUS_SERVICES      PluginServices injection
05_CONFIG_SYSTEM          FlexGet-style, no plugins: wrapper
06_STATE_MODEL            Run/Job terminology, nested dataclasses
```

---

## 2. IMPLEMENTATION PHASES

```
PHASE 1: Foundation (Est. 4 hours)
    - State models (Run, Job, nested dataclasses)
    - StateManager API updates
    - Backward compatibility aliases

PHASE 2: Plugin System (Est. 6 hours)
    - Manifest schema update
    - PluginServices implementation
    - Capability tracking

PHASE 3: Execution (Est. 4 hours)
    - StageExecutor
    - Orchestrator refactor
    - Config loading updates

PHASE 4: Migration (Est. 2 hours)
    - Plugin manifest updates
    - Config.yml updates
    - Test updates

TOTAL: ~16 hours
```

---

## 3. FILE CHANGES

### 3.1 New Files

```
core/
    orchestrator.py              # ~200 lines - Central coordinator
    plugins/
        services.py              # ~150 lines - PluginServices
        stage_executor.py        # ~200 lines - Stage-based execution
        capability.py            # ~80 lines - CapabilityTracker

state/
    models.py                    # REWRITE ~250 lines
```

### 3.2 Modified Files

```
core/plugins/
    discovery.py                 # +50 lines - stage/mode support
    sdk/manifest.py              # +30 lines - new fields

__main__.py                      # -150 lines (move to orchestrator)

infrastructure/config/
    loader.py                    # +100 lines - FlexGet-style
```

### 3.3 Plugin Manifests

```
plugins/scanner/manifest.yml     # +stage, +mode, +provides
plugins/renamer/manifest.yml     # +stage, +requires, +provides
plugins/tmdb/manifest.yml        # +stage, +requires, +provides
plugins/ffprobe/manifest.yml     # +stage, +requires, +provides
```

---

## 4. DETAILED IMPLEMENTATION

### 4.1 Phase 1: State Models

```python
# state/models.py - Complete rewrite

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class StateEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RunStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0


@dataclass
class RunStats:
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0


@dataclass
class Run:
    id: str
    status: RunStatus = field(default_factory=RunStatus)
    stats: RunStats = field(default_factory=RunStats)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobInput:
    path: str
    category: str = "unknown"


@dataclass
class JobStatus:
    state: StateEnum = StateEnum.PENDING
    success: bool = True
    executed_plugins: List[str] = field(default_factory=list)
    failed_plugins: List[str] = field(default_factory=list)
    skipped_plugins: List[str] = field(default_factory=list)


@dataclass
class Job:
    id: str
    run_id: str
    index: int
    input: JobInput
    status: JobStatus = field(default_factory=JobStatus)
    plugins: Dict[str, Any] = field(default_factory=dict)


# Backward compatibility
ExecutionState = Run
MatchState = Job
```

### 4.2 Phase 2: Plugin Services

```python
# core/plugins/services.py

@dataclass
class PluginServices:
    state: 'StateService'
    events: 'EventService'
    logger: 'LogService'
    config: 'ConfigService'


class StateService:
    def __init__(self, manager: StateManager):
        self._manager = manager
        self._current_job: Optional[Job] = None
    
    def get_current_job(self) -> Job:
        return self._current_job
    
    def get_all_jobs(self) -> List[Job]:
        return self._manager.get_all_jobs()


class EventService:
    def __init__(self, bus: EventBus):
        self._bus = bus
    
    def emit(self, event: str, data: Dict = None):
        self._bus.emit(event, data or {})


class LogService:
    def __init__(self, debugger, plugin_name: str):
        self._debugger = debugger
        self._name = plugin_name
    
    def info(self, msg: str, **kwargs):
        self._debugger.info(self._name, msg, **kwargs)


class ConfigService:
    def __init__(self, config: Dict):
        self._config = config
    
    def get(self, key: str, default=None):
        # Dot-notation access
        parts = key.split('.')
        value = self._config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
        return value if value is not None else default
```

### 4.3 Phase 3: Stage Executor

```python
# core/plugins/stage_executor.py

class StageExecutor:
    STAGES = ['input', 'parse', 'metadata', 'output']
    
    def __init__(self, registry: PluginRegistry, state: StateManager):
        self._registry = registry
        self._state = state
        self._tracker = CapabilityTracker()
    
    def execute(self) -> Run:
        for stage in self.STAGES:
            self._execute_stage(stage)
        return self._state.complete_run()
    
    def _execute_stage(self, stage: str):
        plugins = self._registry.get_by_stage(stage)
        
        if stage == 'input':
            for plugin in plugins:
                jobs = plugin.execute_run(self._services)
                for job_data in jobs:
                    self._state.register_job(job_data['input']['path'])
                self._tracker.register(plugin.name, plugin.manifest.provides)
        else:
            for job in self._state.get_all_jobs():
                for plugin in plugins:
                    if self._tracker.check(plugin.manifest.requires):
                        result = plugin.execute(job, self._services)
                        self._state.update_plugin(job.id, plugin.name, result)
                        self._tracker.register(plugin.name, result.provides)
```

---

## 5. MIGRATION STEPS

### 5.1 Manifest Migration

```yaml
# BEFORE (tmdb/manifest.yml)
name: tmdb
version: 1.0.0
category: output
depends_on: [renamer]
expects: [renamer.parsed]

# AFTER
name: tmdb
version: 1.0.0
stage: metadata
mode: per_job
requires: [data.parsed]
provides: [data.metadata, network.api]
```

### 5.2 Config Migration

```yaml
# BEFORE (config.yml)
plugins:
  scanner:
    enabled: true
    targets: [/downloads]
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}

tasks:
  - name: print
    type: print

# AFTER
options:
  debug: true

scanner:
  targets: [/downloads]

tmdb:
  api_key: ${TMDB_API_KEY}

tasker:
  tasks:
    - name: print
      type: print
```

---

## 6. TESTING STRATEGY

```
UNIT TESTS:
    tests/unit/state/test_models.py      # Run, Job dataclasses
    tests/unit/core/test_services.py     # PluginServices
    tests/unit/core/test_capability.py   # CapabilityTracker
    tests/unit/core/test_stage.py        # StageExecutor

INTEGRATION TESTS:
    tests/integration/test_execution.py  # Full run flow
    tests/integration/test_plugins.py    # Plugin loading
```

---

## 7. ROLLBACK PLAN

```
If issues arise:

1. Backward compatibility aliases exist
2. Old config format still loadable
3. Old manifest fields still parsed
4. StateManager old methods still work

To rollback:
    git revert <commit>
    # No data migration needed
```

---

## 8. SUCCESS CRITERIA

```
[ ] All existing tests pass
[ ] Scanner -> Renamer -> TMDb flow works
[ ] Config.yml both formats accepted
[ ] Manifests both formats accepted
[ ] Events emitted correctly
[ ] MongoDB persistence unchanged
```

---

## 9. EXECUTION ORDER

```
1. Create new state/models.py
2. Update StateManager with new API
3. Create core/plugins/services.py
4. Create core/plugins/capability.py
5. Create core/plugins/stage_executor.py
6. Create core/orchestrator.py
7. Update __main__.py to use Orchestrator
8. Update manifest.py for new fields
9. Update discovery.py for stage/mode
10. Migrate plugin manifests
11. Migrate config.yml
12. Run all tests
```

---

**Status: FINAL - Ready for execution**
