# DEPRECATED - Use AI/DATASETS.yml instead

See AI/DATASETS.yml for the current data structures reference.

---

## 1. CONFIG.YML

### 1.1 Üst Düzey Yapı

```yaml
aliases:
  <shortcut>: <path>

options:
  log_level: DEBUG | INFO | WARNING | ERROR | CRITICAL
  debug: boolean
  dry_run: boolean
  hardlink: boolean

<plugin_name>:
  enabled: boolean
  <plugin_specific_config>
```

### 1.2 Aliases

```yaml
aliases:
  e: "execution"
  m: "match"
  g: "globals"
  movie: "renamer.parsed.movie"
  show: "renamer.parsed.show"
  tmdb_movie: "tmdb.movie"
  tmdb_show: "tmdb.show"
```

### 1.3 Options

```yaml
options:
  log_level: string
  debug: boolean
  dry_run: boolean
  hardlink: boolean
  memory:
    <key>: <value>
```

### 1.4 Scanner Plugin Config

```yaml
scanner:
  enabled: boolean
  targets:
    - string
  allow_virtual_paths: boolean
  extensions:
    - string
  recursive: boolean
  min_size_bytes: integer
```

### 1.5 Renamer Plugin Config

```yaml
renamer:
  enabled: boolean
  media_type: auto | movie | show
```

### 1.6 TMDb Plugin Config

```yaml
tmdb:
  enabled: boolean
  api_key: string
  language: string
  region: string
  include_raw_data: boolean
  extras:
    movie_credits: boolean
    movie_images: boolean
    movie_keywords: boolean
    movie_videos: boolean
    tv_credits: boolean
    tv_episode_credits: boolean
    tv_episode_images: boolean
    tv_images: boolean
    tv_keywords: boolean
    tv_season_images: boolean
    tv_videos: boolean
```

### 1.7 Tasker Plugin Config

```yaml
tasker:
  enabled: boolean
  dry_run: boolean
  save_output: boolean
  output_dir: string
  tasks:
    - name: string
      type: print | save
      template: string
      condition: string
      destination: string
```

---

## 2. PLUGIN MANIFEST (manifest.yml)

### 2.1 Tam Yapı

```yaml
name: string
version: string
description: string
class_name: string
entry_point: string

stage: input | parse | data | output
run_mode: per_run | per_job
category: input | output

requires:
  - string
provides:
  - string
trigger_rule: all_success | one_success | all_done | all_fail | none_fail

categories:
  - movie
  - show

config_schema:
  <field_name>:
    type: string | integer | boolean | array | object
    required: boolean
    default: <value>
    min_length: integer
    max_length: integer
    secret: boolean

fs_lock:
  - string

hooks:
  - string
listens_to:
  - string

capabilities:
  - string

reactive: boolean
```

### 2.2 Stage Değerleri

| Stage | Açıklama | Run Mode |
|-------|----------|----------|
| input | Dosya keşfi | per_run |
| parse | Dosya adı parsing | per_job |
| data | Harici veri çekme | per_job |
| output | Çıktı üretme | per_job |

### 2.3 Trigger Rule Değerleri

| Rule | Açıklama |
|------|----------|
| all_success | Tüm requires başarılı olmalı |
| one_success | En az bir requires başarılı olmalı |
| all_done | Tüm requires tamamlanmalı |
| all_fail | Tüm requires başarısız olmalı |
| none_fail | Hiçbir requires başarısız olmamalı |

---

## 3. STATE MODELS

### 3.1 RunState

```python
@dataclass
class RunState:
    id: str
    status: RunStatus
    config: dict[str, Any]
    plugins: dict[str, dict[str, Any]]
```

```json
{
  "id": "run_abc12345",
  "status": {
    "state": "pending | running | success | failed | partial | cancelled",
    "success": true,
    "total_jobs": 0,
    "completed": 0,
    "failed": 0,
    "plugins": {},
    "started_at": "2024-12-19T10:00:00",
    "finished_at": "2024-12-19T10:01:00",
    "duration_ms": 60000
  },
  "config": {},
  "plugins": {}
}
```

### 3.2 JobState

```python
@dataclass
class JobState:
    index: int
    run_id: str
    id: str
    input: InputData
    output: OutputData
    status: JobStatus
    plugins: dict[str, dict[str, Any]]
```

