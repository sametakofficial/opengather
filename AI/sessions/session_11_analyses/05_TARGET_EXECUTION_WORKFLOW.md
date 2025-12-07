# HEDEF EXECUTION WORKFLOW

```yaml
tarih: 2025-12-04
durum: target_state
kaynak: 
  - HUMAN/FINAL_DATASETS.yml (TRUTH SOURCE)
  - AI/sessions/session_11_strategy/*.md
  - AI/PHILOSOPHY.md
```

---

## 1. HEDEF GENEL AKIŞ

```
┌─────────────────────────────────────────────────────────────────────┐
│                         __main__.py                                  │
│                         (~50 satır - minimal)                        │
├─────────────────────────────────────────────────────────────────────┤
│  1. CLI args parse                                                   │
│  2. config = load_config("config.yml")                              │
│  3. orchestrator = build_orchestrator(config)                       │
│  4. result = orchestrator.run()                                     │
│  5. sys.exit(0 if result.success else 1)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LIFECYCLE:                                                          │
│  ┌──────────┐   ┌────────────┐   ┌──────────┐   ┌──────────┐       │
│  │ INIT     │──▶│ INPUT      │──▶│ EXECUTE  │──▶│ FINALIZE │       │
│  │          │   │ (per_run)  │   │ (stages) │   │          │       │
│  └──────────┘   └────────────┘   └──────────┘   └──────────┘       │
│       │              │                │               │              │
│  Plugins         Scanner          PARSE/DATA/      Persist         │
│  Validate        creates         OUTPUT stages     MongoDB         │
│  Config          jobs                               emit complete  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 4-STAGE EXECUTION (HEDEF)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    4-STAGE EXECUTION FLOW                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STAGE 1: INPUT (per_run)                                     │    │
│  │ ├── scanner.execute_run(services)                            │    │
│  │ │   └── Dosyaları tara, job'lar oluştur                     │    │
│  │ └── PROVIDES: job.create, fs.read, input.value, input.data  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                            │                                         │
│                            ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STAGE 2: PARSE (per_job)                                     │    │
│  │ ├── for job in jobs:                                         │    │
│  │ │     renamer.execute(job, services)                         │    │
│  │ │     └── Dosya adını parse et, metadata çıkar              │    │
│  │ └── PROVIDES: state.update                                   │    │
│  │ └── OUTPUT: job.plugins.renamer.parsed                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                            │                                         │
│                            ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STAGE 3: DATA (per_job, parallel mümkün)                     │    │
│  │ ├── for job in jobs:                                         │    │
│  │ │     if requires_satisfied(tmdb):                           │    │
│  │ │       tmdb.execute(job, services)                          │    │
│  │ │     if requires_satisfied(ffprobe):                        │    │
│  │ │       ffprobe.execute(job, services)                       │    │
│  │ └── PROVIDES: http.request, state.update, process.spawn     │    │
│  │ └── OUTPUT: job.plugins.{tmdb,ffprobe,tvdb,...}             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                            │                                         │
│                            ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STAGE 4: OUTPUT (mixed - per_job + per_run)                  │    │
│  │ ├── for job in jobs:                                         │    │
│  │ │     tasker.execute(job, services)                          │    │
│  │ │     └── Task'ları çalıştır (print, save)                  │    │
│  │ ├── rclone.execute_run(services)  # per_run                 │    │
│  │ │     └── Bulk upload                                        │    │
│  │ └── PROVIDES: fs.write, output.values, output.data          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. REQUIRES + TRIGGER_RULE WORKFLOW (HEDEF)

```
┌─────────────────────────────────────────────────────────────────────┐
│              REQUIRES + TRIGGER_RULE DECISION FLOW                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Plugin çalıştırılacak mı?                                          │
│  │                                                                   │
│  ├── 1. requires[] al                                               │
│  │       requires:                                                  │
│  │         - job.plugins.renamer.parsed    # State path            │
│  │         - provides.http.request         # Provide completion    │
│  │         - events.file.created           # Event fired           │
│  │                                                                   │
│  ├── 2. Her require için status kontrol et                         │
│  │       job.plugins.renamer.parsed  → FILLED / EMPTY              │
│  │       provides.http.request       → COMPLETED / PENDING         │
│  │       events.file.created         → FIRED / NOT_FIRED           │
│  │                                                                   │
│  ├── 3. trigger_rule uygula                                         │
│  │       ┌──────────────┬─────────────────────────────────────┐    │
│  │       │ TRIGGER_RULE │ KOŞUL                                │    │
│  │       ├──────────────┼─────────────────────────────────────┤    │
│  │       │ all_success  │ TÜM requires SUCCESS (default)      │    │
│  │       │ one_success  │ En az BİR require SUCCESS           │    │
│  │       │ all_done     │ TÜM requires DONE (fail dahil)      │    │
│  │       │ all_fail     │ TÜM requires FAIL                   │    │
│  │       │ none_fail    │ HİÇBİR require FAIL değil           │    │
│  │       └──────────────┴─────────────────────────────────────┘    │
│  │                                                                   │
│  └── 4. Karar                                                        │
│          ├── EXECUTE: Koşul sağlandı                                │
│          ├── SKIP: Koşul sağlanmadı                                 │
│          └── WAIT: reactive=true ise değişiklik bekle              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. PROVIDES SYSTEM WORKFLOW (HEDEF)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PROVIDES WORKFLOW                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Plugin manifest'te provides tanımlar:                           │
│     provides:                                                        │
│       - http.request                                                │
│       - fs.write:/srv/media    # Path constraint                   │
│                                                                      │
│  2. Conflict detection (startup):                                    │
│     ┌────────────────────────────────────────────────────────┐      │
│     │ LOCKABLE PROVIDES (çakışma kontrol):                   │      │
│     │   fs.write, fs.delete, fs.move, fs.hardlink, fs.symlink│      │
│     │                                                         │      │
│     │ NON-LOCKABLE (parallel safe):                          │      │
│     │   fs.read, fs.copy, http.request, state.update         │      │
│     └────────────────────────────────────────────────────────┘      │
│                                                                      │
│  3. Provides completion:                                             │
│     class TMDbPlugin:                                                │
│       def execute(self, job, services):                             │
│         response = await self.fetch()                               │
│         # http.request tamamlandı - bekleyenler başlasın           │
│         services.complete_provide("http.request")                   │
│         await self.download_artwork()                               │
│         services.complete_provide("fs.write")                       │
│                                                                      │
│  4. Requires bekleyenler:                                            │
│     requires: [provides.http.request]                               │
│     # http.request complete olunca plugin çalışır                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. ALIAS SYSTEM WORKFLOW (HEDEF)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ALIAS SYSTEM (HEDEF)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SYSTEM ALIASES (8 adet - FINAL_DATASETS.yml):                      │
│  ┌──────────────┬───────────────────────────────────────────────┐   │
│  │ ALIAS        │ DEĞER                                          │   │
│  ├──────────────┼───────────────────────────────────────────────┤   │
│  │ run          │ Run state object                               │   │
│  │ job          │ Current job state object                       │   │
│  │ jobs         │ All jobs in current run                        │   │
│  │ plugins      │ Current job plugins data                       │   │
│  │ config       │ Frozen config snapshot (readonly)              │   │
│  │ options      │ config.options shortcut                        │   │
│  │ provides     │ Active provides registry (readonly)            │   │
│  │ events       │ Event bus history (readonly)                   │   │
│  └──────────────┴───────────────────────────────────────────────┘   │
│                                                                      │
│  USER ALIASES (config.aliases):                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ aliases:                                                      │   │
│  │   m: job.plugins.tmdb.movie                                  │   │
│  │   s: job.plugins.tmdb.show                                   │   │
│  │   p: job.plugins.renamer.parsed                              │   │
│  │   movie: job.plugins.renamer.parsed.movie                    │   │
│  │   video: job.plugins.ffprobe.video                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  INLINE ALIASES (Jinja2 - HER YERDE):                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ # config.yml task template içinde                            │   │
│  │ {% set m = job.plugins.tmdb.movie %}                         │   │
│  │ {{ m.title }} ({{ m.release_date[:4] }})                     │   │
│  │                                                               │   │
│  │ # manifest.yml içinde (HEDEF - henüz yok)                    │   │
│  │ requires:                                                     │   │
│  │   - {{ alias.renamer_parsed }}  # alias kullanımı            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  PRIORITY:                                                           │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ 1. Inline ({% set %})        ← HIGHEST PRIORITY            │     │
│  │ 2. User (config.aliases)                                    │     │
│  │ 3. System (run, job, ...)    ← LOWEST PRIORITY             │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. CONFIG JINJA2 KULLANIMI (HEDEF)

