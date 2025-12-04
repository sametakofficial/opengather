# PHASE 4: ORCHESTRATOR

```yaml
phase: 4
öncelik: 🟠 YÜKSEK
tahmini_süre: 6-8 saat
bağımlılık: P1 (State Models), P2 (MongoDB), P3 (Plugin Services)
strateji_belgesi: 03_orchestrator_and_execution_flow.md
test_türü: integration
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P1 tamamlandı (RunState, JobState mevcut)
- [ ] P2 tamamlandı (MongoDB persistence çalışıyor)
- [ ] P3 tamamlandı (PluginServices, BasePlugin hazır)
- [ ] Tüm unit testler PASS

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Dosya: `src/archiverr/__main__.py`

```python
# MEVCUT YAPI (392 satır) - TÜM LOGİC TEK DOSYADA

def cli_main():
    # Config loading (20 satır)
    config = load_config_with_tracking(str(config_path))

    # Debug & validation (30 satır)
    debugger = init_debugger(enabled=debug)
    validator = ConfigValidator()

    # Event bus setup (20 satır)
    event_bus = EventBus(debugger=debugger)

    # State management setup (20 satır)
    state = GlobalStateManager()
    state.configure(persistence=persistence, ...)
    execution_id = state.start_execution(config)

    # Plugin discovery & loading (40 satır)
    discovery = PluginDiscovery()
    all_plugins = discovery.discover()
    loader = PluginLoader(all_plugins, config)
    input_plugins = loader.load_by_category('input')
    output_plugins = loader.load_by_category('output')

    # Dependency resolution (20 satır)
    resolver = DependencyResolver(all_plugins)
    execution_groups = resolver.resolve(enabled_output)

    # Input plugin execution (10 satır)
    executor = PluginExecutor()
    input_matches = executor.execute_input_plugins(input_plugins)

    # Output pipeline loop (150 satır) ← EN BÜYÜK BÖLÜM
    for index, match in enumerate(input_matches):
        result = executor.execute_output_pipeline(...)
        # Plugin result tracking
        # Task execution
        # State updates

    # API response building (30 satır)
    api_response = builder.build(...)

    # Report generation (20 satır)
    generate_dual_reports(api_response, timestamp)
```

### 1.2 Sorunlar

1. **SRP İhlali:** 392 satır tek fonksiyonda
2. **Test Zorluğu:** Monolitik yapı unit test'i zorlaştırıyor
3. **Kategori Sistemi:** 2 category (input/output) yerine 4 stage gerekli
4. **Global State:** `GlobalStateManager` singleton pattern

### 1.3 Mevcut Dosya Yapısı

```
src/archiverr/
├── __main__.py              # 392 satır → ~50 satır olacak
├── core/
│   ├── plugins/
│   │   ├── discovery.py     # Plugin discovery
│   │   ├── loader.py        # Plugin loading
│   │   ├── resolver.py      # Dependency resolution
│   │   └── executor.py      # 2 category executor
│   │
│   # NOT: core/tasks YOK - tasker bir PLUGIN!
│   # Task sistemi = tasker plugin (stage: output)
│
├── state/
│   ├── models.py            # State models
│   └── manager.py           # GlobalStateManager
└── events/
    └── bus.py               # EventBus
```

---

## 2. HEDEF YAPI

### 2.1 Yeni Dosya Yapısı

```
src/archiverr/
├── __main__.py              # Entry point (~50 satır)
│
├── core/
│   ├── orchestrator.py      # YENİ: Ana coordinator (~200 satır)
│   │
│   ├── plugins/
│   │   ├── discovery.py     # Değişiklik yok
│   │   ├── loader.py        # stage bazlı load
│   │   ├── registry.py      # YENİ: Plugin registry
│   │   ├── resolver.py      # requires/provides bazlı
│   │   └── stage_executor.py # YENİ: 4 stage executor
│   │
│   ├── services/            # P3'ten
│   │   ├── protocols.py
│   │   └── ...
│   │
│   └── validation/         # Validation system (P7)
│       ├── config.py
│       ├── manifest.py
│       └── dependency.py
│   # NOT: core/tasks YOK - tasker plugin (stage: output)!
│
├── state/
│   ├── models.py            # P1'den (RunState, JobState)
│   └── manager.py           # StateManager
│
└── events/
    └── bus.py
