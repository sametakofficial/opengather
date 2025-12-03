# CONFLICT DETECTION SISTEMI

```yaml
tarih: 2025-12-03
durum: brainstorm
kaynak: session_11_strategy, PHILOSOPHY.md
```

---

## 1. PROBLEM TANIMI

```
+----------------------------------------------------------+
|                    CONFLICT SENARYOSU                     |
+----------------------------------------------------------+
|                                                           |
|  SENARYO 1: Ayni klasore yazan iki plugin                |
|                                                           |
|  tasker:                                                  |
|    provides: [fs.write:/data/movies]                     |
|                                                           |
|  custom_saver:                                            |
|    provides: [fs.write:/data/movies]                     |
|                                                           |
|  Ikisi de DATA stage'de, paralel calisacak               |
|  SONUC: Race condition, dosya bozulmasi                  |
|                                                           |
+----------------------------------------------------------+
|                                                           |
|  SENARYO 2: Ayni state path'i update eden iki plugin     |
|                                                           |
|  tmdb_extended:                                           |
|    provides: [job.update:job.plugins.tmdb.movie.title]   |
|                                                           |
|  omdb:                                                    |
|    provides: [job.update:job.plugins.tmdb.movie.title]   |
|                                                           |
|  SONUC: Hangisinin degeri gecerli? Belirsiz.             |
|                                                           |
+----------------------------------------------------------+
```

---

## 2. LOCKABLE VS NON-LOCKABLE PROVIDES

```
+----------------------------------------------------------+
|              LOCKABLE (CONFLICT YARATABILIR)              |
+----------------------------------------------------------+
|                                                           |
|  FS OPERASYONLARI:                                        |
|  fs.write        Dosya yazdi                             |
|  fs.delete       Dosya sildi                             |
|  fs.move         Dosya tasidi                            |
|  fs.hardlink     Hardlink olusturdu                      |
|  fs.symlink      Symlink olusturdu                       |
|                                                           |
+----------------------------------------------------------+

+----------------------------------------------------------+
|              NON-LOCKABLE (PARALEL GUVENLI)               |
+----------------------------------------------------------+
|                                                           |
|  fs.read         100 plugin okuyabilir, sorun yok        |
|  http.request    Rate limit disinda paralel guvenli      |
|  job.create      Her plugin kendi job'unu olusturur      |
|  state.update    Farkli path = sorun yok                 |
|  process.spawn   Bagimsiz processler                     |
|                                                           |
+----------------------------------------------------------+
```

---

## 3. CONFLICT DETECTION FLOW

```
                    CONFIG LOAD
                         |
                         v
+----------------------------------------------------------+
|  PHASE 1: Plugin Discovery                               |
|  - manifest.yml dosyalarini oku                          |
|  - provides listelerini topla                            |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  PHASE 2: Config Load + Import                           |
|  - config.yml oku                                        |
|  - !include ile import edilen parcalari merge et         |
|  - manifest.yml config icine import edilir               |
|  - PHP require gibi: import edilen yerde merge           |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  PHASE 3: Conflict Detection                             |
|  - Ayni stage'deki pluginleri grupla                     |
|  - Lockable provides'lari karsilastir                    |
|  - Path overlap tespiti                                  |
+----------------------------------------------------------+
                         |
           +-------------+-------------+
           |                           |
           v                           v
    NO CONFLICT                   CONFLICT FOUND
           |                           |
           v                           v
    Continue                      WARNING/ERROR
                                       |
                         +-------------+-------------+
                         |                           |
                         v                           v
                   requires ekle              --force ile
                   (serialize)                bypass et
```

---

## 4. PROVIDES LOCK SYNTAX

### 4.1 Static Lock

```yaml
# manifest.yml
provides:
  - fs.write # Generic (path yok, her yere yazabilir)
  - fs.write:/data/archive # Static lock (sabit path)
  - fs.write:/data/movies # Baska static lock
```

### 4.2 Dynamic Lock (Config'den)

```yaml
# manifest.yml
provides:
  - fs.write:{{config.tasker.save_path}}

# config.yml
tasker:
  save_path: /data/archive/movies
```

**Render sonrasi:**

```yaml
provides:
  - fs.write:/data/archive/movies
```

### 4.3 Dinamik Degisken Iceren Lock (YASAK)

```yaml
# HATALI - Config error verir
provides:
  - fs.write:{{job.plugins.tmdb.movie.title}}
```

**Sebep:** `job.*` degerleri runtime'da olusur. Validation startup'ta calisir. Bu deger henuz yok.

---

## 5. PATH OVERLAP TESPITI

