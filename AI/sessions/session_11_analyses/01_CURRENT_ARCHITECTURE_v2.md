# ARCHIVERR - CURRENT ARCHITECTURE (v2 - Güncel)

```yaml
tarih: 2025-12-04
versiyon: session-11-refactored
durum: WORKING
son_test: archiverr komutu başarılı çalışıyor
```

---

## 1. GENEL MİMARİ (GÜNCEL)

```
┌─────────────────────────────────────────────────────────────────┐
│                        __main__.py                               │
│                    (Entry Point ~170 loc)                        │
│  • CLI args parse (serve / default)                             │
│  • load_config_with_tracking()                                  │
│  • ConfigValidator check                                        │
│  • build_orchestrator()                                         │
│  • orchestrator.run()                                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Orchestrator                               │
│                    (orchestrator.py ~500 loc)                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ LIFECYCLE:                                               │    │
│  │   initialize() → startup_validation                      │    │
│  │   run() → execute_stages() → finalize()                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬───────────────┐
          ▼               ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────────┐
│  PluginRegistry │ │StageExecutor│ │ StateManager │ │ EventBus │
│  (discovery +   │ │ (4-stage)   │ │ (state ops)  │ │ (events) │
│   loading)      │ │             │ │              │ │          │
└────────┬────────┘ └──────┬──────┘ └──────────────┘ └──────────┘
         │                 │
         │    ┌────────────┴────────────┐
         │    │                         │
         ▼    ▼                         ▼
    ┌────────────┐              ┌────────────────┐
    │  Plugins   │              │  TaskManager   │
    │ scanner    │              │  (tasker için) │
    │ renamer    │              └───────┬────────┘
    │ tmdb       │                      │
    │ ffprobe    │                      ▼
    │ tasker     │              ┌────────────────┐
    └────────────┘              │TemplateManager │
                                │ (Jinja2)       │
                                └────────────────┘
```

---

## 2. 4-STAGE EXECUTION (ÇALIŞIYOR ✅)

```
┌─────────────────────────────────────────────────────────────────┐
│                    STAGE EXECUTION FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ STAGE 1: INPUT (per_run)                     ✅ ÇALIŞIYOR│    │
│  │ └── scanner.execute_run(services)                        │    │
│  │     └── Dosyaları tara, job'lar oluştur                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ STAGE 2: PARSE (per_job)                     ✅ ÇALIŞIYOR│    │
│  │ └── renamer.execute(job, services)                       │    │
│  │     └── Dosya adını parse et                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ STAGE 3: DATA (per_job, PARALLEL)            ✅ ÇALIŞIYOR│    │
│  │ ├── ffprobe.execute(job, services)  ──┐                  │    │
│  │ └── tmdb.execute(job, services)     ──┴── PARALLEL       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ STAGE 4: OUTPUT (per_job)                    ✅ ÇALIŞIYOR│    │
│  │ └── tasker.execute(job, services)                        │    │
│  │     └── Task'ları çalıştır (print, save)                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. CONFIG LOADING (ÇALIŞIYOR ✅)

```
┌──────────────────────────────────────────────────────────────────┐
│ load_config_with_tracking("config.yml")                          │
│                                                                   │
│ 1. load_yaml_with_includes()    → !include directive (❓ TEST)   │
│ 2. expand_env_vars()            → ${VAR} expansion   ✅          │
│ 3. normalize_config()           → FlexGet style     ✅          │
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│ CONFIG STRUCTURE (FlexGet Style)                                 │
│                                                                   │
│ options:              ✅ debug, dry_run, hardlink, memory        │
│ aliases:              ✅ m, p, s, video, movie, show, audio      │
│ scanner:              ✅ targets, recursive                       │
│ renamer:              ✅ media_type                               │
│ tmdb:                 ✅ api_key, language, region, extras       │
│ ffprobe:              ✅ timeout                                  │
│ tasker:               ✅ tasks array                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. ALIAS SİSTEMİ (KISMEN ÇALIŞIYOR ⚠️)

