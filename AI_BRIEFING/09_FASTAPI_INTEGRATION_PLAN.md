# FASTAPI INTEGRATION PLAN - INDUSTRY-LEVEL ARCHITECTURE

**Version**: 1.0.0  
**Date**: 2025-11-26  
**Status**: Planning Phase  
**Author**: Architecture Analysis

---

## 📊 EXECUTIVE SUMMARY

Bu döküman, Archiverr projesinin FastAPI ile tam entegrasyonu için endüstri seviyesinde bir mimari planı sunmaktadır.

### Amaç
CLI-only uygulamadan **API-first architecture**'a geçiş:
- Config parametrelerini API'den verme
- Real-time execution monitoring
- WebSocket ile live progress
- External integrations (Sonarr/Radarr benzeri)

### Öncelik Kararı: MongoDB ÖNCE → FastAPI SONRA

**Neden?**

| Kriter | MongoDB Önce | FastAPI Önce |
|--------|--------------|--------------|
| Async Performance | ✅ Motor ile optimal | ❌ Sync DB = blocking |
| State Persistence | ✅ API response'u belirler | ❌ Stateless API anlamsız |
| Real-time Updates | ✅ DB'den okuma | ❌ Memory'de state tutamaz |
| WebSocket Support | ✅ DB change streams | ❌ Manual state tracking |
| Sonarr/Radarr Pattern | ✅ DB-first yaklaşım | ❌ |

---

## 🔍 ENDÜSTRİ ARAŞTIRMASI

### 1. FastAPI Best Practices (zhanymkanov - 15k+ ⭐)

**Proje Yapısı - Netflix Dispatch Inspired:**
```
fastapi-project/
├── src/
│   ├── auth/                    # Her domain kendi klasöründe
│   │   ├── router.py           # Endpoints
│   │   ├── schemas.py          # Pydantic models
│   │   ├── models.py           # DB models
│   │   ├── service.py          # Business logic
│   │   ├── dependencies.py     # DI
│   │   ├── config.py           # Domain config
│   │   ├── constants.py        # Error codes
│   │   ├── exceptions.py       # Custom exceptions
│   │   └── utils.py            # Helpers
│   ├── config.py               # Global config
│   ├── database.py             # DB connection
│   └── main.py                 # FastAPI app
├── tests/
└── requirements/
```

**Key Patterns:**
- Domain-based structure (not file-type based)
- Dependency Injection for validation
- BaseSettings per domain
- Async routes for I/O, sync for CPU

### 2. MongoDB + Motor (Async)

```python
# database.py
import motor.motor_asyncio

class Database:
    client: AsyncIOMotorClient = None
    
    @classmethod
    async def connect(cls, uri: str, database: str):
        cls.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        cls.db = cls.client[database]
        
    @classmethod
    async def disconnect(cls):
        cls.client.close()

# Dependency injection
async def get_db():
    return Database.db
```

### 3. Background Tasks vs Celery

| Kullanım | BackgroundTasks | Celery |
|----------|-----------------|--------|
| Basit tasklar (email, log) | ✅ | ❌ Overkill |
| CPU-intensive (ML, parsing) | ❌ Blocking | ✅ |
| Task queue management | ❌ | ✅ |
| Task status tracking | ❌ | ✅ |
| Multiple workers | ❌ | ✅ |
| **Archiverr execution** | ❌ | ✅ |

### 4. Radarr/Sonarr API Pattern

```
/api/v3/
├── /movie                    # CRUD endpoints
├── /movie/{id}
├── /command                  # Async operations
├── /command/{id}             # Task status
├── /queue                    # Active operations
├── /history                  # Operation logs
├── /health                   # System status
├── /system/status
└── /config/*                 # Settings
```

**Key Features:**
- Command System: Async operations → task ID → poll status
- Health endpoints
- History/audit trail
- OpenAPI 3.0 spec

---

## 🏗️ ARCHIVERR API MİMARİSİ

### API Endpoint Yapısı