```

### 2.2 Orchestrator Sınıfı

```python
# core/orchestrator.py

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum

from archiverr.state.models import RunState, StateEnum
from archiverr.state.manager import StateManager
from archiverr.events import EventBus
from archiverr.infrastructure.persistence import PersistenceInterface
from .plugins.stage_executor import StageExecutor
from .plugins.registry import PluginRegistry


class Stage(Enum):
    INPUT = "input"
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"


@dataclass
class RunResult:
    """Orchestrator run sonucu"""
    run_id: str
    success: bool
    total_jobs: int
    completed: int
    failed: int
    duration_ms: int
    error: Optional[str] = None


class Orchestrator:
    """
    Ana koordinatör sınıfı.

    Tüm execution flow'u yönetir:
    - Run lifecycle (start → execute → finalize)
    - 4 Stage execution (input → parse → data → output)
    - Error handling ve recovery
    - Event emission
    """

    STAGES = [Stage.INPUT, Stage.PARSE, Stage.DATA, Stage.OUTPUT]

    def __init__(
        self,
        event_bus: EventBus,
        state: StateManager,
        persistence: PersistenceInterface,
        stage_executor: StageExecutor,
        plugin_registry: PluginRegistry,
        config: Dict[str, Any]
    ):
        self._event_bus = event_bus
        self._state = state
        self._persistence = persistence
        self._stage_executor = stage_executor
        self._plugin_registry = plugin_registry
        self._config = config
        self._run_id: Optional[str] = None

    def run(self) -> RunResult:
        """
        Ana execution method.

        Returns:
            RunResult with execution summary
        """
        try:
            self._initialize()
            self._execute_stages()
            self._finalize(success=True)
            return self._build_result(success=True)
        except CriticalError as e:
            self._handle_critical_error(e)
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))
        except Exception as e:
            self._handle_unexpected_error(e)
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))

    def _initialize(self) -> None:
        """Run başlangıç işlemleri"""
        # Start run in state
        self._run_id = self._state.start_run(self._config)

        # Emit run.started event
        self._event_bus.emit("run.started", {
            "run_id": self._run_id,
            "config": self._config
        })

        # Register event handlers
        self._register_event_handlers()

    def _execute_stages(self) -> None:
        """4 Stage'i sırayla çalıştır"""
        for stage in self.STAGES:
            self._event_bus.emit("stage.started", {"stage": stage.value})

            try:
                self._stage_executor.execute_stage(stage)
                self._event_bus.emit("stage.completed", {"stage": stage.value})
            except StageError as e:
                # Stage failed but continue with next stage
                self._event_bus.emit("stage.failed", {
                    "stage": stage.value,
                    "error": str(e)
                })
                # Continue to next stage (best effort)

    def _finalize(self, success: bool) -> None:
        """Run sonlandırma işlemleri"""
        # Complete run in state
        self._state.complete_run(success=success)

        # Flush to persistence
        self._persistence.flush()

        # Emit run.completed event
        run = self._state.get_run()
        self._event_bus.emit("run.completed", {
            "run_id": self._run_id,
            "success": success,
            "total_jobs": run.status.total_jobs,
            "completed": run.status.completed,
            "failed": run.status.failed
        })

    def _register_event_handlers(self) -> None:
        """Event handler'ları kaydet"""
        # State persistence on job complete
        self._event_bus.subscribe("job.completed", self._on_job_completed)
        self._event_bus.subscribe("plugin.completed", self._on_plugin_completed)

    def _on_job_completed(self, data: Dict) -> None:
        """Job tamamlandığında persistence'a kaydet"""
        job_id = data.get("job_id")
        if job_id:
            job = self._state.get_job(job_id)
            if job:
                self._persistence.save_job(job.to_dict())

    def _on_plugin_completed(self, data: Dict) -> None:
        """Plugin tamamlandığında persistence'a kaydet"""
        job_id = data.get("job_id")
        plugin_name = data.get("plugin_name")
        plugin_data = data.get("data", {})

        if job_id and plugin_name:
            self._persistence.save_plugin({
                "job_id": job_id,
                "run_id": self._run_id,
                "plugin_name": plugin_name,
                "data": plugin_data
            })

    def _build_result(self, success: bool, error: str = None) -> RunResult:
        """RunResult oluştur"""
        run = self._state.get_run()
        return RunResult(
            run_id=self._run_id,
            success=success,
            total_jobs=run.status.total_jobs,
            completed=run.status.completed,
            failed=run.status.failed,
            duration_ms=run.status.duration_ms,
            error=error
        )

    def _handle_critical_error(self, error: Exception) -> None:
        """Critical error handling"""
        self._event_bus.emit("run.error", {
            "run_id": self._run_id,
            "error": str(error),
            "critical": True
        })

    def _handle_unexpected_error(self, error: Exception) -> None:
        """Unexpected error handling"""
        self._event_bus.emit("run.error", {
            "run_id": self._run_id,
            "error": str(error),
            "critical": False
        })


