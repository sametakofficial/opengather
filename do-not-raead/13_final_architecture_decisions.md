# FİNAL MİMARİ KARARLARI

```yaml
date: 2025-12-01
type: final-decisions
status: approved
```

---

# BÖLÜM 1: STAGE SİSTEMİ

## 1.1 Kesinleşen Stage Sıralaması

```
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION FLOW                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. INPUT                                                    │
│     └── Scanner, FileReader                                  │
│     └── Job oluşturma                                        │
│                                                              │
│  2. PARSE                                                    │
│     └── Renamer                                              │
│     └── Dosya adı parse, kategori tespiti                    │
│     └── Input path'e DOKUNMAZ (kutsal)                       │
│                                                              │
│  3. METADATA                                                 │
│     └── TMDb, TVDb, FFProbe                                  │
│     └── External API'lerden metadata toplama                 │
│                                                              │
│  4. PROCESS                                                  │
│     └── DuplicateCleaner, AIDetector, Tasker                 │
│     └── Metadata sonrası işlemler                            │
│     └── Tasker burada: print/save işlemleri                  │
│                                                              │
│  5. SYNC                                                     │
│     └── Rclone, Notification                                 │
│     └── TASKER'DAN SONRA çalışır                             │
│     └── Senkronizasyon ve bildirimler                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 1.2 Stage İsim Değişiklikleri

| Eski | Yeni | Neden |
|------|------|-------|
| modify | **process** | Daha genel, metadata sonrası tüm işlemler |
| finalize | **sync** | Daha spesifik, senkronizasyon aşaması |
| output | ~~kaldırıldı~~ | Tasker plugin oldu, ayrı stage yok |

## 1.3 Kritik Karar: Sync Stage Task'lardan Sonra

```
ESKİ DÜŞÜNCE:
... → finalize → output(tasks)

YENİ KARAR:
... → process(tasker dahil) → sync
```

**Neden?** Rclone, Tasker'ın kaydettiği dosyaları sync etmeli. Tasker'dan önce çalışırsa dosyalar henüz yok.

---

# BÖLÜM 2: MANIFEST SCHEMA

## 2.1 Final Schema

```yaml
# plugins/{name}/manifest.yml

# === IDENTITY ===
name: string                    # Unique identifier (required)
version: string                 # Semver (required)
description: string             # Human readable (optional)

# === STAGE & MODE ===
stage: input | parse | metadata | process | sync
mode: per_job | per_run         # Default: per_job

# === DEPENDENCY (DAG) ===
requires:                       # Data path dependencies
  - renamer.parsed.movie        # job.plugins.X.Y var mı?

provides:                       # Capability declarations
  - metadata.movie              # Bu plugin ne sağlar?
  - online.action               # Network işlemi yapıyor

waits_for:                      # Capability-based ordering
  - file.write                  # Bu cap'i sağlayanlar bitsin

# === REACTIVE ===
triggers_on:                    # Event-based re-execution
  - file.created                # Bu event'te tekrar çalış

emits:                          # Documentation (optional)
  - file.created                # Bu plugin hangi event'leri emit eder

# === IMPLEMENTATION ===
class_name: string              # Python class name
entry_point: string             # Default: client.py

# === CONFIG ===
config_schema:
  field_name:
    type: string | int | bool | list | dict
    required: bool
    default: any
    description: string
```

## 2.2 Standart Capability Değerleri

```yaml
# === INPUT ===
input.files          # Dosya listesi sağlar (Scanner)
input.virtual        # Virtual input sağlar (FileReader)

# === PARSE ===
parsed.movie         # Film parse sonucu
parsed.show          # Dizi parse sonucu
parsed.episode       # Bölüm parse sonucu

# === METADATA ===
metadata.movie       # Film metadata'sı
metadata.show        # Dizi metadata'sı
metadata.episode     # Bölüm metadata'sı
metadata.file        # Dosya metadata'sı (FFProbe)

# === PROCESS ===
duplicates.cleaned   # Duplicate temizleme yapıldı
ai.detected          # AI analizi yapıldı
file.write           # Dosya yazma yapıldı
output.printed       # Terminal output yapıldı

# === NETWORK ===
online.action        # Network işlemi yapıldı (API, HTTP, etc.)

