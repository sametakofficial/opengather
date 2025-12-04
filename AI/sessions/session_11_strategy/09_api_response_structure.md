# API RESPONSE STRUCTURE

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/06_STATE_MODEL.md
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- input.path -> input.value
- input.data eklendi (size_bytes, source, etc.)
- output.values eklendi (paths array)
- output.data eklendi (task results detay)
- plugins AYRI COLLECTION (memory management için)
- job.plugins YOK - ayrı endpoint ile erişilir
- Template context'e plugins alias inject edilir
```

**ÖNEMLİ:** Plugins ayrı collection'da saklanır!

- Memory management (hot/cold tiering)
- API: GET /jobs/{id}/plugins
- Template: {{ plugins.tmdb.movie.title }}

---

## 1. FULL RESPONSE SCHEMA

```javascript
{
  // Run-level data
  "run": {
    "id": "run_abc123",
    "status": {
      "state": "completed",
      "success": true,
      "total_jobs": 10,
      "completed": 10,
      "failed": 0,
      "started_at": "2025-11-30T12:00:00Z",
      "finished_at": "2025-11-30T12:01:00Z",
      "duration_ms": 60000
    },
    "config": {
      "options": {
        "debug": true,
        "dry_run": false
      },
      "plugins": {...},
      "tasks": [...]
    }
  },

  // All jobs
  "jobs": [
    {
      "index": 0,
      "job_id": "job_run_abc123_0",

      "input": {
        "value": "/media/file.mkv",    // v2: path -> value
        "data": {                       // v2: eklendi
          "filename": "file.mkv",
          "extension": "mkv",
          "size_bytes": 5368709120,
          "source": "filesystem"
        }
      },

      "status": {
        "state": "completed",
        "success": true,
        "executed_plugins": ["scanner", "renamer", "tmdb"],
        "failed_plugins": [],
        "skipped_plugins": ["tvdb"],
        "started_at": "2025-11-30T12:00:01Z",
        "finished_at": "2025-11-30T12:00:03Z",
        "duration_ms": 2500
      },

      "output": {
        "values": ["/movies/Mr. & Mrs. Smith (2005)/file.mkv"],
        "data": {
          "tasks": {
            "print_header": {
              "type": "print",
              "success": true,
              "rendered": "MOVIE: Mr. & Mrs. Smith (2005)"
            },
            "save_file": {
              "type": "save",
              "success": true,
              "destination": "/movies/Mr. & Mrs. Smith (2005)/file.mkv"
            }
          }
        }
      }

      // NOT: plugins burada YOK!
      // Ayrı endpoint: GET /jobs/{job_id}/plugins
    }
  ],

  // PLUGINS AYRI COLLECTION (memory management)
  // Endpoint: GET /v1/jobs/{job_id}/plugins
  "plugins": [
    {
      "job_id": "job_run_abc123_0",
      "plugin_name": "scanner",
      "stage": "input",
      "status": {"success": true, "duration_ms": 100},
      "data": {
        "filename": "file.mkv",
        "extension": "mkv",
        "size_bytes": 5368709120
      }
    },
    {
      "job_id": "job_run_abc123_0",
      "plugin_name": "renamer",
      "stage": "parse",
      "status": {"success": true, "duration_ms": 50},
      "data": {
        "parsed": {
          "movie": {
            "name": "Mr. & Mrs. Smith",
            "year": 2005,
            "quality": "1080p"
          }
        }
      }
    },
    {
      "job_id": "job_run_abc123_0",
      "plugin_name": "tmdb",
      "stage": "data",
      "status": {"success": true, "duration_ms": 800},
      "data": {
        "movie": {
          "id": 1234,
          "title": "Mr. & Mrs. Smith",
          "original_title": "Mr. & Mrs. Smith",
          "release_date": "2005-06-10",
          "overview": "...",
          "poster_path": "/abc123.jpg",
          "vote_average": 7.2,
          "genres": ["Action", "Comedy", "Romance"]
        }
      }
    },
    {
      "job_id": "job_run_abc123_0",
      "plugin_name": "ffprobe",
      "stage": "data",
      "status": {"success": true, "duration_ms": 500},
      "data": {
        "video": {
          "codec": "hevc",
          "width": 1920,
          "height": 1080,
          "fps": 23.976
        },
        "audio": [{"codec": "aac", "channels": 6, "language": "eng"}]
      }
    }
  ]
}
```

---

## 2. TEMPLATE CONTEXT

Template rendering için context:

```python
context = {
    # State access
    'run': {...},
    'job': {...},
    'jobs': [...],

    # PLUGINS (ayrı collection'dan yüklenir, context'e inject edilir)
    'plugins': load_plugins_for_job(job.id),  # {tmdb: {...}, renamer: {...}}

    # Config access
    'options': {...},
    'config': {...},

    # Short aliases
    'r': run,
    'j': job,
    'o': options,
}