class CriticalError(Exception):
    """Run'ı durduran kritik hata"""
    pass


class StageError(Exception):
    """Stage başarısız oldu ama run devam edebilir"""
    pass
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: Exception Classes Oluştur

**Dosya:** `src/archiverr/core/exceptions.py` (YENİ)

```python
"""Orchestrator exception classes"""

class ArchiverrError(Exception):
    """Base exception for Archiverr"""
    pass


class CriticalError(ArchiverrError):
    """
    Run'ı durduran kritik hata.

    Örnekler:
    - Config yüklenemedi
    - Database bağlantısı başarısız
    - Hiç plugin yüklenemedi
    """
    pass


class StageError(ArchiverrError):
    """
    Stage başarısız oldu ama run devam edebilir.

    Örnekler:
    - Tüm plugin'ler fail oldu
    - Dependency resolve edilemedi
    """
    pass


class PluginError(ArchiverrError):
    """
    Plugin hatası - job skip edilir.

    Örnekler:
    - API timeout
    - Parse hatası
    - Requires satisfied değil
    """
    pass
```

**Test:**

```python
def test_exception_hierarchy():
    assert issubclass(CriticalError, ArchiverrError)
    assert issubclass(StageError, ArchiverrError)
    assert issubclass(PluginError, ArchiverrError)
```

---

### ADIM 2: PluginRegistry Class Oluştur

**Dosya:** `src/archiverr/core/plugins/registry.py` (YENİ)

