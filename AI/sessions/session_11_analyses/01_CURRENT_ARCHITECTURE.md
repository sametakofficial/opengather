# ARCHIVERR - CURRENT ARCHITECTURE ANALYSIS

```yaml
tarih: 2025-12-04
versiyon: session-11
durum: analysis
```

---

## 1. GENEL MIMARI

```
┌─────────────────────────────────────────────────────────────────┐
│                        __main__.py                               │
│                    (Entry Point ~170 loc)                        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Orchestrator                               │
│                    (orchestrator.py ~500 loc)                    │
│  - run lifecycle: initialize → execute_stages → finalize        │
│  - event emission                                                │
│  - error handling                                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐
│  PluginRegistry │ │StageExecutor│ │ StateManager │
│  (discovery)    │ │ (4-stage)   │ │ (state ops)  │
└────────┬────────┘ └──────┬──────┘ └──────────────┘
         │                 │
         │    ┌────────────┴────────────┐
         │    │                         │
         ▼    ▼                         ▼
    ┌────────────┐              ┌────────────────┐
    │  Plugins   │              │  TaskManager   │
    │ (per_job/  │              │  (print/save)  │
    │  per_run)  │              └───────┬────────┘
    └────────────┘                      │
                                        ▼
                               ┌────────────────┐
                               │TemplateManager │
                               │ (Jinja2 render)│
                               └────────────────┘
```

---

## 2. CONFIG LOADING WORKFLOW

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. load_config_with_tracking("config.yml")                        │
│    ├── load_yaml_with_includes()     → !include directive        │
│    ├── expand_env_vars()             → ${VAR} expansion          │
│    └── normalize_config()            → FlexGet style             │
└────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. Config Structure                                               │
│    options: {debug, dry_run, hardlink, memory}                   │
│    aliases: {m: job.plugins.tmdb.movie, ...}                     │
│    scanner: {...}                                                │
│    renamer: {...}                                                │
│    tmdb: {...}                                                   │
│    ffprobe: {timeout: 15, ...}                                   │
│    tasker: {tasks: [...]}                                        │
└────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. Orchestrator receives config                                   │
│    └── Passes to StageExecutor, PluginRegistry, TaskManager      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. TEMPLATE CONTEXT BUILD (CURRENT)

```python
# template_manager.py - render() method builds:
jinja_context = {
    'apiresponse': context,           # Full API response
    'globals': api_globals,           # API root globals
    'match_globals': match_globals,   # Current match globals
    'options': global_options,        # options from config
    'output': match_output,           
    'index': current_index,
    'total': len(matches),
    'matches': matches,
    
    # Alias support
    'execution': {...},
    'match': {...},
    
    # Plugin data (auto-injected)
    'tmdb': plugin_data,
    'renamer': plugin_data,
    ...
    
    # User aliases from config
    # (resolved via _resolve_alias_path)
}
```

### ⚠️ EKSİK: `config` alias inject edilmiyor!

```python
# PHILOSOPHY.md Section 9 - OLMASI GEREKEN:
SYSTEM_ALIASES = {
    'job': ...,
    'run': ...,
    'config': 'config',  # ← EKSİK!
}

# Template'de kullanım:
{{ config.ffprobe.timeout }}  # ← ÇALIŞMIYOR!
```

---

## 4. ALIAS RESOLUTION WORKFLOW

