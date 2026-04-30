# Agent Response | session:ef30ac79 | agent:architecture-reviewer | agent_id:a692ace3b3d91d04a | seq:29 | 2026-04-30 01:59:00
# transcript: /home/samet/.claude/projects/-home-samet-Workspace-bedrock-bedrock-Tasarilar-archiverr/ef30ac79-18cf-4997-9bfa-f1382bd1099b/subagents/agent-a692ace3b3d91d04a.jsonl

Confirmed: `job.completed` is emitted via `Events.JOB_COMPLETED` from `state/job_manager.py:146`. Audit's M1 claim is fully verified — every job completion fires the buggy event handler that writes `{job_id, run_id, stage, status}` shape, which `save_job` filters on `id` (line 213-214) and upserts a phantom doc. Real bug.

I have enough. Now let me write the hostile re-audit response.

---

## TL;DR (5 satır)

Önceki audit'in **5 ana iddiasından 3'ü doğrulandı, 1'i kısmen doğrulandı, 1'i körü körüne agresif** (B3 duplicate router). M1 garbage upsert REAL BUG (her job.completed event'inde tetikleniyor). M4 dead API claim DOĞRU (`save_plugin_result` interface'te yok, sadece `hasattr` guard var). "Triple-copy plugin data" iddiası YANLIŞ — `plugins` collection (cross-job query) ile `plugin_docs` (per-target snapshot) farklı concern, `jobs.plugins` runtime cache. Plan'ın "körü körüne sil" ruhu AGENT.md §"YAGNI > SOLID" prensibinin **kapsamı dışında** — silinecekler ile recovery için tutulanları net ayırmak gerek.

---

## 1) Önceki audit — KARAR-KARAR challenge

### M1: orchestrator.py:382-418 event handler garbage doc upsert
- **Önceki audit kanıtı:** `orchestrator.py:392` `save_job({"job_id": job_id, "run_id": ..., "stage": ..., "status": ...})` shape gönderiyor; `pymongo_persistence.py:206-214` `job_dict.get("id", "")` ile filter `{"id": ""}` kuruyor.
- **Yeniden okudum, doğrulandı:** `pymongo_persistence.py:202-221` `save_job`'ın filter'ı `{"id": job_id}` ve `job_id = job_dict.get("id", "")`. Handler `"id"` yerine `"job_id"` koyuyor → `id=""` ile filter kurulup `upsert=True` ile *yeni* boş-id doc yaratır. Her `job.completed` event'inde tetiklenir; emitter aktif: `state/job_manager.py:146`.
- **Bir de kötüsü var:** Aynı işin "doğru" ana yolu zaten `state/job_manager.py:99,131` üzerinden `save_run`/`save_job` çağrısıyla yapılıyor. Yani handler **çift yazma + bozuk shape**. Sonuncu `update_one(... id="")` çağrısı ilk yazımın `id` field'ını silmiyor (filter `id=""` eşleşmediği için yeni doc), ama collection'da `id`/`_id` semantik farkı kafa karıştırıyor.
- **AGENT.md §5 Safety:** "No silent failures … no defensive try/catch around impossible paths". Bu handler hem partial overwrite hem de boş-id garbage doc. Safety kültürüne aykırı.
- **Verdict: BUG, DELETE.** Handler hem işe yaramaz (ana yol zaten yazıyor) hem aktif zarar veriyor. Ana yola dokunmadan handler'ı sil. (~5 dk).

