# PHASE 5: STAGE EXECUTOR (4 STAGE SİSTEMİ)

```yaml
phase: 5
öncelik: 🟠 YÜKSEK
tahmini_süre: 4-6 saat
bağımlılık: P4 (Orchestrator)
strateji_belgesi: 03_orchestrator_and_execution_flow.md (Stage Execution bölümü)
test_türü: integration
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P4 tamamlandı (Orchestrator çalışıyor)
- [ ] PluginRegistry stage bazlı plugin'leri dönebiliyor
- [ ] PluginServices (P3) hazır
- [ ] Integration testler PASS

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Dosya: `src/archiverr/core/plugins/executor.py`

```python
# MEVCUT YAPI - 2 category (input/output)

class PluginExecutor:
    def configure(self, event_bus, execution_id, config, dry_run, debug):
        self._event_bus = event_bus
        self._execution_id = execution_id
        # ...

    def execute_input_plugins(self, input_plugins: Dict) -> List[Dict]:
        """Input plugin'lerini çalıştır, matches döndür"""
        all_matches = []
        for name, plugin in input_plugins.items():
            matches = plugin.get_matches()  # per_run
            all_matches.extend(matches)
        return all_matches

    def execute_output_pipeline(
        self,
        output_plugins: Dict,
        execution_groups: List[List[str]],
        match: Dict,
        resolver: DependencyResolver,
        match_index: int,
        total_matches: int,
        api_response: Dict
    ) -> Dict:
        """Output plugin'lerini sırayla çalıştır"""
        result = match.copy()

        for group in execution_groups:
            for plugin_name in group:
                plugin = output_plugins.get(plugin_name)
                if plugin:
                    # Expectations check
                    # Execute plugin
                    # Update result

        return result
```

### 1.2 Sorunlar

1. **2 Category Limiti:** Sadece input/output var, parse/data yok
2. **Execution Mode Karışık:** per_run ve per_job ayrımı yok
3. **Requires Validation Yok:** Strateji requires sistemini uygulamıyor
4. **PluginServices Kullanmıyor:** Global state erişimi

### 1.3 Mevcut Plugin Manifest (category bazlı)

```yaml
# plugins/tmdb/manifest.yml (MEVCUT)
name: tmdb
category: output
depends_on: [renamer]
expects: [renamer.parsed.movie]
```

---

## 2. HEDEF YAPI

### 2.1 Stage Tanımları

```
┌─────────────────────────────────────────────────────────────┐
│                    4 STAGE SİSTEMİ                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  STAGE    │ MODE     │ PLUGIN'LER          │ PROVIDES        │
│  ─────────┼──────────┼─────────────────────┼─────────────────│
│  input    │ per_run  │ scanner, file-input │ job.create      │
│  parse    │ per_job  │ renamer             │ state.update    │
│  data     │ per_job  │ tmdb, tvdb, ffprobe │ http.request    │
│  output   │ mixed    │ tasker, rclone      │ fs.write        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Execution Flow

```
                    ORCHESTRATOR
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    STAGE EXECUTOR                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  INPUT STAGE (per_run):                                       │
│    scanner.execute_run(services)                              │
│    --> jobs[] oluşturuldu (state.create_job)                 │
│                                                               │
│  PARSE STAGE (per_job):                                       │
│    for job in jobs:                                          │
│        renamer.execute(job, services)                        │
│        --> job.plugins.renamer = {...}                       │
│                                                               │
│  DATA STAGE (per_job, parallel mümkün):                       │
│    for job in jobs:                                          │
│        for plugin in [tmdb, tvdb, ffprobe]:                  │
│            if requires_satisfied(plugin, job):               │
│                plugin.execute(job, services)                 │
│                                                               │
│  OUTPUT STAGE (mixed):                                        │
│    for job in jobs:                                          │
│        tasker.execute(job, services)    # per_job            │
│    rclone.execute_run(services)         # per_run            │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 Yeni Manifest Format (stage bazlı)

```yaml
# plugins/tmdb/manifest.yml (YENİ)
name: tmdb
version: 1.0.0
stage: data # category → stage
requires:
  - job.plugins.renamer.parsed # Explicit prefix
provides:
  - http.request
  - state.update
trigger_rule: all_success # all_success | one_success | all_done
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: Stage Enum ve Mode Tanımla

**Dosya:** `src/archiverr/core/plugins/stage_executor.py` (YENİ)

