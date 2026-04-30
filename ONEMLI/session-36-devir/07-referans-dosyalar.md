# Referans Dosyalar — Mutlak Yollar

> Yeni AI için tüm önemli dosya yolları. Branch'te checkout edildikten sonra
> bu yolların hepsi geçerli olmalı (hiçbir `.deleted/` move yapılmadı).

---

## Kök Felsefe

```
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/AGENT.md
```
**Mutlaka oku.** Project philosophy, non-negotiables, decision rules,
"What Not To Do" listesi. Tüm kararlar bunun lensinden filtrelenmeli.

---

## ONEMLI/ Klasörü

```
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/ONEMLI/
├── kritik-bulgular.md          (8 phantom feature + 4 half + 4 ops + 7 unverified + 4 Pydantic dead)
├── mongodb-audit.md             (15 madde, S36'da 6 uygulandı + annotate)
└── session-36-devir/
    ├── 00-OKU-ONCE.md           (yeni AI onboarding)
    ├── 01-felsefe-ve-mimari.md  (AGENT.md özeti)
    ├── 02-baslangictaki-durum.md (S36 başında ne vardı)
    ├── 03-plan-evrimi.md        (paralel agent karar süreci)
    ├── 04-uygulanan-isler.md    (14 commit detayı)
    ├── 05-mevcut-durum.md       (file-by-file canonical map)
    ├── 06-sonraki-adimlar.md    (smoke-test + tier 1-4)
    ├── 07-referans-dosyalar.md  (bu dosya)
    └── audit-artifacts/
        ├── 01-researcher-industry-evidence.md
        ├── 02-reviewer-hostile-code-audit.md
        ├── 03-simplifier-yagni-filter.md
        ├── 04-reviewer-round1-post-pass5.md
        └── 05-reviewer-round2-post-pass6e.md
```

---

## Datasets/ — Schema-of-Truth (14 shard + README)

```
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/datasets/
├── README.yml                   (canonical_sources_of_truth + S36 changelog)
├── 00-enums.yml                 (state, stage, run_mode, trigger_rule)
├── 01-config.yml                (config.yml top-level + plugin configs)
├── 02-manifest.yml              (plugin manifest.yml + 3-layer merge)
├── 03-run-state.yml             (run, job, jobs, plugin runtime state)
├── 04-template-context.yml      (jinja2 context + alias resolution)
├── 05-events.yml                (event bus events + payloads)
├── 06-mongodb.yml               (collections + indexes + interface + known_unwired)
├── 07-plugin-io.yml             (per-plugin input/output shapes)
├── 08-services.yml              (plugin services contracts)
├── 09-api-fastapi.yml           (FastAPI request/response + endpoint roles)
├── 10-aliases.yml               (inline alias/interpolation model)
├── 11-recovery.yml              (plugin_executions slim contract)
└── 12-safety.yml                (dry_run, no-delete, hardlink central semantics)

/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/SYSTEM_DATASETS.yml
                                  (auto-generated single-file consultation, ~34KB)
```

### `README.yml` özellikle önemli bölümleri
- `canonical_sources_of_truth`: code → dataset map
- `known_divergences_today`: aktif drift listesi
- `dead_schema_removed_2026-04-30`: Session 35-36'da silinen field'lar
- `closed_since_last_review`: tamamlanmış divergence'lar
- `unverified_in_2026-04-30_audit`: spot-check pending alanlar
- **`session_36_changes_2026-04-30`**: S36 PASS-by-PASS changelog

---

## Source — Ana Modüller

### Core
```
src/archiverr/core/
├── orchestrator.py              (S36 PASS 1: _register_event_handlers silindi)
├── plugins/
│   ├── stage_executor.py        (PluginInvoker + ParallelGroupExecutor — refactor C4)
│   ├── resolver.py              (DependencyResolver — plugin requires graph)
│   ├── sdk/
│   │   ├── manifest.py          (PluginManifest Pydantic, dead schema A1 hala içerde)
│   │   ├── result.py            (PluginResult dataclass)
│   │   └── types.py             (PluginStatus/MediaCategory/PluginCategory enums)
│   └── ...
├── services/
│   ├── plugin_services.py       (services.update_plugin canonical)
│   └── protocols.py             (S36 PASS 2: save_plugin_data ghost silindi)
├── safety.py                    (safe_copy, safe_write, safe_move, dry_run)
└── locking/
    ├── manager.py               (FSLockManager — validation only, runtime acquire yok)
    └── validator.py
```

### State
```
src/archiverr/state/
├── models.py                    (RunState, JobState, RunStatus, JobStatus, PluginResult)
├── manager.py                   (GlobalStateManager — S36 PASS 2: dead wrappers silindi)
├── job_manager.py               (canonical save_run/save_job ana yolu, line 99,131)
├── plugin_data_manager.py       (S36 PASS 2/3: dead methods + update_plugin_doc silindi)
├── persistence_delegate.py      (S36 PASS 2/3: hasattr-guard sleeper'lar silindi)
└── template_context.py          (S36 prep: _build_plugin_surface canonical)
```

### Infrastructure
```
src/archiverr/infrastructure/
├── database/
│   ├── interface.py             (PersistenceInterface ABC)
│   ├── pymongo_persistence.py   (S36 PASS 1/3: dead indexes + plugin_docs silindi)
│   ├── null_persistence.py      (no-op fallback)
│   └── async_client.py          (Motor → AsyncMongoClient migration kaynağı)
└── repositories/
    └── plugin_result_repository.py
```

