# SESSION 7 STRATEGY

```yaml
date: 2025-11-28
type: strategy
status: ready_for_execution
```

---

## TASK 1: EventBus DI Refactor

### Target File
`src/archiverr/events/bus.py`

### Current State (Wrong)
```python
class EventBus:
    _instance: Optional['EventBus'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # ...
```

### Target State (Correct)
```python
class EventBus:
    def __init__(self, debugger=None, max_history: int = 1000):
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._history: List[Event] = []
        self._max_history = max_history
        self._lock = Lock()
        self._debugger = debugger
    
    def configure(self, debugger=None, max_history: int = None):
        if debugger is not None:
            self._debugger = debugger
        if max_history is not None:
            self._max_history = max_history
```

### Changes Required
1. Remove `_instance` class variable
2. Remove `__new__` method
3. Remove `_initialized` check in `__init__`
4. Move dependencies to constructor parameters
5. Keep `configure()` for backward compatibility
6. Remove `get_event_bus()` singleton getter at bottom of file

### Files to Update After
- `src/archiverr/__main__.py` - Create EventBus instance, pass to components
- `src/archiverr/events/__init__.py` - Remove `get_event_bus` export if present

### Test Command
```bash
python -m pytest tests/ -v -k "event"
grep -rn "get_event_bus\|EventBus()" src/
```

---

## TASK 2: Subprocess Removal (Preparation)

### Target File
`src/archiverr/api/process_executor.py`

### Current State (Anti-pattern)
```python
result = subprocess.run(
    ['python', '-m', 'archiverr'],
    cwd=str(project_root),
    capture_output=True,
    timeout=timeout
)
```

### Target Architecture
```
core/
├── workers/
│   ├── __init__.py
│   ├── broker.py      # MongoDBBroker setup
│   └── tasks.py       # Taskiq task definitions
```

### Dependencies to Add
```
taskiq>=0.11.0
taskiq-mongodb>=1.0.0
```

### Implementation Steps
1. Create `src/archiverr/core/workers/` directory
2. Create `broker.py`:
```python
from taskiq_mongodb import MongoDBBroker
import os

broker = MongoDBBroker(
    uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
    database="archiverr_tasks"
)
```

3. Create `tasks.py`:
```python
from .broker import broker
from archiverr.core.services.execution_service import ExecutionService

@broker.task
async def run_execution(config: dict, targets: list = None):
    service = ExecutionService(config)
    return await service.execute(targets)
```

4. Update `api/process_executor.py` to use task queue instead of subprocess

### Note
Full implementation requires ExecutionService async refactor. This session prepares the structure.

---

## TASK 3: Plugin SDK Structure (Preparation)

### Target Structure
```
src/archiverr/plugins/
├── sdk/
│   ├── __init__.py
│   ├── base.py          # Move from plugins/base.py
│   ├── manifest.py      # PluginManifest Pydantic model
│   ├── context.py       # ExecutionContext
│   ├── types.py         # Type definitions
│   └── result.py        # PluginResult standardized
```

### Manifest Model
```python
from pydantic import BaseModel
from typing import List, Literal, Optional

class PluginManifest(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    category: Literal["input", "output"]
    class_name: str
    depends_on: List[str] = []
    expects: List[str] = []
    categories: List[str] = []
```

### PluginResult Model
```python
from pydantic import BaseModel
from typing import Any, Dict, Optional
from datetime import datetime

class PluginResult(BaseModel):
    success: bool
    data: Dict[str, Any] = {}
    error: Optional[str] = None
    started_at: datetime
    finished_at: datetime
    
    @property
    def duration_ms(self) -> int:
        return int((self.finished_at - self.started_at).total_seconds() * 1000)
```

---

## SCOPE LIMITATION

### Active Plugins (Modify these only)
- scanner
- file_reader
- renamer
- ffprobe
- tmdb

### Disabled Plugins (Do not touch)
- omdb
- tvmaze
- tvdb

Disable in config.yml:
```yaml
plugins:
  omdb:
    enabled: false
  tvmaze:
    enabled: false
  tvdb:
    enabled: false
```

---

## EXECUTION ORDER

1. EventBus DI Refactor (TASK 1) - Required first
2. Plugin SDK Structure (TASK 3) - Directory setup only
3. Subprocess Replacement Prep (TASK 2) - Structure only

---

## VALIDATION

After execution, verify:
```bash
# No singleton patterns in EventBus
grep -n "_instance\|__new__" src/archiverr/events/bus.py
# Should return nothing

# Tests pass
python -m pytest tests/ -v

# App runs
python -m archiverr
```

---

## REFERENCES

- Task Queue Benchmark: https://stevenyue.com/blogs/exploring-python-task-queue-libraries-with-load-test
- Taskiq Docs: https://taskiq-python.github.io/
- Stremio SDK: https://github.com/Stremio/stremio-addon-sdk