```json
{
  "id": "job_run_abc12345_0",
  "index": 0,
  "run_id": "run_abc12345",
  "input": {
    "value": "/path/to/file.mkv",
    "data": {}
  },
  "output": {
    "values": [],
    "data": {}
  },
  "status": {
    "state": "pending | running | success | failed",
    "success": true,
    "plugins": {
      "<plugin_name>": {
        "state": "completed | failed | skipped",
        "success": true,
        "duration_ms": 100
      }
    },
    "started_at": "2024-12-19T10:00:00",
    "finished_at": "2024-12-19T10:00:01",
    "duration_ms": 1000
  },
  "plugins": {
    "<plugin_name>": {}
  }
}
```

### 3.3 InputData

```json
{
  "value": "string",
  "data": {}
}
```

### 3.4 OutputData

```json
{
  "values": ["string"],
  "data": {}
}
```

### 3.5 StateEnum Değerleri

| Değer | Açıklama |
|-------|----------|
| pending | Bekliyor |
| running | Çalışıyor |
| success | Başarılı |
| failed | Başarısız |
| partial | Kısmi başarı |
| cancelled | İptal edildi |

---

## 4. EVENT BUS

### 4.1 Event Yapısı

```python
@dataclass
class Event:
    name: str
    data: dict[str, Any]
    timestamp: datetime
    source: str
```

### 4.2 Event İsimleri

#### Run Lifecycle

| Event | Data |
|-------|------|
| run.started | run_id |
| run.completed | run_id, success, duration_ms |
| run.failed | run_id, error |
| run.error | run_id, error |

#### Stage Lifecycle

| Event | Data |
|-------|------|
| stage.started | stage, plugins |
| stage.completed | stage, duration_ms |
| stage.failed | stage, error |

#### Job Lifecycle

| Event | Data |
|-------|------|
| job.created | job_id, index, input |
| job.started | job_id |
| job.completed | job_id, success |
| job.failed | job_id, error |
| job.updated | job_id, field, value |
| job.stage_completed | job_id, stage |

#### Plugin Lifecycle

| Event | Data |
|-------|------|
| plugin.started | plugin_name, job_id |
| plugin.completed | plugin_name, job_id, success, data, duration_ms |
| plugin.failed | plugin_name, job_id, error, duration_ms |
| plugin.skipped | plugin_name, job_id, reason |
| plugin.progress | plugin_name, percent, message |
| plugin.updated | plugin_name, job_id, data |

#### Task Lifecycle

| Event | Data |
|-------|------|
| task.started | task_name, job_id |
| task.completed | task_name, job_id |
| task.failed | task_name, job_id, error |

#### State Changes

| Event | Data |
|-------|------|
| state.changed | entity, id, field, value |

#### Database

| Event | Data |
|-------|------|
| db.connected | backend |
| db.disconnected | backend |
| db.synced | collections |
| db.error | error |

---

## 5. MONGODB COLLECTIONS

### 5.1 runs Collection

```json
{
  "_id": "run_abc12345",
  "id": "run_abc12345",
  "status": {
    "state": "string",
    "success": true,
    "total_jobs": 0,
    "completed": 0,
    "failed": 0,
    "started_at": "ISODate",
    "finished_at": "ISODate",
    "duration_ms": 0
  },
  "config": {},
  "plugins": {},
  "created_at": "ISODate"
}
```

### 5.2 jobs Collection

```json
{
  "_id": "job_run_abc12345_0",
  "id": "job_run_abc12345_0",
  "run_id": "run_abc12345",
  "index": 0,
  "input": {
    "value": "string",
    "data": {}
  },
  "output": {
    "values": [],
    "data": {}
  },
  "status": {
    "state": "string",
    "success": true,
    "plugins": {},
    "started_at": "ISODate",
    "finished_at": "ISODate",
    "duration_ms": 0
  },
  "plugins": {}
}
```

### 5.3 plugins Collection

```json
{
  "_id": "ObjectId",
  "job_id": "job_run_abc12345_0",
  "plugin_name": "string",
  "stage": "string",
  "data": {},
  "status": {
    "success": true,
    "duration_ms": 0
  },
  "created_at": "ISODate"
}
```

---

## 6. FASTAPI SCHEMAS

### 6.1 RunResponse

```json
{
  "id": "run_abc12345",
  "status": {
    "state": "pending | running | success | failed | partial | cancelled",
    "success": true,
    "total_jobs": 0,
    "completed": 0,
    "failed": 0,
    "duration_ms": 0,
    "error": null
  },
  "input": {
    "value": "",
    "data": {}
  },
  "output": {
    "values": [],
    "data": {}
  },
  "jobs": ["job_id"],
  "config": {},
  "options": {},
  "created_at": "datetime",
  "completed_at": "datetime"
}
```

### 6.2 RunListResponse

