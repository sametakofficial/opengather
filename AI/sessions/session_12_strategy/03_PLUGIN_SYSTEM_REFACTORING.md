# PLUGIN SYSTEM REFACTORING

```yaml
tarih: 2024-12-08
durum: strategy
session: 12
konu: Plugin communication methods and execution patterns
```

---

## OVERVIEW

Session 12'de plugin sistemi **3 temel method** üzerine kurulu:

```python
createJob(input_value, input_data) -> job_id
updateJob(key, value)              # 🔴 ID yok, current context
updatePlugin(data)                 # 🔴 Name yok, current context
```

**⚠️ ÖNEMLİ**: Update methods ID/name almaz. Current job/plugin context internal'da tutuluyor.

Bu methodlar **job queue paradigması** ile uyumlu çalışır:
- Per-run: Job oluşturur (createJob)
- Per-job: Job ve plugin datasını günceller (updateJob, updatePlugin)

---

## PLUGIN COMMUNICATION METHODS

### 1. createJob()

```python
def createJob(
    input_value: str,
    input_data: Dict[str, Any]
) -> str:
    """
    Create a new job and return job_id
    
    Args:
        input_value: Job input (path, query, etc.)
        input_data: Input plugin metadata
    
    Returns:
        job_id: Created job ID
    
    Access:
        - per_run: ✅ (primary use case)
        - per_job: ✅ (rare, e.g., failed job retry)
    """
```

#### Usage Pattern

```python
# Scanner plugin (per_run)
class ScannerPlugin(BasePlugin):
    def execute_run(self, services: PluginServices):
        files = self.scan_directory(config.scanner.targets)
        
        for file_path in files:
            # Create job
            job_id = services.create_job(
                input_value=file_path,
                input_data={
                    "filename": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "extension": file_path.suffix,
                    "modified_at": file_path.stat().st_mtime
                }
            )
            
            # Job created and queued automatically
            services.logger.info(f"Job created: {job_id}")
```

#### Job Creation Flow

```
1. Scanner: createJob(path, metadata)
   ↓
2. State Manager: Create job object
   - id = generate_job_id()
   - input.value = path
   - input.data = metadata
   - status.state = "pending"
   ↓
3. Job Queue: Add job to queue
   ↓
4. Return job_id to plugin
   ↓
5. Job execution başlar (parse → data → output)
```

### 2. updateJob()

```python
def updateJob(
    key: str,
    value: Any
) -> None:
    """
    Update CURRENT job state
    
    Args:
        key: Dot-notation path (e.g., "output.values")
        value: New value
    
    Access:
        - per_run: ❌ (no job context)
        - per_job: ✅ (updates current job)
    
    Notes:
        - Current job context is held internally by PluginServices
        - No job_id needed - always updates the job being processed
    
    Raises:
        AccessDenied: If called from per_run plugin
    """
```

#### Usage Pattern

```python
# Tasker plugin (output stage, per_job)
class TaskerPlugin(BasePlugin):
    def execute(self, job: JobState, services: PluginServices):
        # Execute tasks
        results = self.execute_tasks(job, services)
        
        # Update job output (🔴 ID yok)
        services.updateJob(
            key="output.values",
            value=["/srv/archive/Movie.mkv"]
        )
        
        services.updateJob(
            key="output.data.tasks",
            value=results
        )
```

#### Update Keys

```yaml
# Allowed keys
"input.value"           # Job input path
"input.data"            # Input metadata
"output.values"         # Output paths (array)
"output.data"           # Output plugin data
"status.state"          # Job state (orchestrator only)
"status.executed"       # Executed plugins (orchestrator only)
```

### 3. updatePlugin()

