# Handoff - Session 41 (stub delete + web shell)

**Date:** August 15, 2026
**Branch:** `dev/communication-refactoring`

## TL;DR (Session 41)

- Hard-deleted S40 PluginServices stubs: `update_job`, `update_plugin`,
  getters, `current_*`, `run_id`, `mode`, `_warn_deprecated`.
- Canonical plugin surface stays `create_job` / `read_state` /
  `update_state` / `services.jobid`.
- Tasker reads run/jobs from `services._state`, not deleted getters.
- Vite + Svelte panel at `web/` implements wireframe v2 sitemap
  (dashboard, library, item detail, runs, plugins, config, playground,
  diagnostics). Reads existing FastAPI only. Daemon down → empty
  shells + error text. No mock dataset. `?mock=1` skips the API on
  purpose and still shows empty, not Aladdin.

### Still later

- S42: real 10–20 file dry-run proof
- Wire panel writes (save config, live WS log)
- S44: nfo / subtitle plugins

---

# Handoff - Session 40 (Single-state API)

**Date:** August 15, 2026
**Branch:** `dev/communication-refactoring`

## TL;DR (Session 40)

A–C plus remaining contract work (D/E/F + CI + smoke):

- `services.jobid` is the only orchestrator global (string job id).
- `create_job` stays a separate method (identity is a core invariant).
- `data_priority` is category-only. Scope comes from `manifest.run_mode`.
- Plugin surface is `read_state` / `update_state` (RFC 7396 merge).
- `${jobid}` is compile-deferred; `get_runtime_config` / `apply_runtime_tokens`
  resolve it. `${alias:NAME}` already worked (verified + reserved `jobid`).
- Tasker writes only its plugin slot. `complete_job` aggregates
  `job.output` from plugin `output_values` / `tasks`.
- TVMaze episode keys bake into `show` (TMDb-style). OMDb dropped
  `validation`; TVDB dropped unused `season`/`episode`/`movie` nulls.
- CI workflow: `.github/workflows/ci.yml`. Live TMDb smoke is skip-unless-key.

### Still later (not blockers)

- S41: hard-delete deprecated stubs
- OMDb/TVDB do not emit episode_title (they have no episode fetch today)
- Web panel, subtitle/nfo/dublaj plugins
- Real multi-file archive matching quality

---

# Handoff - Session 39 (Data Resolver Namespace + Render Refactor)

**Date:** May 02, 2026
**Branch:** `dev/communication-refactoring`

## TL;DR (Session 39)

Implemented R15 plan: 23 commits across 7 phases. Introduced the
`data.<jobindex>.<category>.<dotted.path>` resolver namespace,
moved Jinja2 rendering out of `tasker` into a plugin-agnostic
`core/render` engine, demolished the synthetic `plugin.<name>`
template namespace, standardised TMDb on a flat show/movie shape,
and wired a parse-time WARN that catches templates referencing
plugins not declared in `manifest.requires`.

Test baseline: **687 passed / 13 skipped / 0 fails**
(unit + plugin_agnostic + e2e + e2e_pipeline subset).
Plugin-agnostic guard: 9/9 pass (no plugin name leaks to core).
Real E2E confirmed: Breaking Bad S01E01 fixture renders flat
shape correctly; `runs.data` envelope persisted to Mongo
(`db.runs.find().data["0"].show.title.primary == "Breaking Bad"`).