### M4: save_plugin_result, update_plugin_result, save_plugin_data — "dead API" claim
- **Yeniden grep:**
  - `save_plugin_result`: PyMongo'da yok (`pymongo_persistence.py:1-414` içinde def yok), `interface.py:15-189` içinde abstractmethod değil. Sadece `state/persistence_delegate.py:152-182` `hasattr` guard ile çağırıyor; `state/plugin_data_manager.py:264` ve `state/manager.py:258`'de wrapper'lar var. Production caller (plugins/, core/, api/): **0**. Test: sadece mock üzerinde (`tests/unit/state/test_state_manager.py:30,238` — `mock.save_plugin_result = MagicMock()`).
  - `update_plugin_result`: `state/manager.py:258` ve `plugin_data_manager.py:230` tanımlar; non-test caller: **0** (plugins/, core/, api/, orchestrator.py'de yok). Sadece test (`test_state_manager.py:163-220`, `test_plugin_agnostic.py:128,136`).
  - `save_plugin_data`: `state/manager.py:246` ve `plugin_data_manager.py:198` tanımlar; production caller: **0**. Plugin'ler `services.update_plugin(data=...)` kullanıyor (scanner/client.py:74, tmdb/client.py:169, ffprobe/client.py:143, renamer/client.py:89, tasker/plugin.py:92).
- **Recovery (11-recovery.yml) bunları planlıyor mu?** Hayır. 11-recovery.yml `plugin_executions` ve future `checkpoints`'i tarif ediyor; `plugin_result` persistence'ını içermiyor. `dataset/06-mongodb.yml:87-107` interface listesinde de bu metotlar **yok** (ve commit `2026-04-30` notunda silindiklerini söylüyor).
- **AGENT.md §"Writing Style":** "no defensive try/catch around impossible paths … no `Any` casts to hide typing issues". `hasattr(_persistence, 'save_plugin_result')` — interface'te yok, defansif type hack.
- **Verdict: REALLY-DEAD, REMOVE.** Audit doğru. Test'ler MagicMock üstünde çağırıyor; testleri de güncellemek gerek (~30 dk toplam).

### "Triple-copy plugin data" — jobs.plugins + plugins + plugin_docs
- **Writer/reader haritası (gerçek grep):**
  - **`jobs.plugins`** (in-memory + Mongo embedded): writer `state/plugin_data_manager.py:125` (`job.plugins[plugin_name] = data`); save'i `save_run`/`save_job` üzerinden gidiyor. Reader: `template_context.py` (Jinja), `api/v1/jobs/router.py:233-242,290-296` (embedded fallback). **Hot path: in-memory state, render context.**
  - **`plugins` collection** (flat `(job_id, plugin_name)` doc): writer `pymongo_persistence.py:226 save_plugin` ← `plugin_data_manager.py:145`. Reader: `api/v1/jobs/router.py:219,271` (primary), `api/v1/plugins/router.py:93,131` (cross-job analytics: "tüm renamer çıktılarını listele"). **Cross-job query surface.**
  - **`plugin_docs`** (per-target aggregate, `_id=run_id|job_id`): writer `pymongo_persistence.py:251 update_plugin_doc` ← `plugin_data_manager.py:106,131`. Reader: `pymongo_persistence.py:268 get_plugin_doc` (sadece persistence-içi). API'de **0** caller (grep `plugin_docs` API'de hit yok).
- **Hipotez kanıt:**
  - `jobs.plugins` embedded = render-time canonical surface (`04-template-context.yml`). **Vazgeçilmez.**
  - `plugins` collection = flat shape, `(job_id, plugin_name)` unique index ile cross-job query (örn. "son 10 run'da renamer'ın confidence'ı"). API gerçekten okuyor → **canlı**.
  - `plugin_docs` = niyet "per-target tek round-trip snapshot"; ama API kullanmıyor, persistence-internal. **Kanıt:** `interface.py` listesinde `update_plugin_doc/get_plugin_doc` abstract bile değil; PyMongo-only. AGENT.md §"Decision Rule": "If removing a component would destroy the project's truth model, keep it core". `plugin_docs` truth model'i etkilemiyor — `plugins` collection aynı bilgiyi yeterli ve hızlı veriyor.
- **AGENT.md §"YAGNI > SOLID":** "Three similar lines > premature abstraction. 'This works and is readable' is a valid review conclusion." Burada *üç koleksiyon* var; üçü **farklı concern** ama biri (plugin_docs) consumer'ı olmadığı için ölü ağırlık.
- **Verdict: PARTIAL-OVERLAP.**
  - `jobs.plugins` = KEEP (template context truth)
  - `plugins` = KEEP (cross-job analytics; API live reader)
  - `plugin_docs` = DROP after one decision: confirm no future API plan uses it. *Bu ÜÇLÜ kopya değil; iki canlı concern + bir ölü kayıt yeri*. Önceki audit "üçlü kopya, drop birini" de aynı yere geliyor ama nedensellik daha zayıf anlatılmış.