```python
def updatePlugin(
    data: Dict[str, Any]
) -> None:
    """
    Update CURRENT plugin's data
    
    Args:
        data: Plugin-specific data to store in plugin.{name}.data
    
    Access:
        - per_run: ❌ (no plugin context)
        - per_job: ✅ (updates current plugin data)
    
    Notes:
        - Current plugin name is held internally by PluginServices
        - Data is stored in: plugin.{current_plugin_name}.data
        - No plugin_name needed - always updates the executing plugin
    
    Raises:
        AccessDenied: If called from per_run plugin
    """
```

#### Usage Pattern

```python
# TMDb plugin (data stage, per_job)
class TMDbPlugin(BasePlugin):
    def execute(self, job: JobState, services: PluginServices):
        # Get parsed data (🔴 plugin.{name}.data.* yapısı)
        parsed = job.plugins.get("renamer", {}).get("data", {}).get("parsed", {})
        
        # Fetch metadata
        movie = self.fetch_movie(parsed.get("movie", {}).get("name"))
        
        # Update plugin data (🔴 plugin_name yok)
        services.updatePlugin(
            data={
                "movie": {
                    "id": movie.id,
                    "title": movie.title,
                    "release_date": movie.release_date,
                    "genres": movie.genres,
                    "runtime": movie.runtime
                }
            }
        )
        
        # Now accessible as: plugin.tmdb.data.movie.title
```

#### Data Structure

```yaml
# After updatePlugin(data) → stored in plugin.tmdb.data
plugin:
  tmdb:
    status:  # Auto-added by system
      state: completed
      success: true
      duration_ms: 800
    data:    # Plugin data (HER ŞEY data içinde)
      movie:
        id: 12345
        title: Movie Name
        release_date: 2024-01-15
        genres: [Action, Drama]
```

---

## PLUGIN EXECUTION PATTERNS

### Pattern 1: Per-run Input Plugin

```python
class ScannerPlugin(BasePlugin):
    """
    Input plugin: Creates jobs
    Mode: per_run
    Stage: None
    """
    
    def execute_run(self, services: PluginServices):
        # Access: run, config (read-only)
        targets = services.config.get("scanner.targets", [])
        
        # Scan directories
        files = self.scan_directories(targets)
        
        # Create jobs
        for file_path in files:
            job_id = services.create_job(
                input_value=str(file_path),
                input_data={
                    "filename": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "extension": file_path.suffix[1:],  # Remove dot
                    "source": "filesystem"
                }
            )
            
            services.logger.debug(f"Created job {job_id}")
        
        return PluginResult.success({
            "scanned_count": len(files)
        })
```

### Pattern 2: Parse Stage Plugin

```python
class RenamerPlugin(BasePlugin):
    """
    Parse plugin: Extracts metadata from filename
    Mode: per_job
    Stage: parse
    """
    
    def execute(self, job: JobState, services: PluginServices):
        # Access: run, config, job, jobs, plugin, plugins
        filename = job.input.data.get("filename", "")
        
        # Parse filename
        parsed = self.parse_filename(filename)
        
        # Update plugin data
        services.update_plugin(
            plugin_name="renamer",
            data={
                "parsed": parsed  # {movie: {...}, show: null}
            }
        )
        
        return PluginResult.success({"parsed": parsed})
```

### Pattern 3: Data Stage Plugin

```python
class TMDbPlugin(BasePlugin):
    """
    Data plugin: Fetches external metadata
    Mode: per_job
    Stage: data
    """
    
    def execute(self, job: JobState, services: PluginServices):
        # Get parsed data from renamer
        parsed = job.plugins.get("renamer", {}).get("parsed", {})
        
        if not parsed.get("movie"):
            return PluginResult.skipped("No movie data to fetch")
        
        # Fetch from TMDb API
        movie = self.fetch_movie(
            title=parsed["movie"]["name"],
            year=parsed["movie"].get("year")
        )
        
        # Update plugin data
        services.update_plugin(
            plugin_name="tmdb",
            data={"movie": movie}
        )
        
        return PluginResult.success({"movie": movie})
```

### Pattern 4: Output Stage Plugin

