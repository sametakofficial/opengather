# STAGE EXECUTION MODEL

```yaml
date: 2025-12-02
type: technical-spec
status: final
```

---

## 1. CURRENT STATE

```
CURRENT EXECUTION (executor.py):

  1. execute_input_plugins()    # All input plugins
  2. For each match:
       execute_output_pipeline()  # All output plugins
```

**Problems:**
- Only 2 categories (input/output)
- No stage-based ordering within output
- No per_run vs per_job distinction at orchestrator level
- Output execution order relies solely on depends_on

---

## 2. PROPOSED STAGE MODEL

```
+--------+   +-------+   +----------+   +--------+
| INPUT  |-->| PARSE |-->| METADATA |-->| OUTPUT |
+--------+   +-------+   +----------+   +--------+
  per_run     per_job      per_job       per_job
```

### 2.1 Stage Definitions

```
STAGE       MODE      PURPOSE                    EXAMPLES
--------------------------------------------------------------------
INPUT       per_run   Create jobs from sources   scanner, file-reader
PARSE       per_job   Parse/extract from input   renamer, filename-parser
METADATA    per_job   Enrich with external data  tmdb, tvdb, ffprobe
OUTPUT      per_job   Produce final output       tasker, renamer-action
```

---

## 3. EXECUTION FLOW SCHEMA

```
+------------------------------------------------------------------+
|                      ORCHESTRATOR.RUN()                           |
+------------------------------------------------------------------+
|                                                                   |
|  1. INITIALIZATION                                               |
|     state.start_run(config)                                      |
|     capability_tracker = CapabilityTracker()                     |
|                                                                   |
|  2. INPUT STAGE (per_run)                                        |
|     +---------------------------------------------------------+  |
|     | for plugin in input_plugins:                             | |
|     |     jobs = plugin.execute_run(services)                  | |
|     |     for job in jobs:                                     | |
|     |         state.register_job(job)                          | |
|     |     capability_tracker.register(plugin.name, provides)   | |
|     +---------------------------------------------------------+  |
|                              |                                    |
|                              v                                    |
|  3. PARSE STAGE (per_job)                                        |
|     +---------------------------------------------------------+  |
|     | for job in state.get_jobs():                             | |
|     |     for plugin in parse_plugins:                         | |
|     |         if capability_tracker.check(plugin.requires):    | |
|     |             result = plugin.execute(job, services)       | |
|     |             state.update_job(job, plugin, result)        | |
|     |             capability_tracker.register(plugin, provides)| |
|     +---------------------------------------------------------+  |
|                              |                                    |
|                              v                                    |
|  4. METADATA STAGE (per_job)                                     |
|     +---------------------------------------------------------+  |
|     | for job in state.get_jobs():                             | |
|     |     for plugin in metadata_plugins:                      | |
|     |         if capability_tracker.check(plugin.requires):    | |
|     |             result = plugin.execute(job, services)       | |
|     |             state.update_job(job, plugin, result)        | |
|     +---------------------------------------------------------+  |
|                              |                                    |
|                              v                                    |
|  5. OUTPUT STAGE (per_job)                                       |
|     +---------------------------------------------------------+  |
|     | for job in state.get_jobs():                             | |
|     |     for plugin in output_plugins:                        | |
|     |         if capability_tracker.check(plugin.requires):    | |
|     |             result = plugin.execute(job, services)       | |
|     |             state.update_job(job, plugin, result)        | |
|     +---------------------------------------------------------+  |
|                              |                                    |
|                              v                                    |
|  6. FINALIZATION                                                 |
|     state.complete_run()                                         |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 4. PER_RUN VS PER_JOB SCHEMA

```
+---------------------+------------------------------------------+
|      per_run        |               per_job                    |
+---------------------+------------------------------------------+
|                     |                                          |
| execute_run()       |  for job in jobs:                        |
|      |              |      execute(job)                        |
|      v              |           |                              |
|  List[Job]          |           v                              |
|                     |      PluginResult                        |
+---------------------+------------------------------------------+

SIGNATURE:

  per_run:
    def execute_run(self, services: Services) -> List[Job]
    
  per_job:
    def execute(self, job: Job, services: Services) -> PluginResult
```

---

## 5. STAGE WITHIN DEPENDENCY RESOLUTION

```
+------------------------------------------------------------------+
|                    DEPENDENCY RESOLUTION                          |
+------------------------------------------------------------------+
|                                                                   |
|  INPUT:                                                          |
|    +----------------+                                            |
|    |   [scanner]    |  # No dependencies                         |
|    +----------------+                                            |
|            |                                                      |
|            v provides: data.input                                |
|                                                                   |
|  PARSE:                                                          |
|    +----------------+                                            |
|    |   [renamer]    |  # requires: data.input                    |
|    +----------------+                                            |
|            |                                                      |
|            v provides: data.parsed                               |
|                                                                   |
|  METADATA (topological sort within stage):                       |
|    +-------+   +--------+                                        |
|    | tmdb  |   | ffprobe|  # Both require data.parsed            |
|    +-------+   +--------+  # Can run in parallel                 |
|        |           |                                              |
|        v           v                                              |
|    data.metadata  data.mediainfo                                 |
|                                                                   |
|  OUTPUT:                                                         |
|    +----------------+                                            |
|    |   [tasker]     |  # requires: data.metadata                 |
|    +----------------+                                            |
|            |                                                      |
|            v provides: io.write                                  |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 6. PARALLEL EXECUTION WITHIN STAGE