```
+----------------------------------------------------------+
|              PATH OVERLAP ALGORITMASI                     |
+----------------------------------------------------------+
|                                                           |
|  ORNEK 1: Tam eslesme                                     |
|  plugin_a: fs.write:/data/movies                         |
|  plugin_b: fs.write:/data/movies                         |
|  SONUC: CONFLICT (ayni path)                             |
|                                                           |
|  ORNEK 2: Parent-child                                   |
|  plugin_a: fs.write:/data                                |
|  plugin_b: fs.write:/data/movies                         |
|  SONUC: WARNING (parent icinde child)                    |
|                                                           |
|  ORNEK 3: Farkli pathler                                 |
|  plugin_a: fs.write:/data/movies                         |
|  plugin_b: fs.write:/data/shows                          |
|  SONUC: OK (farkli pathler)                              |
|                                                           |
|  ORNEK 4: Dynamic prefix                                 |
|  plugin_a: fs.write:/data/{{x}}/file                     |
|  Render: fs.write:/data/                                 |
|  SONUC: Degisken kisim atilir, static prefix alinir     |
|                                                           |
+----------------------------------------------------------+
```

---

## 6. VALIDATION DAVRANISI

```
+----------------------------------------------------------+
|  DURUM                          AKSIYON                   |
+----------------------------------------------------------+
|                                                           |
|  Ayni path, ayni stage          ERROR (run durdur)       |
|  Parent-child overlap           WARNING (devam et)        |
|  Generic provides (path yok)    SKIP (kontrol yok)       |
|  Dynamic degisken (job.*)       ERROR (config hatasi)    |
|  Farkli stage                   OK (sirali calisir)      |
|  requires ile bagimli           OK (serialize edilmis)   |
|                                                           |
+----------------------------------------------------------+

USER AKSIYON:
  --force          Conflict uyarilarini atla, calistir
  requires ekle    Pluginleri siralama ile serialize et
```

---

## 7. CONFLICT REGISTRY

```python
class ConflictRegistry:
    """Conflict tespiti icin registry"""

    LOCKABLE_PROVIDES = {
        'fs.write', 'fs.delete', 'fs.move',
        'fs.hardlink', 'fs.symlink'
    }

    def __init__(self):
        self._provides: Dict[str, List[ProvideEntry]] = {}

    def register(self, plugin: str, stage: str, provide: str) -> None:
        """Plugin provide degerini kaydet"""
        base, path = self._parse_provide(provide)

        if base not in self.LOCKABLE_PROVIDES:
            return  # Non-lockable, skip

        key = f"{stage}:{base}"
        entry = ProvideEntry(plugin=plugin, path=path)
        self._provides.setdefault(key, []).append(entry)

    def detect_conflicts(self) -> List[Conflict]:
        """Tum conflictleri tespit et"""
        conflicts = []

        for key, entries in self._provides.items():
            if len(entries) < 2:
                continue

            for i, a in enumerate(entries):
                for b in entries[i+1:]:
                    if self._paths_conflict(a.path, b.path):
                        conflicts.append(Conflict(
                            plugin_a=a.plugin,
                            plugin_b=b.plugin,
                            provide=key,
                            path_a=a.path,
                            path_b=b.path
                        ))

        return conflicts

    def _paths_conflict(self, a: str, b: str) -> bool:
        """Iki path cakisiyor mu?"""
        if not a or not b:
            return True  # Generic provides = potential conflict
        return a == b or a.startswith(b) or b.startswith(a)

    def _parse_provide(self, provide: str) -> Tuple[str, Optional[str]]:
        """fs.write:/path -> (fs.write, /path)"""
        if ':' in provide:
            base, path = provide.split(':', 1)
            return base, path
        return provide, None
```

**Uyari:** Ornek kod, yaklasimi gosterir. Execution session'da mevcut codebase'e uyarlanmalidir.

---

## 8. CONFIG ORNEK

```yaml
# config.yml

# Conflict uyarilarini atla
options:
  force_conflicts: true

# Plugin provides override
tasker:
  provides:
    - fs.write:/srv/media/movies # Config'de override
```

---

## 9. CLI DAVRANISI

```
$ archiverr
ERROR: Conflict detected

  tasker (stage: output)
    provides: fs.write:/data/movies

  custom_saver (stage: output)
    provides: fs.write:/data/movies

Resolution options:
  1. Add requires to serialize execution:
     custom_saver:
       requires:
         - provides.fs.write   # Wait for tasker

  2. Use different paths:
     custom_saver:
       provides:
         - fs.write:/data/custom

  3. Force run (not recommended):
     $ archiverr --force
```

---

## 10. MEVCUT STRATEJI ILE KARSILASTIRMA

```
MEVCUT (10_STANDARD_TERMS.md):
  - Lockable/non-lockable ayrimi VAR
  - Path-based lock PLANLANMIS
  - Dynamic lock (config'den) PLANLANMIS

EKLENEN:
  - ConflictRegistry class yapisi
  - Path overlap algoritmasi (parent-child)
  - CLI hata mesaji formati
  - --force bypass
  - Config'de provides override
```

---

**Son Guncelleme:** 2025-12-03
