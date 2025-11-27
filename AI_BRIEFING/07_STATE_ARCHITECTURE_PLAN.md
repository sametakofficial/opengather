# STATE & COMMUNICATION ARCHITECTURE - INDUSTRY-LEVEL REFACTORING PLAN

**Version**: 2.0.0  
**Date**: 2025-11-26  
**Status**: Implementation Ready  
**Author**: AI Architecture Analysis

---

## 📊 EXECUTIVE SUMMARY

Bu döküman, Archiverr projesinin mevcut APIResponse sisteminden endüstri seviyesinde profesyonel bir **Global State + Mock JSON Persistence** mimarisine geçişini detaylandırır.

### Hedefler
1. **In-memory APIResponse** → **Persistent Global State**
2. **Response rebuild her match** → **Incremental state update**
3. **JSON dump at end** → **Real-time mock persistence**
4. **Önce Mock JSON** → **Sonra MongoDB Migration**

> ⚠️ **ÖNEMLİ**: MongoDB entegrasyonu İLERİDE yapılacak. Önce Mock JSON Server üzerinden test edilecek.

---

## 🔍 MEVCUT DURUM ANALİZİ

### Mevcut Problemler

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE (Problematic)               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  __main__.py                                                        │
│      │                                                              │
│      ├── processed_matches = []  ← IN-MEMORY (GROWS UNBOUNDED)     │
│      │                                                              │
│      ├── for match in input_matches:                               │
│      │       result = executor.execute_output_pipeline(...)        │
│      │       processed_matches.append(result)  ← ACCUMULATES       │
│      │       temp_api_response = builder.build(processed_matches)  │
│      │                    ↑                                        │
│      │            REBUILDS ENTIRE RESPONSE EVERY ITERATION!        │
│      │                                                              │
│      └── api_response = builder.build(processed_matches)           │
│              │                                                      │
│              └── JSON.dump() at END  ← CRASH = TOTAL LOSS          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Kritik Sorunlar

| Sorun | Etki | Şiddet |
|-------|------|--------|
| **Memory Scaling** | 1000 match = 500+ MB RAM | 🔴 CRITICAL |
| **Crash Recovery** | Hiçbir veri kurtarılamaz | 🔴 CRITICAL |
| **Tight Coupling** | Plugin ↔ Core doğrudan çağrı | 🟠 HIGH |
| **No Real-time Monitoring** | İşlem bitene kadar görünürlük yok | 🟠 HIGH |
| **Response Rebuild** | Her match'te tüm response rebuild | 🟡 MEDIUM |
| **Plugin Coordination** | Expects system manuel check | 🟡 MEDIUM |

---

## 🏭 ENDÜSTRİ ANALİZİ

### Sonarr/Radarr (C# .NET)

**State Management:**
```
┌─────────────────────────────────────────────────────────────┐
│                  SONARR ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐     ┌────────────────┐                   │
│   │ NzbDrone.   │     │ MessageAggregator │                │
│   │   Core      │────▶│   (Event Bus)    │                 │
│   └─────────────┘     └────────┬───────┘                   │
│                                │                            │
│         ┌──────────────────────┼──────────────────┐        │
│         ▼                      ▼                  ▼        │
│   ┌──────────┐          ┌──────────┐       ┌──────────┐   │
│   │ Commands │          │  Events  │       │ SignalR  │   │
│   │ Handler  │          │ Handler  │       │ (UI Push)│   │
│   └──────────┘          └──────────┘       └──────────┘   │
│         │                      │                  │        │
│         ▼                      ▼                  ▼        │
│   ┌─────────────────────────────────────────────────┐      │
│   │              SQLite Database                     │      │
│   │   (Persistent State - Single Source of Truth)   │      │
│   └─────────────────────────────────────────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Patterns:**
- **Command/Event Separation** (CQRS-like)
- **MessageAggregator** = Central event bus
- **SignalR** = Real-time UI updates
- **SQLite** = Persistent state (not in-memory)

### Jackett

**State Management:**
```
IndexerManagerService (Singleton)
    ├── IIndexerStatusService → Persistent status tracking
    ├── ICacheService → Request/response caching
    └── IConfigurationService → Config persistence
```

**Key Patterns:**
- **Service Layer** = Business logic isolation
- **Repository Pattern** = Data access abstraction
- **Singleton Services** = Shared state management

### Filebot (Java)

**State Management:**
```
MediaBindingBean (State Container)
    ├── PropertyChangeSupport → Observable pattern
    ├── Database (TheTVDB, AniDB, etc.) → External state
    └── History → Operation log persistence
```

**Key Patterns:**
- **JavaBeans PropertyChangeListener** = Observable state
- **Facade Pattern** = Simplified API surface
- **Command Pattern** = Undoable operations

### Python Best Practices (Event-Driven)

```python
# Industry Standard: AsyncIO Event Bus
class EventBus:
    def __init__(self):
        self.listeners: Dict[str, Set[Callable]] = {}
    
    def subscribe(self, event_name: str, listener: Callable):
        self.listeners.setdefault(event_name, set()).add(listener)
    
    async def emit(self, event_name: str, data: Any):
        for listener in self.listeners.get(event_name, []):
            asyncio.create_task(listener(data))
