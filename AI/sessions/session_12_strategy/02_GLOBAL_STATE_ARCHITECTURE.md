# GLOBAL STATE ARCHITECTURE

```yaml
tarih: 2024-12-08
durum: strategy
session: 12
konu: 6 global state object design and access control
```

---

## OVERVIEW

Session 12'de global state **6 objeye** ayrılıyor:

```
run      - Run metadata and statistics
config   - Frozen configuration (merged)
job      - Current job being processed
jobs     - All jobs in this run
plugin   - Current job's all plugin data
plugins  - All jobs' all plugin data
```

Bu yapı **job ve plugins arasında tutarlı bir ilişki** sağlar:
- `job` = current job, `jobs` = all jobs
- `plugin` = current job's plugins, `plugins` = all jobs' plugins

---

## STATE ACCESS MATRIX

### Per-run Plugins

```
ERIŞIM:
  ✅ run      (read-only)
  ✅ config   (read-only)

ERIŞEMEZ:
  ❌ job      (henüz hiç job yok)
  ❌ jobs     (henüz oluşturulmadı)
  ❌ plugin   (plugin data yok)
  ❌ plugins  (plugin data yok)
```

**SEBEP**: Per-run pluginler job oluşturmadan ÖNCE çalışır.

### Per-job Plugins

```
ERIŞIM:
  ✅ run      (read-only)
  ✅ config   (read-only)
  ✅ job      (read-write, current job)
  ✅ jobs     (read-only, all jobs)
  ✅ plugin   (read-write, current job plugins)
  ✅ plugins  (read-only, all jobs plugins)
```

**SEBEP**: Per-job pluginler job içinde çalışır, tüm state'e erişim gerekir.

---

## 1. RUN STATE

### Structure

```yaml
run:
  id: run_abc123
  status:
    state: running | completed | failed
    success: true | false
    total_jobs: 10
    completed: 8
    failed: 1
    skipped: 1
    started_at: "2024-01-15T12:00:00Z"
    finished_at: null | "2024-01-15T12:05:00Z"
    duration_ms: 300000
  config:  # Config snapshot (bkz. CONFIG STATE)
    options:
      debug: true
    aliases: {}
```

### Access Rules

```
SCOPE: Entire run
READ: All plugins (per_run, per_job)
WRITE: Only orchestrator

AVAILABLE IN:
  - Jinja2 templates: {{ run.total_jobs }}
  - Trigger rules: run.total_jobs:10
  - Plugin code: services.state.get_run()
```

### Common Paths

```yaml
run.id                    # Run ID
run.status.state          # running | completed | failed
run.status.total_jobs     # Total job count
run.status.completed      # Completed job count
run.status.failed         # Failed job count
run.status.started_at     # ISO timestamp
run.status.duration_ms    # Duration in milliseconds
```

### MongoDB Storage

```javascript
// Collection: runs
{
  _id: ObjectId("..."),
  id: "run_abc123",
  status: {
    state: "completed",
    success: true,
    total_jobs: 10,
    completed: 10,
    failed: 0,
    started_at: ISODate("2024-01-15T12:00:00Z"),
    finished_at: ISODate("2024-01-15T12:05:00Z"),
    duration_ms: 300000
  },
  config: { /* frozen config snapshot */ },
  created_at: ISODate("2024-01-15T12:00:00Z"),
  updated_at: ISODate("2024-01-15T12:05:00Z")
}
```

---

## 2. CONFIG STATE

### Structure

```yaml
config:
  options:
    debug: true
    dry_run: false
    force_conflicts: false
  
  aliases:
    m: plugin.tmdb.data.movie
    s: plugin.tmdb.data.show
    p: plugin.renamer.data.parsed
  
  scanner:
    targets: [/downloads/movies]
    recursive: true
    extensions: [mkv, mp4]
  
  tmdb:
    api_key: ${TMDB_API_KEY}
    language: tr-TR
  
  tasker:
    archive_path: /srv/archive
    tasks: [...]
```

### Merge Process

```
1. Load manifest.yml (plugin defaults)
2. Load config.yml (user overrides)
3. Deep merge: config.yml WINS
4. Freeze config (immutable after startup)
5. Add to global state as "config"
```

