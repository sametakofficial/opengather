# PROVIDES & REQUIRES SISTEMI

```yaml
tarih: 2025-12-02
durum: final
amac: Teknik etki bazli provides ve requires sistemi
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- input.value, input.data, output.values, output.data provides eklendi
- lockable: fs.write, fs.delete, fs.move, fs.hardlink, fs.symlink (5 adet)
- non-lockable: fs.copy, fs.mkdir, fs.chmod, state.update, job.create
- provides icinde job.* ve run.* YASAK
- process.spawn, process.exec eklendi
```

---

## 1. PROVIDES FELSEFESI

```
+----------------------------------------------------------+
|                    PROVIDES FELSEFESI                     |
+----------------------------------------------------------+
|                                                           |
|  PROVIDES = GERCEK TEKNIK ETKI                           |
|                                                           |
|  Bir provide degeri su ozelliklere sahip OLMALI:         |
|                                                           |
|  1. GERCEK ETKI: Sistemde fiziksel bir degisiklik        |
|     - Dosya yazildi, silindi, tasindi                    |
|     - Network istegi yapildi                             |
|     - Process calistirildi                               |
|                                                           |
|  2. TEKNIK DEGER: Olcuelebilir bir islem                 |
|     - Bandwidth kullanimi (http.request)                 |
|     - Disk I/O (fs.write)                                |
|     - CPU/Memory (process.spawn)                         |
|                                                           |
|  3. DIS DUNYA ETKISI: Geri alinamaz veya takip edilebilir|
|     - API rate limit etkisi                              |
|     - Dosya sistemi degisikligi                          |
|                                                           |
+----------------------------------------------------------+

GECERSIZ PROVIDES (KALDIRILAN):
  - metadata.parsed   # Kategori, teknik etki degil
  - metadata.movie    # Sadece state update, fs/http degil
  - notification.sent # Belirsiz, hangi kanal?
  - data.parsed       # Kategori

GECERLI PROVIDES:
  - fs.write          # Dosya yazildi (gercek etki)
  - http.request      # Network istegi (bandwidth)
  - job.create        # Yeni job olusturuldu (state degisimi)
```

---

## 2. PROVIDES LISTESI

### FS (File System Operations)

```
+----------------------------------------------------------+
|  PROVIDE          ANLAM                    ORNEK PLUGIN   |
+----------------------------------------------------------+
|  fs.read          Dosya okundu             scanner        |
|  fs.write         Dosya yazildi            tasker         |
|  fs.delete        Dosya silindi            cleaner        |
|  fs.move          Dosya tasindi            organizer      |
|  fs.copy          Dosya kopyalandi         backup         |
|  fs.hardlink      Hardlink olusturuldu     linker         |
|  fs.symlink       Symlink olusturuldu      linker         |
|  fs.mkdir         Dizin olusturuldu        organizer      |
|  fs.chmod         Izinler degistirildi     fixer          |
+----------------------------------------------------------+
```

### HTTP (Network Operations)

```
+----------------------------------------------------------+
|  PROVIDE          ANLAM                    ORNEK PLUGIN   |
+----------------------------------------------------------+
|  http.request     HTTP istegi yapildi      tmdb, tvdb     |
|                   (GET/POST/PUT/DELETE)                   |
+----------------------------------------------------------+

NOT: http.response KALDRILDI
  - response istek sonucudur, ayri provide degil
  - Bir plugin http.request yaparsa response zaten var
```

### JOB (Job Lifecycle)

```
+----------------------------------------------------------+
|  PROVIDE          ANLAM                    ORNEK PLUGIN   |
+----------------------------------------------------------+
|  job.create       Yeni job olusturuldu     scanner        |
+----------------------------------------------------------+

NOT: job.update KALDRILDI
  - Her plugin zaten job'u update eder
  - state.update ile karisir
```

### STATE (State Operations)

```
+----------------------------------------------------------+
|  PROVIDE          ANLAM                    ORNEK PLUGIN   |
+----------------------------------------------------------+
|  state.update     State guncellendi        tum pluginler  |
+----------------------------------------------------------+

NOT: Fiil formu kullanildi (update, updated degil)
  - "update" = eylem
  - "updated" = durum (past tense)
  - Provides eylem bildirir
```

