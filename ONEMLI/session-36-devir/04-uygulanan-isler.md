# Uygulanan İşler — 14 commit detayı

## Commit zinciri (chronological)

```
e725fdb  session 36: HANDOFF final — 14 commits, 527/0/15 green, smoke-test ready
7f440c3  session 36 PASS 6.E: cache-after-ping + minor test mock cleanup
feec863  session 36 PASS 6.D: include system_router in v1 router (was orphaned)
426e10b  session 36: dataset + HANDOFF alignment for PASS 6.A/B/C
dcf380c  session 36 PASS 6.C: drop legacy executions/matches/plugin_results readers (N6)
55fe4bf  session 36 PASS 6.B: broaden PyMongo exception handling to 503 (partial)
5dbf851  session 36 PASS 6.A: rewire test_plugin_agnostic to canonical API (recover 12 tests)
e07c970  session 36 prep: dataset cleanup + template context canonical move + audit artifacts
827e91a  session 36: ONEMLI/mongodb-audit.md — annotate session 36 outcome
5d7cf22  session 36: HANDOFF.md update — Session 36 sprint summary
1d364ec  session 36 PASS 5: kill misleading docstring + phantom URL fields (Y2, Y6)
83a42d0  session 36 PASS 4: API hygiene + dataset alignment
bd3840b  session 36 PASS 3: drop plugin_docs collection chain (zero readers, pure write amplification)
68f55f9  session 36 PASS 2: drop dead save_plugin_result/update_plugin_result/save_plugin_data chain
3ebbdb7  session 36 PASS 1: kill orchestrator garbage upsert + dead indexes + plugin_executions field rename
```

---

## PASS 1 — `3ebbdb7`

### F1: Kill orchestrator event handler garbage upsert
**Sorun:** `core/orchestrator.py:382-418` `_register_event_handlers` her `job.completed`
event'inde `save_job({"job_id": job_id, "run_id": ..., "stage": ..., "status": ...})`
çağrıyordu. Ama `save_job`'un filter shape'i `{"id": job_dict.get("id", "")}` —
"id" field yok, filter `{"id": ""}` olur, `upsert=True` ile boş-id garbage doc
yaratır. Memory observation 458 confirmed real bug.

**Fix:** `_register_event_handlers` metodu + caller (line 281-282) silindi.
Ana yol (`state/job_manager.py:99,131`) zaten `save_run`/`save_job` ile yazıyor.

### F2: Dead `runs.started_at` indexes drop
**Sorun:** `pymongo_persistence.py` `_create_indexes` `runs.started_at` ve
`(status, started_at)` indexleri yaratıyor. `RunState.to_dict()` (`models.py:162-168`)
top-level `started_at` yazmıyor (sadece `status.started_at`). Index hiç doc'a vurmaz.

**Fix:** `_create_indexes` ve `_create_new_indexes` tek metoda birleştirildi,
ölü indexler silindi.

### F5: `plugin_executions.started_at` → `created_at` rename
**Sorun:** `datasets/11-recovery.yml:26` schema `started_at` diyor, kod
`pymongo_persistence.py:376` `created_at` yazıyor.