```python
class TaskerPlugin(BasePlugin):
    """
    Output plugin: Executes tasks and saves results
    Mode: per_job
    Stage: output
    """
    
    def execute(self, job: JobState, services: PluginServices):
        # Render task templates
        tasks = self.render_tasks(job, services)
        
        # Execute tasks
        results = {}
        output_paths = []
        
        for task in tasks:
            if task["type"] == "save":
                path = self.save_file(task, job, services)
                output_paths.append(path)
                results[task["name"]] = {
                    "type": "save",
                    "success": True,
                    "destination": path
                }
            elif task["type"] == "print":
                rendered = self.render_template(task["template"], job)
                print(rendered)
                results[task["name"]] = {
                    "type": "print",
                    "success": True,
                    "rendered": rendered
                }
        
        # Update job output
        services.update_job(job.id, "output.values", output_paths)
        services.update_job(job.id, "output.data.tasks", results)
        
        # Update plugin data
        services.update_plugin(
            plugin_name="tasker",
            data={"tasks": results}
        )
        
        return PluginResult.success({"tasks": results})
```

---

## PLUGIN BASE CLASS

### BasePlugin Interface

```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass
class PluginResult:
    """Plugin execution result"""
    status: str  # "success", "failed", "skipped"
    data: Optional[Dict] = None
    error: Optional[str] = None
    
    @classmethod
    def success(cls, data: Dict) -> 'PluginResult':
        return cls(status="success", data=data)
    
    @classmethod
    def failed(cls, error: str) -> 'PluginResult':
        return cls(status="failed", error=error)
    
    @classmethod
    def skipped(cls, reason: str = "") -> 'PluginResult':
        return cls(status="skipped", error=reason)


class BasePlugin(ABC):
    """
    Base class for all plugins
    
    Subclasses must implement ONE of:
    - execute_run() for per_run plugins
    - execute() for per_job plugins
    """
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
    
    def execute_run(self, services: PluginServices) -> PluginResult:
        """
        Execute once per run (per_run plugins)
        
        Override this for input plugins that create jobs
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute_run()"
        )
    
    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        """
        Execute for each job (per_job plugins)
        
        Override this for parse/data/output plugins
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute()"
        )
```

---

## PLUGIN SERVICES INTERFACE

```python
class PluginServices:
    """
    Unified interface for plugins to interact with the system
    
    Access control is enforced based on plugin mode (per_run vs per_job)
    """
    
    def __init__(
        self,
        state: StateManager,
        event_bus: EventBus,
        logger: Logger,
        config: ConfigManager,
        mode: str  # "per_run" or "per_job"
    ):
        self._state = state
        self._event_bus = event_bus
        self._logger = logger
        self._config = config
        self._mode = mode
    
    # Job Management
    def createJob(self, input_value: str, input_data: Dict) -> str:
        """Create new job (both per_run and per_job)"""
        return self._state.create_job(input_value, input_data)
    
    def updateJob(self, key: str, value: Any) -> None:
        """Update CURRENT job (per_job only) - ID yok!"""
        self._check_access("per_job", "updateJob")
        # Current job_id is held internally
        self._state.update_job(self._current_job_id, key, value)
    
    def updatePlugin(self, data: Dict) -> None:
        """Update CURRENT plugin data (per_job only) - Name yok!"""
        self._check_access("per_job", "updatePlugin")
        # Current plugin name is held internally
        # Data stored in: plugin.{self._current_plugin_name}.data
        self._state.update_plugin(self._current_plugin_name, data)
    
    # State Access
    def get_run(self) -> RunState:
        """Get run state (all plugins)"""
        return self._state.get_run()
    
    def get_current_job(self) -> JobState:
        """Get current job (per_job only)"""
        self._check_access("per_job", "get_current_job")
        return self._state.get_current_job()
    
    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs (per_job only)"""
        self._check_access("per_job", "get_all_jobs")
        return self._state.get_all_jobs()
    
    # Config Access
    def get_config(self, key: str = None, default: Any = None) -> Any:
        """Get config value (all plugins)"""
        if key:
            return self._config.get(key, default)
        return self._config.get_all()
    
    # Event Bus
    def emit(self, event: str, data: Dict = None) -> None:
        """Emit event (all plugins)"""
        self._event_bus.emit(event, data)
    
    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe to event (all plugins)"""
        self._event_bus.subscribe(event, handler)
    
    # Logging
    @property
    def logger(self) -> Logger:
        """Get logger (all plugins)"""
        return self._logger
    
    # Access Control
    def _check_access(self, required_mode: str, method: str):
        """Check if current plugin mode has access to method"""
        if self._mode != required_mode:
            raise AccessDenied(
                f"{method}() requires {required_mode} mode, "
                f"but plugin is {self._mode}"
            )
```