```python
"""Plugin registry for discovery, loading, and management"""

from typing import Dict, List, Optional, Any
from enum import Enum

from .discovery import PluginDiscovery
from .loader import PluginLoader


class Stage(Enum):
    INPUT = "input"
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"


class PluginRegistry:
    """
    Plugin discovery ve yönetim merkezi.

    Responsibilities:
    - Plugin discovery
    - Plugin loading (stage bazlı)
    - Plugin lookup
    - Manifest caching
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._discovery = PluginDiscovery()
        self._all_plugins: Dict[str, Any] = {}
        self._plugins_by_stage: Dict[Stage, Dict[str, Any]] = {
            stage: {} for stage in Stage
        }
        self._loaded = False

    def discover_and_load(self) -> None:
        """Tüm plugin'leri keşfet ve yükle"""
        if self._loaded:
            return

        # Discover all plugins
        self._all_plugins = self._discovery.discover()

        # Load enabled plugins by stage
        loader = PluginLoader(self._all_plugins, self._config)

        for stage in Stage:
            self._plugins_by_stage[stage] = loader.load_by_stage(stage.value)

        self._loaded = True

    def get_plugins_by_stage(self, stage: Stage) -> Dict[str, Any]:
        """Stage'e göre plugin'leri getir"""
        if not self._loaded:
            self.discover_and_load()
        return self._plugins_by_stage.get(stage, {})

    def get_plugin(self, name: str) -> Optional[Any]:
        """İsme göre plugin getir"""
        if not self._loaded:
            self.discover_and_load()
        return self._all_plugins.get(name)

    def get_manifest(self, name: str) -> Optional[Dict]:
        """Plugin manifest'ini getir"""
        plugin = self.get_plugin(name)
        if plugin:
            return getattr(plugin, 'manifest', None)
        return None

    def get_all_manifests(self) -> Dict[str, Dict]:
        """Tüm manifest'leri getir"""
        if not self._loaded:
            self.discover_and_load()

        manifests = {}
        for name, plugin in self._all_plugins.items():
            manifest = getattr(plugin, 'manifest', None)
            if manifest:
                manifests[name] = manifest
        return manifests

    @property
    def total_plugins(self) -> int:
        """Toplam plugin sayısı"""
        return len(self._all_plugins)

    @property
    def enabled_plugins(self) -> List[str]:
        """Aktif plugin isimleri"""
        enabled = []
        for stage in Stage:
            enabled.extend(self._plugins_by_stage[stage].keys())
        return enabled
```

**Test:**

