# ORCHESTRATOR & EXECUTION FLOW

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/03_STAGE_EXECUTION.md, 08_IMPLEMENTATION.md
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- per_run: input stage (scanner, vs.)
- per_job: parse, data, output stages
- error handling: plugin fail = skip, stage fail = continue, run fail = critical only
- run asla durmasin felsefesi
```

---

## CURRENT KOD DURUMU

```
CURRENT (__main__.py):
  - 392 satir, tum logic burada
  - GlobalStateManager kullaniliyor
  - Orchestrator YOK

STRATEJI (hedef):
  - __main__.py ~50 satir
  - Orchestrator sinifi ayri
  - DI pattern tam uygulama
```

---

## 1. MIMARI

```
+----------------------------------------------------------+
|                    MIMARI KARAR                           |
+----------------------------------------------------------+
|                                                           |
|  MEVCUT:                                                  |
|  __main__.py = 400+ satir (SRP ihlali)                   |
|                                                           |
|  YENI:                                                    |
|  __main__.py (~50 satir) -> Orchestrator (~200 satir)    |
|                                                           |
+----------------------------------------------------------+
```

### Component Diagram

```
                         __main__.py
                             |
                             v
+----------------------------------------------------------+
|                        Orchestrator                       |
+----------------------------------------------------------+
|  Dependencies (injected):                                 |
|    EventBus, StateManager, Persistence                   |
|    PluginRegistry, StageExecutor, TaskManager            |
|                                                           |
|  Methods:                                                 |
|    run() -> RunResult                                    |
|    _initialize()                                         |
|    _execute_stages()                                     |
|    _finalize()                                           |
+----------------------------------------------------------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
   StateManager        StageExecutor       TaskManager
```

---

## 2. STAGE EXECUTION (4 STAGE)

```
                    ORCHESTRATOR
                         |
                         v
+----------------------------------------------------------+
|                    STAGE LOOP                             |
|                                                           |
|  for stage in [INPUT, PARSE, DATA, OUTPUT]:           |
|      plugins = get_plugins_by_stage(stage)               |
|      sorted = topological_sort_by_requires(plugins)      |
|      execute_stage(sorted)                               |
|                                                           |
+----------------------------------------------------------+
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
    +-------+        +--------+        +-------+
    | INPUT |        | PARSE  |        | DATA  |
    +-------+        +--------+        +-------+
        |                |                |
        v                v                v
    per_run          per_job           per_job
    scanner          renamer           tmdb,tvdb
        |                |                |
        v                v                v
    job.created      metadata.         http.response
                     parsed            metadata.movie
                                          |
                                          v
                                      +-------+
                                      | OUTPUT|
                                      +-------+
                                          |
                                          v
                                      per_job
                                      tasker
                                          |
                                          v
                                      fs.write
```

---

## 3. EXECUTION FLOW

### High-Level

```
orchestrator.run()
        |
        v
+-------------------+
| 1. _initialize()  |  Start run, emit run.started
+-------------------+
        |
        v
+-------------------+
| 2. _execute_stages|  INPUT -> PARSE -> DATA -> OUTPUT
+-------------------+
        |
        v
+-------------------+
| 3. _finalize()    |  Complete run, emit run.completed
+-------------------+
        |
        v
      DONE
```

### Stage Execution Detail

```
+----------------------------------------------------------+
|                    STAGE EXECUTION                        |
+----------------------------------------------------------+
|                                                           |
|  INPUT STAGE (per_run):                                   |
|    scanner.execute_run(services)                          |
|    --> jobs[] olusturuldu                                |
|                                                           |
|  PARSE STAGE (per_job):                                   |
|    for job in jobs:                                      |
|        renamer.execute(job, services)                    |
|                                                           |
|  DATA STAGE (per_job, paralel):                        |
|    for job in jobs:                                      |
|        tmdb.execute(job, services)    \                  |
|        tvdb.execute(job, services)     > Paralel         |
|        ffprobe.execute(job, services) /                  |
|                                                           |
|  OUTPUT STAGE (mixed):                                    |
|    for job in jobs:                                      |
|        tasker.execute(job, services)  # per_job          |
|    rclone.execute_run(services)       # per_run          |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. PARALEL EXECUTION

```
              PARALLEL EXECUTION

STAGE ARASI: Sequential (sirali)
  INPUT --> PARSE --> DATA --> OUTPUT

STAGE ICI: Parallel (ayni grup, requires satisfied)
  DATA: [tmdb, tvdb, ffprobe] --> Paralel

JOB ARASI: Configurable
  jobs[0] --> jobs[1] --> jobs[2]  (sequential)
  jobs[0..N]                        (parallel, optional)

+----------------------------------------------------------+
|                EXECUTOR LOGIC                             |
|                                                           |
|  for stage in STAGES:                                    |
|      groups = topological_sort(stage_plugins)            |
|                                                           |
|      for group in groups:                                |
|          if all(p.mode == 'per_run' for p in group):     |
|              # Paralel calistir                          |
|              await asyncio.gather(*[                     |
|                  p.execute_run(services)                 |
|                  for p in group                          |
|              ])                                          |
|          else:                                           |
|              # Job loop                                  |
|              for job in jobs:                            |
|                  await asyncio.gather(*[                 |
|                      p.execute(job, services)            |
|                      for p in group                      |
|                      if p.mode == 'per_job'              |
|                  ])                                      |
|                                                           |
+----------------------------------------------------------+
```

