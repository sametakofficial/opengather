# Sonraki Adımlar — Öncelik Sırası

> Bu dosya audit-2'nin (`audit-artifacts/05-reviewer-round2-post-pass6e.md`) F bölümü
> + kullanıcının "FastAPI ve MongoDB güncellemesi" hedefiyle yazıldı.

---

## TIER 1: SMOKE TEST (zorunlu, 10-15 dk)

### Adım 1: MongoDB başlat
```bash
cd /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr
docker compose up -d mongodb
# bekle 5 saniye
```

### Adım 2: Konfigürasyon doğrula
```bash
cat config.yml | grep -E "MONGODB_URI|database|mongodb"
# beklenen: MONGODB_URI=mongodb://localhost:27017
```

### Adım 3: Run + observation
```bash
source .venv/bin/activate
python -m archiverr  # küçük dataset, dry_run=true (default)
# Beklenen output:
#   - run_id üretilir (run_{uuid8})
#   - 9 plugin'den hangileri çalışırsa plugin_executions'a "completed" yazar
#   - jobs.plugins embedded + plugins collection cross-job query yazar
```

### Adım 4: API ile state oku
```bash
# Başka terminalde
uvicorn archiverr.api.main:app --reload --port 8000

# 3. terminalde
curl http://localhost:8000/api/v1/runs/                       # list
curl http://localhost:8000/api/v1/runs/{run_id}/status        # detail
curl http://localhost:8000/api/v1/jobs/run/{run_id}           # jobs
curl http://localhost:8000/api/v1/plugins/run/{run_id}        # plugin output
curl http://localhost:8000/api/v1/system/status               # canonical stats: runs/jobs/plugins
```

### Smoke-test'te dikkat edilecekler
- Mongo connect başarısız ise endpoint'ler **503** dönmeli (Internal Server Error 500 değil)
- `/api/v1/system/status` `collections.runs/jobs/plugins` döndürmeli
- `/api/v1/system/diagnostics` always-empty döndürür (DiagnosticsLogger unwired — KARAR İSTER)
- `runs/router.py:46-48` `execution_id` legacy alias'ı hit alırsa → pre-S36 doc'lar var demektir, migration script gerek
- `runs/router.py:68-70` `summary.total_matches` legacy embedded fallback hit'i benzer sinyal

---

## TIER 2: Kullanıcının onayını bekleyen 3 soru

(`ONEMLI/mongodb-audit.md` ve audit-2 raporunda belirtilenler.)

### Soru 1: `plugin_docs` Mongo collection migration
PASS 3'te kod silindi ama gerçek Mongo'daki collection (varsa) `.deleted/`
işaretlenmesi gerek. Operatör tarafı.

```bash
# Önce kontrol:
mongoexport --uri=mongodb://localhost:27017/archiverr --collection=plugin_docs --out=plugin_docs_backup.json
# Eğer dolu ise:
mkdir -p .deleted
mv plugin_docs_backup.json .deleted/
mongo archiverr --eval "db.plugin_docs.drop()"
```

### Soru 2: Legacy collection migration (executions/matches/plugin_results)
Aynı şekilde.
```bash
for col in executions matches plugin_results; do
  mongoexport --uri=... --collection=$col --out=${col}_backup.json
done
# Eğer dolu ise .deleted/'a taşı.
```

### Soru 3: DiagnosticsLogger karar
`DiagnosticsLogger` (utils/debug.py) hiç instantiate edilmiyor. `api/v1/system/router.py:180`
boş okuyor. Karar: **wire** (operatör forensic ihtiyacı varsa) veya **delete**
(boş infrastructure pure cost).

---

## TIER 3: Smoke-test sonrası temizlik (öncelik sırası)

### A) Migration kalıntıları (smoke test verisiyle değerlendirilebilir)
**Defer until smoke-test data shows:**
- `runs/router.py:46-48` `_doc_to_run_response` `execution_id` → `run_id` rename + `exec_X` → `run_X` ID transformation
- `runs/router.py:68-70` `summary.total_matches` legacy embedded summary fallback
- `runs/router.py:91-92` `match_ids` / `config_snapshot` legacy field aliases
- `jobs/router.py` benzer `execution_id` / `match_id` legacy alias kalıntıları

**Karar verme tarzı:** Smoke-test sonrası prod Mongo'da bu shape'ler hit alıyor mu kontrol et.
- Hit yoksa: defansif kod sil (AGENT.md "no defensive try/catch around impossible paths")
- Hit var: migration script yaz (one-time data transform), sonra fallback'leri sil

### B) Open question'ları kapat
`ONEMLI/kritik-bulgular.md`'deki 3 vizyon sorusu hala açık:
1. Bu projeyi kim kullanacak — sen mi, başkaları da mı?
2. Çoklu orchestrator gerçek senaryo mu?
3. Reactive plugin'ler gerçekten istiyor musun?

Bu sorular cevaplanırsa şu kararlar netleşir:
- A4 audit log infrastructure (compliance gerek mi?)
- A5/A6 lease/heartbeat/checkpoints (multi-orch gerek mi?)
- A1 reactive plugin model (event-driven extensibility?)
- C1 CI/CD (GitHub Actions) — başkası kullanacaksa zorunlu
- C2 plugin developer docs — başkası yazacaksa zorunlu

### C) E1/K6 — per_run plugin_executions wiring
Recovery scan canonical surface'i `plugin_executions`. Per-run plugins (`scanner`,
`file-reader`) bu collection'a yazmıyor. Kritik bug değil ama **recovery contract'ı
inconsistent**.