```
┌─────────────────────────────────────────────────────────────────────┐
│                 JINJA2 CONFIG KULLANIMI                              │
│              (FlexGet style - aynı syntax)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  DEĞİŞKEN TANIMLAMA:                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ {% set m = job.plugins.tmdb.movie %}                         │   │
│  │ {% set year = m.release_date[:4] %}                          │   │
│  │ {{ m.title }} ({{ year }})                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  KOŞUL (IF/ELSE):                                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ {% if job.plugins.renamer.parsed.movie %}                    │   │
│  │   /movies/{{ m.title }}/                                     │   │
│  │ {% elif job.plugins.renamer.parsed.show %}                   │   │
│  │   /shows/{{ s.name }}/Season {{ s.season }}/                 │   │
│  │ {% else %}                                                    │   │
│  │   /unknown/                                                   │   │
│  │ {% endif %}                                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  DÖNGÜ (FOR):                                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ {% for audio in job.plugins.ffprobe.audio %}                 │   │
│  │   Audio {{ loop.index }}: {{ audio.language }}               │   │
│  │ {% endfor %}                                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  FİLTRELER:                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ {{ m.title | upper }}              # BÜYÜK HARF             │   │
│  │ {{ m.title | lower }}              # küçük harf             │   │
│  │ {{ m.title | replace(' ', '_') }}  # boşluk → _             │   │
│  │ {{ genres | join(', ') }}          # liste → string         │   │
│  │ {{ runtime | default(0) }}         # default değer          │   │
│  │ {{ value | int }}                  # integer'a çevir        │   │
│  │ {{ season | string | zfill(2) }}   # "1" → "01"             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ÖRNEK CONFIG TASK:                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ tasker:                                                       │   │
│  │   tasks:                                                      │   │
│  │     - name: save_movie                                       │   │
│  │       type: save                                              │   │
│  │       condition: "{{ job.plugins.renamer.parsed.movie }}"    │   │
│  │       template: |                                             │   │
│  │         {% set m = job.plugins.tmdb.movie %}                 │   │
│  │         {% set year = m.release_date[:4] %}                  │   │
│  │         {{ config.archive_path }}/Movies/                    │   │
│  │         {{ m.title }} ({{ year }})/                          │   │
│  │         {{ m.title }}.{{ job.input.data.extension }}         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. MANIFEST ALIAS KULLANIMI (HEDEF - YENİ)

```
┌─────────────────────────────────────────────────────────────────────┐
│                MANIFEST İÇİNDE ALIAS KULLANIMI                       │
│                     (HEDEF - implement edilecek)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  MEVCUT (uzun yol):                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ # plugins/tmdb/manifest.yml                                  │   │
│  │ requires:                                                     │   │
│  │   - job.plugins.renamer.parsed                               │   │
│  │   - job.plugins.scanner.category                             │   │
│  │   - job.plugins.ffprobe.video.codec                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  HEDEF (alias ile):                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ # plugins/tmdb/manifest.yml                                  │   │
│  │ aliases:                                                      │   │
│  │   renamer_parsed: job.plugins.renamer.parsed                 │   │
│  │   category: job.plugins.scanner.category                     │   │
│  │                                                               │   │
│  │ requires:                                                     │   │
│  │   - {{ renamer_parsed }}                                     │   │
│  │   - {{ category }}                                           │   │
│  │                                                               │   │
│  │ # Veya inline:                                                │   │
│  │ requires:                                                     │   │
│  │   - job.plugins.{{ config.parser_plugin }}.parsed           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  WORKFLOW:                                                           │
│  1. Manifest YAML yükle                                              │
│  2. manifest.aliases al                                             │
│  3. Jinja2 ile template render et (requires, provides, etc.)        │
│  4. Resolved manifest kullan                                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. TASKER REQUIRES (HEDEF)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TASKER PLUGIN (HEDEF)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  MEVCUT:                                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ name: tasker                                                  │   │
│  │ stage: output                                                 │   │
│  │ requires: []                      # BOŞ - yanlış!            │   │
│  │ provides: [fs.write, output.values, output.data]             │   │
│  │ trigger_rule: all_done                                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  HEDEF:                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ name: tasker                                                  │   │
│  │ stage: output                                                 │   │
│  │ requires:                                                     │   │
│  │   - provides.state.update   # DATA stage pluginleri bitsin  │   │
│  │   # NOT: fs.write gereksiz çünkü tasker kendi fs.write yapan│   │
│  │   # diğer OUTPUT pluginlerden önce/sonra çalışma için       │   │
│  │   # provides path constraint kullanılır                      │   │
│  │ provides:                                                     │   │
│  │   - fs.write:{{ config.archive_path }}  # Path constraint   │   │
│  │   - output.values                                            │   │
│  │   - output.data                                              │   │
│  │ trigger_rule: all_done    # Bazı plugin fail olsa bile çalış│   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  NEDEN provides.state.update?                                        │
│  - DATA stage pluginleri (tmdb, ffprobe) state.update provide eder │
│  - Tasker onların bitmesini beklemeli                               │
│  - trigger_rule: all_done ile bazıları fail olsa bile çalışır      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. TODO LİSTESİ

| # | Görev | Öncelik | Durum |
|---|-------|---------|-------|
| 1 | provides alias'ını template context'e inject et | P1 | 📋 |
| 2 | events alias'ını template context'e inject et | P1 | 📋 |
| 3 | Manifest içinde alias/Jinja2 kullanımı | P2 | 📋 |
| 4 | Tasker requires güncelle (provides.state.update) | P1 | 📋 |
| 5 | Config Jinja2 kullanımını dokümante et | P2 | 📋 |
| 6 | Provides completion system (complete_provide) | P2 | 📋 |
| 7 | Conflict detection for lockable provides | P2 | 📋 |

---

**Son Güncelleme:** 2025-12-04