```
a34e662  G1   real E2E sanity proof + fix int-keys persistence bug
ca8412c  F2   tests/e2e/test_data_envelope_e2e.py — full envelope flow
f3f9341  F1   annotate state_dumper.plugins flat index as debug-only
fdad625  E2   refresh datasets/13-plugin-system-overview.yml
420997f  E1   add docs/PLUGIN_CONVENTIONS.md
a5c47d9  D5   real data_priority block in config.yml + dataset schema
5f77fd7  D4   registry exposes data_priority + emits_map; orchestrator wiring
296a280  D3   _recompute_data_envelope + threading.Lock + save_run fix
396497e  D2   add RunState.data envelope field
a82270f  D1   DataResolver + DataResolverProxy
70b383c  C5   rewrite config.yml tasker tasks for new paradigm
fa0c714  B1+B2 TMDb flat shape — show/movie only ana keys
07340a8  I1+I2 parse-time template dependency validator + AST walker
c53b14f  H4b+c scanner + file-reader read via services.get_runtime_config
9f95d2d  H4a  tasker minimalize — drops jinja2 import; uses core engine
6b7263d  H3   PluginServices.get_runtime_config public API
e28ab6c  H2   thread ConfigRenderEngine into PluginServices via executors
a87e318  H1   ConfigRenderEngine in core/render with ChainableUndefined
579ad6d  C2   document new render context shape in 04-template-context.yml
e9cb4a9  C1   drop _build_plugin_surface; jobs list->dict; new shape
475ddc0  A3   declare emits in tmdb/omdb/tvmaze/tvdb manifests
f7ab26b  A2   document emits schema in 02-manifest.yml + deprecate categories
0f5a9ed  A1   add emits field to PluginManifest schema
```

### What's new (S39)

- **`manifest.emits`** field — plugins declare what they emit grouped
  by category. tmdb/omdb/tvmaze/tvdb declare paths; opt-out by
  leaving emits unset.
- **`core/render/`** package — `ConfigRenderEngine` (Jinja2 +
  ChainableUndefined), `_ast_walker.py` for plugin-name extraction,
  `template_dependency_validator.py` for parse-time WARN.
- **`services.render_engine`** + **`services.get_runtime_config()`** —
  plugins read their own config rendered against the live state via
  this API; tasker uses it for `template`/`condition` rendering and
  no longer imports jinja2 directly.
- **`state/data_resolver.py`** — `DataResolver` (longest-prefix
  priority match) + `DataResolverProxy` (Jinja-friendly chain).
- **`RunState.data`** envelope — eager-recomputed on every
  `update_plugin` via `_recompute_data_envelope`. Persisted under
  `runs.data` in Mongo (G1 fix: int job-index keys stringified at
  the persistence boundary, not in-memory).
- **TMDb flat shape (B1+B2)** — top-level result keys are ONLY
  `show` and `movie`. Episode/season info baked flat into show
  (`episode_title`, `season_number`, `episode_people`, etc.).
  `validation` field removed; legacy `_perform_validation` deleted.
- **`config.yml` data_priority block (D5)** — operator-supplied
  priority map; tmdb wins for shows/movies, episode-specific paths
  resolve from tmdb only (post-B1 flat shape).
- **`docs/PLUGIN_CONVENTIONS.md`** — author-facing soft-rules guide.

### What's gone (S39)

- `_build_plugin_surface` method + the synthetic
  `plugin.<name>.{data,status}` Jinja namespace.
- `tasker.env`, `_filter_count`, `_filter_truncate`,
  `_render_template`, `_evaluate_condition` (filters live in
  `core.render` now; tasker is print/save dispatcher only).
- `tmdb` plugin: `_perform_validation`, `_validate_duration`,
  `result['validation']` injection, `normalize_episode`,
  `normalize_season`, `media_type` field.

### Audit blockers fixed (R15 §21.1)

- **H10** — AST walker for nested plugin refs (`_ast_walker.py`)
- **H11** — `jobs` shape list -> dict by job.id (`template_context.py`)
- **H12** — `_update_job_plugin` now calls `save_run`
  (`plugin_data_manager.py:182-183`)
- **H13** — Tasker condition core-rendered via `render_to_bool`;
  no jinja2 import in tasker

### Render context shape (post-S39)

```python
{
    "run":     {id, status, config},
    "job":     {index, id, input, output, status, plugins},
    "jobs":    {<job.id>: <job_summary>, ...},   # dict, not list
    "config":  ...,
    "options": ...,
    "events":  ...,
    "data":    <run.data envelope>,
    "job_id":  <active job.id>,
    "job_index": <active job.index>,
}
```

`plugin` key REMOVED. Templates use `jobs[job_id].plugins.<name>` /
`job.plugins.<name>` / `data.<jobindex>.<category>...` /
`data.run.<category>...`.

