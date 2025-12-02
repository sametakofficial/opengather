# PROVIDES SYSTEM

```yaml
tarih: 2025-12-02
durum: final
kritik: Bu dosya provides degerlerinin felsefesini tanimlar
```

---

## 1. CURRENT (Reddedilen)

```yaml
# 15_final_architecture.md'deki degerler
provides:
  - input.files
  - parsed.movie
  - parsed.show
  - metadata.movie
  - metadata.show
  - output.moved
  - output.copied
```

Sorunlar:
- Kategori bazli (metadata.movie = kategori)
- Plugin agnostik ihlali (movie = archiverr-specific)
- Stage ile karisik (input, output prefix)

---

## 2. FEATURE

```yaml
# Islem bazli provides
provides:
  - http.request
  - http.response
  - fs.read
  - fs.write
  - fs.delete
  - fs.move
  - job.created
  - metadata.parsed
  - metadata.movie
  - metadata.show
  - notification.sent
```

---

## 3. WHY

### Felsefe

```
+----------------------------------------------------------+
|              PROVIDES FELSEFESI                           |
+----------------------------------------------------------+
|                                                           |
|  SORU: provides ne icin var?                             |
|                                                           |
|  CEVAP:                                                  |
|    1. Execution ordering (DAG)                           |
|    2. Plugin capability declaration                      |
|    3. Trust-based security (ne yaptigini soyle)          |
|                                                           |
|  SORU: "metadata" provides olabilir mi?                  |
|                                                           |
|  CEVAP: HAYIR                                            |
|    - "metadata" kategoridir, islem degildir              |
|    - "http.response" islemdir                            |
|    - Kategori = stage, islem = provides                  |
|                                                           |
+----------------------------------------------------------+
```

### Endustri Ornekleri

```
SISTEM              CAPABILITY ORNEKLERI
--------------------------------------------------
Linux capabilities  CAP_NET_BIND_SERVICE
                    CAP_SYS_ADMIN
                    CAP_DAC_OVERRIDE

AWS IAM             s3:GetObject
                    ec2:RunInstances
                    lambda:InvokeFunction

OSGi                osgi.service
                    osgi.wiring.package
                    osgi.wiring.bundle

Android             android.permission.INTERNET
                    android.permission.READ_STORAGE
                    android.permission.CAMERA
```

Ortak Ozellik: Islem/eylem bazli, kaynak/kategori degil.

---

## 4. SCHEMA

### Provides Taxonomy

```
                    PROVIDES
                       |
       +---------------+---------------+
       |               |               |
       v               v               v
      HTTP            FS             JOB
       |               |               |
       v               v               v
  http.request     fs.read        job.created
  http.response    fs.write
                   fs.delete
                   fs.move

       +---------------+---------------+
       |               |               |
       v               v               v
   METADATA       NOTIFICATION     CUSTOM
       |               |               |
       v               v               v
  metadata.parsed notification.sent custom.*
  metadata.movie
  metadata.show
```

### Standart Provides Listesi

```
+----------------------------------------------------------+
|                 STANDART PROVIDES                         |
+----------------------------------------------------------+
|                                                           |
|  HTTP                                                     |
|  http.request       Dis API'ye istek yapti               |
|  http.response      Dis API'den cevap aldi               |
|                                                           |
|  FS (Filesystem)                                          |
|  fs.read            Dosya/dizin okudu                    |
|  fs.write           Dosya yazdi/kopyaladi                |
|  fs.delete          Dosya sildi                          |
|  fs.move            Dosya tasidi                         |
|                                                           |
|  JOB                                                      |
|  job.created        Yeni job olusturdu                   |
|                                                           |
|  METADATA                                                 |
|  metadata.parsed    Dosya adi parse edildi               |
|  metadata.movie     Film metadata alindi                 |
|  metadata.show      Dizi metadata alindi                 |
|                                                           |
|  NOTIFICATION                                             |
|  notification.sent  Bildirim gonderildi                  |
|                                                           |
+----------------------------------------------------------+
```

---

## 5. KULLANIM ORNEKLERI

### Scanner