```
/api/v1/
│
├── /executions/                    # Execution management
│   ├── POST   /                   # Start new execution
│   ├── GET    /                   # List executions
│   ├── GET    /{id}               # Get execution details
│   ├── GET    /{id}/matches       # Get matches for execution
│   ├── GET    /{id}/status        # Real-time status
│   ├── DELETE /{id}               # Cancel execution
│   └── WebSocket /{id}/stream     # Live progress stream
│
├── /matches/                       # Match management
│   ├── GET    /                   # List all matches
│   ├── GET    /{id}               # Get match details
│   ├── GET    /{id}/plugins       # Plugin results for match
│   └── GET    /{id}/tasks         # Task results for match
│
├── /plugins/                       # Plugin management
│   ├── GET    /                   # List available plugins
│   ├── GET    /{name}             # Plugin details
│   ├── GET    /{name}/schema      # Plugin config schema
│   └── POST   /{name}/test        # Test plugin config
│
├── /config/                        # Configuration
│   ├── GET    /                   # Get current config
│   ├── PUT    /                   # Update config
│   ├── POST   /validate           # Validate config
│   └── GET    /schema             # Config JSON schema
│
├── /tasks/                         # Task templates
│   ├── GET    /                   # List task templates
│   ├── POST   /                   # Create task template
│   ├── PUT    /{name}             # Update task
│   └── DELETE /{name}             # Delete task
│
├── /system/                        # System info
│   ├── GET    /health             # Health check
│   ├── GET    /status             # System status
│   ├── GET    /version            # Version info
│   └── GET    /logs               # Recent logs
│
└── /targets/                       # Scan targets
    ├── GET    /                   # List targets
    ├── POST   /                   # Add target
    ├── DELETE /{id}               # Remove target
    └── POST   /scan               # Trigger scan
```

### Request/Response Örnekleri

#### 1. Start Execution
```http
POST /api/v1/executions/
Content-Type: application/json

{
  "config_override": {
    "options": {
      "dry_run": true,
      "debug": true
    },
    "plugins": {
      "tmdb": {
        "enabled": true,
        "lang": "tr"
      }
    }
  },
  "targets": [
    "/home/user/torrents/",
    "/media/downloads/"
  ],
  "tasks": ["print_match_header", "save_nfo"]
}
```

**Response:**
```json
{
  "execution_id": "abc12345",
  "status": "running",
  "started_at": "2025-11-26T17:14:34.984Z",
  "websocket_url": "/api/v1/executions/abc12345/stream",
  "poll_url": "/api/v1/executions/abc12345/status"
}
```

#### 2. Get Execution Status
```http
GET /api/v1/executions/abc12345/status
```

**Response:**
```json
{
  "execution_id": "abc12345",
  "status": "running",
  "progress": {
    "total_matches": 10,
    "completed_matches": 3,
    "current_match": {
      "index": 3,
      "input_path": "/path/to/file.mkv",
      "current_plugin": "tmdb"
    }
  },
  "elapsed_ms": 5420,
  "estimated_remaining_ms": 12000
}
```

#### 3. WebSocket Live Stream
```javascript
const ws = new WebSocket("ws://localhost:8000/api/v1/executions/abc12345/stream");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Event types: match.started, plugin.completed, match.completed, execution.completed
  console.log(data.event, data.data);
};
```

**Event Stream:**
```json
{"event": "match.started", "data": {"index": 0, "input_path": "/path/file.mkv"}}
{"event": "plugin.completed", "data": {"match_index": 0, "plugin": "renamer", "duration_ms": 45}}
{"event": "plugin.completed", "data": {"match_index": 0, "plugin": "tmdb", "duration_ms": 1200}}
{"event": "match.completed", "data": {"index": 0, "success": true, "duration_ms": 2500}}
{"event": "execution.completed", "data": {"total_matches": 10, "success": true}}
```

---

## 📁 PROJE YAPISISI (YENİ)

### Önerilen Final Yapı

