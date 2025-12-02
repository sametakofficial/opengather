# RISK ANALİZİ VE CONFLICT SENARYOLARI

```yaml
date: 2025-12-01
type: risk-analysis
status: in-progress
```

---

# TEMEL FELSEFE (PHILOSOPHY.md'den)

```
STAGES: input → parse → metadata → output (4 stage)
Event bağlılık varsa → Stage GEREKSIZ
Kategori bağlılık varsa → Stage GEREKLİ
```

---

# RİSK LİSTESİ

---

## 1. FILE WRITE + CLOUD SYNC SONSUZ DÖNGÜ

**Sorun:** Tasker dosya yazar → Rclone sync yapar → Rclone yeni dosya algılar → tekrar sync → ∞

**Neden:** İkisi de `fs.write` event'ini hem emit eder hem dinler.

**Çözüm Seçenekleri:**

| Seçenek | Açıklama | Dezavantaj |
|---------|----------|------------|
| A. Event source filter | Event'e source_plugin ekle, kendi event'ini ignore et | Her plugin bunu kontrol etmeli |
| B. Batch write | Plugin system yazma isteklerini toplar, hepsi bitince tetikler | Karmaşık orchestration |
| C. Write lock | Bir plugin yazarken diğerleri bekler | Performans kaybı |
| D. Stage separation | Write yapanlar ayrı stage, sync yapanlar ayrı stage | PHILOSOPHY ihlali - event varsa stage gereksiz |
| **E. run_id tracking** | Her event'e run_id ekle, aynı run içinde tekrar tetikleme | Basit, temiz |

**Çözüm:** Sistem ilk çalıştırmada UYARI verir:
- "Bu iki plugin hem write hem upload yapıyor: tasker, rclone"
- Kullanıcı birini diğerine `depends` ekler
- `--force` ile çalıştırılırsa random sıra, risk kullanıcıda

---

## 2. DUPLICATE CLEANER + CLOUD SYNC ÇAKIŞMASI

**Sorun:** DuplicateCleaner dosya siler → Rclone sync yapar → Remote'da hala var → Rclone geri çeker

**Neden:** Silme ve sync aynı anda, hangisi önce belirsiz.

**Çözüm Seçenekleri:**

| Seçenek | Açıklama | Dezavantaj |
|---------|----------|------------|
| A. after | Rclone `after: [fs.delete]` | Bu cap'i sağlayanlar bitsin |
| B. Priority | DuplicateCleaner priority: 10, Rclone priority: 100 | Magic numbers, bakımı zor |
| **C. Explicit ordering** | Config'de sıra belirlenir | Kullanıcı sorumluluğu |

**Çözüm:** Manifest'te `after` ile bağımlılık
```yaml
# rclone/manifest.yml
after: [fs.delete]  # Silme işlemleri bittikten sonra sync
```

---

## 3. AYNI DOSYAYA BİRDEN FAZLA PLUGİN YAZMA

**Sorun:** Tasker `/movies/film.mkv` yazar → AIEnricher aynı yere yazar → Override

**Neden:** İki plugin aynı destination'a yazıyor.

**Çözüm Seçenekleri:**

| Seçenek | Açıklama | Dezavantaj |
|---------|----------|------------|
| A. First write wins | İlk yazan kazanır, ikinci hata alır | Sessiz fail |
| B. Last write wins | Son yazan kazanır | Data loss |
| **C. Path reservation** | Plugin system path'leri reserve eder, conflict → error | Validation overhead |
| D. Unique suffix | Conflict varsa `film_1.mkv`, `film_2.mkv` | Kirli output |

**Önerilen:** C - Path reservation
- Plugin `services.filesystem.reserve(path)` çağırır
- Başka plugin aynı path'i isterse → hata
- Hata mesajı net: "Path already reserved by {plugin_name}"

**Kaynak:** Database row locking, file locking (flock)

---

## 4. TEMPLATE'DE OLMAYAN PLUGİN REFERANSI

**Sorun:** Tasker template'de `{{ job.plugins.ai_detector.result }}` var ama ai_detector fail oldu veya yok.

**Neden:** Tasker çalıştığında beklenen data state'de yok.

**Çözüm Seçenekleri:**