```json
{
  "items": [RunResponse],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

### 6.3 RunCreate

```json
{
  "config": {},
  "dry_run": true
}
```

---

## 7. PLUGIN SDK

### 7.1 PluginResult

```json
{
  "success": true,
  "data": {},
  "error": null,
  "started_at": "datetime",
  "finished_at": "datetime",
  "metadata": {
    "skipped": false,
    "skip_reason": ""
  }
}
```

### 7.2 ExecutionContext

```json
{
  "execution_id": "string",
  "match_index": 0,
  "total_matches": 0,
  "config": {},
  "dry_run": true,
  "debug": false,
  "api_response": {},
  "previous_results": {}
}
```

### 7.3 PluginServices

```
services.state      → StateService
services.events     → EventService
services.logger     → LoggerService
services.config     → ConfigService
services.template   → TemplateService
services.provides   → ProvidesService
```

---

## 8. TEMPLATE CONTEXT (Jinja2)

### 8.1 Global Context

```
{{ run }}                → RunState
{{ run.id }}             → string
{{ run.status }}         → RunStatus

{{ job }}                → JobState
{{ job.id }}             → string
{{ job.index }}          → integer
{{ job.input.value }}    → string

{{ config }}             → dict
{{ config.options }}     → dict
{{ config.<plugin> }}    → dict

{{ index }}              → integer (current job index)
```

### 8.2 Plugin Context

```
{{ plugin.<name>.data }}         → Plugin output data
{{ plugin.<name>.status }}       → Plugin status