```
src/archiverr/
│
├── api/                            # 🆕 FastAPI Application
│   ├── __init__.py
│   ├── main.py                    # FastAPI app initialization
│   ├── dependencies.py            # Global dependencies
│   │
│   ├── v1/                        # API version 1
│   │   ├── __init__.py
│   │   ├── router.py              # Main router (includes all)
│   │   │
│   │   ├── executions/            # Execution domain
│   │   │   ├── router.py          # /executions endpoints
│   │   │   ├── schemas.py         # Request/response models
│   │   │   ├── service.py         # Business logic
│   │   │   ├── dependencies.py    # Domain dependencies
│   │   │   └── websocket.py       # WebSocket handler
│   │   │
│   │   ├── matches/               # Match domain
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   ├── plugins/               # Plugin domain
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   ├── config/                # Config domain
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   │
│   │   └── system/                # System domain
│   │       ├── router.py
│   │       └── schemas.py
│   │
│   └── websocket/                 # WebSocket management
│       ├── __init__.py
│       ├── manager.py             # Connection manager
│       └── events.py              # Event broadcasting
│
├── infrastructure/                 # 🆕 Technical implementations
│   ├── __init__.py
│   │
│   ├── database/                  # Database layer
│   │   ├── __init__.py
│   │   ├── connection.py          # Motor async connection
│   │   ├── interface.py           # Abstract base
│   │   └── models.py              # Beanie ODM models
│   │
│   ├── repositories/              # Repository pattern
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── execution_repo.py
│   │   ├── match_repo.py
│   │   └── plugin_result_repo.py
│   │
│   └── workers/                   # Background workers
│       ├── __init__.py
│       ├── celery_app.py          # Celery configuration
│       └── tasks.py               # Celery tasks
│
├── core/                          # Core orchestration (MEVCUT)
│   ├── plugins/                   # Plugin system
│   └── tasks/                     # Task system
│
├── state/                         # State management (MEVCUT)
│   ├── manager.py
│   └── models.py
│
├── events/                        # Event bus (MEVCUT)
│   ├── bus.py
│   └── handlers.py
│
├── plugins/                       # Plugin implementations (MEVCUT)
│   ├── scanner/
│   ├── renamer/
│   ├── tmdb/
│   └── ...
│
├── cli/                           # CLI interface (MEVCUT)
│   └── main.py                    # CLI entry point
│
└── __main__.py                    # Main entry (CLI or API)
```

---

## 🔄 EXECUTION FLOW (API)

### 1. API-Triggered Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API EXECUTION FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Client                    FastAPI                    Celery Worker         │
│    │                          │                            │                │
│    │  POST /executions        │                            │                │
│    │─────────────────────────▶│                            │                │
│    │                          │                            │                │
│    │                          │  Create execution record   │                │
│    │                          │───────────▶ MongoDB        │                │
│    │                          │                            │                │
│    │                          │  Queue task               │                │
│    │                          │───────────────────────────▶│                │
│    │                          │                            │                │
│    │  Return execution_id     │                            │                │
│    │◀─────────────────────────│                            │                │
│    │                          │                            │                │
│    │  WebSocket connect       │                            │                │
│    │═════════════════════════▶│                            │                │
│    │                          │                            │                │
│    │                          │                   Execute plugins            │
│    │                          │                            │                │
│    │                          │  Event: plugin.completed   │                │
│    │  WebSocket event         │◀═══════════════════════════│                │
│    │◀═════════════════════════│                            │                │
│    │                          │                            │                │
│    │                          │  Event: match.completed    │                │
│    │  WebSocket event         │◀═══════════════════════════│                │
│    │◀═════════════════════════│                            │                │
│    │                          │                            │                │
│    │                          │  Update DB                 │                │
│    │                          │◀═══════════════════════════│                │
│    │                          │                            │                │
│    │  execution.completed     │                            │                │
│    │◀═════════════════════════│                            │                │
│    │                          │                            │                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Hybrid Mode: CLI + API

```python
# __main__.py

import sys
import uvicorn

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # API mode
        uvicorn.run(
            "archiverr.api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )
    else:
        # CLI mode (existing behavior)
        from archiverr.cli.main import cli_main
        cli_main()

if __name__ == "__main__":
    main()
```

**Kullanım:**
```bash
# CLI mode (mevcut)
python -m archiverr

# API mode (yeni)
python -m archiverr serve

# veya direkt uvicorn
uvicorn archiverr.api.main:app --reload
```

---

## 🗃️ PYDANTIC SCHEMAS

### Execution Schemas

```python
# api/v1/executions/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ConfigOverride(BaseModel):
    """Partial config override for execution"""
    options: Optional[Dict[str, Any]] = None
    plugins: Optional[Dict[str, Dict[str, Any]]] = None

class ExecutionCreate(BaseModel):
    """Request to create new execution"""
    targets: List[str] = Field(..., min_items=1)
    config_override: Optional[ConfigOverride] = None
    tasks: Optional[List[str]] = None  # Task names to execute
    
class ExecutionResponse(BaseModel):
    """Execution response"""
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    # Summary
    total_matches: int = 0
    completed_matches: int = 0
    failed_matches: int = 0
    
    # URLs for client
    websocket_url: Optional[str] = None
    poll_url: Optional[str] = None

class ExecutionProgress(BaseModel):
    """Real-time execution progress"""
    execution_id: str
    status: ExecutionStatus
    progress: Dict[str, Any]
    elapsed_ms: int
    estimated_remaining_ms: Optional[int] = None

class MatchResponse(BaseModel):
    """Match in execution"""
    index: int
    input_path: str
    category: Optional[str] = None
    status: str
    success: bool
    duration_ms: Optional[int] = None
    plugins: Dict[str, Any] = {}
    tasks: List[Dict[str, Any]] = []
```

