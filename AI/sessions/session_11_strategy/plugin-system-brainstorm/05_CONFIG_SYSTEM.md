# CONFIG SYSTEM

```yaml
tarih: 2025-12-02
durum: final
kritik: config.yml + manifest.yml merge ve import sistemi
```

---

## 1. CURRENT

```yaml
# config.yml (mevcut)
plugins:
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}
    language: tr-TR
```

Sorunlar:
- plugins: wrapper gereksiz
- enabled field her yerde
- Manifest ayri dosya, merge yok

---

## 2. FEATURE

```yaml
# config.yml (yeni - FlexGet style)
tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

scanner:
  targets:
    - /downloads
    
tasker:
  tasks:
    !include: ./tasks/
```

---

## 3. WHY

### Endustri Ornekleri

```
SISTEM              CONFIG PATTERN
--------------------------------------------------
FlexGet             Plugin adi = top-level key
                    No "plugins:" wrapper
                    
Home Assistant      !include, !include_dir_list
                    integration: {...}
                    
Docker Compose      services:
                      app: {...}
                      
Ansible             !include, roles/
```

### Archiverr Karari

```
+----------------------------------------------------------+
|              FLEXGET STYLE CONFIG                         |
+----------------------------------------------------------+
|                                                           |
|  MEVCUT:                                                  |
|  plugins:                                                 |
|    tmdb:                                                  |
|      enabled: true                                       |
|      api_key: xxx                                        |
|                                                           |
|  YENI:                                                    |
|  tmdb:                                                    |
|    api_key: xxx                                          |
|                                                           |
|  NEDEN:                                                   |
|  - Daha temiz                                            |
|  - Daha az nesting                                       |
|  - FlexGet, HA, Ansible pattern                          |
|  - enabled = key varsa true                              |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. SCHEMA

### Config + Manifest Merge

```
              CONFIG LOADING FLOW

+----------------------------------------------------------+
|  1. config.yml yukle                                     |
|     tmdb:                                                |
|       api_key: xxx                                       |
|       language: tr-TR                                    |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  2. Plugin discovery                                     |
|     plugins/tmdb/manifest.yml oku                        |
|     name: tmdb                                           |
|     stage: metadata                                      |
|     requires: [renamer.parsed]                           |
|     provides: [http.response]                            |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  3. Merge (config uzerine manifest)                      |
|     tmdb:                                                |
|       # config.yml'den                                   |
|       api_key: xxx                                       |
|       language: tr-TR                                    |
|       # manifest.yml'den                                 |
|       _stage: metadata                                   |
|       _requires: [renamer.parsed]                        |
|       _provides: [http.response]                         |
|       _mode: per_job                                     |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  4. Validation                                           |
|     - config_schema kontrolu                             |
|     - required fields kontrolu                           |
|     - type validation                                    |
+----------------------------------------------------------+
```

### Import Directive

```
              !INCLUDE DIRECTIVE

SYNTAX:
  !include file.yml           # Tek dosya
  !include_list dir/          # Dizin -> list
  !include_merge dir/         # Dizin -> merge

ORNEK:
  # config.yml
  scanner:
    targets:
      - /downloads
      
  tasker:
    tasks:
      !include_list: ./tasks/
      
  # ./tasks/movie_print.yml
  - name: movie_print
    type: print
    template: "{{ tmdb.movie.title }}"
    
  # ./tasks/save_movie.yml
  - name: save_movie
    type: save
    destination: "/media/movies/..."

SONUC:
  tasker:
    tasks:
      - name: movie_print
        type: print
        template: "..."
      - name: save_movie
        type: save
        destination: "..."
```

---

## 5. ENABLED LOGIC

```
+----------------------------------------------------------+
|              PLUGIN ENABLED DETECTION                     |
+----------------------------------------------------------+
|                                                           |
|  KURAL 1: Key varsa enabled                              |
|  tmdb:                                                    |
|    api_key: xxx                                          |
|  --> tmdb ENABLED                                        |
|                                                           |
|  KURAL 2: false ise disabled                             |
|  tvdb: false                                             |
|  --> tvdb DISABLED                                       |
|                                                           |
|  KURAL 3: enabled: false ile disabled                    |
|  omdb:                                                    |
|    enabled: false                                        |
|    api_key: xxx                                          |
|  --> omdb DISABLED                                       |
|                                                           |
|  KURAL 4: Key yoksa disabled                             |
|  # ffprobe hic yok                                       |
|  --> ffprobe DISABLED                                    |
|                                                           |
+----------------------------------------------------------+
```

---

## 6. MANIFEST AUTO-MERGE

```
              MANIFEST AUTO-MERGE

