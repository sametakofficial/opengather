# Felsefe ve Mimari — AGENT.md özeti

**Kanonik kaynak:** `/home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/AGENT.md`

Bu dosya AGENT.md'nin **özetidir**, replacement değildir. Karar verirken
mutlaka tam AGENT.md'yi oku — özellikle "What Not To Do" ve "Decision Rule:
Core or Plugin?" bölümlerini.

---

## Tek-Cümle-Identity

> Archiverr is a domain-specific, manifest-driven media metadata
> orchestration runtime that gives plugins high freedom while keeping core
> stable, plugin-agnostic, deterministic, and safe for real file archives.

## Kazanan Tasarım Prensibi

> High plugin potential inside strict domain-specific stability rails.

Archiverr Kestra/Temporal/Airflow OLMAK İSTEMİYOR. Onlar generic workflow
engine; Archiverr media-metadata-spesifik. **Domain rails = stage modeli**
(per_run → PARSE → DATA → OUTPUT).

---

## Non-Negotiable Mimari Kuralları

### 1. Core Plugin-Agnostic Olmak ZORUNDA

`src/archiverr/core/` plugin adı (scanner, renamer, tmdb, tvdb, tvmaze,
omdb, ffprobe, tasker, file-reader) **string literal olarak içeremez**.

`tests/unit/core/test_plugin_agnostic.py::TestCorePluginAgnosticGuard` bunu
runtime'da kontrol eder. Bu test her zaman PASS olmalı.

Core sadece şu generic kavramları bilir: plugin, manifest, stage, run mode,
requires, provides, trigger rule, job, run, service, result.

**Eğer `if plugin == "tmdb":` yazıyorsan tasarım yanlış.**

### 2. Manifest = Sözleşme

Her plugin `manifest.yml` deklare eder:
- `name`, `version`, `stage`, `run_mode`, `class_name`, `entry_point`
- `requires`: ne hazır olmalı (örn: `plugin.renamer.parsed:success`)
- `provides`: ne üretiyor/değiştiriyor (örn: `http.request`, `fs.write:/path`)
- `trigger_rule`: koşullu execution (all_success / one_success / vs)
- `config_schema`: opsiyonel doğrulama

### 3. 3-Stage Pipeline (DEĞİŞTİRME)

```
per_run input plugins → PARSE → DATA → OUTPUT
```

- `PARSE`: filename/path/probe'tan structured info çıkar
- `DATA`: harici/dahili provider'lardan metadata getir
- `OUTPUT`: render, task, rename plan, fs change

Yeni stage eklemek için domain ihtiyacı kanıtla. Aksi yasak.

### 4. Plugin Sözleşmeleri Strict

```python
# per_run plugin
def execute_run(services) -> dict: ...

# per_job plugin
def execute(job, services) -> PluginResult: ...
```

Backwards-compat magic, signature introspection, dict fallback, "accept anything"
adapter YASAK. (Session 34'te zaten temizlendi.)

### 5. Safety > Convenience

- Dry-run **default mental model**.
- No silent failures (no bare `except: pass`).
- No-delete: `os.remove`, `shutil.rmtree` YASAK. Use `.deleted/` move.
- `dry_run`, `hardlink`, `no_delete` config option'larına saygı.

---

## Engineering Taste / Style

> Complexity is allowed only when earned by a current requirement.

Yasak (AI-code slop):
- gereksiz abstraction
- obvious code'u tekrar yorum
- impossible path'lara defansif try/catch
- `Any` cast ile typing problem gizleme
- factory-factory pattern
- speculative extension point
- generic workflow platform inside media archive tool

İzin (AGENT.md "YAGNI > SOLID"):
- 3 benzer satır > premature abstraction
- "This works and is readable" geçerli review sonucu

---

## Decision Rule: Core mi Plugin mı?

> **Core invariant'lara sahip olur. Plugins strateji'lere sahip olur.**

**Core:**
- canonical state model
- run/job identity
- transaction/safety boundary
- event log
- artifact store
- scheduler/planner
- validation
- no-delete/dry-run enforcement hook
- stable domain lifecycle

**Plugin:**
- metadata provider integration
- parsing strategy
- matching/scoring strategy
- subtitle discovery
- output renderer
- rename plan generator
- external system integration
- optional side-effect action

> Eğer bir bileşeni silmek projenin truth model'ini yıkıyorsa, **core**'da kalsın.
> Eğer veriyi üretmek/zenginleştirmek/dönüştürmek için bir alternatif yolsa, **plugin**.

---

## Üç-Strike Reuse Kuralı

Archiverr şu an step 1: media metadata recipe'i kanıtlamaya çalışıyor.
Step 2 (başka domain ile reuse) ve Step 3 (üçüncü project) gelmeden,
Archiverr'ın plugin runtime'ı **generic middleware'e EXTRACT EDİLMEMELİ**.

Bu yüzden:
- Multi-orchestrator support → ERTELENDİ (slim contract)
- Lease/heartbeat → ERTELENDİ
- Audit log infrastructure → ERTELENDİ
- Sandboxed plugin runner → ERTELENDİ (no untrusted plugin yet)
- SSE/WebSocket → ERTELENDİ (no UI consumer yet)
- Marketplace → ERTELENDİ (SDK olgunlaşmamış)

---

## Şu anki güçlü noktalar (Session 36 sonrası)

1. Core gerçekten plugin-agnostic (test guard yeşil).
2. Stage modeli sade ve domain-fit.
3. `manifest.yml` zorunlu `stage` + `run_mode` (Session 34'te enforced).
4. requires/provides hardcoded coupling olmadan plugin işbirliği sağlıyor.
5. Trigger rule'lar conditional execution.
6. Dependency grouping safe paralelizasyon.
7. Main-thread commit modeli runtime stability.
8. No-delete/dry-run kültürü sıkı.
9. **MongoDB kanonik 4 collection (S36 temizliği sonrası)**: runs, jobs, plugins, plugin_executions.
10. **API canonical-only** (S36 PASS 6.C sonrası): legacy executions/matches/plugin_results reader fallback'leri silindi.

## Şu anki zayıf noktalar (gelecek hedefler)

1. SDK olgunluğu düşük (plugin yazarken iç convention bilmek lazım).
2. `provides` semantik tam ayrılmadı (capability vs effect).
3. Plugin isolation yok (in-process trusted Python).
4. `dict[str, Any]` plugin result data → tipsiz.
5. Retry/timeout/failure-policy modeli olgunlaşmadı.
6. `api_version`/`min_core_version` plugin manifest'inde yok.
7. Plugin template/docs gen/validate CLI yok.
8. Filesystem lock/effect planning advisory.
9. Reusable middleware değil (tek bir domain runtime'ı).

---

**Sonraki:** `02-baslangictaki-durum.md` — Session 36 başında neler vardı?
