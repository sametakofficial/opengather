# Kritik Bulgular — Archiverr 2026-04-30

**Kaynak:** Schema-vs-code reality audit (architecture-reviewer agent, 2026-04-30, 165 field denetlendi)
**Branch:** `dev/communication-refactoring`
**Tetikleyen oturum:** ef30ac79

> Bu dosya tarihsel bir audit kaydıdır. Canonical kaynak `datasets/` shard'ları + `memory-bank/` dir.
> Bu dosyada işaretlenen "phantom features" ve "unverified" maddeler yeni karar verilmedikçe tutulmalıdır.

---

## Audit özeti

- **165 field** denetlendi (14 dataset shard'ı × tüm field'lar)
- **24 SİL** uygulandı (gerçekten ölü, kanıt: kodda 0 reader/writer)
- **17 YENİDEN-YAZ** uygulandı (yanıltıcı doc → gerçek davranışla hizalandı)
- **15 ARAŞTIR** kalıcı olarak `datasets/README.yml#unverified_in_2026-04-30_audit` altında işaretlendi (sahte temizlik yapılmadı)

Audit ham raporu: `.claude/session-artifacts/ef30ac79/agent-architecture-reviewer-*.md`

---

## A) Phantom features — planlanmış ama hiç wire edilmemiş

| # | Özellik | Durum | Karar gerekiyor |
|---|---|---|---|
| A1 | **Reactive plugin model** (`capabilities`, `hooks`, `listens_to`, `reactive`) | Pydantic'te tanımlı, 0 reader. Session 34 (commit `5c24b22`, 2026-04-17) eklendi, hiç çalışmadı. Datasets'ten temizlendi. | İptal mi, wire mi? |
| A2 | **Manifest-level aliases** | `10-aliases.yml#scopes.manifest` doc'taydı; `PluginManifest` schema'sında `aliases` field'ı yok. Datasets'ten kaldırıldı. | Gerçekten lazım mı? |
| A3 | **fs_lock runtime acquire/release** | `core/locking/{manager,validator}.py` validation yapıyor (statik path conflict detection); gerçek lock alımı/serbest bırakması yok. 4 plugin'in manifest'inde `fs_lock: []` boş. | Concurrent FS koruması gerek mi? |
| A4 | **Side-effects audit trail** (`plugin.side_effect` event + `plugin_executions.side_effects` field + `checkpoints.side_effects`) | Sıfır emitter; Mongo trace yazılmıyor. `12-safety.yml`'da yazılmıştı, temizlendi. | Compliance/forensic ihtiyacı var mı? |
| A5 | **Lease + heartbeat + atomic claim** | `11-recovery.yml#out_of_scope` — bilinçli ertelenmiş (Session 35 F1). Slim contract: tek-orchestrator-per-Mongo. | Çoklu orchestrator gerçek senaryo mu? |
| A6 | **Checkpoints + idempotency_key** (output plugin retry) | Aynı — slim contract dışı, schema dokümante ama writer yok. | Output plugin retry gerekli mi? |
| A7 | **PluginStatus / MediaCategory / PluginCategory enum kullanımı** | Enum'lar `sdk/types.py`'de var, kod string literal kullanıyor (`stage_executor.py`, `orchestrator.py`). | Enum disipline edilmeli mi, doc-only mi kalsın? |
| A8 | **Config freeze** (Pydantic frozen / immutable wrapper) | "config readonly" doc, gerçek frozen yok; deepcopy convention. | Gerek var mı? |

---

## B) Yarım/yanıltıcı kalan — gerçek davranış doc'a uymuyor

| # | Konu | Açık |
|---|---|---|
| B1 | `JobState.plugins` (data) vs `JobState.status.plugins` (status) | Dual write, plugin contract etkilemiyor ama bookkeeping çiftleniyor (~300 LOC iş, 8+ plugin client + stage_executor + state_dumper + template_context). |
| B2 | `get_execution_order` flat list | Group bilgisini düşürüyor; `list[list[str]]` dönmesi daha doğru (~20 LOC iş). |
| B3 | API duplicate router | `api/v1/run/` vs `api/v1/runs/` paralel schemas, hangisi canonical belirsiz. |
| B4 | Jinja forbidden features enforcement | `{% include %}` yasaklı yazıyor ama gerçek check yok; render-time error veriyor. |