### Access Rules

```
SCOPE: Frozen at startup
READ: All plugins (per_run, per_job)
WRITE: Never (immutable)

AVAILABLE IN:
  - Jinja2 templates: {{ config.tmdb.api_key }}
  - Trigger rules: config.options.debug:true
  - Plugin code: services.config.get("tmdb.api_key")
  - FS locks: {{config.archive_path}}
```

### Common Paths

```yaml
config.options.debug           # Debug mode flag
config.options.dry_run         # Dry run flag
config.{plugin}.{option}       # Plugin-specific config
config.aliases.{name}          # User-defined aliases
```

### Why Immutable?

```
SEBEP 1: Predictability
  - Plugin execution sırasında config değişmez
  - Trigger rules güvenilir

SEBEP 2: FS Lock Validation
  - Startup'ta conflict detection
  - Config values bilinir

SEBEP 3: Reproducibility
  - Aynı config = aynı sonuç
  - Debug kolaylığı
```

---

## 3. JOB STATE (Current Job)

### Structure

```yaml
job:
  index: 0
  id: job_run_abc123_0
  run_id: run_abc123
  
  input:
    value: /data/movies/Movie.2024.mkv
    data:
      filename: Movie.2024.mkv
      size_bytes: 5368709120
      extension: mkv
  
  output:
    values:
      - /srv/archive/Movie (2024)/Movie.mkv
      - /srv/archive/Movie (2024)/Movie.nfo
    data:
      tasks:
        save_movie:
          type: save
          output: /srv/archive/Movie (2024)/Movie.mkv
  
  status:
    state: pending | running | completed | failed
    success: true | false
    executed: [scanner, renamer, tmdb]
    failed: []
    skipped: [tvdb]
    started_at: "2024-01-15T12:00:01Z"
    finished_at: null
    duration_ms: 0
```

### Access Rules

```
SCOPE: Current job being processed
READ: per_job plugins only
WRITE: per_job plugins only (via updateJob)

DENIED:
  - per_run plugins (no current job context)

AVAILABLE IN:
  - Jinja2 templates: {{ job.input.value }}
  - Trigger rules: job.input.value
  - Plugin code: services.state.get_current_job()
```

### Input vs Output

```
INPUT:
  - value: Job input (path, query, etc.)
  - data: Input plugin data (scanner metadata)
  
OUTPUT:
  - values: Array of output paths/results
  - data: Output plugin data (tasker results)

RULE:
  - input.data = plugin.{input_plugin}
  - output.data = plugin.{output_plugin}
```

### Common Paths

```yaml
job.id                      # Job ID
job.index                   # Job index in run
job.input.value             # Input path/query
job.input.data.*            # Input plugin metadata
job.output.values[]         # Output paths array
job.output.data.*           # Output plugin data
job.status.state            # Job state
job.status.success          # Success flag
job.status.executed[]       # Executed plugins
```

### MongoDB Storage

```javascript
// Collection: jobs
{
  _id: ObjectId("..."),
  run_id: "run_abc123",
  index: 0,
  id: "job_run_abc123_0",
  input: {
    value: "/data/movies/Movie.2024.mkv",
    data: { /* scanner metadata */ }
  },
  output: {
    values: ["/srv/archive/Movie.mkv"],
    data: { /* tasker results */ }
  },
  status: {
    state: "completed",
    success: true,
    executed: ["scanner", "renamer", "tmdb", "tasker"],
    failed: [],
    skipped: ["tvdb"]
  },
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

---

## 4. JOBS STATE (All Jobs)

### Structure

```yaml
jobs:
  - index: 0
    id: job_run_abc123_0
    run_id: run_abc123
    input: { ... }
    output: { ... }
    status: { ... }
  
  - index: 1
    id: job_run_abc123_1
    run_id: run_abc123
    input: { ... }
    output: { ... }
    status: { ... }
```

### Access Rules

```
SCOPE: All jobs in this run
READ: per_job plugins only (read-only)
WRITE: Never (use updateJob for current job)

DENIED:
  - per_run plugins (jobs not created yet)

AVAILABLE IN:
  - Jinja2 templates: {{ jobs[0].input.value }}
  - Trigger rules: jobs[0].status.success:true
  - Plugin code: services.state.get_all_jobs()
