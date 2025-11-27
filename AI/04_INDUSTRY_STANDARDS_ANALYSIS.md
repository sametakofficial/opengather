# 🏭 ENDÜSTRİ STANDARTLARI ANALİZ RAPORU

> **Tarih**: 2025-11-27  
> **Analiz Tipi**: Kapsamlı Internet Araştırması + Kod Analizi  
> **Amaç**: Archiverr projesini endüstri standartlarına uygun hale getirmek için detaylı analiz

---

## 📋 İÇİNDEKİLER

1. [Executive Summary](#1-executive-summary)
2. [Python Proje Yapısı Standartları](#2-python-proje-yapısı-standartları)
3. [FastAPI Best Practices Analizi](#3-fastapi-best-practices-analizi)
4. [Plugin Sistemi Analizi](#4-plugin-sistemi-analizi)
5. [Test Stratejisi Analizi](#5-test-stratejisi-analizi)
6. [Configuration Management](#6-configuration-management)
7. [Logging & Monitoring](#7-logging--monitoring)
8. [Security Analizi](#8-security-analizi)
9. [Mevcut Planların Değerlendirmesi](#9-mevcut-planların-değerlendirmesi)
10. [Güncellenmiş Refactoring Planı](#10-güncellenmiş-refactoring-planı)

---

## 1. EXECUTIVE SUMMARY

### Genel Değerlendirme

| Kategori | Mevcut | Hedef | Öncelik |
|----------|--------|-------|---------|
| **Proje Yapısı** | 5/10 | 9/10 | 🔴 Kritik |
| **Plugin Sistemi** | 4/10 | 9/10 | 🔴 Kritik |
| **Test Coverage** | 2/10 | 8/10 | 🔴 Kritik |
| **API Tasarımı** | 5/10 | 9/10 | 🟠 Yüksek |
| **Configuration** | 4/10 | 9/10 | 🟠 Yüksek |
| **Security** | 3/10 | 9/10 | 🔴 Kritik |
| **Documentation** | 5/10 | 8/10 | 🟡 Orta |
| **Logging/Monitoring** | 3/10 | 8/10 | 🟡 Orta |

### Ana Eksiklikler (Araştırma Sonucu)

1. **`pyproject.toml` YOK** - Modern Python standartı (PEP 517/518/621)
2. **Plugin SDK YOK** - Jellyfin/Stremio gibi profesyonel plugin geliştirme altyapısı
3. **Type Hints Eksik** - mypy strict mode uyumsuzluğu
4. **Pre-commit Hooks YOK** - Code quality automation eksik
5. **Structured Logging YOK** - Production-ready logging sistemi eksik
6. **WebSocket/SSE YOK** - Real-time progress monitoring eksik
7. **Background Task Queue YOK** - Long-running tasks için ARQ/Celery eksik
8. **Rate Limiting YOK** - API abuse koruması eksik
9. **Health Checks YOK** - Kubernetes-ready liveness/readiness probes eksik
10. **Metrics/Tracing YOK** - Observability (Prometheus/OpenTelemetry) eksik

---

## 2. PYTHON PROJE YAPISI STANDARTLARI

### 2.1 Araştırma Kaynakları

- **PyOpenSci Python Package Guide** (https://www.pyopensci.org/python-package-guide/)
- **Python Packaging User Guide** (https://packaging.python.org/)
- **Hynek Schlawack Blog** (https://hynek.me/articles/testing-packaging/)

### 2.2 Mevcut Durum vs Standart

#### ❌ Mevcut (Eski Yöntem)
```
archiverr/
├── setup.py          # ❌ Deprecated, PEP 517 öncesi
├── requirements.txt  # ✅ OK ama eksik
├── src/archiverr/    # ✅ src layout doğru
└── tests/            # ⚠️ Kısmen doğru
```

#### ✅ Endüstri Standardı (2024+)
```
archiverr/
├── pyproject.toml        # 🆕 Tek config dosyası (PEP 621)
├── src/archiverr/
│   ├── __init__.py
│   ├── py.typed          # 🆕 PEP 561 marker
│   └── ...
├── tests/
│   ├── conftest.py
│   └── ...
├── docs/
├── .pre-commit-config.yaml  # 🆕 Code quality automation
├── .github/
│   └── workflows/
│       ├── ci.yml           # 🆕 CI/CD
│       └── release.yml
└── README.md
```

### 2.3 `pyproject.toml` Eksikliği (KRİTİK)

**Kaynak**: PEP 517, PEP 518, PEP 621 (https://packaging.python.org/en/latest/guides/modernize-setup-py-project/)

```toml
# ÖNERİLEN pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "archiverr"
version = "2.1.0"
description = "Plugin-agnostic media metadata and renaming automation tool"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [
    {name = "Your Name", email = "your@email.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Video",
]
keywords = ["media", "metadata", "renaming", "automation", "plex", "jellyfin"]

dependencies = [
    "pyyaml>=6.0.1",
    "jinja2>=3.1.2",
    "requests>=2.31.0",
    "pydantic>=2.4.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
api = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "motor>=3.3.0",
]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.25.0",
    "mypy>=1.5.0",
    "ruff>=0.1.0",
    "pre-commit>=3.5.0",
]

[project.scripts]
archiverr = "archiverr.__main__:main"

[project.urls]
Homepage = "https://github.com/yourusername/archiverr"
Documentation = "https://archiverr.readthedocs.io"
Repository = "https://github.com/yourusername/archiverr"
Issues = "https://github.com/yourusername/archiverr/issues"

[tool.ruff]
target-version = "py310"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.isort]
known-first-party = ["archiverr"]

[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "slow: Slow tests",
]

[tool.coverage.run]
source = ["src/archiverr"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

---

## 3. FASTAPI BEST PRACTICES ANALİZİ

### 3.1 Araştırma Kaynakları

- **zhanymkanov/fastapi-best-practices** (GitHub, 5k+ stars)
- **Netflix Dispatch** (Production FastAPI)
- **FastAPI Official Docs**

### 3.2 Proje Yapısı Karşılaştırması

#### Netflix Dispatch Yapısı (Referans)
```
src/
├── auth/
│   ├── router.py
│   ├── schemas.py
│   ├── models.py
│   ├── service.py
│   ├── dependencies.py
│   ├── exceptions.py
│   ├── config.py
│   ├── constants.py
│   └── utils.py
├── posts/
│   └── (aynı yapı)
├── config.py          # Global configs
├── database.py        # DB connection
├── exceptions.py      # Global exceptions
└── main.py
```

#### Mevcut Archiverr Yapısı (EKSİK)
```
src/archiverr/api/v1/
├── executions/
│   ├── router.py      # ✅
│   └── schemas.py     # ✅
│   ├── service.py     # ❌ EKSİK
│   ├── exceptions.py  # ❌ EKSİK
│   └── constants.py   # ❌ EKSİK
```

### 3.3 Eksik Best Practices

#### 1. Module-Level Exceptions (EKSİK)
**Kaynak**: Netflix Dispatch pattern

```python
# api/v1/executions/exceptions.py - ÖNERİLEN
from fastapi import HTTPException, status

class ExecutionException(HTTPException):
    """Base exception for execution module"""
    pass

class ExecutionNotFoundError(ExecutionException):
    def __init__(self, execution_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{execution_id}' not found"
        )

class ExecutionAlreadyRunningError(ExecutionException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="An execution is already in progress"
        )

class ExecutionFailedError(ExecutionException):
    def __init__(self, reason: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {reason}"
        )
```

#### 2. Service Layer (EKSİK)
**Sorun**: Router'lar doğrudan DB erişimi yapıyor

```python
# api/v1/executions/service.py - ÖNERİLEN
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

class ExecutionService:
    """Business logic for executions"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._collection = db["executions"]
    
    async def list_executions(
        self, 
        limit: int = 20, 
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[dict]:
        query = {}
        if status:
            query["status"] = status
        
        cursor = self._collection.find(query)
        cursor = cursor.sort("started_at", -1)
        cursor = cursor.skip(offset).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_execution(self, execution_id: str) -> Optional[dict]:
        exec_id = self._normalize_id(execution_id)
        return await self._collection.find_one({"_id": exec_id})
    
    async def start_execution(self, config: dict) -> str:
        # Business logic here
        ...
    
    @staticmethod
    def _normalize_id(execution_id: str) -> str:
        if not execution_id.startswith("exec_"):
            return f"exec_{execution_id}"
        return execution_id
```

#### 3. Async Test Client (EKSİK)
**Kaynak**: FastAPI Best Practices

```python
# tests/conftest.py - ÖNERİLEN
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from archiverr.api.main import app

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

# Test kullanımı
@pytest.mark.asyncio
async def test_list_executions(async_client):
    response = await async_client.get("/api/v1/executions/")
    assert response.status_code == 200
```

#### 4. Pydantic Custom Base Model (EKSİK)
**Kaynak**: FastAPI Best Practices

```python
# api/schemas/base.py - ÖNERİLEN
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict
from fastapi.encoders import jsonable_encoder

def datetime_to_iso(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.isoformat()

class BaseSchema(BaseModel):
    """Custom base schema with common functionality"""
    
    model_config = ConfigDict(
        json_encoders={datetime: datetime_to_iso},
        populate_by_name=True,
        from_attributes=True,
    )
    
    def to_dict(self) -> dict:
        """Return dict with only serializable fields"""
        return jsonable_encoder(self.model_dump())
```

---

## 4. PLUGIN SİSTEMİ ANALİZİ

### 4.1 Araştırma Kaynakları

- **Jellyfin Plugin Template** (https://github.com/jellyfin/jellyfin-plugin-template)
- **Stremio Addon SDK** (https://github.com/Stremio/stremio-addon-sdk)
- **Home Assistant Integration Architecture** (https://developers.home-assistant.io/docs/architecture_components/)
- **pluggy library** (pytest plugin framework)

### 4.2 Mevcut Plugin Sistemi Eksiklikleri

#### Mevcut Yapı (BASIT)
```python
# plugins/base.py - Mevcut
class BasePlugin(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = None
        self.category = None
        self._metadata = {}
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        pass
```

**EKSİKLER:**
1. ❌ Plugin lifecycle hooks (startup, shutdown, suspend, resume)
2. ❌ Plugin SDK / API client
3. ❌ Plugin configuration schema validation
4. ❌ Plugin dependency injection
5. ❌ Plugin versioning & compatibility checking
6. ❌ Plugin events/signals system
7. ❌ Plugin state management
8. ❌ Plugin testing utilities
9. ❌ Plugin documentation generator
10. ❌ Plugin marketplace/registry support

### 4.3 Endüstri Standardı Plugin Sistemi

#### Jellyfin Plugin Model
```csharp
// Jellyfin'den ilham alınarak Python'a adapte edilmiş
public interface IPlugin
{
    Guid Id { get; }
    string Name { get; }
    string Description { get; }
    Version Version { get; }
    
    void OnStartup();
    void OnShutdown();
    void OnConfigurationChanged();
}
```

#### ÖNERİLEN: Archiverr Plugin SDK

```python
# src/archiverr/sdk/__init__.py

"""
Archiverr Plugin SDK

Provides utilities and base classes for plugin development.

Example plugin:
    
    from archiverr.sdk import (
        BasePlugin, 
        OutputPlugin,
        PluginConfig,
        PluginContext,
        hook,
    )
    
    class MyPluginConfig(PluginConfig):
        api_key: str
        timeout: int = 30
    
    class MyPlugin(OutputPlugin[MyPluginConfig]):
        name = "my_plugin"
        version = "1.0.0"
        
        @hook
        async def on_startup(self):
            self.logger.info("Plugin started")
        
        async def execute(self, context: PluginContext) -> PluginResult:
            # Plugin logic here
            return PluginResult(success=True, data={...})
"""

from .base import (
    BasePlugin,
    InputPlugin,
    OutputPlugin,
)
from .config import PluginConfig
from .context import PluginContext
from .result import PluginResult, PluginError
from .hooks import hook, HookSpec
from .testing import PluginTestCase, MockContext
from .schema import SchemaGenerator

__all__ = [
    "BasePlugin",
    "InputPlugin", 
    "OutputPlugin",
    "PluginConfig",
    "PluginContext",
    "PluginResult",
    "PluginError",
    "hook",
    "HookSpec",
    "PluginTestCase",
    "MockContext",
    "SchemaGenerator",
]
```

#### Plugin Lifecycle Hooks (ÖNERİLEN)

```python
# src/archiverr/sdk/base.py

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List
from pydantic import BaseModel
import logging

ConfigT = TypeVar("ConfigT", bound=BaseModel)

class PluginLifecycle(ABC):
    """Plugin lifecycle hooks"""
    
    async def on_load(self) -> None:
        """Called when plugin is loaded"""
        pass
    
    async def on_startup(self) -> None:
        """Called when plugin is started"""
        pass
    
    async def on_shutdown(self) -> None:
        """Called when plugin is shutting down"""
        pass
    
    async def on_config_changed(self, old_config, new_config) -> None:
        """Called when configuration changes"""
        pass


class BasePlugin(PluginLifecycle, ABC, Generic[ConfigT]):
    """
    Enhanced base plugin with full SDK support.
    
    Features:
    - Generic config type with Pydantic validation
    - Lifecycle hooks
    - Built-in logger
    - State management
    - Event subscription
    """
    
    # Class-level metadata (override in subclass)
    name: str = "base_plugin"
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    category: str = "unknown"
    
    # Dependencies
    depends_on: List[str] = []
    expects: List[str] = []
    
    def __init__(self, config: ConfigT, context: "PluginContext"):
        self._config = config
        self._context = context
        self._logger = logging.getLogger(f"archiverr.plugins.{self.name}")
        self._state: dict = {}
    
    @property
    def config(self) -> ConfigT:
        return self._config
    
    @property
    def logger(self) -> logging.Logger:
        return self._logger
    
    @property
    def context(self) -> "PluginContext":
        return self._context
    
    @abstractmethod
    async def execute(self, match_data: dict) -> "PluginResult":
        """Execute plugin logic"""
        raise NotImplementedError
    
    # State management
    def get_state(self, key: str, default=None):
        return self._state.get(key, default)
    
    def set_state(self, key: str, value):
        self._state[key] = value
    
    # Event helpers
    async def emit_event(self, event_name: str, data: dict):
        await self._context.event_bus.emit(
            f"plugin.{self.name}.{event_name}",
            data
        )
    
    # Validation helpers
    def validate_expects(self, match_data: dict) -> bool:
        """Check if required data exists in match_data"""
        for path in self.expects:
            if not self._resolve_path(match_data, path):
                return False
        return True
    
    @staticmethod
    def _resolve_path(data: dict, path: str):
        """Resolve dot-notation path in dict"""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
```

#### Plugin Context (ÖNERİLEN)

```python
# src/archiverr/sdk/context.py

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from archiverr.events.bus import EventBus
    from archiverr.state.manager import GlobalStateManager

@dataclass
class PluginContext:
    """
    Context object passed to plugins.
    
    Provides access to:
    - Event bus for emitting/subscribing to events
    - State manager for accessing global state
    - Match index and input path
    - Previous plugin results
    - Logging utilities
    """
    
    event_bus: "EventBus"
    state_manager: "GlobalStateManager"
    
    # Current execution context
    execution_id: str
    match_index: int
    input_path: str
    
    # Results from previous plugins
    previous_results: Dict[str, Any]
    
    # Dry run mode
    dry_run: bool = False
    debug: bool = False
    
    def get_plugin_result(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get result from a specific plugin"""
        return self.previous_results.get(plugin_name)
    
    def has_plugin_result(self, plugin_name: str) -> bool:
        """Check if plugin has produced result"""
        result = self.previous_results.get(plugin_name, {})
        return result.get("status", {}).get("success", False)
```

#### Plugin Result (ÖNERİLEN)

```python
# src/archiverr/sdk/result.py

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

@dataclass
class PluginError:
    """Structured plugin error"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    recoverable: bool = False

@dataclass
class PluginResult:
    """
    Standardized plugin result.
    
    All plugins must return this type for consistency.
    """
    
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[PluginError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Timing
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    # Metadata
    cache_hit: bool = False
    api_calls: int = 0
    
    @property
    def duration_ms(self) -> Optional[int]:
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds() * 1000)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": {
                "success": self.success,
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                "duration_ms": self.duration_ms,
                "cache_hit": self.cache_hit,
                "api_calls": self.api_calls,
            },
            "errors": [
                {"code": e.code, "message": e.message, "details": e.details}
                for e in self.errors
            ],
            "warnings": self.warnings,
            **self.data,
        }

    @classmethod
    def error(cls, code: str, message: str, **kwargs) -> "PluginResult":
        """Create error result"""
        return cls(
            success=False,
            errors=[PluginError(code=code, message=message, **kwargs)]
        )
```

#### Plugin Testing Utilities (ÖNERİLEN)

```python
# src/archiverr/sdk/testing.py

from typing import Dict, Any, Optional, Type
from unittest.mock import MagicMock, AsyncMock
import pytest

class MockContext:
    """Mock context for testing plugins"""
    
    def __init__(
        self,
        execution_id: str = "test_exec",
        match_index: int = 0,
        input_path: str = "/test/file.mkv",
        previous_results: Optional[Dict[str, Any]] = None,
        dry_run: bool = True,
        debug: bool = True,
    ):
        self.execution_id = execution_id
        self.match_index = match_index
        self.input_path = input_path
        self.previous_results = previous_results or {}
        self.dry_run = dry_run
        self.debug = debug
        
        self.event_bus = AsyncMock()
        self.state_manager = MagicMock()
    
    def get_plugin_result(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        return self.previous_results.get(plugin_name)
    
    def has_plugin_result(self, plugin_name: str) -> bool:
        result = self.previous_results.get(plugin_name, {})
        return result.get("status", {}).get("success", False)


class PluginTestCase:
    """
    Base test case for plugin testing.
    
    Usage:
        class TestMyPlugin(PluginTestCase):
            plugin_class = MyPlugin
            
            @pytest.fixture
            def config(self):
                return {"api_key": "test", "timeout": 5}
            
            @pytest.mark.asyncio
            async def test_execute_success(self, plugin, mock_context):
                result = await plugin.execute({"renamer": {...}})
                assert result.success
    """
    
    plugin_class: Type = None
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Override to provide plugin config"""
        return {}
    
    @pytest.fixture
    def mock_context(self) -> MockContext:
        return MockContext()
    
    @pytest.fixture
    def plugin(self, config, mock_context):
        """Create plugin instance"""
        if self.plugin_class is None:
            pytest.skip("plugin_class not defined")
        return self.plugin_class(config, mock_context)
```

---

## 5. TEST STRATEJİSİ ANALİZİ

### 5.1 Araştırma Kaynakları

- **pytest Best Practices** (Real Python, NerdWallet)
- **Testing APIs with Pytest** (CodiLime)
- **Python Testing with pytest** (O'Reilly Book)

### 5.2 Mevcut Test Durumu

```
tests/
├── conftest.py (3KB)
├── test_api.py (5KB)              # 16 tests
├── test_state_management.py (15KB) # 26 tests
├── test_persistence.py (12KB)
├── test_full_pipeline.py (11KB)   # ⚠️ Plugin-dependent
├── test_integration.py (14KB)     # ⚠️ Plugin-dependent
├── test_execution_service.py (13KB)
├── test_real_api.py (15KB)        # ⚠️ Real HTTP
├── unit/                          # 45 tests
│   ├── core/
│   ├── state/
│   └── api/
├── integration/                   # ❌ Boş
└── e2e/                          # ❌ Boş
```

**TOPLAM**: ~87 test, ancak yapı karışık

### 5.3 Test Piramidi (Eksik)

```
          /\
         /  \         E2E Tests (10%)
        /----\        - Full workflow tests
       /      \       - Real API calls (mocked)
      /--------\      
     /          \     Integration Tests (20%)
    /------------\    - Service interactions
   /              \   - Database tests
  /----------------\  
 /                  \ Unit Tests (70%)
/--------------------\
                      - Plugin-agnostic
                      - Fast (<1s per test)
                      - No external deps
```

### 5.4 ÖNERİLEN Test Yapısı

```
tests/
├── conftest.py              # Global fixtures
├── unit/
│   ├── conftest.py          # Unit test fixtures
│   ├── core/
│   │   ├── test_discovery.py
│   │   ├── test_loader.py
│   │   ├── test_resolver.py
│   │   └── test_executor.py
│   ├── state/
│   │   └── test_manager.py
│   ├── api/
│   │   ├── test_health.py
│   │   ├── test_executions.py
│   │   └── test_matches.py
│   └── sdk/
│       ├── test_plugin_base.py
│       ├── test_plugin_result.py
│       └── test_plugin_context.py
├── integration/
│   ├── conftest.py          # Integration fixtures
│   ├── test_execution_flow.py
│   ├── test_mongodb.py
│   └── test_api_server.py
├── e2e/
│   ├── conftest.py          # E2E fixtures
│   └── test_full_workflow.py
└── plugins/                 # Plugin-specific tests (AYRI)
    ├── tmdb/
    │   └── test_tmdb_plugin.py
    ├── renamer/
    │   └── test_parser.py
    └── scanner/
        └── test_scanner.py
```

### 5.5 Pytest Markers (Güncelleme)

```python
# pytest.ini veya pyproject.toml
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (may require database)",
    "e2e: End-to-end tests (full system)",
    "slow: Slow tests (skip with -m 'not slow')",
    "plugin: Plugin-specific tests",
    "api: API endpoint tests",
    "requires_db: Requires database connection",
    "requires_api: Requires external API",
]
```

### 5.6 Coverage Hedefi

| Module | Mevcut | Hedef |
|--------|--------|-------|
| `core/plugins/` | ~30% | 90% |
| `state/` | ~50% | 90% |
| `api/` | ~40% | 85% |
| `sdk/` | 0% | 95% |
| `plugins/*` | ~10% | 70% |
| **TOPLAM** | ~25% | **80%** |

---

## 6. CONFIGURATION MANAGEMENT

### 6.1 Araştırma Kaynakları

- **12-Factor App** (https://12factor.net/config)
- **Pydantic Settings** (https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **FastAPI Settings Guide**

### 6.2 Mevcut Sorunlar

1. ❌ `config.yml` içinde hardcoded API keys
2. ❌ Environment variable merge logic hatalı
3. ❌ Config schema validation eksik
4. ❌ Type safety yok
5. ❌ Config inheritance/override mekanizması yok

### 6.3 ÖNERİLEN: Pydantic Settings

```python
# src/archiverr/config/settings.py

from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class DatabaseSettings(BaseSettings):
    """Database configuration"""
    
    model_config = SettingsConfigDict(
        env_prefix="ARCHIVERR_DB_",
        env_file=".env",
    )
    
    backend: str = Field(default="mock", description="Database backend: mock, mongodb")
    uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    database: str = Field(default="archiverr", alias="MONGODB_DATABASE")
    
    # Connection pool
    max_pool_size: int = Field(default=50, ge=1, le=100)
    min_pool_size: int = Field(default=5, ge=1, le=50)
    timeout_ms: int = Field(default=5000, ge=1000, le=30000)


class APISettings(BaseSettings):
    """API server configuration"""
    
    model_config = SettingsConfigDict(
        env_prefix="ARCHIVERR_API_",
        env_file=".env",
    )
    
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    # CORS
    cors_origins: List[str] = ["*"]
    cors_methods: List[str] = ["*"]


class PluginSettings(BaseSettings):
    """Plugin API keys (from environment ONLY)"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
    )
    
    tmdb_api_key: Optional[str] = Field(default=None, alias="TMDB_API_KEY")
    tvdb_api_key: Optional[str] = Field(default=None, alias="TVDB_API_KEY")
    omdb_api_key: Optional[str] = Field(default=None, alias="OMDB_API_KEY")
    
    @field_validator("tmdb_api_key", "tvdb_api_key", "omdb_api_key", mode="before")
    @classmethod
    def validate_not_hardcoded(cls, v, info):
        # Prevent accidental hardcoded keys
        if v and len(v) < 8:
            raise ValueError(f"{info.field_name} looks like a placeholder, not a real key")
        return v


class Settings(BaseSettings):
    """Root settings container"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
    )
    
    # Environment
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    
    # Nested settings
    database: DatabaseSettings = DatabaseSettings()
    api: APISettings = APISettings()
    plugins: PluginSettings = PluginSettings()
    
    # Application
    debug: bool = False
    dry_run: bool = False
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")


# Singleton instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

---

## 7. LOGGING & MONITORING

### 7.1 Araştırma Kaynakları

- **structlog** (https://www.structlog.org/)
- **OpenTelemetry Python** (https://opentelemetry.io/docs/instrumentation/python/)
- **Prometheus Python Client**

### 7.2 Mevcut Durum

- ❌ Custom `utils/debug.py` kullanılıyor
- ❌ Structured logging yok
- ❌ JSON output yok (production için)
- ❌ Trace/correlation ID yok
- ❌ Metrics yok

### 7.3 ÖNERİLEN: structlog

```python
# src/archiverr/logging.py

import structlog
import logging
import sys
from typing import Optional

def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
):
    """
    Configure structured logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON format (for production)
        log_file: Optional file path for logs
    """
    
    # Shared processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if json_format:
        # Production: JSON format
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a logger instance"""
    return structlog.get_logger(name)


# Context helpers
def bind_execution_context(execution_id: str):
    """Bind execution ID to all subsequent logs"""
    structlog.contextvars.bind_contextvars(execution_id=execution_id)

def bind_match_context(match_index: int, input_path: str):
    """Bind match context to all subsequent logs"""
    structlog.contextvars.bind_contextvars(
        match_index=match_index,
        input_path=input_path,
    )

def clear_context():
    """Clear all bound context"""
    structlog.contextvars.clear_contextvars()
```

### 7.4 ÖNERİLEN: Health Checks

```python
# src/archiverr/api/v1/health/router.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

router = APIRouter(tags=["Health"])

class HealthStatus(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    version: str
    checks: Dict[str, Any]

class LivenessResponse(BaseModel):
    status: str
    timestamp: datetime

class ReadinessResponse(BaseModel):
    status: str
    timestamp: datetime
    checks: Dict[str, bool]


@router.get("/health", response_model=HealthStatus)
async def health_check(db=Depends(get_optional_database)):
    """
    Comprehensive health check.
    
    Returns status of all dependencies.
    """
    checks = {}
    overall_status = "healthy"
    
    # Database check
    if db:
        try:
            await db.command("ping")
            checks["database"] = {"status": "up", "type": "mongodb"}
        except Exception as e:
            checks["database"] = {"status": "down", "error": str(e)}
            overall_status = "degraded"
    else:
        checks["database"] = {"status": "not_configured"}
    
    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="2.1.0",
        checks=checks,
    )


@router.get("/health/live", response_model=LivenessResponse)
async def liveness_probe():
    """
    Kubernetes liveness probe.
    
    Returns 200 if the application is running.
    """
    return LivenessResponse(
        status="alive",
        timestamp=datetime.utcnow(),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_probe(db=Depends(get_optional_database)):
    """
    Kubernetes readiness probe.
    
    Returns 200 if the application is ready to serve traffic.
    """
    checks = {}
    ready = True
    
    # Database readiness
    if db:
        try:
            await db.command("ping")
            checks["database"] = True
        except Exception:
            checks["database"] = False
            ready = False
    else:
        checks["database"] = True  # Mock mode is OK
    
    if not ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        timestamp=datetime.utcnow(),
        checks=checks,
    )
```

---

## 8. SECURITY ANALİZİ

### 8.1 Mevcut Güvenlik Sorunları

| Sorun | Şiddet | Durum |
|-------|--------|-------|
| Hardcoded API keys in config.yml | 🔴 KRİTİK | ❌ Hala var |
| `eval()` usage in ffprobe | 🔴 KRİTİK | ❌ Hala var |
| No rate limiting | 🟠 YÜKSEK | ❌ Eksik |
| No input sanitization | 🟠 YÜKSEK | ⚠️ Kısmi |
| No authentication | 🟡 ORTA | ❌ Eksik (lokal için OK) |

### 8.2 eval() Düzeltmesi (KRİTİK)

```python
# plugins/ffprobe/client.py - MEVCUT (GÜVENSİZ)
'fps': eval(video_stream.get('r_frame_rate', '0/1').replace('/', './'))

# ÖNERİLEN DÜZELTME
def safe_parse_framerate(fps_string: str) -> float:
    """Safely parse ffprobe frame rate string (e.g., '30000/1001')"""
    try:
        if '/' in fps_string:
            num, den = fps_string.split('/')
            return float(num) / float(den) if float(den) != 0 else 0.0
        return float(fps_string)
    except (ValueError, ZeroDivisionError):
        return 0.0

# Kullanım
'fps': safe_parse_framerate(video_stream.get('r_frame_rate', '0/1'))
```

### 8.3 Rate Limiting (ÖNERİLEN)

```python
# src/archiverr/api/middleware/rate_limit.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI

limiter = Limiter(key_func=get_remote_address)

def setup_rate_limiting(app: FastAPI):
    """Configure rate limiting middleware"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Router'da kullanım
from slowapi import limiter

@router.post("/", response_model=ExecutionStartResponse)
@limiter.limit("10/minute")  # 10 execution per minute
async def start_execution(request: Request, ...):
    ...
```

---

## 9. MEVCUT PLANLARIN DEĞERLENDİRMESİ

### 9.1 AI/02_TODO.md Değerlendirmesi

| Görev | Değerlendirme | Öneri |
|-------|---------------|-------|
| Repository Pattern | ✅ Doğru yaklaşım | Öncelik ver |
| GlobalStateManager Async | ✅ Doğru | Öncelik ver |
| Response Format | ✅ Doğru | snake_case kullan |
| Test Refactor | ⚠️ Eksik | Plugin SDK testleri ekle |
| Pydantic Schemas | ✅ Doğru | Custom base model ekle |
| Type Hints | ✅ Doğru | mypy strict mode |

### 9.2 Eksik Konular (TODO'da Olmayan)

1. ❌ **pyproject.toml migrasyonu**
2. ❌ **Plugin SDK oluşturma**
3. ❌ **Pre-commit hooks**
4. ❌ **Structured logging (structlog)**
5. ❌ **Health check endpoints**
6. ❌ **Rate limiting**
7. ❌ **WebSocket/SSE progress streaming**
8. ❌ **Background task queue**
9. ❌ **Metrics/Observability**
10. ❌ **API documentation enhancement**

### 9.3 AI/03_ARCHITECTURE.md Değerlendirmesi

| Konu | Değerlendirme |
|------|---------------|
| Plugin-Agnostic principle | ✅ Mükemmel |
| Directory structure | ⚠️ Güncellemeli |
| Execution flow | ✅ Doğru |
| MongoDB collections | ✅ Doğru |
| Plugin structure | ⚠️ SDK eksik |

---

## 10. GÜNCELLENMİŞ REFACTORING PLANI

### FAZ 0: Acil Güvenlik Düzeltmeleri (1 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 0.1 | `eval()` güvenlik açığını düzelt | 🔴 KRİTİK |
| 0.2 | API keys'i .env'e taşı (config.yml'dan sil) | 🔴 KRİTİK |
| 0.3 | `.env.example` oluştur | 🔴 KRİTİK |

### FAZ 1: Modern Python Project Setup (2-3 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 1.1 | `pyproject.toml` oluştur (PEP 621) | 🔴 KRİTİK |
| 1.2 | `setup.py` deprecated yap | 🟠 YÜKSEK |
| 1.3 | `.pre-commit-config.yaml` oluştur | 🟠 YÜKSEK |
| 1.4 | `ruff` konfigürasyonu | 🟠 YÜKSEK |
| 1.5 | `mypy` strict mode setup | 🟡 ORTA |
| 1.6 | `src/archiverr/py.typed` marker | 🟡 ORTA |

### FAZ 2: Plugin SDK (3-5 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 2.1 | `sdk/` modülü oluştur | 🔴 KRİTİK |
| 2.2 | `PluginContext` class | 🔴 KRİTİK |
| 2.3 | `PluginResult` standardize | 🔴 KRİTİK |
| 2.4 | Lifecycle hooks (on_startup, on_shutdown) | 🟠 YÜKSEK |
| 2.5 | Plugin testing utilities | 🟠 YÜKSEK |
| 2.6 | Mevcut plugin'leri SDK'ya migrate | 🟠 YÜKSEK |
| 2.7 | Plugin documentation generator | 🟡 ORTA |

### FAZ 3: Configuration & Logging (2 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 3.1 | Pydantic Settings migration | 🔴 KRİTİK |
| 3.2 | structlog integration | 🟠 YÜKSEK |
| 3.3 | JSON logging for production | 🟠 YÜKSEK |
| 3.4 | Correlation ID / trace context | 🟡 ORTA |

### FAZ 4: API Enhancement (3-4 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 4.1 | Health check endpoints (/live, /ready) | 🔴 KRİTİK |
| 4.2 | Rate limiting (slowapi) | 🟠 YÜKSEK |
| 4.3 | Module-level exceptions | 🟠 YÜKSEK |
| 4.4 | Service layer pattern | 🟠 YÜKSEK |
| 4.5 | Custom Pydantic base model | 🟡 ORTA |
| 4.6 | OpenAPI tags & documentation | 🟡 ORTA |

### FAZ 5: Persistence & State (3-4 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 5.1 | Repository Pattern interface | 🔴 KRİTİK |
| 5.2 | MotorRepository (async) | 🔴 KRİTİK |
| 5.3 | GlobalStateManager async | 🔴 KRİTİK |
| 5.4 | Response format standardization | 🟠 YÜKSEK |

### FAZ 6: Testing Infrastructure (2-3 gün)

| # | Görev | Öncelik |
|---|-------|---------|
| 6.1 | Test directory restructure | 🟠 YÜKSEK |
| 6.2 | Plugin-agnostic test fixtures | 🟠 YÜKSEK |
| 6.3 | Async test client setup | 🟠 YÜKSEK |
| 6.4 | Coverage thresholds | 🟡 ORTA |
| 6.5 | CI/CD pipeline (GitHub Actions) | 🟡 ORTA |

### FAZ 7: Advanced Features (Sonra)

| # | Görev | Öncelik |
|---|-------|---------|
| 7.1 | WebSocket progress streaming | 🟡 ORTA |
| 7.2 | Background task queue (ARQ) | 🟡 ORTA |
| 7.3 | Prometheus metrics | 🟢 DÜŞÜK |
| 7.4 | OpenTelemetry tracing | 🟢 DÜŞÜK |

---

## ÖZET

Bu analiz, kapsamlı internet araştırmaları sonucunda hazırlanmıştır. Archiverr projesinin endüstri standartlarına ulaşması için gereken temel değişiklikler:

1. **Modern Python Packaging** - pyproject.toml, ruff, mypy
2. **Plugin SDK** - Jellyfin/Stremio benzeri profesyonel SDK
3. **Configuration** - Pydantic Settings, 12-factor app
4. **Logging** - structlog, JSON format, trace context
5. **API** - Health checks, rate limiting, service layer
6. **Testing** - Test pyramid, async client, coverage

Tahmini toplam süre: **15-20 gün** (tam zamanlı çalışma)

---

*Bu doküman, endüstri standartlarına dayalı kapsamlı bir araştırma sonucunda hazırlanmıştır.*
