# Active Context

**Last Updated:** Session 35 - April 17, 2026
**Version:** v2.4.0-dev
**Branch:** `dev/communication-refactoring`

## What Just Happened (Session 35)

### Event Bus Contract Closure (WP-9)
1. **services.events** — read-only EventService (`has_fired`, `history`, `snapshot`); no `emit`/`subscribe` for plugins (would re-create the parallel ordering system Session 34 closed)
2. **{{ events }} in templates** — `TemplateContextBuilder` accepts `events=` kwarg; tasker passes `services.events.snapshot()`
3. **requires events.*:fired** — `ValueMatcher` resolves event paths via `bus.has_fired`; only `:fired` allowed; missing bus = loud error (was silent pass before)
4. **Scaffolding cleanup** — `events/handlers.py` → `.deleted/` (zero subscribers); `VALIDATION_*` enums dropped; 11 documented enums kept (in `datasets/05-events.yml`)

### Audit Followups
- **A1** Interpolator alias→alias cycle now raises `InterpolationError` (was `RecursionError`)
- **B1-3** `services.run_safety` resolved once at run start; tasker drops local `dry_run`/`hardlink` reads; manifest drops `config_schema.dry_run`/`provides`
- **C1-2** `_save_exec_state` warn-once-per-run + counter; `_recover_crashed` mode-aware (`full`→CriticalError, `degraded`→warn)
- **D1** `state/manager` drops duplicate `EXECUTION_COMPLETED` emit; 6 LEGACY enums trimmed
- **D2** `dependency_validator._extract_plugin_from_requires` bug fix — modern `plugin.<name>.<path>:success` was extracting "plugin" as fake dep; new explicit prefix table covers `plugin.`/`plugins.`/`job.plugins.` and skips `events.`/`provides.`/`job.input.*`/`run.*`
- **F1** Slim recovery model documented in `datasets/11-recovery.yml` + HANDOFF.md
- **H1** `denormalize_config` audit: zero callers, zero existence (already removed Session 34)

### Tests
- Baseline: 593 passed → Final: **621 passed, 35 skipped, 0 failed**
- Net delta: +28 new tests across 4 new test files
- Plugin-agnostic guard re-verified clean

### Audit Result (PASS-WITH-NOTES)
- All 7 commits exist with expected hashes/messages
- One audit "1 failed test" claim was hallucinated (test name doesn't exist) — reproduced runs show 0 failures
- Plan deviations (in-place rewrite, EventServiceImpl naming) — both intentional, both functional

## What Happened in Session 33 (kept for context)

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
| services.events read-only | DONE (S35) | Plugins do not emit/subscribe — would re-create parallel ordering |
| {{ events }} template injection | DONE (S35) | Read surface only, via snapshot dict |
| requires: events.*:fired | DONE (S35) | Only :fired allowed; missing bus = loud error |
| Recovery model: slim | DOCUMENTED (S35 F1) | One orchestrator per Mongo deployment; lease/heartbeat deferred |
| persistence_mode default = degraded | DONE (S34) | No silent NullPersistence swap; full/off explicit |
| Single interpolation engine | DONE (S34) | One path-aware resolver; cycle detection (A1 fix S35) |
| Hard legacy plugin cut-off | DONE (S34) | All 9 on modern protocol, no bridge code |

## Known Issues (Current)

### Fixed in Session 35
- ~~Interpolator alias→alias cycle = RecursionError~~ FIXED (proper InterpolationError)
- ~~tasker reads run-scope safety from local config~~ FIXED (services.run_safety)
- ~~_save_exec_state silent debug~~ FIXED (warn-once + counter)
- ~~_recover_crashed silent fallback~~ FIXED (mode-aware: full=CriticalError, degraded=warn)
- ~~services.events documented but unwired~~ CLOSED (read-only EventServiceImpl)
- ~~{{ events }} promised in datasets but missing~~ CLOSED (snapshot kwarg)
- ~~requires events.* parsed but never matched~~ CLOSED (matcher events.* branch)
- ~~dependency_validator extracts "plugin" as fake dep~~ FIXED (explicit prefix table)
- ~~datasets/11-recovery.yml promised lease/heartbeat~~ DOCS UPDATED (slim contract)

### Remaining (Low Priority)
- Plugin data stored in 5+ places (consolidation deferred)
- FastAPI endpoints disconnected from orchestrator
- No CI/CD pipeline (next priority)
- Config normalization not mandatory at load time
- `.deleted/` dirs inside live source tree (intentional per no-delete policy)
- Pre-existing W293 whitespace warnings in untouched service files (separate ruff --fix pass)
- Recovery: lease/heartbeat/atomic-claim deferred to Session 36+ (slim contract documented)

## What To Do Next

1. **Ruff cleanup pass** — single `ruff check src/ --fix` for the pre-existing W293s
2. **Wire one kept-but-unemitted Events.\*** as a smoke test of the closed contract (e.g. `JOB_STARTED`)
3. **Plugin developer documentation** — was blocked by incomplete contract; now closed
4. **Real pipeline smoke test** — `python -m archiverr --config config.yml` using `{{ events }}` in tasker templates
5. **Set up CI/CD** — GitHub Actions for pytest + ruff on push
6. **Write a novel plugin** — nfo-writer or subtitle-finder
7. **StageExecutor decomposition** — 991 → ~500 LOC (optional, big refactor)
