# ORCHESTRATOR & EXECUTION FLOW

```yaml
date: 2025-11-30
sources: v5-part2, v6, brainstorm-v2
status: final
```

---

## 1. MİMARİ KARAR

### 1.1 __main__.py Sorunu

```
MEVCUT DURUM:
__main__.py = 400+ satır
├── Config loading
├── Plugin discovery
├── Plugin loading
├── Dependency resolution
├── Input execution
├── Output execution loop
├── Task execution
├── State management
├── Error handling
└── Completion

SORUN: Single Responsibility Principle ihlali
```

### 1.2 Çözüm: Orchestrator Pattern

```
YENİ YAPI:
__main__.py (~50 satır)
├── CLI argument parsing
├── Orchestrator initialization
└── orchestrator.run()

Orchestrator (~200 satır)
├── Phase coordination
├── Plugin lifecycle
├── State orchestration
└── Error propagation
```

---

## 2. COMPONENT DİAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                         __main__.py                          │
│                                                              │
│  def main():                                                 │
│      config = load_config()                                  │
│      orchestrator = Orchestrator(config)                     │
│      orchestrator.run()                                      │
│                                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        Orchestrator                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Dependencies (injected):                                    │
│  ├── EventBus                                                │
│  ├── StateManager                                            │
│  ├── Persistence                                             │
│  ├── PluginRegistry                                          │
│  ├── PhaseExecutor                                           │
│  └── TaskManager                                             │
│                                                              │
│  Methods:                                                    │
│  ├── run() -> RunResult                                      │
│  ├── _initialize()                                           │
│  ├── _execute_phases()                                       │
│  ├── _execute_tasks()                                        │
│  └── _finalize()                                             │
│                                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ StateManager │   │PhaseExecutor│   │ TaskManager │
└─────────────┘   └─────────────┘   └─────────────┘
```

---

## 3. DEPENDENCY INJECTION

### 3.1 Initialization Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    INITIALIZATION                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. load_dotenv()                                            │
│     └── .env → environment variables                         │
│                                                              │
│  2. config = load_config()                                   │
│     └── config.yml → Dict                                    │
│                                                              │
│  3. debugger = Debugger(config)                              │
│                                                              │
│  4. event_bus = EventBus(debugger)                           │
│                                                              │
│  5. persistence = DatabaseConnection.from_env().connect()    │
│     └── Returns: PyMongoPersistence (CLI) or                 │
│                  MotorPersistence (API)                      │
│                                                              │
│  6. state = StateManager(event_bus, persistence)             │
│                                                              │
│  7. plugin_registry = PluginRegistry()                       │
│     └── discover() → load() → resolve()                      │
│                                                              │
│  8. phase_executor = PhaseExecutor(plugin_registry, state)   │
│                                                              │
│  9. task_manager = TaskManager(config['tasks'], state)       │
│                                                              │
│  10. orchestrator = Orchestrator(                            │
│          event_bus=event_bus,                                │
│          state=state,                                        │
│          persistence=persistence,                            │
│          phase_executor=phase_executor,                      │
│          task_manager=task_manager,                          │
│          config=config                                       │
│      )                                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. EXECUTION FLOW

### 4.1 High-Level Flow

```
orchestrator.run()
        │
        ▼
┌───────────────────┐
│ 1. _initialize()  │  Start run, emit run.started
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. _execute_phases│  INPUT → PARSE → METADATA → MODIFY
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. _execute_tasks │  Per-job task execution
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. _finalize()    │  Complete run, emit run.completed
└─────────┬─────────┘
          │
          ▼
       DONE
```

### 4.2 Detailed Execution

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE EXECUTION                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE: INPUT                                                │
│  ├── Execute: scanner.execute()                              │
│  ├── Output: List[Job]                                       │
│  └── For each job: state.register_job(index, path)           │
│                                                              │
│  PHASE: PARSE                                                │
│  ├── For each job:                                           │
│  │   ├── Validate requires                                   │
│  │   ├── Execute: renamer.execute(job)                       │
│  │   └── state.update_plugin(index, 'renamer', result)       │
│  └── Emit: phase.completed                                   │
│                                                              │
│  PHASE: METADATA                                             │
│  ├── TMDb (batch mode):                                      │
│  │   ├── Filter: jobs with renamer.parsed                    │
│  │   ├── Execute: tmdb.execute_batch(valid_jobs)             │
│  │   └── For each result: state.update_plugin(...)           │
│  ├── FFProbe (per_job mode):                                 │
│  │   └── Same as parse phase                                 │
│  └── Emit: phase.completed                                   │
│                                                              │
│  PHASE: MODIFY                                               │
│  ├── Splitter (batch mode):                                  │
│  │   ├── Input: all jobs                                     │
│  │   ├── Output: modified jobs list                          │
│  │   └── state.update_jobs(new_jobs)                         │
│  └── Emit: phase.completed                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Task Execution

```
┌─────────────────────────────────────────────────────────────┐
│                    TASK EXECUTION                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  For each job (index 0 to N-1):                              │
│  │                                                           │
│  ├── context = state.get_context(job_index=index)            │
│  │                                                           │
│  ├── For each task in config.tasks:                          │
│  │   │                                                       │
│  │   ├── Check condition (if any)                            │
│  │   │   └── Skip if condition false                         │
│  │   │                                                       │
│  │   ├── task.type == 'print':                               │
│  │   │   ├── rendered = template.render(task.template)       │
│  │   │   └── print(rendered)                                 │
│  │   │                                                       │
│  │   ├── task.type == 'save':                                │
│  │   │   ├── dest = template.render(task.destination)        │
│  │   │   ├── if not dry_run: copy(source, dest)              │
│  │   │   └── state.add_task_result(index, result)            │
│  │   │                                                       │
│  │   └── task.type == 'summary':                             │
│  │       └── Only execute on last job                        │
│  │                                                           │
│  └── state.complete_job(index)                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. ORCHESTRATOR IMPLEMENTATION

