# Session 36 Başlangıç Durumu

## Branch state (session 36 başlangıcı, 2026-04-30 ~01:00 GMT+3)

- Branch: `dev/communication-refactoring`
- HEAD: `c4e3808` (session 35 F1: document slim recovery)
- Test: 418 passed, 24 skipped, 0 failed (Session 33 sonrası)
- Mongo down (`localhost:27017` connection refused) → 4 test fail (`tests/test_api.py`,
  `tests/unit/api/test_endpoints.py` — sıralama-bağımlı flakiness)

## Kullanıcının ilk talebi (session başlangıcı)

> "selam archiverr projesini incele ve en son yaptığımız araştırmalara fln varsa
> bul bakalım bi ne var ne yok en son nerede kalmışız neler planlamışız bak..."

Sonra:
> "bence veri yapılarını kesinleştirmekten başlayalım"

Sonra:
> "yazılım baya sağlam yapmışız ama demi çok iyi proje ha ciddi zekice tasarlanmış
> şimdi neler yapmak gerek bi sürü eksik tespit etmişsindir heralde"

Sonra (kritik):
> "mongodb deki plugin docs unu bilmiyorum gerekirse kaldırırız da mevcut en son
> mongodb veri yapısını... eksikleri tespit et... ne eksik ne fazla ne kötü
> eleştirisi ve net yeni geliştirme planları çıkarmamız ve sistemin artık tam
> entegre mongodb ile kaliteli çalışmasını sağlamamız gerek"

---

## Session başlangıcında bulunan iki önemli "güncel kalmamış" durum

### 1. `datasets/` shard'larında dead schema kalıntıları

`datasets/` 14 shard'ında (00-enums, 01-config, ... 12-safety, README) çoğunluğu
**kodda hiç reader'ı olmayan** schema field'ları vardı. Session 35'te yapılmış
audit doğrulamamış, datasets güncel değildi.

Örnek phantom field'lar (Pydantic'te tanımlı, 0 reader):
- `manifest.capabilities`, `hooks`, `listens_to`, `reactive` (Session 34 commit `5c24b22`'de eklenmiş, hiç wire edilmemiş)
- `discovery_extras._resolved_at` (yazıcı/okuyucu yok)
- `template_support.deprecated_fields.requires_only_jinja_render` (kaynak yok)
- `scanner.min_size_bytes`, `tmdb.include_raw_data` (config option, kullanılmıyor)
- `context_shape.plugins`, `provides`, `index`, `<resolved_alias>` (TemplateContextBuilder bunları emit etmiyor)
- 9 dead event (`run.failed`, `job.started`, `plugin.started`, `plugin.progress`, `task.*`, `state.changed`, `db.*`)
- 4 unwired Mongo interface method (`save_checkpoint`, `get_checkpoints`, `claim_plugin_execution`, `heartbeat_plugin_execution`)

### 2. ONEMLI klasörü (session başında oluşturuldu)

Kullanıcı başlangıçta:
> "bu bulgular çok iyi bunları bir yere kaydet ONEMLI adlı bir klasör oluşturup
> içine kritik bulgular adında bir md oluşturup kaydet"

`ONEMLI/kritik-bulgular.md` oluşturuldu — 8 phantom feature (A1-A8), 4 half-feature
(B1-B4), 4 ops task (C1-C4), 7 unverified (D), 4 Pydantic dead field (E).

Sonra:
> "şimdi biz veri yapıları kesinleştiyse sistemin mongodb sine başlayalım"

`ONEMLI/mongodb-audit.md` oluşturuldu — 9 collection, 7 EKSIK (E1-E7),
8 FAZLA (F1-F8), 10 KOTU (K1-K10), P1/P2/P3 plan (15 madde).

### 3. Kullanıcının uyarısı (kritik)

İlk MongoDB audit'inden sonra kullanıcı uyardı:
> "subagentlere danış bakalım verdiğin kararlar ne kadar mantıklı, mongodb
> konusunda yani veri yaplarında biz indexleme hızlı olsun diye bazı şeyleri
> duplicate yazmış olabiliriz direkt silmeye karar vermek göt iter generic
> bir analiz değil projeyi iyice anlayıp anladığın kadarıyla mongodb deki
> yapılan şeylerin neden yapıldığını gerçekten düşün"

> "AGENT.md yi oku yeni yazdım bu projeyi iyi anlatıyor tüm subagentlerde
> kesin okusunlar bunu ve derin bir şekilde analiz et"

Bu uyarı session 36'nın **ana çalışma stilini belirledi**:
- Her plan adımı 2+ subagent ile doğrulandı
- Her dead code iddiası `file:line` + grep + audit ile kanıtlandı
- AGENT.md tüm subagentlere zorunlu okutuldu
- "Triple-copy plugin storage = waste" gibi ilk-düşünce kararlar refute edilmeye
  açık tutuldu

---

## Önceki audit'lerin (Session 35 öncesi) durumu

| Doc | Tarih | Durum (Session 36 başında) |
|---|---|---|
| `datasets/` 14 shard | Session 35 | "Drift mevcut, aktif olmayanlar listelenmemiş" |
| `kritik-bulgular.md` | Session 36 başında oluşturuldu | Yeni audit, 8 phantom feature listesi |
| `mongodb-audit.md` | Session 36 başında oluşturuldu | İlk audit, 15 maddeli plan (sonradan filtrelendi) |
| `HANDOFF.md` | Session 33 | "Session 33 sprint sonrası, slim recovery model" |
| `AGENT.md` | Yeni (kullanıcı session sırasında yazdı) | Tüm subagentlere zorunlu okuma |

---

## Branch'de session 36 öncesi birikmiş uncommitted değişiklikler

Session 35 sonu + Session 36 başı bazı dataset cleanup ve template context refactor
işleri yapılmıştı ama commit edilmemişti:

- `datasets/00-enums.yml` ... `datasets/12-safety.yml` + `README.yml` (dead schema temizliği)
- `src/archiverr/state/template_context.py` (`_build_plugin_surface` eklendi)
- `src/archiverr/plugins/tasker/plugin.py` (canonical context construction tasker'dan kaldırıldı)
- `tests/unit/state/test_template_context_wp4.py` (`"plugin"` top-level key assertion)
- `SYSTEM_DATASETS.yml` (auto-generated full consultation file, ~34KB)

Session 36'nın `e07c970` (prep) commit'i bu değişiklikleri tek commit olarak topladı.

---

## Session 36 başlangıcındaki açık sorular (ONEMLI/kritik-bulgular.md'den)

1. Bu projeyi kim kullanacak — sadece sen mi, yoksa başkaları da mı?
2. Çoklu orchestrator gerçek bir senaryo mu, yoksa "bir ihtimal" mi?
3. Reactive plugin'ler / event-driven extensibility gerçekten istiyor musun?

Bu sorular session 36 sonunda **henüz cevaplanmadı**. Defer kararları:
- Çoklu orchestrator → slim contract (single per Mongo)
- Reactive plugins → iptal (manifest'ten temizlenmedi ama datasets'ten silindi)

---

**Sonraki:** `03-plan-evrimi.md` — paralel agent'lar ile plan nasıl şekillendi?
