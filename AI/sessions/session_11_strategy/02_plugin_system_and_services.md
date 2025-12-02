# PLUGIN SYSTEM & SERVICES

```yaml
date: 2025-12-02
sources: v4, v5, v6, brainstorm-v1, brainstorm-v2, 11_execution_modes, plugin-system-brainstorm
status: updated
```

**UPDATE 2025-12-02:** See `plugin-system-brainstorm/` for finalized, industry-researched specs.
Key changes: 4-stage model (not 6), generic provides, PluginServices injection.

---

## 1. PHASE SİSTEMİ

### 1.1 4-Stage Model (UPDATED)

```
STAGE       MODE        DESCRIPTION                 EXAMPLES
──────────────────────────────────────────────────────────────
input       per_run     Job creation                Scanner, FileReader
parse       per_job     Parse input data            Renamer
metadata    per_job     External API data           TMDb, TVDb, FFProbe
output      per_job     Task execution              Tasker (plugin)
```

**Simplified from 6 to 4 stages:**
- Removed `modify` (rare use case, can be metadata)
- Removed `finalize` (can be per_run in output)
- Tasker is now a plugin, not core

### 1.2 Phase Execution Sırası

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE EXECUTION                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE 1: INPUT (per_run)                                    │
│  └── Scanner, FileReader                                     │
│      └── Output: List[Job]                                   │
│                                                              │
│  PHASE 2: PARSE (per_job)                                    │
│  └── Renamer                                                 │
│      └── Input: job.input.path                               │
│      └── Output: job.plugins.renamer.parsed                  │
│                                                              │
│  PHASE 3: METADATA (per_job)                                 │
│  └── TMDb, TVDb, FFProbe                                     │
│      └── Input: job.plugins.renamer.parsed                   │
│      └── Output: job.plugins.{name}.{data}                   │
│                                                              │
│  PHASE 4: OUTPUT (per_job)                                   │
│  └── Tasker plugin                                           │
│      └── Input: job with all plugin data                     │
│      └── Output: print, save actions                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. PLUGIN MANIFEST YAPISI

### 2.1 manifest.yml Schema

```yaml
# plugins/{name}/manifest.yml
name: string                    # Unique identifier
version: string                 # Semver
description: string             # Human readable

# Phase & Execution
phase: input | parse | metadata | modify | finalize
execution_mode: per_job | per_run  # Default: per_job

# Dependencies
requires: List[string]          # e.g., ["renamer.parsed"]

# Class info
class_name: string              # Python class name
entry_point: string             # Default: "client.py"
```

### 2.2 Örnekler

```yaml
# plugins/scanner/manifest.yml
name: scanner
version: 1.0.0
phase: input
execution_mode: per_run
requires: []
class_name: ScannerPlugin

# plugins/renamer/manifest.yml
name: renamer
version: 1.0.0
phase: parse
execution_mode: per_job
requires: []
class_name: RenamerPlugin

# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
phase: metadata
execution_mode: per_job
requires:
  - renamer.parsed.movie
  - renamer.parsed.show
class_name: TMDbPlugin
```

---

## 3. EXECUTION MODE

### 3.1 per_job vs per_run

```
MODE        SIGNATURE                   USE CASE
────────────────────────────────────────────────────────────────
per_job     execute(job, services)      Renamer, FFProbe, TMDb
per_run     execute_run(services)       Scanner, Rclone, Summary
```

**TMDb Not:** TMDb per_job modunda çalışır. API batching istiyorsa
içeride kendi cache/batch mekanizmasını kullanır. Execution mode
plugin'in ne zaman çalıştığını belirler, nasıl çalıştığını değil.

### 3.2 BasePlugin Interface

```python
class BasePlugin(ABC):
    name: str
    config: Dict
    
    @property
    def manifest(self) -> PluginManifest:
        """Load from manifest.yml"""
    
    @property
    def execution_mode(self) -> str:
        """'per_job' or 'per_run'"""
        return self.manifest.execution_mode
    
    # Per-job execution
    def execute(self, job: Job, services: PluginServices) -> PluginResult:
        """Override for per_job mode"""
        raise NotImplementedError
    
    # Per-run execution
    def execute_run(self, services: PluginServices) -> PluginResult:
        """Override for per_run mode"""
        raise NotImplementedError
    
    # Event handler (optional)
    def on_event(self, event: str, data: Dict) -> None:
        """Handle EventBus events"""
        pass
```

---

## 4. PLUGIN SERVICES (eski: SDK)

### 4.1 Neden "Services" adı?

```
SDK       → Software Development Kit (harici geliştiriciler için)
Services  → Internal service interface (plugin'lerin core ile iletişimi)

Archiverr bağlamında "Services" daha doğru çünkü:
- Plugin'ler harici değil, proje parçası
- Interface tarzı bir yapı (not a toolkit)
```

### 4.2 PluginServices Interface

```python
@dataclass
class PluginServices:
    """Services provided to plugins during execution"""
    
    # Job access
    jobs: JobService
    
    # Task emission
    tasks: TaskService
    
    # Logging
    logger: PluginLogger
    
    # Config access
    config: ConfigService
```

### 4.3 JobService

```python
class JobService:
    """Job operations for plugins"""
    
    def __init__(self, state: StateManager):
        self._state = state
    
    # Read operations
    def get_current(self) -> Job:
        """Get current job (per_job mode)"""
    
    def get_all(self) -> List[Job]:
        """Get all jobs (batch mode)"""
    
    def get_by_id(self, job_id: str) -> Optional[Job]:
        """Get specific job"""
    
    # Write operations (modify phase only)
    def create(self, input_path: str, category: str = "unknown") -> Job:
        """Create new job"""
    
    def update_input(self, job_id: str, **kwargs) -> None:
        """Update job input data"""
    
    # Plugin data
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Optional[Dict]:
        """Get another plugin's data for this job"""
```

