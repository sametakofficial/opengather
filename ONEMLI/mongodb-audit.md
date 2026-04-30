# MongoDB Reality+Gap Audit — Archiverr 2026-04-30

**Branch:** `dev/communication-refactoring` · **Audit anı son commit:** `c4e3808`
**Tetikleyen oturum:** ef30ac79
**Audit türü:** Architecture-reviewer agent, comprehensive collection-by-collection + datasets-vs-code

> Kanonik kaynak `datasets/` ve `pymongo_persistence.py`. Bu dosya tarihsel kayıt + plan.

> **GÜNCELLEME 2026-04-30 (Session 36):** Bu auditin önerileri parallel research/review/simplifier
> filtresinden geçirildi. Uygulanan plan **F1-F6 + Y1-Y3 + N7-N8** oldu (5 PASS / 6 commit).
> İlk audit'in 15 maddesinden 6'sı uygulandı, 6'sı YAGNI/AGENT.md filtresi ile elendi, 3'ü
> kullanıcı onayına ertelendi. Düzeltilen/geri alınan kararlar:
>
> - **B3 (`/run/` vs `/runs/` duplicate router) ÇÜRÜTÜLDÜ:** İki ayrı execution model.
> - **M3 (datasets'e plugin_docs/diagnostics ekle) YÖN TERS:** known_unwired olarak işaretlendi.
> - **M5 (started_at vs created_at) YÖN TERS:** Schema kodu izledi (slim contract = today's truth).
> - **"Triple-copy plugin storage" framing'i ÇÜRÜTÜLDÜ:** 2 canlı concern + 1 ölü surface;
>   sadece `plugin_docs` silindi (`plugins` koleksiyonu = MongoDB Extended Reference pattern).
>
> Detay: `HANDOFF.md` (session 36) ve `.claude/session-artifacts/ef30ac79/agent-*-{26,29,31}.md`.

---

## Özet Sayım

- **Aktif collection:** 6 (`runs`, `jobs`, `plugins`, `plugin_docs`, `plugin_executions`, `diagnostics` [bağlanmamış])
- **Legacy hayalet collection:** 3 (`executions`, `matches`, `plugin_results` — yazıcı 0, API hâlâ okuyor)
- **Eksikler (E1-E7):** 7 madde
- **Fazlalıklar (F1-F8):** 8 madde
- **Kötülükler (K1-K10):** 10 madde
- **Plan: P1=5, P2=7, P3=3 madde**

## En kritik 3 bulgu

1. **K3 / M1 (CRITICAL BUG):** `orchestrator.py:382-418` event handler `save_job`'a `{job_id, run_id, stage, status}` shape gönderiyor — `pymongo_persistence.py:206` filter `{"id": ""}` (boş string) ile sorguluyor → **`upsert=True` ile `id=""` garbage document yaratır**. Mongo bağlıysa smoke test bunu doğrudan patlatır.

2. **F2 / M4:** `save_plugin_result` **ölü zincir**. `persistence_delegate.py:171` `hasattr` guard'ı ile sessizce `False` dönüyor; PyMongo'da implementasyon yok; `update_plugin_result` runtime caller sayısı 0. Yeni dev "var sandığında" yanlış varsayımla kod yazar.

3. **F1 / K1 / M6:** `plugin_docs` ile `plugins` collection rolü çakışıyor — **plugin verisi 3 yerde** (`jobs.plugins` embedded + `plugins` collection + `plugin_docs._id={run|job}_id`). API `plugin_docs`'u kullanmıyor; tüketicisi yok.

---

## Kısım 1 — Collection-by-collection

### 1.1 `runs`
- **Yazıcılar:** `pymongo_persistence.py:178-200 save_run` ← `state/job_manager.py:99,131`, `state/manager.py:146,164`, `state/plugin_data_manager.py:107`, `infrastructure/repositories/run_repository.py:36`
- **Okuyucular:** `pymongo_persistence.py:274 get_run`, `api/v1/runs/router.py:118,156,159,207,249`, `run_repository.py:48`
- **Index:** `_create_indexes`: `started_at`, `(status, started_at)` ← **ÖLÜ** (top-level değil); `_create_new_indexes`: `id` unique, `created_at`, `status.state`
- **Shape:** `RunState.to_dict()` → `id, status{...,plugins,...}, config, plugins, created_at, updated_at`
- **`06-mongodb.yml` uyum:** ⚠️ `persistence_mode` field'ı schema'da var ama yazıcı yok (hayalî)

### 1.2 `jobs`
- **Yazıcılar:** `pymongo_persistence.py:202-224 save_job` ← `job_manager.py:98,131`, `repositories/job_repository.py:36`, **+ `orchestrator.py:392` event handler (BOZUK SHAPE — bkz K3)**
- **Okuyucular:** `pymongo_persistence.py:278,283`, `api/v1/jobs/router.py:120,157,189,191,219,229`, `runs/router.py:319`
- **Index:** `_create_indexes`: `run_id`. `_create_new_indexes`: `(run_id,index)` unique, `id` unique, `run_id`. `:320-323` migration: `run_id_1_index_1` drop
- **Shape:** `JobState.to_dict()` → `id, index, run_id, input{value,data}, output{values,data}, status{state,success,plugins,started_at,finished_at,duration_ms}, plugins`
- **`06-mongodb.yml` uyum:** ⚠️ Ana yolla uyumlu; event-handler 2. yol shape'i bozuk

### 1.3 `plugins`
- **Yazıcılar:** `pymongo_persistence.py:226-249 save_plugin` ← `plugin_data_manager.py:145,228`, `repositories/plugin_result_repository.py:56,89`, **+ `orchestrator.py:408` event handler (farklı shape)**
- **Okuyucular:** `pymongo_persistence.py:287,292`, `api/v1/jobs/router.py:219,271`, `api/v1/plugins/router.py:93,131`, `plugin_result_repository.py:106`
- **Index:** `(job_id, plugin_name)` unique, `run_id`, `job_id`
- **Shape:** writer-bağımlı: `{job_id, plugin_name, data, run_id, job_index}` veya `+stage,+status` (event handler) → **K4 inconsistency**
- **`06-mongodb.yml` uyum:** ⚠️ `status` block schema'da var, ana yazıcı yazmıyor (sadece event handler — duplicate write)

### 1.4 `plugin_docs`
- **Yazıcılar:** `pymongo_persistence.py:251-266 update_plugin_doc` ← `plugin_data_manager.py:106` (run-level), `:131` (job-level)
- **Okuyucular:** `pymongo_persistence.py:268 get_plugin_doc`. **API'den çağrılmıyor** (grep 0). Sadece persistence-içi.
- **Index:** `created_at`, `updated_at`. `_id` zaten unique.
- **Shape:** `{_id: target_id, <plugin_name>: {data...}, created_at, updated_at}` — plugin adı top-level field
- **`06-mongodb.yml` uyum:** ❌ **HİÇ LİSTELENMEMİŞ** (yeni divergence)

### 1.5 `plugin_executions`
- **Yazıcılar:** `pymongo_persistence.py:347-389 save_plugin_execution` ← `stage_executor.py:402` (state transitions), `orchestrator.py:494` (recovery → `crashed`)
- **Okuyucular:** `pymongo_persistence.py:391-400 get_unfinished_plugin_executions` ← `orchestrator.py:476`. **API'den okunmuyor**
- **Index:** `(job_id, plugin_name, attempt)` unique, `run_id`, `state`, `(run_id, state)`
- **Shape:** `{run_id, job_id, plugin_name, state, attempt, updated_at, created_at, [error], [finished_at]}`
- **`06-mongodb.yml` + `11-recovery.yml` uyum:** ⚠️ `started_at` schema vs `created_at` kod (isim sapması K5); `duration_ms` yazılmıyor

### 1.6 `diagnostics` (KEŞFEDİLEN, dataset'te yok)
- **Yazıcılar:** `infrastructure/database/diagnostics.py:90-122 DiagnosticsLogger.log`. **AMA bağlanmamış**: `DiagnosticsLogger` instance'ını wire eden kod yok; `Debugger.set_diagnostics_logger` (utils/debug.py:72) hiç çağrılmıyor.
- **Okuyucular:** `api/v1/system/router.py:180` — yazıcı bağlı olmadığı için collection boş.
- **`06-mongodb.yml` uyum:** ❌ Hiç yok. Yeni divergence.

### 1.7 Legacy hayalet: `executions`, `matches`, `plugin_results`
API fallback olarak okuyor (`api/v1/runs/router.py:209,328`, `api/v1/jobs/router.py:165,224,278`, `api/v1/plugins/router.py:136`, `api/deps/common.py:62,72`). Yazıcı 0. Migration debt.

---

## Kısım 2 — Mongo dışı veri yapılarının yansıması

### 2.1 `03-run-state.yml`
- `run.status.plugins` (RunStatus.plugins, models.py:93) → **WRITER YOK**, runtime sıfır write. Mongo'ya boş `{}` yazılıyor (E3)
- `run.plugins` → `runs.plugins` (`save_run`) + `plugin_docs._id=run_id` (dual-write)
- `job.plugins` → `jobs.plugins` (embedded) + `plugins` collection + `plugin_docs._id=job_id` **(üçlü kopya, K1)**
- `job.status.plugins` → `jobs.status.plugins` (writer: `stage_executor.py:476/660/665/671`)
- `plugin_result` (`03-run-state.yml:57-65`) → **MONGO'YA HİÇ YAZILMIYOR** (`save_plugin_result` PyMongo'da yok, `hasattr` ile sessiz drop)

### 2.2 `05-events.yml`
- `job.completed` event → `orchestrator.py:417,385-397` → `save_job` BOZUK SHAPE (K3)
- `plugin.completed` event → `orchestrator.py:418,399-415` → `save_plugin` (duplicate write, sonuncu kazanır)
- Diğer 14 event: **Mongo'ya yazılmıyor** — audit-trail yok

### 2.3 `07-plugin-io.yml`
Her plugin update'i: `services.update_plugin` → `_update_job_plugin` → **HEM** `update_plugin_doc(job_id, plugin_name, data)` `plugin_docs` **HEM** `save_plugin(...)` `plugins`. Çift yazma her plugin output'unda.

### 2.4 `08-services.yml`
- `services.state.save_plugin_data` → `manager.py:246` → `plugin_data_manager.py:198-228` → tek `save_plugin`. **Hiçbir plugin runtime caller'ı yok** → ölü API (F4)
- `update_plugin` proxy: aktif kullanılan; her çağrıda dual-write tetikler

### 2.5 `11-recovery.yml#plugin_executions` ↔ kod

| Schema field | Kod yazıyor mu? |
|---|---|
| `started_at` | ❌ (yerine `created_at`) — **K5 isim sapması** |
| `finished_at` | Sadece terminal state'te |
| `duration_ms` | ❌ |
| `error` | Şartlı |
| `claimed_at`, `lease_expires_at`, `idempotency_key`, `output_fingerprint` | ❌ (slim contract — doğru) |

### 2.6 `12-safety.yml#audit`
`PlannedOperation` 27 hit `safety.py` içinde — caller plugin'ler dönüş değerini **kullanmıyor**. Mongo trace yok (12-safety zaten "in-process only" diyor). E5 borç.

---

## Kısım 3 — Eksik / Fazla / Kötü

### EKSİK
- **E1** — Per-run plugin sonuçları `plugin_executions`'a yazılmıyor (recovery scan görmez)
- **E2** — Stage transition timestamps Mongo'da yok
- **E3** — `run.status.plugins` writer yok (run-level execution durumu kayıp)
- **E4** — Aggregated `failed_at`/`error_message` yok (operatör "neden başarısız" göremez)
- **E5** — `PlannedOperation` log'u yok (FS audit trail in-process)
- **E6** — `diagnostics` collection bağlı değil
- **E7** — `run.config.tasks` (06-mongodb:18) — `RunState.config.tasks` _unverified_

### FAZLA
- **F1** — `plugin_docs` ile `plugins` collection rol çakışması
- **F2** — `save_plugin_result` ölü API (sessiz drop)
- **F3** — `update_plugin_result` ölü (sıfır runtime caller)
- **F4** — `save_plugin_data` state API ölü (sıfır plugin caller)
- **F5** — `orchestrator.py:382-418` event handler'ları (partial overwrite + bug)
- **F6** — Legacy collections (`executions`, `matches`, `plugin_results`) okumaları
- **F7** — `NullPersistence` `save_plugin_execution`/`get_unfinished_*` override etmiyor (minor)
- **F8** — `_create_indexes`'teki ölü index'ler (`runs.started_at` top-level değil)

### KÖTÜ
- **K1** — Üçlü kopya plugin verisi
- **K2** — `plugin_docs._id` heterojenliği (run_id VEYA job_id)
- **K3** — `save_job` filter bug: handler `job_id` gönderir, sorgu `id` filtreler → garbage doc upsert
- **K4** — `plugins` collection shape writer-bağımlı (`stage`/`status` opsiyonel)
- **K5** — `plugin_executions.created_at` ↔ schema `started_at` isim sapması
- **K6** — Per_run plugin'ler `plugin_executions`'a yazmıyor
- **K7** — `_create_indexes` + `_create_new_indexes` ikiye bölünmüş, ölü index'ler temizlenmemiş
- **K8** — `PluginResultRepository` external caller 0 — ölü repo
- **K9** — `RunRepository.get_recent/get_failed/get_all` stub döndürüyor; API repo bypass ediyor
- **K10** — `save_plugin_result` interface'te yok ama delegate çağırıyor (type-safe değil)

---

## Kısım 4 — Plan

### P1 — Smoke test'e çıkmadan zorunlu (~45-90 dk)

| # | Eylem | Why | Files |
|---|---|---|---|
| **M1** | `orchestrator.py:382-418` event handler'larını sil veya doğru shape | K3 kritik bug — garbage doc upsert | `core/orchestrator.py:382-418` |
| **M2** | `_create_indexes`'teki ölü index'leri temizle, `_create_new_indexes` ile birleştir | F8/K7 — atıl index'ler | `pymongo_persistence.py:155-176` |
| **M3** | `06-mongodb.yml`'e `plugin_docs` + `diagnostics` ekle | Yeni divergence | `datasets/06-mongodb.yml` |
| **M4** | Ölü API'leri kaldır (`save_plugin_result`, `update_plugin_result`, `save_plugin_data`) | F2/F3/F4/K10 — sessiz drop, type-safe değil | `state/persistence_delegate.py:152-182`, `state/plugin_data_manager.py:198-264`, `state/manager.py:246-264` |
| **M5** | `plugin_executions` schema/kod isim sapmasını gider (`started_at` vs `created_at`) | K5 | `pymongo_persistence.py:376` veya `datasets/11-recovery.yml:26` |

### P2 — Kalite/tutarlılık (~3-5 saat)

| # | Eylem | Why |
|---|---|---|
| **M6** | `plugin_docs` vs `plugins` rolünü resmî olarak ayır veya birleştir | F1/K1/K2 |
| **M7** | Per-run plugin'ler için `_save_exec_state` yolunu aç | E1/K6 |
| **M8** | `run.status.plugins` writer ekle veya field'ı kaldır | E3/F8 |
| **M9** | Legacy collection okuma fallback'lerini API'den temizle | F6 |
| **M10** | `RunRepository` stub'larını implement et veya kaldır | K9 |
| **M11** | `save_plugin` shape standardize et | K4 |
| **M12** | `DiagnosticsLogger`'ı bağla veya tamamen sil | E6 |

### P3 — Karar gerek (vizyon sorusu)

| # | Eylem | Soru |
|---|---|---|
| **M13** | Run-level audit/event log Mongo'ya yazılsın mı? | Operator-CLI mi, multi-tenant servis mi? |
| **M14** | `plugins` collection keep mi drop mu? | `plugin_docs` ile rol çakışması |
| **M15** | Recovery model genişletilsin mi? | Çoklu orchestrator senaryosu gerçek mi? |

---

## Kısım 5 — `plugin_docs` vs `plugins` niyeti

- **`plugins`**: `(job_id, plugin_name)` unique, per-plugin per-job satır. Tasarım niyeti (interface.py:54-65 docstring): "stored separately for memory management; hot/cold tiering for large datasets" — runs/jobs doc'larını şişirmemek için.
- **`plugin_docs`**: `_id = target_id` (run_id VEYA job_id), per target agregat doc, plugin adı top-level field. Tasarım niyeti: "tek round-trip per-target plugin payload snapshot". **API kullanmıyor** (grep 0).

**Pratik öneri (M14):** **Seçenek A** = `plugin_docs` drop. API zaten `plugins` okuyor, üçlü kopya ikiliye iner, write maliyeti yarıya düşer, YAGNI.

İki collection'ın aynı update yolundan ardışık iki çağrıyla yazılması (`plugin_data_manager.py:131,145`) yazarın "ikisini de güncel tut, hangisi tüketilecek bilmiyorum" düşüncesinin göstergesi.