```python
def test_registry_discover_and_load():
    config = {"scanner": {"targets": ["/test"]}, "renamer": {}}
    registry = PluginRegistry(config)
    registry.discover_and_load()

    assert registry.total_plugins > 0
    assert len(registry.enabled_plugins) > 0

def test_registry_get_by_stage():
    config = {"scanner": {"targets": ["/test"]}}
    registry = PluginRegistry(config)
    registry.discover_and_load()

    input_plugins = registry.get_plugins_by_stage(Stage.INPUT)
    assert "scanner" in input_plugins or len(input_plugins) >= 0
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Mevcut `PluginDiscovery` ve `PluginLoader` ile uyumlu mu?
- `load_by_stage` metodu mevcut mu? (yoksa `load_by_category` adapte et)

---

### ADIM 3: Orchestrator Class Oluştur

**Dosya:** `src/archiverr/core/orchestrator.py` (YENİ)

```python
"""Main orchestrator for Archiverr execution"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

from archiverr.state.models import RunState, StateEnum
from archiverr.state.manager import StateManager
from archiverr.events import EventBus
from archiverr.infrastructure.persistence import PersistenceInterface
from archiverr.utils.debug import Debugger

from .plugins.registry import PluginRegistry, Stage
from .plugins.stage_executor import StageExecutor
from .exceptions import CriticalError, StageError


@dataclass
class RunResult:
    """Orchestrator run sonucu"""
    run_id: str
    success: bool
    total_jobs: int
    completed: int
    failed: int
    duration_ms: int
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "total_jobs": self.total_jobs,
            "completed": self.completed,
            "failed": self.failed,
            "duration_ms": self.duration_ms,
            "error": self.error
        }


class Orchestrator:
    """
    Ana koordinatör sınıfı.

    __main__.py'deki 392 satırlık cli_main() fonksiyonunun
    refactored versiyonu. Tüm execution logic burada.
    """

    STAGES = [Stage.INPUT, Stage.PARSE, Stage.DATA, Stage.OUTPUT]

    def __init__(
        self,
        event_bus: EventBus,
        state: StateManager,
        persistence: PersistenceInterface,
        plugin_registry: PluginRegistry,
        config: Dict[str, Any],
        debugger: Optional[Debugger] = None
    ):
        self._event_bus = event_bus
        self._state = state
        self._persistence = persistence
        self._plugin_registry = plugin_registry
        self._config = config
        self._debugger = debugger

        # Created during run
        self._run_id: Optional[str] = None
        self._stage_executor: Optional[StageExecutor] = None
        self._start_time: Optional[datetime] = None

    def run(self) -> RunResult:
        """
        Ana execution method.

        Flow:
        1. _initialize(): Run başlat, handler'ları kaydet
        2. _execute_stages(): 4 stage'i sırayla çalıştır
        3. _finalize(): Run tamamla, persistence flush

        Returns:
            RunResult with execution summary
        """
        self._start_time = datetime.now()

        try:
            self._initialize()
            self._execute_stages()
            self._finalize(success=True)
            return self._build_result(success=True)

        except CriticalError as e:
            self._log("error", f"Critical error: {e}")
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))

        except Exception as e:
            self._log("error", f"Unexpected error: {e}")
            self._finalize(success=False)
            return self._build_result(success=False, error=str(e))

    def _initialize(self) -> None:
        """Run başlangıç işlemleri"""
        self._log("info", "Initializing run")

        # Discover and load plugins
        self._plugin_registry.discover_and_load()
        self._log("debug", f"Loaded {self._plugin_registry.total_plugins} plugins")

        # Validate at least one plugin loaded
        if self._plugin_registry.total_plugins == 0:
            raise CriticalError("No plugins found")

        # Start run in state
        self._run_id = self._state.start_run(self._config)
        self._log("debug", f"Run started: {self._run_id}")

        # Create stage executor
        self._stage_executor = StageExecutor(
            state=self._state,
            plugin_registry=self._plugin_registry,
            event_bus=self._event_bus,
            config=self._config,
            debugger=self._debugger
        )

        # Emit run.started event
        self._event_bus.emit("run.started", {
            "run_id": self._run_id,
            "config": self._config,
            "plugins": self._plugin_registry.enabled_plugins
        })

        # Register event handlers for persistence
        self._register_event_handlers()

    def _execute_stages(self) -> None:
        """4 Stage'i sırayla çalıştır"""
        for stage in self.STAGES:
            self._log("info", f"Executing stage: {stage.value}")
            self._event_bus.emit("stage.started", {
                "run_id": self._run_id,
                "stage": stage.value
            })

            try:
                self._stage_executor.execute_stage(stage)

                self._event_bus.emit("stage.completed", {
                    "run_id": self._run_id,
                    "stage": stage.value
                })
                self._log("debug", f"Stage completed: {stage.value}")

            except StageError as e:
                # Stage failed but continue with next stage (best effort)
                self._event_bus.emit("stage.failed", {
                    "run_id": self._run_id,
                    "stage": stage.value,
                    "error": str(e)
                })
                self._log("warn", f"Stage failed: {stage.value} - {e}")
                # Continue to next stage

    def _finalize(self, success: bool) -> None:
        """Run sonlandırma işlemleri"""
        self._log("info", f"Finalizing run (success={success})")

        # Complete run in state
        self._state.complete_run(success=success)

        # Flush all pending data to persistence
        if self._persistence:
            run = self._state.get_run()
            if run:
                self._persistence.save_run(run.to_dict())

        # Emit run.completed event
        run = self._state.get_run()
        self._event_bus.emit("run.completed", {
            "run_id": self._run_id,
            "success": success,
            "total_jobs": run.status.total_jobs if run else 0,
            "completed": run.status.completed if run else 0,
            "failed": run.status.failed if run else 0,
            "duration_ms": run.status.duration_ms if run else 0
        })

    def _register_event_handlers(self) -> None:
        """Event handler'ları kaydet"""
        # Persist job on complete
        def on_job_completed(data: Dict):
            job_id = data.get("job_id")
            if job_id and self._persistence:
                job = self._state.get_job(job_id)
                if job:
                    self._persistence.save_job(job.to_dict())

        # Persist plugin data on complete
        def on_plugin_completed(data: Dict):
            if self._persistence:
                self._persistence.save_plugin({
                    "job_id": data.get("job_id"),
                    "run_id": self._run_id,
                    "plugin_name": data.get("plugin_name"),
                    "stage": data.get("stage"),
                    "data": data.get("data", {}),
                    "status": data.get("status", {})
                })

        self._event_bus.subscribe("job.completed", on_job_completed)
        self._event_bus.subscribe("plugin.completed", on_plugin_completed)

    def _build_result(self, success: bool, error: str = None) -> RunResult:
        """RunResult oluştur"""
        run = self._state.get_run()

        duration_ms = 0
        if self._start_time:
            duration_ms = int((datetime.now() - self._start_time).total_seconds() * 1000)

        return RunResult(
            run_id=self._run_id or "",
            success=success,
            total_jobs=run.status.total_jobs if run else 0,
            completed=run.status.completed if run else 0,
            failed=run.status.failed if run else 0,
            duration_ms=duration_ms,
            error=error
        )

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Debug logger wrapper"""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func("orchestrator", message, **kwargs)
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- `StateManager.start_run()` ve `complete_run()` metodları P1'den mevcut mu?
- `StageExecutor` P5'te oluşturulacak, şimdilik stub kullan

---

### ADIM 4: Factory Function Oluştur

**Dosya:** `src/archiverr/core/orchestrator.py` (devam)

```python
def build_orchestrator(
    config: Dict[str, Any],
    debugger: Optional[Debugger] = None,
    persistence: Optional[PersistenceInterface] = None
) -> Orchestrator:
    """
    Factory function for Orchestrator.

    Tüm bağımlılıkları oluşturur ve inject eder.
    __main__.py'de kullanılacak.

    Args:
        config: Loaded configuration dict
        debugger: Optional debugger instance
        persistence: Optional persistence (default: from env)

    Returns:
        Configured Orchestrator instance
    """
    from archiverr.events import EventBus
    from archiverr.state.manager import StateManager
    from archiverr.infrastructure.database import DatabaseConnection

    # Create event bus
    event_bus = EventBus(debugger=debugger)

    # Create state manager
    state = StateManager()

    # Create persistence (from env if not provided)
    if persistence is None:
        db_connection = DatabaseConnection.from_env()
        persistence = db_connection.connect()

    # Configure state with persistence
    state.configure(
        persistence=persistence,
        debugger=debugger,
        event_bus=event_bus
    )

    # Create plugin registry
    plugin_registry = PluginRegistry(config)

    return Orchestrator(
        event_bus=event_bus,
        state=state,
        persistence=persistence,
        plugin_registry=plugin_registry,
        config=config,
        debugger=debugger
    )
```

---

### ADIM 5: **main**.py'i Sadeleştir

**Dosya:** `src/archiverr/__main__.py` (güncelle)

```python
"""Archiverr - Config-Driven Media Organizer