# === SYNC ===
remote.synced        # Remote sync yapıldı
notification.sent    # Bildirim gönderildi
```

## 2.3 Standart Event Değerleri

```yaml
# === CORE EVENTS (Orchestrator emit eder) ===
run.started          # Run başladı
run.completed        # Run bitti
stage.started        # Stage başladı
stage.completed      # Stage bitti
job.created          # Yeni job oluştu
job.completed        # Job işlendi
plugin.started       # Plugin çalışmaya başladı
plugin.completed     # Plugin bitti

# === FILE EVENTS (Pluginler emit eder) ===
file.created         # Yeni dosya oluştu
file.deleted         # Dosya silindi
file.moved           # Dosya taşındı
file.renamed         # Dosya yeniden adlandırıldı

# === CUSTOM EVENTS ===
# Pluginler kendi event'lerini tanımlayabilir
# Convention: plugin_name.action
# Örnek: rclone.sync_completed
```

---

# BÖLÜM 3: DEPENDENCY SİSTEMİ

## 3.1 Üç Farklı Dependency Tipi

| Tip | Anahtar | Ne Bekler | Semantik |
|-----|---------|-----------|----------|
| **Data** | `requires` | Data path | `job.plugins.X.Y` var mı? |
| **Capability** | `waits_for` | Capability | Bu cap'i provide edenler bitti mi? |
| **Event** | `triggers_on` | Event | Bu event emit edilince (tekrar) çalış |

## 3.2 requires vs waits_for

```yaml
# requires = DATA bağımlılığı
# "Bu veri olmadan çalışamam"
tmdb:
  requires: [renamer.parsed.movie]
  # → renamer.parsed.movie job state'inde olmalı

# waits_for = CAPABILITY bağımlılığı  
# "Bu capability'yi sağlayanlar bitmeden çalışmam"
rclone:
  waits_for: [file.write]
  # → file.write provide eden TÜM pluginler bitmeli
```

## 3.3 waits_for Semantik: ALL

```
waits_for: [metadata.movie]

= metadata.movie provide eden TÜM pluginler tamamlanmalı
= TMDb bitti + OMDb bitti + ... → Rclone başlayabilir
```

## 3.4 Validation Kuralları

```python
# 1. Self-wait yasak
provides ∩ waits_for = ∅

# 2. Circular dependency yasak
A waits_for B, B waits_for A = ERROR

# 3. Unknown capability uyarı
waits_for: [unknown.cap] = WARNING (çalışır ama uyarı verir)
```

---

# BÖLÜM 4: TASKER PLUGIN

## 4.1 Tasker = Plugin

```yaml
# plugins/tasker/manifest.yml
name: tasker
version: 1.0.0
description: Configurable print/save task executor
stage: process
mode: per_job
waits_for: []           # Config'e göre otomatik hesaplanır
provides:
  - file.write
  - output.printed
emits:
  - file.created
class_name: TaskerPlugin
```

## 4.2 Config Yapısı

```yaml
# config.yml
tasker:
  tasks:
    - name: print_movie
      type: print
      condition: "{{ job.category == 'movie' }}"
      template: |
        {{ job.plugins.tmdb.movie.title }} ({{ job.plugins.tmdb.movie.year }})
    
    - name: save_movie
      type: save
      condition: "{{ job.category == 'movie' }}"
      source: "{{ job.input.path }}"
      destination: "/movies/{{ job.plugins.tmdb.movie.title }} ({{ job.plugins.tmdb.movie.year }})/{{ job.input.filename }}"
      method: hardlink  # copy | hardlink | symlink | move
```

## 4.3 Template Dependency Extraction

```python
class TaskerPlugin:
    def get_implicit_waits_for(self) -> List[str]:
        """Template'lerden bağımlılıkları çıkar"""
        deps = set()
        pattern = r'\{\{\s*job\.plugins\.(\w+)\.'
        
        for task in self.config.get('tasks', []):
            for field in ['template', 'condition', 'destination']:
                if field in task:
                    matches = re.findall(pattern, task[field])
                    deps.update(matches)
        
        # Her plugin için onun provides'ını ekle
        waits = []
        for plugin_name in deps:
            manifest = self.registry.get_manifest(plugin_name)
            if manifest and manifest.provides:
                waits.extend(manifest.provides)
        
        return waits
```

---

# BÖLÜM 5: FLEXGET-STYLE CONFIG

## 5.1 Config Yapısı

```yaml
# config.yml - plugins: parent YOK

# === CONFIG METADATA ===
_config:
  version: 1.0
  name: my_archiverr_config