---

## 5. ERROR HANDLING

```
                ERROR PROPAGATION

+----------------------------------------------------------+
|                                                           |
|  PLUGIN ERROR                                             |
|    |                                                      |
|    +--> Job failed olarak isaretle                       |
|    +--> Sonraki plugin'ler skip (bu job icin)            |
|    +--> Diger job'lar etkilenmez                         |
|                                                           |
|  STAGE ERROR                                              |
|    |                                                      |
|    +--> Stage failed olarak isaretle                     |
|    +--> Sonraki stage'ler calisir (best effort)          |
|    +--> Run failed olarak isaretle                       |
|                                                           |
|  CRITICAL ERROR                                           |
|    |                                                      |
|    +--> Run durdurulur                                   |
|    +--> Cleanup calisir                                  |
|    +--> Exit code != 0                                   |
|                                                           |
+----------------------------------------------------------+
```

---

## 6. EVENT FLOW

```
Orchestrator                StateManager              EventBus
     |                           |                        |
     | start_run()               |                        |
     |-------------------------->|                        |
     |                           | emit('run.started')    |
     |                           |----------------------->|
     |                           |                        |
     | create_job()              |                        |
     |-------------------------->|                        |
     |                           | emit('job.created')    |
     |                           |----------------------->|
     |                           |                        |
     | update_plugin()           |                        |
     |-------------------------->|                        |
     |                           | emit('plugin.completed')
     |                           |----------------------->|
     |                           |                        |
     | complete_job()            |                        |
     |-------------------------->|                        |
     |                           | emit('job.completed')  |
     |                           |----------------------->|
     |                           |                        |
     | complete_run()            |                        |
     |-------------------------->|                        |
     |                           | emit('run.completed')  |
     |                           |----------------------->|
```

---

## 7. DOSYA YAPISI

```
src/archiverr/
|-- __main__.py              # Entry point (~50 lines)
|
|-- core/
|   |-- orchestrator.py      # Main coordinator
|   |
|   |-- plugins/
|   |   |-- registry.py      # Discovery + Loading
|   |   |-- resolver.py      # Dependency resolution (DAG)
|   |   |-- executor.py      # Stage execution
|   |   |-- services.py      # PluginServices
|   |   +-- validators.py    # Requires validation
|   |
|   +-- tasks/
|       |-- manager.py       # Task orchestration
|       +-- template.py      # Template rendering
|
|-- state/
|   |-- models.py            # RunState, JobState
|   +-- manager.py           # State operations
|
|-- events/
|   +-- bus.py               # EventBus
|
+-- infrastructure/
    +-- persistence/
        |-- interface.py
        |-- pymongo.py
        +-- motor.py
```

---

## 8. ORCHESTRATOR IMPLEMENTATION

```python
class Orchestrator:
    STAGES = ['input', 'parse', 'data', 'output']

    def __init__(
        self,
        event_bus: EventBus,
        state: StateManager,
        persistence: PersistenceInterface,
        stage_executor: StageExecutor,
        config: Dict
    ):
        self._event_bus = event_bus
        self._state = state
        self._persistence = persistence
        self._stage_executor = stage_executor
        self._config = config

    def run(self) -> RunResult:
        try:
            self._initialize()
            self._execute_stages()
            self._finalize()
            return self._build_result(success=True)
        except Exception as e:
            self._handle_error(e)
            return self._build_result(success=False, error=str(e))

    def _initialize(self) -> None:
        run_id = self._state.start_run(self._config)
        self._register_event_handlers()

    def _execute_stages(self) -> None:
        for stage in self.STAGES:
            self._stage_executor.execute_stage(stage)

    def _finalize(self) -> None:
        self._state.complete_run()
        self._persistence.flush()
```

**Uyari:** Ornek kod, direkt kopyalanmaz. Mevcut codebase ile uyumlu sekilde yeniden yazilmalidir.

---

## 9. MEVCUT vs YENI

```
MEVCUT (__main__.py):
  400+ satir
  - Config loading
  - Plugin discovery + loading
  - Dependency resolution
  - Input/output execution loop
  - Task execution
  - State management
  - Error handling scattered

YENI:
  __main__.py (~50 satir):
    load_config()
    orchestrator = build_orchestrator(...)
    result = orchestrator.run()
    sys.exit(0 if result.success else 1)

  Orchestrator:
    - Stage coordination (4 stage)
    - Plugin lifecycle
    - State orchestration
    - Error propagation

DEGISIKLIKLER:
  - SRP: __main__.py sadece entry point
  - 6 phase -> 4 stage
  - PhaseExecutor -> StageExecutor
  - Stage icinde paralel execution
```

---

**Son Guncelleme:** 2025-12-02