### API
```
src/archiverr/api/
├── main.py                      (FastAPI app, lifespan, CORS)
├── deps/
│   ├── database.py              (S36 PASS 6.E: cache-after-ping fix)
│   └── common.py                (S36 PASS 4 Y3 + PASS 6.C: legacy methods silindi)
└── v1/
    ├── router.py                (S36 PASS 6.D: system_router include)
    ├── __init__.py              (S36 PASS 6.D: docstring güncellendi)
    ├── run/                     (subprocess CLI proxy)
    │   ├── router.py            (S36 PASS 4 Y1: full stderr logger)
    │   └── schemas.py           (S36 PASS 5 Y6: phantom URL fields silindi)
    ├── runs/                    (canonical RESTful CRUD)
    │   └── router.py            (S36 PASS 6.B/C: PyMongoError + legacy fallback temizliği)
    ├── jobs/router.py           (S36 PASS 6.B/C)
    ├── plugins/router.py        (S36 PASS 6.B/C)
    └── system/router.py         (S36 PASS 4 Y3: canonical stats; PASS 6.D include eklendi)
```

### Plugins
```
src/archiverr/plugins/
├── scanner/      (per_run input — file enumerator)
├── file-reader/  (per_run input)
├── renamer/      (per_job parse — filename → structured)
├── tmdb/         (per_job data)
├── tvdb/         (per_job data)
├── omdb/         (per_job data)
├── tvmaze/       (per_job data)
├── ffprobe/      (per_job data — media probe)
└── tasker/       (per_job output — rename plan + safe_copy + dry_run)
```

Hepsi `services.update_plugin(data=...)` kullanır — canonical writer chain.

---

## Tests

```
tests/
├── test_api.py                  (API smoke; pre-existing 4 fail S36'da çözüldü)
├── test_full_pipeline.py        (E2E CLI; mongo-bağımlı)
├── test_real_api.py             (skip if no Mongo)
├── test_integration.py          (skip if no Mongo)
├── verify_refactor.py           (S36: docstring update for canonical chain)
└── unit/
    ├── api/
    │   ├── test_endpoints.py    (S36 PASS 6.E: 9-fail cluster çözüldü)
    │   └── test_legacy.py       (skipped — legacy router removed)
    ├── core/
    │   ├── test_plugin_agnostic.py  (S36 PASS 6.A: 14 PASS, ZERO TOLERANCE guard)
    │   ├── plugins/test_stage_executor.py
    │   ├── config/test_*.py
    │   └── ...
    └── state/
        ├── test_state_manager.py  (S36 PASS 2/6.E: canonical update_plugin path)
        └── test_template_context_wp4.py  (S36 prep: "plugin" top-level key)
```

---

## Memory Bank (gitignored ama önemli)

```
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/memory-bank/
├── activeContext.md             (Last Updated April 18, eski; S36 yansıtmıyor)
├── progress.md                  (eski)
├── techContext.md               (eski)
└── ...
```

**Yeni AI için TODO**: bu dosyaları S36 sonu durumuna göre güncelle (memory-bank-sync agent ile).

---

## Audit Artifacts (mutlak yollar)

Tam metinler `ONEMLI/session-36-devir/audit-artifacts/` altında. Mutlak yollar
ek olarak:

```
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/.claude/session-artifacts/ef30ac79/
├── agent-architecture-researcher-26.md  (industry evidence — workflow-core, Kestra, Mongo official)
├── agent-architecture-reviewer-29.md    (kod hostile re-audit, B3 çürütme)
├── agent-simplifier-31.md               (YAGNI filter, 33 → 6 madde)
├── agent-architecture-reviewer-42.md    (round-1 post-PASS 5)
└── agent-architecture-reviewer-45.md    (round-2 post-PASS 6.E, root cause fix)
```

`.claude/session-artifacts/` her oturumda artar; **devir paketinin
`audit-artifacts/`'ı bu 5 kritik raporun snapshot'ı**.

---

## HANDOFF

```
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/HANDOFF.md
```
Session 36 sprint summary + 14 commits + 527/0/15 + smoke-test ready notu.
Eski Session 33 içeriği aşağıda korundu.

---

## Git

Branch: `dev/communication-refactoring`
Last commit: `e725fdb`

```bash
cd /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr
git log --oneline 3ebbdb7~1..HEAD
# 14 commits — Session 36 ekibi
```

---

## CLAUDE.md (ortam talimatları)

```
/home/samet/.claude/CLAUDE.md                                        (global)
/home/samet/Workspace/bedrock/bedrock/Tasarilar/.claude/CLAUDE.md     (project parent)
/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/.claude/CLAUDE.md  (project)
```
- No-delete policy
- Session artifacts auto-save
- Mode: orchestrator
- GPT-5.4 via Claudish CLI delegation

---

## Çalışma Komutları (cheat sheet)

```bash
# Setup
cd /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr
source .venv/bin/activate

# Test
pytest tests/unit/ -q --tb=line              # unit (Mongo-bağımsız)
pytest tests/ -q --tb=line                   # tüm suite (mongo varsa daha çok pass)
pytest tests/unit/core/test_plugin_agnostic.py -v  # ZERO TOLERANCE guard

# Lint
ruff check src/
mypy src/archiverr/

# Smoke
docker compose up -d mongodb
python -m archiverr                           # CLI run (dry_run=true default)
uvicorn archiverr.api.main:app --reload --port 8000

# Git
git status --short
git log --oneline -15
git diff <commit>~1 <commit>                 # belirli PASS'in tam diff'i
```

---

**Devir paketi tamam.** Yeni AI başlamak için `00-OKU-ONCE.md`'den başla.
