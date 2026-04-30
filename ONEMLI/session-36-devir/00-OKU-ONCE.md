# Session 36 Devir Paketi — Yeni AI İçin Başlangıç Kılavuzu

**Tarih:** 2026-04-30
**Branch:** `dev/communication-refactoring`
**Son commit:** `e725fdb` (HEAD)
**Test durumu:** 527 passed, 0 failed, 15 skipped (intentional)

> Bu dosya yeni AI'a iletilmek üzere hazırlandı. **Önce bu dosyayı oku**, sonra
> diğer dosyalara dal. Klasördeki dosya isimleri sıralı (00→07): sırayla oku.

---

## 1. Sen Kimsin / Ben Kimim

Bu klasör Archiverr projesinin Session 36 (2026-04-30) çalışmasının **tam devir paketi**.
Önceki AI (Claude Opus 4.7 1M) kullanıcıyla 8+ saatlik bir oturumda projenin
MongoDB ve FastAPI katmanlarını derinlemesine temizledi, plan-yap-doğrula
döngüsüyle ilerledi.

**Sen** (yeni AI) buradan devam edeceksin. Yapacağın iş:
1. Bu paketi sırayla oku (00→07).
2. Kullanıcıya şu anki state'i 5 satırda raporla.
3. Kullanıcının bir sonraki talebine göre devam et.

**Kullanıcı** (Türk, Samet) şu çalışma kurallarını uyguluyor:
- "Hiç durma" / commit-driven (her PASS git commit ile atılır, geri dönüş için)
- "Subagentlere danış" — her büyük karar 2+ agent (researcher + reviewer) ile doğrulanır
- "Körü körüne silme" — her dead code iddiası `file:line` + grep + audit ile kanıtlanır
- "Audit sonuçlarını sentezleyip yazma" — her agent çıktısı **mutlak yol** ile iletilir, ben/sen sentez yapmayız

---

## 2. Proje Hakkında — 2 Cümle

Archiverr = plugin-driven media archive orchestration runtime.
3-stage pipeline (PARSE → DATA → OUTPUT, per_run input plugin'leri önce),
manifest-driven, plugin-agnostic core (test-enforced ZERO TOLERANCE),
MongoDB persistence (4 canonical collection: `runs`, `jobs`, `plugins`,
`plugin_executions`), FastAPI REST API.

**Felsefeyi anlamak şart:** `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/AGENT.md`

---

## 3. Hızlı State Özeti (5 satır)

1. **Branch**: `dev/communication-refactoring`, HEAD = `e725fdb`
2. **Test**: 527/0/15 (tüm test'ler yeşil — Mongo açık değilken bile)
3. **Bu session'da**: 14 commit, ~500 LOC silindi, 0 canonical writer kırıldı
4. **MongoDB**: 4 canonical collection, audit sonrası temiz; smoke-test hazır
5. **Sıradaki adım**: `docker compose up -d mongodb` + gerçek smoke test

---

## 4. Bu Klasördeki Dosyalar

```
ONEMLI/session-36-devir/
├── 00-OKU-ONCE.md                     ← bu dosya (onboarding)
├── 01-felsefe-ve-mimari.md            ← AGENT.md özeti + non-negotiables
├── 02-baslangictaki-durum.md          ← session başlangıcında ne vardı
├── 03-plan-evrimi.md                  ← 3 paralel agent + simplifier ile plan
├── 04-uygulanan-isler.md              ← 14 commit detayı (PASS 1 → 6.E)
├── 05-mevcut-durum.md                 ← şu an ne durumda (file-by-file)
├── 06-sonraki-adimlar.md              ← yapılması gereken iş + öncelik
├── 07-referans-dosyalar.md            ← projeye ait önemli dosya yolları
└── audit-artifacts/                   ← 5 subagent raporu (sentezsiz)
    ├── 01-researcher-industry-evidence.md
    ├── 02-reviewer-hostile-code-audit.md
    ├── 03-simplifier-yagni-filter.md
    ├── 04-reviewer-round1-post-pass5.md
    └── 05-reviewer-round2-post-pass6e.md
```

---

## 5. Devam Etmek için ne yapmalısın

### Adım 1 — Onboarding (15 dakika)
1. `01-felsefe-ve-mimari.md` oku — AGENT.md'nin non-negotiable kuralları
2. `04-uygulanan-isler.md` oku — son 14 commit'te ne değiştirildi
3. `05-mevcut-durum.md` oku — file-by-file canonical map
4. `06-sonraki-adimlar.md` oku — sıradaki PASS'ler

### Adım 2 — State doğrulama (5 dakika)
```bash
cd /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr
git status --short
git log --oneline -15
# Beklenen: 14 commit, "session 36 PASS X" prefix'leriyle
```

### Adım 3 — Test doğrulama (3 dakika)
```bash
source .venv/bin/activate
pytest tests/unit/ tests/verify_refactor.py -q --tb=line
# Beklenen: 510 passed, 12 skipped (Mongo-bağımsız altküme)
```

### Adım 4 — Smoke test (10 dakika, Mongo gerekir)
```bash
docker compose up -d mongodb
# config.yml'de MONGODB_URI doğru mu kontrol
python -m archiverr  # küçük dataset ile dry_run
# /api/v1/runs endpoint'i ile status oku
```

### Adım 5 — Kullanıcıya rapor
5 satırlık state özeti ver; kullanıcının bir sonraki talebini bekle.

---

## 6. Önemli Kurallar (UYMAZSAN İŞİ KIRARSIN)

1. **AGENT.md** kuralları zorunlu (özet `01-felsefe-ve-mimari.md`'de).
2. **No-delete policy**: dosya silmek yerine `mkdir -p .deleted && mv target .deleted/`.
3. **Test enforced**: `tests/unit/core/test_plugin_agnostic.py` core'da plugin-spesifik
   string literal varsa fail eder. Bu test her zaman PASS olmalı.
4. **Manifest-driven**: plugin'ler `manifest.yml` üzerinden discover edilir.
   Core'da plugin name string'i YOK.
5. **3-stage pipeline**: per_run input → PARSE → DATA → OUTPUT. Yeni stage ekleme.
6. **Slim recovery contract**: tek-orchestrator-per-Mongo. Lease/heartbeat ERTELENDİ.

---

## 7. Audit Felsefesi (kullanıcı bunu çok önemsiyor)

Her büyük karar 3 farklı subagent ile doğrulanır:
- **architecture-researcher** — endüstri kanıtı (workflow-core, Kestra, Temporal,
  MongoDB official) + GitHub repo URL'leri
- **architecture-reviewer** — kodu hostile re-audit (file:line + grep)
- **simplifier** — YAGNI filtresi (AGENT.md "complexity earned only by current requirement")

Subagent çıktılarını **MUTLAK YOLLA** ileteceksin — sentez yapmayacaksın.
`audit-artifacts/` klasöründe her birinin tam metni var.

---

**Hazırsan `01-felsefe-ve-mimari.md` ile devam.**
