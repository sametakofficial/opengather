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

| PREFIX       | SOURCE          | SEMANTIK                        |
| ------------ | --------------- | ------------------------------- |
| `job.*`      | GlobalState     | Path dolu olana kadar bekle     |
| `provides.*` | ProvideRegistry | Provide tamamlanana kadar bekle |
| `events.*`   | EventBus        | Event emit edilene kadar bekle  |

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

KATEGORI BAZLI DEGIL - TEKNIK ETKI BAZLI:

```
YANLIS: provides: [metadata.movie]   # Kategori, etki yok
DOGRU:  provides: [http.request]     # Teknik etki var
DOGRU:  provides: [fs.write]         # Disk etkisi var
```

Standart provides degerleri:

```
# File System (gercek disk etkisi)
fs.read          Dosya okudu
fs.write         Dosya yazdi
fs.delete        Dosya sildi
fs.move          Dosya tasidi
fs.copy          Dosya kopyaladi
fs.hardlink      Hardlink olusturdu
fs.symlink       Symlink olusturdu
fs.mkdir         Dizin olusturdu

# Network (bandwidth etkisi)
http.request     HTTP istek yapti

# State (job lifecycle)
job.create       Yeni job olusturdu
state.update     State guncelledi

# Process (CPU/memory etkisi)
process.spawn    Dis process calistirdi
process.exec     Komut execute etti
```

KALDIRILAN (kategori bazli, teknik etki yok):

```
metadata.parsed  -> state.update kullan
metadata.movie   -> state.update kullan
notification.*   -> belirsiz, spesifik provide kullan
data.*           -> kategori, teknik degil
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

## 10. CONFIG/MANIFEST ILISKISI

### 10.1 Temel Prensip

```
config.yml  = KAYNAK (kullanici tanimli, override eder)
manifest.yml = DEFAULT (plugin tanimli, base degerler)

Merge: deep_merge(manifest, config) = config KAZANIR
```

### 10.2 Immutable Fields (Degistirilemez)

```
name, version, stage, class_name, entry_point
```

Bu alanlar manifest.yml'de tanimlanir, config.yml override EDEMEZ.

### 10.3 Mutable Fields (Degistirilebilir)

```
requires, provides, trigger_rule, reactive, config_schema alanlari
```

Bu alanlar config.yml ile override edilebilir.

### 10.4 Merge Kurallari

```
1. manifest.yml once okunur (base)
2. config.yml uzerine yazilir (override)
3. Ayni key = config kazanir
4. Nested dict = recursive merge
5. List = replace (extend degil)
```

---

## 11. CONFLICT DETECTION

### 11.1 Lockable Provides

```
LOCKABLE (conflict yaratabilir):
  fs.write, fs.delete, fs.move, fs.copy, fs.hardlink, fs.symlink

NON-LOCKABLE (paralel calisabilir):
  fs.read, http.request, job.create, state.update, process.spawn
```

### 11.2 Provides Lock Syntax

```yaml
provides:
  - fs.write # Generic (lock yok)
  - fs.write:/data/archive # Static lock
  - fs.write:{{config.save_path}} # Dynamic lock (config'den)
```

### 11.3 Conflict Davranisi

```
Ayni lockable path + ayni stage + paralel execution = CONFLICT

CONFLICT tespit edildiginde:
  1. WARNING/ERROR (mode'a gore)
  2. --force ile bypass
  3. requires ekleyerek serialize

Dinamik path'ler icin:
  - Static prefix cikarilir (/data/{{x}}/file -> /data/)
  - Prefix match = WARNING (error degil)
```

### 11.4 Dinamik Degisken Yasagi

```
PROVIDES LOCK ICIN:
  {{config.*}}  -> GECERLI (startup'ta cozulur)
  {{job.*}}     -> GECERSIZ (runtime degeri)
  {{run.*}}     -> GECERSIZ (runtime degeri)

SEBEP:
  - Conflict detection STARTUP'ta calisir
  - job.* ve run.* RUNTIME'da olusur
  - Startup'ta bu degerler YOK
  - Conflict detection YAPILAMAZ
```

### 11.5 Job Lock Gereksizligi

```
FS LOCK: Zorunlu (gercek disk I/O, geri alinamaz)
JOB LOCK: Gereksiz (in-memory, requires ile siralanabilir)

Her plugin KENDI namespace'ine yazmali:
  tmdb -> job.plugins.tmdb.*
  omdb -> job.plugins.omdb.*

Cross-namespace yazim = Anti-pattern
```

---

## 12. VALIDATION PRENSIPLERI

### 12.1 Validation Katmanlari

```
STARTUP:
  - Config/manifest parse
  - Schema validation
  - Conflict detection
  - Dinamik degisken check
  -> Hata = Exit veya component disable

PRE-EXECUTION:
  - Requires satisfaction
  - Plugin initialization
  -> Hata = Plugin skip

RUNTIME:
  - Template rendering
  - File operations
  -> Hata = Log ve devam (run durmasin)
```

### 12.2 Early Fail Prensibi

```
Startup detection > Runtime detection
- Erken hata = az israf
- Kullanici hizli feedback alir
- Rollback karmasikligi yok
```

---

## 13. INPUT/OUTPUT YAPISI

### 13.1 path -> value (Virtual Destek)

```
input.path  -> input.value
output.paths -> output.values

SEBEP:
- Sadece fiziksel dosya degil, virtual entity destegi
- "The Matrix 1999" gibi arama query'leri
- tmdb://movie/603 gibi virtual referanslar
```

### 13.2 Job Structure

```yaml
job:
  input:
    value: "/path/file.mkv" # veya virtual: "Movie Title 2024"
    data: {} # Input plugin'in ek datasi

  output:
    values: [] # Cikti path/deger listesi (array)
    data: {} # Output plugin'in raw datasi

  plugins:
    scanner: {} # input.data ile AYNI
    tasker: {} # output.data ile AYNI
```

### 13.3 Plugin Data Lokasyonu

```
input.data = job.plugins.{input_plugin}
output.data = job.plugins.{output_plugin}

SEBEP:
- Sistem tarafindan KNOWN lokasyon (input.*, output.*)
- Plugin-specific lokasyon (plugins.*)
- Otomatik mapping gereksiz
- Query kolayligi
```

### 13.4 Phase Kurallari

```
INPUT:  Job olustur, value+data doldur
PARSE:  Analiz, dosya KAYDETME
DATA:   Analiz, cache KAYDEDEBILIR (ffprobe), ana dosya KAYDETME
OUTPUT: Cikti olustur, values+data doldur, dosya KAYDEDER
```

---

## 14. OZET

```
Core      = Dumb + Plugin Agnostik
Config    = Source of Truth + FlexGet Style + !include
Manifest  = Default, config override eder (immutable fields haric)
Stage     = 4 stage: input/parse/data/output
Requires  = Unified (job.* | provides.* | events.*)
Provides  = Teknik Etki (fs.write, http.request, job.create)
Conflict  = Lockable provides (fs.write, fs.delete) path-based lock
Plugin    = Tek interface (PluginServices)
Alias     = Sistem inject (job,provides,events) + kullanici
Run       = ASLA durmasin (plugin fail != job fail)
Input     = value (virtual destegi) + data (plugin datasi)
Output    = values (cikti listesi) + data (task sonuclari)
```