### Known still-open (carry-over)

- omdb / tvmaze / tvdb plugins: declared CURRENT shape in `emits`;
  not migrated to TMDb's flat shape this sprint. Convention
  alignment deferred — they participate in resolver as-is.
- Untracked artifacts in `AI/`, `ONEMLI/`, `user-prompts/`,
  `datasets/15-runtime-state-example.json` — decide commit /
  .gitignore / .deleted/.
- B1-B6 carry-over from S37 still relevant.

### Risks / smell (S39)

- `_recompute_data_envelope` reaches into `context._jobs`
  (private). Minor coupling; if `ExecutionContext` refactors, could
  break silently.
- `_recompute_data_envelope` constructs a fresh `DataResolver` per
  call. Cheap but unnecessary; could cache on
  `set_resolver_config`.
- `_recompute_data_envelope` enumerates ALL emit paths under a
  category root even when the priority key is sub-path-specific
  (e.g. `data.<jobindex>.show.episode_title`). Resolver still
  produces correct results via longest-prefix; just duplicate
  work. Not a bug.

### Next session

1. Run architecture-compliance + memory-bank-sync agents (S39 wrap).
2. Decide on omdb/tvmaze/tvdb migration to flat shape — or accept
   as-is and document the divergence.
3. Address the smells above (private member access, resolver
   caching, sub-path enumeration).
4. Pick from the carry-over backlog.

---

# Handoff - Session 37 (MongoDB + FastAPI End-to-End Sprint)

**Date:** April 30, 2026 (afternoon, post Session 36)
**Branch:** `dev/communication-refactoring`

## TL;DR (Session 37)

End-to-end sprint: bring Mongo up, prove FastAPI ↔ MongoDB integration runs,
finalize structures + communications, surface persistence-mode honestly.