### PROCESS (External Process)

```
+----------------------------------------------------------+
|  PROVIDE          ANLAM                    ORNEK PLUGIN   |
+----------------------------------------------------------+
|  process.spawn    Dis process calistirildi ffprobe        |
|  process.exec     Komut execute edildi     custom scripts |
+----------------------------------------------------------+
```

### GELECEK PROVIDES (Henuz implement edilmedi)

```
+----------------------------------------------------------+
|  PROVIDE          ANLAM                    KULLANIM       |
+----------------------------------------------------------+
|  db.query         Database sorgusu         sqlite, mongo  |
|  cache.read       Cache okundu             redis, memory  |
|  cache.write      Cache yazildi            redis, memory  |
|  queue.publish    Queue'ya mesaj gonderdi  rabbitmq       |
|  queue.consume    Queue'dan mesaj aldi     rabbitmq       |
+----------------------------------------------------------+
```

---

## 3. PROVIDES COMPLETION (ERKEN TAMAMLAMA)

```
+----------------------------------------------------------+
|                    PROVIDES COMPLETION                    |
+----------------------------------------------------------+
|                                                           |
|  PROBLEM:                                                 |
|  Plugin hem http.request hem fs.write yapiyor            |
|  http.request 1 saniye, fs.write 30 saniye suruyor       |
|  http.request bekleyen pluginler 30 saniye bekliyor      |
|                                                           |
|  COZUM: Partial Provides Completion                      |
|  Plugin kendi provide degerlerini AYRI AYRI complete     |
|  edebilir.                                               |
|                                                           |
+----------------------------------------------------------+

IMPLEMENTATION:

  class PluginServices:
      def complete_provide(self, provide: str) -> None:
          """Belirli bir provide'i erken tamamla"""
          self._provides_registry.complete(
              plugin=self.plugin_name,
              provide=provide
          )

KULLANIM:

  class TMDbPlugin:
      async def execute(self, job, services):
          # HTTP istegi yap
          response = await self.fetch_metadata(job)

          # http.request tamamlandi, bekleyenler baslasin
          services.complete_provide("http.request")

          # Yavasta artwork indir
          await self.download_artwork(response)

          # fs.write tamamlandi
          services.complete_provide("fs.write")

          return PluginResult.success(response)

FAYDALAR:
  - Pipeline hizlanir
  - Paralel calisma artar
  - Resource kullanimi optimize olur
```

---

## 4. REQUIRES PREFIX SISTEMI

```
+----------------------------------------------------------+
|                    REQUIRES PREFIX                        |
+----------------------------------------------------------+
|                                                           |
|  PREFIX           KAYNAK              SEMANTIK            |
|  ------           ------              --------            |
|  provides.*       ProvideRegistry     Provide tamamlansin |
|  job.*            StateManager        State path dolu     |
|  events.*         EventBus            Event emit edilsin  |
|                                                           |
+----------------------------------------------------------+

ZORUNLU: Prefix her zaman yazilmali
REDDEDILEN: Implicit parsing (belirsizlik yaratir)
```

### Ornekler

```yaml
# DOGRU: Explicit prefix
requires:
  - provides.http.request
  - provides.fs.write
  - job.input.path
  - job.plugins.renamer.parsed
  - events.job.created

# YANLIS: Prefix yok
requires:
  - http.request          # provides.http.request olmali
  - renamer               # job.plugins.renamer olmali
  - job.created           # events.job.created olmali
```

---

## 5. TRIGGER RULES

```
+----------------------------------------------------------+
|                    TRIGGER RULES                          |
+----------------------------------------------------------+
|                                                           |
|  RULE              SEMANTIK                               |
|  ----              --------                               |
|  all_success       Tum requires SUCCESS (default)        |
|  one_success       En az biri SUCCESS                    |
|  all_done          Hepsi DONE (success/fail farketmez)   |
|  all_fail          Hepsi FAIL                            |
|  none_fail         Hicbiri FAIL degil                    |
|  always            Requires bakmadan calistir            |
|                                                           |
+----------------------------------------------------------+

KAYNAK: Apache Airflow trigger rules
https://airflow.apache.org/docs/apache-airflow/stable/

ONEMLI: Airflow'da tek trigger_rule atanir.
Bizde de ayni - reactive ayri konsept.
```

