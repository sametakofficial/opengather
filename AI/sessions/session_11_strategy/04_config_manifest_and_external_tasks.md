# CONFIG, MANIFEST & EXTERNAL TASKS

```yaml
date: 2025-11-30
sources: v4, v5-part2, user feedback
status: final
```

---

## 1. TEMEL FELSEFE

```
config.yml = SOURCE OF TRUTH
├── Her şeyi tanımlayabilir
├── Plugin config, task config, options
├── Jinja2 template kullanır
└── Alias sistemi kullanır

manifest.yml = PLUGIN'E ÖZEL EKLEME
├── Sadece plugin metadata tanımlar
├── config.yml'e external ekleme
├── config.yml'de de yazılabilir (ama best practice değil)
└── Jinja2 ve alias kullanır

external_task.yml = TASK'A ÖZEL EKLEME
├── Sadece task tanımlar
├── config.yml'e external ekleme
├── config.yml'de de yazılabilir (ama uzun olur)
└── Jinja2 ve alias kullanır
```

---

## 2. ORTAK ÖZELLİKLER

```
Özellik                 config.yml    manifest.yml    external_task
────────────────────────────────────────────────────────────────────
Jinja2 template         ✓             ✓               ✓
Alias sistemi           ✓             ✓               ✓
${ENV_VAR} resolution   ✓             ✓               ✓
State erişimi           ✓             ✓               ✓
Condition yazabilir     ✓             ✓               ✓
```

---

## 3. FARKLILIKLAR (MANIFEST YAPAMAZ)

```
Özellik                     config.yml    manifest.yml
──────────────────────────────────────────────────────────
options tanımlama           ✓             ✗
Birden fazla plugin         ✓             ✗ (sadece kendisi)
Task tanımlama              ✓             ✗
Memory config               ✓             ✗
Plugin enable/disable       ✓             ✗
Başka plugin config         ✓             ✗
```

```
Özellik                     config.yml    external_task
──────────────────────────────────────────────────────────
options tanımlama           ✓             ✗
Plugin tanımlama            ✓             ✗
Memory config               ✓             ✗
Birden fazla task           ✓             ✗ (sadece kendisi)
```

---

## 4. ALIAS SİSTEMİ

### 4.1 Nerede Tanımlanır?

```
Alias tanımlama = Jinja2 set directive
Her yerde kullanılabilir: config.yml, manifest.yml, external_task.yml
```

### 4.2 Syntax

```jinja2
{# Alias tanımlama #}
{% set m = job.plugins.tmdb.movie %}
{% set title = m.title %}
{% set year = m.release_date[:4] %}

{# Kullanım #}
{{ title }} ({{ year }})
```

### 4.3 Global Aliases (Sistem tarafından)

```python
# Template context'e otomatik eklenir
context = {
    'run': run_state,
    'job': current_job,
    'jobs': all_jobs,
    'options': config['options'],
    
    # Kısa aliaslar
    'r': run_state,
    'j': current_job,
}
```

### 4.4 Örnek: manifest.yml'de Alias

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
phase: metadata
requires:
  - renamer.parsed.movie
  - renamer.parsed.show

# Condition with alias
condition: |
  {% set p = job.plugins.renamer.parsed %}
  {{ p.movie or p.show }}
```

### 4.5 Örnek: external_task.yml'de Alias

```yaml
# tasks/movie_rename.yml
name: movie_rename
type: save
condition: "{{ job.plugins.renamer.parsed.movie }}"
template: |
  {% set m = job.plugins.tmdb.movie %}
  {% set r = job.plugins.renamer.parsed.movie %}
  {{ options.movies_dst }}/{{ m.title }} ({{ m.release_date[:4] }})/{{ r.name }}.{{ job.input.path | ext }}
```

---

## 5. CONFIG.YML YAPISI

```yaml
# config.yml - SOURCE OF TRUTH

options:
  debug: bool
  dry_run: bool
  hardlink: bool
  movies_dst: string
  shows_dst: string

plugins:
  {plugin_name}:
    enabled: bool
    # Plugin-specific config...
    # Manifest fields can be overridden here

tasks:
  - name: string
    type: print | save | summary
    condition: string
    template: string
  - external: path/to/task.yml   # External task reference

memory:
  max_state_mb: int
  flush_threshold: float
```

### 5.1 Full Inline Example

```yaml
options:
  debug: true
  dry_run: true
  movies_dst: /media/movies
  shows_dst: /media/shows

plugins:
  scanner:
    enabled: true
    targets:
      - /downloads
    recursive: true
    
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}
    language: tr-TR

tasks:
  - name: print_movie
    type: print
    condition: "{{ job.plugins.renamer.parsed.movie }}"
    template: |
      {% set m = job.plugins.tmdb.movie %}
      MOVIE: {{ m.title }} ({{ m.release_date[:4] }})
      
  - external: tasks/save_movie.yml
```

---

## 6. MANIFEST.YML YAPISI

```yaml
# plugins/{name}/manifest.yml