### M2: dead indexes claim
- **Doğrulandı:** `pymongo_persistence.py:158` `create_index("started_at")` — `RunState.to_dict()` (models.py:162-168) top-level `started_at` yazmıyor; sadece `status.started_at`. Bu index hiçbir doc'a vurmaz. `:159` `[("status", 1), ("started_at", -1)]` aynı sebep — `status` whole-doc, `started_at` top-level yok. `:163` `JOBS run_id` create_index → `:327`'de zaten yeniden create ediliyor (idempotent ama duplicate config).
- `_create_new_indexes` (`:311-345`) zaten doğru indeksleri kuruyor (`id` unique, `created_at`, `status.state`, `(run_id,index)` unique).
- **Verdict: REAL DEAD INDEXES.** `_create_indexes`'teki `runs.started_at` ve `(status, started_at)`'i kaldır. Tek fonksiyona birleştir. (~10 dk).

### M3: plugin_docs + diagnostics datasets'e eklenmemiş
- **`plugin_docs` writer/reader:** writer `pymongo_persistence.py:251`; reader sadece persistence-internal. **API'de 0 reader** (grep `plugin_docs` API/ dizini = 0 hit).
- **`diagnostics`:** `DiagnosticsLogger` instantiation grep: sadece docstring'de (`infrastructure/database/diagnostics.py:13` ve internal `:236`). Core/orchestrator/main.py'de `DiagnosticsLogger(...)` çağrısı **yok**. `Debugger.set_diagnostics_logger` (utils/debug.py:72) hiç çağrılmıyor.
- **Tüketici:** `api/v1/system/router.py:180` `db["diagnostics"].find(...)` okuyor — koleksiyon boş, endpoint sürekli `total_entries=0` döner.
- **Verdict (datasets):** Audit'in M3'ü 06-mongodb.yml'a ekleme önerisi **fazlalık** — `plugin_docs` zaten ya silinecek ya unwired kalacak; `diagnostics` ise unwired-on-purpose. Doğru hareket: 06-mongodb.yml'a "*known unwired*" altında listele, **schema-of-truth'a koyma**. Aksi halde "yazılır" sanısı yaratır. AGENT.md §"contract_freeze_rules: when code disagrees with a dataset file, code is the bug, not the dataset" — burada **kod doğru** (yazıcı yok), dataset'e ekleme kodu phantom'a iter.

### M5: started_at vs created_at name mismatch
- **Schema (06-mongodb.yml:18-19, 11-recovery.yml:26):** `runs.created_at`, `plugin_executions.started_at`.
- **Kod:** `pymongo_persistence.py:376` `"$setOnInsert": {"created_at": now}` — `plugin_executions` koleksiyonuna `created_at` yazıyor. 11-recovery.yml `started_at` diyor.
- Recovery scan `:391-400` `state` üstünden filter ediyor, `started_at` sorgulamıyor — fonksiyonel etki **yok**. Görünür şikayet: schema-vs-code drift.
- **Verdict: SCHEMA-RENAME, NOT MIGRATION.** Slim contract zaten "future-work fields not written today" diyor. En kolay: 11-recovery.yml'de `started_at`'i `created_at` (kod adı) olarak güncelle. Migration yok, sadece YAML edit (~2 dk). Önceki audit doğru ama "code is the bug" varsayımı yanlış — burada *schema dataset'i kodla hizalanmalı çünkü slim contract written-today'i tarif eder*.

---

## 2) Yeni bulgular (önceki audit'in kaçırdıkları)

**Y1 — `api/v1/run/router.py` subprocess-execution bypass:** `/api/v1/run/` POST endpoint orchestrator'ı **subprocess** olarak başlatıyor (`subprocess.run([sys.executable, '-m', 'archiverr'])`, line 84-97). Bu, `persistence_mode` contract'ı (`orchestrator.py:512-617`) tamamen baypas ediyor — `MONGODB_URI` env üzerinden kalıtsal alıyor, dry_run/options merge'i temp YAML'a yazılıyor (line 59-69). Önceki audit bunu hiç görmedi. Süreç patladığında child output yutuluyor. AGENT.md §5: "no silent failures" → ihlal: subprocess stderr 500-byte truncate ediliyor (`run/router.py:109`).