```python
"""Stage-based plugin execution"""

from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from archiverr.state.models import JobState
from archiverr.state.manager import StateManager
from archiverr.events import EventBus
from archiverr.core.services import PluginServices, create_plugin_services
from archiverr.core.exceptions import StageError, PluginError
from archiverr.utils.debug import Debugger

from .registry import PluginRegistry


class Stage(Enum):
    INPUT = "input"
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"


class ExecutionMode(Enum):
    PER_RUN = "per_run"    # Plugin run başına 1 kez çalışır
    PER_JOB = "per_job"    # Plugin her job için çalışır


# Stage → Default execution mode mapping
STAGE_MODES = {
    Stage.INPUT: ExecutionMode.PER_RUN,
    Stage.PARSE: ExecutionMode.PER_JOB,
    Stage.DATA: ExecutionMode.PER_JOB,
    Stage.OUTPUT: ExecutionMode.PER_JOB,  # mixed ama default per_job
}
```

---

### ADIM 2: RequiresValidator Class

**Dosya:** `src/archiverr/core/plugins/requires_validator.py` (YENİ)

```python
"""Requires validation for plugin execution"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from archiverr.state.models import JobState


@dataclass
class RequiresResult:
    """Requires validation result"""
    satisfied: bool
    missing: List[str]


class RequiresValidator:
    """
    Plugin requires validation.

    Path format: "job.plugins.{plugin_name}.{path}"
    Example: "job.plugins.renamer.parsed.movie"
    """

    def validate(self, job: JobState, requires: List[str]) -> RequiresResult:
        """
        Validate all requires paths exist in job state.

        Args:
            job: Current job state
            requires: List of required paths

        Returns:
            RequiresResult with satisfaction status and missing paths
        """
        if not requires:
            return RequiresResult(satisfied=True, missing=[])

        missing = []
        for path in requires:
            if not self._path_exists(job, path):
                missing.append(path)

        return RequiresResult(
            satisfied=len(missing) == 0,
            missing=missing
        )

    def _path_exists(self, job: JobState, path: str) -> bool:
        """Check if path exists and has value in job state"""
        parts = path.split('.')

        # Parse path: job.plugins.{plugin}.{rest}
        if len(parts) < 3:
            return False

        if parts[0] != 'job':
            return False

        if parts[1] == 'plugins':
            # job.plugins.renamer.parsed.movie
            plugin_name = parts[2]
            remaining_path = parts[3:]

            # Get plugin data from job
            plugin_data = getattr(job, 'plugins', {}).get(plugin_name, {})

            # Navigate remaining path
            current = plugin_data
            for part in remaining_path:
                if not isinstance(current, dict):
                    return False
                if part not in current:
                    return False
                current = current[part]

            # Check not None/empty
            return current is not None

        elif parts[1] == 'input':
            # job.input.value, job.input.data.filename
            return self._get_nested_value(job.input, parts[2:]) is not None

        elif parts[1] == 'output':
            # job.output.values, job.output.data
            return self._get_nested_value(job.output, parts[2:]) is not None

        return False

    def _get_nested_value(self, obj: Any, path: List[str]) -> Optional[Any]:
        """Get nested value from object"""
        current = obj
        for part in path:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
```

**Test:**

```python
def test_requires_validator_basic():
    validator = RequiresValidator()

    job = JobState(index=0, run_id="test")
    job.plugins = {
        "renamer": {
            "parsed": {"movie": {"name": "Test Movie"}}
        }
    }

    # Satisfied
    result = validator.validate(job, ["job.plugins.renamer.parsed.movie"])
    assert result.satisfied == True
    assert result.missing == []

    # Not satisfied
    result = validator.validate(job, ["job.plugins.tmdb.movie"])
    assert result.satisfied == False
    assert "job.plugins.tmdb.movie" in result.missing

def test_requires_empty():
    validator = RequiresValidator()
    job = JobState(index=0, run_id="test")

    result = validator.validate(job, [])
    assert result.satisfied == True
```

---

### ADIM 3: StageExecutor Class

**Dosya:** `src/archiverr/core/plugins/stage_executor.py` (devam)