Plugin discovery sirasinda:
  1. plugins/*/manifest.yml oku
  2. config.yml'de plugin adi var mi kontrol et
  3. Varsa: manifest degerlerini _ prefix ile ekle
  4. Yoksa: plugin disabled

MERGE PRIORITY:
  config.yml > manifest.yml

ORNEK:
  # manifest.yml
  name: tmdb
  stage: metadata
  config_schema:
    language:
      default: en-US
      
  # config.yml
  tmdb:
    language: tr-TR
    
  # SONUC
  tmdb:
    language: tr-TR           # config override
    _stage: metadata          # manifest'ten
    _mode: per_job            # manifest'ten (default)
```

---

## 7. ENV VAR RESOLUTION

```
              ENV VAR PATTERNS

SYNTAX:
  ${VAR_NAME}           # Required
  ${VAR_NAME:-default}  # With default

RESOLUTION ORDER:
  1. .env dosyasi
  2. Environment variables
  3. Default value (varsa)

ORNEK:
  tmdb:
    api_key: ${TMDB_API_KEY}
    region: ${TMDB_REGION:-TR}
    
SONUC (.env'de TMDB_API_KEY=abc123):
  tmdb:
    api_key: abc123
    region: TR
```

---

## 8. CONFIG SNAPSHOT

```
              CONFIG SNAPSHOT (MongoDB)

KURAL: API key'ler ${VAR} olarak saklanir

ORNEK:
  # Runtime config
  tmdb:
    api_key: abc123def456
    
  # MongoDB snapshot
  tmdb:
    api_key: ${TMDB_API_KEY}
    
NEDEN:
  - Guvenlik: Key'ler DB'de saklanmaz
  - Reproducibility: .env + snapshot = ayni sonuc
```

---

## 9. ALIAS SYSTEM (Config Icinde)

```yaml
# config.yml
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show

tmdb:
  api_key: ${TMDB_API_KEY}

tasker:
  tasks:
    - name: print_movie
      type: print
      template: "{{ m.title }} ({{ m.release_date[:4] }})"
```

Detay: 07_ALIAS_SYSTEM.md

---

## 10. VALIDATION FLOW

```
              CONFIG VALIDATION

+----------------------------------------------------------+
|  STARTUP VALIDATION                                       |
|                                                           |
|  1. YAML syntax kontrolu                                 |
|  2. Required fields kontrolu                             |
|  3. Type validation (config_schema)                      |
|  4. Path validation (targets exist?)                     |
|  5. Secret validation (api_key format)                   |
+----------------------------------------------------------+
                         |
                         v
+----------------------------------------------------------+
|  RUNTIME VALIDATION                                       |
|                                                           |
|  1. Plugin requires satisfied?                           |
|  2. Template syntax valid?                               |
|  3. Condition syntax valid?                              |
+----------------------------------------------------------+
```

---

## 11. IMPLEMENTATION

```python
class ConfigLoader:
    def load(self, path: Path) -> Config:
        # 1. Raw YAML
        raw = yaml.safe_load(path.read_text())
        
        # 2. !include resolve
        resolved = self._resolve_includes(raw, path.parent)
        
        # 3. ${ENV} resolve
        env_resolved = self._resolve_env_vars(resolved)
        
        # 4. Plugin discovery & merge
        plugins = {}
        for name, manifest in self._discover_plugins():
            if name in env_resolved:
                plugins[name] = self._merge_manifest(
                    env_resolved[name],
                    manifest
                )
        
        # 5. Validation
        self._validate(plugins)
        
        return Config(
            plugins=plugins,
            aliases=env_resolved.get('aliases', {}),
            options=env_resolved.get('options', {})
        )
    
    def _merge_manifest(self, config: Dict, manifest: Dict) -> Dict:
        """Manifest degerlerini config'e ekle"""
        result = dict(config)
        result['_stage'] = manifest.get('stage', 'output')
        result['_mode'] = manifest.get('mode', 'per_job')
        result['_requires'] = manifest.get('requires', [])
        result['_provides'] = manifest.get('provides', [])
        result['_after'] = manifest.get('after', [])
        return result

Not: Direkt execution'da kullanilmaz, sadece
pattern gosterimi icin yazilmistir.
```

---

## 12. ORNEK CONFIG

```yaml
# config.yml (TAM ORNEK)

# Options
options:
  debug: true
  dry_run: false

# Aliases
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  p: job.plugins.renamer.parsed

# Plugins (FlexGet style - no wrapper)
scanner:
  targets:
    - /downloads/movies
    - /downloads/shows
  recursive: true

renamer:
  media_type: auto

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR
  
ffprobe:
  timeout: 30

tasker:
  tasks:
    !include_list: ./tasks/

# Disabled plugin
tvdb: false
```
