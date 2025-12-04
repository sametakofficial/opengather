# SESSION 11 - ÖNCELİK ANALİZİ VE GENEL BAKIŞ

```yaml
tarih: 2025-12-04
hazırlayan: AI Assistant
amaç: Büyük refactoring için önceliklendirilmiş TODO sistemi
yaklaşım: Her aşama bağımsız test edilebilir, yol gösterici ama sorgulatıcı
```

---

## ⚠️ ÖNEMLİ UYARI

**Bu belge yol gösterici niteliktedir.** Buradaki implementasyon önerileri:

- Direkt kopyala-yapıştır için DEĞİL
- Mevcut codebase ile uyumluluğu SEN kontrol etmelisin
- Kod örneklerini sorgula, daha iyi implemente edebilir misin düşün
- FINAL_DATASETS.yml tek truth source, stratejiye uy

---

## 1. STRATEJİ BELGELERİ ÖNCELİK HARİTASI

### Bağımlılık Grafiği

```
┌─────────────────────────────────────────────────────────────────┐
│                         BAĞIMLILIK GRAFİĞİ                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   [01_STATE_MODELS] ◄────────────────────────────────────────┐   │
│         │                                                     │   │
│         ▼                                                     │   │
│   [06_MONGODB_PERSISTENCE]                                    │   │
│         │                                                     │   │
│         ▼                                                     │   │
│   [02_PLUGIN_SERVICES] ◄─────────────────────────────────┐   │   │
│         │                                                 │   │   │
│         ▼                                                 │   │   │
│   [03_ORCHESTRATOR] ──────────────────────────────────────┼───┘   │
│         │                                                 │       │
│         ▼                                                 │       │
│   [STAGE_EXECUTOR] ◄──────────────────────────────────────┘       │
│         │                                                         │
│         ▼                                                         │
│   [04_CONFIG_MANIFEST]                                            │
│         │                                                         │
│         ▼                                                         │
│   [05_VALIDATION_TESTING]                                         │
│         │                                                         │
│         ▼                                                         │
│   [11_FASTAPI_REFACTORING]                                        │
│         │                                                         │
│         ▼                                                         │
│   [07_MEMORY_MANAGEMENT]                                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. PHASE YAPISI VE ÖNCELİK SIRASI

| Phase  | Konu                       | Kaynak             | Tahmini Süre | Kritiklik | Bağımlılık |
| ------ | -------------------------- | ------------------ | ------------ | --------- | ---------- |
| **P1** | State Models & Terminoloji | 01_state_structure | 4-6 saat     | 🔴 KRİTİK | -          |
| **P2** | MongoDB & Persistence      | 06_mongodb         | 4-6 saat     | 🔴 KRİTİK | P1         |
| **P3** | Plugin Services            | 02_plugin_system   | 6-8 saat     | 🟠 YÜKSEK | P1, P2     |
| **P4** | Orchestrator               | 03_orchestrator    | 6-8 saat     | 🟠 YÜKSEK | P1, P2, P3 |
| **P5** | Stage Executor (4 Stage)   | 03_orchestrator    | 4-6 saat     | 🟠 YÜKSEK | P4         |
| **P6** | Config & Manifest          | 04_config_manifest | 4-6 saat     | 🟡 ORTA   | P3, P5     |
| **P7** | Validation System          | 05_validation      | 4-6 saat     | 🟡 ORTA   | P1-P6      |
| **P8** | FastAPI Refactoring        | 11_FASTAPI         | 6-8 saat     | 🟡 ORTA   | P1, P2, P7 |
| **P9** | Memory Management          | 07_memory          | 4-6 saat     | 🟢 DÜŞÜK  | P2, P8     |

---

## 3. MEVCUT DURUM ANALİZİ

### 3.1 Terminoloji Değişiklikleri (Tüm Kod Tabanı)

```
MEVCUT → YENİ (HER YERDE DEĞİŞMELİ)
────────────────────────────────────
ExecutionState    → RunState
MatchState        → JobState
execution_id      → run_id
match             → job
total_matches     → total_jobs
completed_matches → completed
failed_matches    → failed
input_path        → input.value
(yeni)            → input.data
(yeni)            → output.values
(yeni)            → output.data
```

### 3.2 Mevcut Dosya Yapısı (Değişecek)

```
src/archiverr/
├── __main__.py          # 392 satır → ~50 satır (Orchestrator'a taşınacak)
├── state/
│   ├── models.py        # ExecutionState, MatchState → RunState, JobState
│   └── manager.py       # GlobalStateManager → StateManager
├── core/
│   └── plugins/
│       ├── executor.py  # 2 category → 4 stage
│       └── ...
└── api/
    └── v1/
        ├── executions/  # → runs/
        └── matches/     # → jobs/
