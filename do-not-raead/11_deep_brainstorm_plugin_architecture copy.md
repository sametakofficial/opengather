# DEEP BRAINSTORM: PLUGIN ARCHITECTURE

```yaml
date: 2025-12-01
type: deep-brainstorm
status: critical-analysis
```

---

# BÖLÜM 1: MEVCUT DURUM ANALİZİ

## 1.1 Mevcut Manifest Yapısı (Gerçek Kod)

```yaml
# tmdb/manifest.yml (MEVCUT)
name: tmdb
category: output           # input | output
depends_on: [renamer]      # Plugin isimleri
expects: [renamer.parsed]  # Data path'leri
```

```yaml
# scanner/manifest.yml (MEVCUT)
name: scanner
category: input
depends_on: []
expects: []
```

**Gözlem:** Mevcut sistem basit ama sınırlı:
- Sadece 2 kategori (input/output)
- `depends_on` = plugin sırası
- `expects` = data requirement

---

## 1.2 Session 11'de Önerilen (Şimdiye Kadar)

```
6 Stage: INPUT → PARSE → METADATA → MODIFY → FINALIZE → OUTPUT
```

```yaml
# Önerilen manifest
phase: input | parse | metadata | modify | finalize
execution_mode: per_job | per_run
requires: [data.paths]
provides: [capabilities]
waits_for: [capabilities]
triggers_on: [events]
```

---

# BÖLÜM 2: KRİTİK SORULAR VE ANALİZ

## 2.1 STAGE SİSTEMİ - Gerçekten Gerekli mi?

### Soru: Finalize ayrı bir stage mi olmalı?

**Argüman FOR (ayrı stage):**
- Semantik anlam: "Her şey bittikten sonra"
- Orchestrator için basit: stage sırasıyla çalıştır

**Argüman AGAINST (ayrı stage değil):**
- waits_for zaten bunu çözüyor
- Stage eklemek = rigidity, flexibility azalır
- Docker Compose'da da ayrı stage yok, depends_on var

**User'ın Noktası:**
> "finalize stage'in ne anlamı var ki eğer rclone waits_for'a tasker yazabilecekse"

**CEVAP:** User haklı. Stage = rigid kategori. waits_for = flexible dependency.

```
SONUÇ: Stage sistemi sadece semantik gruplandırma için.
       Gerçek execution sırası = topological sort of dependencies
```

### Alternatif: Stage'siz, Pure Dependency Model

```yaml
name: scanner
provides: [input.files]

name: renamer
requires: [input.files]        # scanner'ı bekle
provides: [parsed.movie, parsed.show]

name: tmdb
requires: [parsed.movie]
provides: [metadata.movie, api.completed]

name: tasker
requires: [metadata.movie]
provides: [output.saved, output.printed]

name: rclone
requires: [output.saved]       # tasker bitmeden başlama
provides: [sync.completed]
```

**Avantaj:** Hiç stage yok, pure DAG
**Dezavantaj:** Kullanıcılar için anlaması zor

---

## 2.2 TASKER CONFLICT: Template'de Sonraki Plugin Data'sı

### Problem Senaryosu

```yaml
# config.yml
tasker:
  tasks:
    - name: print_ai_result
      template: "{{ job.plugins.ai_detector.result }}"  # ???
```

**Soru:** AI Detector tasker'dan SONRA çalışırsa, template'de kullanamaz mıyız?

### Analiz

```
Execution Order (waits_for'a göre):
1. scanner
2. renamer
3. tmdb
4. ai_detector (requires: tmdb)
5. tasker (requires: ai_detector? veya tmdb?)
```

**Case A:** Tasker requires: [ai_detector]
- AI detector önce çalışır
- Template'de kullanılabilir
- ÇALIŞIR