```python
class Orchestrator:
    """Central execution coordinator"""
    
    def __init__(
        self,
        event_bus: EventBus,
        state: StateManager,
        persistence: PersistenceInterface,
        phase_executor: PhaseExecutor,
        task_manager: TaskManager,
        config: Dict
    ):
        self._event_bus = event_bus
        self._state = state
        self._persistence = persistence
        self._phase_executor = phase_executor
        self._task_manager = task_manager
        self._config = config
        self._dry_run = config.get('options', {}).get('dry_run', False)
    
    def run(self) -> RunResult:
        """Execute complete run"""
        try:
            self._initialize()
            self._execute_phases()
            self._execute_tasks()
            self._finalize()
            return self._build_result(success=True)
        except Exception as e:
            self._handle_error(e)
            return self._build_result(success=False, error=str(e))
    
    def _initialize(self) -> None:
        """Start run, register handlers"""
        run_id = self._state.start_run(self._config)
        self._register_event_handlers()
    
    def _execute_phases(self) -> None:
        """Execute all plugin phases"""
        self._phase_executor.execute()
    
    def _execute_tasks(self) -> None:
        """Execute tasks for all jobs"""
        jobs = self._state.get_all_jobs()
        
        for i, job in enumerate(jobs):
            is_last = (i == len(jobs) - 1)
            context = self._state.get_context(job_index=job.index)
            
            self._task_manager.execute_for_job(
                context=context,
                job_index=job.index,
                is_last=is_last,
                dry_run=self._dry_run
            )
            
            self._state.complete_job(job.index)
    
    def _finalize(self) -> None:
        """Complete run, cleanup"""
        self._state.complete_run()
        self._persistence.flush()
    
    def _register_event_handlers(self) -> None:
        """Register progress and stats handlers"""
        self._event_bus.subscribe('job.completed', self._on_job_completed)
        self._event_bus.subscribe('job.failed', self._on_job_failed)
```

---

## 6. EVENT FLOW

```
Orchestrator                StateManager              EventBus
     │                           │                        │
     │ start_run()               │                        │
     ├──────────────────────────►│                        │
     │                           │ emit('run.started')    │
     │                           ├───────────────────────►│
     │                           │                        │
     │ register_job()            │                        │
     ├──────────────────────────►│                        │
     │                           │ emit('job.started')    │
     │                           ├───────────────────────►│
     │                           │                        │
     │ update_plugin()           │                        │
     ├──────────────────────────►│                        │
     │                           │ emit('plugin.completed')
     │                           ├───────────────────────►│
     │                           │                        │
     │ complete_job()            │                        │
     ├──────────────────────────►│                        │
     │                           │ emit('job.completed')  │
     │                           ├───────────────────────►│
     │                           │                        │
     │ complete_run()            │                        │
     ├──────────────────────────►│                        │
     │                           │ emit('run.completed')  │
     │                           ├───────────────────────►│
```

---

## 7. DOSYA YAPISI

```
src/archiverr/
├── __main__.py              # Entry point (~50 lines)
│
├── core/
│   ├── orchestrator.py      # Main coordinator
│   │
│   ├── plugins/
│   │   ├── registry.py      # Discovery + Loading
│   │   ├── resolver.py      # Dependency resolution
│   │   └── executor.py      # Phase execution
│   │
│   └── tasks/
│       ├── manager.py       # Task orchestration
│       └── template.py      # Template rendering
│
├── state/
│   ├── models.py            # RunState, JobState
│   └── manager.py           # State operations
│
├── events/
│   └── bus.py               # EventBus (MEVCUT)
│
└── infrastructure/
    └── persistence/
        ├── interface.py
        ├── pymongo.py
        └── motor.py
```

---

## 8. MEVCUT vs YENİ

### __main__.py Mevcut (simplified)

```python
def main():
    # 50+ lines of setup
    # 200+ lines of execution logic
    # Error handling scattered
    pass
```

### __main__.py Yeni

```python
def main():
    load_dotenv()
    config = load_config()
    
    # Build dependencies
    debugger = Debugger(config)
    event_bus = EventBus(debugger)
    persistence = get_persistence()
    state = StateManager(event_bus, persistence)
    
    # Build orchestrator
    orchestrator = build_orchestrator(
        config=config,
        event_bus=event_bus,
        state=state,
        persistence=persistence
    )
    
    # Run
    result = orchestrator.run()
    sys.exit(0 if result.success else 1)
```

---

## 9. ERROR HANDLING

```
┌─────────────────────────────────────────────────────────────┐
│                    ERROR PROPAGATION                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Plugin Error                                                │
│  └── Caught by PhaseExecutor                                 │
│      └── Mark job as failed                                  │
│          └── Continue with next job                          │
│                                                              │
│  Phase Error                                                 │
│  └── Caught by Orchestrator                                  │
│      └── Log error                                           │
│          └── Continue with next phase (best effort)          │
│                                                              │
│  Critical Error                                              │
│  └── Caught by Orchestrator                                  │
│      └── Mark run as failed                                  │
│          └── Finalize and exit                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

**Son Güncelleme:** 2025-11-30
