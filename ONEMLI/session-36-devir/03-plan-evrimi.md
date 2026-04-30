# Plan Evrimi — 3 paralel agent + simplifier ile karar süreci

Bu dosya, Session 36'da MongoDB + FastAPI temizlik planının **nasıl şekillendiğini**
belgeler. Tek bir AI'ın "şunlar dead" demesi yerine, 3 farklı bakış açısının
çakıştığı yerlerin filtrelenmesi ile sağlam plana ulaşıldı.

---

## Aşama 0: İlk audit (orchestrator yapımı)

`ONEMLI/mongodb-audit.md` (`827e91a` commit'inde annotate edildi) — ilk audit
**15 maddelik plan** önerdi:
- M1: orchestrator.py:382-418 event handler garbage upsert silme
- M2: dead indexes silme
- M3: `plugin_docs` + `diagnostics` datasets'e ekleme
- M4: dead `save_plugin_*` API silme
- M5: `started_at` vs `created_at` field rename
- P1 (5), P2 (7), P3 (3) madde

Kullanıcı tepkisi:
> "subagentlere danış... duplicate'ler index hızı için olabilir... direkt silmeye
> karar vermek göt iter generic bir analiz değil"

Bu yüzden 3 paralel doğrulama başlatıldı.

---

## Aşama 1: Paralel doğrulama (3 agent)

### Agent A: `architecture-researcher` (industry kanıtı)

**Çıktı:** `audit-artifacts/01-researcher-industry-evidence.md`

Endüstri repolarından kanıt topladı:
- **workflow-core** (danielgerlag, .NET): MongoDB persistence pattern
- **Temporal**: event-sourced append-only log
- **Kestra**: 3-layer architecture (queue/repo/storage)
- **MongoDB official**: 6 Rules of Thumb, Embedding vs References, Extended Reference Pattern, Schema Versioning

**Önemli verdict'ler (kanıtla):**
- M1 (event handler): DELETE — kanıt: filter mismatch real bug
- M4 (save_plugin_result chain): DELETE 3/3 — AGENT.md §4 anti-pattern
- "Triple-copy plugin storage": **SPLIT VERDICT** — `jobs.plugins` embedded + `plugins` collection 2-tier industry pattern, `plugin_docs` 0 reader
- B3 ("/run/" vs "/runs/" duplicate): "/runs/ canonical seç" (sonradan reviewer çürüttü)
- Beanie/SSE/schema_version → AGENT.md "no speculative extension points" filtresinde elendi

### Agent B: `architecture-reviewer` (kod hostile re-audit)

**Çıktı:** `audit-artifacts/02-reviewer-hostile-code-audit.md`

Kodu derinden tarayıp **researcher'ın görmediği şeyleri** buldu:

**Önemli düzeltmeler:**
- **B3 ÇÜRÜTÜLDÜ**: `/run/` (subprocess CLI proxy) ve `/runs/` (RESTful CRUD) **iki ayrı execution model**, duplicate değil. Kanıt: `api/v1/run/router.py:84-97` subprocess execution + `api/v1/runs/router.py:200-204` `run_in_threadpool(_run_orchestrator)`.
- **M3 YÖN TERS**: `plugin_docs` + `diagnostics` schema-of-truth'a ekleme phantom yaratır. Bunun yerine `known_unwired` listesi.
- **M5 YÖN TERS**: Schema kodu izlemeli (slim contract = today's truth), aksi değil.
- **"Triple-copy" framing yanlış**: 2 canlı concern + 1 ölü surface (`plugins` collection LIVE API consumer var: `api/v1/plugins/router.py:93,131`).

**Yeni bulgular (Y1-Y6):**
- Y1: `/run/` subprocess silent failure — stderr 500-byte truncate (AGENT.md §5 ihlali)
- Y2: `api/main.py:62-63` misleading docstring (executions/matches reklamı)
- Y3: `system/router.py` stats legacy collection sayıyor
- Y4: `runs/router.py:286` infinite-recursion riski (sonradan dismiss)
- Y5: SSE eksik (defer)
- Y6: `tasker.tasks` phantom (sonradan reviewer kendi düzeltti: collection değil, plugin output verisi)

### Agent C: `simplifier` (YAGNI filter)

**Çıktı:** `audit-artifacts/03-simplifier-yagni-filter.md`

Researcher'ın 10 + reviewer'ın 8 + ilk audit'in 15 = 33 öneriyi **6 madde / ~1.5 saate** indirgedi.

Çürütülen öneriler (12 madde):
- `schema_version` field (speculative extension)
- SSE sketch (no UI consumer)
- Beanie ODM (premature)
- M3 datasets ekleme (phantom yaratır)
- N6 büyük temizlik (1 saat + risk)
- Defansif yorum satırları (no-op)
- Yorumlama framework değişiklikleri (verdict aynı, framing değişmesi plan maddesi değil)

**Simplifier'ın final 6 maddesi:** F1, F2, F3, F4, F5, F6 (PASS 1-4 olarak uygulandı).

> Kullanıcı bu noktada simplifier'ı eleştirdi: "bu simplifier biraz mallık yapmış
> olabilir bence sen onu umursama öncekilerden devam et... fastapi ve mongodb
> güncellemeye başla hiç durma"

Bu yüzden simplifier'ın "smoke-test öncesi mutlak minimum F1+F2+F5" kısıtlaması
genişletildi → tüm F1-F6 + Y1-Y6 + N7-N8 yapıldı.

---

## Aşama 2: Plan netleştirme (kullanıcı kararı)

Sıralama:
1. **PASS 1** (smoke-test minimum, ~17 dk): F1 + F2 + F5
2. **PASS 2** (~45 dk): F3 dead chain
3. **PASS 3** (~20 dk): F4 plugin_docs
4. **PASS 4** (~1 saat): Y1 + Y3 + N7 + N8
5. **PASS 5**: Y2 + Y6
6. **PASS 6.A** (round-2 audit önerisi): test_plugin_agnostic rewire
7. **PASS 6.B** (round-2): PyMongoError catch genişletme
8. **PASS 6.C** (round-2): N6 legacy fallback temizliği
9. **PASS 6.D** (kendi tespitim): orphaned system_router include
10. **PASS 6.E** (round-2 root cause fix): cache-after-ping

---

## Aşama 3: 1. Round Audit (post-PASS 5)

**Çıktı:** `audit-artifacts/04-reviewer-round1-post-pass5.md`

5 PASS commit'inin tam doğrulaması. Bulgular:
- **5/5 ana iddia doğrulandı** (M1, M2, M4 tam; "triple-copy" partial; B3 framing'i)
- **Kritik regresyon**: PASS 2'de `test_plugin_agnostic.py:128,136` rewire edilmemiş, 12 test SKIPPED
- **N6 yarım**: stats endpoint düzeltildi, ana router'lardaki defansif fallback'ler hala duruyor
- **Y6 yanlış kategori**: `tasker.tasks` collection değil

Audit önerisi: PASS 6.A → 6.C → smoke test → 6.D (suite flakiness)

---

## Aşama 4: 2. Round Audit (post-PASS 6.E)

**Çıktı:** `audit-artifacts/05-reviewer-round2-post-pass6e.md`

PASS 6.A/B/C'nin doğrulaması. Bulgular:
- **PASS 6.A ✅**: 14/14 yeşil, plugin-agnostic guard restored, AGENT.md ZERO TOLERANCE invariant runtime'da çalışıyor
- **PASS 6.B ⚠️ kısmi**: `PyMongoError` dispatch doğru AMA gerçek root cause `deps/database.py:53-54 _async_db cache` race condition. Suite flakiness suite-only (smoke-test'i etkilemez).
- **PASS 6.C ✅**: Silmeler kanıtlı temiz (0 dead caller), `delete_run` cascade `plugin_executions` ekleme doğru
- **Yeni bulgu Y3 (yeni)**: `runs/router.py:46-48` ve `jobs/router.py` `execution_id` legacy alias kalıntıları (smoke-test sonrası karar)

Audit önerisi: **PASS 6.E** (cache-after-ping fix) → memory-bank sync → smoke test.

PASS 6.E uygulandı, **9-fail suite cluster komple çözüldü** (510→527 pass).

---

## Karar Süreci Özeti — kim ne dedi, kim doğru çıktı?

| Konu | İlk audit | Researcher | Reviewer | Final karar |
|---|---|---|---|---|
| M1 event handler | DELETE | DELETE ✓ | DELETE ✓ | DELETE (PASS 1) |
| M2 dead indexes | DELETE | DELETE ✓ | DELETE ✓ | DELETE (PASS 1) |
| M3 datasets ekleme | ADD | ima ediyor | **YÖN TERS** | known_unwired (PASS 4) |
| M4 dead API | DELETE | DELETE 3/3 | DELETE 3/3 | DELETE (PASS 2) |
| M5 rename yön | code→schema | code→schema | **schema→code** | schema→code (PASS 1) |
| B3 /run/ vs /runs/ | DUPLICATE | onayladı | **ÇÜRÜTTÜ** | iki ayrı model (PASS 4) |
| 3-tier plugin | DROP üçünü | 2-tier doğru | **2 canlı + 1 ölü** | sadece plugin_docs drop (PASS 3) |
| N6 legacy fallback | yok | yok | flag etti | DELETE (PASS 6.C) |
| Y1-Y6 | yok | yok | reviewer buldu | Y1+Y2+Y3+Y6 fix, Y4+Y5 dismiss/defer (PASS 4-5) |
| 9-fail flakiness | yok | yok | reviewer buldu (audit 2) | cache-after-ping fix (PASS 6.E) |

**Reviewer en değerli agent oldu** — kodu file:line ile kanıtladığı için researcher'ın
endüstri-only kararlarının üstüne geçti. Researcher industry context için kritik
ama "X repo Y pattern kullanıyor" → "Archiverr da kullanmalı" çıkarımı zayıf;
reviewer'ın "kod şu an N yapıyor" netliği üstüne karar verildi.

---

## AGENT.md filtresi — neyi reddettik?

Bu bölüm önemli çünkü yeni AI da aynı filtreyi uygulamalı.

**Reddedildi (AGENT.md "no speculative extension points"):**
- `schema_version: int` field eklemek (MongoDB official pattern olsa da, 0 consumer)
- SSE/WebSocket implementation (no UI consumer)
- Beanie ODM migration (manifest+result Pydantic v2 zaten yeterli)
- Audit `events` capped collection (slim contract dışı)
- Multi-orchestrator lease/heartbeat (slim contract dışı)
- Plugin_executions checkpoints field genişletme (future-work, slim)
- DiagnosticsLogger wire (`api/v1/system/router.py:180` empty read; karar: drop OR wire)
- "do not re-add per-result CRUD" defansif yorum (no-op)

**Kabul edildi (mevcut bug fix veya yazılı sözleşmeyi koruma):**
- F1 garbage upsert (real bug)
- F2 dead indexes (pure cost)
- F3 dead API chain (anti-pattern)
- F4 plugin_docs (zero readers, write amplification)
- F5 schema-code align (today's truth)
- F6 known_unwired note (avoid phantom)
- Y1 stderr logger (no silent failures)
- Y2 misleading docstring (avoid phantom)
- Y3 canonical stats (consistency)
- Y6 phantom URL fields (no speculative)
- N6 legacy fallback (defensive try/catch around impossible paths)
- 6.D system_router include (orphaned router = dead infrastructure)
- 6.E cache-after-ping (race condition real bug)

---

**Sonraki:** `04-uygulanan-isler.md` — 14 commit'in detayı.
