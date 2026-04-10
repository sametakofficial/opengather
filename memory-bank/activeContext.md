# Active Context

**Last Updated:** Session 33 - April 10, 2026
**Version:** v2.4.0-dev
**Branch:** `dev/communication-refactoring`

## What Just Happened (Session 33)

### Deep Analysis (5 parallel agents)
1. **Architecture Reviewer** -- 15 findings (2 CRITICAL, 4 HIGH, 5 MEDIUM, 4 LOW)
2. **Plugin Inventory** -- Mapped all 9 plugins, found 3 legacy, 2 missing base class
3. **Test Suite Analysis** -- 558 tests, 24% module coverage, zero E2E tests
4. **Strategic Plan Review** -- 32-session history synthesis, actionable roadmap
5. **Core Code Deep Scan** -- StageExecutor god object (991 LOC), import graph, complexity

### Phase 0: Critical Fixes
1. **NullPersistence** -- MongoDB no longer mandatory, CLI works without DB
2. **ProvidesRegistry singleton removed** -- Per-run instance, no shared global state
3. **complete_job() idempotency** -- Checks state before completing, no double-counting
4. **_handle_plugin_error fixed** -- "warn" for PluginError, "error" for unexpected
5. **Renamer silent exceptions fixed** -- Now logs parse failures via self.warn()
6. **Dead code removed** -- _execute_per_job (40 LOC), _group_parallel_plugins (60 LOC)
7. **_build_global_state cached per-job** -- Invalidated after plugin completes

### Phase 1: Plugin Migration (ALL 9 now current protocol)
1. **tvdb** -- execute(job, services) -> PluginResult, base class logging
2. **omdb** -- execute(job, services) -> PluginResult, base class logging
3. **tvmaze** -- Added OutputPlugin base class, full migration
4. **tasker** -- Added OutputPlugin base class, removed duplicate PluginResult
5. **file-reader** -- Migrated to execute_run(services)
6. **tmdb** -- Fixed async/sync duplication, setup() now synchronous
7. **BasePlugin.setup()** -- Changed from async to sync (pipeline is sync)

### Phase 2: E2E Tests (14 new tests)
1. Scanner creates jobs from virtual paths
2. Renamer parses TV shows and movies (parametrized)
3. TMDb with mocked API responses
4. Full pipeline: scanner -> renamer (multi-job)
5. Orchestrator with NullPersistence
6. Protocol compliance: all plugins have correct signature
7. Base class inheritance: all plugins extend OutputPlugin/InputPlugin
8. NullPersistence interface compliance

### Phase 3: Code Quality
1. Fixed encapsulation violation (GlobalStateManager -> JobManager.configure())

## Active Decisions

| Decision | Status | Rationale |
|----------|--------|-----------|
| Plugin-agnostic core | ENFORCED | Guard test prevents regression |
| All plugins current protocol | DONE | 9/9 use execute(job, services) -> PluginResult |
| NullPersistence fallback | DONE | MongoDB optional, CLI works standalone |
| Per-run ProvidesRegistry | DONE | No shared mutable state between runs |
| Sync pipeline | CONFIRMED | async removed from BasePlugin.setup() |
| "Playground" vision | CONFIRMED | Focus on exercising plugin system |

## Known Issues (Current)

### Fixed This Session
- ~~ProvidesRegistry singleton shared state~~ FIXED (per-run instance)
- ~~MongoDB mandatory in build_orchestrator~~ FIXED (NullPersistence fallback)
- ~~3 legacy plugins (tvdb, omdb, tvmaze)~~ MIGRATED
- ~~2 plugins missing base class (tvmaze, tasker)~~ FIXED
- ~~_execute_per_job duplicate path~~ REMOVED
- ~~_group_parallel_plugins dead code~~ REMOVED
- ~~_build_global_state per-plugin waste~~ CACHED
- ~~Renamer silent exceptions~~ FIXED
- ~~Dead conditional in _handle_plugin_error~~ FIXED
- ~~async setup duplication in TMDb~~ FIXED

### Remaining (Low Priority)
- Plugin data stored in 5+ places (consolidation deferred)
- FastAPI endpoints disconnected from orchestrator
- No CI/CD pipeline (next priority)
- Config normalization not mandatory at load time
- .deleted/ dirs inside live source tree

## What To Do Next

1. **Set up CI/CD** -- GitHub Actions for pytest + ruff on push
2. **Write a novel plugin** -- nfo-writer or subtitle-finder
3. **StageExecutor decomposition** -- 991 -> ~500 LOC (optional, big refactor)
4. **Data consolidation** -- Single source of truth for plugin data
