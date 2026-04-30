# Agent Response | session:ef30ac79 | agent:architecture-reviewer | agent_id:ac0d7b63ea921b73b | seq:42 | 2026-04-30 12:37:29
# transcript: /home/samet/.claude/projects/-home-samet-Workspace-bedrock-bedrock-Tasarilar-archiverr/ef30ac79-18cf-4997-9bfa-f1382bd1099b/subagents/agent-ac0d7b63ea921b73b.jsonl

`tasker.tasks` is NOT in 06-mongodb.yml — this is correct (it's plugin output data, not a Mongo collection). User's Y6 framing is wrong.

I have enough. Let me write the audit.

---

## TL;DR (4 satır max)

5 PASS commit'in ana iddialarının **tamamı kanıtlandı** — silinen path'lerin hepsi gerçekten ölüydü, ana yazma yolu (`save_run`/`save_job` üzerinden embedded plugins) sağlam. **Tek somut regresyon: test coverage erozyonu** — `test_plugin_agnostic.py:128,136` `update_plugin_result` çağırıyor, metod silindiği için 12 test SKIPPED'a düşmüş ("Legacy GlobalStateManager execution API removed") ama yeniden yazılmamış. Y2/Y4/Y6 PASS 5'te kapatılmış (kullanıcının prompt'u bayat); Y5 (SSE) tek kalan ve geleceğe ertelendi. Smoke-test öncesi tek bloker: test_plugin_agnostic'i `update_plugin` rotasına geçirmek (~30 dk).

---

## A) Plan uygunluğu tablosu

| Madde | Yapıldı mı? | Doğru yapıldı mı? | Açıklama |
|---|---|---|---|
| **N1** orchestrator event handler garbage upsert | EVET (PASS 1) | EVET | `core/orchestrator.py` `_register_event_handlers` + iki handler tamamen silindi. `__init__`'teki çağırma da silindi (line 280). Ana yol `state/job_manager.py:98-99,131` aktif: `save_job` + `save_run` çift yazıyor. |
| **N2** dead indexes | EVET (PASS 1) | EVET | `_create_indexes` ve `_create_new_indexes` tek metoda birleşti, ölü `runs.started_at` + `(status, started_at)` kaldırıldı, try/except ile sarıldı (idempotent). |
| **N3** dead `save_plugin_*` chain | EVET (PASS 2) | KISMEN | Üç metod (+ `hasattr` guard) silindi. Ama `tests/unit/core/test_plugin_agnostic.py:128,136` hâlâ `state.update_plugin_result(...)` çağırıyor → 12 test `pytest.mark.skip` ile yamandı, **rewire edilmedi**. Coverage erozyonu var. |
| **N4** `started_at`→`created_at` schema/code align | EVET (PASS 1) | EVET | `datasets/11-recovery.yml` kod ile hizalandı, `duration_ms` (yazılmıyor) kaldırıldı, `updated_at` (yazılıyor) eklendi. |
| **N5** `plugin_docs` drop | EVET (PASS 3) | EVET | `PLUGIN_DOCS` constant + indexes + `update_plugin_doc` writer + `get_plugin_doc` reader silindi. `_update_run_plugin` ve `_update_job_plugin` artık çağırmıyor. `src/` altında tek bir `plugin_docs` referansı kalmamış. `delete_run` zaten plugin_docs'a dokunmuyordu, etkilenmedi. |
| **N6** API legacy fallbacks (executions/matches/plugin_results) | KISMEN | YETERSİZ | Sadece **stats/status endpoint'lerinde** (`api/deps/common.py:46-48`, `system/router.py:110-114`) düzeltildi. Ana router'larda (`runs/router.py:116,154,209,247,261,265,269,328,331`, `jobs/router.py:118,165,195,224,231,278,287`, `plugins/router.py:136`) defansif `["runs","executions"]` fallback'leri **hâlâ yerinde**. M9/F6 büyük temizlik yapılmadı. |
| **N7** `06-mongodb.yml` `known_unwired` section | EVET (PASS 4) | EVET | `diagnostics` ve `plugin_docs` not edildi. |
| **N8** `/run/` vs `/runs/` rol ayrımı dataset'te | EVET (PASS 4) | EVET | `09-api-fastapi.yml`'a iki ayrı execution model olarak yazıldı. |
| **Y1** subprocess silent failure | EVET (PASS 4) | EVET | `api/v1/run/router.py:109` stderr/stdout error log eklendi. |
| **Y2** `api/main.py:62-63` misleading docstring | EVET (PASS 5) | EVET | Endpoint tablosu güncellendi (`/run`, `/runs`, `/jobs`, `/plugins`, `/system`). |
| **Y3** stats endpoint canonical keys | EVET (PASS 4) | EVET | `runs/jobs/plugins` artık. |
| **Y4** `get_run_status` recursion riski | İNCELENDİ-DİSMİSS | DOĞRU | PASS 5 commit mesajında "no self-recursion" diye işaretlenmiş. Kod doğru: `get_run` ve `get_run_status` iki ayrı module-level coroutine. |
| **Y5** SSE/WebSocket | HAYIR | — | Bilinçli ertelendi, AGENT.md "no speculative extension points" ile uyumlu. PASS 5 ayrıca phantom `websocket_url`/`poll_url` field'larını sildi. |
| **Y6** `tasker.tasks` phantom | YANLIŞ İDDİA | — | `tasker.tasks` Mongo collection'ı DEĞİL. `JobState.output.data.tasks` (renaming context içeriği). `06-mongodb.yml`'da yok, olmaması doğru. README.yml'da "data shape spot-check pending" notu var, o ayrı. Kullanıcının Y6 olarak yazdığı şey yanlış kategorize edilmiş. |

---

## B) Regresyon — kanıtlı (her madde için file:line)

### B.1 — Orchestrator event handler silindi (N1)
**Kanıt:** `src/archiverr/core/orchestrator.py` — `_register_event_handlers` metodu yok (`grep` sonuç boş). `__init__`'teki çağırma da yok.
**Ana yol GERÇEKTEN yazıyor mu?** EVET. `src/archiverr/state/job_manager.py:98-99` `self._persistence.save_job(job)` + `self._persistence.save_run(run)` job_completed sırasında. `:131` ikinci kez `save_job(job)`. `JobState.to_dict()` (`models.py:127-136`) `plugins` field'ını içeriyor, yani embedded plugin verisi `jobs.plugins`'da otomatik yazılıyor. Plugin tamamlama Mongo trace'i: `plugin_executions` collection'ı `stage_executor.py:402` üzerinden hâlâ yazıyor. **Regresyon yok.**

### B.2 — `state/plugin_data_manager.py` `update_plugin_doc` çağrıları silindi (N5)
**Kanıt:** `plugin_data_manager.py:88-146` — `_update_run_plugin` artık sadece `self._persistence.save_run(run)` çağırıyor; `_update_job_plugin` sadece `save_plugin(plugin_doc)`. `update_plugin_doc` çağrısı yok.
**Embedded plugin verisi yazılıyor mu?** EVET. `RunState.to_dict()` (`models.py:162-168`) `plugins` field'ını içerir → `runs.plugins` embedded. `JobState.to_dict()` aynı şekilde `jobs.plugins` embedded yazıyor. **Per_run plugin verisi sadece embedded** (`plugins` collection'a per_run yazılmıyordu zaten — `_update_run_plugin` sadece `save_run` çağırıyor). **Regresyon yok.**

### B.3 — `pymongo_persistence.py` `PLUGIN_DOCS` koleksiyonu silindi (N5)
**Kanıt:** `pymongo_persistence.py:64-67` sadece 4 collection: `RUNS, JOBS, PLUGINS, PLUGIN_EXECUTIONS`. `grep -rn "plugin_docs" src/ → yalnız .deleted/ arşivinde.` `delete_run` (`:288-298`) sadece `PLUGINS`/`JOBS`/`RUNS` siliyor; eski kod da plugin_docs'a dokunmuyordu (audit doğrulandı). **Regresyon yok.**

### B.4 — `state/persistence_delegate.py` wrapper'lar silindi (N3)
**Kanıt:** `persistence_delegate.py` (122 satır) — sadece `save_run`, `save_job`, `save_plugin`, `configure`, `is_available` kaldı. `save_plugin_result`, `update_plugin_result`, `save_plugin_data`, `update_plugin_doc` yok.
**Hâlâ caller var mı?** `grep -rn "save_plugin_result\|update_plugin_result\|save_plugin_data" src/ → sıfır hit (.deleted hariç).` Production caller yok.

### B.5 — Test coverage erozyonu — REGRESYON
**Kanıt:** `tests/unit/core/test_plugin_agnostic.py:128,136` hâlâ `state.update_plugin_result(0, ...)` çağırıyor; metod silindiği için **12 test sınıfı `pytest.mark.skip("Legacy GlobalStateManager execution API removed")` ile yamandı** (line 94, 146, 166, 191, 201, 212, 222, 228, 239, 281, 285, 289 — `pytest --tb=line` çıktısında listelendi).
PASS 2'nin commit mesajı "Tests rewired to canonical update_plugin path" diyor. Bu doğru sadece `test_state_manager.py` için. `test_plugin_agnostic.py` rewire edilmedi, **bypass edildi**. Plugin-agnostic guard test'lerinin yarıdan fazlası artık çalışmıyor.

---

## C) Yeni doğan sorunlar

### C.1 — `test_plugin_agnostic.py` skip edilmiş (CRITICAL)
12 test SKIPPED. Plugin-agnostic davranışın asıl runtime guard'ı (`test_state_manager_with_mock_plugin`, `test_dependency_resolver_with_mock_plugins`, `test_input_plugin_has_no_dependencies` vb.) artık yürütülmüyor. AGENT.md'nin "ZERO TOLERANCE" kuralı bu test üzerinden enforce ediliyordu. PASS 2'nin "tests rewired" iddiası kısmen yanlış.
**Düzeltme:** `update_plugin_result(idx, name, result)` → `update_plugin(job_id, name, result.data)` rotasına çevir. ~30 dk.

### C.2 — N6 yarım kaldı: API legacy fallback'ler hâlâ ana router'larda
**Kanıt (grep):** `api/v1/runs/router.py:116,154,209,247,261,265,269,328,331`, `api/v1/jobs/router.py:118,165,195,224,231,278,287`, `api/v1/plugins/router.py:136` — `executions/matches/plugin_results` fallback okumaları yerinde. Sadece stats endpoint'i temizlendi. Smoke-test'te 6+ endpoint eski schema'ya düşebilir. AGENT.md §"no defensive try/catch around impossible paths" ihlali devam ediyor.

### C.3 — Test suite'i çok flaky
**Kanıt:** Full suite çalıştırınca 8 fail (Mongo bağlı değil → 500 yerine 503 dönmesi gerekiyor). Tek başına çalıştırılırsa pass; sıralama-bağımlı. Bu **PASS commit'lerin değil**, observation 481'deki pre-existing API hata yönetimi sorunudur. Ama smoke-test öncesi konfor için biri ele almalı.

### C.4 — API consumer impact (UI/dashboard) — DÜŞÜK RİSK
`system/router.py:110-114` ve `api/deps/common.py:46-48` `executions/matches/plugin_results` → `runs/jobs/plugins` shape değiştirdi. **Eğer** bir UI dashboard `db_status.collections.executions` field'ını okuyorsa kırılır. Ama observation 449 zaten "API legacy fallbacks pervasive" demiş — UI muhtemelen henüz inşa edilmemiş, mevcut consumer yok. Smoke-test ile doğrulanmalı.

---

## D) Kalan iş — öncelik sırası

| Sıra | Madde | Önem | Neden |
|---|---|---|---|
| **1 (KRİTİK)** | `test_plugin_agnostic.py` rewire (`update_plugin_result` → `update_plugin`) | YÜKSEK | Plugin-agnostic guard test'leri silinen API yüzünden 12 test SKIPPED. AGENT.md ZERO TOLERANCE invariant'ı runtime'da kontrol edilmiyor. ~30 dk. |
| **2 (ÖNEMLİ)** | N6 — API legacy fallback'lerini canonical-only'a indir | ORTA | `runs/router.py`, `jobs/router.py`, `plugins/router.py` 14+ defansif fallback. AGENT.md §"no defensive try/catch around impossible paths". `executions`/`matches`/`plugin_results` zaten yazıcısı 0. ~1 saat. |
| **3 (ÖNEMLİ)** | Pre-existing 500-vs-503 bug (observation 481) | ORTA | Mongo down olunca 500 yerine 503 dönmeli. `tests/test_api.py:79` ve `tests/unit/api/test_endpoints.py:76` flaky çünkü bu hata. Smoke-test'in temiz çıkması için gerekli. ~30 dk. |
| **4 (KÜÇÜK)** | Y2/Y4/Y6 — kullanıcının listesinde ama PASS 5'te kapatıldı | TAMAM | İş yok. Y2 (PASS 5 commit), Y4 (PASS 5 dismiss kanıtlı), Y6 (yanlış kategori — `tasker.tasks` collection değil, plugin output verisi). |
| **5 (ERTELE)** | Y5 — SSE/WebSocket | DÜŞÜK | UI consumer yok. AGENT.md §"no speculative extension points". UI gerçekten gerekene kadar bekle. |

**Öncelik sırası:** 1 → 3 → 2 → 4-5. (1 ve 3 smoke-test bloker; 2 hijyen; 4-5 ya tamam ya bekleme.)

---

## E) Update gereken dataset/memory bank dosyaları

### Datasets
- **`06-mongodb.yml`** — PASS 4'te `known_unwired` eklendi. Ek olarak `update_plugin_doc`/`get_plugin_doc` PyMongo'dan tamamen silindi: dataset'in interface yorum bloğunda (`:118` etrafında) `update_plugin_doc -- removed PASS 3` notu varsa OK; yoksa eklenmeli.
- **`11-recovery.yml`** — PASS 1'de `started_at`→`created_at` align edildi. ✓
- **`08-services.yml`** — `services.state.save_plugin_data` referansı varsa silinmeli (canonical olan `services.update_plugin`).
- **`README.yml`** — `dead_schema_removed_2026-04-30` veya yeni bir bölüm: `session_36_pass_1_to_5` altında silinen path'ler listelenmeli.

### Memory bank
- **`memory-bank/activeContext.md`** — Şu an uncommitted (134→86 satır major rewrite). PASS 1-5 özeti girmeli.
- **`memory-bank/progress.md`** — PASS 1-5 özet, tamamlanan N1-N5+N7+N8 + Y1-Y4 işaretlenmeli; kalan N6 (kısmen), Y5 (ertelendi) belirtilmeli.
- **`memory-bank/techContext.md`** — Mongo collection sayımı 6→4 (`runs, jobs, plugins, plugin_executions`). PluginDataManager API'si (`update_plugin` canonical, `update_plugin_result/save_plugin_data` silindi) güncellenmeli.
- **`HANDOFF.md`** — Session 36 sonu: 5 PASS commit, 1 known regression (test_plugin_agnostic skip), 3 kalan iş (test rewire, 500→503 fix, N6 cleanup).

---

## F) AGENT.md uyumluluğu — son kontrol

| Madde | Uyum | Kanıt |
|---|---|---|
| **no speculative extension points** | ✓ | PASS 5 `websocket_url`/`poll_url` phantom field'ları sildi. PASS 3 `plugin_docs` (zero readers) sildi. PASS 2 `save_plugin_result` hasattr-guard sleeper'ı (interface'te abstractmethod değil, "ileride lazım olur" mentalitesi) sildi. |
| **complexity earned only by current requirement** | ✓ | 3-tier plugin storage → 2-tier (Extended Reference Pattern). PluginDataManager gereksiz wrapper'lar (`save_plugin_data`, `update_plugin_result`) silindi. PluginExecutions slim contract korundu (`claimed_at`, `lease_expires_at`, `idempotency_key`, `output_fingerprint` schema'dan da silindi). |
| **no defensive try/catch around impossible paths** | ✗ KISMEN | `persistence_delegate.py:63,86,109` `hasattr(self._persistence, 'save_run/save_job/save_plugin')` guards hâlâ orada — bunlar her zaman True (interface'te abstractmethod). Defensive ama küçük; M9/F6 (API router fallbacks) hâlâ büyük ihlal. PASS commit'leri **bu konuda iyileştirdi ama tamamlamadı**. |
| **core stays plugin-agnostic** | ✓ | `core/orchestrator.py`'da plugin adı yok; persistence layer plugin adı bilmiyor. test_plugin_agnostic guard'ı (commit hooks) hâlâ aktif (2 PASSED guard test'i). Ama runtime test'lerin 12'si SKIPPED — guard'ın asıl assertion'larını kaybettik. |

---

## G) Bir sonraki PASS önerisi (en kritik 3 madde)

**Smoke-test öncesi (zorunlu) — toplam ~1.5 saat:**

1. **PASS 6.A — `test_plugin_agnostic.py` rewire (~30 dk)**
   - Why: AGENT.md ZERO TOLERANCE plugin-agnostic invariant'ı runtime'da kontrol edilmesi şart. 12 SKIPPED test plugin contract'ının asıl regresyon network'ü.
   - What: `state.update_plugin_result(idx, name, PluginResult)` → `state.update_plugin(job_id, name, result.data)`. `PluginResult` import'u kaldır. `mock_input_plugin["name"]` zaten generic — sadece API rotası değişiyor.
   - Files: `tests/unit/core/test_plugin_agnostic.py:121-140` ve diğer 11 SKIPPED bloğu.

2. **PASS 6.B — 500→503 hata yönetimi (~30 dk)**
   - Why: `test_get_execution_not_found` ve `test_endpoints.py` flaky; smoke-test temiz çıkmıyor. Mongo down olunca 500 (silent failure) yerine 503 (Service Unavailable) dönmeli. AGENT.md §5 "no silent failures" kapsamında.
   - What: `api/v1/runs/router.py` `get_run` (`:139`) içinde `ConnectionFailure`/`ServerSelectionTimeoutError` yakalaması.
   - Observation 481 referans.

3. **PASS 6.C — N6 API legacy fallback temizliği (~1 saat)**
   - Why: AGENT.md §"no defensive try/catch around impossible paths" en büyük kalan ihlal. `executions`/`matches`/`plugin_results` writer'ı 0; tüm fallback'ler dead read. UI yokken temizleme maliyeti minimum.
   - What: `runs/router.py` line 116, 154, 209, 247, 261, 265, 269, 328, 331; `jobs/router.py` line 118, 165, 195, 224, 231, 278, 287; `plugins/router.py` line 136. Ayrıca `api/deps/common.py:56-84` `get_recent_executions_async`, `delete_execution_async` legacy metodları.
   - **Smoke test sonrası** olabilir (silmeden önce gerçek prod Mongo'da bu collection'larda veri olup olmadığını kontrol et — `mkdir -p .deleted && mongoexport`).

**Sıralama:** 6.A → 6.B → SMOKE TEST → 6.C.

**Smoke-test ne zaman hazır:** PASS 6.A (test guard'ları onaran) + PASS 6.B (Mongo-down davranışı düzeltilen) tamamlandığında. Toplam ~1 saat ek iş. PASS 6.C smoke-test sonrası, çünkü silme işlemi prod-data sürpriziyle karşılaşabilir.

---

İlgili dosya yolları (mutlak):
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/tests/unit/core/test_plugin_agnostic.py:128,136` (regresyon)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/tests/unit/api/test_endpoints.py:76` (pre-existing 500-vs-503)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/runs/router.py:116,154,209,247,261,265,269,328,331` (N6 kalanı)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/jobs/router.py:118,165,195,224,231,278,287` (N6 kalanı)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/plugins/router.py:136` (N6 kalanı)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/deps/common.py:56-84` (N6 legacy methods)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/persistence_delegate.py:63,86,109` (defensive hasattr guards, küçük)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/plugin_data_manager.py:88-146` (canonical writer chain — DOĞRULANDI)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/infrastructure/database/pymongo_persistence.py:64-67,154-188,288-298` (4 collection, indexes, delete_run)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/models.py:127-136,162-168` (RunState/JobState.to_dict — embedded plugins kanıtı)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/job_manager.py:98-99,131` (canonical persistence ana yolu)
