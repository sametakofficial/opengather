# Session 33: Deep Analysis & Action Plan

**Date:** 2026-04-10
**Methodology:** 5 parallel agents (architecture reviewer, plugin inventory, test suite analysis, strategic plan review, core code deep scan)
**Scope:** Full codebase audit -- architecture, plugins, tests, code quality, historical decisions

---

## 1. Executive Summary

| Metric | Score | Detail |
|--------|-------|--------|
| **Architecture** | 8/10 | Solid macro design, plugin-agnostic core enforced, clean delegation |
| **Code Quality** | 6.5/10 | StageExecutor god object (991 LOC), dead code, shared mutable state |
| **Plugin Health** | 5/9 working | 3 legacy protocol, 2 missing base class, 1 missing API key |
| **Test Coverage** | 24% modules | 558 tests but 52% of modules untested, zero E2E |
| **Technical Debt** | Medium-High | 15 architectural findings (2 CRITICAL, 4 HIGH, 5 MEDIUM, 4 LOW) |

**One-line verdict:** Architecture is excellent, execution layer needs cleanup, plugins need migration, real testing is missing.

---

## 2. Critical Findings (Fix Before Anything Else)

### CRITICAL-1: Module-Level Singletons Create Shared State

**Files:** `provides_registry.py:382-398`, `config_loader.py:277,366-378`, `connection.py:58-59`

`ProvidesRegistry` is a module-level singleton. Two concurrent API-triggered runs share it. `complete_all()` from run A corrupts run B's state. Same pattern in `config_loader._original_config` and `DatabaseConnection._instance`.

**Fix:** Pass `ProvidesRegistry` as constructor arg to `StageExecutor`. Create fresh instance per-run in `build_orchestrator()`. Remove module-level singleton. Same for `_original_config` -- return from function, don't store globally.

**Impact:** Blocks concurrent execution (API layer already exists)

### CRITICAL-2: MongoDB Is Mandatory Despite Being Optional

**File:** `orchestrator.py:481-484`

```python
if persistence is None:
    raise ImportError("MongoDB not available")
```

`pyproject.toml` declares MongoDB as optional (`[project.optional-dependencies]`), but the factory crashes without it. Wrong exception type too (`ImportError` vs `CriticalError`).

**Fix:** Create `NullPersistence` implementing `PersistenceInterface` (no-op writes). Use as default when MongoDB unavailable. CLI users should never need MongoDB.

