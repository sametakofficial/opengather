# Session 31 - Deep Plugin System Brainstorm

**Date:** April 10, 2026
**Branch:** `dev/communication-refactoring`
**Focus:** Plugin system architecture brainstorm -- 3-agent parallel analysis
**Type:** Planning / Analysis

---

## Executive Summary

3 specialized sub-agents analyzed the plugin system simultaneously from different perspectives:
1. **Architecture Reviewer** -- structural analysis, semantic gaps, execution flow
2. **Simplifier (YAGNI Audit)** -- wired vs orphaned code
3. **Data Flow Analyzer** -- actual plugin communication patterns

The results are highly consistent and reveal a clear picture: **the plugin system has excellent bones but significant wiring gaps**. The core abstractions are well-designed but many never got connected to the execution pipeline.

---

## 1. THE BIG PICTURE: What Works vs What Doesn't

### Actually Wired and Working
| System | Status | Evidence |
|--------|--------|----------|
| Trigger Rules | WIRED | `stage_executor.py:347-378` evaluates trigger rules before every plugin execution |
| EventBus (emission) | WIRED | Orchestrator + StageExecutor actively emit run/stage/plugin events |
| PluginServices (concrete) | WIRED | `core/services/plugin_services.py` -- the class executors actually use |
| FSLockManager (validation) | PARTIAL | Validates manifests at startup, but never acquires/releases locks at runtime |
| Plugin data flow via job.plugins | WIRED | StageExecutor stores plugin results, plugins read via job.plugins |
| Manifest discovery + loading | WIRED | PluginRegistry discovers, loads, organizes by stage |

### Orphaned (Built But Never Connected)
| System | Lines | Evidence |
|--------|-------|----------|
| ProvidesRegistry | ~400 LOC | Never consulted during execution. complete()/fail() never called |
| ProvidesServiceImpl | ~90 LOC | Wraps ProvidesRegistry. Never reaches plugins |
| PluginServices (protocol-based dataclass) | ~120 LOC | `core/services/__init__.py` -- different class than what pipeline uses |
| Protocol definitions | ~100 LOC | `protocols.py` -- StateService, EventService etc. Only used by dead dataclass |
| DependencyResolver | ~160 LOC | Proper topo sort with cycle detection. Never instantiated |
| StartupValidator | ~200 LOC | `validate_at_startup()` never called. Orchestrator does ad-hoc validation instead |
| AliasResolver (class) | ~80 LOC | Duplicate of working function in config_loader.py |
| Event handlers | ~180 LOC | DebugHandler, ProgressHandler, ConsoleProgressHandler, StatisticsHandler -- never instantiated |
| **Total orphaned** | **~1,330 LOC** | |

---

## 2. CRITICAL FINDING: The provides/requires Semantic Gap

This is the single most important architectural issue in the project.

### Current State

**provides** declares generic capabilities:
```yaml
# tmdb manifest
provides:
  - http.request      # "I make HTTP calls"
  - state.update      # "I update state"
```

**requires** declares specific data paths:
```yaml
# tmdb manifest
requires:
  - plugin.renamer.parsed:success   # "I need renamer's parsed data to succeed"
```

### The Problem

These two systems **never intersect**:

1. `StageExecutor._check_plugin_requires()` resolves requires via `TriggerRuleManager` -> `ValueMatcher` -> dot-notation path lookup against global state. **It never checks ProvidesRegistry.**

2. `StageExecutor._group_parallel_plugins()` does set intersection on provides/requires strings for parallel grouping. But `{"http.request", "state.update"}` vs `{"plugin.renamer.parsed:success"}` will **never intersect** -- different namespaces. So the parallelization logic is effectively a no-op: it always concludes there are no conflicts.

3. No manifest's `requires` ever references another plugin's `provides`. The `provides.*` prefix is supported by RequiresValidator but unused.

### Why This Matters

The provides field is pure metadata decoration. It has **zero functional impact** on:
- Execution ordering
- Parallel grouping
- Dependency resolution
- Lock management