```
┌─────────────────────────────────────────────────────────────────┐
│                      ALIAS RESOLUTION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ SYSTEM ALIASES:                                                  │
│ ┌────────────┬─────────────────────────┬────────┐               │
│ │ Alias      │ Değer                   │ Durum  │               │
│ ├────────────┼─────────────────────────┼────────┤               │
│ │ run        │ Run state object        │ ✅     │               │
│ │ job        │ Current job state       │ ✅     │               │
│ │ jobs       │ All jobs list           │ ✅     │               │
│ │ options    │ config.options          │ ✅     │               │
│ │ index      │ Current job index       │ ✅     │               │
│ │ config     │ Frozen config snapshot  │ ❌     │               │
│ │ provides   │ Active provides         │ ❌     │               │
│ │ events     │ Event bus               │ ❌     │               │
│ └────────────┴─────────────────────────┴────────┘               │
│                                                                  │
│ USER ALIASES (config.aliases):                      ✅ ÇALIŞIYOR │
│ ┌────────────┬─────────────────────────────────────┐            │
│ │ m          │ job.plugins.tmdb.movie              │            │
│ │ s          │ job.plugins.tmdb.show               │            │
│ │ p          │ job.plugins.renamer.parsed          │            │
│ │ video      │ job.plugins.ffprobe.video           │            │
│ │ audio      │ job.plugins.ffprobe.audio           │            │
│ └────────────┴─────────────────────────────────────┘            │
│                                                                  │
│ ⚠️ {{ config.ffprobe.timeout }} ÇALIŞMIYOR!                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. PLUGIN REGISTRY (ÇALIŞIYOR ✅)

```
┌─────────────────────────────────────────────────────────────────┐
│                     PLUGIN LOADING FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ 1. PluginDiscovery.discover()                                   │
│    └── Scan plugins/ directory                                  │
│    └── Load manifest.yml / plugin.yml                           │
│    └── Return: {name: manifest_dict}                            │
│                                                                  │
│ 2. PluginLoader.load_by_category('input'|'output')              │
│    └── Check stage from manifest                                │
│    └── Check enabled from config                                │
│    └── Validate config_schema                                   │
│    └── Import plugin class                                      │
│    └── Instantiate with config                                  │
│                                                                  │
│ 3. PluginRegistry organizes by stage:                           │
│    ┌─────────┬─────────────────┐                                │
│    │ Stage   │ Plugins         │                                │
│    ├─────────┼─────────────────┤                                │
│    │ input   │ scanner         │                                │
│    │ parse   │ renamer         │                                │
│    │ data    │ ffprobe, tmdb   │                                │
│    │ output  │ tasker          │                                │
│    └─────────┴─────────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. REQUIRES/PROVIDES (KISMEN ÇALIŞIYOR ⚠️)

```
┌─────────────────────────────────────────────────────────────────┐
│                  REQUIRES/PROVIDES SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ MANIFEST DECLARATION:                              ✅ ÇALIŞIYOR  │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ requires:                                                   │  │
│ │   - job.plugins.renamer.parsed    # State path ✅          │  │
│ │   - provides.http.request         # Provide ⚠️ NOT TRACKED │  │
│ │                                                             │  │
│ │ provides:                                                   │  │
│ │   - fs.read                       # Effect ✅               │  │
│ │   - fs.write:/srv/media           # Path constraint ❌     │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│ LOCKABLE CONFLICT DETECTION:                       ❌ ÇALIŞMIYOR │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ HEDEF: fs.write:/data aynı anda sadece 1 plugin            │  │
│ │ MEVCUT: Conflict uyarı var ama path-based değil            │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│ TRIGGER RULES:                                     ⚠️ KISMEN    │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │ all_success   ✅ (default)                                  │  │
│ │ all_done      ⚠️ (tasker'da var, tam test yok)             │  │
│ │ one_success   ❌                                            │  │
│ │ all_fail      ❌                                            │  │
│ │ none_fail     ❌                                            │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. STATE STRUCTURE (ÇALIŞIYOR ✅)

```
RunState
├── id: str              "run_abc123"
├── status: RunStatus
│   ├── state: StateEnum (pending|running|completed|failed)
│   ├── success: bool
│   ├── total_jobs: int
│   ├── completed: int
│   └── failed: int
└── config: Dict         (frozen snapshot)

JobState  
├── id: str              "job_run_abc123_0"
├── index: int           0
├── run_id: str          "run_abc123"
├── input: InputData
│   ├── value: str       "/path/file.mkv"
│   └── data: Dict       {filename, extension, size_bytes}
├── plugins: Dict        {renamer: {...}, tmdb: {...}}
├── output: OutputData
│   ├── values: List[str]
│   └── data: Dict
└── status: JobStatus
    ├── state: StateEnum
    ├── success: bool
    └── executed: List[str]
```

---

## 8. EVENT BUS (ÇALIŞIYOR ✅)

```
┌─────────────────────────────────────────────────────────────────┐
│ EMITTED EVENTS (debug output'ta görülüyor)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ run.started      → Run initialized                ✅             │
│ run.completed    → Run finished                   ✅             │
│ stage.started    → Stage began                    ✅             │
│ stage.completed  → Stage finished                 ✅             │
│ plugin.completed → Plugin executed                ✅             │
│ job.created      → Job created by scanner         ✅             │
│ job.completed    → Job finished                   ✅             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. TASKER OUTPUT (ÇALIŞIYOR ✅)

```
ÖRNEK ÇIKTI:

========== JOB 0 15 ========== 
MOVIE: Mr & Mrs Smith (2005)
TMDb: Bay ve Bayan Smith (2005)

Template'ler render ediliyor:
- {{ index }} → job index
- {{ p.movie.name }} → parsed movie name  
- {{ m.title }} → TMDb title (Türkçe)
- {{ config.ffprobe.timeout }} → ❌ ÇALIŞMIYOR
```

---

## 10. EKSİKLER ÖZET

| Kategori | Eksik | Öncelik |
|----------|-------|---------|
| Alias | config, provides, events | P0 |
| Config | !include test | P1 |
| Provides | Path-based locking | P1 |
| Provides | complete_provide() | P2 |
| Trigger | one_success, all_fail, none_fail | P2 |
| Reactive | reactive: true handling | P2 |
| Memory | Hot/cold tiering | P3 |

---

**Son Güncelleme:** 2025-12-04 23:15
