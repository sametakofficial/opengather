# BRAINSTORM: EXECUTION MODEL v2

```yaml
date: 2025-12-01
type: brainstorm
status: in_progress
previous: 11_brainstorm_execution_model.md
```

---

## USER'IN YENİ FİKİRLERİ

### 1. Stage Yapısı (4 Stage)

```
INPUT → PARSE → METADATA → POST → FINALIZE
                              │
                              └── Task'tan SONRA çalışır
```

**POST Stage (eski modify):**
- Metadata sonrası işlemler
- AI-based detection (fail olan job'lar için)
- Notification pluginleri
- Duplicate cleaner

**FINALIZE Stage:**
- Task'lardan SONRA çalışır
- Rclone, cloud sync
- Summary report

### 2. Task System → Tasker Plugin

```yaml
# config.yml
tasker:
  tasks:
    - name: print_movie
      type: print
      condition: "{{ job.plugins.renamer.parsed.movie }}"
      template: |
        MOVIE: {{ job.plugins.tmdb.movie.title }}
    
    - name: save_movie
      type: save
      destination: |
        {{ options.movies_dst }}/{{ job.plugins.tmdb.movie.title }}/...
```

**Neden Plugin?**
- Core system daha dumb/playground olur
- Her plugin kendi log/save işlemini yapabilir
- Tasker sadece configure edilebilir log/save

### 3. provides + waits_for Sistemi

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
provides:
  - online_action
  - metadata.movie
  - metadata.show

# plugins/rclone/manifest.yml
name: rclone
waits_for:
  - online_action    # TMDb, TVDb gibi API çağrısı yapanlar bitsin
  - file_action      # Save, rename, delete yapanlar bitsin
```

**Avantaj:** Circular dependency yok, çakışma yok

### 4. triggers_on (Event Tetikleme)

```yaml
# plugins/file_logger/manifest.yml
name: file_logger
triggers_on:
  - events.file.create
  - events.file.delete
  - events.file.rename
```

**Not:** triggers_on ≠ waits_for
- triggers_on: Her event'te tekrar çalış
- waits_for: Bu provide'lar bitene kadar başlama

### 5. FlexGet Tarzı Config

```yaml
# FlexGet örneği:
tasks:
  my-task:
    rss: http://...
    series:
      - Show Name
    download: /path/

# Archiverr için (ÖNERİ):
scanner:
  targets:
    - /downloads
  recursive: true

renamer:
  # config...

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

tasker:
  tasks:
    - name: print_movie
      type: print
      template: ...
```

**Fark:**
- `plugins:` parent yok
- Plugin adı direkt root'ta
- Daha clean, FlexGet gibi

---

## YENİ STAGE SİSTEMİ

```
┌─────────────────────────────────────────────────────────────┐
│                    5-STAGE EXECUTION                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. INPUT                                                    │
│     └── Scanner, FileReader                                  │
│         └── Job oluşturur, input.path verir                  │
│                                                              │
│  2. PARSE                                                    │
│     └── Renamer                                              │
│         └── input.path'i parse eder                          │
│         └── parsed data ekler                                │
│                                                              │
│  3. METADATA                                                 │
│     └── TMDb, TVDb, FFProbe                                  │
│         └── provides: online_action, metadata.*              │
│                                                              │
│  4. POST (eski: modify)                                      │
│     ├── Tasker (per_job)                                     │
│     │   └── print, save tasks                                │
│     ├── AI Detector (per_job)                                │
│     │   └── Fail job'ları AI ile analiz                      │
│     ├── Notification (per_run)                               │
│     │   └── Telegram, Discord                                │
│     └── DuplicateCleaner (per_run)                           │
│         └── waits_for: [tasker]                              │
│                                                              │
│  5. FINALIZE (task'tan sonra)                                │
│     └── Rclone (per_run)                                     │
│         └── waits_for: [online_action, file_action]          │
│         └── Cloud sync                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## MANIFEST SCHEMA (ÖNERİ)

```yaml
name: string
version: string
stage: input | parse | metadata | post | finalize
execution_mode: per_job | per_run

# Ne sağlıyor?
provides:
  - online_action          # API çağrısı yapıyor
  - file_action            # Dosya işlemi yapıyor
  - metadata.movie         # Movie metadata
  - metadata.show          # Show metadata
  - notification           # Bildirim gönderiyor

# Neleri bekliyor?
waits_for:
  - online_action          # API yapanlar bitsin
  - file_action            # Dosya işlemi yapanlar bitsin
  - tasker                 # Task'lar tamamlansın

# Hangi event'lerde tekrar çalış?
triggers_on:
  - events.file.create
  - events.file.delete

# Data gereksinimleri
requires:
  - renamer.parsed.movie

class_name: string
```

---

## CONFIG YAPISI (FlexGet-inspired)

```yaml
# config.yml - FlexGet tarzı, plugins: parent yok

options:
  debug: true
  dry_run: true
  movies_dst: /media/movies
  shows_dst: /media/shows

scanner:
  targets:
    - /downloads
  recursive: true
  extensions:
    - mkv
    - mp4

renamer:
  # parser config...

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

ffprobe:
  # config...

tasker:
  tasks:
    - name: print_movie
      type: print
      condition: "{{ job.plugins.renamer.parsed.movie }}"
      template: |
        {% set m = job.plugins.tmdb.movie %}
        MOVIE: {{ m.title }} ({{ m.release_date[:4] }})
    
    - name: save_movie
      type: save
      condition: "{{ job.plugins.renamer.parsed.movie }}"
      destination: |
        {{ options.movies_dst }}/{{ m.title }}/{{ job.input.path | basename }}

rclone:
  remote: gdrive
  path: /media

notification:
  telegram:
    bot_token: ${TELEGRAM_BOT_TOKEN}
    chat_id: ${TELEGRAM_CHAT_ID}
```

---

## PROVIDES/WAITS_FOR ÖRNEKLERİ

### TMDb

```yaml
name: tmdb
stage: metadata
provides:
  - online_action
  - metadata.movie
  - metadata.show
```

### Tasker

```yaml
name: tasker
stage: post
provides:
  - file_action      # save yaparsa
  - tasker           # diğerleri bekleyebilsin
```

### DuplicateCleaner

```yaml
name: duplicate_cleaner
stage: post
execution_mode: per_run
provides:
  - file_action
waits_for:
  - tasker           # Task'lar bitsin
```

### Rclone

```yaml
name: rclone
stage: finalize
execution_mode: per_run
waits_for:
  - online_action    # API'ler bitsin
  - file_action      # Dosya işlemleri bitsin
```

---

## EXECUTION LOGIC

```python
class Orchestrator:
    def execute(self):
        # Stage sırası
        for stage in ['input', 'parse', 'metadata', 'post', 'finalize']:
            plugins = self._get_stage_plugins(stage)
            
            # waits_for'a göre sırala
            sorted_plugins = self._topological_sort(plugins)
            
            for plugin in sorted_plugins:
                # waits_for kontrolü
                if not self._all_provides_ready(plugin.waits_for):
                    continue  # Bekle
                
                # Execute
                if plugin.execution_mode == 'per_run':
                    result = plugin.execute_run(services)
                else:
                    for job in jobs:
                        result = plugin.execute(job, services)
                
                # provides güncelle
                self._mark_provides_ready(plugin.provides)
                
                # triggers_on kontrolü
                for event in pending_events:
                    if event in plugin.triggers_on:
                        # Tekrar çalıştır
                        plugin.execute(...)
```

---

## AÇIK SORULAR

### Q1: Stage isimleri?

```
Mevcut:  INPUT → PARSE → METADATA → POST → FINALIZE
Alternatif: INPUT → PARSE → ENRICH → PROCESS → SYNC
```

### Q2: Tasker stage'i?

```
A) POST stage'inde (metadata sonrası)
B) Kendi stage'i (TASK stage)
C) FINALIZE'dan önce ayrı
```

### Q3: provides değerleri standart mı?

```
Standart provides:
- online_action
- file_action
- metadata.*
- notification

Custom provides da olabilir mi?
- tasker
- duplicate_cleaned
```

### Q4: triggers_on ne zaman çalışır?

```
A) Event geldiği anda (immediate)
B) Stage sonunda (batch)
C) Run sonunda (deferred)
```

---

## SONRAKI ADIMLAR

- [ ] Stage isimlerini finalize et
- [ ] Tasker'ın stage'ini belirle
- [ ] provides/waits_for standart listesi
- [ ] triggers_on davranışı
- [ ] Config loader refactor (FlexGet style)

---

**Status: AWAITING USER FEEDBACK**