```

### Use Cases

```yaml
# Template: Show all processed files
{% for j in jobs %}
  - {{ j.input.value }} → {{ j.status.state }}
{% endfor %}

# Trigger: Wait for 10 jobs
requires:
  - run.total_jobs:10

# Plugin: Access other jobs
def execute(self, job, services):
    all_jobs = services.state.get_all_jobs()
    for other_job in all_jobs:
        if other_job.id != job.id:
            # Process other job data
            pass
```

### Common Paths

```yaml
jobs[0].id                  # First job ID
jobs[0].input.value         # First job input
jobs[0].status.state        # First job state
jobs[].input.value          # All job inputs (list)
```

---

## 5. PLUGIN STATE (Current Job Plugins)

### Structure

```yaml
plugin:
  job_id: job_run_abc123_0
  run_id: run_abc123
  
  scanner:
    status:
      state: completed
      success: true
      started_at: "2024-01-15T12:00:02Z"
      finished_at: "2024-01-15T12:00:03Z"
      duration_ms: 800
      error: null
    data:              # 🔴 HER ŞEY data içinde
      filename: Movie.2024.mkv
      extension: mkv
      size_bytes: 5368709120
  
  renamer:
    status:
      state: completed
      success: true
      started_at: "2024-01-15T12:00:04Z"
      finished_at: "2024-01-15T12:00:05Z"
      duration_ms: 200
      error: null
    data:
      movie:
        name: Movie Name
        year: 2024
        quality: 1080p
  
  tmdb:
    status:
      state: completed
      success: true
      started_at: "2024-01-15T12:00:06Z"
      finished_at: "2024-01-15T12:00:07Z"
      duration_ms: 800
      error: null
    data:
      movie:
        id: 12345
        title: Movie
        release_date: 2024-01-15
        genres: [Action, Drama]
```

### Access Rules

```
SCOPE: Current job's all plugin data
READ: per_job plugins
WRITE: per_job plugins (via updatePlugin)

DENIED:
  - per_run plugins (no plugin data yet)

AVAILABLE IN:
  - Jinja2 templates: {{ plugin.tmdb.data.movie.title }}
  - Trigger rules: plugin.tmdb.data.movie:success
  - Plugin code: services.state.get_plugin_data("tmdb", "data.movie")
  - Aliases: m: plugin.tmdb.data.movie
```

### Data Structure

```
plugin.{plugin_name}:
  status:
    state: pending | running | completed | failed
    success: bool
    started_at: timestamp
    finished_at: timestamp
    duration_ms: int
    error: null | string
  
  data:              # 🔴 HER ŞEY data içinde
    # Plugin'in kendi datasını buraya ekler
    # Örnek: movie, parsed, video, tasks, etc.
```

### Update Pattern

```python
# Plugin kendi datasını ekler
services.state.update_plugin(
    plugin_name="tmdb",
    data={
        "movie": {
            "id": 12345,
            "title": "Movie Name",
            "release_date": "2024-01-15"
        }
    }
)

# Sonuç:
# plugin.tmdb.data.movie.title = "Movie Name"
# plugin.tmdb.data.movie.id = 12345
```

### Common Paths

```yaml
plugin.{name}.status.state           # Plugin execution state
plugin.{name}.status.success         # Success flag
plugin.renamer.data.parsed.movie     # Parsed movie data
plugin.tmdb.data.movie.title         # TMDb movie title
plugin.ffprobe.data.video.codec      # FFprobe video codec
plugin.tasker.data.tasks.*           # Task results
```

### MongoDB Storage

```javascript
// Collection: plugins
{
  _id: ObjectId("..."),
  run_id: "run_abc123",
  job_id: "job_run_abc123_0",
  job_index: 0,
  
  // Her plugin bir key olarak
  scanner: {
    status: { state: "completed", success: true },
    filename: "Movie.2024.mkv",
    size_bytes: 5368709120
  },
  renamer: {
    status: { state: "completed", success: true },
    parsed: { movie: { name: "Movie Name", year: 2024 } }
  },
  tmdb: {
    status: { state: "completed", success: true },
    movie: { id: 12345, title: "Movie" }
  },
  
  created_at: ISODate("...")
}
```

---

## 6. PLUGINS STATE (All Jobs Plugins)

### Structure

```yaml
plugins:
  - job_id: job_run_abc123_0
    job_index: 0
    run_id: run_abc123
    scanner: { ... }
    renamer: { ... }
    tmdb: { ... }
  
  - job_id: job_run_abc123_1
    job_index: 1
    run_id: run_abc123
    scanner: { ... }
    renamer: { ... }
    tmdb: { ... }