### 4.4 TaskService

```python
class TaskService:
    """Task operations for plugins"""
    
    def emit(self, job: Job, task_type: str, **data) -> None:
        """Emit task for execution"""
        # Types: rename, move, copy, delete, custom
```

---

## 5. PLUGIN RESULT

### 5.1 PluginResult Structure

```python
@dataclass
class PluginResult:
    status: PluginStatus          # SUCCESS, FAILED, SKIPPED
    data: Optional[Dict] = None   # Plugin-specific data
    error: Optional[str] = None   # Error message if failed
    
    @classmethod
    def success(cls, data: Dict) -> 'PluginResult':
        return cls(status=PluginStatus.SUCCESS, data=data)
    
    @classmethod
    def failed(cls, error: str) -> 'PluginResult':
        return cls(status=PluginStatus.FAILED, error=error)
    
    @classmethod
    def skipped(cls, reason: str = "") -> 'PluginResult':
        return cls(status=PluginStatus.SKIPPED, error=reason)

class PluginStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"          # eski: not_supported
```

### 5.2 Data Structure Convention

```
Plugin          Data Keys
────────────────────────────────────────────────
scanner         input.path, input.virtual
renamer         parsed.movie, parsed.show
tmdb            movie, show, season, episode
ffprobe         video, audio, container
```

---

## 6. VALIDATION SİSTEMİ

### 6.1 requires Validation

```python
class RequiresValidator:
    """Validate plugin requirements before execution"""
    
    def validate(self, plugin: BasePlugin, job: Job) -> Tuple[bool, List[str]]:
        """
        Check if all requires are satisfied.
        
        Returns:
            (can_execute, missing_paths)
        """
        missing = []
        for path in plugin.manifest.requires:
            if not self._path_exists(job, path):
                missing.append(path)
        
        return (len(missing) == 0, missing)
    
    def _path_exists(self, job: Job, path: str) -> bool:
        """Check if nested path exists in job data"""
        parts = path.split('.')
        current = job.plugins
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        return True
```

### 6.2 Validation Akışı

```
Plugin Execution Request
        │
        ▼
┌───────────────────┐
│ Check requires    │
│ for current job   │
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
satisfied    missing
    │           │
    ▼           ▼
 EXECUTE     SKIP
    │           │
    ▼           ▼
SUCCESS/    SKIPPED
FAILED      (with reason)
```

---

## 7. PLUGIN KATEGORİLERİ ZORUNLULUKLARI

### 7.1 INPUT Category

```
Zorunluluk: En az 1 input plugin ÖNERILIR (yoksa 0 job)
Execution: Run başında, bir kez
Output: List[Job] döner
Example: Scanner, FileReader
```

### 7.2 PARSE Category

```
Zorunluluk: Opsiyonel
Execution: Input bittikten sonra, per_job
Dependency: Genelde input plugin'e bağlı
Example: Renamer
```

### 7.3 METADATA Category

```
Zorunluluk: Opsiyonel
Execution: Parse bittikten sonra
Dependency: requires ile tanımlanır
Example: TMDb, TVDb, FFProbe
```

### 7.4 MODIFY Category

```
Zorunluluk: Opsiyonel
Execution: Metadata bittikten sonra
Capability: Yeni job oluşturabilir, var olanı değiştirebilir
Example: Splitter, DuplicateDetector
```

---

## 8. PHASE EXECUTOR

```python
class PhaseExecutor:
    """Execute plugins by phase"""
    
    PHASES = ['input', 'parse', 'metadata', 'modify', 'finalize']
    
    def __init__(self, plugins: List[BasePlugin], state: StateManager):
        self._plugins = self._group_by_phase(plugins)
        self._state = state
    
    def execute(self) -> None:
        for phase in self.PHASES:
            self._execute_phase(phase)
    
    def _execute_phase(self, phase: str) -> None:
        plugins = self._plugins.get(phase, [])
        if not plugins:
            return
        
        # Sort by requires (topological)
        sorted_plugins = self._sort_by_requires(plugins)
        
        for plugin in sorted_plugins:
            if plugin.execution_mode == 'per_run':
                self._execute_per_run(plugin)
            else:
                self._execute_per_job(plugin)
    
    def _execute_per_job(self, plugin: BasePlugin) -> None:
        services = self._build_services()
        for job in self._state.get_all_jobs():
            # Validate requires
            can_run, missing = self._validator.validate(plugin, job)
            if not can_run:
                result = PluginResult.skipped(f"Missing: {missing}")
            else:
                result = plugin.execute(job, services)
            
            self._state.update_plugin(job.index, plugin.name, result)
    
    def _execute_per_run(self, plugin: BasePlugin) -> None:
        services = self._build_services()
        result = plugin.execute_run(services)
        self._state.update_plugin_result(plugin.name, result)
```

---

## 9. MEVCUT vs YENİ

### Mevcut plugin.json

```json
{
  "name": "tmdb",
  "version": "1.0.0",
  "category": "output",
  "class_name": "TMDbPlugin",
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed.movie", "renamer.parsed.show"]
}
```

### Yeni manifest.yml

```yaml
name: tmdb
version: 1.0.0
phase: metadata
execution_mode: per_job
requires:
  - renamer.parsed.movie
  - renamer.parsed.show
class_name: TMDbPlugin
```

**Değişiklikler:**
- `category: output` → `phase: metadata`
- `depends_on` kaldırıldı (requires yeterli)
- `expects` → `requires`
- `+execution_mode`

---

**Son Güncelleme:** 2025-11-30