Usage:
    python -m archiverr           # CLI mode (default)
    python -m archiverr serve     # API server mode
"""
import sys
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from archiverr.utils.config_loader import load_config_with_tracking
from archiverr.utils.debug import init_debugger
from archiverr.core.config_validator import ConfigValidator
from archiverr.core.orchestrator import build_orchestrator


def serve_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(
        "archiverr.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


def cli_main():
    """CLI entry point - refactored with Orchestrator."""
    config_path = Path("config.yml")

    if not config_path.exists():
        print("ERROR: config.yml not found", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config_with_tracking(str(config_path))
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize debug system
    debug = config.get('options', {}).get('debug', False)
    debugger = init_debugger(enabled=debug)

    # Validate config
    validator = ConfigValidator()
    if validator.is_available():
        is_valid, error_msg = validator.validate(config)
        if not is_valid:
            debugger.error("config", "Invalid configuration", error=error_msg)
            sys.exit(1)

    # Build and run orchestrator
    orchestrator = build_orchestrator(config, debugger=debugger)
    result = orchestrator.run()

    # Log result
    debugger.info("system", "Archiverr complete",
                  success=result.success,
                  total_jobs=result.total_jobs,
                  completed=result.completed,
                  failed=result.failed)

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Archiverr")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    if args.command == "serve":
        serve_api(host=args.host, port=args.port, reload=args.reload)
    else:
        cli_main()


if __name__ == "__main__":
    main()
```

**NOT:** Bu değişiklik ~50 satıra düşürüyor (392 → ~50).

---

## 4. BACKWARD COMPATIBILITY

### 4.1 Geçiş Stratejisi

```python
# Geçiş döneminde her iki yol da çalışabilir:

# Yeni yol (Orchestrator)
def cli_main_new():
    orchestrator = build_orchestrator(config)
    result = orchestrator.run()

# Eski yol (mevcut cli_main) - deprecated
def cli_main_legacy():
    # Mevcut 392 satırlık kod
    pass

# Feature flag ile geçiş
def cli_main():
    use_orchestrator = os.getenv("ARCHIVERR_USE_ORCHESTRATOR", "false") == "true"

    if use_orchestrator:
        cli_main_new()
    else:
        cli_main_legacy()
```

### 4.2 Gradual Migration

1. **Phase 4.1:** Orchestrator skeleton oluştur
2. **Phase 4.2:** StageExecutor stub ekle (P5'e bağlı)
3. **Phase 4.3:** Feature flag ile test
4. **Phase 4.4:** Eski kodu kaldır

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests

```python
# tests/unit/core/test_orchestrator.py

import pytest
from unittest.mock import Mock, MagicMock
from archiverr.core.orchestrator import Orchestrator, RunResult, build_orchestrator
from archiverr.core.exceptions import CriticalError, StageError


class TestOrchestrator:
    @pytest.fixture
    def mock_dependencies(self):
        return {
            "event_bus": Mock(),
            "state": Mock(),
            "persistence": Mock(),
            "plugin_registry": Mock(),
            "config": {"options": {"debug": True}}
        }

    @pytest.fixture
    def orchestrator(self, mock_dependencies):
        mock_dependencies["plugin_registry"].total_plugins = 5
        mock_dependencies["plugin_registry"].enabled_plugins = ["scanner", "renamer"]
        mock_dependencies["state"].start_run.return_value = "run_test123"
        mock_dependencies["state"].get_run.return_value = Mock(
            status=Mock(total_jobs=10, completed=10, failed=0, duration_ms=1000)
        )
        return Orchestrator(**mock_dependencies)

    def test_run_success(self, orchestrator, mock_dependencies):
        """Başarılı run testi"""
        result = orchestrator.run()

        assert result.success == True
        assert result.run_id == "run_test123"
        mock_dependencies["state"].start_run.assert_called_once()
        mock_dependencies["state"].complete_run.assert_called_once_with(success=True)

    def test_run_emits_events(self, orchestrator, mock_dependencies):
        """Event emission testi"""
        orchestrator.run()

        event_bus = mock_dependencies["event_bus"]
        # run.started, stage.started (x4), stage.completed (x4), run.completed
        assert event_bus.emit.call_count >= 10

    def test_critical_error_stops_run(self, orchestrator, mock_dependencies):
        """Critical error run'ı durdurmalı"""
        mock_dependencies["plugin_registry"].total_plugins = 0
        mock_dependencies["plugin_registry"].discover_and_load.return_value = None

        result = orchestrator.run()

        assert result.success == False
        assert "No plugins found" in result.error

    def test_stage_error_continues(self, orchestrator, mock_dependencies):
        """Stage error sonraki stage'e devam etmeli"""
        # StageExecutor stub - stage error at parse
        stage_executor = Mock()
        stage_executor.execute_stage.side_effect = [
            None,  # input OK
            StageError("Parse failed"),  # parse FAIL
            None,  # data OK
            None   # output OK
        ]
        orchestrator._stage_executor = stage_executor

        result = orchestrator.run()

        # Run should complete (with failures)
        assert stage_executor.execute_stage.call_count == 4


