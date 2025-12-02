# FINAL DECISIONS - SESSION 11

```yaml
date: 2025-11-30
sources: v1-v7, brainstorm v1-v2
status: final
```

---

## TERMINOLOGY

| Old | New | Notes |
|-----|-----|-------|
| ExecutionState | RunState | Class name |
| MatchState | JobState | Class name |
| execution | run | Context key (old removed) |
| match | job | Context key (old removed) |
| matches | jobs | Context key (old removed) |
| not_supported | skipped | Status value |
| SDK | Plugin Services | Conceptual rename |
| plugin.json | manifest.yml | File format |
| depends_on | (removed) | Use requires only |
| expects | requires | Field rename |
| category | phase | Manifest field |
| batch | per_run | Execution mode |

---

## STATE STRUCTURE

```
RunState
├── id: str
├── status: RunStatus
│   ├── state: pending|running|completed|failed
│   ├── success: bool
│   ├── total_jobs: int
│   ├── completed: int
│   ├── failed: int
│   └── timing fields
└── config: Dict

JobState
├── index: int
├── job_id: str (global unique)
├── run_id: str
├── input: JobInput
│   ├── path: str
│   ├── category: str
│   └── virtual: bool
├── status: JobStatus
├── output: JobOutput
└── plugins: Dict[str, Any]
```

---

## PHASE SYSTEM

```
Phase        Category    Mode        Description
─────────────────────────────────────────────────────────
input        INPUT       per_run     Job creation
parse        INPUT       per_job     Input parsing
metadata     OUTPUT      per_job     External API data
modify       OUTPUT      per_job/run Job manipulation
finalize     OUTPUT      per_run     Final sync, cleanup
output       TASK        per_job     Task execution (NOT plugin)
```

---

## MANIFEST FORMAT

```yaml
name: string
version: string
phase: input|parse|metadata|modify|finalize
execution_mode: per_job|per_run
priority: int (1-255, default: 100)
requires: [path.to.data]
subscribes: [event.name]        # EventBus
class_name: string
config_schema: {...}
```

---

## EXECUTION FLOW

```
1. __main__.py          → Parse args, build deps
2. Orchestrator.run()   → Coordinate execution
3. PhaseExecutor        → Execute INPUT → PARSE → METADATA → MODIFY
4. TaskManager          → Execute tasks per job
5. Finalize             → Complete run, flush to MongoDB
```

---

## MEMORY MANAGEMENT

```
Config:
  max_state_mb: 500
  flush_threshold: 0.8
  eviction_policy: completed_first

Strategy:
  - Track memory per job
  - Flush completed jobs to MongoDB at threshold
  - Lazy load from MongoDB when needed
```

---

## MONGODB COLLECTIONS

```
runs     → Run-level data
jobs     → Job-level data
plugins  → Plugin results per job
```

---

## VALIDATION

```
Config       → Startup validation
Manifest     → Discovery-time validation
Requires     → Pre-execution validation (SKIP if missing)
Runtime      → Error logging, continue execution
```

---

## NO BACKWARD COMPATIBILITY NEEDED

```
Henüz published olmadığımız için:
- Eski terimler (execution, match, matches) kaldırıldı
- Yeni terimler (run, job, jobs) kullanılıyor
- Short aliases eklendi: r, j, o
- Custom aliases: Jinja2 {% set %} ile
```

---

## NOT CHANGING

```
EventBus            → Already exists, functional
executor.py         → Refactor, not replace
tmdb.movie          → Plugin data structure unchanged
Template syntax     → $ syntax still works
MongoDB connection  → PyMongo (CLI) / Motor (API)
```

---

## IMPLEMENTATION PRIORITY

```
1. State models (RunState, JobState)
2. Manifest migration (json → yml)
3. Phase executor
4. Orchestrator
5. Plugin Services (JobService, TaskService)
6. Memory management
7. Tests
```

---

## ESTIMATED EFFORT

```
Component                Hours
───────────────────────────────
State models             2
Manifest migration       1
Phase executor           2
Orchestrator             2
Plugin Services          2
Memory management        3
Tests                    3
─────────────────────────────
Total                   15
```

---

## FILES TO CREATE

```
core/orchestrator.py
core/plugins/services.py
core/plugins/events.py           # Event coordination
infrastructure/memory/tracker.py
infrastructure/memory/flush.py
infrastructure/memory/loader.py
infrastructure/config/loader.py
infrastructure/config/validator.py
tasks/                           # External task directory
```

---

## FILES TO MODIFY

```
__main__.py (simplify)
state/models.py (nested dataclasses)
state/manager.py (memory integration)
core/plugins/executor.py (phase-based)
core/plugins/base.py (PluginResult update)
core/tasks/template.py (context aliases)
```

---

## FILES TO DELETE/DEPRECATE

```
None - incremental migration
```

---

**Session 11 Strategy Complete**
**Ready for Execution**