**Y2 — `api/main.py:62-63` map-doc legacy collection'ları reklam ediyor:** "Execution CRUD" ve "Query processed matches" satırları docstring'de var ama `executions`/`matches` route'ları kayıtlı değil; sadece API fallback olarak okunuyor. Misleading public docs.

**Y3 — `api/deps/common.py:47-49` `get_statistics` için `executions/matches/plugin_results` count'larını okuyor:** `system/router.py:111-114` aynı stats'i `DatabaseStatus.collections`'a yansıtıyor. Yeni canonical olan `runs/jobs/plugins`'i hiç göstermiyor. Smoke test'te çıkış misleading.

**Y4 — `runs/router.py:286` infinite-recursion riski:** `get_run_status` `await get_run(run_id, db)` çağırıyor (kendi modülündeki function). Şu an çalışıyor ama test edilmemiş. Minor.

**Y5 — `runs/router.py:180-227` create_run endpoint orchestrator'ı thread pool'da çalıştırıyor**, ama bu blocking-from-async; AGENT.md §"Scalability and Resilience" perspektifinden tek pratik streaming/SSE çözüm yok. Long-running run için sadece poll var (`/{run_id}/status`). Plan: P3 tartışması.

**Y6 — `tasker.tasks` koleksiyonu kanıtı:** Mongo'da gerçekten yazılıyor mu? Grep `tasker.tasks` (db collection olarak) → 0 hit. Yani 06-mongodb.yml'a eklenmemiş bu collection **gerçekte de yok**. README.yml'da mention edilmiyor.

---

## 3) FastAPI yapısı — ayrı analiz

**`api/v1/run/` vs `api/v1/runs/` DUPLICATE DEĞİL:**
- `/run/` (singular, 173 LOC): subprocess execution endpoint. POST `/api/v1/run/` → fork + `python -m archiverr` + parse `reports/api_response_full_*.json`. **Use case**: full-run blackbox trigger. Schema: `RunResponse{execution_id, summary, api_response}` (legacy shape, `run/schemas.py`).
- `/runs/` (plural, 345 LOC): RESTful CRUD. GET list, GET by id, POST in-process orchestrator, DELETE, GET status, GET jobs. **Use case**: API-driven UI/poll. Schema: canonical `RunResponse{id, status, input, output, jobs, config, options}` (runs/schemas.py).