**Fix:** Schema kodu izledi (slim contract = today's truth):
- `started_at` → `created_at`
- `updated_at` eklendi (kod yazıyordu)
- `duration_ms` silindi (kod hesaplamıyordu)

---

## PASS 2 — `68f55f9`

### F3: Dead plugin API chain drop
3 metod silindi (production caller=0, sadece test mock'larında):

1. `core/services/protocols.py` — `StateService.save_plugin_data` ghost Protocol method
2. `state/persistence_delegate.py:152-182` — `save_plugin_result` `hasattr`-guard sleeper
3. `state/plugin_data_manager.py:198-264` — `save_plugin_data` + `update_plugin_result` wrappers
4. `state/manager.py:246-264` — `GlobalStateManager.save_plugin_data` + `update_plugin_result` wrappers

**Canonical writer chain (canlı, dokunulmadı):**
```
plugin → services.update_plugin(data=...)
  → PluginServices.update_plugin
  → GlobalStateManager.update_plugin       (state/manager.py:191)
  → PluginDataManager.update_plugin        (state/plugin_data_manager.py:56)
  → _update_job_plugin                     (state/plugin_data_manager.py:114)
  → pymongo.save_plugin(plugin_doc)        (plugins koleksiyonu HALA yazılıyor)
```

**Test rewrite:** `tests/unit/state/test_state_manager.py` 3 test (`test_update_plugin_result_*`)
canonical `update_plugin(target_id, plugin_name, data)` rotasına çevrildi.

---

## PASS 3 — `bd3840b`

### F4: `plugin_docs` collection drop (zero readers)
**Kanıt (grep):**
- API readers: 0
- Plugin readers: 0
- Sadece persistence-internal: `pymongo_persistence.get_plugin_doc` (caller=0)

**Silindi:**
- `pymongo_persistence.py`: `PLUGIN_DOCS` constant + indexes + `update_plugin_doc` writer + `get_plugin_doc` reader
- `state/persistence_delegate.py`: `update_plugin_doc` `hasattr`-guard wrapper
- `state/plugin_data_manager.py`: `_update_run_plugin` ve `_update_job_plugin` artık `update_plugin_doc` çağırmıyor

**Per-run plugin data canonical surface:** `runs.<run_id>.plugins` embedded (via `save_run`).
**Per-job plugin data canonical surfaces:** `jobs.<job_id>.plugins` embedded (via `save_job`)
+ `plugins` collection (cross-job query, MongoDB Extended Reference pattern).

**Industry rationale:** workflow-core (danielgerlag) `WorkflowInstance.ExecutionPointers`
embedded + separate `wfc.execution_errors` collection — aynı 2-tier pattern.
`plugin_docs` 3. tier was pure waste (no readers).

---

## PASS 4 — `83a42d0`

### Y1: Subprocess stderr full-log
**Sorun:** `api/v1/run/router.py:109` subprocess stderr'i 500-byte truncate ediyor →
silent failure (AGENT.md §5 ihlali).

**Fix:** Logger eklendi, full stderr/stdout error level'da loglanıyor.
Response body 500-char truncated kalıyor (client convenience).

### Y3: Stats canonical keys
**Sorun:** `api/v1/system/router.py` ve `api/deps/common.py` stats legacy
collection sayımı (`executions/matches/plugin_results`) gösteriyor.

**Fix:** Canonical (`runs/jobs/plugins`) ile değiştirildi.

### N7: `06-mongodb.yml` known_unwired section
**Sorun:** PASS 3'te silinen `plugin_docs` ve hiç wire edilmemiş `diagnostics`
schema-of-truth'a koyulmamalı (phantom yaratır).

**Fix:** `known_unwired` block eklendi (decision: drop OR wire).

### N8: `09-api-fastapi.yml` `/run/` vs `/runs/` rol ayrımı
**Sorun:** İlk audit "duplicate router" demişti, reviewer iki ayrı model olduğunu
kanıtladı.

**Fix:** Dataset'e iki ayrı endpoint family olarak yazıldı:
- `/run/` = subprocess CLI proxy (blackbox), `RunResponse{execution_id, ...}`
- `/runs/` = canonical RESTful CRUD, `RunResponse{id, status, ...}` (canonical shape)

---

## PASS 5 — `1d364ec`

### Y2: `api/main.py` misleading docstring
Endpoint tablosu `/api/v1/executions` ve `/api/v1/matches` reklamı yapıyordu (silinmiş).
Güncellendi: `/run`, `/runs`, `/jobs`, `/plugins`, `/system`.

### Y6: Phantom URL fields drop
`api/v1/run/schemas.py` `websocket_url` ve `poll_url` `default=None` olarak tanımlı
ama hiç set/read edilmiyor. Pure speculative extension. Silindi.

### Y4 dismiss
`runs/router.py:286` `get_run_status -> get_run` "infinite recursion" suspicion'i.
İncelendi — `get_run` ve `get_run_status` iki ayrı module-level coroutine, kendisini
çağırmıyor. Recursion yok.

---

## PASS 6.A — `5dbf851` (round-1 audit kritik bulgu)

**Sorun:** PASS 2'de `tests/unit/core/test_plugin_agnostic.py:128,136` rewire
edilmemiş, eski `state.update_plugin_result(...)` çağrısı kalmıştı. `@_legacy_skip`
decorator (`hasattr(GlobalStateManager, "start_execution")` False) tüm class'ı
skip'e atıyordu → 12 test SKIPPED. AGENT.md ZERO TOLERANCE plugin-agnostic
invariant runtime'da kontrol edilmiyordu.

**Fix:**
- `_LEGACY_SKIP` marker silindi
- 4 class'tan `@_legacy_skip` decorator kaldırıldı
- `TestPluginAgnosticExecution` canonical API'ye taşındı:
  - `start_execution` → `start_run`
  - `register_match` → `create_job + get_job(idx)`
  - `update_plugin_result(idx, name, result)` → `update_plugin(job.id, name, data)`
  - `complete_match` → `complete_job`
  - `complete_execution` → `complete_run`

**Sonuç:** 12 SKIPPED → 14 PASSED. Test toplam: 498 → 510 pass.

---

## PASS 6.B — `55fe4bf` (round-1 audit önerisi, partial)

**Sorun:** Mongo down olunca 9 endpoint test'i 500 dönüyordu (503 bekleniyor).
İlk hipotez: `ConnectionFailure + ServerSelectionTimeoutError` catch yetersiz.

**Fix (partial):**
3 router'da (`runs`, `jobs`, `plugins`):
```python
except OperationFailure -> 500 (DB up but query bad)
except PyMongoError     -> 503 (covers all connectivity errors via base)
except Exception        -> 500 (true server bug)
```

`PyMongoError` base class `AutoReconnect`, `NetworkTimeout`, `ConnectionFailure`,
`ServerSelectionTimeoutError` hepsini kapsar.

**Yetersizlik:** Suite-level 9 fail çözülmedi (audit 2 root cause buldu, PASS 6.E).
Sebep: `deps/database.py` cache race, PyMongoError dispatch'e ulaşılmıyordu.

---

## PASS 6.C — `dcf380c` (round-1 audit önerisi N6)

### Legacy `executions/matches/plugin_results` reader fallbacks drop
AGENT.md §"no defensive try/catch around impossible paths" — bu collection'ların
yazıcısı 0, defansif read sadece misleading 200/empty response veriyordu.

**Etkilenen dosyalar:**

`runs/router.py`:
- `list_runs`: `["runs", "executions"]` count fallback → sadece `runs`
- `get_run`: `exec_` ID prefix variants + `["runs", "executions"]` iteration → `run_X` / `X` + sadece `runs`
- `create_run`: post-orchestrator `executions` find_one fallback drop
- `delete_run`: cascade legacy `matches/plugin_results/executions` drop, `plugin_executions` ekle
- `get_run_jobs`: `matches` collection fallback drop

`jobs/router.py`:
- `list_jobs`: `$or` 4-shape filter → `run_id` $in canonical; `matches` fallback drop
- `get_jobs_by_run`: `exec_` prefix + `matches` fallback drop
- `get_job`: `matches` fallback drop
- `get_job_plugins`: `plugin_results` + `matches` fallback chain → `jobs.plugins` embedded fallback only
- `get_job_plugin`: aynı

`plugins/router.py`:
- `get_plugins_by_run`: `plugin_results` fallback drop, `match_id`/`execution_id` aliases drop

`api/deps/common.py`:
- `AsyncPersistenceWrapper.EXECUTIONS` bölümü tamamen silindi
- `get_recent_executions(_async)`, `get_execution(_async)`, `delete_execution(_async)`, `_normalize_exec_id` — zero non-test caller

`tests/test_integration.py`:
- `persistence.get_recent_executions(limit=10)` → `persistence.get_runs(limit=10)` (guarded by hasattr)

**Net etki:** ~120 LOC azaldı, canonical-only read paths.

---

## PASS 6.D — `feec863` (kendi tespitim)

**Sorun:** `api/v1/system/router.py` `/health`, `/status`, `/version`,
`/diagnostics` endpoint'leri tanımlı ama `api/v1/router.py`'a hiç `include_router`
edilmemiş. PASS 4'te `system/router.py` stats key'lerini fix etmiştim AMA route'lar
ulaşılmazdı.

**Fix:**
- `api/v1/router.py` `system_router` include
- Inline `/system/health` ve `/system/info` (thinner duplicates) silindi
- `api/v1/__init__.py` docstring güncellendi (executions/matches reklamı silindi)

---

## PASS 6.E — `7f440c3` (round-2 audit root cause fix)

**Round-2 audit'in identified root cause:**

`api/deps/database.py:69` `_async_db = client[database]` cache atamasını
**ping'den ÖNCE** yapıyordu:
```python
_async_db = _async_client[database]   # CACHE SET
await _async_db.command('ping')       # PING (fail edebilir)
# ... if fail: return None ama _async_db hala cache'lenmiş!
```

Mongo down → ping fail → except `return None` AMA `_async_db` global'i ölü
referansa set kalmış. Sonraki çağrı `if _async_db is not None: return _async_db`
hit eder, ölü referansı döner. Endpoint code AsyncDatabase üzerinde işlem
yapmaya çalışır, ServerSelectionTimeoutError fırlar AMA bu **endpoint try/except
zinciri ulaşmadan ÖNCE**, lifespan startup hatası olarak FastAPI generic 500
handler'ına düşer.

**Fix:**
- `client` ve `db` local değişkenler
- Ping başarılı olursa cache'le (`_async_client = client; _async_db = db`)
- Ping fail olursa `await client.close()` + globals reset (`None`)
- Sync `get_sync_db` için aynı pattern

**Sonuç:** 9-fail suite cluster komple çözüldü. 510 pass → **527 pass, 0 fail**.

**Bonus temizlik:**
- `tests/unit/state/test_state_manager.py:31,205` `mock.update_plugin_doc` setup silindi
- `tests/verify_refactor.py:83-86` docstring `save_plugin_data` → canonical `update_plugin` chain

---

## Doc commits (3 adet)

### `5d7cf22` — HANDOFF.md initial Session 36 update
Session 36 sprint özeti, defer'lı işler listesi.

### `827e91a` — ONEMLI/mongodb-audit.md annotate
İlk audit'in 15 maddesinden hangileri uygulandı, hangileri elendi, hangileri
ertelendi notu eklendi. 4 yön-değişikliği listesi (B3, M3, M5, "triple-copy").

### `e07c970` — Session 36 prep
Session 35 sonu/Session 36 başında birikmiş uncommitted değişikliklerin tek
commit'i (datasets cleanup + template context canonical move + ONEMLI/ + SYSTEM_DATASETS).

### `426e10b` — Dataset + HANDOFF alignment for PASS 6.A/B/C
- `datasets/06-mongodb.yml` interface "removed" comment block PASS 2/3 kapsayacak şekilde genişletildi
- `datasets/08-services.yml` ghost `save_plugin_data` → canonical `update_plugin` signature
- `datasets/README.yml` `session_36_changes_2026-04-30` changelog block (PASS-by-PASS)

### `e725fdb` — HANDOFF final
Session 36 TL;DR'ı 14 commits / 527-0-15 olarak güncelledi, smoke-test ready notu.

---

## Net etki — sayılar

- **14 commit** (10 PASS sub-iteration + 4 doc/prep)
- **~500 LOC silindi** (net azalma)
- **0 canonical writer kırıldı** (`save_run`, `save_job`, `save_plugin`, `update_plugin` chain dokunulmadı)
- **Test:** 418 → 527 pass (+109 ek test, ÖNEMLİ: bunların 12'si plugin-agnostic guard, 9'u flaky API endpoint)
- **Skipped:** 24 → 15 (intentional legacy markers)
- **Failed:** 4 (pre-existing) → 0
- **Mongo collections:** 6 (`runs`, `jobs`, `plugins`, `plugin_docs`, `plugin_executions`, `diagnostics`-empty) → 4 canonical (`runs`, `jobs`, `plugins`, `plugin_executions`)
- **Dead schema fields silindi:** ~24 (Session 35 başında listelenmiş + S36 prep'te uygulandı)

---

**Sonraki:** `05-mevcut-durum.md` — şu an file-by-file ne durumda?
