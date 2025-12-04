# PHASE 3: PLUGIN SERVICES

```yaml
phase: 3
öncelik: 🟠 YÜKSEK
tahmini_süre: 6-8 saat
bağımlılık: P1 (State Models), P2 (MongoDB)
strateji_belgesi: 02_plugin_system_and_services.md
test_türü: unit + integration
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P1 tamamlandı (RunState, JobState mevcut)
- [ ] P2 tamamlandı (MongoDB persistence çalışıyor)
- [ ] to_dict() metodları doğru format üretiyor

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Plugin Erişim Yöntemi

```python
# MEVCUT: ExecutionContext (core/plugins/context.py)
@dataclass
class ExecutionContext:
    event_bus: EventBus
    execution_id: str
    config: Dict[str, Any]
    dry_run: bool = False
    debug: bool = False
    match_index: Optional[int] = None
    total_matches: Optional[int] = None

# Plugin içinde kullanım:
class TMDbPlugin:
    def process(self, context: ExecutionContext, data: dict) -> dict:
        debugger = get_debugger()  # Global!
        debugger.info("tmdb", "Fetching movie...")

        # State erişimi YOK - sadece data dict geçiyor
        # Event emit: context.event_bus.emit(...)
```

### 1.2 Sorunlar

1. **Global state erişimi:** `get_debugger()` global fonksiyon
2. **State erişimi yok:** Plugin state'i güncelleyemiyor direkt
3. **Config erişimi dağınık:** `context.config` veya global
4. **Event emit karmaşık:** `context.event_bus.emit()`

---

## 2. HEDEF YAPI

### 2.1 PluginServices Interface

```python
@dataclass
class PluginServices:
    """Plugin'lerin erişebileceği TEK interface"""
    state: StateService
    events: EventService
    logger: LoggerService
    config: ConfigService

# Plugin içinde kullanım:
class TMDbPlugin:
    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        services.logger.info("Fetching movie...")

        parsed = services.state.get_plugin_data(job.id, "renamer")
        movie = self.fetch_movie(parsed.get("movie", {}).get("name"))

        services.state.update(job.id, "tmdb.movie", movie)
        services.events.emit("plugin.completed", {"plugin": "tmdb"})

        return PluginResult.success({"movie": movie})
```

### 2.2 Service Interfaces

```python
# StateService - Job ve Run state erişimi
class StateService(Protocol):
    def get_current_job(self) -> JobState: ...
    def get_job(self, job_id: str) -> Optional[JobState]: ...
    def get_all_jobs(self) -> List[JobState]: ...
    def update(self, job_id: str, key: str, value: Any) -> None: ...
    def get_run(self) -> RunState: ...
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Dict: ...

# EventService - Event emit ve subscribe
class EventService(Protocol):
    def emit(self, event: str, data: Dict = None) -> None: ...
    def subscribe(self, event: str, handler: Callable) -> None: ...

# LoggerService - Structured logging
class LoggerService(Protocol):
    def debug(self, message: str, **kwargs) -> None: ...
    def info(self, message: str, **kwargs) -> None: ...
    def warn(self, message: str, **kwargs) -> None: ...
    def error(self, message: str, **kwargs) -> None: ...

