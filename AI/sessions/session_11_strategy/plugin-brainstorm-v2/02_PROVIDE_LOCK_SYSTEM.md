# PROVIDE LOCK SYSTEM

```yaml
tarih: 2025-12-03
durum: brainstorm
odak: fs.write:/path ve job.update lock analizi
```

---

## 1. LOCK TIPLERI

```
+----------------------------------------------------------+
|                    LOCK TIPLERI                           |
+----------------------------------------------------------+
|                                                           |
|  TIP 1: FS LOCK (Dosya Sistemi)                          |
|  fs.write:/data/archive                                  |
|  fs.delete:/data/temp                                    |
|  fs.move:/data/source -> /data/dest                      |
|                                                           |
|  TIP 2: JOB LOCK (State Update)                          |
|  job.update:job.plugins.tmdb.movie.title                 |
|  job.update:job.plugins.renamer.parsed                   |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. FS LOCK DETAYI

### 2.1 Temel Kullanim

```yaml
# manifest.yml
provides:
  - fs.write # Generic (uyari)
  - fs.write:/data/archive # Static path
  - fs.write:{{config.save_path}} # Dynamic (config'den)
```

### 2.2 Tasker Plugin Ozel Durumu

```yaml
# config.yml
tasker:
  tasks:
    - name: save_movie
      type: save
      path: /data/archive/{{tmdb.movie.title}}/{{tmdb.movie.year}}.mkv
    - name: save_show
      type: save
      path: /data/archive/{{tmdb.show.name}}/S{{s}}E{{e}}.mkv

  # Kullanici MANUAL tanimlar (en stabil yontem)
  provides:
    - fs.write:/data/archive
```

**Neden manual?**

```
+----------------------------------------------------------+
|              NEDEN KULLANICI MANUAL TANIMLAR?             |
+----------------------------------------------------------+
|                                                           |
|  SECENEK A: Otomatik path analizi                        |
|  - Task path'lerini parse et                             |
|  - Degisken kisimlarini at                               |
|  - Ortak prefix bul                                      |
|                                                           |
|  SORUN:                                                   |
|  - Jinja2 parser cok karmasik                            |
|  - Edge case'ler cok fazla                               |
|  - /a/{{x}}/b ve /a/{{y}}/c -> ortak kok ne?             |
|  - Stabilite riski yuksek                                |
|                                                           |
|  SECENEK B: Kullanici manual tanimlar (SECILEN)          |
|  - Kullanici provides listesini config'de yazar          |
|  - Ortak kok kullanicinin sorumlulugu                    |
|  - Basit, stabil, test edilebilir                        |
|                                                           |
+----------------------------------------------------------+
```

### 2.3 Path Prefix Cikarma

Eger kullanici dinamik path kullanirsa:

```yaml
provides:
  - fs.write:/data/{{category}}/movies
```

**Render:**

```
/data/{{category}}/movies
      ^^^^^^^^^^^^
      Degisken tespit edildi

Sonuc: fs.write:/data/
       ^^^^^^^^^^^^^^^
       Static prefix
```

```python
def extract_static_prefix(path: str) -> str:
    """Degisken oncesi static prefix cikar"""
    if '{{' not in path:
        return path

    idx = path.index('{{')
    prefix = path[:idx].rstrip('/')
    return prefix if prefix else '/'
```

---

## 3. JOB LOCK ANALIZI

### 3.1 Potansiyel Use Case

```yaml
# Plugin A (tmdb)
provides:
  - job.update:job.plugins.tmdb.movie

# Plugin B (omdb - tmdb verisini zenginlestir)
provides:
  - job.update:job.plugins.tmdb.movie.imdb_id
```

### 3.2 Analiz

```
+----------------------------------------------------------+
|              JOB LOCK GEREKLI MI?                         |
+----------------------------------------------------------+
|                                                           |
|  ARGUMAN 1: GEREKLI                                       |
|  - Ayni state path'e iki plugin yazarsa son yazan kazanir|
|  - Race condition mumkun                                  |
|  - Data inconsistency riski                              |
|                                                           |
|  ARGUMAN 2: GEREKSIZ (SECILEN)                           |
|  - Her plugin kendi namespace'ini yazar                  |
|  - tmdb -> job.plugins.tmdb.*                            |
|  - omdb -> job.plugins.omdb.*                            |
|  - Cross-namespace yazim anti-pattern                    |
|  - requires ile siralama zaten var                       |
|                                                           |
|  SONUC: JOB LOCK GEREKSIZ                                |
|  - fs.write gercek disk I/O, geri alinamaz               |
|  - job.update in-memory, requires ile siralanabilir      |
|  - Her plugin kendi namespace'ine yazsin                 |
|                                                           |
+----------------------------------------------------------+
```

### 3.3 Anti-Pattern Uyarisi

```yaml
# YANLIS: Baska plugin'in datasina yazma
provides:
  - job.update:job.plugins.tmdb.movie.custom_field

# DOGRU: Kendi namespace'ine yaz
provides:
  - state.update   # Generic
