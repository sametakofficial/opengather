# Mevcut Durum — File-by-File Canonical Map

**Snapshot tarihi:** 2026-04-30, post `e725fdb` (Session 36 sonu)
**Test durumu:** 527 passed, 0 failed, 15 skipped (intentional)

---

## MongoDB — Canonical 4 Collection

```
runs          → RunState.to_dict() (state/models.py:155-168)
                Writer: save_run (pymongo_persistence.py)
                Reader: api/v1/runs/router.py
                Embedded: status, plugins, jobs[], config, options, input, output

jobs          → JobState.to_dict() (state/models.py:127-136)
                Writer: save_job (pymongo_persistence.py)
                Reader: api/v1/jobs/router.py
                Embedded: status, plugins (per-job plugin data hot path)

plugins       → flat (job_id, plugin_name) doc — Extended Reference Pattern
                Writer: save_plugin (pymongo_persistence.py)
                  ← _update_job_plugin (state/plugin_data_manager.py:114)
                  ← _update_run_plugin? (run plugins go to runs.plugins embedded)
                Reader: api/v1/plugins/router.py + api/v1/jobs/router.py
                Use case: cross-job query ("son 50 renamer çıktısı")

plugin_executions → recovery surface (slim contract)
                Writer: save_plugin_execution (pymongo_persistence.py:347)
                  ← stage_executor.py:402 (per_job plugins)
                  ← orchestrator.py:494 (per_run plugins?)
                Reader: get_unfinished_plugin_executions (recovery scan)
                Note: per-run plugin execution recording E1/K6 issue, not yet wired
```

### Removed (Session 36)
- `plugin_docs` (PASS 3) — pure write amplification
- `runs.started_at` indexes (PASS 1) — never matched
- legacy `executions`, `matches`, `plugin_results` reader fallbacks (PASS 6.C)

### Known unwired (datasets/06-mongodb.yml notes)
- `diagnostics` — `DiagnosticsLogger` never instantiated; `system/router.py:180`
  reads always-empty collection. Decision: drop OR wire.

---

## API — Canonical Routes

`api/main.py` → mounts `api/v1/router.py` at `/api/v1`

`api/v1/router.py` includes:
- `runs_router` at `/runs` (canonical CRUD)
- `jobs_router` at `/jobs`
- `plugins_router` at `/plugins`
- `run_router` at `/run` (subprocess CLI proxy, blackbox)
- `system_router` at `/system` (PASS 6.D'de orphaned'tan kurtarıldı)

### Endpoint detayları

```
POST /api/v1/run/                  subprocess execution (full process isolation)
                                    Logs full stderr on failure (S36 PASS 4 Y1 fix)
                                    Response: legacy shape (execution_id, total_matches, ...)

GET  /api/v1/runs/                 list runs (pagination, state filter)
POST /api/v1/runs/                 create + execute (in-process via run_in_threadpool)
GET  /api/v1/runs/{run_id}         detail
GET  /api/v1/runs/{run_id}/status  status only (polling)
GET  /api/v1/runs/{run_id}/jobs    nested jobs
DELETE /api/v1/runs/{run_id}       cascade delete (jobs + plugins + plugin_executions + runs)

GET  /api/v1/jobs/                 list jobs (run_id filter)
GET  /api/v1/jobs/run/{run_id}     all jobs by run
GET  /api/v1/jobs/{job_id}         detail
GET  /api/v1/jobs/{job_id}/plugins         all plugin data for job
GET  /api/v1/jobs/{job_id}/plugins/{name}  specific plugin

GET  /api/v1/plugins/                  list plugins
GET  /api/v1/plugins/{plugin_name}     detail
GET  /api/v1/plugins/run/{run_id}      cross-job plugin output for run

GET  /api/v1/system/health
GET  /api/v1/system/status        (database connection, system info)
GET  /api/v1/system/version
GET  /api/v1/system/diagnostics   (currently always-empty; DiagnosticsLogger unwired)
```

### Exception handling pattern (PASS 6.B)
```python
except OperationFailure as e:           # DB up but query bad
    raise HTTPException(500, ...)
except PyMongoError as e:                # base — catches AutoReconnect,
    raise HTTPException(503, ...)        # NetworkTimeout, ConnectionFailure,
except Exception as e:                   # ServerSelectionTimeoutError
    raise HTTPException(500, ...)
```

### Cache-after-ping pattern (PASS 6.E)
`api/deps/database.py` `get_async_db` ve `get_sync_db`:
- Local `client`/`db` değişkenleri
- Ping başarılı olursa global cache'e ata
- Ping fail olursa `await client.close()` + globals reset
- **Bu, suite-level test flakiness'in root cause fix'iydi**

---

## State Layer — Plugin Writer Chain

### Canonical (CANLI)
```python
# Plugin code (örn: src/archiverr/plugins/tmdb/client.py:169)
services.update_plugin(data=result_data)

# core/services/plugin_services.py:109
def update_plugin(target_id, plugin_name, data):
    self._state.update_plugin(tid, pname, data or {})

# state/manager.py:191
def update_plugin(target_id, plugin_name, data):
    self._plugin_manager.update_plugin(...)

# state/plugin_data_manager.py:56
def update_plugin(target_id, plugin_name, data, get_job_func):
    if target_id starts with "run_":
        self._update_run_plugin(...)         # writes runs.plugins embedded only
    else:
        self._update_job_plugin(target_id, plugin_name, data, get_job_func)

# state/plugin_data_manager.py:114
def _update_job_plugin(job_id, plugin_name, data, get_job_func):
    job.plugins[plugin_name] = data            # 1) embedded jobs.plugins
    self._persistence.save_plugin(plugin_doc)  # 2) plugins collection
```