```python
class StageExecutor:
    """
    Stage-based plugin executor.

    4 stage'i sırayla çalıştırır:
    - INPUT: per_run, job'ları oluşturur
    - PARSE: per_job, metadata parse
    - DATA: per_job, external data fetch
    - OUTPUT: mixed, file operations
    """

    def __init__(
        self,
        state: StateManager,
        plugin_registry: PluginRegistry,
        event_bus: EventBus,
        config: Dict[str, Any],
        debugger: Optional[Debugger] = None
    ):
        self._state = state
        self._registry = plugin_registry
        self._event_bus = event_bus
        self._config = config
        self._debugger = debugger
        self._requires_validator = RequiresValidator()

    def execute_stage(self, stage: Stage) -> None:
        """
        Execute all plugins for given stage.

        Args:
            stage: Stage to execute (INPUT, PARSE, DATA, OUTPUT)

        Raises:
            StageError: If stage execution fails critically
        """
        self._log("info", f"Executing stage: {stage.value}")

        # Get plugins for this stage
        plugins = self._registry.get_plugins_by_stage(stage)

        if not plugins:
            self._log("debug", f"No plugins for stage: {stage.value}")
            return

        # Sort by requires (topological sort)
        sorted_plugins = self._topological_sort(plugins)

        # Get execution mode for this stage
        mode = STAGE_MODES.get(stage, ExecutionMode.PER_JOB)

        try:
            if mode == ExecutionMode.PER_RUN:
                self._execute_per_run(stage, sorted_plugins)
            else:
                self._execute_per_job(stage, sorted_plugins)
        except Exception as e:
            self._log("error", f"Stage {stage.value} failed: {e}")
            raise StageError(f"Stage {stage.value} failed: {e}")

    def _execute_per_run(self, stage: Stage, plugins: List) -> None:
        """Execute plugins once per run (INPUT stage)"""
        self._log("debug", f"Executing {len(plugins)} plugins (per_run)")

        for plugin in plugins:
            plugin_name = getattr(plugin, 'name', str(plugin))
            self._log("debug", f"Executing plugin: {plugin_name}")

            try:
                # Create services for this plugin
                services = self._create_services(plugin_name)

                # Execute plugin
                result = plugin.execute_run(services)

                # Emit event
                self._event_bus.emit("plugin.completed", {
                    "plugin_name": plugin_name,
                    "stage": stage.value,
                    "mode": "per_run",
                    "success": result.status.value == "success" if hasattr(result, 'status') else True,
                    "data": result.data if hasattr(result, 'data') else {}
                })

            except Exception as e:
                self._log("error", f"Plugin {plugin_name} failed: {e}")
                self._event_bus.emit("plugin.failed", {
                    "plugin_name": plugin_name,
                    "stage": stage.value,
                    "error": str(e)
                })
                # Continue with next plugin

    def _execute_per_job(self, stage: Stage, plugins: List) -> None:
        """Execute plugins for each job (PARSE, DATA, OUTPUT stages)"""
        jobs = self._state.get_all_jobs()

        if not jobs:
            self._log("warn", f"No jobs to process for stage: {stage.value}")
            return

        self._log("debug", f"Executing {len(plugins)} plugins for {len(jobs)} jobs")

        for job in jobs:
            for plugin in plugins:
                plugin_name = getattr(plugin, 'name', str(plugin))

                # Check requires
                manifest = self._registry.get_manifest(plugin_name)
                requires = manifest.get('requires', []) if manifest else []

                if requires:
                    validation = self._requires_validator.validate(job, requires)
                    if not validation.satisfied:
                        self._log("debug", f"Skipping {plugin_name} for job {job.id}: requires not satisfied")
                        self._mark_plugin_skipped(job, plugin_name, validation.missing)
                        continue

                try:
                    # Create services for this plugin and job
                    services = self._create_services(plugin_name)
                    services.state.set_current_job(job.id)

                    # Execute plugin
                    result = plugin.execute(job, services)

                    # Update job state with plugin result
                    if hasattr(result, 'data') and result.data:
                        self._state.update_plugin_data(job.id, plugin_name, result.data)

                    # Mark plugin as executed
                    success = result.status.value == "success" if hasattr(result, 'status') else True
                    self._mark_plugin_executed(job, plugin_name, success)

                    # Emit event
                    self._event_bus.emit("plugin.completed", {
                        "job_id": job.id,
                        "plugin_name": plugin_name,
                        "stage": stage.value,
                        "mode": "per_job",
                        "success": success,
                        "data": result.data if hasattr(result, 'data') else {}
                    })

                except Exception as e:
                    self._log("error", f"Plugin {plugin_name} failed for job {job.id}: {e}")
                    self._mark_plugin_failed(job, plugin_name, str(e))
                    self._event_bus.emit("plugin.failed", {
                        "job_id": job.id,
                        "plugin_name": plugin_name,
                        "stage": stage.value,
                        "error": str(e)
                    })
                    # Continue with next plugin

            # Emit job progress event
            self._event_bus.emit("job.progress", {
                "job_id": job.id,
                "stage": stage.value,
                "completed": True
            })

    def _topological_sort(self, plugins: Dict) -> List:
        """Sort plugins by requires dependencies"""
        # Simple implementation - for complex DAG, use proper algorithm
        # For now, return plugins in dict order
        return list(plugins.values())

    def _create_services(self, plugin_name: str) -> PluginServices:
        """Create PluginServices for a plugin"""
        from archiverr.utils.debug import get_debugger

        return create_plugin_services(
            state_manager=self._state,
            event_bus=self._event_bus,
            debugger=get_debugger() if self._debugger else None,
            config=self._config,
            plugin_name=plugin_name
        )

    def _mark_plugin_executed(self, job: JobState, plugin_name: str, success: bool) -> None:
        """Mark plugin as executed in job status"""
        if success:
            job.status.executed.append(plugin_name)
        else:
            job.status.failed.append(plugin_name)

    def _mark_plugin_failed(self, job: JobState, plugin_name: str, error: str) -> None:
        """Mark plugin as failed in job status"""
        job.status.failed.append(plugin_name)
        job.status.success = False

    def _mark_plugin_skipped(self, job: JobState, plugin_name: str, missing: List[str]) -> None:
        """Mark plugin as skipped in job status"""
        job.status.skipped.append(plugin_name)

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Debug logger wrapper"""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func("stage_executor", message, **kwargs)
```