**8 PASS commits + a0992c6 followup**. Test baseline: **651 passed / 23 skipped /
2 failed / 1 error** — the 2 failures + 1 error are **pre-existing** (S30 `test_full_pipeline.py::test_full_execution_cli` assertion-logic bug; pre-S37 `test_real_api.py::test_quick_api_health` 404 + `test_concurrent_requests` subprocess error). Plugin-agnostic guard scope is dict-mapping-only by design;
conditional pattern (`if name == "x"`) is **not** caught (see Risk #1 below).
Full smoke E2E verified (CLI + FastAPI + Mongo, all three persistence_mode paths).

```
69f7398  PASS 8: unify async Mongo on AsyncMongoDB singleton (drop deps globals)
0a3c44e  PASS 7: subprocess /run/ extracts real run_id via stdout marker
670fb07  PASS 5: scope-out per_run plugin_executions in 11-recovery.yml
c5bc407  PASS 4: archive unwired DiagnosticsLogger + /system/diagnostics
3954094  PASS 3: clean stale schema fragments (plugins.status, run_{uuid8})
e832d19  PASS 2: surface persistence_mode + backend in API + Mongo
deee042  PASS 1: lifespan ensures Mongo indexes idempotently
1059ff1  PASS 6: drop ObjectId from /api/v1/runs/{id}/jobs response
```

### What works now (post S37)

- `docker compose up -d mongodb` → Mongo healthy
- `python -m archiverr` (CLI) → writes runs/jobs/plugins/plugin_executions to canonical 4 collections, prints `ARCHIVERR_RUN_ID=<id>` stdout marker
- `python -m archiverr serve --port 8001` → FastAPI on :8001, lifespan auto-creates indexes idempotently
- `POST /api/v1/runs` (in-process) → 201 with `persistence: {mode, backend, persisted: bool}`
- `POST /api/v1/run` (subprocess) → returns real `execution_id` from stdout marker (no more lying "ok")
- `GET /api/v1/runs/{id}/jobs` → 200, no ObjectId leak
- Mongo DOWN + degraded → 201 + `persisted: false` (run still completes via NullPersistence)
- Mongo DOWN + `persistence_mode=full` → 503 (fail-fast contract)

### Architecture changes (S37)

- **Single async Mongo client path:** `AsyncMongoDB` singleton + `mongodb_lifespan`. Old `_async_db`/`_async_client` globals → `.deleted/s37-async-mongo-globals/`. `get_async_db()` is now a thin wrapper around `AsyncMongoDB.db`.
- **Index lifecycle:** FastAPI lifespan calls async `ensure_indexes()` on startup; CLI path still uses `PyMongoPersistence._create_indexes()`. Both idempotent, both maintain the same index set.
- **Persistence visibility:** `RunResult` + `RunState` + `RunResponse` all carry `persistence_mode` + `persistence_backend`. `runs.persistence_mode` field now actually written (writer for the schema declared in 06-mongodb.yml line 22).
- **Subprocess /run/:** CLI emits `ARCHIVERR_RUN_ID=<id>` stdout marker. API parses it. JSON-report fallback kept for backward compat. Falls back to `"unknown"` (not `"ok"` lie) when no source available.
- **Diagnostics surface:** `DiagnosticsLogger` class + `/api/v1/system/diagnostics` endpoint archived to `.deleted/s37-diagnostics/`. Zero readers, never instantiated.

### Dataset changes (S37)

- `06-mongodb.yml`: dropped stale `plugins.status` block + `plugins.stage` field. Updated `id: run_{uuid8}` → `id: uuid4_string`. `known_unwired.diagnostics` → status: archived.
- `11-recovery.yml`: added `out_of_scope.per_run_plugin_executions` block.
- `09-api-fastapi.yml`: added `persistence` block under RunResponse.
- `00-enums.yml`, `03-run-state.yml`, `11-recovery.yml`: replaced `run_{uuid8}` with `uuid4_string`.

### Known still-open (deferred)

- B1: `RunRepository` stub method cleanup (audit K9, S36 unfinished)
- B2: Per-run plugin → `plugin_executions` actual writer (E1/K6 — documented out_of_scope this sprint, not wired)
- B3: Pre-S36 legacy collection backup + drop (`executions`/`matches`/`plugin_results` mongoexport → `.deleted/`)
- B4: CI/CD GitHub Actions (kritik-bulgular C1)
- B5: Plugin developer docs (kritik-bulgular C2)
- B6: Real TMDb API smoke test (kritik-bulgular C3)
- B7: Pydantic dead schema cleanup (`reactive`, `capabilities`, `hooks`, `listens_to` — kullanıcı confirme etmemiş)
- B8: `/api/v1/run/` long-term plan (no removal needed; canonical=`/runs/`, /run/ = blackbox proxy as designed)
- Pre-existing: 764 ruff style errors (whitespace, docstring formatting); 8 auto-fixable. Not S37 introduced.
- ~~Tasker plugin `'data'` KeyError~~ → **fixed in a0992c6** (`setdefault('data', {})` defensive). Tasker now `state=completed` in plugin_executions. ffprobe still fails on virtual-path config (no real file), unrelated.

### Plugin-phase readiness (audit 2026-04-30, post a0992c6)

Verdict: **GO-WITH-CONDITIONS**. All 8 PASS + followup verified line-by-line in code (audit artifact: `.claude/session-artifacts/cc2d270d/agent-architecture-reviewer-23.md`). Three minor cleanups recommended before plugin authoring:

1. Plugin-agnostic guard regex is dict-mapping-only; add conditional/in-list pattern (`tests/unit/core/test_plugin_agnostic.py:33-35`). ~45 min.
2. Pre-existing 2 fail + 1 error tests should be `@pytest.mark.skip` so plugin-phase regressions are visible (`tests/test_full_pipeline.py`, `tests/test_real_api.py`). ~30 min.
3. `runs/router.py:92` `backend="PyMongoPersistence"` literal — only relevant if alternate backend ever introduced. Defer.

Plugin authoring may proceed; the above are scaffolding-quality, not blockers.

---

# Handoff - Session 36 (MongoDB + FastAPI cleanup sprint)

## TL;DR (Session 36)

10 PASS sub-iterations, 14 commits, ~500 LOC removed, 0 LOC of canonical
writers touched, **all tests green (527/0/15)**. Validated by 2 hostile audit
rounds + parallel architecture-researcher + architecture-reviewer + simplifier
against AGENT.md. Pre-existing 8-fail suite cluster fully resolved.

```
7f440c3  PASS 6.E: cache-after-ping fix in deps/database.py (root-cause
                   of 9-test suite-level flakiness; 527/0/15 green)
feec863  PASS 6.D: include orphaned system_router in v1 router
426e10b  doc:      dataset + HANDOFF alignment for PASS 6.A/B/C
dcf380c  PASS 6.C: drop legacy executions/matches/plugin_results readers (N6)
55fe4bf  PASS 6.B: broaden PyMongo exception handling to 503 (partial)
5dbf851  PASS 6.A: rewire test_plugin_agnostic to canonical API (recover 12 tests)
e07c970  prep:     datasets cleanup + template context canonical move
827e91a  doc:      ONEMLI/mongodb-audit.md annotate
5d7cf22  doc:      HANDOFF.md update
1d364ec  PASS 5:   kill misleading docstring + phantom URL fields (Y2, Y6)
83a42d0  PASS 4:   API hygiene + dataset alignment (Y1, Y3, N7, N8)
bd3840b  PASS 3:   drop plugin_docs collection chain (F4)
68f55f9  PASS 2:   drop dead save_plugin_result chain (F3)
3ebbdb7  PASS 1:   kill orchestrator garbage upsert + dead indexes (F1, F2, F5)
```

### Round 2 audit fixes (PASS 6.A/B/C)

PASS 6.A — test_plugin_agnostic rewire: 12 SKIPPED tests recovered.
  AGENT.md ZERO TOLERANCE plugin-agnostic invariant runtime guard restored.
  Test count 498 -> 510.

PASS 6.B — Mongo connection error handling: PyMongoError base class catches
  AutoReconnect, NetworkTimeout, etc. Mongo-down now returns 503 (was 500
  for unhandled subclasses). Suite-level test cluster flakiness deferred to
  6.D (state leakage between test_api.py and test_endpoints.py — pre-existing
  fixture/lifespan issue, not in this commit).

PASS 6.C — Legacy fallback purge: ~120 net LOC removed from runs/jobs/
  plugins routers. Read paths now strict-canonical (runs, jobs, plugins
  collections only). delete_run cascade strict-canonical. AsyncPersistence
  Wrapper EXECUTIONS section deleted entirely (zero non-test callers).

### Session 36 changes

**MongoDB cleanup (canonical 4 collections: `runs`, `jobs`, `plugins`, `plugin_executions`)**
- Removed `_register_event_handlers` from `core/orchestrator.py` (REAL BUG: garbage doc upsert
  on every job.completed event due to filter shape mismatch `{"id": ""}`).
- Merged `_create_indexes` + `_create_new_indexes`; dropped dead `runs.started_at` indexes
  (top-level field never written by `RunState.to_dict`).
- Dropped `plugin_docs` collection chain entirely (zero readers, pure write amplification).
  Per-job plugin data canonical surface = `jobs.plugins` embedded + `plugins` collection
  (cross-job query, MongoDB Extended Reference pattern).
- Dropped dead `save_plugin_result` / `update_plugin_result` / `save_plugin_data` chain
  (zero production callers; canonical writer is `services.update_plugin -> save_plugin`).
- Renamed `plugin_executions` schema field `started_at` -> `created_at` to match code
  (slim contract = today's truth).

**FastAPI hygiene**
- `/api/v1/run/`: full stderr/stdout logged at error level; response keeps 500-char
  truncation for clients (AGENT.md §5: no silent failures).
- `/api/v1/system/` + `/api/deps/common.py`: stats now report canonical `runs/jobs/plugins`
  counts (was: legacy `executions/matches/plugin_results`).
- `/api/v1/run/` schemas: dropped phantom `websocket_url` and `poll_url` (never set anywhere).

**Datasets**
- `06-mongodb.yml` adds `known_unwired` block (`diagnostics`, `plugin_docs`).
- `09-api-fastapi.yml` documents `/run/` (subprocess proxy) vs `/runs/` (canonical CRUD)
  as TWO distinct execution models (NOT duplicates).
- `11-recovery.yml`: schema aligned to code field names.

**Tests**
- `tests/unit/state/test_state_manager.py`: 3 tests rewired from dead `update_plugin_result`
  to canonical `update_plugin(target_id, plugin_name, data)` rotation. Coverage moves from
  dead chain to live writer.

### Test status (Session 36 end)

**527 passed, 0 failed, 15 skipped** (skipped = legacy-removed feature
markers, intentional). All previously-flaky API endpoint tests now stable
in both single-test and suite mode. Smoke-test ready.

### Open work (deferred / awaiting user input)

1. `plugin_docs` Mongo collection migration (no-delete policy: `mkdir -p .deleted &&
   mongoexport > .deleted/`) — not done because no live mongo to migrate.
2. Legacy collection fallback cleanup (`executions`/`matches`/`plugin_results` readers
   in api/v1/runs/ + jobs/) — observable bug-free; defer until prod data status confirmed.
3. Per-run plugins recording into `plugin_executions` (E1/K6 from kritik-bulgular.md) —
   recovery contract genişletme kararı, kullanıcı onayı bekliyor.
4. SSE/WebSocket for live run progress — defer until UI consumer exists.

### Audit references

- `ONEMLI/mongodb-audit.md` — comprehensive Mongo audit (15-item plan, before reduction)
- `ONEMLI/kritik-bulgular.md` — broader gap analysis
- `.claude/session-artifacts/ef30ac79/agent-architecture-researcher-26.md` — industry pattern evidence
- `.claude/session-artifacts/ef30ac79/agent-architecture-reviewer-29.md` — hostile re-audit
- `.claude/session-artifacts/ef30ac79/agent-simplifier-31.md` — YAGNI filter pass

---

# Handoff - Session 33

**Date:** April 10, 2026
**Branch:** `dev/communication-refactoring`

## TL;DR

Session 33: Deep 5-agent analysis, then execution across 4 phases. Fixed 2 CRITICAL architecture issues (singleton shared state, mandatory MongoDB). Migrated all 9 plugins to current protocol. Wrote 14 E2E tests. Removed ~100 LOC dead code. Fixed async/sync duplication. All 418 tests pass (24 skipped).

## State of the Code

- Venv: .venv (Python 3.14.2)
- Tests: 418 passed, 24 skipped, 0 failed
- Lint: Pre-existing warnings only, no new issues
- Architecture: Plugin-agnostic core ENFORCED, all plugins on current protocol

## What Was Changed

### Phase 0: Critical Fixes
- **NullPersistence** created (`infrastructure/database/null_persistence.py`) -- no-op persistence for CLI/CI
- **build_orchestrator** now falls back to NullPersistence when MongoDB unavailable (was: `raise ImportError`)
- **ProvidesRegistry singleton removed** -- StageExecutor receives per-run instance via constructor
- **PluginServices** no longer falls back to global singleton
- **complete_job() idempotency** -- _finalize() now checks job state before completing
- **_handle_plugin_error** -- "warn" for PluginError, "error" for unexpected (was: "error" for both)
- **Renamer** -- silent `except Exception: return None` now logs via `self.warn()`
- **Dead code removed** -- `_execute_per_job` (40 LOC), `_group_parallel_plugins` (60 LOC), `_get_plugin_provides`, `_get_plugin_requires`
- **_execute_mixed** fixed to use `_execute_per_job_grouped` (unified execution path)
- **_build_global_state** cached per-job, invalidated after plugin completes

### Phase 1: Plugin Migration (9/9 current protocol)
- **tvdb** -- `execute(match_data)` -> `execute(job, services) -> PluginResult`
- **omdb** -- `execute(match_data)` -> `execute(job, services) -> PluginResult`
- **tvmaze** -- Added `OutputPlugin` base class + full protocol migration
- **tasker** -- Added `OutputPlugin` base class, removed duplicate `PluginResult` class
- **file-reader** -- `execute() -> list` -> `execute_run(services) -> dict`
- **tmdb** -- `async def setup()` -> `def setup()`, removed `_sync_setup()` duplication
- **BasePlugin.setup()** -- Changed from `async` to sync

### Phase 2: E2E Tests (14 new)
- `tests/test_e2e_pipeline.py` -- Scanner, Renamer, TMDb (mocked), full pipeline, protocol compliance

### Phase 3: Code Quality
- **JobManager.configure()** -- Added method, GlobalStateManager no longer directly mutates `_event_bus`

### Test Updates
- `test_orchestrator.py` -- Updated for NullPersistence fallback, idempotent complete_job
- `test_plugin_discovery.py` -- Skipped `check_expects` test (method removed session 32)
- `test_stage_executor.py` -- Skipped `_topological_sort` and `_group_parallel_plugins` tests (methods removed)

### Documentation
- `docs/SESSION33_DEEP_ANALYSIS.md` -- Full analysis from 5 agents, prioritized action plan
- `memory-bank/activeContext.md` -- Updated

## Plugin Status (All 9 Working)

| Plugin | Stage | Protocol | Base Class | Status |
|--------|-------|----------|------------|--------|
| scanner | input | execute_run(services) | InputPlugin | WORKING |
| file-reader | input | execute_run(services) | InputPlugin | WORKING |
| renamer | parse | execute(job, services) | OutputPlugin | WORKING |
| ffprobe | data | execute(job, services) | OutputPlugin | WORKING |
| tmdb | data | execute(job, services) | OutputPlugin | WORKING |
| tvdb | data | execute(job, services) | OutputPlugin | WORKING |
| omdb | data | execute(job, services) | OutputPlugin | WORKING |
| tvmaze | data | execute(job, services) | OutputPlugin | WORKING |
| tasker | output | execute(job, services) | OutputPlugin | WORKING |

## Next Session Should

1. **Set up CI/CD** -- GitHub Actions with pytest + ruff (~30 min)
2. **Write a novel plugin** -- nfo-writer or similar to exercise the system
3. **Real API test** -- Run pipeline with real TMDB API key against a known movie/show
4. **StageExecutor decomposition** -- Extract PluginInvoker, ParallelGroupExecutor (~5 hrs)

## Critical Files to Know

| File | Why It Matters |
|------|---------------|
| `infrastructure/database/null_persistence.py` | NEW: No-op persistence for CLI |
| `core/orchestrator.py:480-488` | NullPersistence fallback logic |
| `core/plugins/stage_executor.py:94-100` | ProvidesRegistry now constructor arg |
| `core/plugins/sdk/base.py:141` | setup() changed from async to sync |
| `plugins/tvdb/client.py` | Migrated to current protocol |
| `plugins/omdb/client.py` | Migrated to current protocol |
| `plugins/tvmaze/client.py` | Migrated + added OutputPlugin base |
| `plugins/tasker/plugin.py` | Migrated + added OutputPlugin base |
| `plugins/file-reader/client.py` | Migrated to execute_run(services) |
| `tests/test_e2e_pipeline.py` | NEW: 14 E2E tests |
| `docs/SESSION33_DEEP_ANALYSIS.md` | Full analysis and action plan |

## Recovery model: slim (Session 35 F1)

Single startup scan in `persistence_mode=full` marks any non-terminal
`plugin_executions` row (`state in [started, running, claimed]`) as
`crashed`. There is no in-flight lease, no heartbeat, no atomic claim.

**Operational consequence:** at most one orchestrator may run against a
given Mongo deployment at a time. A second concurrent process is
undefined behaviour today.

**Mode behaviour:**
- `full`: connect-fail → CriticalError; recovery scan runs; query-fail
  during scan → CriticalError (durability promise).
- `degraded` (default): connect-fail → warn + continue; recovery scan
  skipped; `_save_exec_state` failures are warn-once-per-run + counter.
- `off`: NullPersistence; no recovery.

Future-work (deferred to Session 36+): lease + heartbeat + atomic claim,
checkpoints + idempotency_key for output plugins. The schema in
`datasets/11-recovery.yml` keeps these fields documented but unwired so
the slim shape is forward-compatible.
