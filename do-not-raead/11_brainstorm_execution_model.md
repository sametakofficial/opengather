# BRAINSTORM: EXECUTION MODEL v2

```yaml
date: 2025-11-30
type: brainstorm
status: in_progress
```

---

## USER PROPOSAL

### 1. Sadece 2 Phase

```
MEVCUT (6 phase):
input → parse → metadata → modify → finalize → output

ÖNERİLEN (2 phase):
INPUT → OUTPUT
```

### 2. depends_on Sistemi (Docker Compose Pattern)

```yaml
# Docker Compose örneği:
services:
  web:
    depends_on:
      - db
  db:
    ...

# Plugin manifest örneği:
name: rclone
phase: output
execution_mode: per_run
run_order: last              # ilk mi son mu?
depends_on:
  - events.file.delete
  - events.file.rename
  - events.file.create
  - events.online_action
```

### 3. Renamer = INPUT Plugin

```
Eski düşünce:
- Scanner → job oluşturur, input.path verir
- Renamer → parse eder, parsed data verir

Yeni düşünce:
- Scanner → job oluşturur, input.path verir
- Renamer → INPUT plugin, input.path'i DEĞİŞTİRİR
- Her plugin kendi data'sını plugins içinde saklar
```

### 4. Her Plugin Kendi Data'sını Saklar

```
Job:
├── input:
│   ├── scanner: {path: "/original.mkv"}
│   └── renamer: {path: "/parsed/Movie (2024).mkv"}
├── plugins:
│   ├── scanner: {...}
│   ├── renamer: {parsed: {...}}
│   └── tmdb: {movie: {...}}
└── output:
    ├── task1: {...}
    └── rclone: {...}
```

### 5. per_run Pluginler İçin run_order

```
run_order: first    # Paralel başlat, en başta
run_order: last     # Paralel başlat, en sonda
```

---

## ANALİZ SORULARI

### Q1: Input Override Nasıl Çalışacak?

```
Senaryo:
1. Scanner: input.path = "/downloads/file.mkv"
2. Renamer: input.path = "/movies/Movie (2024)/file.mkv"

Soru: Template'de hangi path kullanılacak?
- {{ job.input.path }} → Hangisi?
- {{ job.input.scanner.path }} → Scanner'ın verdiği
- {{ job.input.renamer.path }} → Renamer'ın verdiği
```

**Olası Çözümler:**

A) Son yazan kazanır (last-write-wins)
```
job.input.path = Son INPUT plugin'in değeri
```

B) Namespace ile
```
job.input.scanner.path
job.input.renamer.path
job.input.path = aktif/son değer
```

C) Array olarak
```
job.inputs = [
  {plugin: "scanner", path: "..."},
  {plugin: "renamer", path: "..."}
]
```

---

### Q2: depends_on Event Tipleri

```
Önerilen events:
├── file.create
├── file.delete
├── file.rename
├── file.move
└── online_action   # API çağrısı yapan plugin

Soru: online_action nasıl tespit edilecek?
- Manifest'te declare mı? (api_calls: true)
- Runtime'da tespit mi?
```

---

### Q3: run_order vs depends_on

```
Senaryo:
- Rclone: run_order: last, depends_on: [file.delete]
- Summary: run_order: last

Soru: İkisi de "last" - hangisi önce?
```

**Olası Çözümler:**

A) depends_on olanlar en son
```
1. Tüm pluginler çalışır
2. run_order: last pluginler çalışır (depends_on olmayanlar)
3. run_order: last + depends_on olanlar en son
```

B) Priority eklenir (ama user bunu istemedi)

C) depends_on = implicit "wait for all"
```
depends_on varsa → tüm ilgili event'ler tamamlanınca çalışır
depends_on yoksa → sırayla çalışır
```

---

### Q4: Per-run Plugin State

```
Senaryo:
- Rclone per_run çalışıyor
- 100 job var, her biri file.create event'i gönderiyor

Soru: Rclone her event'te mi çalışacak, yoksa toplu mu?
```

**Olası Çözümler:**

A) Event collection
```python
class RclonePlugin:
    def on_event(self, event):
        self._pending.append(event)
    
    def execute_run(self):
        # Tüm pending'leri işle
        self.sync(self._pending)
```

B) Run sonunda tek çalışma
```
depends_on: [run.complete]
```

---

### Q5: INPUT vs OUTPUT Ayrımı

```
Mevcut kategoriler:
- INPUT: Scanner, Renamer (input verir/değiştirir)
- OUTPUT: TMDb, FFProbe, Rclone (data ekler veya action yapar)

Soru: TMDb ne yapıyor?
- Input değiştirmiyor
- Data ekliyor (plugins.tmdb.movie)
- File action yapmıyor

TMDb = OUTPUT mu?
```

---

## YENİ MODEL ÖNERİSİ

```
┌─────────────────────────────────────────────────────────────┐
│                    2-PHASE MODEL                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT PHASE                                                 │
│  ├── Scanner (per_run, run_order: first)                     │
│  │   └── Creates jobs, sets input.path                       │
│  ├── Renamer (per_job)                                       │
│  │   └── Modifies input.path, adds parsed data               │
│  └── ...                                                     │
│                                                              │
│  OUTPUT PHASE                                                │
│  ├── TMDb (per_job)                                          │
│  │   └── Adds plugins.tmdb.movie                             │
│  ├── FFProbe (per_job)                                       │
│  │   └── Adds plugins.ffprobe.video                          │
│  ├── TaskManager (per_job)                                   │
│  │   └── Executes print/save tasks                           │
│  └── Rclone (per_run, run_order: last)                       │
│      └── depends_on: [file.*, online_action]                 │
│      └── Syncs to remote                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## MANIFEST SCHEMA (ÖNERİ)

```yaml
name: string
version: string
phase: input | output
execution_mode: per_job | per_run

# Per-run için
run_order: first | last        # Default: first

# Event bağımlılıkları
depends_on:
  - events.file.create
  - events.file.delete
  - events.file.rename
  - events.online_action
  - plugins.renamer              # Plugin tamamlanınca

# Data requirements
requires:
  - renamer.parsed.movie

class_name: string
```

---

## EVENT TİPLERİ

```
Plugin Events:
├── plugins.{name}.started
├── plugins.{name}.completed
└── plugins.{name}.failed

File Events:
├── file.create
├── file.delete
├── file.rename
└── file.move

Phase Events:
├── phase.input.completed
└── phase.output.completed

Run Events:
├── run.started
└── run.completed

Action Events:
└── online_action               # API/network call yapıldı
```

---

## AÇIK SORULAR

1. **Input namespace**: `job.input.path` mi `job.input.{plugin}.path` mi?

2. **online_action detection**: Manifest'te mi declare edilecek?

3. **depends_on + run_order kombinasyonu**: Nasıl priority?

4. **Event collection**: per_run plugin event'leri nasıl toplayacak?

5. **Circular dependency**: A depends_on B, B depends_on A?

---

## SONRAKI ADIMLAR

- [ ] User feedback: Input namespace çözümü
- [ ] User feedback: online_action detection
- [ ] User feedback: run_order priority
- [ ] Finalize manifest schema
- [ ] Update other strategy docs

---

**Status: AWAITING USER FEEDBACK**
