# Agent Response | session:ef30ac79 | agent:architecture-reviewer | agent_id:ad2315e95dbca3da5 | seq:45 | 2026-04-30 13:07:30
# transcript: /home/samet/.claude/projects/-home-samet-Workspace-bedrock-bedrock-Tasarilar-archiverr/ef30ac79-18cf-4997-9bfa-f1382bd1099b/subagents/agent-ad2315e95dbca3da5.jsonl

Now I have everything. Writing the audit.

---

## TL;DR (4 satır max)

PASS 6.A **gerçekten** 14/14 yeşil ve plugin-agnostic guard runtime'da yeniden aktif. PASS 6.B doğru ama yetersiz: 9-fail cluster **PyMongoError dispatch hatası değil, module-global state-leak** (`deps/database.py:28-31` `_async_db` cache + lifespan `app.state.db = None` yarışı), 503 hijyeni `except` zincirine asla ulaşmıyor. PASS 6.C silmeleri kanıtlı temiz; dead caller yok. **Smoke test'e 6.A+6.C yeterli; 6.B'nin gerçek fix'i ayrı PASS.**

---

## A) PASS 6.A doğrulama

`pytest tests/unit/core/test_plugin_agnostic.py -v` → **14 passed, 0 skipped** (kanıt yukarıda). Audit-42'nin "12 SKIPPED" eleştirisi tamamen kapatılmış.

**Semantik testi:**
- `test_state_manager_with_mock_plugin` (line 90-123): `start_run` → `create_job` → `update_plugin(job.id, name, data)` → `complete_job` → `complete_run` zinciri tam. `run_state.status.total_jobs == 1`, `completed == 1` assertion'ları meaningful.
- `test_match_state_plugins_are_generic` (line 144-159): `JobState.plugins` dict-keyed string assertion — plugin-agnostic kontrat'ı somut.
- `test_dependency_resolver_with_mock_plugins` (line 211-244): `resolver.resolve(enabled)` çıktı sırası ("input önce, output sonra") generic-name ile doğrulanıyor. AGENT.md ZERO TOLERANCE invariant'ı (input plugin sıralaması) burada.

**AGENT.md guard çalışıyor mu?** EVET. `TestCorePluginAgnosticGuard.test_no_hardcoded_plugin_name_maps_in_core` (line 46-70) `core/` altındaki `*.py` dosyalarını yine satır-satır tarıyor; `'scanner': 'input'` veya `'tmdb': 'data'` mapping pattern'ini regex ile yakalıyor. PASSED. Bu testler **runtime guard değil static analyzer** — plugin-agnostic ihlali compile-time'da yakalar. Şüphe yok.

