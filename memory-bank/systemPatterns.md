# System Patterns

## Architecture Rules (STRICTLY ENFORCED)

### 1. Plugin-Agnostic Core
- Core MUST NEVER reference plugin names or implementations
- Zero hardcoded plugin names in core (ZERO tolerance)
- `test_plugin_agnostic.py` has static analysis guard that scans core source files
- Session 39 baseline: plugin-agnostic guard remains 9/9 PASS after data resolver + render refactor
- Plugins declare stage, run mode, provides, requires, and optional emits in `manifest.yml`
- Core discovers via manifest files, resolves dependencies generically

### 2. Requires System (Runtime Validation)
```yaml
# Plugins declare what data they need
requires:
  - plugin.renamer.parsed:success
```
Core checks required plugin state/data generically before execution. Plugin-specific validation stays inside plugins.

### 3. 3-Stage Pipeline
```
INIT -> PER_RUN (input plugins) -> PARSE -> DATA -> OUTPUT -> FINALIZE
```
Each stage executes plugins in dependency-resolved groups. Parallel within groups.

### 4. Manifest-Driven Plugin Discovery
```yaml
# Every plugin declares in manifest.yml:
name: tmdb
stage: data           # REQUIRED - no inference from plugin name
run_mode: per_job     # REQUIRED - per_run or per_job
provides:             # Capabilities / locks provided by plugin
  - http.request
  - state.update
requires:             # Dependencies on other plugin data
  - plugin.renamer.parsed:success
emits:                # Optional data resolver declaration
  show:
    - title.primary
    - identifiers.tmdb_id
```
Discovery priority: manifest.yml > manifest.yaml > plugin.yml > plugin.yaml > plugin.json

### 5. State Management (SRP)
```
GlobalStateManager
  -> JobManager (job lifecycle)
  -> PluginDataManager (plugin data CRUD)
  -> PersistenceDelegate (MongoDB writes, error handling)
  -> StateEventEmitter (EventBus events)
  -> TemplateContextBuilder (Jinja2 context)
  -> DataResolver (run.data envelope recomputation)
```

### 6. Data Resolver Namespace
```
data.<jobindex>.<category>.<dotted.path>
```
- Resolver priority comes from config `data_priority`.
- Priority matching uses longest-prefix semantics.
- Plugins opt in through manifest `emits`; undeclared plugin payload remains available through `job.plugins` / `jobs[...]` but not through the prioritized `data.*` namespace.
- `RunState.data` is recomputed after plugin updates and persisted under `runs.data`.
- Persistence boundary stringifies integer job-index keys for Mongo compatibility.

### 7. Render Engine Boundary
- Jinja2 rendering lives in `core/render/ConfigRenderEngine` with `ChainableUndefined`.
- `tasker` no longer owns Jinja2; it receives already rendered runtime config through services and dispatches print/save actions.
- Parse-time template dependency validator warns when templates reference plugins not declared in `manifest.requires`.
- Synthetic `plugin.<name>.{data,status}` template namespace is removed.
- Templates use `jobs[job_id].plugins.<name>`, `job.plugins.<name>`, `data.*`, and `run.*`.

### 8. Compact Response Pattern
Type-based structural simplification. Keep 1 example per type, discard redundant data.
Result: 145 KB -> 9 KB (94% reduction). Used for AI analysis.

### 9. No-Delete Policy
NEVER use rm/rmdir. Always `mkdir -p .deleted && mv target .deleted/`

### 10. Response Structure v4
```
response.globals.status        -> Run-level status
response.matches[].globals     -> Job-level status
response.matches[].plugins.X   -> Plugin data (plugin-managed)
```
Validation lives in `plugin.globals.validation`, never aggregated by core.

## Design Patterns Used

| Pattern | Location | Notes |
|---------|----------|-------|
| Factory | `build_orchestrator()` | Assembles orchestrator with DI |
| Registry | `PluginRegistry` | Plugin discovery/loading |
| Observer | `EventBus` | Loose coupling between components |
| Strategy | Executor + Resolver | Pluggable execution strategies |
| DI | `ExecutionContext` | Runtime dependencies for plugins |
| Template Method | `BasePlugin.execute()` | Plugin execution contract |