# === PLUGIN CONFIGS (direkt isim) ===
scanner:
  targets:
    - /downloads/movies
    - /downloads/shows
  exclude:
    - "*.sample.*"
    - "*.trailer.*"

renamer:
  patterns:
    movie: "{{ title }} ({{ year }})"
    show: "{{ title }}/Season {{ season }}/{{ title }} - S{{ season }}E{{ episode }}"

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR
  region: TR

ffprobe:
  include_raw: false

tasker:
  tasks:
    - name: print_info
      type: print
      template: "Processing: {{ job.plugins.renamer.parsed.title }}"
    
    - name: save_movie
      type: save
      condition: "{{ job.category == 'movie' }}"
      destination: "/media/movies/{{ job.plugins.tmdb.movie.title }} ({{ job.plugins.tmdb.movie.year }})/"

rclone:
  remote: gdrive
  path: /Archiverr
  flags:
    - --progress
    - --transfers=4
```

## 5.2 Plugin Enable/Disable

```yaml
# Disable tamamen
tmdb: false

# Disable ama config kalsın
tmdb:
  enabled: false
  api_key: ${TMDB_API_KEY}

# Enable (default)
tmdb:
  api_key: ${TMDB_API_KEY}
```

## 5.3 External Config Import

```yaml
# config.yml
scanner:
  !include: ./scanner-config.yml

tasker:
  tasks:
    !include_list: ./tasks/
```

```yaml
# scanner-config.yml
targets:
  - /downloads
exclude:
  - "*.sample.*"
```

---

# BÖLÜM 6: CORE SYSTEM

## 6.1 Core Sorumlulukları (Dumb Core)

```
CORE YAPACAKLARI:
├── Config loading + ${ENV_VAR} resolution + !include
├── Plugin discovery (manifest.yml okuma)
├── Plugin loading (class import)
├── Dependency validation (circular check, self-wait check)
├── DAG construction (topological sort)
├── Stage execution (sırayla)
├── PluginServices injection
├── State management
├── Event bus
└── Persistence (MongoDB)

CORE YAPMAYACAKLARI:
├── ❌ Print/Save işlemleri (Tasker yapacak)
├── ❌ Template rendering (Tasker yapacak)
├── ❌ Plugin-specific logic (her plugin kendi işini yapacak)
```

## 6.2 PluginServices Interface

```python
@dataclass
class PluginServices:
    """Core'un pluginlere sağladığı servisler"""
    
    # State access
    state: StateService          # Job/Run state okuma/yazma
    
    # Event bus
    events: EventService         # Event emit/subscribe
    
    # Filesystem
    filesystem: FilesystemService  # Dosya okuma/yazma
    
    # Logging
    logger: LoggerService        # Plugin-specific logging
    
    # Config
    config: ConfigService        # Global config erişimi
    
    # Registry
    registry: RegistryService    # Diğer plugin manifest'lerine erişim
```

## 6.3 Execution Flow

```python
class Orchestrator:
    STAGES = ['input', 'parse', 'metadata', 'process', 'sync']
    
    def run(self):
        self.state.start_run()
        
        for stage in self.STAGES:
            self.execute_stage(stage)
        
        self.state.complete_run()
    
    def execute_stage(self, stage: str):
        plugins = self.get_plugins_for_stage(stage)
        sorted_plugins = self.topological_sort(plugins)
        
        for plugin in sorted_plugins:
            if plugin.mode == 'per_run':
                self.execute_per_run(plugin)
            else:
                self.execute_per_job(plugin)
    
    def execute_per_job(self, plugin):
        for job in self.state.get_jobs():
            if self.validate_requires(plugin, job):
                result = plugin.execute(job, self.services)
                self.state.set_job_plugin_result(job.id, plugin.name, result)
```

---

# BÖLÜM 7: INPUT PATH KUTSALLIĞI

## 7.1 Kural

```
INPUT PATH DEĞİŞTİRİLEMEZ.
Sadece INPUT stage plugin'leri job oluşturabilir.
Parser'lar input.path'e dokunmaz.
```

## 7.2 Job State Yapısı

```python
@dataclass
class JobState:
    # Unique identifiers
    id: str              # UUID
    index: int           # Run içi sıra numarası
    
    # Input (KUTSAL - değiştirilemez)
    input: InputData
    
    # Plugin results
    plugins: Dict[str, PluginResult]
    
    # Category (renamer belirler)
    category: str        # movie | show | unknown
    
    # Status
    status: JobStatus