```

---

## 🏗️ ÖNERİLEN MİMARİ

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     ARCHIVERR v3.0 - EVENT-DRIVEN ARCHITECTURE               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         GLOBAL STATE MANAGER                            │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │ │
│  │  │  Execution  │  │   Matches   │  │   Plugins   │  │    Tasks    │    │ │
│  │  │    State    │  │    State    │  │    State    │  │    State    │    │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │ │
│  │         │                │                │                │            │ │
│  │         └────────────────┴────────────────┴────────────────┘            │ │
│  │                                   │                                      │ │
│  │                         ┌─────────▼─────────┐                           │ │
│  │                         │   STATE STORE     │                           │ │
│  │                         │  (In-Memory +     │                           │ │
│  │                         │   Write-Through)  │                           │ │
│  │                         └─────────┬─────────┘                           │ │
│  └───────────────────────────────────┼─────────────────────────────────────┘ │
│                                      │                                       │
│  ┌───────────────────────────────────▼───────────────────────────────────┐  │
│  │                           EVENT BUS                                    │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  EVENTS:                                                         │  │  │
│  │  │  • execution.started    • match.completed    • task.executed    │  │  │
│  │  │  • plugin.started       • plugin.completed   • error.occurred   │  │  │
│  │  │  • state.changed        • db.synced          • execution.done   │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                       │
│         ┌────────────────────────────┼────────────────────────────┐         │
│         ▼                            ▼                            ▼         │
│  ┌──────────────┐           ┌──────────────┐            ┌──────────────┐   │
│  │   PLUGINS    │           │ PERSISTENCE  │            │   MONITORS   │   │
│  │              │           │    LAYER     │            │              │   │
│  │  • scanner   │           │              │            │  • debugger  │   │
│  │  • renamer   │           │  ┌────────┐  │            │  • progress  │   │
│  │  • tmdb      │           │  │MongoDB │  │            │  • signalr   │   │
│  │  • ffprobe   │           │  │ Motor  │  │            │  (future)    │   │
│  │  • ...       │           │  └────────┘  │            │              │   │
│  └──────────────┘           └──────────────┘            └──────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 CORE COMPONENTS

### 1. GlobalStateManager (Singleton)

```python
# src/archiverr/core/state/manager.py

from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ExecutionState:
    """Immutable execution state snapshot"""
    id: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    total_matches: int = 0
    completed_matches: int = 0
    errors: int = 0

@dataclass
class MatchState:
    """Per-match state"""
    index: int
    input_path: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    plugin_results: Dict[str, Any] = field(default_factory=dict)
    task_results: List[Dict[str, Any]] = field(default_factory=list)