**Case B:** Tasker requires: [tmdb] (ai_detector'ı beklemez)
- Tasker önce çalışır
- AI detector sonra
- Template'de job.plugins.ai_detector YOK
- ÇALIŞMAZ

### Çözüm: Explicit Dependency

```yaml
# tasker config
tasker:
  requires_plugins: [ai_detector]  # veya manifest'te
  tasks:
    - template: "{{ job.plugins.ai_detector.result }}"
```

**SONUÇ:** Tasker'ın hangi plugin'leri beklediği explicit olmalı.
Template'de kullanılan her plugin = implicit dependency.

### Devil's Advocate: Template Parser?

```python
# Otomatik dependency detection?
def extract_dependencies(template: str) -> List[str]:
    # {{ job.plugins.X.Y }} pattern'lerini bul
    return ['tmdb', 'ai_detector']
```

**Problem:** Jinja2 conditionals:
```jinja2
{% if some_condition %}
  {{ job.plugins.optional_plugin.data }}
{% endif %}
```
Bu optional dependency mi? Required mı? Parser bilemez.

**SONUÇ:** Explicit dependency > Implicit parsing

---

## 2.3 CONFIG → CORE → PLUGIN İLİŞKİSİ

### Soru: Config değerleri nasıl resolve edilecek?

```yaml
# config.yml
tmdb:
  language: tr-TR
  api_key: ${TMDB_API_KEY}

tasker:
  tasks:
    - template: "{{ job.plugins.tmdb.movie.title }}"
```

### Akış Analizi

```
┌─────────────────────────────────────────────────────────────┐
│                    CONFIG FLOW                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Core loads config.yml                                    │
│     └── Raw YAML → Dict                                      │
│                                                              │
│  2. Core resolves ${ENV_VAR}                                 │
│     └── ${TMDB_API_KEY} → "abc123..."                        │
│                                                              │
│  3. Core passes to plugin                                    │
│     └── plugin.config = {"language": "tr-TR", ...}           │
│                                                              │
│  4. Plugin executes, returns data                            │
│     └── result = {"movie": {"title": "..."}}                 │
│                                                              │
│  5. Core stores in state                                     │
│     └── job.plugins.tmdb = result                            │
│                                                              │
│  6. Tasker renders template                                  │
│     └── context = {job: {..., plugins: {tmdb: {...}}}}       │
│     └── Jinja2.render(template, context)                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Soru: Tasker template'leri ne zaman resolve edilir?

**Option A:** Config load time (YANLIŞ)
```python
# config load sırasında
template = "{{ job.plugins.tmdb.movie.title }}"
# job yok, tmdb çalışmadı, HATA
```

**Option B:** Execution time (DOĞRU)
```python
# tasker çalışırken
for job in jobs:
    context = build_context(job)  # state'ten
    rendered = jinja2.render(template, context)
```

**SONUÇ:** Template = lazy evaluation at execution time

---

## 2.4 TASK SYSTEM → PLUGIN DÖNÜŞÜMÜ

### User'ın Önerisi:
> "task system plugin olsun, ismi tasker, modify stage'inde"

### Conflict Analizi

**Conflict 1: Core'dan Plugin'e Taşıma**

```
MEVCUT:
Core → TaskManager (hardcoded)
     → print, save actions

ÖNERİLEN:
Core → Plugin System → Tasker Plugin
                     → print, save actions
```

Soru: Tasker plugin başka plugin'lerin sonucunu nasıl bilecek?

**Cevap:** Aynı şekilde - state'ten:
```python
class TaskerPlugin:
    def execute(self, job, services):
        # job.plugins içinde tüm plugin sonuçları var
        context = {'job': job.to_dict()}
        for task in self.config['tasks']:
            rendered = jinja2.render(task['template'], context)
```

**Conflict 2: Save İşlemi Kimin Sorumluluğu?**

```
MEVCUT:
TaskManager.save() → shutil.copy() / hardlink

ÖNERİLEN:
TaskerPlugin.save() → shutil.copy() / hardlink
                    → EventBus.emit('file.created')
```

Soru: Plugin dosya sistemi erişimi olmalı mı?

**Cevap:** Evet, zaten var. Scanner dosya okuyor.
Tasker dosya yazabilir. services.filesystem sağlanır.

**Conflict 3: Task Definition Nerede?**

```yaml
# MEVCUT config.yml
tasks:
  - name: print_movie
    type: print
    template: ...

# ÖNERİLEN
tasker:
  tasks:
    - name: print_movie
      type: print
      template: ...
```

Fark yok, sadece namespace değişiyor.

### Devil's Advocate: Neden Plugin Yapalım?

**Argüman FOR plugin:**
- Tutarlılık: her şey plugin
- Extensibility: farklı tasker'lar (json, xml, custom)
- Core daha dumb

**Argüman AGAINST plugin:**
- Complexity: bir şeyi plugin yapmak overhead
- Task system çok temel, core'da olmalı
- Her şey plugin olursa core ne yapar?

**User'ın Cevabı:**
> "core daha çok arşiv düzenleme playground'una dönüşecek, dumb olacak ama plugin system sayesinde..."

**SONUÇ:** User'ın vizyonu = FlexGet modeli. Core = orchestrator + plugin loader. Her feature = plugin.

---

## 2.5 PROVIDES/REQUIRES/TRIGGERS_ON - TERMİNOLOJİ

### Endüstri Araştırması

| Sistem | "Sağlar" | "Gerektirir" | "Tetikler" |
|--------|----------|--------------|------------|
| OSGi | Provide-Capability | Require-Capability | - |
| Gradle | capabilities | dependencies | - |
| npm | exports | dependencies | - |
| Airflow | - | upstream/downstream | trigger_rule |
| Docker | - | depends_on | - |
| Kubernetes | - | - | triggers |
| FlexGet | - | - | on_* hooks |

### Analiz

**provides/requires** = OSGi/Gradle pattern (capability-based)
**depends_on** = Docker/Airflow pattern (explicit ordering)
**triggers_on** = Kubernetes/Event pattern

### Önerilen İsimler (Endüstri Uyumlu)

```yaml
# Option A: OSGi-inspired
capabilities:          # provides
  - metadata.movie
  - api.call
requirements:          # requires
  - input.files

# Option B: Simpler
provides:
  - metadata.movie
requires:
  - input.files
on_event:              # triggers_on
  - file.created
```

**SONUÇ:** `provides` / `requires` / `on_event` daha clean ve anlaşılır.

---

## 2.6 EVENT BUS - EVENT DISCOVERY

### Problem

Plugin-agnostic sistemde EventBus event'leri nasıl keşfedecek?

```
Scenario:
1. TMDb plugin çalışır
2. EventBus.emit('metadata.completed', data)
3. Rclone plugin bunu dinliyor mu? Dinlemeli mi?
```

### Endüstri Çözümleri

**A. Schema Registry (Kafka Pattern)**
```yaml
# events_schema.yml
events:
  file.created:
    payload: {path: string, size: int}
  metadata.completed:
    payload: {plugin: string, job_id: string}
```

**B. Convention-based (Node.js Pattern)**
```
Events follow naming convention:
- {domain}.{action}
- file.created, file.deleted
- plugin.started, plugin.completed
- job.created, job.failed
```

**C. Plugin Declares (Manifest)**
```yaml
# manifest.yml
emits:
  - file.created
  - metadata.movie
on_event:
  - file.created
```

### Önerim: Hybrid

```yaml
# Core events (built-in, documented)
core_events:
  - run.started
  - run.completed
  - job.created
  - job.completed
  - plugin.started
  - plugin.completed
  - file.created
  - file.deleted
  - file.moved

# Plugin manifest
emits: [custom.event]    # Optional, for documentation
on_event: [file.created] # Subscribe
```

**SONUÇ:** Convention + Manifest declaration

---

## 2.7 PER_RUN / PER_JOB ÇAKIŞMALARI

### Senaryo 1: per_run ile per_job Aynı Stage'de

```
MODIFY stage:
- DuplicateCleaner (per_run) → tüm job'ları analiz
- Splitter (per_job) → job başına çalış
```

Soru: Hangisi önce?

**Cevap:** requires/provides ile belirlenir:
```yaml
# duplicate_cleaner
provides: [duplicates.cleaned]
requires: [metadata.movie]  # tmdb bitsin

# splitter
requires: [duplicates.cleaned]  # cleaner bitsin
```

### Senaryo 2: per_run Event Collection

```
TMDb (per_job):
- Job 1: emit('api.call')
- Job 2: emit('api.call')
- Job 100: emit('api.call')

Rclone (per_run, on_event: [api.call]):
- 100 event geldi, 100 kez mi çalışacak?
```

**Çözüm Seçenekleri:**

**A. Debounce/Batch**
```python
class Orchestrator:
    def handle_event(self, event):
        if plugin.execution_mode == 'per_run':
            self.batch_events[plugin].append(event)
            # Run sonunda toplu çalıştır
```

**B. Run-End Trigger**
```yaml
# manifest
on_event: [run.completed]  # Sadece run bitince
```

**C. provides/requires (Event Yerine)**
```yaml
# tmdb
provides: [api.completed]

# rclone
requires: [api.completed]  # TMDb bitsin
# on_event yok, sadece dependency
```

**SONUÇ:** per_run plugin'ler için `on_event` değil `requires` kullan.
`on_event` sadece per_job reactive plugin'ler için.

---

## 2.8 SESSION 11 STRATEGY ENTEGRASYONU

### Mevcut Strategy Dosyaları

```
session_11_strategy/
├── 01_state_structure_and_naming.md    ✅ Geçerli
├── 02_plugin_system_and_services.md    ⚠️ Güncellenmeli
├── 03_orchestrator_and_execution_flow.md ⚠️ Güncellenmeli
├── 04_config_manifest_and_external_tasks.md ⚠️ Güncellenmeli
├── 05_validation_and_testing.md        ✅ Geçerli
├── 06_mongodb_and_persistence.md       ✅ Geçerli
├── 07_memory_management.md             ✅ Geçerli (Optional)
├── 08_project_structure.md             ⚠️ Güncellenmeli
├── 09_api_response_structure.md        ✅ Geçerli
├── 10_final_decisions.md               ⚠️ Güncellenmeli
```

### Güncellenmesi Gerekenler

1. **02_plugin_system**: 6 stage → pure dependency model?
2. **03_orchestrator**: Topological sort implementation
3. **04_config_manifest**: FlexGet-style config
4. **08_project_structure**: Tasker plugin location
5. **10_final_decisions**: Yeni terimler

---

# BÖLÜM 3: KARARLAR VE ÖNERİLER

## 3.1 Stage Sistemi

```
ÖNCEKİ: 6 stage (rigid)
YENİ: 2 soft category + pure dependency

categories:
  - input: Job oluşturur (scanner, file-reader)
  - process: Data ekler/değiştirir (diğer hepsi)

Execution order = topological sort of requires/provides
```

## 3.2 Manifest Schema (Final Öneri)

```yaml
name: string
version: string
category: input | process     # Sadece semantik

# Dependency (DAG)
provides:
  - capability.names
requires:
  - capability.names

# Reactive (Event-based)
on_event:
  - event.names

# Execution
mode: per_job | per_run

class_name: string
```

## 3.3 Terminology (Final)

| Kavram | İsim | Neden |
|--------|------|-------|
| Ne sağlar | `provides` | OSGi, Gradle standard |
| Ne gerektirir | `requires` | OSGi, npm standard |
| Ne dinler | `on_event` | Explicit, clear |
| Çalışma modu | `mode` | Kısa, clear |
| Kategori | `category` | Mevcut (tutarlılık) |

## 3.4 Task System

```
Karar: Tasker plugin olsun
Stage: Yok (requires ile sıra belirlenir)
provides: [output.saved, output.printed]
```

## 3.5 FlexGet-Style Config

```yaml
# config.yml - NO plugins: parent
scanner:
  targets: [/downloads]

renamer: {}

tmdb:
  api_key: ${TMDB_API_KEY}

tasker:
  tasks:
    - name: print_movie
      template: ...
```

---

# BÖLÜM 4: AÇIK SORULAR

1. **Circular dependency detection**: A requires B, B requires A?

2. **Optional requires**: TMDb movie OR show varsa çalış?
   ```yaml
   requires:
     any_of: [parsed.movie, parsed.show]
   ```

3. **Conditional provides**: Sadece movie bulunca provide et?
   ```yaml
   provides:
     - metadata.movie  # if movie found
   ```

4. **Event naming convention**: Camel? Dot? Underscore?
   - `fileCreated` vs `file.created` vs `file_created`
   - Önerim: `domain.action` (dot notation)

5. **Core events vs Plugin events**: Ayrı namespace?
   - `core.run.started` vs `plugin.tmdb.completed`

---

# BÖLÜM 5: SONRAKI ADIMLAR

1. User feedback on:
   - Stage'siz pure dependency model
   - Manifest schema
   - Terminology

2. Güncellenecek dosyalar:
   - 02_plugin_system
   - 03_orchestrator
   - 04_config_manifest
   - 10_final_decisions

3. Implementation plan

---

**Status: AWAITING USER FEEDBACK**