### Trigger Rule Ornekleri

```yaml
# Default: Tum requires basarili olsun
trigger_rule: all_success

# Fallback: Biri basarili olsa yeter
trigger_rule: one_success

# Cleanup: Basarisiz olsa bile calistir
trigger_rule: all_done

# Error handler: Sadece hata varsa
trigger_rule: all_fail

# Logger: Her zaman calistir
trigger_rule: always
```

---

## 6. REACTIVE MODE

```
+----------------------------------------------------------+
|                    REACTIVE MODE                          |
+----------------------------------------------------------+
|                                                           |
|  TANIM: State degistiginde plugin'i tekrar calistir      |
|  KAPSAM: Sadece per_run pluginler icin                   |
|                                                           |
|  trigger_rule: NE ZAMAN calistirilacak                   |
|  reactive: TEKRAR calistirilacak mi                      |
|                                                           |
+----------------------------------------------------------+

KULLANIM SENARYOLARI:

  1. Summary Plugin (per_run + reactive):
     - Tum joblar bittikten sonra calis (trigger_rule: all_done)
     - Her job tamamlandiginda tekrar calis (reactive: true)

  2. Watcher Plugin (per_run + reactive):
     - State degistiginde notification gonder

  3. Progress Plugin (per_run + reactive):
     - Progress bar guncelle

MANIFEST:

  name: summary
  stage: output
  mode: per_run
  requires:
    - provides.state.update
  trigger_rule: all_done
  reactive: true

NOT: per_job pluginler icin reactive anlamsiz
     (zaten her job icin ayri calisir)
```

---

## 7. RUN ASLA DURMASIN

```
+----------------------------------------------------------+
|                    ERROR HANDLING                         |
+----------------------------------------------------------+
|                                                           |
|  FELSEFE: Run ASLA durmasin                              |
|                                                           |
|  PLUGIN FAIL:                                             |
|    - Job FAIL olmaz                                      |
|    - Diger pluginler devam eder                          |
|    - Requires karsilanmayan pluginler SKIP               |
|                                                           |
|  STAGE FAIL:                                              |
|    - Sonraki stage devam eder                            |
|    - Requires karsilanan pluginler calisir               |
|                                                           |
|  RUN FAIL:                                                |
|    - Sadece kritik hata (config yok, vb.)               |
|    - Normal plugin hatalari run'i durdurmaz              |
|                                                           |
+----------------------------------------------------------+

GEREKCE:
  - Bozuk metadata plugin tum sistemi baltalamamali
  - Log pluginleri her zaman calisabilmeli
  - all_fail trigger ile error handler yazilabilmeli
  - Partial success kabul edilebilir
```

---

## 8. MANIFEST OZETI

```yaml
# Kimlik
name: string
version: string
stage: input | parse | data | output

# Dependency
requires:
  - provides.* # Provide bekle
  - job.* # State bekle
  - events.* # Event bekle
provides:
  - fs.* # File system
  - http.request # Network
  - job.create # Job lifecycle
  - state.update # State update
  - process.* # External process

# Execution
trigger_rule: all_success | one_success | all_done | all_fail | none_fail | always
reactive: true | false # Sadece per_run icin

# Implementation
class_name: string
entry_point: string # Default: client.py
```

---

## CHANGELOG

```
2025-12-02 v2:
  - KALDIRILAN: metadata.*, notification.*, data.*
  - KALDIRILAN: http.response (http.request yeterli)
  - EKLENEN: fs.copy, fs.hardlink, fs.symlink, fs.mkdir, fs.chmod
  - EKLENEN: process.spawn, process.exec
  - EKLENEN: Provides early completion (complete_provide)
  - EKLENEN: Explicit prefix zorunlulugu (provides.*, job.*, events.*)
  - EKLENEN: all_done, all_fail, none_fail trigger rules
  - GUNCELLENEN: state.updated -> state.update (fiil formu)
  - GUNCELLENEN: job.created -> job.create (fiil formu)
  - GUNCELLENEN: Run asla durmasin felsefesi
```