```
┌─────────────────────────────────────────────────────────────────┐
│ alias_resolver.py                                                │
│                                                                  │
│ SYSTEM_ALIASES (cannot override):                               │
│   job, jobs, run, options, index, count, globals                │
│                                                                  │
│ SHORT_ALIASES (can override):                                   │
│   j → job, r → run, o → options, g → globals                    │
│                                                                  │
│ USER_ALIASES (from config.aliases):                             │
│   m → job.plugins.tmdb.movie                                    │
│   p → job.plugins.renamer.parsed                                │
│   ...                                                           │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ AliasResolver.build_context(base_context)                       │
│                                                                  │
│ 1. Start with base_context (job, run, options, ...)            │
│ 2. Inject user aliases (m, p, ...)                              │
│ 3. Inject short aliases (j, r, o, g)                            │
│ 4. Return enhanced context                                       │
│                                                                  │
│ ⚠️ config is NOT injected into context!                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. PLUGIN EXECUTION FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│ StageExecutor.execute_stage(stage)                              │
│                                                                  │
│ For each stage in [INPUT, PARSE, DATA, OUTPUT]:                 │
│   1. Get plugins by stage                                       │
│   2. Topological sort by requires                               │
│   3. Execute plugins                                            │
│      ├── per_run: execute_run(services)                         │
│      └── per_job: for job in jobs: execute(job, services)       │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ PluginServices (injected to plugins)                            │
│                                                                  │
│ services.state   → StateServiceImpl                             │
│ services.events  → EventServiceImpl                             │
│ services.logger  → LoggerServiceImpl                            │
│ services.config  → ConfigServiceImpl                            │
│                                                                  │
│ ✓ services.config.get("ffprobe.timeout") WORKS                 │
│ ✗ {{ config.ffprobe.timeout }} in templates DOESN'T WORK       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. STATE STRUCTURE

```
RunState
├── id: str              "run_abc123"
├── status: RunStatus
│   ├── state: StateEnum (pending|running|completed|failed)
│   ├── success: bool
│   ├── total_jobs: int
│   ├── completed: int
│   └── failed: int
└── config: Dict         (frozen snapshot)

JobState  
├── id: str              "job_run_abc123_0"
├── index: int           0
├── run_id: str          "run_abc123"
├── input: InputData
│   ├── value: str       "/path/file.mkv"
│   └── data: Dict       {filename, extension, size_bytes}
├── output: OutputData
│   ├── values: List[str]
│   └── data: Dict
└── status: JobStatus
    ├── state: StateEnum
    ├── success: bool
    ├── executed: List[str]
    ├── failed: List[str]
    └── skipped: List[str]

PluginData (ayrı collection)
├── job_id: str
├── plugin_name: str
├── stage: str
├── status: Dict
└── data: Dict           (plugin-specific)
```

---

## 7. EVENT BUS FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│ EventBus Lifecycle Events                                        │
│                                                                  │
│ run.started    → Run initialized                                │
│ stage.started  → Stage began                                    │
│ stage.completed → Stage finished successfully                   │
│ stage.failed   → Stage failed                                   │
│ plugin.completed → Plugin executed                              │
│ plugin.failed  → Plugin error                                   │
│ job.completed  → Job finished                                   │
│ run.completed  → Run finished                                   │
│ run.error      → Run error occurred                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. REQUIRES/PROVIDES SYSTEM

### Requires (Dependency Declaration)

```yaml
# manifest.yml
requires:
  - job.plugins.renamer.parsed     # State path
  - provides.http.request          # Provide completion
  - events.file.created            # Event fired
```

### Provides (Technical Effect Declaration)

```yaml
# manifest.yml
provides:
  - fs.read
  - fs.write
  - http.request
  - state.update
  - job.create
  - process.spawn
```

### Lockable vs Non-lockable

```
LOCKABLE (conflict detection):
  fs.write, fs.delete, fs.move, fs.hardlink, fs.symlink

NON-LOCKABLE (parallel safe):
  fs.read, fs.copy, fs.mkdir, http.request, state.update
```

---

## 9. VALIDATION LAYERS

```
STARTUP VALIDATION:
├── ConfigValidator      → YAML syntax, schema
├── ManifestValidator    → Plugin manifests
└── DependencyValidator  → Requires satisfaction

PRE-EXECUTION VALIDATION:
├── RequiresValidator    → Path format check
└── TriggerRuleValidator → Condition check

RUNTIME VALIDATION:
├── Template rendering   → Jinja2 errors
└── File operations      → FS errors
```

---

## 10. CURRENT ISSUES IDENTIFIED

| Issue | Location | Impact |
|-------|----------|--------|
| `config` alias missing | alias_resolver.py, template_manager.py | `{{ config.ffprobe.timeout }}` doesn't work |
| Legacy terminology | Various | `execution` vs `run`, `match` vs `job` |
| Template context incomplete | template_manager.py | Missing system aliases |
| TaskManager doesn't have config ref | task_manager.py | Can't pass config to TemplateManager |

---

**Son Güncelleme:** 2025-12-04