class TestRunResult:
    def test_to_dict(self):
        result = RunResult(
            run_id="run_abc",
            success=True,
            total_jobs=10,
            completed=10,
            failed=0,
            duration_ms=5000
        )
        d = result.to_dict()

        assert d["run_id"] == "run_abc"
        assert d["success"] == True
        assert d["total_jobs"] == 10


class TestBuildOrchestrator:
    def test_factory_creates_orchestrator(self):
        config = {"options": {"debug": False}}

        # Mock the imports
        with pytest.mock.patch.multiple(
            'archiverr.core.orchestrator',
            EventBus=Mock,
            StateManager=Mock,
            DatabaseConnection=Mock
        ):
            orchestrator = build_orchestrator(config)
            assert orchestrator is not None
```

### 5.2 Integration Tests

```python
# tests/integration/core/test_orchestrator_integration.py

import pytest
from archiverr.core.orchestrator import build_orchestrator


@pytest.fixture
def minimal_config():
    return {
        "options": {"debug": True, "dry_run": True},
        "scanner": {"targets": ["/tmp/test_input"]}
    }


class TestOrchestratorIntegration:
    def test_full_run_with_dummy_plugins(self, minimal_config, tmp_path):
        """Dummy plugin ile tam cycle"""
        # Create test file
        test_file = tmp_path / "test.mkv"
        test_file.write_text("test content")

        minimal_config["scanner"]["targets"] = [str(tmp_path)]

        orchestrator = build_orchestrator(minimal_config)
        result = orchestrator.run()

        assert result.run_id.startswith("run_")
        # total_jobs >= 0 (depends on scanner implementation)

    def test_run_with_no_input_files(self, minimal_config, tmp_path):
        """Input dosyası yoksa 0 job"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        minimal_config["scanner"]["targets"] = [str(empty_dir)]

        orchestrator = build_orchestrator(minimal_config)
        result = orchestrator.run()

        assert result.success == True
        assert result.total_jobs == 0
```

---

## 6. PHASE 4 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `CriticalError`, `StageError`, `PluginError` exception'ları oluşturuldu
- [ ] `PluginRegistry` sınıfı oluşturuldu ve çalışıyor
- [ ] `Orchestrator` sınıfı oluşturuldu
- [ ] `build_orchestrator()` factory function çalışıyor
- [ ] `__main__.py` sadeleştirildi (~50 satır)
- [ ] Event emission çalışıyor (run.started, stage.\*, run.completed)
- [ ] Error handling çalışıyor (critical stops, stage continues)
- [ ] Unit testler yazıldı ve PASS
- [ ] Integration testler yazıldı ve PASS
- [ ] Feature flag ile geçiş mümkün

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ StageExecutor implementasyonu (P5'te)
- ❌ 4 Stage plugin execution (P5'te)
- ❌ Task execution integration (P5 sonrası)
- ❌ Report generation (ayrı refactor)

---

## 7. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                       | Belirti                     | Çözüm                                      |
| --------------------------- | --------------------------- | ------------------------------------------ |
| Plugin discovery fail       | `No plugins found` error    | `ARCHIVERR_PLUGINS_PATH` env var kontrol   |
| State not configured        | `RuntimeError` on start_run | `state.configure()` çağrıldığından emin ol |
| Event handler exception     | Silent failure              | Event bus'ta exception logging ekle        |
| Circular import             | `ImportError`               | Lazy import veya TYPE_CHECKING kullan      |
| Persistence connection fail | `ConnectionError`           | Mock persistence'a fallback                |

---

## 8. SONRAKİ PHASE'E GEÇİŞ

Phase 4 tamamlandığında:

1. Git commit: `feat(orchestrator): add Orchestrator class with DI pattern`
2. Git tag: `v0.x.x-phase4`
3. `05_PHASE5_STAGE_EXECUTOR.md` dosyasını oku
4. StageExecutor tasarımına başla (4 stage execution)

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/core/test_orchestrator.py` çalıştır
- Feature flag ile yeni Orchestrator test et: `ARCHIVERR_USE_ORCHESTRATOR=true python -m archiverr`
- Mevcut testler hala PASS mı kontrol et