**Kanonik:** `/runs/` (CRUD model, 06-mongodb.yml ile shape uyumlu, `/{run_id}/...` sub-resource'lar burada). `/run/` ise "trigger-and-block" CLI proxy — kept for blackbox testing.

**Endpoint→collection coupling:**
- `runs/router.py` → `runs`, `executions` (legacy fallback), `jobs`, `matches` (legacy fallback), `plugins`, `plugin_results` (legacy fallback)
- `jobs/router.py` → `jobs`, `matches` (legacy), `plugins`, `plugin_results` (legacy)
- `plugins/router.py` → `plugins`, `plugin_results` (legacy)
- `system/router.py` → `diagnostics` (boş)

**AGENT.md §1 ihlali var mı?** "Core must stay plugin-agnostic". API katmanı core değil ama bağımlı. Plugin-spesifik literal grep: `api/` altında `tmdb`, `tvdb`, `tvmaze`, `omdb`, `ffprobe`, `tasker`, `scanner`, `renamer` literal'ı yok (kontrol: `grep -rn "tmdb\|tvdb" api/`). API katmanı plugin-agnostic. ✓

**Streaming/SSE/long-running:** Hayır. `runs/router.py:200-204` `run_in_threadpool(_run_orchestrator)`. Endpoint complete olana kadar bloke. WebSocket / SSE planı yok (`run/schemas.py:60` `websocket_url` field'ı var ama hiç set edilmiyor — phantom). Önceki kritik-bulgular A1 (reactive plugin) ile aynı kategori — schema'da var, runtime'da yok.

---

## 4) AGENT.md uyumluluk değerlendirmesi

1. **§5 "no silent failures":** `persistence_delegate.py:171` `hasattr(self._persistence, 'save_plugin_result')` → False → silent return. Phantom interface üyesi. **İhlal.**
2. **§"Decision Rule: Core or Plugin":** `orchestrator.py:382-418` event handler core'da plugin-agnostic ama **persistence shape'i hardcode**. Core invariant'ı zorlamıyor (filter-vs-key drift). **Smell.**
3. **§"Writing Style":** `runs/router.py:111-119` `count==0 → fallback to "executions"`; `jobs/router.py:114-119` aynı. Defensive legacy fallback'lar prod'da yapışkan duruyor. AGENT.md §"no defensive try/catch around impossible paths" — önceki audit F6 doğru.
4. **§"contract_freeze_rules: code is the bug, not the dataset":** İSTİSNA — `plugin_executions.started_at` (schema) vs `created_at` (kod): `pymongo_persistence.py:376` field adı tarihsel; schema dataset'in tarif ettiği "future-work fields"'in hangi adı kullanacağı henüz dondurulmamış. Burada dataset'i kodun gerçeğine hizalamak daha doğru çünkü slim contract'ın anlamı "today's truth".
5. **§"plugin-agnostic":** API ve persistence layer plugin-agnostic. ✓ Bu güçlü tutulmuş.

---

## 5) Önerilen düzeltilmiş plan (8 madde max)

| # | WHAT | WHY (AGENT.md ref + kod kanıtı) | WHERE | EFFORT |
|---|---|---|---|---|
| **N1** | `_register_event_handlers`'taki `on_job_completed` ve `on_plugin_completed` handler'larını kaldır | §5 "no silent failures"; çift yazma + bozuk shape (`save_job` filter `id` vs handler `job_id`). Ana yol zaten `state/job_manager.py:99,131` üzerinden yazıyor | `core/orchestrator.py:382-418` | 5 dk |
| **N2** | `_create_indexes`'teki ölü `runs.started_at` ve `(status, started_at)` indekslerini kaldır; `_create_new_indexes` ile birleştir | §"Writing Style: no speculative extension points". `RunState.to_dict()` (models.py:162-168) top-level `started_at` yazmıyor | `pymongo_persistence.py:155-176` + `:311-345` | 10 dk |
| **N3** | `save_plugin_result`/`update_plugin_result`/`save_plugin_data` ve `persistence_delegate.save_plugin_result` (hasattr-guard) sil; testleri (test_state_manager.py:163-220, test_plugin_agnostic.py:128,136) `update_plugin` rotasına çevir | §5 "no defensive try/catch around impossible paths"; interface'te abstract değil, prod caller=0 | `state/persistence_delegate.py:152-182`, `plugin_data_manager.py:198-265`, `manager.py:246-263`, ilgili testler | 30-45 dk |
| **N4** | `plugin_executions` field adını schema'da kodla hizala (`started_at`→`created_at`) **veya** kodu schema'ya çevir | §"contract_freeze: code is the bug, not the dataset" — burada slim contract bağlamında dataset adı dondurulmadı, kod canlı yazıyor → schema'yı kodla hizala | `datasets/11-recovery.yml:26` | 2 dk |
| **N5** | `plugin_docs` koleksiyonunu sil **veya** API'ye reader bağla. Karar: API consumer yoksa drop | §"YAGNI > SOLID"; `plugins` (cross-job query) + `jobs.plugins` (template context) ikilisi yeterli; üçüncü surface **sadece persistence-internal** | `pymongo_persistence.py:251-272`, `plugin_data_manager.py:106,131,145` (1 satır kaldır) | 30 dk |
| **N6** | API legacy fallback'lerini (`executions`/`matches`/`plugin_results`) tek migration script'iyle elle (eğer veri varsa) yoksa direkt sil | §"Writing Style: no defensive try/catch around impossible paths"; her endpoint'te 6+ defansif fallback. `runs/router.py:111-119,154-163,247-269,309-332`, `jobs/router.py:114-119,162-168,222-231,276-287` | API/v1 + `api/deps/common.py:47-49` | 1 saat |
| **N7** | `06-mongodb.yml`'a "known unwired" bölümü ekle: `plugin_docs` (eğer N5'te tutulduysa) ve `diagnostics`. Yazıcı yokken şema-of-truth'a koyma | §"contract_freeze_rules"; misleading dokümantasyon önle | `datasets/06-mongodb.yml` | 5 dk |
| **N8** | `api/v1/run/` (subprocess) ile `api/v1/runs/` (in-process) arasındaki rolü `09-api-fastapi.yml`'a yaz: kanonik = `/runs/`, `/run/` = blackbox/CLI-proxy | §"contract_freeze_rules"; `kritik-bulgular.md#B3` belirsiz, oysa **iki farklı execution model** (subprocess vs build_orchestrator) | `datasets/09-api-fastapi.yml` | 10 dk |

**Toplam: ~2.5 saat. Kritik smoke test öncesi: N1, N2, N4 (15 dk).**

---

## 6) Kullanıcının "körü körüne silme, neden öyle olduğunu anla" uyarısına cevap

Önceki audit'in agresyon ölçüsü:
- **M1 (DELETE handler):** Doğru karar, doğru gerekçe. ✓
- **M2 (DELETE indexes):** Doğru karar. ✓
- **M3 (ADD `plugin_docs` + `diagnostics` to dataset):** **YANLIŞ YÖN.** Yazıcısı olmayan bir koleksiyonu schema-of-truth'a eklemek phantom feature yaratır. Bunun yerine "known unwired" bölümü.
- **M4 (DELETE dead APIs):** Doğru karar; ben sadece test güncelleme efor'unu netleştirdim.
- **M5 (rename `started_at`/`created_at`):** Doğru, ama yön ters: schema kodu takip etmeli.
- **M6 (`plugin_docs` vs `plugins` çakışması):** Kullanıcı haklı — önceki audit "drop birini, üçlü kopya" diyor; gerçek **iki canlı concern + bir ölü surface**. Drop kararı doğru ama gerekçesi `jobs.plugins` ve `plugins` collection'ın AYRI roller olduğu vurgulanmadan verilmiş.

**Yumuşatma stratejim:**
- "Triple copy" framing'i reddedip iki-canlı-bir-ölü framing'ini öne çıkardım.
- "körü körüne silme" prensibi gereği `/run/` vs `/runs/` "duplicate router" iddiasını **çürüttüm** — iki ayrı execution model.
- `M3`'ü tersine çevirdim: schema'ya yazıcı-olmayan koleksiyonları eklemek yerine "known unwired" işareti.
- AGENT.md §"YAGNI > SOLID" çerçevesinde her madde için "neden var ki bu kod?" sorusunu sordum; recovery contract (11-recovery.yml `slim`) ışığında future-work field'larını korudum.

**Önceki audit'in skor kartı:** 5 ana iddia için 3 doğru, 1 yön ters, 1 framing-zayıf-ama-sonuç-doğru. Plan'ın 15 maddesinden 8'ini sıkıştırılmış N1-N8'e dönüştürdüm. Kullanıcı uyarısı haklıydı: önceki audit "delete-first" fitlesinde ilerlemiş, ama silinecekler ile schema-doc düzenlenecekler arasındaki ayrımı bulanıklaştırmıştı.

---

İlgili dosya yolları (mutlak):
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/core/orchestrator.py:382-418` (M1/N1 garbage doc)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/infrastructure/database/pymongo_persistence.py:155-176, 202-221, 251-272, 311-345, 376` (M2/N2, N4, N5)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/infrastructure/database/interface.py:1-189` (canonical API surface)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/persistence_delegate.py:152-182` (N3 hasattr-guard)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/plugin_data_manager.py:106-265` (N3, N5)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/manager.py:246-263` (N3)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/state/models.py:155-168` (RunState.to_dict)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/run/router.py:38-173` (subprocess execution)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/runs/router.py:90-345` (CRUD + in-process)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/jobs/router.py:114-296` (legacy fallbacks)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/src/archiverr/api/v1/system/router.py:111-114, 151-201` (`diagnostics` reader, `executions/matches/plugin_results` stats)
- `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/datasets/06-mongodb.yml`, `datasets/11-recovery.yml`, `datasets/09-api-fastapi.yml` (N4, N7, N8)