```

### Access Rules

```
SCOPE: All jobs' all plugin data
READ: per_job plugins only (read-only)
WRITE: Never (use updatePlugin for current job)

DENIED:
  - per_run plugins (no plugin data yet)

AVAILABLE IN:
  - Jinja2 templates: {{ plugins[0].tmdb.movie.title }}
  - Trigger rules: plugins[0].renamer.parsed:success
  - Plugin code: services.state.get_all_plugins()
```

### Use Cases

```yaml
# Template: List all processed movies
{% for p in plugins %}
  {% if p.tmdb.movie %}
    - {{ p.tmdb.movie.title }} ({{ p.tmdb.movie.release_date[:4] }})
  {% endif %}
{% endfor %}

# Plugin: Compare with other jobs
def execute(self, job, services):
    all_plugins = services.state.get_all_plugins()
    
    for other in all_plugins:
        if other.job_id != job.id:
            # Compare with other job's plugin data
            if other.tmdb.movie.title == current_title:
                # Duplicate found
                pass
```

### Common Paths

```yaml
plugins[0].tmdb.movie.title      # First job's TMDb title
plugins[0].renamer.parsed        # First job's parsed data
plugins[].tmdb.movie.id          # All TMDb IDs (list)
```

---

## STATE LIFECYCLE

### Startup

```python
# 1. Config merge ve freeze
config = merge_config(manifest, user_config)
global_state.set("config", config)

# 2. Run başlat
run = create_run(config)
global_state.set("run", run)

# 3. Per-run pluginler çalışır
for plugin in per_run_plugins:
    # Sadece run ve config erişebilir
    plugin.execute_run(services)
```

### Job Creation

```python
# Per-run plugin: Scanner
job_id = services.create_job(
    input_value="/path/to/movie.mkv",
    input_data={"size_bytes": 5368709120}
)

# Job created but pending (input.value not set yet)
services.update_job(job_id, "input.value", "/path/to/movie.mkv")

# Now job is created, added to queue
```

### Job Execution

```python
# For each job in queue
for job in job_queue:
    # Set current job
    global_state.set("job", job)
    global_state.set("plugin", {})  # Current job plugins
    
    # Parse stage
    for plugin in parse_plugins:
        result = plugin.execute(job, services)
        services.update_plugin(plugin.name, result.data)
    
    # Data stage
    for plugin in data_plugins:
        result = plugin.execute(job, services)
        services.update_plugin(plugin.name, result.data)
    
    # Output stage
    for plugin in output_plugins:
        result = plugin.execute(job, services)
        services.update_plugin(plugin.name, result.data)
    
    # Add to jobs and plugins arrays
    global_state.append("jobs", job)
    global_state.append("plugins", current_plugin_data)
```

### Finalization

```python
# Update run status
run.status.state = "completed"
run.status.finished_at = now()
run.status.duration_ms = calculate_duration()

# Persist to MongoDB
persistence.save_run(run)
persistence.save_jobs(jobs)
persistence.save_plugins(plugins)
```

---

## STATE MANAGER INTERFACE

### Core Methods

```python
class StateManager:
    """Global state manager for run, config, jobs, plugins"""
    
    # Run state
    def start_run(self, config: Dict) -> str:
        """Start new run, return run_id"""
    
    def get_run(self) -> RunState:
        """Get current run state"""
    
    def complete_run(self) -> None:
        """Mark run as completed"""
    
    # Config state
    def set_config(self, config: Dict) -> None:
        """Set frozen config (startup only)"""
    
    def get_config(self) -> Dict:
        """Get frozen config"""
    
    # Job state
    def create_job(self, input_value: str, input_data: Dict) -> str:
        """Create new job, return job_id"""
    
    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """Update job field"""
    
    def get_current_job(self) -> JobState:
        """Get current job being processed"""
    
    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs in this run"""
    
    # Plugin state
    def update_plugin(self, plugin_name: str, data: Dict) -> None:
        """Update current job's plugin data"""
    
    def get_current_plugins(self) -> Dict:
        """Get current job's all plugin data"""
    
    def get_all_plugins(self) -> List[Dict]:
        """Get all jobs' all plugin data"""
