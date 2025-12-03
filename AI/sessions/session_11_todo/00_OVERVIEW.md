# SESSION 11 TODO LIST - OVERVIEW

```yaml
oluşturulma: 2025-12-04
durum: aktif
hedef: Session 11 stratejisinin kademeli implementasyonu
prensip: Küçük adımlar, test edilebilir, breaking change yok
```

---

## MEVCUT PROJE DURUMU

### Dosya Yapısı (src/archiverr/)

```
src/archiverr/
├── __main__.py           # 392 satır - REFACTOR GEREKLİ
├── state/
│   ├── models.py         # ExecutionState, MatchState - RENAME GEREKLİ
│   └── manager.py        # GlobalStateManager - UPDATE GEREKLİ
├── core/
│   └── plugins/
│       ├── discovery.py  # manifest.yml okur - UPDATE GEREKLİ
│       ├── executor.py   # 2 category executor - 4 STAGE GEREKLİ
│       ├── loader.py     # Plugin yükler - UPDATE GEREKLİ
│       ├── resolver.py   # Dependency resolver - UPDATE GEREKLİ
│       └── sdk/
│           ├── manifest.py   # PluginManifest - UPDATE GEREKLİ
│           ├── context.py    # ExecutionContext - UPDATE GEREKLİ
│           └── base.py       # BasePlugin - UPDATE GEREKLİ
├── events/
│   └── bus.py            # EventBus - MEVCUT, OK
├── infrastructure/
│   └── database/         # MongoDB - MEVCUT, OK
└── plugins/              # 68 items - MANIFEST UPDATE GEREKLİ
```

### Mevcut vs Hedef Karşılaştırması

| Alan           | MEVCUT                        | HEDEF                          | Öncelik |
| -------------- | ----------------------------- | ------------------------------ | ------- |
| Terminoloji    | execution, match              | run, job                       | P1      |
| State Models   | ExecutionState, MatchState    | RunState, JobState             | P1      |
| Stages         | 2 (input, output)             | 4 (input, parse, data, output) | P2      |
| Manifest       | category, depends_on, expects | stage, requires, provides      | P2      |
| Input          | input_path                    | input.value, input.data        | P1      |
| Output         | -                             | output.values, output.data     | P1      |
| Orchestrator   | **main**.py içinde            | orchestrator.py                | P3      |
| PluginServices | SDK context                   | services interface             | P3      |

---

## PHASE YAPISI

```
+----------------------------------------------------------+
|  PHASE 1: State Models (Breaking Change YOK)             |
|  Hedef: Yeni modeller YANINDA eski modeller              |
|  Dosyalar: state/models.py, state/manager.py             |
|  Test: Unit tests                                        |
+----------------------------------------------------------+
           |
           v
+----------------------------------------------------------+
|  PHASE 2: Manifest Schema (Backward Compatible)          |
|  Hedef: Yeni alanlar EKLENİR, eski alanlar KALIR         |
|  Dosyalar: sdk/manifest.py, discovery.py                 |
|  Test: Mevcut pluginler çalışmaya devam etmeli           |
+----------------------------------------------------------+
           |
           v
+----------------------------------------------------------+
|  PHASE 3: Config System (Additive)                       |
|  Hedef: FlexGet style config EKLENIR                     |
|  Dosyalar: utils/config_loader.py                        |
|  Test: Alias resolution                                  |
+----------------------------------------------------------+
           |
           v
+----------------------------------------------------------+
|  PHASE 4: Stage Executor (Parallel Development)          |
|  Hedef: 4-stage executor AYRI dosyada                    |
|  Dosyalar: core/stage_executor.py (YENİ)                 |
|  Test: Mevcut executor ETKİLENMEZ                        |
+----------------------------------------------------------+
           |
           v
+----------------------------------------------------------+
|  PHASE 5: Validation (Additive)                          |
|  Hedef: Conflict detection EKLENIR                       |
|  Dosyalar: core/validators/ (YENİ)                       |
|  Test: Warning/error tests                               |
+----------------------------------------------------------+
           |
           v
+----------------------------------------------------------+
|  PHASE 6: Migration (Gradual)                            |
|  Hedef: __main__.py simplification                       |
|  Dosyalar: core/orchestrator.py (YENİ)                   |
|  Test: E2E tests                                         |
+----------------------------------------------------------+
```

---

## TAHMINI SÜRE

| Phase      | Task Sayısı | Tahmini Süre   |
| ---------- | ----------- | -------------- |
| Phase 1    | 12 task     | 4-6 saat       |
| Phase 2    | 10 task     | 3-4 saat       |
| Phase 3    | 8 task      | 2-3 saat       |
| Phase 4    | 14 task     | 6-8 saat       |
| Phase 5    | 10 task     | 4-5 saat       |
| Phase 6    | 8 task      | 4-5 saat       |
| **TOPLAM** | **62 task** | **23-31 saat** |

---

## KURALLAR

### Breaking Change Önleme

1. **YENİ DOSYA > MEVCUT DOSYA DEĞİŞİKLİĞİ**

   - Yeni modeller ayrı dosyada oluşturulur
   - Eski modeller ALIAS olarak kalır

2. **BACKWARD COMPATIBLE MANIFEST**

   - `category` ve `stage` ikisi de kabul edilir
   - `depends_on` ve `requires` ikisi de çalışır
   - Discovery otomatik dönüşüm yapar

3. **GRADUAL MIGRATION**
   - Pluginler birer birer migrate edilir
   - Her migrate sonrası test çalıştırılır

### Test Prensibi

```python
# Her task için:
# 1. ÖNCE test yaz (RED)
# 2. SONRA kod yaz (GREEN)
# 3. SON refactor (REFACTOR)
```

---

## DOSYA LİSTESİ

```
session_11_todo/
├── 00_OVERVIEW.md              # Bu dosya
├── 01_PHASE1_MODELS.md         # State model tasks
├── 02_PHASE2_MANIFEST.md       # Manifest schema tasks
├── 03_PHASE3_CONFIG.md         # Config system tasks
├── 04_PHASE4_STAGE_EXECUTOR.md # Stage executor tasks
├── 05_PHASE5_VALIDATION.md     # Validation tasks
├── 06_PHASE6_MIGRATION.md      # Final migration tasks
└── 07_CHECKLIST.md             # Quick reference checklist
```

---

## BAŞLANGIÇ NOKTASI

**İLK GÖREV:** `01_PHASE1_MODELS.md` → Task 1.1

**Neden Phase 1?**

- State modelleri TÜM sisteme bağlı
- Terminoloji değişikliği en temel değişiklik
- Unit test yazılabilir (izole)
- Breaking change riski EN DÜŞÜK (yeni dosya)

---

**SON GÜNCELLEME:** 2025-12-04