---

## C) Hiç başlanmamış operasyonel iş

| # | Konu | Efor | Notu |
|---|---|---|---|
| C1 | CI/CD (GitHub Actions + pytest + ruff) | ~30 dk | HANDOFF S33'ten beri açık |
| C2 | Plugin developer docs | ~2-3 saat | activeContext'te listeli |
| C3 | Real API smoke test (gerçek TMDb key) | ~30 dk | HANDOFF S33'ten beri açık |
| C4 | StageExecutor decomposition (PluginInvoker + ParallelGroupExecutor) | ~5 saat | "Stop refactoring, write plugins" mottosu altında ertele |

---

## D) Doğrulanmamış maddeler (`unverified_in_2026-04-30_audit`)

Bunlar "yapılacak iş" değil, "denetlenecek alan". Yeni plugin yazılırken vurursa gerçek durumu öğrenilir.

1. `03-run-state.yml`: `run.status.plugins` ve `run.plugins` shape'lerinin writer'ları net lokalize edilmedi
2. `05-events.yml`: `run.completed` ve `plugin.completed` payload field setleri doğrulanmadı
3. `06-mongodb.yml`: `indexes_additions.plugin_executions` gerçekten oluşturuluyor mu (`pymongo_persistence._create_new_indexes`)
4. `07-plugin-io.yml`: ffprobe / tvdb / omdb / tvmaze / tasker.tasks data shape'leri (per-field spot-check yapılmadı)
5. `09-api-fastapi.yml`: `api/v1/run/` vs `api/v1/runs/` paralel router'ları — hangisi canonical
6. `10-aliases.yml`: `${path:-fallback}` default-syntax parsing'i interpolator'da
7. `02-manifest.yml`: `requires_path_prefix_rule` strict enforcement

---

## E) Pydantic dead code temizliği (datasets'ten silindi, Pydantic'te kaldı)

`src/archiverr/core/plugins/sdk/manifest.py`:

| Satır | Field | Durum |
|---|---|---|
| 27 | `reactive: bool` | Datasets'ten silindi, Pydantic'te kaldı |
| 33 | `capabilities: list[str]` | Aynı |
| 36 | `hooks: list[str]` | Aynı |
| 37 | `listens_to: list[str]` | Aynı |

Plugin manifest.yml'larında `extra=ignore` ile drop oluyor; ama temizken temiz olsun: ~10 dakikalık iş + test.

---

## Yapılan dataset temizliği (2026-04-30)

Tek koherent değişiklik seti — 12 shard düzenlendi, SYSTEM_DATASETS.yml regenerate edildi (34KB).

Detay liste: `datasets/README.yml#dead_schema_removed_2026-04-30`.

---

## Önerilen sıralama (kuşkucu görüş)

**Şimdi yapılması mantıklı:**
1. **C1 — CI/CD** (en küçük lokma, en yüksek değer)
2. **E — Pydantic dead schema temizliği** (10 dk)
3. **B3 — API duplicate router** çözümü (canonical seç, diğerini `.deleted/`)

**Karar gerektiren (vizyon sorusu):**
- A1 (reactive plugins): vision-analysis "killed" diye işaretlemiş gibi. Gerçekten event-driven plugin istiyor musun?
- A4 (side-effects audit): operasyonel ihtiyaç var mı? Şu an PlannedOperation in-process zaten loglanıyor.
- A5/A6 (lease/heartbeat/checkpoints): çoklu orchestrator gerçek bir senaryo mu?

**Kesinlikle erteleme:**
- C4 (StageExecutor decomposition): yeni plugin acısı olmadan dokunma.

---

## Açık sorular (cevapsız bırakma)

1. **Bu projeyi kim kullanacak — sadece sen mi, yoksa başkaları da mı?**
   (CI/CD, docs, side-effects audit gibi maddeler buna bağlı.)
2. **Çoklu orchestrator gerçek bir senaryo mu, yoksa "bir ihtimal" mi?**
   (A5/A6 buna bağlı — lease/heartbeat/checkpoints ya gerek ya değil.)
3. **Reactive plugin'ler / event-driven extensibility gerçekten istiyor musun, yoksa A1'i tamamen iptal mi edelim?**