```

Eger bir plugin baska plugin'in verisine yaziyorsa:

- requires ile bagimlilik kur
- O plugin tamamlandiktan sonra calis
- Lock degil, siralama cozumu

---

## 4. LOCK SCOPE KARARI

```
+----------------------------------------------------------+
|              SCOPE KARARI                                 |
+----------------------------------------------------------+
|                                                           |
|  FS LOCK: ZORUNLU                                         |
|  - Gercek disk I/O                                       |
|  - Race condition kritik                                  |
|  - Bozuk dosya = geri alinamaz                           |
|                                                           |
|  JOB LOCK: OPSIYONEL/GEREKSIZ                            |
|  - In-memory islem                                       |
|  - requires ile siralanabilir                            |
|  - Namespace izolasyonu yeterli                          |
|                                                           |
|  HTTP LOCK: GEREKSIZ                                      |
|  - Rate limiting ayri konsept                            |
|  - Lock degil, throttling                                |
|                                                           |
+----------------------------------------------------------+
```

---

## 5. FS_LOCK ALTERNATIF SYNTAX

Eger sadece FS lock gerekiyorsa, provides sistemini kirletmemek icin:

### 5.1 Secenek A: Provides Icinde (MEVCUT PLAN)

```yaml
provides:
  - fs.write:/data/archive
```

### 5.2 Secenek B: Ayri Alan (ALTERNATIF)

```yaml
provides:
  - fs.write

fs_lock:
  - /data/archive
  - /data/movies
```

### 5.3 Karsilastirma

```
+----------------------------------------------------------+
|  SECENEK              AVANTAJ              DEZAVANTAJ     |
+----------------------------------------------------------+
|                                                           |
|  A: provides icinde   Tek sistem           Syntax karisik |
|                       Tutarli              :path eki      |
|                                                           |
|  B: fs_lock alani     Temiz ayrim          Iki alan       |
|                       Acik intent          Tekrar         |
|                                                           |
+----------------------------------------------------------+

KARAR: SECENEK A (provides icinde)
- Tek unified sistem
- PHILOSOPHY.md ile uyumlu
- Daha az alan, daha az karisiklik
```

---

## 6. PROVIDES LOCK REGISTRY

```python
class ProvideLockRegistry:
    """Lockable provides kayit ve tespit"""

    # Hangi provides lock destekler?
    LOCKABLE = {
        'fs.write': True,
        'fs.delete': True,
        'fs.move': True,
        'fs.hardlink': True,
        'fs.symlink': True,
    }

    # Hangi provides KESINLIKLE lock gerektirmez?
    NON_LOCKABLE = {
        'fs.read',
        'http.request',
        'job.create',
        'state.update',
        'process.spawn',
        'process.exec',
    }

    def is_lockable(self, provide: str) -> bool:
        base = provide.split(':')[0]
        return base in self.LOCKABLE

    def parse_lock_path(self, provide: str) -> Optional[str]:
        """fs.write:/path -> /path"""
        if ':' not in provide:
            return None
        _, path = provide.split(':', 1)
        return self._strip_variables(path)

    def _strip_variables(self, path: str) -> str:
        """Degisken oncesi prefix"""
        if '{{' not in path:
            return path
        return path[:path.index('{{')].rstrip('/')
```

**Uyari:** Ornek kod, yaklasimi gosterir. Execution session'da mevcut codebase'e uyarlanmalidir.

---

## 7. CONFIG VALIDATION RULES

```
+----------------------------------------------------------+
|              VALIDATION KURALLARI                         |
+----------------------------------------------------------+
|                                                           |
|  KURAL 1: Dinamik degisken kontrolu                      |
|  - {{config.*}} -> GECERLI                               |
|  - {{job.*}} -> GECERSIZ (runtime degeri)                |
|  - {{run.*}} -> GECERSIZ (runtime degeri)                |
|                                                           |
|  KURAL 2: Path format kontrolu                           |
|  - Mutlak path olmali (/ ile baslamali)                  |
|  - Relative path UYARI                                   |
|                                                           |
|  KURAL 3: Bos path kontrolu                              |
|  - fs.write: -> UYARI (generic, conflict riski)          |
|  - fs.write:/path -> OK                                  |
|                                                           |
+----------------------------------------------------------+
```

---

## 8. SONUC

```
+----------------------------------------------------------+
|              FINAL KARARLAR                               |
+----------------------------------------------------------+
|                                                           |
|  FS LOCK:                                                 |
|  - EVET, provides icinde syntax: fs.write:/path          |
|  - Dynamic: {{config.*}} GECERLI                         |
|  - Dynamic: {{job.*}} GECERSIZ                           |
|  - Static prefix cikarma: /a/{{x}}/b -> /a               |
|  - Tasker icin kullanici manual tanimlar                 |
|                                                           |
|  JOB LOCK:                                                |
|  - HAYIR, gereksiz                                       |
|  - Namespace izolasyonu yeterli                          |
|  - requires ile siralama cozum                           |
|                                                           |
|  SYNTAX:                                                  |
|  - provides icinde tutulacak (ayri alan yok)             |
|  - : ile path eklenir                                    |
|                                                           |
+----------------------------------------------------------+
```

---

**Son Guncelleme:** 2025-12-03
