# Agent Response | session:ef30ac79 | agent:simplifier | agent_id:a5d8c4027aa67d9a2 | seq:31 | 2026-04-30 02:01:48
# transcript: /home/samet/.claude/projects/-home-samet-Workspace-bedrock-bedrock-Tasarilar-archiverr/ef30ac79-18cf-4997-9bfa-f1382bd1099b/subagents/agent-a5d8c4027aa67d9a2.jsonl

## TL;DR (3 satır)
6 maddelik final plan, ~1.5 saat toplam, smoke-test öncesi 15 dakika kritik düzeltme. Plan; subprocess router'ı, plugin_docs'u, Beanie/SSE/schema_version'u ve dataset'e phantom collection eklemeyi YAPMIYOR. Sadece observable bug'lar + zero-consumer dead code'a odaklanıyor.

## ÇÜRÜTÜLEN ÖNERİLER (sıkı YAGNI lensi)

| # | Öneri | Kim | Neden YAGNI'yi geçemedi | Verdict |
|---|---|---|---|---|
| R1 | `schema_version: int` field ekle (lazy migrate) | researcher D4 | "İlk shape değişiminde işe yarar" = klasik speculative extension. 0 consumer, 0 migration bugün. AGENT.md §"no speculative extension points" | ELE |
| R2 | SSE / `EventSourceResponse` planı sketch | researcher D9 | "UI olunca lazım" — UI yok. AGENT.md §"complexity earned by current requirement" | ELE |
| R3 | Repository pattern + Beanie ODM tartışması | researcher B | "Defer" diyor zaten — zaten yapılmıyor, plana yazmak gürültü | ELE (no-op) |
| R4 | Audit `events` collection capped/TTL ipucu | researcher D | Zaten "defer" işaretli, kod değişikliği değil | ELE (no-op) |
| R5 | `interface.py`'a "do not re-add per-result CRUD" yorum satırı | researcher E5 | Defansif yorum, kod davranışını değiştirmez. Three-strikes değil | ELE |
| R6 | M3: `plugin_docs`/`diagnostics`'i `06-mongodb.yml` schema-of-truth'a ekle | önceki audit | Reviewer YÖN-TERS dedi: yazıcısı olmayan koleksiyonu schema'ya yazmak phantom feature yaratır | ELE |
| R7 | N6: Legacy fallback'leri (`executions`/`matches`/`plugin_results`) topluca temizle | reviewer N6 | 1 saatlik iş + test riski + "veri var mı?" karar gerektirir. Observable bug değil, tech-debt | ERTELE |
| R8 | N8: `/run/` vs `/runs/` rolünü `09-api-fastapi.yml`'a yaz | reviewer N8 | Pure dataset edit, davranış değişmez; düşük öncelik | ERTELE |
| R9 | "Recovery slim contract" yorumu eklemek | researcher D10 | Zaten dataset'te var, no-op | ELE |
| R10 | per_run plugins'i `plugin_executions`'a yaz (E1/K6) | researcher | Recovery zaten "slim" contract'ta defer; yeni write path = yeni complexity | ERTELE (kullanıcı kararı) |
| R11 | `DiagnosticsLogger` wire-or-delete | researcher | Reviewer "unwired-on-purpose, schema'ya koyma" dedi. Kullanmaktan vazgeçildi → bırak | ELE |
| R12 | "Triple copy → 2-tier" terminolojisi | researcher | Verdict aynı (drop `plugin_docs`); framing değişikliği plan maddesi değil | ELE (zaten F3'te) |

## FINAL PLAN — sadece şart olanlar (sıralı)

| # | WHAT | WHY (AGENT.md kuralı + observable bug) | EFFORT | RISK |
|---|---|---|---|---|
| **F1** | `core/orchestrator.py:382-418` — `on_job_completed` ve `on_plugin_completed` event handler'larını sil | §5 Safety: REAL BUG. Her `job.completed`'da `save_job` filter shape mismatch (`{"id": ""}`) garbage doc upsert. Ana yol (`state/job_manager.py:99,131`) zaten yazıyor | 5 dk | düşük |
| **F2** | `pymongo_persistence.py:155-176` — ölü `runs.started_at` ve `(status, started_at)` indekslerini sil; `_create_indexes` + `_create_new_indexes` tek metoda birleştir | §"no speculative extension points": `RunState.to_dict()` top-level `started_at` yazmıyor → index hiç doc'a vurmaz, pure cost | 10 dk | düşük |
| **F3** | `save_plugin_result` / `update_plugin_result` / `save_plugin_data` (manager + plugin_data_manager + persistence_delegate'in `hasattr` guard'ı) sil; ilgili testleri `update_plugin` rotasına çevir | §4 Plugin Contracts: "Avoid signature introspection, dict fallbacks". Production caller=0; `hasattr` guard interface'te abstract olmayan bir method'u silent-drop ediyor — exact anti-pattern | 30-45 dk | orta (test güncellemesi) |
| **F4** | `plugin_docs` writer/reader chain'i sil: `pymongo_persistence.update_plugin_doc/get_plugin_doc` + `plugin_data_manager.py:106,131` çağrıları. Mongo collection için `mkdir -p .deleted && mv` migration script | §"YAGNI > SOLID": API reader=0, plugin reader=0, sadece persistence-internal dead write amplification. `jobs.plugins` (template ctx) + `plugins` collection (cross-job query) zaten iki canlı concern | 20 dk | orta (mv migration kullanıcı onayı ister) |
| **F5** | `datasets/11-recovery.yml:26` — `plugin_executions.started_at` → `created_at` (kodla hizala) | §"contract_freeze: code is the bug, not the dataset" — burada ters: slim contract "today's truth"'u tarif eder, kod canlı yazıyor (`pymongo_persistence.py:376`), dataset henüz dondurulmamış | 2 dk | yok |
| **F6** | `datasets/06-mongodb.yml`'a kısa "known unwired" listesi: `diagnostics` (DiagnosticsLogger hiç instantiate edilmiyor, `system/router.py:180` boş okuyor). `plugin_docs` F4 ile gittiği için yazma | §"contract_freeze_rules": misleading dataset = phantom feature. Bir cümlelik açıklama yeter, schema-of-truth'a koyma | 5 dk | yok |

**Toplam: ~1 saat 15 dk.**

## SMOKE-TEST ÖNCESİ MUTLAK MİNİMUM

**F1, F2, F5** (toplam 17 dk).

- **F1** olmadan smoke-test her job.completed'da garbage doc yaratır → DB state misleading.
- **F2** olmadan smoke-test'in oluşturduğu indekslerle prod arasında drift kalır.
- **F5** olmadan dataset-vs-code freeze contract'ı ihlal kalır; hostile reviewer tekrar tekrar bayraklayacak.

**F3, F4, F6** smoke-test sonrasına ertelenebilir (gözlemlenebilir bug yok, dead code temizliği).

## ERTELENEN / KARAR İSTEYEN

- **F4 (`plugin_docs` drop):** Mongo collection silme = irreversible. No-delete policy gereği `.deleted/` workflow + kullanıcı onayı şart. Code-side silme efor'a dahil; collection migration ayrı bir adım.
- **R7 (legacy fallback temizliği):** Smoke-test sonrasına. "Eski veri var mı, prod'a basıldı mı, basit migration mi yoksa hard-cut mi?" — kullanıcı kararı.
- **R10 (per_run plugins → `plugin_executions`):** Recovery contract şu an "slim". Yeni write path açmak yeni invariant doğurur. Yalnızca recovery genişletme kararı verilirse.
- **N8 dataset edit, R2 SSE sketch:** Davranış değişikliği değil; gerçek UI consumer çıkana kadar yazılı kontrat değişmez.

## KULLANICIYA NET 3 SORU

1. **`plugin_docs` koleksiyonunu silmeye onay var mı?** (Code-side temiz, ama Mongo'daki mevcut docs için `.deleted/` migration gerekir; geri dönüş = git revert + collection restore.)
2. **Legacy fallback'ler (`executions`/`matches`/`plugin_results`) prod DB'lerinde gerçekten veri taşıyor mu?** (Cevap "boş" ise hard-cut; "veri var" ise ayrı migration session — şu an plana dahil değil.)
3. **`/api/v1/run/` (subprocess) endpoint'ini kanonik kabul edip korumayı mı, yoksa `/runs/`'a tek-yol konsolidasyon planı yapmayı mı tercih ediyorsun?** (İki ayrı execution model olduğu doğrulandı; bugün kod değişikliği gereksiz, ama uzun vadede bir karar.)