The actual orchestration works entirely through state-path-based requires (`plugin.renamer.parsed:success`) and trigger rules.

### What a Real provides System Could Be

**Option A: Data Contract provides (recommended)**
```yaml
# tmdb manifest
provides:
  - data.movie          # "I produce movie metadata"
  - data.show           # "I produce show metadata"
  - data.validation     # "I produce validation results"

# tasker manifest  
requires:
  - provides.data.movie:completed    # "I need movie data from someone"
  # NOT: plugin.tmdb.data:success    # This hardcodes the source
```

This makes plugins truly decoupled -- tasker doesn't need to know WHO provides movie data, just THAT it's available.

**Option B: Keep capability provides but make them functional**
Wire ProvidesRegistry into StageExecutor so it actually tracks and gates execution.

**Option C: Drop provides entirely, formalize requires**
Accept that requires uses plugin names directly and that provides is decoration. Remove the orphaned infrastructure.

---

## 3. TWO PluginServices CLASSES

### The Conflict

Two completely separate implementations exist:

1. **`core/services/plugin_services.py`** (the real one)
   - Concrete class with `_state`, `_event_bus`, `_logger`, `_config`
   - Methods: `create_job()`, `update_plugin()`, `emit()`, `update_status()`
   - **No `provides` field**
   - Used by: StageExecutor, PerRunPluginExecutor

2. **`core/services/__init__.py`** (the dead one)
   - `@dataclass` with protocol-typed fields: `state: StateService`, `events: EventService`, `provides: ProvidesService`
   - Created by `create_plugin_services()` factory
   - **Never used by any executor**
   - References: ProvidesServiceImpl, all Protocol definitions

### Decision Needed

Either:
- **Merge**: Bring the protocol-based design INTO the concrete class (add provides, type with protocols)
- **Keep concrete**: Accept the concrete class is the real API. Move the dead dataclass + protocols to `.deleted/`

---

## 4. PLUGIN INTERFACE: 22 hasattr Checks

The executor uses runtime introspection instead of a proper plugin interface:

```python
# stage_executor.py -- current approach
if hasattr(plugin, 'execute'):
    sig = inspect.signature(plugin.execute)
    params = list(sig.parameters.keys())
    if len(params) >= 2:
        return plugin.execute(job, services)  # new style
    else:
        return plugin.execute(legacy_data)    # legacy
elif hasattr(plugin, 'process'):
    return plugin.process(legacy_data, {})    # very legacy
```

### What Should Exist

```python
# Two clear interfaces
class PerRunPlugin(Protocol):
    name: str
    def execute_run(self, services: PluginServices) -> dict: ...

class PerJobPlugin(Protocol):
    name: str
    def execute(self, job: JobState, services: PluginServices) -> PluginResult: ...
```

Then the executor dispatches by run_mode (from manifest), not by hasattr probing.

### Current Plugin Method Usage

