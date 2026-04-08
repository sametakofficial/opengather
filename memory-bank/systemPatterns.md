# System Patterns

## Architecture Rules (STRICTLY ENFORCED)

### 1. Plugin-Agnostic Core
- Core MUST NEVER reference plugin names or implementations
- Zero hardcoded plugin names in core (ZERO tolerance)
- `test_plugin_agnostic.py` has static analysis guard that scans core source files
- Plugins declare stage, provides, requires in `manifest.yml`
- Core discovers via manifest files, resolves dependencies generically

### 2. Expects System (Runtime Validation)
```python
# Plugins declare what data they need
requires:
  - plugin.renamer.parsed:success

# Core checks at runtime before executing
available_data = extract_available_data(result)
ready = [p for p in group if resolver.check_expects(p, available_data)]
```

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
provides:             # REQUIRED - what this plugin provides
  - http.request
  - state.update
requires:             # Dependencies on other plugin data
  - plugin.renamer.parsed:success
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
```

### 6. Compact Response Pattern
Type-based structural simplification. Keep 1 example per type, discard redundant data.
Result: 145 KB -> 9 KB (94% reduction). Used for AI analysis.

### 7. No-Delete Policy
NEVER use rm/rmdir. Always `mkdir -p .deleted && mv target .deleted/`

### 8. Response Structure v4
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