**Impact:** Blocks CI/CD (tests can't run without MongoDB mock), blocks new developer onboarding

---

## 3. Plugin System Status

### Inventory

| # | Plugin | Stage | Protocol | Base Class | API Key | Status |
|---|--------|-------|----------|------------|---------|--------|
| 1 | **scanner** | input | `execute_run(services)` | InputPlugin | -- | WORKING |
| 2 | **file-reader** | input | `execute()` (legacy) | InputPlugin | -- | PARTIAL -- wrong protocol |
| 3 | **renamer** | parse | `execute(job, services)` | OutputPlugin | -- | WORKING |
| 4 | **ffprobe** | data | `execute(job, services)` | OutputPlugin | -- | WORKING (needs binary) |
| 5 | **tmdb** | data | `execute(job, services)` | OutputPlugin | `ac7d9e...` | WORKING |
| 6 | **tvdb** | data | `execute(match_data)` | OutputPlugin | `ac27b3...` | LEGACY -- 1-arg signature |
| 7 | **omdb** | data | `execute(match_data)` | OutputPlugin | `3aed01a3` | LEGACY -- 1-arg signature |
| 8 | **tvmaze** | data | `execute(match_data)` | **NONE** | EMPTY | BROKEN -- no base class, no API key |
| 9 | **tasker** | output | `execute(job, services)` | **NONE** | -- | WORKING but no base class |

### Migration Required

**3 Legacy Plugins (tvdb, omdb, tvmaze):**
- Change `execute(match_data: dict) -> dict` to `execute(job, services) -> PluginResult`
- Access data via `job.plugins.get(...)` instead of `match_data` dict
- Use `services` for logging, state updates
- Return `PluginResult` instead of raw dict

**2 Missing Base Class (tvmaze, tasker):**
- Inherit from `OutputPlugin`
- Delete local stub methods (`debug()`, `info()`, `warn()`, `error()`)
- Delete local `PluginResult` class (tasker has its own duplicate)

**1 Missing API Key:**
- TVMaze: `TVMAZE_API_KEY` is empty in `.env`. Note: TVMaze API is actually free and doesn't require a key for basic use -- verify and update plugin accordingly.

**1 Wrong Protocol (file-reader):**
- Uses `execute() -> list` instead of `execute_run(services) -> dict`
- Also has hyphenated module name (`file-reader` -- non-standard Python import)

### Plugin-Specific Bugs Found

| Plugin | Issue | Severity |
|--------|-------|----------|
| **renamer** | Silent `except Exception: return None` in `_parse_show`/`_parse_movie` (lines 105, 119) -- violates no-silent-failures rule | HIGH |
| **tmdb** | Accesses `job.plugins.get('renamer', {})` with hardcoded plugin name string | MEDIUM |
| **tmdb** | Dual init path: `async def setup()` never called, `_sync_setup()` duplicates it | MEDIUM |
| **tasker** | Reads `self.dry_run` from plugin config, not from `services.get_config()` | MEDIUM |
| **tasker** | 16KB file, does too much (template engine + condition evaluator + file writer) | LOW |

---

## 4. Architecture Findings (Full List)

### By Severity

| ID | Sev | Location | Issue |
|----|-----|----------|-------|
| C-1 | **CRITICAL** | `provides_registry.py`, `config_loader.py`, `connection.py` | Module-level singletons, shared mutable state across runs |
| C-2 | **CRITICAL** | `orchestrator.py:481` | MongoDB mandatory, wrong exception type |
| H-1 | **HIGH** | `stage_executor.py:285` | Dead `_execute_per_job` method shadows active path |
| H-2 | **HIGH** | `tasker/plugin.py:19` | No BasePlugin inheritance, duplicate PluginResult |
| H-3 | **HIGH** | `stage_executor.py:537` | Dead conditional in `_handle_plugin_error` |
| H-4 | **HIGH** | `tmdb/client.py:93` | Hardcoded plugin name for data access |
| M-1 | **MEDIUM** | `stage_executor.py:637` | Two independent grouping algorithms |
| M-2 | **MEDIUM** | `loader.py:191` | Four config format detection paths, no rejection |
| M-3 | **MEDIUM** | `sdk/base.py:141` | Async setup hooks never called |
| M-4 | **MEDIUM** | `state/manager.py:68` | Direct mutation of `JobManager._event_bus` |
| M-5 | **MEDIUM** | `orchestrator.py:337` | `complete_job()` may double-complete in `_finalize()` |
| L-1 | **LOW** | `connection.py:58` | Class-level DB singleton persists across tests |
| L-2 | **LOW** | `stage_executor.py:386` | `except (PluginError, Exception)` is redundant |
| L-3 | **LOW** | `src/.deleted/`, `tests/.deleted/` | Retired code lives inside live source tree |
| L-4 | **LOW** | `renamer/client.py:105,119` | Silent bare except violates project rules |

---

## 5. Code Quality Deep Scan

### Module Complexity

| File | Lines | Methods | Max Nesting | Verdict |
|------|-------|---------|-------------|---------|
| `stage_executor.py` | 991 | 34 | 7 | **GOD OBJECT** -- needs decomposition |
| `orchestrator.py` | 503 | 13 | 6 | Clean, well-delegated |
| `provides_registry.py` | 398 | 16 | 3 | Thread-safe, well-designed |
| `registry.py` | 396 | 15 | 4 | Clean facade |
| `manager.py` | 308 | 33 | 5 | Large facade (33 methods) |
| `plugin_services.py` | 300 | 10 | 4 | Good anti-corruption layer |
| `plugin_data_manager.py` | 264 | ? | ? | Adequate |
| `exceptions.py` | 225 | -- | -- | Well-tiered hierarchy |
| `models.py` | 199 | -- | 2 | Clean data structures |
| `resolver.py` | 153 | 5 | 3 | Correct algorithm |

### StageExecutor Decomposition Recommendation

Current 991 LOC with 34 methods should become:

```
StageExecutor (entry point, ~200 LOC)
├── PluginInvoker (single plugin execution, result extraction, ~250 LOC)
├── ParallelGroupExecutor (thread pool, group management, ~200 LOC)
├── RequiresChecker (trigger evaluation, requires validation, ~150 LOC)
└── LegacyFormatAdapter (1-arg plugins, old data format, ~100 LOC)
```

### Import Graph (No Circular Dependencies Detected)

```
Orchestrator
├── PluginRegistry → PluginDiscovery, PluginLoader
├── StageExecutor → DependencyResolver, TriggerRuleManager, ProvidesRegistry
├── GlobalStateManager → JobManager, PluginDataManager, PersistenceDelegate
├── EventBus → handlers
├── PerRunPluginExecutor
├── StateDumper
└── ResultBuilder
```

---

## 6. Test Suite Health

### Coverage Summary

| Area | Tests | Assertions | Module Coverage |
|------|-------|-----------|----------------|
| Core Logic | 331 | 642 | GOOD |
| State | 56 | 157 | PARTIAL |
| API | 48 | 137 | PARTIAL |
| Utils | 36 | 63 | ADEQUATE |
| Integration | 87 | 148 | WEAK |
| **Plugins** | **0** | **0** | **ZERO** |

### What Has Zero Test Coverage

**Critical gaps:**
- All 9 plugins -- no plugin-level tests exist
- `core/services/plugin_services.py` -- the plugin API facade
- `core/triggers/evaluator.py` -- trigger rule evaluation
- `core/locking/manager.py` -- filesystem lock detection
- `state/context.py`, `state/job_manager.py`, `state/persistence_delegate.py`
- `cli/main.py` -- CLI entry point
- All infrastructure/database modules (only integration tested)

### What's Missing

- **Zero E2E tests** -- no test runs the actual pipeline with real plugins
- **Zero plugin tests** -- no test validates individual plugin behavior
- **Zero parametrized tests** -- `@pytest.mark.parametrize` never used
- **Only 1 async test file** despite async infrastructure
- **5 skipped tests** (3 need pymongo, 1 legacy, 1 memory subsystem)

### Test Quality

- 70% mocked, 30% real behavior -- appropriate for unit tests
- Core pipeline tests are genuine (not just smoke tests)
- `conftest.py` has good plugin-agnostic fixtures
- Test organization is logical and well-structured

---

## 7. Historical Context (32 Sessions)

### Evolution Phases

| Phase | Sessions | Character | Key Outcome |
|-------|----------|-----------|-------------|
| Ambitious v1 | 1-10 | Build everything | Schema, memory, Celery, git branching |
| Simplification | 11-14 | Mature judgment | manifest.yml, Jinja2, plugin-agnostic core |
| Dormancy | 15-27 | 5 months idle | 3 init-only sessions, nothing built |
| Revival Sprint | 28-31 | 3-day sprint | Guard test, protocols, DependencyResolver |
| Strategic Reckoning | 32 | Self-assessment | ~909 LOC deleted, 2 bugs fixed, 6 diagrams |

### Killed Decisions (Don't Revive)

- Web UI -- no users, no demand
- Git-like media state versioning -- over-engineering
- Schema system (3,500 LOC) -- replaced by plugin validation
- Custom variable engine -- replaced by Jinja2
- Plugin hot-reloading -- YAGNI for CLI
- Plugin marketplace -- YAGNI for 1 developer

### Deferred Decisions (Revisit When Needed)

- MongoDB wiring -- only when API has users
- FastAPI connection -- contingent on MongoDB
- Plugin status timeout -- only when a plugin actually hangs
- Data contract provides -- only if plugin count > 15

### The Refactoring Treadmill Problem

31 sessions of framework work, zero external users, zero E2E tests. The architecture is excellent but untested against reality. **The system has never successfully processed a real media file end-to-end in a test.**

---

## 8. Prioritized Action Plan

### Phase 0: Critical Fixes (Before Everything Else)

| # | Task | Effort | Impact | Files |
|---|------|--------|--------|-------|
| 0.1 | Create `NullPersistence` -- make MongoDB optional | 30 min | CRITICAL | `infrastructure/database/`, `orchestrator.py` |
| 0.2 | Remove `ProvidesRegistry` singleton, pass as constructor arg | 45 min | CRITICAL | `provides_registry.py`, `stage_executor.py`, `orchestrator.py` |
| 0.3 | Fix `complete_job()` idempotency in `_finalize()` | 15 min | HIGH | `orchestrator.py:337`, `job_manager.py` |
| 0.4 | Fix dead conditional in `_handle_plugin_error` | 5 min | HIGH | `stage_executor.py:537` |
| 0.5 | Fix renamer silent exceptions | 10 min | HIGH | `renamer/client.py:105,119` |

### Phase 1: Plugin Migration (Get All 9 Working)

| # | Plugin | Work | Effort |
|---|--------|------|--------|
| 1.1 | **tasker** | Add `OutputPlugin` inheritance, delete local `PluginResult`, fix `dry_run` source | 1 hr |
| 1.2 | **tvdb** | Migrate to `execute(job, services) -> PluginResult` | 1.5 hr |
| 1.3 | **omdb** | Migrate to `execute(job, services) -> PluginResult` | 1.5 hr |
| 1.4 | **tvmaze** | Add `OutputPlugin` base, migrate protocol, verify API key situation | 2 hr |
| 1.5 | **file-reader** | Migrate to `execute_run(services) -> dict` | 1 hr |
| 1.6 | **tmdb** | Fix async setup duplication, consider hardcoded 'renamer' access | 30 min |

**Total plugin migration:** ~7.5 hours

### Phase 2: Real Testing

| # | Task | Effort |
|---|------|--------|
| 2.1 | Write E2E test: scanner -> renamer -> tmdb -> tasker (movie path) | 2 hr |
| 2.2 | Write E2E test: scanner -> renamer -> tmdb (TV show path) | 1 hr |
| 2.3 | Write plugin unit tests for each migrated plugin | 3 hr |
| 2.4 | Add `@pytest.mark.parametrize` for parse edge cases (renamer) | 1 hr |
| 2.5 | Test with real media file path (manual, document results) | 30 min |

### Phase 3: Code Quality

| # | Task | Effort |
|---|------|--------|
| 3.1 | Remove dead `_execute_per_job` and `_group_parallel_plugins` | 30 min |
| 3.2 | Fix `except (PluginError, Exception)` redundancy | 10 min |
| 3.3 | Make config normalization mandatory at load time | 30 min |
| 3.4 | Resolve async setup -- commit to sync (rename, remove `_sync_setup`) | 30 min |
| 3.5 | Fix `GlobalStateManager.configure()` encapsulation violation | 15 min |
| 3.6 | Move `.deleted/` dirs to top-level `_archive/` | 15 min |
| 3.7 | Cache `_build_global_state` per-job (5-line perf fix) | 10 min |

### Phase 4: CI/CD (After Tests Pass)

| # | Task | Effort |
|---|------|--------|
| 4.1 | GitHub Actions: `pytest tests/ -v` on push | 30 min |
| 4.2 | GitHub Actions: `ruff check src/` on push | 10 min |
| 4.3 | GitHub Actions: `mypy src/archiverr/` on push | 10 min |
| 4.4 | Add pre-commit hooks (ruff, pytest quick) | 20 min |

### Phase 5: StageExecutor Decomposition (Optional, Big Refactor)

Only if Phase 0-3 are complete and tests are green:

| # | Task | Effort |
|---|------|--------|
| 5.1 | Extract `PluginInvoker` from stage_executor | 2 hr |
| 5.2 | Extract `ParallelGroupExecutor` | 1.5 hr |
| 5.3 | Extract `RequiresChecker` | 1 hr |
| 5.4 | Extract `LegacyFormatAdapter` (can be removed after Phase 1) | 30 min |

---

## 9. What NOT To Do

1. **Don't add new plugins** until all 9 existing ones work
2. **Don't wire MongoDB** -- no users need it yet
3. **Don't touch FastAPI** -- contingent on MongoDB
4. **Don't replace DependencyResolver** with graphlib -- sideways move
5. **Don't add a DI framework** -- singleton works for CLI
6. **Don't build a Web UI** -- no users
7. **Don't refactor StageExecutor** until Phase 0-3 are done
8. **Don't add async** to the pipeline -- it's sync and that's fine

---

## 10. Success Criteria

**Session 33 is successful if:**

- [ ] All 9 plugins use current protocol (`execute(job, services) -> PluginResult`)
- [ ] All 9 plugins have base class inheritance
- [ ] At least 1 E2E test passes with real plugin execution (scanner -> renamer -> tmdb -> tasker)
- [ ] Critical findings C-1 and C-2 are fixed
- [ ] All HIGH findings are addressed
- [ ] `pytest tests/ -v` runs green (or known skips only)

**Stretch goals:**
- [ ] CI/CD configured
- [ ] Plugin-level unit tests for each migrated plugin
- [ ] StageExecutor < 500 LOC

---

## Appendix A: File Sizes (Core)

```
src/archiverr/core/plugins/stage_executor.py    991 LOC  ← GOD OBJECT
src/archiverr/core/orchestrator.py              503 LOC
src/archiverr/core/provides_registry.py         398 LOC
src/archiverr/core/plugins/registry.py          396 LOC
src/archiverr/state/manager.py                  308 LOC
src/archiverr/core/services/plugin_services.py  300 LOC
src/archiverr/state/plugin_data_manager.py      264 LOC
src/archiverr/core/exceptions.py                225 LOC
src/archiverr/state/models.py                   199 LOC
src/archiverr/state/job_manager.py              190 LOC
src/archiverr/state/persistence_delegate.py     182 LOC
src/archiverr/core/plugins/resolver.py          153 LOC
src/archiverr/state/context.py                   92 LOC
```

## Appendix B: Plugin File Sizes

```
src/archiverr/plugins/tasker/plugin.py          16178 bytes  ← LARGEST PLUGIN
src/archiverr/plugins/tmdb/client.py            10527 bytes
src/archiverr/plugins/tvdb/client.py             9169 bytes
src/archiverr/plugins/tvmaze/client.py           8450 bytes
src/archiverr/plugins/omdb/client.py             7534 bytes
src/archiverr/plugins/ffprobe/client.py          6111 bytes
src/archiverr/plugins/renamer/client.py          4264 bytes
src/archiverr/plugins/scanner/client.py          4048 bytes
src/archiverr/plugins/file-reader/client.py      3516 bytes
```

## Appendix C: API Key Status

```
TMDB_API_KEY=ac7d9e25e603a7167f183ed446b58e8f     ✓ Configured
TVDB_API_KEY=ac27b346-7bec-4667-a4c9-51c82525c461  ✓ Configured
OMDB_API_KEY=3aed01a3                               ✓ Configured
TVMAZE_API_KEY=                                      ✗ EMPTY (TVMaze API may not need key)
```