| Plugin | run_mode | Method | Style |
|--------|----------|--------|-------|
| scanner | per_run | `execute_run(services)` | New |
| file-reader | per_run | `execute_run(services)` | New (but returns list, doesn't create jobs) |
| renamer | per_job | `execute(job, services)` | New |
| tmdb | per_job | `execute(job, services)` | New |
| ffprobe | per_job | `execute(job, services)` | New |
| tasker | per_job | `execute(job, services)` | New |
| tvdb | per_job | `execute(match_data)` | Legacy |
| tvmaze | per_job | `execute(match_data)` | Legacy |
| omdb | per_job | `execute(match_data)` | Legacy |

3 legacy plugins need migration to eliminate hasattr checks.

---

## 5. DUAL TOPOLOGICAL SORT

Two implementations exist:

1. **`resolver.py` DependencyResolver** -- Proper algorithm with cycle detection (DFS), dependency graph, group-based sort. **Never used.**

2. **`stage_executor.py._topological_sort()`** -- Just sorts by `len(requires)`. Not a real topo sort. **Actually used.**

The StageExecutor's version works for linear chains but breaks for diamond dependencies. Since the real DependencyResolver exists and is better, it should replace the pseudo-sort.

---

## 6. MANIFEST ACCURACY AUDIT

### Undeclared Dependencies (ffprobe)

tmdb, tvdb, and omdb all read `ffprobe.container.duration` for validation but none declare it in their `requires`:

| Plugin | Reads ffprobe? | Declared in requires? |
|--------|---------------|----------------------|
| tmdb | `job.plugins.get('ffprobe', {})` (client.py:147) | NO |
| tvdb | `match_data.get('ffprobe', {})` (client.py:138) | NO |
| omdb | `match_data.get('ffprobe', {})` (client.py:152) | NO |

This means if ffprobe hasn't run yet or fails, these plugins silently get empty data.

### provides Mismatches

| Plugin | Claims provides | Actually does? |
|--------|----------------|---------------|
| tvdb | `state.update` | Never calls `services.update_plugin()` |
| tvmaze | `state.update` | Never calls `services.update_plugin()` |
| omdb | `state.update` | Never calls `services.update_plugin()` |
| file-reader | `job.create` | Never calls `services.create_job()` |

### Tasker Over-Constraint

Tasker's manifest requires `plugin.tmdb.data:success` and `plugin.renamer.data:success`. But:
- Tasker reads ALL plugins dynamically (plugin.py:79-86)
- It should work without tmdb if configured for non-tmdb tasks
- `trigger_rule: all_done` means it runs regardless, but the requires still create unnecessary coupling

### OMDb Bug

`omdb/client.py:38-39` reads `match_data.get('input', {}).get('category')`, but `_job_to_legacy_data()` puts input data under `input.data`, not at `input` root. Category actually comes from renamer's output (`renamer.category`). This means OMDb's category detection is likely always `'unknown'`.

---

## 7. CROSS-PLUGIN COUPLING MAP

All data-stage plugins hardcode plugin names:

```
tmdb     -> reads 'renamer', 'ffprobe' by name
tvdb     -> reads 'renamer', 'ffprobe' by name
tvmaze   -> reads 'renamer' by name
omdb     -> reads 'renamer', 'ffprobe' by name
tasker   -> reads 'renamer' by name (convenience shortcuts)
```

This is **expected and acceptable** for plugin-to-plugin communication. Plugins knowing each other is fine -- the rule is that CORE must not know plugin names. But it does highlight that:

1. Renamer is effectively a **required infrastructure plugin** (every other plugin depends on it)
2. ffprobe is an **optional but widely-used** infrastructure plugin
3. These relationships should be declared in manifests (currently undeclared for ffprobe)

---

## 8. EVENT SYSTEM: Broken Progress Tracking

### Legacy Event Name Mismatch

Event handlers listen for legacy names that the new pipeline never emits:

| Handler | Listens for | Pipeline emits |
|---------|------------|----------------|
| ProgressHandler | `MATCH_COMPLETED`, `MATCH_FAILED` | `PLUGIN_COMPLETED`, `PLUGIN_FAILED` |
| ConsoleProgressHandler | `MATCH_COMPLETED`, `EXECUTION_STARTED` | `PLUGIN_COMPLETED`, `RUN_STARTED` |
| StatisticsHandler | mixed legacy + new | partial match |

### Event Usage

- 28 event constants defined in `Events` class
- ~8 actually emitted by the pipeline
- 20 aspirational (never emitted)
- `on_job_completed` handler is a no-op (body is `pass`)

---

## 9. BRAINSTORM: STRATEGIC DIRECTIONS

Given all findings, here are the key strategic decisions to make:

### Decision 1: provides System Future

| Option | Effort | Benefit | Risk |
|--------|--------|---------|------|
| A: Data contract provides | HIGH | True plugin decoupling, marketplace-ready | Over-engineering for 9 plugins |
| B: Wire existing ProvidesRegistry | MEDIUM | Provides becomes functional | Still generic capabilities |
| C: Drop provides, keep requires only | LOW | Clean up ~500 LOC dead code | Lose future extensibility |
| **D: Hybrid -- keep provides in manifest as documentation, wire for parallel grouping only** | **LOW-MEDIUM** | **Honest about what it does** | **None** |

### Decision 2: Plugin Interface

| Option | Effort | Benefit |
|--------|--------|---------|
| A: `typing.Protocol` (duck typing with type checking) | LOW | Minimal change, mypy catches issues |
| B: ABC with registration decorator | MEDIUM | Stronger enforcement |
| **C: Protocol + migration of 3 legacy plugins** | **MEDIUM** | **Eliminates all hasattr, clean interface** |

### Decision 3: Orphaned Code

| Action | ~LOC | Priority |
|--------|------|----------|
| Move dead PluginServices dataclass + protocols to .deleted/ | ~220 | Could wait |
| Wire or remove ProvidesRegistry | ~490 | Decision 1 dependent |
| Wire DependencyResolver or merge into StageExecutor | ~160 | HIGH -- actual correctness issue |
| Wire StartupValidator | ~200 | MEDIUM -- validation exists but disconnected |
| Fix event handler names | ~20 | LOW -- handlers aren't used anyway |

### Decision 4: Legacy Plugin Migration

3 plugins (tvdb, tvmaze, omdb) use legacy `execute(match_data)` interface:
- Migrate to `execute(job, services)` 
- Update to use `services.update_plugin()` instead of returning raw dicts
- Properly declare ffprobe dependency in manifests
- Fix OMDb category bug

---

## 10. RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Correctness (no new features, just fix what's broken)
1. Fix OMDb category bug
2. Add missing ffprobe dependency to tmdb/tvdb/omdb manifests
3. Wire DependencyResolver (replace pseudo topo-sort in StageExecutor)
4. Wire StartupValidator into orchestrator._initialize()

### Phase 2: Plugin Interface Cleanup
5. Define PerRunPlugin and PerJobPlugin protocols
6. Migrate tvdb, tvmaze, omdb to new execute(job, services) interface
7. Remove hasattr-based dispatch from StageExecutor

### Phase 3: provides System Decision
8. Either wire ProvidesRegistry for parallel grouping or move to .deleted/
9. Clean up the dead PluginServices dataclass + protocols
10. Update manifest provides values to be accurate (or remove if going with Option C)

### Phase 4: Wiring Gaps
11. Wire FSLockManager acquire/release during plugin execution
12. Wire EventBus progress tracking (or remove dead handlers)
13. Connect persistence handlers properly (fix on_job_completed no-op)

---

## Appendix: Data Flow Diagram

```
                    +-----------+
                    |  config   |  (frozen at startup)
                    +-----+-----+
                          |
                    +-----v-----+
        per_run --> |  scanner  | --> creates jobs (input.value + input.data)
                    +-----------+
                          |
                    +-----v-----+
        PARSE   --> |  renamer  | --> job.plugins.renamer = {parsed, category}
                    +-----------+
                          |
              +-----------+-----------+-----------+
              |           |           |           |
        +-----v--+  +----v---+  +----v----+  +---v----+  +--------+
 DATA   | ffprobe|  |  tmdb  |  |  tvdb   |  | tvmaze |  |  omdb  |
        | video  |  | movie  |  | show    |  | show   |  | movie  |
        | audio  |  | show   |  | episode |  | episode|  | show   |
        | contanr|  |        |  |         |  |        |  |        |
        +--------+  +----+---+  +----+----+  +---+----+  +---+----+
              |           |           |           |           |
              +-----------+-----------+-----------+-----------+
                          |
                    +-----v-----+
       OUTPUT   --> |  tasker   | --> reads ALL plugins dynamically
                    |           |    writes: output.values, output.data
                    +-----------+

  * = undeclared dependency (ffprobe -> tmdb, tvdb, omdb)
  Renamer coupling: tmdb, tvdb, tvmaze, omdb, tasker all hardcode 'renamer'
```

---

*Session 31 -- brainstorm complete. 3 parallel sub-agents used.*
*Next session should: make decisions on the 4 strategic questions, then execute Phase 1.*