```python
# orchestrator.py'da per_run plugin executor'ında benzer save_plugin_execution call'u
self._persistence.save_plugin_execution(
    run_id=self._run_id,
    job_id="",  # per_run = no job
    plugin_name=plugin.name,
    state=plugin_state,
    attempt=1,
)
```

Ya boş `job_id` schema'da OK olarak işaretlenmeli, ya da `plugin_executions` doc
shape'i `target_id` field'ı üzerinden run_id/job_id polymorphic olmalı.

### D) Memory bank sync (audit önerisi PASS 6.E)
`memory-bank/activeContext.md` `Last Updated: April 18, 2026` → Session 36 yansıtmıyor.
PASS 6.A/B/C/D/E + N6 cleanup + plugin-agnostic guard restoration listesi eksik.

```bash
# Bu session sonu memory-bank-sync agent ile yapılacaktı, şimdi manuel:
# (memory-bank gitignored, commit'lenmez)
```

### E) Legacy schema rename (smoke-test data ile)
Eğer prod Mongo'da pre-S36 doc'lar varsa:
```python
# Bir kerelik migration:
# RunState eski: status field'ı string idi
# JobState eski: match_index/total_matches kullanıyordu
# Plugin eski: match_id field'ı (jobs.plugins'in eski adı)
```

---

## TIER 4: Vizyon kararı sonrası gelecek işleri

> Bu işler `ONEMLI/kritik-bulgular.md` Tier C'de listelenmişti. Kullanıcı vizyon
> sorularını cevapladıktan sonra sıralanır.

### C1: CI/CD (~30 dk)
GitHub Actions + pytest + ruff. Eğer projeyi başka biri kullanacaksa zorunlu.

### C2: Plugin developer docs (~2-3 saat)
Plugin yazarı için: manifest format, services API, requires/provides syntax,
trigger rules, lifecycle.

### C3: Real API smoke test (~30 dk)
Gerçek TMDb/TVDb API key ile en az 1 başarılı pipeline.

### C4: StageExecutor decomposition (~5 saat)
PluginInvoker + ParallelGroupExecutor split. **MOTTOSU: "Stop refactoring,
write plugins"** — yeni plugin yazma acısı olmadan dokunma.

### A1-A8 dead schema bulgu kapatma
- A1 reactive plugin (Pydantic'te kalan `reactive`/`capabilities`/`hooks`/`listens_to`) → SİL ya da WIRE
- A4 side-effects audit trail → kullanıcı kararı
- A5/A6 lease/heartbeat/checkpoints → multi-orch kararı
- A7 enum kullanımı discipline (PluginStatus/MediaCategory/PluginCategory) → kod string literal yerine enum'a geçir
- A8 Config freeze (Pydantic frozen) → küçük UX iyileştirmesi

---

## Yeni AI için ipuçları

### Çalışma stili (kullanıcı tercih ediyor)
1. **Commit-driven** (her PASS git commit, geri dönüş için)
2. **Subagent doğrulama** (her büyük karar 2+ agent ile)
3. **Body-text parental tone değil** — Türkçe konuşuyor, "abi" diyor, kısa "yap" / "devam" / "durma" cümleleriyle yönlendirir.
4. **Sentez yok** — agent çıktıları **mutlak yolla** iletilir
5. **Dürüst** — abartılı "perfect!" / "absolutely correct!" yasak. Eğer yanlış yaptıysan söyle, geri al, yeniden yap.
6. **AGENT.md zorunlu** — her subagent'a bu dosya okutturulmalı

### Trap'lar
1. **"Triple copy waste"** gibi yüzeysel kararlar — Extended Reference Pattern denormalization olabilir
2. **"Dead method, sil"** — `hasattr` guard'lar bug değil, defansif eski API olabilir, prod caller grep ile kontrol şart
3. **"Duplicate router"** — iki ayrı execution model olabilir
4. **"Schema kodu izlemeli"** her zaman değil — slim contract / today's truth bağlamı önemli
5. **AGENT.md "complexity earned only by current requirement"** — `schema_version`, SSE, Beanie gibi "ileride lazım" işler ELE, şimdiki tek bug'ı çöz

### Komutlar (kullanıcı bunlara alışık)
```bash
cd /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr
source .venv/bin/activate

# Test
pytest tests/ -v
pytest tests/unit/ -q --tb=line

# Lint+type
ruff check src/
mypy src/archiverr/

# Smoke
python -m archiverr  # CLI run
uvicorn archiverr.api.main:app --reload --port 8000

# Git
git status --short
git log --oneline -10
```

### Audit yaptırma reçetesi
```
Agent({
  description: "Hostile re-audit of <X>",
  subagent_type: "architecture-reviewer",
  prompt: """
  ZORUNLU OKUMA:
  1. /home/.../AGENT.md
  2. /home/.../ONEMLI/session-36-devir/00-OKU-ONCE.md
  3. (varsa) önceki audit artifact yolu

  GÖREV: <bağlam + spesifik soru>

  ÇIKTI FORMATI:
  ## TL;DR (4 satır max)
  ## A) <ana iddia> doğrulama (file:line + grep)
  ## B) Yeni doğan sorunlar (varsa)
  ## C) Bir sonraki PASS önerisi (en kritik 3 madde)

  KURALLAR:
  - Bence yok, kanıt + file:line + grep
  - Yumuşatma; dürüst söyle
  - Kod yazma, sadece audit raporu
  """,
  run_in_background: true
})
```

---

**Sonraki:** `07-referans-dosyalar.md` — projeye ait tüm önemli dosya yolları.