```
METADATA STAGE PARALLELIZATION:

  Job 0:
    tmdb ----+
             +--> wait for all --> continue
    ffprobe -+
    
IMPLEMENTATION:

  async def execute_stage(stage: str, jobs: List[Job]):
      plugins = get_plugins_by_stage(stage)
      
      for job in jobs:
          # Find plugins that can run in parallel
          ready = [p for p in plugins 
                   if capability_tracker.check(p.requires)]
          
          # Execute in parallel
          results = await asyncio.gather(*[
              p.execute(job, services) for p in ready
          ])
          
          # Update state
          for plugin, result in zip(ready, results):
              state.update_job(job, plugin, result)
```

---

## 7. STAGE EXECUTOR IMPLEMENTATION

```python
class StageExecutor:
    """Execute plugins by stage with dependency resolution"""
    
    STAGES = ['input', 'parse', 'metadata', 'output']
    
    def __init__(self, registry: PluginRegistry, state: StateManager):
        self._registry = registry
        self._state = state
        self._tracker = CapabilityTracker()
    
    def execute_all(self) -> RunResult:
        for stage in self.STAGES:
            self._execute_stage(stage)
        return self._state.get_result()
    
    def _execute_stage(self, stage: str):
        plugins = self._registry.get_by_stage(stage)
        sorted_plugins = self._sort_by_requires(plugins)
        
        if stage == 'input':
            self._execute_input_stage(sorted_plugins)
        else:
            self._execute_job_stage(sorted_plugins, stage)
    
    def _execute_input_stage(self, plugins: List[Plugin]):
        for plugin in plugins:
            if plugin.mode != 'per_run':
                raise ConfigError(f'{plugin.name}: input plugins must be per_run')
            
            jobs = plugin.execute_run(self._build_services())
            for job in jobs:
                self._state.register_job(job)
            
            self._tracker.register(plugin.name, plugin.provides)
    
    def _execute_job_stage(self, plugins: List[Plugin], stage: str):
        for job in self._state.get_jobs():
            for plugin in plugins:
                if not self._tracker.check(plugin.requires):
                    self._state.skip_plugin(job, plugin, 'requires not met')
                    continue
                
                if plugin.mode == 'per_run':
                    # per_run in non-input stage: run once, apply to all
                    if not self._has_run_this_stage(plugin, stage):
                        plugin.execute_run(self._build_services())
                        self._mark_run(plugin, stage)
                else:
                    result = plugin.execute(job, self._build_services())
                    self._state.update_job(job, plugin, result)
                    self._tracker.register(plugin.name, result.provides)
```

---

## 8. STAGE TRANSITION EVENTS

```
EVENT                     WHEN                    PAYLOAD
--------------------------------------------------------------------
stage.started            Stage begins            {stage: str}
stage.completed          Stage ends              {stage: str, duration_ms: int}
job.stage.started        Job enters stage        {job_id: str, stage: str}
job.stage.completed      Job exits stage         {job_id: str, stage: str}
```

---

## 9. ERROR HANDLING

```
ERROR STRATEGY BY STAGE:

  INPUT:
    Plugin error -> FATAL (no jobs created)
    
  PARSE:
    Plugin error -> Mark job as failed, continue with next job
    
  METADATA:
    Plugin error -> Mark plugin as failed for job, continue
    
  OUTPUT:
    Plugin error -> Mark plugin as failed for job, continue
    
SCHEMA:

  +--------------------------------------------------+
  |               ERROR PROPAGATION                   |
  +--------------------------------------------------+
  |                                                   |
  |  INPUT ERROR:                                    |
  |    scanner.execute() throws                      |
  |         |                                         |
  |         v                                         |
  |    Run.status = FAILED                           |
  |    Run.error = "Input plugin failed: ..."        |
  |    EXIT                                          |
  |                                                   |
  |  PARSE/METADATA/OUTPUT ERROR:                    |
  |    plugin.execute() throws                       |
  |         |                                         |
  |         v                                         |
  |    Job.plugins[name].status = FAILED             |
  |    Job.plugins[name].error = "..."               |
  |    CONTINUE with next plugin/job                 |
  |                                                   |
  +--------------------------------------------------+
```

---

## CHANGELOG

```
- Removed: 6-stage model (INPUT/PARSE/METADATA/MODIFY/FINALIZE/OUTPUT)
- Simplified: 4-stage model (INPUT/PARSE/METADATA/OUTPUT)
- Added: Stage-based execution with capability tracking
- Added: Parallel execution within stages
- Added: Stage transition events
- Added: Clear error handling per stage
```

---

**Status: FINAL - Ready for implementation**
