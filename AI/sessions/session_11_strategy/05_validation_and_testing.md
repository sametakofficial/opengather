# VALIDATION & TESTING

```yaml
tarih: 2025-12-02
durum: final
kaynak: plugin-system-brainstorm/09_REQUIRES_SYSTEM.md
v2_override: plugin-brainstorm-v2
```

---

## V2 OVERRIDE OZET

```
v1 -> v2 DEGISIKLIKLER:

- Runtime Validation KALDIRILDI (run asla durmasin)
- startup: config, schema, conflict, dynamic-var check
- pre-execution: requires, plugin-init
- runtime: YOK
- dynamic variable check: job.* ve run.* provides icinde YASAK
- error codes eklendi (E001-E021, W001-W003)
```

---

## 1. VALIDATION KATMANLARI

```
LAYER                    NE ZAMAN              AKSIYON
----------------------------------------------------------
Config Validation        Startup               Fail/Warn
Manifest Validation      Plugin discovery      Fail (skip plugin)
Plugin Config Validation Plugin loading        Fail (disable plugin)
Conflict Detection       Startup               Fail/Warn (--force bypass)
Dynamic Var Check        Startup               Fail (job.*/run.* YASAK)
Requires Validation      Pre-execution         Skip (mark skipped)
Runtime Validation       v2: KALDIRILDI        Run asla durmasin
```

---

## 2. CONFIG VALIDATION

### 2.1 Required Fields

```
config.yml
├── options: Optional[Dict]
│   ├── debug: bool (default: false)
│   ├── dry_run: bool (default: false)
│   └── hardlink: bool (default: false)
│
├── plugins: Required[Dict]
│   └── {name}: Dict
│       └── enabled: Required[bool]
│
└── tasks: Optional[List]
    └── []: TaskConfig
        ├── name: Required[str]
        ├── type: Required[print|save|summary]
        ├── condition: Optional[str]
        ├── template: Required for print
        └── destination: Required for save
```

### 2.2 Validation Rules

```python
class ConfigValidationRules:
    @staticmethod
    def validate_plugins_not_empty(config: Dict) -> Optional[str]:
        if not config.get('plugins'):
            return "No plugins defined"
        return None

    @staticmethod
    def validate_at_least_one_enabled(config: Dict) -> Optional[str]:
        plugins = config.get('plugins', {})
        enabled = [n for n, c in plugins.items() if c.get('enabled')]
        if not enabled:
            return "No plugins enabled"
        return None

    @staticmethod
    def validate_task_type(task: Dict) -> Optional[str]:
        valid_types = ['print', 'save', 'summary']
        if task.get('type') not in valid_types:
            return f"Invalid task type: {task.get('type')}"
        return None

    @staticmethod
    def validate_task_has_template(task: Dict) -> Optional[str]:
        if task.get('type') == 'print' and not task.get('template'):
            return f"Task '{task.get('name')}' missing template"
        return None
```

---

## 3. MANIFEST VALIDATION

### 3.1 Schema

```
manifest.yml
|-- name: Required[str] - lowercase, no spaces
|-- version: Required[str] - semver
|-- stage: Required[input|parse|data|output]
|-- class_name: Required[str]
|-- requires: Optional[List[str]]
|-- provides: Optional[List[str]]
|-- trigger_rule: Optional[all_success|one_success|all_done|all_fail|none_fail]
|                 # v2: always KALDIRILDI, 5 adet kaldi
|-- reactive: Optional[bool]
|-- entry_point: Optional[str] (default: client.py)
+-- config_schema: Optional[Dict]
```

### 3.2 Validation Rules

```
+----------------------------------------------------------+
|                    MANIFEST VALIDATION                    |
+----------------------------------------------------------+
|                                                           |
|  REQUIRED FIELDS                                          |
|  - name: non-empty, lowercase, [a-z][a-z0-9_]*           |
|  - version: semver format                                |
|  - stage: input | parse | data | output                  |
|  - class_name: valid Python identifier                   |
|                                                           |
|  PROVIDES                                                 |
|  - Standart listeden (http.*, fs.*, job.*, metadata.*)   |
|  - Custom: custom.* prefix                               |
|                                                           |
|  REQUIRES (implicit parsing)                              |
|  - job.* veya run.* -> state                             |
|  - Provides listesinde -> provide                        |
|  - Plugin adiysa -> plugin                               |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. REQUIRES VALIDATION

### 4.1 Path Format

```
requires format: "plugin_name.path.to.data"

Examples:
├── "renamer.parsed.movie"
├── "renamer.parsed.show"
├── "tmdb.movie"
└── "ffprobe.video.codec"
```

### 4.2 Validation Logic

```python
class RequiresValidator:
    def validate(self, plugin: BasePlugin, job: JobState) -> RequiresResult:
        """
        Returns:
            RequiresResult with can_execute and missing paths
        """
        requires = plugin.manifest.requires
        missing = []

        for path in requires:
            if not self._path_exists(job, path):
                missing.append(path)

        return RequiresResult(
            can_execute=len(missing) == 0,
            missing=missing
        )

    def _path_exists(self, job: JobState, path: str) -> bool:
        parts = path.split('.')

        # First part is plugin name
        plugin_name = parts[0]
        if plugin_name not in job.plugins:
            return False

        # Navigate nested path
        current = job.plugins[plugin_name]
        for part in parts[1:]:
            if not isinstance(current, dict):
                return False
            if part not in current:
                return False
            current = current[part]

        # Check not None/empty
        return current is not None