{{ plugin.renamer.parsed }}      → Parsed filename data
{{ plugin.tmdb.data.movie }}     → TMDb movie data
{{ plugin.tmdb.data.show }}      → TMDb show data
{{ plugin.tmdb.data.episode }}   → TMDb episode data
{{ plugin.ffprobe.data }}        → FFProbe data
```

### 8.3 Aliases (Shortcuts)

```
{{ movie }}         → {{ plugin.renamer.parsed.movie }}
{{ show }}          → {{ plugin.renamer.parsed.show }}
{{ tmdb_movie }}    → {{ plugin.tmdb.data.movie }}
{{ tmdb_show }}     → {{ plugin.tmdb.data.show }}
```

### 8.4 Template Functions

```
{{ count:<path> }}              → Array length
{{ index:<path>:<index> }}      → Array item at index
{{ value | default('N/A') }}    → Default value
{{ value | truncate(100) }}     → Truncate string
```

---

## 9. PLUGIN DATA STRUCTURES

### 9.1 Scanner Output

```json
{
  "path": "/path/to/file.mkv",
  "virtual": false,
  "size": 1073741824,
  "extension": "mkv"
}
```

### 9.2 Renamer Output

```json
{
  "parsed": {
    "movie": {
      "name": "Movie Title",
      "year": 2024,
      "resolution": "1080p",
      "source": "BluRay",
      "codec": "x264"
    },
    "show": {
      "name": "Show Title",
      "season": 1,
      "episode": 1,
      "title": "Episode Title",
      "resolution": "720p"
    }
  },
  "category": "movie | show",
  "confidence": 0.95
}
```

### 9.3 TMDb Movie Output

```json
{
  "movie": {
    "media_type": "movie",
    "identifiers": {
      "tmdb_id": "string",
      "imdb_id": "string"
    },
    "title": {
      "primary": "string",
      "original": "string",
      "localized": "string"
    },
    "release": {
      "date": "YYYY-MM-DD",
      "year": 2024,
      "status": "Released"
    },
    "runtime": 120,
    "ratings": {
      "tmdb": {
        "score": 8.5,
        "votes": 10000
      }
    },
    "overview": "string",
    "genres": ["Action", "Drama"],
    "financial": {
      "budget": 100000000,
      "revenue": 500000000
    },
    "images": {
      "poster": "/path.jpg",
      "backdrop": "/path.jpg",
      "posters": [],
      "backdrops": []
    },
    "people": {
      "cast": [
        {
          "name": "string",
          "character": "string",
          "profile_path": "string",
          "order": 0
        }
      ],
      "crew": [
        {
          "name": "string",
          "job": "Director",
          "department": "Directing"
        }
      ]
    },
    "videos": [
      {
        "name": "string",
        "key": "string",
        "site": "YouTube",
        "type": "Trailer"
      }
    ],
    "keywords": ["string"]
  }
}
```

### 9.4 TMDb Show Output

```json
{
  "show": {
    "media_type": "show",
    "identifiers": {
      "tmdb_id": "string"
    },
    "title": {
      "primary": "string",
      "original": "string",
      "localized": "string"
    },
    "air_dates": {
      "first": "YYYY-MM-DD",
      "last": "YYYY-MM-DD",
      "year": 2024
    },
    "status": "Returning Series | Ended",
    "runtime": 45,
    "ratings": {
      "tmdb": {
        "score": 8.5,
        "votes": 10000
      }
    },
    "overview": "string",
    "genres": ["Drama"],
    "network": {
      "name": "string",
      "id": "string"
    },
    "seasons": {
      "total": 5
    },
    "episodes": {
      "total": 50
    },
    "images": {
      "poster": "/path.jpg",
      "backdrop": "/path.jpg"
    },
    "people": {
      "cast": [],
      "crew": []
    }
  },
  "episode": {
    "media_type": "episode",
    "identifiers": {
      "tmdb_id": "string"
    },
    "title": {
      "primary": "string"
    },
    "season_number": 1,
    "episode_number": 1,
    "air_date": "YYYY-MM-DD",
    "runtime": 45,
    "overview": "string",
    "images": {
      "still": "/path.jpg"
    },
    "people": {
      "guest_stars": []
    }
  }
}
```

### 9.5 FFProbe Output

```json
{
  "format": {
    "filename": "string",
    "format_name": "matroska,webm",
    "format_long_name": "Matroska / WebM",
    "duration": "3600.000",
    "size": "1073741824",
    "bit_rate": "2500000"
  },
  "streams": [
    {
      "index": 0,
      "codec_type": "video | audio | subtitle",
      "codec_name": "h264",
      "width": 1920,
      "height": 1080,
      "duration": "3600.000"
    }
  ]
}
```

### 9.6 Tasker Output

```json
{
  "tasks_executed": 5,
  "tasks_skipped": 1,
  "output_files": ["/path/to/output.json"]
}
```

---

## 10. ID FORMATS

| Entity | Format | Örnek |
|--------|--------|-------|
| Run | run_{uuid8} | run_abc12345 |
| Job | job_{run_id}_{index} | job_run_abc12345_0 |
| Plugin | {plugin_name} | tmdb |

---

## 11. ENUMS

### 11.1 StateEnum

```
pending
running
success
failed
partial
cancelled
```

### 11.2 Stage

```
input
parse
data
output
```

### 11.3 PluginStatus

```
pending
running
completed
failed
skipped
```

### 11.4 MediaCategory

```
movie
show
episode
season
```

### 11.5 PluginCategory

```
input
output
```

---

## 12. CONFIG SCHEMA (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "aliases": {
      "type": "object",
      "additionalProperties": {"type": "string"}
    },
    "options": {
      "type": "object",
      "properties": {
        "debug": {"type": "boolean", "default": false},
        "dry_run": {"type": "boolean", "default": true},
        "hardlink": {"type": "boolean", "default": false}
      }
    },
    "plugins": {
      "type": "object",
      "patternProperties": {
        "^[a-z0-9-]+$": {
          "type": "object",
          "properties": {
            "enabled": {"type": "boolean"}
          },
          "required": ["enabled"]
        }
      }
    },
    "tasks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["print", "save", "external"]},
          "template": {"type": "string"},
          "destination": {"type": "string"},
          "condition": {"type": "string"}
        },
        "required": ["name"]
      }
    }
  },
  "required": ["options"]
}
```

---

## 13. SERVICE PROTOCOLS

### 13.1 StateService

```python
def get_current_job() -> JobState
def get_job(job_id: str) -> JobState | None
def get_job_by_index(index: int) -> JobState | None
def get_all_jobs() -> list[JobState]
def get_run() -> RunState
def get_plugin_data(job_id: str, plugin_name: str) -> dict
def save_plugin_data(job_id: str, plugin_name: str, stage: str, data: dict, status: dict) -> None
```

### 13.2 EventService

```python
def emit(event: str, data: dict | None) -> None
def subscribe(event: str, handler: Callable) -> None
```

### 13.3 LoggerService

```python
def debug(message: str, **kwargs) -> None
def info(message: str, **kwargs) -> None
def warn(message: str, **kwargs) -> None
def error(message: str, **kwargs) -> None
```

### 13.4 ConfigService

```python
def get(key: str, default: Any) -> Any
def get_plugin(plugin_name: str) -> dict
def get_option(option: str, default: Any) -> Any
```

### 13.5 TemplateService

```python
def render(template: str, context: dict) -> str
def build_context(job_id: str) -> dict
```

### 13.6 ProvidesService

```python
def complete(provide: str) -> None
def is_completed(provide: str) -> bool
def get_status(provide: str) -> dict
```

---

*Bu belge Archiverr sistemindeki tüm veri yapılarının kesinlik referansıdır.*
