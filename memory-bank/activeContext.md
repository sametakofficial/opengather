# Active Context

**Last Updated:** Session 31 - April 10, 2026
**Version:** v2.3.2-dev
**Branch:** `dev/communication-refactoring`

## What Just Happened (Session 31)

### Completed
1. **DependencyResolver wired into StageExecutor** - Replaced `len(requires)` pseudo-sort with proper topological sort and cycle detection via `_resolve_execution_groups()`
2. **ProvidesRegistry wired into execution lifecycle** - Register on init from manifests, complete/fail after plugin execution, injected into global_state for trigger evaluation
3. **StartupValidator wired into Orchestrator._initialize()** - Config, manifest, dependency validation at startup; replaces legacy `validate_dependencies()`
4. **DependencyResolver fixed** - Now handles `plugin.*.field:success` requires format (strips value matcher suffix)
5. **OMDb category bug fixed** - Was reading category from wrong path (`input.category` instead of `plugins.renamer.category`), always got 'unknown'
6. **Manifest accuracy fixes** - Removed false `state.update` provides from tvdb/tvmaze/omdb; fixed tasker requires (`plugin.renamer.data` -> `plugin.renamer.parsed`)
7. **New execution method** - `_execute_per_job_grouped()` uses pre-resolved dependency groups instead of ad-hoc parallel grouping
8. **11 new tests** - DependencyResolver integration (7) + ProvidesRegistry lifecycle (4)

### Test Results
- **420 unit tests passed** (+11 new), 4 failed (MongoDB), 17 skipped
- Ruff: 40 whitespace warnings on stage_executor (cosmetic, pre-existing)

## Active Decisions

| Decision | Status | Rationale |
|----------|--------|-----------|
| Plugin-agnostic core | ENFORCED | Guard test prevents regression |
| manifest.yml as single source | DONE | All plugins migrated |
| Stage executor decomposed | DONE | 5 SRP methods, each independently testable |
| PyMongo sync for CLI | ACTIVE | Motor deprecated |
| Beanie ODM dropped | ACTIVE | Raw pymongo instead |
| Session End Protocol | ENFORCED | CLAUDE.md mandates commit + report + HANDOFF + audit |

## Known Issues (Current)

### Blocking Nothing
- 4 tests fail without MongoDB running (expected)
- 40 ruff whitespace warnings on stage_executor (cosmetic)

### Needs Attention
- `tests/unit/core/test_plugin_services.py` - 0 bytes
- `tests/unit/core/validation/test_startup_validator.py` - 0 bytes
- `tests/unit/infrastructure/test_pymongo_persistence.py` - 0 bytes
- `tests/e2e/` and `tests/integration/` - empty directories
- FastAPI endpoints disconnected from orchestrator
- Plugin data stored in 5 places (consistency risk)
- Deprecated Motor code still exists (`mongodb.py`, 526 LOC)
- Config validation schema exists but not enforced
- 4 legacy plugin method variants via `hasattr()` (no Protocol/ABC)

## What To Do Next (Priority Order)

1. **Fix ruff whitespace warnings** - 40 cosmetic issues in stage_executor
2. **Define Plugin Protocol** - Replace 4 `hasattr()` checks with ABC/Protocol
3. **Consolidate plugin data** - Single authoritative store instead of 5 locations
4. **Move deprecated Motor code** - `mongodb.py` to `.deleted/`
5. **Fix FastAPI output path** - `process_executor.py` expects old report format
6. **MongoDB backend integration** - Connect pymongo_persistence.py to orchestrator