```yaml
provides:
  - job.created    # Yeni job'lar olusturuyor
  - fs.read        # Dizin okuyor
```

### Renamer

```yaml
provides:
  - metadata.parsed     # Dosya adi parse edildi
```

### TMDb

```yaml
requires:
  - metadata.parsed     # Renamer'in parse sonucu

provides:
  - http.response       # TMDb'den cevap
  - metadata.movie      # Film metadata
```

### Tasker

```yaml
requires:
  - http.response       # Metadata gerekli

provides:
  - fs.write            # Dosya kopyaladi/tasidi
```

---

## 6. DAG EXECUTION

```
              PROVIDES-BASED EXECUTION ORDER

  scanner                renamer                 tmdb
     |                      |                      |
provides:               stage:                 requires:
job.created             extract                metadata.parsed
fs.read                 (input sonrasi)            |
     |                      |                      v
     +----> INPUT DONE ---->+----> SATISFIED ----->+
                            |                      |
                        provides:              provides:
                        metadata.parsed        http.response
                            |                  metadata.movie
                            v                      |
                        COMPLETE                   v
                                              COMPLETE
                                                   |
                                                   v
                                              tasker
                                                   |
                                              requires:
                                              http.response
                                                   |
                                                   v
                                              SATISFIED -> EXECUTE
```

---

## 7. REQUIRES VS PROVIDES

```
+----------------------------------------------------------+
|              REQUIRES vs PROVIDES                         |
+----------------------------------------------------------+
|                                                           |
|  requires                                                 |
|  - NE: provides degeri, state path veya plugin adi       |
|  - AMAÇ: Bu olmadan baslamam                             |
|  - ORNEK: requires: [metadata.parsed, http.response]     |
|                                                           |
|  provides                                                 |
|  - NE: Standart terimlerden islem                        |
|  - AMAÇ: Ben bunu yapiyorum (declaration)                |
|  - ORNEK: provides: [http.response, fs.write]            |
|                                                           |
+----------------------------------------------------------+

NOT: after, waits_for, depends_on, triggers_on KALDIRILDI.
     Hepsi requires icinde UNIFIED.
     Bkz: 09_REQUIRES_SYSTEM.md
```

---

## 8. VALIDATION

```python
VALID_PROVIDES = {
    # HTTP
    "http.request",
    "http.response",
    
    # Filesystem
    "fs.read",
    "fs.write",
    "fs.delete",
    "fs.move",
    
    # Job
    "job.created",
    
    # Metadata
    "metadata.parsed",
    "metadata.movie",
    "metadata.show",
    
    # Notification
    "notification.sent",
}

# Not: Ornek kod, direkt kullanilmaz.
```

---

## 9. CUSTOM PROVIDES

```yaml
# Plugin kendi provides degeri tanimlayabilir
# Prefix: custom.*

provides:
  - custom.ai.detection
  - custom.subtitle.extracted
```

Kurallar:
- custom.* prefix zorunlu
- Standart listede olmayan deger = hata (custom olmadan)
- Custom provides diger plugin'ler tarafindan require edilebilir

---

## 10. EARLY COMPLETION (Phase 2)

```
KONSEPT: Plugin bitmeden provides tamamlandi bildirimi

ORNEK:
  - TMDb 60sn calisiyor
  - http.response 10sn'de tamamlandi
  - Kalan 50sn ekstra islem (credits, images)
  - Tasker 10sn'de baslamali, 60sn beklememeli

IMPLEMENTATION:

  class TMDbPlugin(BasePlugin):
      def execute(self, job, services):
          # API cagri
          movie = self.fetch_movie(...)
          
          # http.response tamamlandi
          services.provides.complete("http.response")
          
          # Ekstra islemler (credits, images)
          credits = self.fetch_credits(...)
          images = self.fetch_images(...)
          
          return result

KARAR: Phase 2'de implement edilebilir.
       Ilk versiyonda zorunlu degil.
       Performans optimizasyonu olarak dusunulebilir.

Not: Direkt execution'da kullanilmaz, sadece
konsept gosterimi icin yazilmistir.
```
