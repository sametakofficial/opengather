# Active Context

**Last Updated:** Session 29 - April 8, 2026
**Version:** v2.3.1-dev
**Branch:** `dev/communication-refactoring`

## What Just Happened (Session 29)

### Completed
1. **Venv rebuilt** - Python 3.14.2, all deps installed (`pip install -e ".[all]"`)
2. **Hardcoded plugin names removed from core** - The #1 architecture violation is FIXED
   - Deleted `PLUGIN_STAGE_MAP` (11 plugin names) from `manifest_normalizer.py`
   - Deleted `plugin_provides` (11 plugin names) from `manifest_normalizer.py`
   - Replaced with generic stage-based inference only
   - Removed `PLUGIN_STAGE_MAP` import from `loader.py`
3. **All plugins now have manifest.yml** with explicit `stage` and `provides`
   - Created: file-reader, tvdb, omdb, tvmaze
   - Updated: scanner, renamer, tmdb, ffprobe, tasker (added `provides`)
4. **Legacy plugin.json files removed** - Moved 7 files to `.deleted/`
5. **PluginManifest Pydantic model tightened** - `category` deprecation warning, `run_mode` auto-inference
6. **Regression guard test added** - Static analysis scans core for hardcoded plugin name maps
7. **UUID[:8] fixed** - Full UUID4 in `state/manager.py` and `mongodb.py`
8. **PARTIAL state added** - `RunState.complete()` now uses PARTIAL when some jobs fail
9. **Backup files cleaned** - 3 `.bak` files moved to `.deleted/`
10. **pyproject.toml updated** - package-data now includes `manifest.yml`

### Test Results After Changes
- **340 passed** (+4 from baseline), 4 failed (MongoDB not running - expected), 17 skipped
- Ruff: Pre-existing 928 whitespace errors (unchanged)

## Active Decisions

| Decision | Status | Rationale |
|----------|--------|-----------|
| Plugin-agnostic core | ENFORCED | Guard test prevents regression |
| manifest.yml as single source | DONE | All plugins migrated, plugin.json deleted |
| UUID4 full length | DONE | Birthday paradox at 65K with truncated IDs |
| PARTIAL state for mixed results | DONE | 99/100 success shouldn't show as FAILED |
| PyMongo sync for CLI | ACTIVE | Motor deprecated, pymongo async for FastAPI |
| Beanie ODM dropped | ACTIVE | Using raw pymongo instead |

## Known Issues (Current)

### Blocking Nothing
- 4 API endpoint tests fail without MongoDB running (expected)
- 928 ruff whitespace warnings (pre-existing cosmetic debt)

### Needs Attention
- `tests/unit/core/test_orchestrator.py` - 0 bytes (orchestrator untested)
- `tests/unit/core/test_stage_executor.py` - 0 bytes
- `tests/unit/core/test_plugin_services.py` - 0 bytes
- `tests/e2e/` and `tests/integration/` - empty directories
- FastAPI endpoints disconnected from orchestrator (`process_executor.py` reads old path)
- Plugin data stored in 5 places (consistency risk)
- No async persistence interface for FastAPI
- Deprecated Motor code still exists (`infrastructure/database/mongodb.py`, 527 LOC)
- Config validation schema exists but not enforced

## What To Do Next (Priority Order)

1. **Write orchestrator tests** - `test_orchestrator.py` is 0 bytes, orchestrator is 903 LOC
2. **Write stage executor tests** - Critical execution path untested
3. **Fix FastAPI output path** - `process_executor.py` expects old report format
4. **Consolidate plugin data** - Single source of truth instead of 5 copies
5. **Remove deprecated Motor code** - Move `mongodb.py` to `.deleted/`
6. **Implement config validation** - Wire `config.schema.json` into startup
7. **MongoDB backend integration** - Models, repositories, connection wiring