| Seçenek | Açıklama | Dezavantaj |
|---------|----------|------------|
| A. Jinja2 default filter | `{{ job.plugins.ai_detector.result \| default('N/A') }}` | Her template'e eklenmeli |
| **B. Tasker validation** | Tasker başlarken template'deki plugin'leri kontrol eder | Ek validation |
| C. Strict mode | Undefined variable → error | Kullanıcı dostu değil |

**Önerilen:** B - Tasker validation
- Tasker per_run plugin olarak önce tüm template'leri parse eder
- `job.plugins.X` pattern'lerini bulur
- X plugin'i state'de yoksa → warning log + skip task

**Kaynak:** Jinja2 UndefinedError handling, Ansible variable validation

---

## 5. PER_RUN PLUGİN + on ÇAKIŞMASI

**Sorun:** per_run plugin `on: [fs.created]` derse, her fs.created'da mı çalışacak?

**Neden:** per_run = bir kez çalış, `on` = her event'te çalış → çelişki.

**Çözüm:**

| Kural | Açıklama |
|-------|----------|
| **PHILOSOPHY.md §4.2** | `on` sadece per_job için geçerli |
| per_run plugin'ler | `after` kullanır, event değil |

**Validation:** Manifest'te `mode: per_run` + `on` varsa → error

---

## 10. EVENT EMİT SIRALAMASI

**Sorun:** Plugin A `fs.write` emit eder, Plugin B dinliyor. B ne zaman çalışır?

**Neden:** Sync vs async emit belirsiz.

**Çözüm Seçenekleri:**

| Seçenek | Açıklama | Dezavantaj |
|---------|----------|------------|
| A. Sync | Emit eden bekler, listener çalışır, sonra devam | Blocking, yavaş |
| **B. Async queue** | Event queue'ya eklenir, stage sonunda işlenir | Sıralama karmaşık |
| C. Next stage | Event'ler bir sonraki stage'de işlenir | Gecikme |

**Önerilen:** B - Async queue + stage end processing
- Event emit edilince queue'ya eklenir
- Plugin çalışmasına devam eder
- Stage bitince queue işlenir

**Kaynak:** Node.js EventEmitter, RabbitMQ message queue

---

## 11. provides COLLISION - AYNI CAPABILITY BİRDEN FAZLA PLUGİN

**Sorun:** TMDb ve OMDb ikisi de `provides: [metadata.movie]`

**Neden:** Aynı capability birden fazla source.

**Çözüm:** İZİN VER - Bu normal davranış.
- `after: [metadata.movie]` = HEPSİ bitsin
- Conflict değil, feature

---

## 12. PLUGIN SERVICES PERMISSION

**Sorun:** Herhangi bir plugin `services.filesystem.delete("/")` yapabilir mi?

**Neden:** Plugin system güvenlik sınırı yok.

**Çözüm Seçenekleri:**

| Seçenek | Açıklama | Dezavantaj |
|---------|----------|------------|
| A. Sandbox | Plugin izole ortamda çalışır | Performans, karmaşıklık |
| **B. Path restriction** | filesystem sadece config'deki path'lere erişir | Basit, yeterli |
| C. Trust | Plugin geliştirici sorumlu | Güvensiz |

**Önerilen:** B - Path restriction
- `services.filesystem` sadece `scanner.targets` ve `tasker.destination` path'lerine erişebilir
- Dışarı çıkmaya çalışırsa → error

---

# ÖZET: KRİTİK RİSKLER

| # | Risk | Önem | Çözüm |
|---|------|------|-------|
| 1 | Write + Sync döngü | KRİTİK | Sistem uyarı + depends |
| 2 | Delete + Sync çakışma | YÜKSEK | after |
| 3 | Aynı dosyaya yazma | YÜKSEK | Path reservation |
| 4 | Template missing data | ORTA | Tasker validation |
| 5 | per_run + on | DÜŞÜK | Manifest validation |
| 12 | Plugin fs permission | ORTA | sandbox: true |

---

# KARARLAR

- **run_id:** UUID v4
- **Path reservation:** Run boyunca geçerli
- **Event queue:** Memory-based, run sonunda temizlenir

---

**Status: APPROVED**