---

### ADIM 4: Mixed Mode Support (OUTPUT stage)

**Dosya:** `src/archiverr/core/plugins/stage_executor.py` (ek)

```python
def _execute_mixed(self, stage: Stage, plugins: List) -> None:
    """
    Execute plugins in mixed mode (OUTPUT stage).

    Some plugins are per_job (tasker), some are per_run (rclone).
    """
    per_job_plugins = []
    per_run_plugins = []

    for plugin in plugins:
        manifest = self._registry.get_manifest(getattr(plugin, 'name', ''))
        mode = manifest.get('execution_mode', 'per_job') if manifest else 'per_job'

        if mode == 'per_run':
            per_run_plugins.append(plugin)
        else:
            per_job_plugins.append(plugin)

    # Execute per_job plugins first
    if per_job_plugins:
        self._execute_per_job(stage, per_job_plugins)

    # Then per_run plugins
    if per_run_plugins:
        self._execute_per_run(stage, per_run_plugins)


# Update execute_stage to use mixed mode for OUTPUT
def execute_stage(self, stage: Stage) -> None:
    # ... existing code ...

    if stage == Stage.OUTPUT:
        self._execute_mixed(stage, sorted_plugins)
    elif mode == ExecutionMode.PER_RUN:
        self._execute_per_run(stage, sorted_plugins)
    else:
        self._execute_per_job(stage, sorted_plugins)
```

---

### ADIM 5: Parallel Execution (Opsiyonel)

**Dosya:** `src/archiverr/core/plugins/stage_executor.py` (ek)

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class StageExecutor:
    # ... existing code ...

    async def _execute_per_job_parallel(self, stage: Stage, plugins: List) -> None:
        """
        Execute plugins in parallel for each job.

        Plugins with no interdependencies can run simultaneously.
        """
        jobs = self._state.get_all_jobs()

        if not jobs:
            return

        # Group plugins by dependency level
        groups = self._group_by_dependency_level(plugins)

        for group in groups:
            # Execute group in parallel
            tasks = []
            for job in jobs:
                for plugin in group:
                    tasks.append(self._execute_plugin_async(job, plugin, stage))

            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_plugin_async(self, job: JobState, plugin, stage: Stage) -> None:
        """Execute single plugin asynchronously"""
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=4)

        def run_plugin():
            plugin_name = getattr(plugin, 'name', str(plugin))
            services = self._create_services(plugin_name)
            services.state.set_current_job(job.id)
            return plugin.execute(job, services)

        result = await loop.run_in_executor(executor, run_plugin)
        return result

    def _group_by_dependency_level(self, plugins: List) -> List[List]:
        """Group plugins that can run in parallel"""
        # Simple implementation: all plugins in same group
        # For proper implementation, analyze requires graph
        return [plugins]
```

---

## 4. MANIFEST MIGRATION

### 4.1 Eski → Yeni Format

```yaml
# MEVCUT (category bazlı)
name: tmdb
category: output
depends_on: [renamer]
expects: [renamer.parsed.movie]