# Identity (required)
name: string
version: string

# Execution (required)
phase: input | parse | metadata | modify | finalize
execution_mode: per_job | per_run

# Dependencies
requires: List[string]
subscribes: List[string]        # EventBus events

# Implementation
class_name: string
entry_point: string             # Default: client.py

# Config schema (optional)
config_schema:
  {field}:
    type: string | int | bool | list
    required: bool
    default: any

# Optional: condition for execution
condition: string               # Jinja2, can use aliases
```

### 6.1 Manifest Example

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
phase: metadata
execution_mode: per_job

requires:
  - renamer.parsed.movie
  - renamer.parsed.show

class_name: TMDbPlugin

config_schema:
  api_key:
    type: string
    required: true
  language:
    type: string
    default: en-US
```

---

## 7. EXTERNAL TASK YAPISI

```yaml
# tasks/{name}.yml

name: string
type: print | save | summary
condition: string               # Jinja2
template: string                # For print
destination: string             # For save
```

### 7.1 External Task Example

```yaml
# tasks/save_movie.yml
name: save_movie
type: save
condition: |
  {{ job.plugins.renamer.parsed.movie and job.plugins.tmdb.movie }}
destination: |
  {% set m = job.plugins.tmdb.movie %}
  {{ options.movies_dst }}/{{ m.title }} ({{ m.release_date[:4] }})/{{ job.input.path | basename }}
```

---

## 8. MERGE LOGIC

```
┌─────────────────────────────────────────────────────────────┐
│                    CONFIGURATION MERGE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Load config.yml (base)                                   │
│                                                              │
│  2. For each plugin in config.plugins:                       │
│     ├── Load manifest.yml                                    │
│     ├── Merge: config overrides manifest                     │
│     └── Validate against config_schema                       │
│                                                              │
│  3. For each task in config.tasks:                           │
│     ├── If inline: use directly                              │
│     └── If external: load and merge                          │
│                                                              │
│  4. Resolve ${ENV_VAR} patterns                              │
│                                                              │
│  5. Final validation                                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 8.1 Override Priority

```
config.yml > manifest.yml defaults

Example:
manifest.yml:  language: en-US (default)
config.yml:    language: tr-TR
Result:        language: tr-TR
```

---

## 9. JINJA2 CONTEXT

```python
def build_context(run: RunState, job: JobState, config: Dict) -> Dict:
    return {
        # State access
        'run': run.to_dict(),
        'job': job.to_dict(),
        'jobs': [j.to_dict() for j in all_jobs],
        
        # Config access
        'options': config.get('options', {}),
        'plugins': config.get('plugins', {}),
        
        # Short aliases
        'r': run.to_dict(),
        'j': job.to_dict(),
        'o': config.get('options', {}),
    }
```

---

## 10. VALIDATION FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    VALIDATION                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  config.yml:                                                 │
│  ├── options: type check                                     │
│  ├── plugins: enabled field required                         │
│  ├── tasks: name, type required                              │
│  └── memory: range check                                     │
│                                                              │
│  manifest.yml:                                               │
│  ├── name, version, phase, class_name: required              │
│  ├── phase: valid enum                                       │
│  ├── execution_mode: valid enum                              │
│  └── config_schema: valid types                              │
│                                                              │
│  external_task.yml:                                          │
│  ├── name, type: required                                    │
│  ├── type: valid enum                                        │
│  └── template/destination: required based on type            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. DOSYA YAPISI

```
archiverr/
├── config.yml                  # Main config
├── .env                        # Environment variables
│
├── plugins/
│   ├── scanner/
│   │   ├── manifest.yml        # Plugin metadata
│   │   └── client.py
│   ├── tmdb/
│   │   ├── manifest.yml
│   │   └── client.py
│   └── ...
│
└── tasks/                      # External tasks (optional)
    ├── save_movie.yml
    ├── save_show.yml
    └── summary_report.yml
```

---

## 12. IMPLEMENTATION

```python
class ConfigLoader:
    def load(self, config_path: Path) -> Config:
        # 1. Load base config
        raw = yaml.safe_load(config_path.read_text())
        
        # 2. Resolve env vars
        resolved = self._resolve_env_vars(raw)
        
        # 3. Load and merge manifests
        plugins = {}
        for name, plugin_config in resolved.get('plugins', {}).items():
            manifest = self._load_manifest(name)
            plugins[name] = self._merge_plugin(manifest, plugin_config)
        
        # 4. Load external tasks
        tasks = []
        for task in resolved.get('tasks', []):
            if 'external' in task:
                tasks.append(self._load_external_task(task['external']))
            else:
                tasks.append(task)
        
        # 5. Validate
        self._validate(resolved, plugins, tasks)
        
        return Config(
            options=resolved.get('options', {}),
            plugins=plugins,
            tasks=tasks,
            memory=resolved.get('memory', {})
        )
```

---

**Son Güncelleme:** 2025-11-30