### REMOVED (Session 36 PASS 2 + PASS 3)
- `state/manager.py.save_plugin_data` — caller=0
- `state/manager.py.update_plugin_result` — caller=0
- `state/plugin_data_manager.py.save_plugin_data` — caller=0
- `state/plugin_data_manager.py.update_plugin_result` — caller=0
- `state/persistence_delegate.py.save_plugin_result` — `hasattr`-guard sleeper
- `state/persistence_delegate.py.update_plugin_doc` — `hasattr`-guard wrapper
- `core/services/protocols.py.save_plugin_data` — ghost Protocol method
- `pymongo_persistence.py.update_plugin_doc` + `get_plugin_doc` — plugin_docs collection

---

## Recovery — Slim Contract

`datasets/11-recovery.yml`:
```yaml
recovery_model: slim

plugin_executions:
  _id: ObjectId
  run_id: run_{uuid8}
  job_id: job_{run_id}_{index}
  plugin_name: string
  attempt: int
  state: started | running | completed | failed | crashed | skipped
  created_at: ISODate    # was: started_at (PASS 1 align)
  updated_at: ISODate
  finished_at: ISODate | null
  error: string | null
  # future-work fields (slim contract: not written today)
  claimed_at: ISODate | null
  ...
```

Recovery flow: startup'ta `get_unfinished_plugin_executions` non-terminal state'leri
çağırır → "crashed" işaretler.

**Out of scope (defer):**
- `checkpoints` collection (per-plugin idempotency)
- Multi-orchestrator lease/heartbeat
- Per-run plugins → plugin_executions (E1/K6 issue, not yet wired)

---

## Datasets — 14 Shard + README

```
00-enums.yml             ← state, stage, run_mode, trigger_rule, media_category enum'ları
01-config.yml            ← config.yml top-level + per-plugin config
02-manifest.yml          ← plugin manifest.yml (Pydantic) + 3-layer merge
03-run-state.yml         ← run, job, jobs, plugin, plugins, plugin_result runtime state
04-template-context.yml  ← jinja2 context + alias resolution (canonical_sources_of_truth)
05-events.yml            ← event bus events ve payloads
06-mongodb.yml           ← collection schemas + indexes + interface + known_unwired
07-plugin-io.yml         ← per-plugin input/output shapes
08-services.yml          ← plugin services contracts (state, events, logger, config, template, provides)
09-api-fastapi.yml       ← FastAPI request/response shapes + endpoint roles (run vs runs)
10-aliases.yml           ← inline alias/interpolation model (v1)
11-recovery.yml          ← plugin_executions slim contract
12-safety.yml            ← dry_run, no-delete, hardlink central semantics
README.yml               ← index + canonical_sources_of_truth + changelog
SYSTEM_DATASETS.yml      ← auto-generated single-file consultation (~34KB)
```

`README.yml` içinde `session_36_changes_2026-04-30` block tüm PASS değişikliklerini
listeler. Yeni AI bunu mutlaka okumalı.

---

## Test Suite

### Yapısı
```
tests/
├── test_api.py                    ← API smoke (5 fail eski, şimdi yeşil)
├── test_full_pipeline.py          ← E2E CLI test (Mongo bağlı değilse fail; pre-existing)
├── test_real_api.py               ← Mongo gerçek bağlantı (skip if no Mongo)
├── test_integration.py            ← integration (skip if no Mongo)
├── verify_refactor.py             ← session 36 docstring update
└── unit/
    ├── api/test_endpoints.py      ← API unit (pre-existing 9 fail çözüldü PASS 6.E)
    ├── state/test_state_manager.py ← canonical update_plugin path test
    ├── core/test_plugin_agnostic.py ← AGENT.md ZERO TOLERANCE guard (14 PASS, S36 PASS 6.A restore)
    └── ... (diğer unit testler)
```

### Skipped (intentional)
- `test_legacy.py:12` — Legacy API router removed
- `test_memory_management.py:13` — Memory subsystem refactored
- `test_endpoints.py` 6 test — Versioning/branches removed
- `test_plugin_discovery.py:221` — check_expects removed (S32)
- `test_stage_executor.py` 6 test — `_topological_sort` + `_group_parallel_plugins` removed (S32-33)

---

## Plugins (9 active, hepsi modern protocol)

### `per_run` (input stage)
- `scanner` (registry-based file enumerator)
- `file-reader` (path-based file reader)

### `per_job`
- **PARSE**: `renamer` (filename → structured)
- **DATA**: `tmdb`, `tvdb`, `omdb`, `tvmaze`, `ffprobe`
- **OUTPUT**: `tasker` (rename plan + dry_run + hardlink + safe_copy)

Tüm plugin'ler `services.update_plugin(data=...)` kullanır. Hiçbiri ben yazdığım
silinen `update_plugin_result` chain'ini kullanmıyordu (kanıt: PASS 2 grep).

---

## Branch state şu an

```bash
$ git status --short
# (çoğunlukla temiz; sadece dataset modifications + ".deleted/" untracked'ler var)

$ git log --oneline -3
e725fdb session 36: HANDOFF final — 14 commits, 527/0/15 green, smoke-test ready
7f440c3 session 36 PASS 6.E: cache-after-ping + minor test mock cleanup
feec863 session 36 PASS 6.D: include system_router in v1 router (was orphaned)
```

---

**Sonraki:** `06-sonraki-adimlar.md` — sıradaki PASS önerileri.