**"Test pass etsin diye semantik zayıflattım mı?"** HAYIR. `update_plugin_result(idx, name, PluginResult)` → `update_plugin(job.id, name, data)` rotası **canonical API** (kanıt: `state/manager.py:191`). Eski API'nin yaptığı her şey (timestamp, success flag, duration) artık `services.update_plugin` üzerinden değil, **stage_executor.py**'de takip ediliyor (`_save_exec_state` plugin_executions'a yazıyor). Test'in sorumluluğu doğru daraltılmış: "GlobalStateManager generic plugin-name ile data yazabiliyor mu" — bu doğru question. Shallow değil, kapsam doğru.

**Boş kalanlar:** `test_state_manager.py:31, 205` mock'larda `update_plugin_doc = MagicMock()` halen var. Production code'da `update_plugin_doc` çağıran sıfır caller olmasına rağmen mock kalıntı. Yarar yok ama zarar da yok — küçük dataset hijyen (sil veya bırak).

---

## B) PASS 6.B doğrulama

**3 router'da catch zinciri (kanıt grep):**
```
runs/router.py:132,134 / :167,169 / :222,224 / :261,263 / :317,319
jobs/router.py:131,133 / :159,161 / :185,187 / :231,233 / :283,285
plugins/router.py:73,75 / :125,127 / :157,159 / :196,198
```
Pattern doğru: `OperationFailure` → 500, `PyMongoError` (parent) → 503, `Exception` → 500. AutoReconnect/NetworkTimeout/ServerSelectionTimeoutError hepsi PyMongoError subclass — teorik olarak 503.

**ANCAK fix gerçekte çalışmıyor.** Tek-test çalıştırma: `test_list_executions_returns_200` PASSED (503 alır). Suite çalıştırma: 9 test 500 dönüyor. Sebep PyMongo dispatch değil — **deps katmanında**:

1. `deps/database.py:28-31` modül-global `_async_db` cache. İlk başarılı bağlantı sonrası asla reset edilmiyor (sadece `reset_connections()` manuel çağrı).
2. `deps/database.py:53-54`: `if _async_db is not None: return _async_db` — Mongo down olsa bile cache'lenmiş AsyncDatabase referansını döndürüyor.
3. `infrastructure/database/async_client.py:148-154`: lifespan exception yakalandığında `app.state.db = None`. Sonraki test client `get_database` çağrısı `app.state.db = None` görüp `get_async_db()` fallback'ine düşüyor → cache'lenmiş ölü `_async_db` dönüyor.
4. Endpoint `db["runs"].find(...)` çağırıyor; **AsyncMongoClient cursor ServerSelectionTimeoutError raise ediyor** (PyMongoError subclass), BUT bu `await cursor.to_list()` sırasında oluyor değil daha önce başka bir yerde — error message "500 Internal Server Error" diyor, FastAPI generic handler'ına düşüyor. Yani try/except zinciri tetiklenmiyor — büyük olasılıkla TestClient'in startup error reporting'i bunu ham 500'e çeviriyor (lifespan exception raise edilmediği için endpoint kodu hiç çalışmıyor).

**Smoke-test'te ne olacak:** Mongo gerçekten açıkken `app.state.db` valid `AsyncDatabase` olur, sorun çıkmaz. Mongo gerçekten down ise lifespan `app.state.db = None` set eder, `get_database` (line 99-101) `await get_async_db()` çağırır, BU connection deneyecek (`await self._async_db.command('ping')`) ve **fail eder, yeni client cache'lenmez**, `get_database` 503 raise eder. Yani smoke-test'te 503 alacaksın — flakiness sadece test suite'inde.

**Suite flakiness ne yapmalı?** Gerçek fix dependencies'de:
- `deps/database.py:53` cache check'i kaldır VEYA cache başarısız ping sonrası `_async_db = None` yap.
- TestClient fixture'ında `reset_connections()` autouse=True olarak çağır.
- `mongodb_lifespan` exception path'inde `_async_db` global'ini de None'a çek (currently `app.state.db = None` yapıyor ama global cache temiz değil).

**6.D ayrı session mı, defer mı?** Smoke-test yapısal olarak Mongo açıkken çalışacak; flakiness suite-only. **Defer önerilir.** AGENT.md "no defensive try/catch around impossible paths" — bu suite-test ortamı yapay sorunu. Smoke test sonrası 6.D olarak ele al.

---

## C) PASS 6.C doğrulama (en uzun bölüm)

**Silinen path güvenliği:**

`grep -rn "get_recent_executions\|get_execution\b\|delete_execution\|EXECUTIONS\|_normalize_exec_id" src/ tests/ → SADECE .deleted/ ve test_integration.py:332 yorum satırı`. Hiç prod caller yok. `AsyncPersistenceWrapper.EXECUTIONS` blok temiz silinmiş.

**Canonical API kontrolü (kanıt grep `executions|matches|plugin_results` v1/runs|v1/jobs|v1/plugins):**
- `runs/router.py:120` — yorum satırı ("legacy 'executions' fallback dropped")
- `runs/router.py:256` — `db["plugin_executions"].delete_many` — bu **plugin_executions** (aktif slim collection), `executions` değil. Doğru.
- Kalan grep hit'leri yok. **Ana router üçlüsü canonical-only.**

**`runs/router.py:68-70` embedded summary fallback'leri:**
```python
total_jobs=status_data.get("total_jobs", doc.get("summary", {}).get("total_matches", 0))
completed=status_data.get("completed", doc.get("summary", {}).get("completed_matches", 0))
failed=status_data.get("failed", doc.get("summary", {}).get("failed_matches", 0))
```
Bu **migration kalıntısı**. `RunState.to_dict()` `total_matches` adıyla yazmıyor (S36 öncesi yazıyordu). Eski Mongo doc'larında `summary.total_matches` field'ı olabilir. Yeni yazımlarda `status.total_jobs` zaten canonical key. **Karar:** Eğer prod Mongo'da pre-S36 dokümanları yoksa sil; varsa bu yıl içinde data migrate ettikten sonra sil. **Smoke-test boyunca tutmak güvenli** (defansif ama küçük; AGENT.md ihlali değil çünkü gerçek migration semantiği var).

**`delete_run` cascade (`runs/router.py:254-257`):**
```python
await db["jobs"].delete_many({"run_id": actual_id})
await db["plugins"].delete_many({"run_id": actual_id})
await db["plugin_executions"].delete_many({"run_id": actual_id})
await db["runs"].delete_one({"id": actual_id})
```
**`plugin_executions` cascade ekleme doğru.** `plugin_executions` slim trace collection (lease/claimed_at/state). Bir run silindiğinde orphan `plugin_executions` doc'larını bırakmak data leak. AGENT.md slim contract'ı bozmuyor — slim contract field-level (TTL, idempotency_key vb. silindi); cascade lifecycle invariant'ı **canonical**. Eski kodda yoktu çünkü orphan kabul edilmişti; şimdi temiz. Doğru karar.

**N6 dead caller grep (PASS 6.C iddiası):** `update_plugin_result\|save_plugin_result\|save_plugin_data\|update_plugin_doc` src/ altında **0 hit** (.deleted hariç). `tests/verify_refactor.py:83-85` yorum satırı (eski docstring), `tests/unit/state/test_state_manager.py:31,205` mock attribute. Production caller yok. **Silmeler kanıtlı güvenli.**

**Yeni risk:** `jobs/router.py:46-48` hâlâ `execution_id` legacy alias map ediyor (`run_id = doc.get("run_id") or doc.get("execution_id", "")` + `if run_id.startswith("exec_"): run_id = run_id.replace(...)`). Bu PASS 6.C scope'u dışında ama N6'nın "fully canonical" iddiasını kısmen yumuşatıyor. Eski Mongo dokümanları için defansif. **Karar:** Smoke-test sonrası.

---

## D) Yeni doğan sorunlar

1. **`runs/router.py:46-48` ve `jobs/router.py:46-48` `execution_id`/`exec_` kalıntıları.** PASS 6.C "canonical-only" diyor ama document-level migration alias hâlâ var. Tutarsızlık değil ama scope incomplete.
2. **`deps/database.py:28-31` module-global cache anti-pattern.** Singletonish state, test fixture lifecycle'a aykırı. **AGENT.md §"stateless services"** ihlali (deps layer kapsamına girer mi tartışmalı, ama best practice ihlali). Bu suite-flakiness'in kökü.
3. **`tests/unit/state/test_state_manager.py:31,205` `mock.update_plugin_doc = MagicMock()`** kalıntı — production'da method yok ama mock setlenmiş; test artifact temizliği yapılmamış.
4. **`tests/verify_refactor.py:83-85`** docstring `state.save_plugin_data` referansı — bu dosya hâlâ silinmemiş (test mi script mi belirsiz). Ya güncelle ya `.deleted/`'e taşı.

AGENT.md plugin-agnostic core ihlali: **YOK.** `core/` altında plugin name string yok (guard test PASSED).

---

## E) Memory bank / dataset eksikleri

`426e10b` commit'i audit-42'nin tüm önerilerini kapatmış:
- ✓ `08-services.yml:17` — `save_plugin_data` removed comment
- ✓ `06-mongodb.yml` — interface removed block PASS 2/3 kapsayacak şekilde genişletildi
- ✓ `README.yml:78` — `session_36_changes_2026-04-30` block
- ✓ `HANDOFF.md` — Session 36 TL;DR + 8 PASS / 11 commits / round-2 fix detayı

**Eksikler:**
- `memory-bank/activeContext.md` (`Last Updated: April 18, 2026`) — **Session 36 yansıtmıyor.** "FastAPI layer is still not the main proven execution path" hâlâ doğru ama N6 cleanup, plugin-agnostic guard restoration, PyMongoError dispatch genişletme yok.
- `memory-bank/progress.md`, `memory-bank/techContext.md` — kontrol edilmedi (öncelikli olarak `activeContext` zaten 12 gün eski).

---

## F) Bir sonraki PASS önerisi (en kritik 3 madde)

1. **PASS 6.D — module-global cache fix (`deps/database.py:53-54` + `mongodb_lifespan` global reset)** — ~30 dk. 9-fail suite cluster'ı çözer, smoke-test'i daha temiz yapar. Gerçek root-cause fix, AGENT.md "stateless" alignment.
2. **PASS 6.E — memory-bank/activeContext.md sync (Session 36 cleanup yansıt)** — ~15 dk. Yeni session'ların doğru "current state" görmesi için zorunlu.
3. **SMOKE TEST (gerçek Mongo + minimal config)** — bu noktadan sonra `runs/router.py:68-70` summary fallback'lerinin gerekli olup olmadığı, `execution_id` alias kalıntılarının prod'da hit alıp almadığı **veriyle** belirlenir. Spekülatif silmeden önce.

(N6 ekstra hijyen — `execution_id`/`exec_` alias temizliği — smoke-test sonrası, **prod data spot-check ile.**)

---

## G) Smoke-test hazır mı?

**EVET, koşullu.** Şartlar:
- Gerçek Mongo (localhost:27017) açık olacak — bu durumda `app.state.db` valid AsyncDatabase, module-global cache problem değil.
- Test suite flakiness smoke-test path'ini etkilemiyor (suite-only fenomen).
- PASS 6.A canonical API rotası kanıtlı (14/14 yeşil).
- PASS 6.C silmeler dead caller bırakmamış (grep temiz).

**Riskler (smoke-test sırasında izle):**
- Mongo connect başarısız ise endpoint'ler 500 yerine 503 dönmeli; suite test gerçek 503 davranışını single-test modda zaten doğrulamış.
- `jobs/router.py:46-48` `execution_id` alias hiç hit alırsa pre-S36 doc'lar var demektir → migration script gerek.
- `runs/router.py:68-70` summary fallback hit'i benzer sinyal.

**Tavsiye sırası:** memory-bank sync (15 dk) → smoke-test çalıştır → 6.D suite flakiness fix → 6.C ekstra cleanup (alias/summary).

**Önerilen smoke-test yapılandırması:** `MONGODB_URI=mongodb://localhost:27017` + canlı Mongo + 1 küçük dataset (3-5 dosya) + dry_run=true ile run + `/api/v1/runs/{id}/jobs` + `/api/v1/plugins/run/{id}` polling. 5-10 dk sürer.
