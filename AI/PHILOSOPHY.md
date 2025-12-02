# ARCHIVERR PHILOSOPHY

Projenin temel prensipleri ve felsefeleri.

---

## 1. CORE PRENSİPLERİ

### 1.1 Core = Dumb Playground
Core hiçbir iş mantığı içermez. Sadece:
- Plugin yükler
- Config okur
- State yönetir
- EventBus sağlar

Fazlalık feature'lar plugin'e dönüştürülür.

### 1.2 Plugin Agnostik
Core hiçbir plugin'i tanımaz. TMDb, Scanner, Renamer - hepsi eşit.
Hardcoded plugin referansı yasak.

### 1.3 No Hardcoding
- State'e direkt erişim yok → StateManager üzerinden
- Event'e direkt erişim yok → EventBus üzerinden
- Config'e direkt erişim yok → ConfigLoader üzerinden
- `eval()` veya `exec()` yasak

---

## 2. CONFIG PRENSİPLERİ

### 2.1 Config = Source of Truth
Config her şeyi tanımlayabilir. Manifest ve external dosyalar sadece ekleme yapar.

### 2.2 Jinja2 Her Yerde
Config, manifest, external config - hepsi aynı template engine kullanır.
Alias, değişken, koşul, döngü her yerde çalışır.

### 2.3 Alias Sistemi = Inline Değişkenler
Alias sadece config başında değil, her yerde tanımlanabilir.
Bu sayede manifest ve external config de alias oluşturabilir.

```jinja2
{% set m = job.plugins.tmdb.movie %}
{{ m.title }}
```

### 2.4 External Config = Import Sistemi
Herhangi bir config bölümü başka dosyadan import edilebilir.
Task-spesifik değil, genel amaçlı.

```yaml
scanner:
  import: ./scanner-config.yml

tasks:
  import: ./tasks/*.yml
```

---

## 3. STAGE PRENSİPLERİ

### 3.1 Stage = Kategorizasyon için Sıralama
Stage'ler execution sırası için değil, kategori bazlı sıralama için.

### 3.2 Event Bağlılık vs Kategori Bağlılık

```
Bağlılık event türünde ise → Stage GEREKSIZ
  Örnek: file.created event'i dinleyen plugin

Bağlılık kategori türünde ise → Stage GEREKLİ
  Örnek: Metadata plugin'leri (TMDb, TVDb) - hangi event ile tespit edersin?
```

### 3.3 per_run + Stage
per_run plugin'ler stage sıralamasına uyar.
Stage içinde sıralama = requires/waits_for ile.

---

## 4. DEPENDENCY PRENSİPLERİ

### 4.1 TEK DEPENDENCY: requires

```
REDDEDILEN:
  after, waits_for, depends_on, triggers_on
  
KABUL EDILEN:
  requires (tek alan, uc source)
```

### 4.2 REQUIRES PREFIX SISTEMI

| PREFIX | SOURCE | SEMANTIK |
|--------|--------|----------|
| `job.*` | GlobalState | Path dolu olana kadar bekle |
| `provides.*` | ProvideRegistry | Provide tamamlanana kadar bekle |
| `events.*` | EventBus | Event emit edilene kadar bekle |

### 4.3 HARDCODED YASAK
```
YANLIS: requires: [renamer]
DOGRU:  requires: [provides.data.parsed]
DOGRU:  requires: [job.plugins.renamer.parsed]
```

---

## 5. PLUGIN PRENSİPLERİ

### 5.1 Plugin Services
Her plugin şu servislere erişebilir:
- `services.state` - State okuma/yazma
- `services.event_bus` - Event emit/subscribe
- `services.filesystem` - Dosya okuma/yazma
- `services.http` - HTTP istekleri (optional)
- `services.logger` - Loglama

### 5.2 provides = Islem Bazli Deklarasyon
Plugin manifest'inde provides ile ne yaptigini declare eder.

KATEGORI BAZLI DEGIL - ISLEM BAZLI:
```
YANLIS: provides: [metadata.movie]   # Kategori
DOGRU:  provides: [http.response]    # Islem
```

Standart provides degerleri:
```
http.request     HTTP istek yapti
http.response    HTTP cevap aldi
fs.read          Dosya okudu
fs.write         Dosya yazdi
fs.delete        Dosya sildi
fs.move          Dosya tasidi
job.created      Job olusturdu
job.modified     Job degistirdi
state.updated    State guncelledi
data.parsed      Veri parse etti
output.print     Stdout'a yazdi
```

### 5.3 Tasker = Configurable Save/Print
Tasker plugin'i save ve print'i configurable yapar.
Diğer plugin'ler de services.filesystem ile aynı işlemi yapabilir.

---

## 6. STATE PRENSİPLERİ

### 6.1 Explicit Access Only
State'e erişim her zaman explicit path ile:
```
job.plugins.tmdb.movie.title ✓
movie.title ✗ (magic yok)
```

### 6.2 Alias = Kısayol, Magic Değil
Alias kullanıcı tanımlı kısayol.
Sistem hiçbir alias'ı otomatik oluşturmaz.

---

## 7. EVENT PRENSİPLERİ

### 7.1 Convention-based Naming
```
{domain}.{action}
file.created, file.deleted
plugin.started, plugin.completed
job.created, job.failed
```

### 7.2 Plugin Event Discovery
Plugin manifest'inde emits ile declare eder (opsiyonel, dokümantasyon için).
Asıl emit runtime'da olur.

---

## 8. PLUGIN ILETISIMI

### 8.1 Tek Interface: PluginServices
Tum plugin-core iletisimi tek interface uzerinden:
```
services.state   -> Job/Run okuma yazma
services.events  -> Event emit/subscribe
services.logger  -> Loglama
services.config  -> Config erisimi
```

### 8.2 Global Erisim Yasak
- get_debugger() KULLANILMAZ
- Direkt state erisimi YASAK
- Tum erisim services uzerinden

---

## 9. DEFAULT ALIAS SISTEMI

```
+----------------------------------------------------------+
|  SISTEM TARAFINDAN INJECT EDILEN DEFAULT ALIAS'LAR       |
+----------------------------------------------------------+
|  ALIAS          SOURCE              READONLY?             |
+----------------------------------------------------------+
|  job            GlobalState.job     NO                   |
|  jobs           GlobalState.jobs    YES                  |
|  run            GlobalState.run     YES                  |
|  provides       ProvideRegistry     YES                  |
|  events         EventBus.history    YES                  |
|  config         ConfigLoader        YES                  |
+----------------------------------------------------------+
```

### 9.1 Kullanim
```jinja2
{{ job.plugins.tmdb.movie.title }}
{{ provides.http.response }}
{{ events.file.created }}
```

### 9.2 Kullanici Alias
```yaml
aliases:
  m: job.plugins.tmdb.movie
  p: provides
```

---

## 10. OZET

```
Core      = Dumb + Plugin Agnostik
Config    = Source of Truth + FlexGet Style + !include
Stage     = 4 stage: input/extract/enrich/output
Requires  = Unified (job.* | provides.* | events.*)
Provides  = Islem Bazli (http.response, fs.write)
Plugin    = Tek interface (PluginServices)
Alias     = Sistem inject (job,provides,events) + kullanici
```
