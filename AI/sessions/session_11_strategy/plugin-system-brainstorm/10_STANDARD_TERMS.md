# STANDARD TERMS (Provides & Requires)

```yaml
tarih: 2025-12-02
durum: final
amac: Provides ve Requires icin standart terimler
```

---

## 1. PROVIDES KATEGORILERI

```
+----------------------------------------------------------+
|  KATEGORI         TERIMLER                                |
+----------------------------------------------------------+
|  HTTP             http.request                           |
|                   http.response                          |
|                                                           |
|  FS               fs.read                                |
|                   fs.write                               |
|                   fs.delete                              |
|                   fs.move                                |
|                                                           |
|  JOB              job.created                            |
|                                                           |
|  METADATA         metadata.parsed                        |
|                   metadata.movie                         |
|                   metadata.show                          |
|                                                           |
|  NOTIFICATION     notification.sent                      |
+----------------------------------------------------------+
```

---

## 2. PROVIDES DETAYLI LISTE

### HTTP (External API calls)

| Terim | Anlam | Ornek Plugin |
|-------|-------|--------------|
| `http.request` | HTTP istegi yapildi | - |
| `http.response` | HTTP yaniti alindi | tmdb, tvdb |

### FS (File System)

| Terim | Anlam | Ornek Plugin |
|-------|-------|--------------|
| `fs.read` | Dosya okundu | scanner |
| `fs.write` | Dosya yazildi | tasker |
| `fs.delete` | Dosya silindi | cleaner |
| `fs.move` | Dosya tasindi | organizer |

### JOB (Job State)

| Terim | Anlam | Ornek Plugin |
|-------|-------|--------------|
| `job.created` | Yeni job olusturuldu | scanner |
| `job.updated` | Job guncellendi | - |

### METADATA (Parsed Data)

| Terim | Anlam | Ornek Plugin |
|-------|-------|--------------|
| `metadata.parsed` | Dosya adi parse edildi | renamer |
| `metadata.movie` | Film metadata alindi | tmdb |
| `metadata.show` | Dizi metadata alindi | tvdb |
| `metadata.episode` | Bolum metadata alindi | tvdb |

### NOTIFICATION

| Terim | Anlam | Ornek Plugin |
|-------|-------|--------------|
| `notification.sent` | Bildirim gonderildi | notifier |

---

## 3. REQUIRES TURLERI

```
+----------------------------------------------------------+
|  TUR              NASIL ANLASILIR          ORNEK          |
+----------------------------------------------------------+
|  state            job.* veya run.*         job.input.path |
|                   ile baslar                              |
|                                                           |
|  provide          Provides listesinde      http.response  |
|                   kayitli                  metadata.movie |
|                                                           |
|  plugin           Plugin discovery'de      renamer        |
|                   mevcut                   tmdb           |
+----------------------------------------------------------+

Parser otomatik ayirir - prefix yazilmaz.
```

---

## 4. REQUIRES ORNEKLERI

```yaml
# State bekle (job.* ile baslar)
requires:
  - job.input.path
  - job.plugins.renamer.parsed

# Provide bekle (provides listesinde)
requires:
  - metadata.parsed
  - http.response

# Plugin bekle (plugin adi)
requires:
  - renamer
  - tmdb
```

---

## 5. TRIGGER RULE

```
AIRFLOW TRIGGER RULES:
  all_success   - Tum upstream SUCCESS (default)
  one_success   - En az biri SUCCESS
  all_done      - Hepsi EXECUTED (success/fail farketmez)
  always        - Upstream durumuna bakmadan calistir

Kaynak: https://airflow.apache.org/
NOT: Airflow'da bir task'a sadece BIR trigger_rule atanabilir.
```

```
+----------------------------------------------------------+
|  ARCHIVERR TRIGGER RULES                                  |
+----------------------------------------------------------+
|  RULE             SEMANTIK                                |
+----------------------------------------------------------+
|  all_success      Tum requires SUCCESS (default)         |
|  one_success      En az biri SUCCESS                     |
|  always           Stage gelince hemen calistir           |
+----------------------------------------------------------+

KALDIRILDI:
  - all_complete (all_success ile ayni)
  - all_done (kullanim alani yok)
  - one_complete (one_success ile ayni)
```

---

## 6. REACTIVE MODE (on_change yerine)

```
+----------------------------------------------------------+
|  REACTIVE MODE                                            |
+----------------------------------------------------------+
|                                                           |
|  trigger_rule != reactive mode                           |
|                                                           |
|  trigger_rule: NE ZAMAN calistirilacak                   |
|  reactive: TEKRAR calistirilacak mi                      |
|                                                           |
|  Ayri alan olarak tanimlanmali:                          |
|    reactive: true                                        |
|                                                           |
+----------------------------------------------------------+
```

### Manifest Ornegi

```yaml
name: watcher
stage: output
requires:
  - job.plugins.tmdb.movie
trigger_rule: all_success             # Ne zaman
reactive: true                        # Tekrar calistir
provides:
  - notification.sent
```

---

## 7. MANIFEST ALAN OZETI

```yaml
# Zorunlu
name: string
version: string
stage: input | extract | enrich | output

# Dependency
requires: []                          # Liste (implicit parsing)
provides: []                          # Liste (standart terimler)

# Execution
trigger_rule: all_success             # Default
reactive: false                       # Default

# Implementation
class_name: string
entry_point: string                   # Default: client.py
```

---

## CHANGELOG

```
2025-12-02:
  - Standart provides terimleri tanimlandi
  - Requires turleri (state, provide, plugin) aciklandi
  - Trigger rule sadeleştirildi (all_success, one_success, always)
  - on_change -> reactive: true olarak ayrildi
```
