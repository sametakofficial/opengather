# Active Context

**Last Updated:** Session 31 Phase 2 - April 10, 2026
**Version:** v2.3.2-dev
**Branch:** `dev/communication-refactoring`

## What Just Happened (Session 31 Phase 2)

### Completed (Phase 2 -- Protocol + Cleanup)
1. **PerRunPlugin/PerJobPlugin protocols defined** - `@runtime_checkable` Protocol classes in `sdk/types.py` for type-safe plugin dispatch
2. **hasattr reduced 23 to 8** in stage_executor.py:
   - Plugin dispatch: `PerRunPlugin isinstance` for execute_run, `inspect.signature` for execute param count
   - Result extraction: `PluginResult isinstance`, `dict isinstance`, then fallback
   - JobState guards removed (typed class, attributes always exist)
   - Extracted `_ensure_status_plugins` helper
   - Removed dead `process` method fallback
3. **Orphaned executor.py moved to .deleted/** - Unused async PluginExecutor
4. **Dead PluginServices dataclass + factory functions removed** from `services/__init__.py`

### Completed (Phase 1 -- Infrastructure Wiring)
1. **DependencyResolver wired into StageExecutor** - Proper topo sort replacing pseudo-sort
2. **ProvidesRegistry wired into execution lifecycle** - Register/complete/fail from manifests
3. **StartupValidator wired into Orchestrator._initialize()** - Replaces legacy `validate_dependencies()`
4. **DependencyResolver fixed** - Handles `plugin.*.field:success` requires format
5. **OMDb category bug fixed** - Was reading from wrong path
6. **Manifest accuracy fixes** - Removed false provides, fixed tasker requires
7. **`_execute_per_job_grouped()`** - Pre-resolved dependency groups
8. **11 new tests** - DependencyResolver integration (7) + ProvidesRegistry lifecycle (4)

### Test Results
- **419 unit tests passed**, 4 failed (MongoDB), 17 skipped
- Ruff: 40 whitespace warnings on stage_executor (cosmetic, pre-existing)

## Active Decisions

| Decision | Status | Rationale |
|----------|--------|-----------|
| Plugin-agnostic core | ENFORCED | Guard test prevents regression |
| manifest.yml as single source | DONE | All plugins migrated |
| Stage executor decomposed | DONE | 5 SRP methods, each independently testable |
| PerRunPlugin/PerJobPlugin protocols | DONE | @runtime_checkable, hasattr 23->8 |
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
- 8 remaining `hasattr()` calls in stage_executor (down from 23; PerRunPlugin/PerJobPlugin protocols now handle dispatch)

## What To Do Next (Priority Order)

1. **Fix ruff whitespace warnings** - 40 cosmetic issues in stage_executor
2. **Reduce remaining 8 hasattr calls** - Further Protocol adoption for result extraction and state guards
3. **Consolidate plugin data** - Single authoritative store instead of 5 locations
4. **Move deprecated Motor code** - `mongodb.py` to `.deleted/`
5. **Fix FastAPI output path** - `process_executor.py` expects old report format
6. **MongoDB backend integration** - Connect pymongo_persistence.py to orchestrator