```

### 4.3 Requires Behavior

```
┌─────────────────────────────────────────────────────────────┐
│                    REQUIRES CHECK                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Plugin: tmdb                                                │
│  Requires: ["renamer.parsed.movie", "renamer.parsed.show"]   │
│                                                              │
│  Job has:                                                    │
│  ├── renamer.parsed.movie = {name: "Test"}                   │
│  └── renamer.parsed.show = None                              │
│                                                              │
│  Check: OR logic (any match)                                 │
│  Result: CAN EXECUTE (movie exists)                          │
│                                                              │
│  Alternative: AND logic (all required)                       │
│  manifest.yml:                                               │
│    requires:                                                 │
│      - renamer.parsed.movie                                  │
│    requires_all: true  # All must exist                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. PLUGIN LIFECYCLE VALIDATION

```
Discovery → Load → Initialize → Validate → Execute
              │        │           │          │
              │        │           │          └── Runtime errors
              │        │           └── Config schema check
              │        └── Class instantiation check
              └── Import check

At each stage, failure = disable plugin, continue with others
```

---

## 6. TEST STRUCTURE

### 6.1 Directory Layout

```
tests/
├── unit/
│   ├── state/
│   │   ├── test_models.py
│   │   └── test_manager.py
│   ├── core/
│   │   ├── test_orchestrator.py
│   │   ├── test_phase_executor.py
│   │   └── test_template_manager.py
│   ├── validation/
│   │   ├── test_config_validator.py
│   │   ├── test_manifest_validator.py
│   │   └── test_requires_validator.py
│   └── plugins/
│       ├── test_base_plugin.py
│       └── test_plugin_services.py
│
├── integration/
│   ├── test_full_run.py
│   ├── test_plugin_execution.py
│   └── test_task_execution.py
│
└── fixtures/
    ├── config/
    │   ├── valid_config.yml
    │   └── invalid_config.yml
    └── plugins/
        └── mock_plugin/
            ├── manifest.yml
            └── client.py
```

### 6.2 Test Patterns

```python
# Unit test pattern
class TestRequiresValidator:
    @pytest.fixture
    def validator(self):
        return RequiresValidator()

    @pytest.fixture
    def job_with_movie(self):
        return JobState(
            index=0,
            run_id="test",
            plugins={
                'renamer': {
                    'parsed': {
                        'movie': {'name': 'Test Movie'}
                    }
                }
            }
        )

    def test_valid_requires(self, validator, job_with_movie):
        plugin = MockPlugin(requires=['renamer.parsed.movie'])
        result = validator.validate(plugin, job_with_movie)
        assert result.can_execute is True

    def test_missing_requires(self, validator, job_with_movie):
        plugin = MockPlugin(requires=['tmdb.movie'])
        result = validator.validate(plugin, job_with_movie)
        assert result.can_execute is False
        assert 'tmdb.movie' in result.missing
```

---

## 7. VALIDATION ERROR HANDLING

### 7.1 Error Levels

```
LEVEL     ACTION                    EXAMPLE
──────────────────────────────────────────────────────────
FATAL     Exit immediately          config.yml not found
ERROR     Disable component         Invalid manifest
WARNING   Log and continue          Missing optional field
INFO      Log only                  Using default value
```

### 7.2 ValidationResult

```python
@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    warnings: List[str]

    @classmethod
    def ok(cls) -> 'ValidationResult':
        return cls(valid=True, errors=[], warnings=[])

    @classmethod
    def fail(cls, *errors: str) -> 'ValidationResult':
        return cls(valid=False, errors=list(errors), warnings=[])

    def __bool__(self) -> bool:
        return self.valid
```

---

## 8. INPUT PLUGIN ZORUNLULUĞU

### 8.1 Kural

```
Q: Input plugin zorunlu mu?
A: HAYIR, ama önerilir.

Davranış:
├── Input plugin YOK → 0 job, run tamamlanır
├── Input plugin VAR ama 0 job → 0 job, run tamamlanır
└── Input plugin VAR ve N job → N job işlenir

Validation: WARNING level (not error)
```

### 8.2 Implementation

```python
def validate_input_plugins(plugins: List[PluginManifest]) -> ValidationResult:
    input_plugins = [p for p in plugins if p.phase == 'input']

    if not input_plugins:
        return ValidationResult(
            valid=True,
            errors=[],
            warnings=["No input plugins enabled - no jobs will be created"]
        )

    return ValidationResult.ok()
```

---

## 9. TEST FIXTURES

### 9.1 Mock Plugin

```python
# tests/fixtures/plugins/mock_plugin/client.py
class MockPlugin(BasePlugin):
    def __init__(self, **kwargs):
        self._requires = kwargs.get('requires', [])
        self._result = kwargs.get('result', PluginResult.success({}))

    @property
    def manifest(self):
        return PluginManifest(
            name='mock',
            version='1.0.0',
            phase='metadata',
            execution_mode='per_job',
            requires=self._requires,
            class_name='MockPlugin'
        )

    def execute(self, job, services):
        return self._result
```

### 9.2 Mock State

```python
@pytest.fixture
def mock_state():
    state = StateManager.__new__(StateManager)
    state._current_run = RunState(id="test_run")
    state._jobs = {}
    state._job_id_map = {}
    return state

@pytest.fixture
def sample_job():
    return JobState(
        index=0,
        run_id="test_run",
        input=JobInput(path="/test/file.mkv", category="movie"),
        plugins={
            'scanner': {'input': {'path': '/test/file.mkv'}},
            'renamer': {'parsed': {'movie': {'name': 'Test'}}}
        }
    )
```

---

## 10. RUN COMMANDS

```bash
# All tests
pytest tests/

# Unit only
pytest tests/unit/

# Specific module
pytest tests/unit/validation/

# With coverage
pytest --cov=archiverr --cov-report=html tests/

# Verbose
pytest -v tests/

# Stop on first failure
pytest -x tests/
```

---

**Son Guncelleme:** 2025-12-02