# ConfigService - Config erişimi
class ConfigService(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def get_plugin(self, plugin_name: str) -> Dict: ...
    def get_option(self, option: str, default: Any = None) -> Any: ...
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: Service Protocol'leri Tanımla

**Dosya:** `src/archiverr/core/services/protocols.py` (YENİ)

```python
"""Service protocol definitions for Plugin dependency injection"""

from typing import Protocol, Dict, Any, List, Optional, Callable
from archiverr.state.models import JobState, RunState


class StateService(Protocol):
    """State management service protocol"""

    def get_current_job(self) -> JobState:
        """Get currently executing job"""
        ...

    def get_job(self, job_id: str) -> Optional[JobState]:
        """Get job by ID"""
        ...

    def get_all_jobs(self) -> List[JobState]:
        """Get all jobs in current run"""
        ...

    def update(self, job_id: str, key: str, value: Any) -> None:
        """Update job state at given key path (dot notation)"""
        ...

    def get_run(self) -> RunState:
        """Get current run state"""
        ...

    def get_plugin_data(self, job_id: str, plugin_name: str) -> Dict[str, Any]:
        """Get plugin result data for a job"""
        ...


class EventService(Protocol):
    """Event bus service protocol"""

    def emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit an event"""
        ...

    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe to an event"""
        ...


class LoggerService(Protocol):
    """Structured logging service protocol"""

    def debug(self, message: str, **kwargs) -> None: ...
    def info(self, message: str, **kwargs) -> None: ...
    def warn(self, message: str, **kwargs) -> None: ...
    def error(self, message: str, **kwargs) -> None: ...


class ConfigService(Protocol):
    """Configuration service protocol"""

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by key (dot notation)"""
        ...

    def get_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Get plugin configuration"""
        ...

    def get_option(self, option: str, default: Any = None) -> Any:
        """Get from options section"""
        ...
```

**Test:**

```python
def test_protocol_compliance():
    """Verify protocol is properly defined"""
    from archiverr.core.services.protocols import StateService
    assert hasattr(StateService, 'get_current_job')
    assert hasattr(StateService, 'update')
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Python 3.8+ kullanıyorsan Protocol, değilse ABC
- Mevcut codebase'deki benzer pattern'leri incele

---

### ADIM 2: Service Implementasyonları

**Dosya:** `src/archiverr/core/services/state_service.py`

```python
"""StateService implementation that wraps StateManager"""

from typing import Any, Dict, List, Optional
from archiverr.state.models import JobState, RunState
from archiverr.state.manager import StateManager


class StateServiceImpl:
    """StateService implementation"""

    def __init__(self, state_manager: StateManager, current_job_id: Optional[str] = None):
        self._manager = state_manager
        self._current_job_id = current_job_id

    def set_current_job(self, job_id: str) -> None:
        """Set current job context (called by executor)"""
        self._current_job_id = job_id

    def get_current_job(self) -> JobState:
        if not self._current_job_id:
            raise RuntimeError("No current job set")
        job = self._manager.get_job_by_id(self._current_job_id)
        if not job:
            raise RuntimeError(f"Job not found: {self._current_job_id}")
        return job

    def get_job(self, job_id: str) -> Optional[JobState]:
        return self._manager.get_job_by_id(job_id)

    def get_all_jobs(self) -> List[JobState]:
        return self._manager.get_all_jobs()

    def update(self, job_id: str, key: str, value: Any) -> None:
        """Update job state using dot notation path"""
        self._manager.update_job_field(job_id, key, value)

    def get_run(self) -> RunState:
        run = self._manager.get_run()
        if not run:
            raise RuntimeError("No active run")
        return run

    def get_plugin_data(self, job_id: str, plugin_name: str) -> Dict[str, Any]:
        job = self.get_job(job_id)
        if not job:
            return {}
        return job.plugins.get(plugin_name, {})
```

**Dosya:** `src/archiverr/core/services/event_service.py`

```python
"""EventService implementation that wraps EventBus"""

from typing import Any, Callable, Dict, Optional
from archiverr.events import EventBus


class EventServiceImpl:
    """EventService implementation"""

    def __init__(self, event_bus: EventBus):
        self._bus = event_bus

    def emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._bus.emit(event, data or {})

    def subscribe(self, event: str, handler: Callable) -> None:
        self._bus.subscribe(event, handler)
```

**Dosya:** `src/archiverr/core/services/logger_service.py`

```python
"""LoggerService implementation that wraps Debugger"""

from archiverr.utils.debug import Debugger


class LoggerServiceImpl:
    """LoggerService implementation"""

    def __init__(self, debugger: Debugger, plugin_name: str = "plugin"):
        self._debugger = debugger
        self._plugin_name = plugin_name

    def debug(self, message: str, **kwargs) -> None:
        self._debugger.debug(self._plugin_name, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._debugger.info(self._plugin_name, message, **kwargs)

    def warn(self, message: str, **kwargs) -> None:
        self._debugger.warn(self._plugin_name, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._debugger.error(self._plugin_name, message, **kwargs)
```

**Dosya:** `src/archiverr/core/services/config_service.py`

```python
"""ConfigService implementation"""

from typing import Any, Dict


class ConfigServiceImpl:
    """ConfigService implementation"""

    def __init__(self, config: Dict[str, Any]):
        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value using dot notation"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def get_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Get plugin configuration"""
        return self._config.get(plugin_name, {})

    def get_option(self, option: str, default: Any = None) -> Any:
        """Get from options section"""
        return self._config.get('options', {}).get(option, default)
```

---

### ADIM 3: PluginServices Dataclass

**Dosya:** `src/archiverr/core/services/__init__.py`

```python
"""Plugin Services - Dependency Injection for Plugins"""

from dataclasses import dataclass
from .protocols import StateService, EventService, LoggerService, ConfigService
from .state_service import StateServiceImpl
from .event_service import EventServiceImpl
from .logger_service import LoggerServiceImpl
from .config_service import ConfigServiceImpl


@dataclass
class PluginServices:
    """
    Tek interface for plugin dependency injection.

    Plugin'ler sadece bu interface üzerinden sistem kaynaklarına erişir.
    Global fonksiyonlar (get_debugger) ve doğrudan state erişimi YASAK.
    """
    state: StateService
    events: EventService
    logger: LoggerService
    config: ConfigService


def create_plugin_services(
    state_manager,
    event_bus,
    debugger,
    config: dict,
    plugin_name: str = "plugin"
) -> PluginServices:
    """Factory function to create PluginServices"""
    return PluginServices(
        state=StateServiceImpl(state_manager),
        events=EventServiceImpl(event_bus),
        logger=LoggerServiceImpl(debugger, plugin_name),
        config=ConfigServiceImpl(config)
    )


# Backward compatibility - ExecutionContext'ten PluginServices'e adapter
def services_from_context(context, state_manager) -> PluginServices:
    """
    DEPRECATED: ExecutionContext'ten PluginServices oluştur.
    Migration döneminde kullanılacak.
    """
    from archiverr.utils.debug import get_debugger
    return PluginServices(
        state=StateServiceImpl(state_manager),
        events=EventServiceImpl(context.event_bus),
        logger=LoggerServiceImpl(get_debugger(), "plugin"),
        config=ConfigServiceImpl(context.config)
    )
```

---

### ADIM 4: Plugin Base Class Güncelle

**Dosya:** `src/archiverr/plugins/base.py` (varsa güncelle, yoksa oluştur)

```python
"""Base plugin class with new execute signature"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from archiverr.state.models import JobState
from archiverr.core.services import PluginServices


class PluginStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PluginResult:
    """Plugin execution result"""
    status: PluginStatus
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @classmethod
    def success(cls, data: Dict[str, Any] = None) -> 'PluginResult':
        return cls(status=PluginStatus.SUCCESS, data=data or {})

    @classmethod
    def failed(cls, error: str, data: Dict[str, Any] = None) -> 'PluginResult':
        return cls(status=PluginStatus.FAILED, error=error, data=data)

    @classmethod
    def skipped(cls, reason: str = "") -> 'PluginResult':
        return cls(status=PluginStatus.SKIPPED, error=reason)


class BasePlugin(ABC):
    """
    Base class for all plugins.

    Two execution modes:
    - per_job: execute(job, services) called for each job
    - per_run: execute_run(services) called once per run
    """

    @property
    def name(self) -> str:
        """Plugin name from manifest"""
        return getattr(self, '_name', self.__class__.__name__.lower())

    @property
    def stage(self) -> str:
        """Plugin stage from manifest"""
        return getattr(self, '_stage', 'data')

    @property
    def mode(self) -> str:
        """Execution mode: per_job or per_run"""
        # Default: input stage = per_run, others = per_job
        return 'per_run' if self.stage == 'input' else 'per_job'

    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        """
        Execute plugin for a single job (per_job mode).

        Override this for parse, data, output stage plugins.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute() for per_job mode"
        )

    def execute_run(self, services: PluginServices) -> PluginResult:
        """
        Execute plugin for entire run (per_run mode).

        Override this for input stage plugins (scanner, etc.)
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute_run() for per_run mode"
        )
```

**🔍 İMPLEMENTASYON KONTROLÜ:**

- Mevcut plugin base class'ı incele (`plugins/base.py` varsa)
- Yeni signature'a geçiş için adapter kullan (LegacyPluginAdapter)

---

### ADIM 5: Executor'da Services Entegrasyonu

**Bu adım P4 (Orchestrator) ile birlikte yapılabilir.**

Şimdilik sadece interface hazır, entegrasyon P4'te.

---

## 4. BACKWARD COMPATIBILITY

### 4.1 Mevcut Plugin'lerle Uyumluluk

```python
# Adapter for old-style plugins

class LegacyPluginAdapter:
    """Wraps old-style plugin to work with new PluginServices"""

    def __init__(self, legacy_plugin):
        self._plugin = legacy_plugin

    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        # Create old-style context from services
        from archiverr.core.plugins.context import ExecutionContext
        context = ExecutionContext(
            event_bus=services.events._bus,
            execution_id=services.state.get_run().id,
            config=services.config._config,
            dry_run=services.config.get_option('dry_run', False),
            debug=services.config.get_option('debug', False)
        )

        # Convert job to old data format
        data = {"input": {"path": job.input.value}}

        # Call old process method
        try:
            result = self._plugin.process(context, data)
            return PluginResult.success(result)
        except Exception as e:
            return PluginResult.failed(str(e))
```

**NOT:** Adapter pattern geçiş dönemi için. Plugin'ler zamanla yeni signature'a migrate edilecek.

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests

```python
# tests/unit/services/test_state_service.py

from unittest.mock import Mock, MagicMock
from archiverr.core.services import StateServiceImpl
from archiverr.state.models import JobState, RunState

class TestStateService:
    def test_get_current_job(self):
        mock_manager = Mock()
        mock_job = JobState(index=0, run_id="run_test")
        mock_manager.get_job_by_id.return_value = mock_job

        service = StateServiceImpl(mock_manager, current_job_id="job_run_test_0")
        job = service.get_current_job()

        assert job.index == 0
        mock_manager.get_job_by_id.assert_called_with("job_run_test_0")

    def test_update_calls_manager(self):
        mock_manager = Mock()
        service = StateServiceImpl(mock_manager)

        service.update("job_1", "plugins.tmdb.movie", {"title": "Test"})

        mock_manager.update_job_field.assert_called_once()

# tests/unit/services/test_config_service.py

class TestConfigService:
    def test_dot_notation(self):
        config = {"options": {"debug": True, "nested": {"value": 42}}}
        service = ConfigServiceImpl(config)

        assert service.get("options.debug") == True
        assert service.get("options.nested.value") == 42
        assert service.get("nonexistent", "default") == "default"

    def test_get_plugin(self):
        config = {"tmdb": {"api_key": "xxx"}}
        service = ConfigServiceImpl(config)

        plugin_config = service.get_plugin("tmdb")
        assert plugin_config["api_key"] == "xxx"
```

### 5.2 Integration Tests

```python
# tests/integration/services/test_plugin_services.py

def test_create_plugin_services():
    from archiverr.core.services import create_plugin_services
    from archiverr.state.manager import StateManager
    from archiverr.events import EventBus
    from archiverr.utils.debug import init_debugger

    state_manager = StateManager()
    event_bus = EventBus()
    debugger = init_debugger(enabled=True)
    config = {"options": {"debug": True}}

    services = create_plugin_services(
        state_manager, event_bus, debugger, config, "test_plugin"
    )

    assert services.state is not None
    assert services.events is not None
    assert services.logger is not None
    assert services.config is not None

def test_services_workflow():
    """Full workflow with PluginServices"""
    # Setup...
    services = create_plugin_services(...)

    # Start run
    services.state._manager.start_run({})

    # Create job
    job = services.state._manager.create_job("/test.mkv")

    # Update state
    services.state.update(job.id, "plugins.test.data", {"key": "value"})

    # Verify
    updated_job = services.state.get_job(job.id)
    assert updated_job.plugins.get("test", {}).get("data") == {"key": "value"}
```

---

## 6. PHASE 3 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] Service protocol'leri tanımlandı
- [ ] StateServiceImpl çalışıyor
- [ ] EventServiceImpl çalışıyor
- [ ] LoggerServiceImpl çalışıyor
- [ ] ConfigServiceImpl çalışıyor
- [ ] PluginServices dataclass oluşturuldu
- [ ] create_plugin_services factory çalışıyor
- [ ] BasePlugin yeni signature ile güncellendi
- [ ] PluginResult dataclass hazır
- [ ] LegacyPluginAdapter (opsiyonel) hazır
- [ ] Unit testler PASS
- [ ] Mevcut testler PASS (regression)

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ Executor entegrasyonu (P4'te)
- ❌ Plugin migration (plugin bazında)
- ❌ Mevcut plugin'lerin güncellenmesi

---

## 7. SONRAKİ PHASE'E GEÇİŞ

Phase 3 tamamlandığında:

1. Git commit: `feat(services): add PluginServices dependency injection`
2. Git tag: `v0.x.x-phase3`
3. `04_PHASE4_ORCHESTRATOR.md` dosyasını oku
4. Orchestrator tasarımına başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/services/` çalıştır
- PluginServices factory çalışıyor mu test et
- Mevcut plugin'ler adapter ile çalışıyor mu kontrol et