---

## MANIFEST SCHEMA

### Manifest Structure

```yaml
# plugins/{plugin_name}/manifest.yml

# Required fields (immutable)
name: string              # Plugin identifier
version: string           # Semantic version
run_mode: per_run | per_job
class_name: string        # Python class name

# Optional fields (immutable)
entry_point: string       # Default: client.py
description: string       # Plugin description

# Stage (required for per_job, null for per_run)
stage: null | parse | data | output

# Dependency and execution control (mutable)
requires: List[string]    # State paths with optional values
fs_lock: List[string]     # File system lock paths
trigger_rule: string      # all_success, one_success, etc.

# Configuration schema (optional)
config_schema: Dict       # JSON Schema for validation
```

### Manifest Examples

#### Per-run Plugin (Scanner)

```yaml
name: scanner
version: 1.0.0
description: File discovery and job creation
run_mode: per_run
stage: null
class_name: ScannerPlugin
entry_point: client.py

requires: []
fs_lock:
  - /downloads/movies
  - /downloads/shows

trigger_rule: all_success

config_schema:
  targets:
    type: array
    items:
      type: string
    required: true
  recursive:
    type: boolean
    default: true
  extensions:
    type: array
    items:
      type: string
    default: [mkv, mp4, avi]
```

#### Per-job Plugin (Parse Stage)

```yaml
name: renamer
version: 1.0.0
description: Filename parser
run_mode: per_job
stage: parse
class_name: RenamerPlugin

requires: []
fs_lock: []
trigger_rule: all_success

config_schema:
  media_type:
    type: string
    enum: [auto, movie, show]
    default: auto
```

#### Per-job Plugin (Data Stage)

```yaml
name: tmdb
version: 1.0.0
description: TMDb metadata provider
run_mode: per_job
stage: data
class_name: TMDbPlugin

requires:
  - plugin.renamer.data.parsed:success

fs_lock: []  # 🔴 Sadece static path, no variables
trigger_rule: all_success

config_schema:
  api_key:
    type: string
    required: true
  language:
    type: string
    default: en-US
  region:
    type: string
    default: US
```

#### Per-job Plugin (Output Stage)

```yaml
name: tasker
version: 1.0.0
description: Task execution and file operations
run_mode: per_job
stage: output
class_name: TaskerPlugin

requires:
  - plugin.tmdb.data:success
  - plugin.renamer.data:success

fs_lock:
  - /srv/archive  # 🔴 Static path only, no variables

trigger_rule: all_success

config_schema:
  archive_path:
    type: string
    required: true
  tasks:
    type: array
    items:
      type: object
    required: true
```

---

## PLUGIN LIFECYCLE

### Discovery and Loading

```python
# 1. Discovery
plugin_registry.discover_plugins("/path/to/plugins/")
# Scans directories, loads manifest.yml files

# 2. Validation
plugin_registry.validate_manifests()
# Check required fields, schema compliance

# 3. Loading
plugin_registry.load_plugins()
# Import Python classes, instantiate plugins

# 4. Configuration
plugin_registry.merge_config(user_config)
# Merge manifest defaults with user config
```