### Config Schemas

```python
# api/v1/config/schemas.py

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class PluginConfig(BaseModel):
    """Single plugin configuration"""
    enabled: bool = True
    # Other fields are plugin-specific (opaque)
    
    class Config:
        extra = "allow"  # Allow plugin-specific fields

class OptionsConfig(BaseModel):
    """Global options"""
    debug: bool = False
    dry_run: bool = True
    hardlink: bool = True

class TaskConfig(BaseModel):
    """Task definition"""
    name: str
    type: str  # print, save
    template: Optional[str] = None
    condition: Optional[str] = None
    destination: Optional[str] = None

class ArchiverConfig(BaseModel):
    """Full configuration"""
    options: OptionsConfig
    plugins: Dict[str, PluginConfig]
    tasks: List[TaskConfig]
    
class ConfigUpdate(BaseModel):
    """Partial config update"""
    options: Optional[Dict[str, Any]] = None
    plugins: Optional[Dict[str, Any]] = None
    tasks: Optional[List[Dict[str, Any]]] = None
```

---

## 🔧 IMPLEMENTATION PHASES

### Phase 0: MongoDB Integration (ÖNCE)
**Duration: 1-2 sessions**

1. Infrastructure klasör yapısına geçiş
2. Motor async connection
3. Repository pattern implementation
4. Mock → MongoDB migration
5. Test: Existing CLI works with new DB

### Phase 1: Basic FastAPI Setup
**Duration: 1 session**

1. `api/` klasör yapısı oluştur
2. FastAPI app initialization
3. Basic health endpoint
4. CORS configuration
5. Test: `GET /health` works

### Phase 2: Execution Endpoints
**Duration: 2 sessions**

1. `POST /executions` - Create execution
2. `GET /executions` - List executions
3. `GET /executions/{id}` - Get details
4. Celery task for background execution
5. Test: Execution via API

### Phase 3: WebSocket Integration
**Duration: 1-2 sessions**

1. WebSocket connection manager
2. Event broadcasting from Celery
3. Live progress stream
4. Test: Real-time updates work

### Phase 4: Full API
**Duration: 2-3 sessions**

1. Plugin endpoints
2. Config endpoints
3. System endpoints
4. Match endpoints
5. OpenAPI documentation

### Phase 5: Frontend Integration (Opsiyonel)
**Duration: External project**

1. Svelte/React frontend
2. WebSocket connection
3. Real-time dashboard

---

## 📊 TEKNOLOJİ STACK

### Backend
| Component | Technology | Reason |
|-----------|------------|--------|
| Web Framework | FastAPI | Async, OpenAPI, type hints |
| ASGI Server | Uvicorn | High performance |
| Database | MongoDB | Document-oriented, flexible |
| Async Driver | Motor | Native async MongoDB |
| ODM (optional) | Beanie | Type-safe MongoDB ODM |
| Task Queue | Celery | Background task management |
| Message Broker | Redis | Fast, in-memory |
| Validation | Pydantic | Built into FastAPI |

### Development
| Tool | Purpose |
|------|---------|
| pytest | Testing |
| pytest-asyncio | Async tests |
| httpx | Async HTTP client for tests |
| mongomock | MongoDB mock for tests |

---

## ✅ CHECKLIST

### MongoDB (Phase 0)
- [ ] infrastructure/ klasör yapısı
- [ ] Motor async connection
- [ ] Repository implementations
- [ ] Migration from mock
- [ ] CLI still works

### FastAPI (Phase 1-4)
- [ ] api/ klasör yapısı
- [ ] Basic endpoints
- [ ] Celery integration
- [ ] WebSocket support
- [ ] Full API implementation
- [ ] OpenAPI documentation
- [ ] Tests

---

## 📚 REFERENCES

- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices) - 15k+ ⭐
- [FastAPI + MongoDB](https://testdriven.io/blog/fastapi-mongo/)
- [FastAPI + Celery](https://testdriven.io/blog/fastapi-and-celery/)
- [Radarr API](https://radarr.video/docs/api/)
- [Netflix Dispatch](https://github.com/Netflix/dispatch) - Project structure inspiration
- [Motor Documentation](https://motor.readthedocs.io/)