```

### 3.3 Final Kararlar

- **Stage:** 4 adet (input, parse, data, output)
- **Provides:** Teknik etki bazlı
- **Requires:** Tek alan, explicit prefix
- **Config:** FlexGet style (plugin=top-level)
- **Trigger Rules:** 5 adet (always kaldırıldı)

---

## 4. HER PHASE İÇİN TEST STRATEJİSİ

### Test Edilebilirlik İlkesi

> **Her phase tamamlandığında, bir sonraki phase'e geçmeden önce testler PASS olmalı.**

| Phase | Test Türü   | Ne Test Edilir?                   | Başarı Kriteri                       |
| ----- | ----------- | --------------------------------- | ------------------------------------ |
| P1    | Unit        | RunState, JobState dataclass'ları | to_dict(), **post_init** çalışır     |
| P2    | Integration | MongoDB CRUD                      | Document insert/find/update başarılı |
| P3    | Unit        | PluginServices interface          | Mock ile service method'ları çalışır |
| P4    | Integration | Orchestrator.run()                | Dummy plugin ile full cycle          |
| P5    | Integration | 4 Stage execution                 | Her stage sırayla çalışır            |
| P6    | Unit        | Config validation                 | Schema validation geçer              |
| P7    | E2E         | Full validation                   | Startup + pre-execution validation   |
| P8    | API         | Endpoint tests                    | /runs, /jobs CRUD çalışır            |
| P9    | Performance | Memory eviction                   | Hot/cold tiering çalışır             |

---

## 5. RİSK DEĞERLENDİRMESİ

### 5.1 Yüksek Riskler

| Risk                        | Etki                          | Önlem                                         |
| --------------------------- | ----------------------------- | --------------------------------------------- |
| Terminoloji karışıklığı     | Tüm kod tabanında tutarsızlık | Tek seferde, atomik değişiklik                |
| **main**.py refactoring     | Çalışan sistemi bozma         | Paralel Orchestrator geliştir, sonra değiştir |
| MongoDB schema değişikliği  | Mevcut veri kaybı             | Migration script, backward compatibility      |
| Plugin manifest değişikliği | Tüm plugin'ler bozulur        | Geçici dual-format destek                     |

### 5.2 Mitigation Stratejisi

```
1. Her phase için GERİ DÖNÜŞ NOKTASI belirle
2. Feature flag ile yeni kod aktif/pasif yapılabilir olsun
3. Migration sırasında eski format'ı da destekle (geçici)
4. Her phase sonrası SNAPSHOT al (git tag)
```

---

## 7. DOSYA YAPISI (session_11_todo/)

```
session_11_todo/
├── 00_PRIORITY_ANALYSIS.md      # Bu dosya
├── 01_PHASE1_STATE_MODELS.md    # İlk phase detayları
├── 02_PHASE2_MONGODB.md         # İkinci phase detayları
├── 03_PHASE3_PLUGIN_SERVICES.md # Üçüncü phase detayları
├── ...
└── MASTER_CHECKLIST.md          # Tüm checklist'ler tek dosyada
```

---

## 8. BAŞLANGIÇ TALİMATLARI

### Yeni Chat Session Başlatırken

1. Bu dosyayı (`00_PRIORITY_ANALYSIS.md`) oku
2. İlgili phase dosyasını oku (örn: `01_PHASE1_STATE_MODELS.md`)
3. `MASTER_CHECKLIST.md`'de ilgili bölümü bul
4. Mevcut kodu incele
5. Kod örneklerini adapte et, direkt kopyalama

### Chat Context Yönetimi

```
⚠️ Context şişmesini önlemek için:
- Sadece ilgili phase dosyasını yükle
- Strateji belgesinin tamamını değil, ilgili bölümü oku
- Mevcut kodun sadece değişecek kısımlarını incele
- Tüm codebase'i taramaktan kaçın
```

---

**Sonraki Adım:** `01_PHASE1_STATE_MODELS.md` dosyasını oku ve ilk phase'e başla.