```

### Service Facade (Plugin Interface)

```python
class PluginServices:
    """Unified interface for plugins to access state"""
    
    def __init__(self, state: StateManager, ...):
        self.state = state
        self._mode = mode  # per_run or per_job
    
    def create_job(self, input_value: str, input_data: Dict) -> str:
        """Create new job (both per_run and per_job)"""
        return self.state.create_job(input_value, input_data)
    
    def update_job(self, job_id: str, key: str, value: Any) -> None:
        """Update job (per_job only)"""
        if self._mode != "per_job":
            raise AccessDenied("per_run plugins cannot update jobs")
        self.state.update_job(job_id, key, value)
    
    def update_plugin(self, plugin_name: str, data: Dict) -> None:
        """Update plugin data (per_job only)"""
        if self._mode != "per_job":
            raise AccessDenied("per_run plugins cannot update plugin data")
        self.state.update_plugin(plugin_name, data)
    
    def get_run(self) -> RunState:
        """Get run state (all plugins)"""
        return self.state.get_run()
    
    def get_config(self, key: str = None, default: Any = None) -> Any:
        """Get config value (all plugins)"""
        config = self.state.get_config()
        if key:
            return config.get(key, default)
        return config
```

---

## ACCESS CONTROL ENFORCEMENT

### Template Rendering

```python
def render_template(template: str, context_type: str) -> str:
    """Render Jinja2 template with proper context"""
    
    if context_type == "per_run":
        context = {
            "run": state.get_run(),
            "config": state.get_config(),
            # job, jobs, plugin, plugins NOT AVAILABLE
        }
    
    elif context_type == "per_job":
        context = {
            "run": state.get_run(),
            "config": state.get_config(),
            "job": state.get_current_job(),
            "jobs": state.get_all_jobs(),
            "plugin": state.get_current_plugins(),
            "plugins": state.get_all_plugins(),
        }
    
    return jinja_env.from_string(template).render(**context)
```

### Trigger Rule Evaluation

```python
def evaluate_trigger_rule(requires: List[str], context_type: str) -> bool:
    """Evaluate trigger rule with access control"""
    
    for requirement in requires:
        path, value = parse_requirement(requirement)
        
        # Check access
        if context_type == "per_run":
            if path.startswith(("job.", "jobs.", "plugin.", "plugins.")):
                raise AccessDenied(f"per_run cannot access {path}")
        
        # Evaluate
        actual_value = state.get_value(path)
        if not match_value(actual_value, value):
            return False
    
    return True
```

---

## SUMMARY

### 6 Global States

| State | Scope | Access | Mutable |
|-------|-------|--------|---------|
| run | Entire run | All (RO) | Orchestrator only |
| config | Frozen config | All (RO) | Never |
| job | Current job | per_job (RW) | per_job plugins |
| jobs | All jobs | per_job (RO) | Never |
| plugin | Current job plugins | per_job (RW) | per_job plugins |
| plugins | All jobs plugins | per_job (RO) | Never |

### Access Matrix

| Plugin | run | config | job | jobs | plugin | plugins |
|--------|-----|--------|-----|------|--------|---------|
| per_run | ✅ RO | ✅ RO | ❌ | ❌ | ❌ | ❌ |
| per_job | ✅ RO | ✅ RO | ✅ RW | ✅ RO | ✅ RW | ✅ RO |

### Update Methods

| Method | per_run | per_job | Target |
|--------|---------|---------|--------|
| createJob | ✅ | ✅ | Create job |
| updateJob | ❌ | ✅ | Update current job |
| updatePlugin | ❌ | ✅ | Update current plugin data |

---

**Next Document**: 03_PLUGIN_SYSTEM_REFACTORING.md