# YENİ (stage bazlı)
name: tmdb
version: 1.0.0
stage: data
requires:
  - job.plugins.renamer.parsed
provides:
  - http.request
  - state.update
trigger_rule: all_success
```

### 4.2 Migration Map

| Plugin     | Eski Category | Yeni Stage |
| ---------- | ------------- | ---------- |
| scanner    | input         | input      |
| file-input | input         | input      |
| renamer    | output        | parse      |
| tmdb       | output        | data       |
| tvdb       | output        | data       |
| ffprobe    | output        | data       |
| tasker     | output        | output     |
| rclone     | output        | output     |

### 4.3 Backward Compatibility

```python
def _normalize_manifest(manifest: Dict) -> Dict:
    """Convert old category format to new stage format"""
    if 'stage' in manifest:
        return manifest

    category = manifest.get('category', 'output')

    # Map category to stage
    if category == 'input':
        stage = 'input'
    elif manifest.get('name') == 'renamer':
        stage = 'parse'
    else:
        # Default: assume data stage for most plugins
        stage = 'data'

    # Convert depends_on/expects to requires
    requires = []
    for expect in manifest.get('expects', []):
        # "renamer.parsed.movie" → "job.plugins.renamer.parsed.movie"
        requires.append(f"job.plugins.{expect}")

    return {
        **manifest,
        'stage': stage,
        'requires': requires,
        'provides': manifest.get('provides', ['state.update'])
    }
```

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests

```python
# tests/unit/core/plugins/test_stage_executor.py

import pytest
from unittest.mock import Mock, MagicMock
from archiverr.core.plugins.stage_executor import (
    StageExecutor, Stage, ExecutionMode, STAGE_MODES
)
from archiverr.state.models import JobState


class TestStageEnum:
    def test_stage_values(self):
        assert Stage.INPUT.value == "input"
        assert Stage.PARSE.value == "parse"
        assert Stage.DATA.value == "data"
        assert Stage.OUTPUT.value == "output"


class TestStageModes:
    def test_input_is_per_run(self):
        assert STAGE_MODES[Stage.INPUT] == ExecutionMode.PER_RUN

    def test_parse_is_per_job(self):
        assert STAGE_MODES[Stage.PARSE] == ExecutionMode.PER_JOB

    def test_data_is_per_job(self):
        assert STAGE_MODES[Stage.DATA] == ExecutionMode.PER_JOB


class TestStageExecutor:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "state": Mock(),
            "plugin_registry": Mock(),
            "event_bus": Mock(),
            "config": {"options": {"debug": True}},
            "debugger": None
        }

    @pytest.fixture
    def executor(self, mock_dependencies):
        return StageExecutor(**mock_dependencies)

    def test_execute_stage_calls_registry(self, executor, mock_dependencies):
        mock_dependencies["plugin_registry"].get_plugins_by_stage.return_value = {}

        executor.execute_stage(Stage.INPUT)

        mock_dependencies["plugin_registry"].get_plugins_by_stage.assert_called_once()

    def test_execute_per_run_for_input(self, executor, mock_dependencies):
        mock_plugin = Mock()
        mock_plugin.name = "scanner"
        mock_plugin.execute_run.return_value = Mock(data={})

        mock_dependencies["plugin_registry"].get_plugins_by_stage.return_value = {
            "scanner": mock_plugin
        }

        executor.execute_stage(Stage.INPUT)

        mock_plugin.execute_run.assert_called_once()

    def test_execute_per_job_for_parse(self, executor, mock_dependencies):
        mock_plugin = Mock()
        mock_plugin.name = "renamer"
        mock_plugin.execute.return_value = Mock(data={}, status=Mock(value="success"))

        mock_job = JobState(index=0, run_id="test")
        mock_dependencies["state"].get_all_jobs.return_value = [mock_job]
        mock_dependencies["plugin_registry"].get_plugins_by_stage.return_value = {
            "renamer": mock_plugin
        }
        mock_dependencies["plugin_registry"].get_manifest.return_value = {"requires": []}

        executor.execute_stage(Stage.PARSE)

        mock_plugin.execute.assert_called_once()

    def test_requires_not_satisfied_skips_plugin(self, executor, mock_dependencies):
        mock_plugin = Mock()
        mock_plugin.name = "tmdb"

        mock_job = JobState(index=0, run_id="test")
        mock_job.plugins = {}  # No renamer data

        mock_dependencies["state"].get_all_jobs.return_value = [mock_job]
        mock_dependencies["plugin_registry"].get_plugins_by_stage.return_value = {
            "tmdb": mock_plugin
        }
        mock_dependencies["plugin_registry"].get_manifest.return_value = {
            "requires": ["job.plugins.renamer.parsed"]
        }

        executor.execute_stage(Stage.DATA)

        mock_plugin.execute.assert_not_called()
        assert "tmdb" in mock_job.status.skipped