@dataclass
class InputData:
    path: str            # Orijinal dosya yolu (değiştirilemez)
    filename: str        # Dosya adı
    extension: str       # Uzantı
    size: int            # Boyut
    virtual: bool        # Virtual input mu?
```

---

# BÖLÜM 8: ENDÜSTRİ KARŞILAŞTIRMASI

## 8.1 FlexGet

```yaml
# FlexGet config
tasks:
  download_movies:
    rss:
      url: http://...
    regexp:
      accept:
        - "1080p"
    download:
      path: /downloads

# Archiverr config (benzer ama daha basit)
scanner:
  targets: [/downloads]
tmdb:
  api_key: xxx
tasker:
  tasks: [...]
```

**Fark:** Archiverr'da task = FlexGet'teki task değil. Archiverr task = print/save action.

## 8.2 Gradle Capabilities

```groovy
// Gradle - capability conflict
configurations.all {
    resolutionStrategy.capabilitiesResolution
        .withCapability("metadata:movie") {
            select("tmdb")
        }
}

// Archiverr - waits_for ALL semantics
rclone:
  waits_for: [metadata.movie]  # TMDb + OMDb + ... hepsi bitsin
```

**Fark:** Gradle tek seçer, Archiverr hepsini bekler.

## 8.3 Docker Compose

```yaml
# Docker Compose
services:
  web:
    depends_on:
      - db
      - redis

# Archiverr
tmdb:
  waits_for: [parsed.movie]
```

**Benzerlik:** Dependency-based ordering.

## 8.4 Home Assistant

```yaml
# Home Assistant automation
automation:
  - alias: "Turn on lights"
    triggers:
      - trigger: sun
        event: sunset
    actions:
      - action: light.turn_on

# Archiverr plugin
file_logger:
  triggers_on: [file.created]
  # Her file.created event'inde çalış
```

**Benzerlik:** Event-driven triggers.

## 8.5 Airflow

```python
# Airflow DAG
task1 >> task2 >> task3  # Sequential
[task1, task2] >> task3  # Parallel then sequential

# Archiverr
# Topological sort ile otomatik sıralama
# provides/waits_for ile DAG oluşturma
```

**Benzerlik:** DAG-based execution.

---

# BÖLÜM 9: ÖZET KARARLAR

| Konu | Karar | Statü |
|------|-------|-------|
| Stage sayısı | 5: input, parse, metadata, process, sync | ✅ Final |
| modify → | process | ✅ Final |
| finalize → | sync | ✅ Final |
| Sync sırası | Tasker'dan SONRA | ✅ Final |
| Tasker | Plugin olacak, process stage | ✅ Final |
| Task System | Tasker plugin'e taşınacak | ✅ Final |
| Input path | Kutsal, değiştirilemez | ✅ Final |
| Config style | FlexGet-style (plugins: yok) | ✅ Final |
| Dependency | requires + provides + waits_for + triggers_on | ✅ Final |
| api.call → | online.action | ✅ Final |
| waits_for semantik | ALL (tüm provider'lar bitmeli) | ✅ Final |
| Self-wait | Yasak (validation) | ✅ Final |
| Circular dep | Yasak (topological sort) | ✅ Final |

---

# BÖLÜM 10: EXECUTION PLAN

## Phase 1: Core Refactoring (~8 saat)
1. Stage enum güncelleme (modify→process, finalize→sync)
2. Orchestrator stage sıralaması güncelleme
3. Manifest schema güncelleme
4. Dependency resolver (topological sort)
5. Validation (self-wait, circular)

## Phase 2: Tasker Plugin (~4 saat)
1. TaskerPlugin class oluşturma
2. Template rendering
3. Save/Print actions
4. Event emit (file.created)
5. Implicit waits_for extraction

## Phase 3: Config System (~3 saat)
1. FlexGet-style config parser
2. !include support
3. Plugin enable/disable
4. ${ENV_VAR} resolution

## Phase 4: Mevcut Pluginleri Güncelleme (~3 saat)
1. Scanner manifest güncelleme
2. Renamer manifest güncelleme
3. TMDb manifest güncelleme
4. FFProbe manifest güncelleme

## Phase 5: Testing (~2 saat)
1. Manifest validation tests
2. Dependency resolver tests
3. Tasker plugin tests
4. Integration tests

**Toplam: ~20 saat**

---

**Status: APPROVED - Execution bekliyor**