### Execution Flow

```python
# Per-run execution (before job queue)
for plugin in plugin_registry.get_per_run_plugins():
    services = PluginServices(state, events, logger, config, mode="per_run")
    
    result = plugin.execute_run(services)
    
    if result.status == "failed":
        logger.error(f"Plugin {plugin.name} failed: {result.error}")
        # Continue (best effort)

# Per-job execution (for each job in queue)
for job in job_queue:
    state.set_current_job(job)
    
    for stage in ["parse", "data", "output"]:
        stage_plugins = plugin_registry.get_plugins_by_stage(stage)
        
        # Check trigger rules
        ready_plugins = filter_by_trigger_rules(stage_plugins, job)
        
        # Execute plugins
        for plugin in ready_plugins:
            services = PluginServices(
                state, events, logger, config, 
                mode="per_job"
            )
            
            result = plugin.execute(job, services)
            
            # Update plugin status
            state.update_plugin_status(plugin.name, result)
            
            # Emit events
            events.emit("plugin.completed", {
                "job_id": job.id,
                "plugin_name": plugin.name,
                "status": result.status
            })
```

---

## ERROR HANDLING

### Plugin Failure

```python
def execute_plugin(plugin, job, services):
    """Execute plugin with error handling"""
    
    try:
        # Execute plugin
        result = plugin.execute(job, services)
        
        if result.status == "failed":
            # Mark plugin as failed
            job.status.failed.append(plugin.name)
            
            # Log error
            services.logger.error(
                f"Plugin {plugin.name} failed",
                error=result.error,
                job_id=job.id
            )
            
            # Emit event
            services.emit("plugin.failed", {
                "job_id": job.id,
                "plugin_name": plugin.name,
                "error": result.error
            })
            
            # Continue with next plugin (best effort)
        
        elif result.status == "skipped":
            # Mark as skipped
            job.status.skipped.append(plugin.name)
        
        elif result.status == "success":
            # Mark as executed
            job.status.executed.append(plugin.name)
        
        return result
        
    except Exception as e:
        # Unexpected error
        services.logger.error(
            f"Plugin {plugin.name} crashed",
            error=str(e),
            job_id=job.id
        )
        
        job.status.failed.append(plugin.name)
        
        return PluginResult.failed(str(e))
```

### Access Denied

```python
class AccessDenied(Exception):
    """Raised when plugin tries to access forbidden state"""
    pass

# Usage in PluginServices
def update_job(self, job_id, key, value):
    if self._mode == "per_run":
        raise AccessDenied(
            "per_run plugins cannot update jobs. "
            "Only per_job plugins have job write access."
        )
    self._state.update_job(job_id, key, value)
```

---

## SUMMARY

### Plugin Communication

| Method | Signature | per_run | per_job | Purpose |
|--------|-----------|---------|---------|---------|
| createJob | (input_value, input_data) -> job_id | ✅ | ✅ | Create new job |
| updateJob | (key, value) 🔴 ID yok | ❌ | ✅ | Update current job |
| updatePlugin | (data) 🔴 Name yok | ❌ | ✅ | Update current plugin data |

### Plugin Modes

| Mode | Stage | Signature | Use Case |
|------|-------|-----------|----------|
| per_run | null | execute_run(services) | Job creation |
| per_job | parse\|data\|output | execute(job, services) | Job processing |

### State Access

| State | per_run | per_job |
|-------|---------|---------|
| run | ✅ RO | ✅ RO |
| config | ✅ RO | ✅ RO |
| job | ❌ | ✅ RW |
| jobs | ❌ | ✅ RO |
| plugin | ❌ | ✅ RW |
| plugins | ❌ | ✅ RO |

---

**Next Document**: 04_TRIGGER_RULE_SYSTEM.md