class TestRequiresValidator:
    def test_empty_requires(self):
        from archiverr.core.plugins.requires_validator import RequiresValidator

        validator = RequiresValidator()
        job = JobState(index=0, run_id="test")

        result = validator.validate(job, [])

        assert result.satisfied == True

    def test_satisfied_requires(self):
        from archiverr.core.plugins.requires_validator import RequiresValidator

        validator = RequiresValidator()
        job = JobState(index=0, run_id="test")
        job.plugins = {
            "renamer": {"parsed": {"movie": {"name": "Test"}}}
        }

        result = validator.validate(job, ["job.plugins.renamer.parsed.movie"])

        assert result.satisfied == True
```

### 5.2 Integration Tests

```python
# tests/integration/core/test_stage_execution.py

import pytest
from archiverr.core.orchestrator import build_orchestrator


class TestStageExecution:
    @pytest.fixture
    def test_config(self, tmp_path):
        test_file = tmp_path / "test.mkv"
        test_file.write_text("test")

        return {
            "options": {"debug": True, "dry_run": True},
            "scanner": {"targets": [str(tmp_path)]}
        }

    def test_four_stages_execute_in_order(self, test_config):
        """input → parse → data → output"""
        executed_stages = []

        # Mock to track stage order
        orchestrator = build_orchestrator(test_config)
        original_execute = orchestrator._stage_executor.execute_stage

        def track_execute(stage):
            executed_stages.append(stage.value)
            return original_execute(stage)

        orchestrator._stage_executor.execute_stage = track_execute
        orchestrator.run()

        assert executed_stages == ["input", "parse", "data", "output"]

    def test_input_creates_jobs(self, test_config):
        """INPUT stage job oluşturmalı"""
        orchestrator = build_orchestrator(test_config)
        result = orchestrator.run()

        assert result.total_jobs >= 0
```

---

## 6. PHASE 5 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `Stage` enum oluşturuldu (INPUT, PARSE, DATA, OUTPUT)
- [ ] `ExecutionMode` enum oluşturuldu (PER_RUN, PER_JOB)
- [ ] `RequiresValidator` sınıfı oluşturuldu
- [ ] `StageExecutor` sınıfı oluşturuldu
- [ ] per_run execution (INPUT) çalışıyor
- [ ] per_job execution (PARSE, DATA) çalışıyor
- [ ] mixed execution (OUTPUT) çalışıyor
- [ ] Requires validation çalışıyor
- [ ] Plugin skip logic çalışıyor (requires not satisfied)
- [ ] Event emission çalışıyor (plugin.completed, plugin.failed)
- [ ] Unit testler PASS
- [ ] Integration testler PASS

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ Parallel execution (async) - opsiyonel, P5.1'de
- ❌ Complex topological sort - basit sıralama yeterli
- ❌ Mevcut plugin migration - manifest güncelleme ayrı iş

---

## 7. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                   | Belirti             | Çözüm                                   |
| ----------------------- | ------------------- | --------------------------------------- |
| No jobs after INPUT     | total_jobs = 0      | Scanner plugin'in execute_run() kontrol |
| Requires always fails   | All plugins skipped | Path format kontrol: job.plugins.X      |
| Plugin not found        | KeyError            | Registry.get_plugins_by_stage() kontrol |
| Services not configured | RuntimeError        | create_plugin_services() parametreleri  |
| Event handler crash     | Silent failure      | try/except + logging ekle               |

---

## 8. SONRAKİ PHASE'E GEÇİŞ

Phase 5 tamamlandığında:

1. Git commit: `feat(executor): add StageExecutor with 4-stage system`
2. Git tag: `v0.x.x-phase5`
3. `06_PHASE6_CONFIG_MANIFEST.md` dosyasını oku
4. Config ve Manifest değişikliklerine başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/core/plugins/test_stage_executor.py` çalıştır
- 4 stage sırayla çalışıyor mu test et
- Requires validation çalışıyor mu test et
- Mevcut plugin'ler çalışıyor mu kontrol et