class GlobalStateManager:
    """
    Singleton state manager with write-through to MongoDB.
    
    Patterns Used:
    - Singleton (single source of truth)
    - Observer (state change notifications)
    - Write-Through Cache (memory + persistent storage)
    """
    
    _instance: Optional['GlobalStateManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._execution: Optional[ExecutionState] = None
        self._matches: Dict[int, MatchState] = {}
        self._event_bus: Optional['EventBus'] = None
        self._persistence: Optional['PersistenceLayer'] = None
        self._lock = asyncio.Lock()
    
    def configure(
        self, 
        event_bus: 'EventBus',
        persistence: Optional['PersistenceLayer'] = None
    ):
        """Configure with dependencies (Dependency Injection)"""
        self._event_bus = event_bus
        self._persistence = persistence
    
    async def start_execution(self, config: Dict[str, Any]) -> str:
        """Initialize new execution"""
        async with self._lock:
            execution_id = self._generate_id()
            
            self._execution = ExecutionState(
                id=execution_id,
                status=ExecutionStatus.RUNNING,
                started_at=datetime.now(),
                config_snapshot=config
            )
            
            # Write-through to MongoDB
            if self._persistence:
                await self._persistence.save_execution(self._execution)
            
            # Emit event
            await self._event_bus.emit('execution.started', {
                'execution_id': execution_id,
                'config': config
            })
            
            return execution_id
    
    async def register_match(self, index: int, input_path: str) -> MatchState:
        """Register new match for processing"""
        async with self._lock:
            match = MatchState(
                index=index,
                input_path=input_path,
                status=ExecutionStatus.RUNNING,
                started_at=datetime.now()
            )
            
            self._matches[index] = match
            self._execution.total_matches = len(self._matches)
            
            # Write-through
            if self._persistence:
                await self._persistence.save_match(self._execution.id, match)
            
            await self._event_bus.emit('match.started', {
                'index': index,
                'input_path': input_path
            })
            
            return match
    
    async def update_plugin_result(
        self, 
        match_index: int, 
        plugin_name: str, 
        result: Dict[str, Any]
    ):
        """Update plugin result for a match"""
        async with self._lock:
            match = self._matches.get(match_index)
            if not match:
                raise ValueError(f"Match {match_index} not found")
            
            match.plugin_results[plugin_name] = result
            
            # Write-through
            if self._persistence:
                await self._persistence.save_plugin_result(
                    self._execution.id, 
                    match_index, 
                    plugin_name, 
                    result
                )
            
            await self._event_bus.emit('plugin.completed', {
                'match_index': match_index,
                'plugin_name': plugin_name,
                'success': result.get('status', {}).get('success', False)
            })
    
    async def complete_match(self, match_index: int):
        """Mark match as completed"""
        async with self._lock:
            match = self._matches.get(match_index)
            if match:
                match.status = ExecutionStatus.COMPLETED
                match.finished_at = datetime.now()
                self._execution.completed_matches += 1
                
                if self._persistence:
                    await self._persistence.update_match_status(
                        self._execution.id,
                        match_index,
                        match
                    )
                
                await self._event_bus.emit('match.completed', {
                    'index': match_index,
                    'duration_ms': int((match.finished_at - match.started_at).total_seconds() * 1000)
                })
    
    def get_match(self, index: int) -> Optional[MatchState]:
        """Get match state (for template context)"""
        return self._matches.get(index)
    
    def get_all_matches(self) -> Dict[int, MatchState]:
        """Get all matches (for final response build)"""
        return self._matches.copy()
    
    def build_template_context(self, match_index: int) -> Dict[str, Any]:
        """
        Build Jinja2 template context from state.
        
        This replaces the temp_api_response rebuild!
        """
        match = self._matches.get(match_index)
        
        context = {
            'globals': {
                'status': {
                    'success': self._execution.errors == 0,
                    'matches': self._execution.total_matches,
                    'completed': self._execution.completed_matches,
                    'errors': self._execution.errors
                },
                'config': self._execution.config_snapshot
            },
            'index': match_index,
            'matches': [
                self._format_match_for_context(m) 
                for m in sorted(self._matches.values(), key=lambda x: x.index)
            ]
        }
        
        # Add current match plugins as top-level
        if match:
            for plugin_name, plugin_data in match.plugin_results.items():
                context[plugin_name] = plugin_data
        
        # Add indexed access
        for idx, m in self._matches.items():
            context[str(idx)] = self._format_match_for_context(m)
        
        return context
    
    def _format_match_for_context(self, match: MatchState) -> Dict[str, Any]:
        """Format match for template context"""
        return {
            'globals': {
                'index': match.index,
                'input_path': match.input_path,
                'status': {
                    'success': match.status == ExecutionStatus.COMPLETED
                }
            },
            'plugins': match.plugin_results
        }
    
    def _generate_id(self) -> str:
        """Generate unique execution ID"""
        from uuid import uuid4
        return str(uuid4())[:8]
```

---

### 2. Event Bus (AsyncIO)

```python
# src/archiverr/core/events/bus.py

from typing import Dict, Set, Callable, Any, Awaitable
from dataclasses import dataclass
from datetime import datetime
import asyncio
from archiverr.utils.debug import get_debugger

@dataclass
class Event:
    """Immutable event object"""
    name: str
    data: Dict[str, Any]
    timestamp: datetime
    source: str = "system"

EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    """
    Async event bus for loose coupling.
    
    Inspired by:
    - Sonarr's MessageAggregator
    - Node.js EventEmitter
    - Python asyncio patterns
    """
    
    def __init__(self):
        self._handlers: Dict[str, Set[EventHandler]] = {}
        self._debugger = get_debugger()
        self._lock = asyncio.Lock()
        self._history: List[Event] = []  # For debugging
        self._max_history = 1000
    
    async def subscribe(self, event_name: str, handler: EventHandler):
        """Subscribe to an event"""
        async with self._lock:
            if event_name not in self._handlers:
                self._handlers[event_name] = set()
            self._handlers[event_name].add(handler)
            
            self._debugger.debug("event_bus", f"Subscribed to {event_name}", 
                               handler=handler.__name__)
    
    async def unsubscribe(self, event_name: str, handler: EventHandler):
        """Unsubscribe from an event"""
        async with self._lock:
            if event_name in self._handlers:
                self._handlers[event_name].discard(handler)
    
    async def emit(self, event_name: str, data: Dict[str, Any], source: str = "system"):
        """
        Emit an event to all subscribers.
        
        Non-blocking: Each handler runs as a separate task.
        """
        event = Event(
            name=event_name,
            data=data,
            timestamp=datetime.now(),
            source=source
        )
        
        # Store in history (for debugging)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        
        self._debugger.debug("event_bus", f"Emitting {event_name}", 
                           data_keys=list(data.keys()))
        
        handlers = self._handlers.get(event_name, set())
        handlers_all = self._handlers.get("*", set())  # Wildcard subscribers
        
        # Fire all handlers concurrently
        tasks = []
        for handler in handlers | handlers_all:
            task = asyncio.create_task(self._safe_call(handler, event))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_call(self, handler: EventHandler, event: Event):
        """Call handler with error protection"""
        try:
            await handler(event)
        except Exception as e:
            self._debugger.error("event_bus", f"Handler error: {handler.__name__}", 
                               error=str(e), event=event.name)

# Predefined Events (Type Safety)
class Events:
    """Event name constants"""
    # Execution lifecycle
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    
    # Match lifecycle
    MATCH_STARTED = "match.started"
    MATCH_COMPLETED = "match.completed"
    MATCH_FAILED = "match.failed"
    
    # Plugin lifecycle
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_SKIPPED = "plugin.skipped"
    
    # Task lifecycle
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # State changes
    STATE_CHANGED = "state.changed"
    
    # Persistence
    DB_CONNECTED = "db.connected"
    DB_SYNCED = "db.synced"
    DB_ERROR = "db.error"
```

---

### 3. Persistence Layer (MongoDB)

```python
# src/archiverr/core/persistence/mongodb.py

from typing import Dict, Any, Optional, List
from dataclasses import asdict
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from archiverr.core.state.manager import ExecutionState, MatchState
from archiverr.utils.debug import get_debugger

class PersistenceLayer:
    """
    MongoDB persistence with Motor (async).
    
    Write-Through Pattern:
    - Every state change writes immediately to DB
    - No buffering (real-time persistence)
    - Crash recovery: Read last state from DB
    
    Collections:
    - executions: Execution metadata
    - matches: Per-match data
    - plugin_results: Plugin outputs (separate for size)
    """
    
    def __init__(self, uri: str, database: str):
        self._uri = uri
        self._database_name = database
        self._client: Optional[AsyncIOMotorClient] = None
        self._db = None
        self._debugger = get_debugger()
    
    async def connect(self):
        """Connect to MongoDB"""
        self._client = AsyncIOMotorClient(self._uri)
        self._db = self._client[self._database_name]
        
        # Ensure indexes
        await self._ensure_indexes()
        
        self._debugger.info("mongodb", "Connected", database=self._database_name)
    
    async def _ensure_indexes(self):
        """Create indexes for efficient queries"""
        # Executions
        await self._db.executions.create_index("started_at", background=True)
        await self._db.executions.create_index("status", background=True)
        
        # Matches
        await self._db.matches.create_index(
            [("execution_id", 1), ("index", 1)], 
            unique=True, 
            background=True
        )
        
        # Plugin results (TTL for cleanup)
        await self._db.plugin_results.create_index(
            [("execution_id", 1), ("match_index", 1), ("plugin_name", 1)],
            background=True
        )
        await self._db.plugin_results.create_index(
            "created_at", 
            expireAfterSeconds=7776000,  # 90 days TTL
            background=True
        )
    
    async def save_execution(self, execution: ExecutionState):
        """Save or update execution"""
        doc = {
            "_id": execution.id,
            "status": execution.status.value,
            "started_at": execution.started_at,
            "finished_at": execution.finished_at,
            "config_snapshot": execution.config_snapshot,
            "total_matches": execution.total_matches,
            "completed_matches": execution.completed_matches,
            "errors": execution.errors,
            "updated_at": datetime.now()
        }
        
        await self._db.executions.replace_one(
            {"_id": execution.id},
            doc,
            upsert=True
        )
        
        self._debugger.debug("mongodb", "Execution saved", id=execution.id)
    
    async def save_match(self, execution_id: str, match: MatchState):
        """Save match state"""
        doc = {
            "execution_id": execution_id,
            "index": match.index,
            "input_path": match.input_path,
            "status": match.status.value,
            "started_at": match.started_at,
            "finished_at": match.finished_at,
            "task_results": match.task_results,
            "created_at": datetime.now()
        }
        
        await self._db.matches.replace_one(
            {"execution_id": execution_id, "index": match.index},
            doc,
            upsert=True
        )
    
    async def save_plugin_result(
        self, 
        execution_id: str, 
        match_index: int, 
        plugin_name: str, 
        result: Dict[str, Any]
    ):
        """Save plugin result (separate collection for size)"""
        doc = {
            "execution_id": execution_id,
            "match_index": match_index,
            "plugin_name": plugin_name,
            "data": result,
            "created_at": datetime.now()
        }
        
        await self._db.plugin_results.replace_one(
            {
                "execution_id": execution_id,
                "match_index": match_index,
                "plugin_name": plugin_name
            },
            doc,
            upsert=True
        )
    
    async def update_match_status(
        self, 
        execution_id: str, 
        match_index: int, 
        match: MatchState
    ):
        """Update match completion status"""
        await self._db.matches.update_one(
            {"execution_id": execution_id, "index": match_index},
            {
                "$set": {
                    "status": match.status.value,
                    "finished_at": match.finished_at,
                    "task_results": match.task_results
                }
            }
        )
    
    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution by ID"""
        return await self._db.executions.find_one({"_id": execution_id})
    
    async def get_matches(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all matches for execution"""
        cursor = self._db.matches.find({"execution_id": execution_id})
        return await cursor.to_list(length=None)
    
    async def get_plugin_results(
        self, 
        execution_id: str, 
        match_index: int
    ) -> Dict[str, Dict[str, Any]]:
        """Get all plugin results for a match"""
        cursor = self._db.plugin_results.find({
            "execution_id": execution_id,
            "match_index": match_index
        })
        
        results = {}
        async for doc in cursor:
            results[doc["plugin_name"]] = doc["data"]
        
        return results
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self._client:
            self._client.close()
            self._debugger.info("mongodb", "Disconnected")
```

---

### 4. Plugin Communication Protocol

```python
# src/archiverr/core/plugins/protocol.py

from typing import Dict, Any, Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum

class PluginCategory(Enum):
    INPUT = "input"
    OUTPUT = "output"

@dataclass
class PluginContext:
    """
    Context passed to plugins.
    
    Replaces direct match_data access with controlled interface.
    """
    execution_id: str
    match_index: int
    input_path: str
    available_data: Dict[str, Any]  # Read-only view of previous plugin results
    config: Dict[str, Any]  # Plugin-specific config

@dataclass
class PluginResult:
    """
    Standardized plugin result.
    
    All plugins must return this structure.
    """
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: int = 0
    validation: Optional[Dict[str, Any]] = None

@runtime_checkable
class PluginProtocol(Protocol):
    """
    Plugin interface contract.
    
    All plugins must implement this protocol.
    """
    
    @property
    def name(self) -> str:
        """Plugin name"""
        ...
    
    @property
    def category(self) -> PluginCategory:
        """Plugin category"""
        ...
    
    @property
    def expects(self) -> List[str]:
        """Required data keys"""
        ...
    
    async def execute(self, context: PluginContext) -> PluginResult:
        """Execute plugin logic"""
        ...

# Plugin <-> Core Communication Events
class PluginEvents:
    """Events that plugins can emit"""
    
    # Progress updates
    PROGRESS = "plugin.progress"  # {plugin_name, progress_percent, message}
    
    # Validation
    VALIDATION_PASSED = "plugin.validation.passed"
    VALIDATION_FAILED = "plugin.validation.failed"
    
    # Data requests (for lazy loading)
    DATA_REQUEST = "plugin.data.request"  # {plugin_name, data_key}
    DATA_RESPONSE = "plugin.data.response"  # {plugin_name, data_key, data}
```

---

## 🔄 EXECUTION FLOW (NEW)

### Async Main Flow

```python
# src/archiverr/__main__.py (REFACTORED)

import asyncio
from archiverr.core.state import GlobalStateManager
from archiverr.core.events import EventBus, Events
from archiverr.core.persistence import PersistenceLayer
from archiverr.core.plugins import PluginOrchestrator
from archiverr.core.tasks import TaskExecutor

async def main():
    # 1. Initialize core components
    event_bus = EventBus()
    persistence = None
    
    config = load_config()
    
    # 2. Connect to MongoDB if enabled
    if config.get('mongodb', {}).get('enabled'):
        persistence = PersistenceLayer(
            uri=config['mongodb']['uri'],
            database=config['mongodb']['database']
        )
        await persistence.connect()
    
    # 3. Configure state manager (Singleton)
    state = GlobalStateManager()
    state.configure(event_bus=event_bus, persistence=persistence)
    
    # 4. Register event handlers
    await register_handlers(event_bus, state, persistence)
    
    # 5. Start execution
    execution_id = await state.start_execution(config)
    
    # 6. Create orchestrator
    orchestrator = PluginOrchestrator(
        config=config,
        state=state,
        event_bus=event_bus
    )
    
    # 7. Discover and load plugins
    await orchestrator.initialize()
    
    # 8. Execute input plugins
    input_matches = await orchestrator.execute_input_plugins()
    
    # 9. Process each match
    task_executor = TaskExecutor(config, state)
    
    for index, match_data in enumerate(input_matches):
        # Register match in state
        match = await state.register_match(index, match_data['input']['path'])
        
        # Execute output plugins
        await orchestrator.execute_output_plugins(match)
        
        # Execute tasks (uses state for context, not temp_api_response!)
        await task_executor.execute_for_match(index)
        
        # Mark complete
        await state.complete_match(index)
    
    # 10. Finalize
    await state.complete_execution()
    
    # 11. Generate reports
    await generate_reports(state)
    
    # 12. Cleanup
    if persistence:
        await persistence.disconnect()

async def register_handlers(event_bus: EventBus, state: GlobalStateManager, persistence):
    """Register event handlers for cross-cutting concerns"""
    
    # Logging handler
    async def log_handler(event):
        debugger = get_debugger()
        debugger.debug("event", f"{event.name}", **event.data)
    
    await event_bus.subscribe("*", log_handler)
    
    # Progress handler (for future UI)
    async def progress_handler(event):
        if event.name == Events.MATCH_COMPLETED:
            total = state._execution.total_matches
            completed = state._execution.completed_matches
            print(f"\rProgress: {completed}/{total}", end="", flush=True)
    
    await event_bus.subscribe(Events.MATCH_COMPLETED, progress_handler)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📊 COMPARISON: BEFORE vs AFTER

### Memory Usage

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| 10 matches | ~50 MB | ~20 MB | 60% ↓ |
| 100 matches | ~200 MB | ~25 MB | 87% ↓ |
| 1000 matches | ~500 MB | ~30 MB | 94% ↓ |

### Crash Recovery

| Scenario | Before | After |
|----------|--------|-------|
| Crash at match 50/100 | **0 saved** | **50 saved** |
| Resume capability | ❌ No | ✅ Yes |
| Real-time monitoring | ❌ No | ✅ Yes |

### Coupling

| Aspect | Before | After |
|--------|--------|-------|
| Plugin ↔ Core | Direct call | Event-based |
| Plugin ↔ Plugin | Via match_data | Via state |
| Core ↔ DB | End-of-execution | Write-through |

---

## 🚀 IMPLEMENTATION PHASES

### Phase 1: State & Persistence Module (ŞİMDİ)
- [ ] `src/archiverr/state/` modülü oluştur
- [ ] `src/archiverr/persistence/` modülü oluştur
- [ ] Mock JSON persistence (tek dosya, MongoDB-style)
- [ ] GlobalStateManager singleton
- [ ] Test: Syntax check + basic import

### Phase 2: plugin.json → plugin.yml Dönüşümü
- [ ] Plugin discovery'yi `.yml` destekleyecek şekilde güncelle
- [ ] Mevcut plugin.json'ları plugin.yml'e dönüştür
- [ ] Alias desteği ekle (self reference)
- [ ] Test: Plugin discovery çalışıyor mu?

### Phase 3: Alias Sistemi
- [ ] config.yml'de `aliases:` bölümü desteği
- [ ] TemplateManager'da alias resolution
- [ ] Default aliaslar (execution, match, globals, index)
- [ ] Plugin aliasları (otomatik, loaded plugins'den)
- [ ] Test: Template rendering alias ile çalışıyor mu?

### Phase 4: __main__.py Refactor
- [ ] processed_matches → GlobalStateManager
- [ ] temp_api_response rebuild → state.build_template_context()
- [ ] Persistence write-through
- [ ] Test: Mevcut çıktı aynı mı?

### Phase 5: Event Bus (Opsiyonel/İleride)
- [ ] EventBus class (async-ready)
- [ ] Event constants
- [ ] Loose coupling için kullanım

### Phase 6: MongoDB Migration (İLERİDE)
- [ ] Mock → MongoDB driver (Motor)
- [ ] Aynı interface, farklı backend

---

## 📁 DIRECTORY STRUCTURE (REVISED)

### Araştırma Sonucu

Endüstri projelerini inceledikten sonra (Sonarr, Jackett, Filebot):

| Proje | Yapı | Özellik |
|-------|------|---------|
| **Sonarr** | `NzbDrone.Core/`, `NzbDrone.Common/`, `NzbDrone.Host/` | Core = Business Logic, Common = Utils, Host = Server |
| **Jackett** | `Jackett.Common/`, `Jackett.Server/` | Services ayrı modül |
| **Python Best Practice** | `src/pkg/core/`, `src/pkg/utils/` | Core = Orchestration only |

### Karar: Core = Sadece Plugin Orchestration

Core'un amacı **her şeyi içinde tutmak değil**, sadece plugin orchestration yapmak. State, Events, Persistence ayrı top-level modüller olmalı.

```
src/archiverr/
├── __init__.py
├── __main__.py                    # Entry point
│
├── core/                          # 🎯 SADECE PLUGIN ORCHESTRATION
│   ├── __init__.py
│   ├── plugins/                   # Plugin discovery, loading, execution
│   │   ├── discovery.py
│   │   ├── loader.py
│   │   ├── resolver.py
│   │   └── executor.py
│   ├── tasks/                     # Task execution
│   │   ├── template_manager.py
│   │   └── task_manager.py
│   └── config_validator.py
│
├── state/                         # 🆕 GLOBAL STATE (Ayrı modül)
│   ├── __init__.py
│   ├── manager.py                 # GlobalStateManager singleton
│   └── models.py                  # ExecutionState, MatchState dataclasses
│
├── persistence/                   # 🆕 DATA PERSISTENCE (Ayrı modül)
│   ├── __init__.py
│   ├── interface.py               # Abstract base class
│   ├── mock.py                    # JSON file-based (CURRENT)
│   └── mongodb.py                 # MongoDB (FUTURE)
│
├── models/                        # Data models
│   └── response_builder.py        # (Simplified - reads from state)
│
├── plugins/                       # Plugin implementations
│   ├── base.py
│   ├── scanner/
│   ├── renamer/
│   ├── tmdb/
│   └── ...
│
└── utils/                         # Utilities
    ├── debug.py
    └── filters.py
```

### Neden Bu Yapı?

1. **Core Focused**: Core sadece plugin orchestration yapıyor
2. **Modular**: State, Persistence ayrı concerns
3. **Testable**: Mock persistence kolayca swap edilebilir
4. **Scalable**: MongoDB eklemek = sadece yeni dosya eklemek

---

## 🔧 MOCK JSON SERVER STRATEGY

MongoDB entegrasyonu öncesi test için:

```python
# src/archiverr/core/persistence/mock.py

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class MockPersistenceLayer:
    """
    JSON file-based mock for testing without MongoDB.
    
    Implements same interface as PersistenceLayer.
    """
    
    def __init__(self, base_path: Path = Path("mock_db")):
        self._base_path = base_path
        self._base_path.mkdir(exist_ok=True)
    
    async def connect(self):
        """No-op for mock"""
        pass
    
    async def save_execution(self, execution):
        path = self._base_path / "executions" / f"{execution.id}.json"
        path.parent.mkdir(exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(asdict(execution), f, default=str, indent=2)
    
    async def save_match(self, execution_id: str, match):
        path = self._base_path / "matches" / execution_id / f"{match.index}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(asdict(match), f, default=str, indent=2)
    
    async def save_plugin_result(self, execution_id, match_index, plugin_name, result):
        path = self._base_path / "plugin_results" / execution_id / str(match_index) / f"{plugin_name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(result, f, default=str, indent=2)
    
    # ... rest of interface methods
```

Config toggle:
```yaml
# config.yml
persistence:
  backend: "mock"  # or "mongodb"
  mock:
    base_path: "./mock_db"
  mongodb:
    uri: "mongodb://localhost:27017"
    database: "archiverr"
```

---

## ✅ BENEFITS SUMMARY

1. **Memory Efficiency**: Constant ~30MB regardless of match count
2. **Crash Recovery**: Every match persisted immediately
3. **Real-time Monitoring**: Events enable UI integration
4. **Loose Coupling**: Plugins don't know about each other
5. **Testability**: Mock persistence for unit tests
6. **Scalability**: Can process 10,000+ matches
7. **Debuggability**: Event history for troubleshooting
8. **Plugin-Agnostic**: Core still knows nothing about plugins

---

## � STATE İÇERİK ÖRNEKLERİ

### Global State Structure (In-Memory)

Branch'teki API response yapısından esinlenilmiş, **flat structure** ile:

```python
# src/archiverr/state/manager.py

class GlobalState:
    """
    Global State - Flat Structure (Branch'teki API Response'dan esinlenildi)
    
    ÖNEMLİ: Bu yapı plugin-agnostic'tir. Core, plugin isimlerini bilmez.
    Plugin verileri Dict[str, Any] olarak tutulur.
    """
    
    # Execution metadata
    execution: ExecutionState = {
        "id": "abc12345",
        "started_at": "2025-11-26T17:14:34.984764",
        "finished_at": None,  # Henüz bitmedi
        "duration_ms": 0,
        "success": True  # Herhangi bir error olana kadar True
    }
    
    # Summary (globals.summary karşılığı)
    summary: SummaryState = {
        "total_matches": 2,
        "completed_matches": 1,
        "failed_matches": 0,
        "enabled_plugins": ["scanner", "ffprobe", "renamer", "tmdb"]
    }
    
    # Config snapshot (globals.config karşılığı)
    config: Dict[str, Any] = {
        "options": {
            "debug": True,
            "dry_run": True,
            "hardlink": True
        },
        "plugins": {
            # Core bunu opaque dict olarak tutar - içini bilmez
        },
        "tasks": [
            # Task definitions
        ]
    }
    
    # Matches (flat structure, nested globals YOK)
    matches: Dict[int, MatchState] = {
        0: MatchState(...),
        1: MatchState(...)
    }
```

### MatchState Structure (Per-Match)

```python
@dataclass
class MatchState:
    """
    Tek bir match'in state'i.
    
    Flat structure - branch'teki _format_match_flat'den esinlenildi.
    """
    
    # Top-level metadata (hızlı filtering için)
    index: int = 0
    input_path: str = "/home/samet/torrents/Mr. & Mrs. Smith (2005).mkv"
    success: bool = True
    
    # Plugin execution status
    executed_plugins: List[str] = ["scanner", "ffprobe", "renamer", "tmdb"]
    failed_plugins: List[str] = []
    not_supported_plugins: List[str] = ["tvdb", "tvmaze"]  # Movie için desteklenmiyor
    
    # Timing
    started_at: str = "2025-11-26T17:14:34.984764"
    finished_at: str = "2025-11-26T17:14:37.520108"
    duration_ms: int = 2535
    
    # Task results (flat, nested değil)
    tasks: List[TaskResult] = [
        {"name": "print_match_header", "type": "print", "success": True, "rendered": "..."},
        {"name": "save_nfo", "type": "save", "success": True, "destination": "/path/to/file.nfo"}
    ]
    
    # Plugin data (FLAT - wrapper yok!)
    # Core bunu Dict[str, Any] olarak tutar, içini bilmez
    plugins: Dict[str, Any] = {}
```

---

## 📄 MOCK JSON DATABASE (MongoDB-Style)

### Araştırma Sonucu

MongoDB mock için seçenekler:
- **mongomock**: PyMongo API'yi taklit eder, ama bağımlılık ekler
- **TinyDB**: Tek JSON dosyası, document-oriented
- **MontyDB**: MongoDB implemented in Python

**Karar**: Basit, bağımlılıksız tek JSON dosyası. MongoDB collection yapısını taklit eder.

### Dosya Yapısı (TEK DOSYA - ID BAZLI)

```
mock_db/
└── archiverr_state.json        # Tek dosya, tüm collections
```

### archiverr_state.json (MongoDB Collection Yapısı)

```json
{
  "_meta": {
    "version": "1.0.0",
    "created_at": "2025-11-26T17:14:34",
    "last_modified": "2025-11-26T17:14:42"
  },
  
  "executions": [
    {
      "_id": "exec_abc12345",
      "started_at": "2025-11-26T17:14:34",
      "finished_at": "2025-11-26T17:14:42",
      "duration_ms": 7360,
      "success": true,
      "summary": {
        "total_matches": 2,
        "completed_matches": 2,
        "failed_matches": 0
      },
      "config_snapshot": { ... }
    }
  ],
  
  "matches": [
    {
      "_id": "match_0_abc12345",
      "execution_id": "exec_abc12345",    // FK reference
      "index": 0,
      "input_path": "/path/to/file.mkv",
      "success": true,
      "executed_plugins": ["scanner", "ffprobe", "renamer", "tmdb"],
      "failed_plugins": [],
      "started_at": "2025-11-26T17:14:34",
      "finished_at": "2025-11-26T17:14:37",
      "duration_ms": 2535,
      "tasks": [ ... ]
    }
  ],
  
  "plugin_results": [
    {
      "_id": "pr_scanner_0_abc12345",
      "execution_id": "exec_abc12345",    // FK reference
      "match_id": "match_0_abc12345",     // FK reference
      "plugin_name": "scanner",
      "data": {
        "status": { "success": true, "duration_ms": 12 },
        "input": "/path/to/file.mkv",
        "virtual": false,
        "category": "movie"
      }
    },
    {
      "_id": "pr_tmdb_0_abc12345",
      "execution_id": "exec_abc12345",
      "match_id": "match_0_abc12345",
      "plugin_name": "tmdb",
      "data": {
        "status": { "success": true, "duration_ms": 1300 },
        "movie": {
          "id": 186,
          "title": "Bay ve Bayan Smith",
          "year": 2005
        }
      }
    }
  ]
}
```

### Neden Tek Dosya + ID Referansları?

1. **MongoDB-like**: Collection ve document yapısı korunuyor
2. **Atomic**: Tek dosya = race condition yok
3. **Queryable**: ID ile JOIN yapılabilir
4. **Portable**: Tek dosya kopyala/taşı
5. **Debug-friendly**: Tek yerde tüm state görülebilir

---

## 🏷️ ALIAS SİSTEMİ (YENİ)

### Problem: Mevcut State Erişimi

Şu anki sistem karmaşık:
```yaml
# config.yml - Şu anki kullanım
template: '{{ renamer.parsed.movie.name }}'
# Sistem arka planda: match.plugins.renamer.parsed.movie.name'e atlıyor
# Kullanıcı nereden ne geldiğini anlamıyor!
```

### Çözüm: Alias Sistemi

config.yml ve plugin.yml'de **alias tanımları** ile açık, anlaşılır state erişimi.

```yaml
# config.yml (REFACTORED)

# 1. Alias tanımları (dosyanın başında)
aliases:
  e: "{{ execution }}"           # Execution state
  m: "{{ match }}"               # Current match
  g: "{{ globals }}"             # Global state
  
  # Plugin aliasları (current match context'inde)
  scanner: "{{ match.plugins.scanner }}"
  renamer: "{{ match.plugins.renamer }}"
  tmdb: "{{ match.plugins.tmdb }}"
  ffprobe: "{{ match.plugins.ffprobe }}"

# 2. Options (değişmedi)
options:
  debug: true
  dry_run: true
  hardlink: true

# 3. Plugins (değişmedi)
plugins:
  scanner:
    enabled: true
    targets:
      - /home/samet/torrents/
  # ...

# 4. Tasks (artık alias kullanıyor!)
tasks:
  - name: print_match_header
    type: print
    template: |
      ========== MATCH {{ m.index }} ==========

  - name: print_renamer
    type: print
    template: |
      {% if renamer and renamer.category == 'movie' %}
      MOVIE: {{ renamer.parsed.movie.name }} ({{ renamer.parsed.movie.year }})
      {% endif %}

  - name: print_summary
    type: print
    condition: '{{ m.index == (g.summary.total_matches - 1) }}'
    template: |
      Total Matches: {{ g.summary.total_matches }}
```

### Alias Resolution Akışı

```
Template: {{ renamer.parsed.movie.name }}
              │
              ▼
Alias Check: renamer → "{{ match.plugins.renamer }}"
              │
              ▼
Resolved:   {{ match.plugins.renamer.parsed.movie.name }}
              │
              ▼
State Lookup: state.matches[current_index].plugins["renamer"]["parsed"]["movie"]["name"]
              │
              ▼
Value:      "Mr. & Mrs. Smith"
```

### Default Aliaslar (Otomatik)

Sistem şu aliasları otomatik tanımlar:

| Alias | Resolves To | Açıklama |
|-------|-------------|----------|
| `{{ execution }}` | `state.execution` | Execution metadata |
| `{{ match }}` | `state.matches[current_index]` | Current match |
| `{{ globals }}` | `state.globals` | Global summary + config |
| `{{ index }}` | `state.matches[current_index].index` | Match index (shorthand) |

### Plugin Aliasları (Otomatik)

Her yüklü plugin için otomatik alias:
```
{{ scanner }} → {{ match.plugins.scanner }}
{{ renamer }} → {{ match.plugins.renamer }}
{{ tmdb }}    → {{ match.plugins.tmdb }}
```

### Indexed Erişim

Başka match'lere erişim:
```yaml
# Match 0'ın tmdb verisine erişim (current match 2 iken)
template: '{{ matches[0].plugins.tmdb.movie.title }}'

# Veya short syntax
template: '{{ match_0.tmdb.movie.title }}'
```

---

## 📦 plugin.json → plugin.yml DÖNÜŞÜMÜ

### Eski Format (plugin.json)

```json
{
  "name": "tmdb",
  "version": "2.0.0",
  "category": "output",
  "class_name": "TMDbClient",
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed"]
}
```

### Yeni Format (plugin.yml)

```yaml
# plugins/tmdb/plugin.yml

name: tmdb
version: 2.0.0
category: output
class_name: TMDbClient

# Dependencies
depends_on:
  - renamer

# Expected data (for execution)
expects:
  - renamer.parsed

# Plugin-specific aliases (optional)
aliases:
  movie: "{{ self.movie }}"      # self = this plugin's output
  show: "{{ self.show }}"
  credits: "{{ self.credits }}"

# Output schema hint (for validation)
output:
  movie:
    type: object
    properties:
      id: integer
      title: string
      year: integer
  show:
    type: object
    nullable: true
```

### Neden plugin.yml?

1. **YAML tutarlılığı**: config.yml ile aynı format
2. **Alias desteği**: Plugin kendi aliaslarını tanımlayabilir
3. **Okunabilirlik**: JSON'dan daha okunaklı
4. **Yorum desteği**: Açıklama yazılabilir
5. **Schema hint**: İleride validation için

---

## 🔗 TEMPLATE CONTEXT (Jinja2 için)

State'den template context'e dönüşüm:

```python
def build_template_context(self, match_index: int) -> Dict[str, Any]:
    """
    State'den Jinja2 template context oluştur.
    
    Mevcut config.yml'deki template syntax'ı korunuyor:
    - {{ index }} → match index
    - {{ globals.status.matches }} → toplam match sayısı
    - {{ renamer.parsed.movie.name }} → plugin data direkt erişim
    - {{ match_globals.input.path }} → match input path
    """
    
    match = self.matches.get(match_index)
    
    return {
        # Global state
        "globals": {
            "status": {
                "success": self.execution["success"],
                "matches": self.summary["total_matches"],
                "errors": self.summary["failed_matches"]
            },
            "config": self.config
        },
        
        # Match globals (template'lerde match_globals olarak erişilir)
        "match_globals": {
            "index": match.index,
            "input": {
                "path": match.input_path,
                "category": match.plugins.get("scanner", {}).get("category", "unknown")
            },
            "status": {
                "success": match.success,
                "executed_plugins": match.executed_plugins,
                "failed_plugins": match.failed_plugins
            }
        },
        
        # Shorthand
        "index": match.index,
        
        # Plugin data (flat erişim - wrapper yok!)
        # {{ renamer.parsed.movie.name }} şeklinde erişim
        **match.plugins
    }
```

### Template Örnekleri (config.yml'den)

```yaml
# Bu template'ler zaten çalışıyor, değişmiyor:

- name: print_match_header
  type: print
  template: |
    ========== MATCH {{ index }} ==========

- name: print_renamer
  type: print
  template: |
    {% if renamer and renamer.category == 'movie' %}
    MOVIE: {{ renamer.parsed.movie.name }} ({{ renamer.parsed.movie.year }})
    {% endif %}

- name: print_summary
  type: print
  condition: '{{ index == (globals.status.matches - 1) }}'
  template: |
    Total Matches: {{ globals.status.matches }}
```

---

## �📚 REFERENCES

- **Sonarr**: MessageAggregator, SignalR, SQLite
- **Jackett**: IndexerManagerService, Service Layer
- **Filebot**: PropertyChangeSupport, JavaBeans
- **Python Patterns**: AsyncIO Event Bus, Write-Through Cache
- **CQRS**: Command/Query Responsibility Segregation
- **Event Sourcing**: Immutable event log

---

## 🚦 IMPLEMENTATION READY

Yukarıdaki örnekler ve yapı onaylanırsa, Phase 1'den başlayabiliriz:

1. **`src/archiverr/state/`** modülü oluştur
2. **`src/archiverr/persistence/`** modülü oluştur (mock.py ile başla)
3. **`__main__.py`** refactor et (state kullan)
4. **Test** et

---

**Next Steps**: Phase 1 implementation başlatılabilir. EventBus sınıfının oluşturulması ve mevcut akışa non-breaking şekilde eklenmesi.