# NOT: job.plugins YOK
# plugins ayrı key olarak inject edilir
# Ama alias ile job.plugins olarak da erişilebilir
```

---

## 3. TEMPLATE ACCESS PATTERNS

### 3.1 Run Data

```jinja2
{{ run.id }}
{{ run.status.total_jobs }}
{{ run.status.completed }}
{{ run.config.options.debug }}
```

### 3.2 Current Job

```jinja2
{{ job.index }}
{{ job.job_id }}
{{ job.input.path }}
{{ job.input.category }}
{{ job.status.success }}
```

### 3.3 Plugin Data

```jinja2
{# Direct access (plugins context'e inject edilir) #}
{{ plugins.tmdb.movie.title }}
{{ plugins.renamer.parsed.movie.name }}
{{ plugins.ffprobe.video.codec }}

{# job.plugins alias olarak da çalışır #}
{{ job.plugins.tmdb.movie.title }}

{# With filters #}
{{ plugins.tmdb.movie.release_date[:4] }}
{{ job.input.value | basename }}
```

**NOT:** `plugins` ayrı collection'dan yüklenir ve context'e inject edilir.

### 3.4 Iteration

```jinja2
{# All jobs #}
{% for j in jobs %}
  {{ j.index }}: {{ j.plugins.renamer.parsed.movie.name }}
{% endfor %}

{# Plugin genres #}
{% for genre in job.plugins.tmdb.movie.genres %}
  - {{ genre }}
{% endfor %}
```

### 3.5 Conditionals

```jinja2
{% if job.plugins.renamer.parsed.movie %}
  MOVIE: {{ job.plugins.tmdb.movie.title }}
{% elif job.plugins.renamer.parsed.show %}
  SHOW: {{ job.plugins.tmdb.show.name }}
{% endif %}
```

---

## 4. TEMPLATE ALIASES

### 4.1 System Aliases

```python
# template_manager.py
context = {
    # Full names
    'run': run_data,
    'job': job_data,
    'jobs': jobs_data,
    'options': config_options,

    # Short aliases
    'r': run_data,
    'j': job_data,
    'o': config_options,
}
```

### 4.2 Custom Aliases (Jinja2 set)

```jinja2
{% set m = job.plugins.tmdb.movie %}
{% set title = m.title %}
{{ title }} ({{ m.release_date[:4] }})
```

---

## 5. RESPONSE BUILDER

```python
class ResponseBuilder:
    def __init__(self, state: StateManager):
        self._state = state

    def build(self) -> Dict:
        """Build full API response"""
        run = self._state.get_current_run()
        jobs = self._state.get_all_jobs()

        return {
            'run': run.to_dict() if run else {},
            'jobs': [j.to_dict() for j in jobs]
        }

    def build_for_template(self, job_index: Optional[int] = None) -> Dict:
        """Build template context with aliases"""
        response = self.build()

        context = {
            # Primary
            'run': response['run'],
            'jobs': response['jobs'],

            # Aliases
            'execution': response['run'],
            'matches': response['jobs'],
        }

        # Current job
        if job_index is not None and job_index < len(response['jobs']):
            context['job'] = response['jobs'][job_index]
            context['match'] = context['job']

        return context
```

---

## 6. PLUGIN DATA CONVENTIONS

### 6.1 Standard Keys

```
Plugin          Required Keys
─────────────────────────────────────────────────
scanner         input.path, input.virtual
renamer         parsed.movie OR parsed.show
tmdb            movie OR show (+ season, episode)
tvdb            show (+ season, episode)
ffprobe         video, audio[], container
```

### 6.2 Status Object

Her plugin'in `status` objesi:

```javascript
{
  "status": {
    "success": true,
    "started_at": "...",
    "finished_at": "...",
    "duration_ms": 123,
    "error": null
  }
}
```

---

## 7. ERROR RESPONSE

```javascript
{
  "run": {
    "id": "run_xyz789",
    "status": {
      "state": "failed",
      "success": false,
      "total_jobs": 5,
      "completed": 3,
      "failed": 2,
      "error": "Critical error in phase: metadata"
    }
  },
  "jobs": [
    {
      "index": 3,
      "status": {
        "state": "failed",
        "success": false,
        "executed_plugins": ["scanner", "renamer"],
        "failed_plugins": ["tmdb"],
        "error": "API rate limit exceeded"
      },
      "plugins": {
        "tmdb": {
          "status": {
            "success": false,
            "error": "HTTP 429: Too Many Requests"
          }
        }
      }
    }
  ]
}
```

---

## 8. MEVCUT vs YENİ

### Mevcut

```javascript
{
  "globals": {
    "status": {...},
    "config": {...}
  },
  "matches": [
    {
      "globals": {
        "index": 0,
        "input_path": "...",
        "status": {...}
      },
      "plugins": {...}
    }
  ]
}
```

### Yeni

```javascript
{
  "run": {
    "id": "...",
    "status": {...},
    "config": {...}
  },
  "jobs": [
    {
      "index": 0,
      "job_id": "...",
      "input": {...},
      "status": {...},
      "output": {...},
      "plugins": {...}
    }
  ]
}
```

**Key Changes:**

- `globals` → `run`
- `matches` → `jobs`
- `globals.input_path` → `input.path`
- `+job_id` field
- `+output.tasks`
- Nested structure throughout

---

**Son Guncelleme:** 2025-12-02
