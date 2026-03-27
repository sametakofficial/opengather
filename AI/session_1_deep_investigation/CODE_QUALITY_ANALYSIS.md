# Code Quality Analysis
## Kod Kalitesi ve Yazılım Prensipleri Analizi

---

## 1. PYTHON BEST PRACTICES

### 1.1 Type Hints Kullanımı

**Durum:** ✅ İyi

```python
# Örnek: orchestrator.py
def __init__(
    self,
    event_bus: EventBus,
    state: GlobalStateManager,
    persistence: Any,  # ⚠️ Any kullanımı
    plugin_registry: PluginRegistry,
    config: dict[str, Any],
    debugger: Debugger | None = None
):
```

**İyileştirme Önerisi:**
```python
from archiverr.infrastructure.database import PersistenceInterface

persistence: PersistenceInterface | None = None  # Somut tip
```

### 1.2 Dataclass Kullanımı

**Durum:** ✅ Çok İyi

```python
# state/models.py - Örnek kullanım
@dataclass
class JobState:
    index: int
    run_id: str
    id: str = field(default="")
    input: InputData = field(default_factory=lambda: InputData(""))
    output: OutputData = field(default_factory=OutputData)
    status: JobStatus = field(default_factory=JobStatus)
    plugins: dict[str, dict[str, Any]] = field(default_factory=dict)
```

### 1.3 Enum Kullanımı

**Durum:** ✅ İyi

```python
# core/plugins/registry.py
class Stage(Enum):
    PARSE = "parse"
    DATA = "data"
    OUTPUT = "output"

# state/models.py
class StateEnum(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
```

### 1.4 ABC ve Protocol Kullanımı

**Durum:** ✅ İyi

```python
# core/plugins/sdk/base.py
class BasePlugin(ABC):
    @abstractmethod
    def execute(self, *args, **kwargs):
        pass

# core/services/protocols.py
@runtime_checkable
class StateService(Protocol):
    def get_current_job(self) -> 'JobState':
        ...
```

---

## 2. SOLID PRENSİPLERİ ANALİZİ

### 2.1 Single Responsibility Principle (SRP)

| Dosya | Sorumluluklar | Değerlendirme |
|-------|---------------|---------------|
| `orchestrator.py` | Run lifecycle, delegation | ✅ İyi (delegate pattern) |
| `stage_executor.py` | Stage execution, parallel exec, validation, caching, event emission | 🔴 Çok fazla! |
| `state/manager.py` | State coordination, delegation | ✅ İyi |
| `plugins/tasker/plugin.py` | Task execution, template rendering, JSON output | 🟡 Biraz fazla |

**stage_executor.py SRP İhlali Detayı:**

Mevcut sorumluluklar (bölünmeli):
1. Stage orchestration
2. Plugin execution (per_run, per_job)
3. Parallel execution management
4. Requires/provides validation
5. Plugin data caching
6. Event emission
7. Job state management
8. Legacy plugin support

**Önerilen Bölme:**
```
stage_executor/
├── __init__.py
├── orchestrator.py      # Stage orchestration
├── per_job_runner.py    # Per-job execution
├── per_run_runner.py    # Per-run execution
├── parallel.py          # ThreadPoolExecutor logic
├── validation.py        # Requires validation
└── cache.py             # Plugin data caching
```

### 2.2 Open/Closed Principle (OCP)

**Durum:** ✅ İyi

Plugin sistemi genişlemeye açık:
```python
# Yeni plugin eklemek için:
# 1. plugins/ altında klasör oluştur
# 2. manifest.yml yaz
# 3. BasePlugin'dan inherit et
# Core kodu değiştirmeden genişleme mümkün
```

### 2.3 Liskov Substitution Principle (LSP)

**Durum:** ✅ İyi

```python
class InputPlugin(BasePlugin):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.category = "input"

class OutputPlugin(BasePlugin):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.category = "output"
```

Alt sınıflar üst sınıfın yerine geçebilir.

### 2.4 Interface Segregation Principle (ISP)

**Durum:** ✅ İyi

```python
# core/services/protocols.py - Küçük, odaklı interface'ler
class StateService(Protocol): ...
class EventService(Protocol): ...
class LoggerService(Protocol): ...
class ConfigService(Protocol): ...
class TemplateService(Protocol): ...
class ProvidesService(Protocol): ...
```

### 2.5 Dependency Inversion Principle (DIP)

**Durum:** 🟡 Kısmen İyi

**İyi Örnek:**
```python
# build_orchestrator() - Dependency Injection
def build_orchestrator(
    config: dict[str, Any],
    debugger: Debugger | None = None,
    persistence: Any = None,
    event_bus: EventBus | None = None
) -> Orchestrator:
```

**İyileştirme Gereken:**
```python
# stage_executor.py - Direkt import
from archiverr.core.services.plugin_services import PluginServices
# Öneri: Protocol üzerinden inject edilmeli
```

---

## 3. CLEAN CODE PRENSİPLERİ

### 3.1 Meaningful Names

**İyi Örnekler:**
```python
plugin_registry
stage_executor
event_bus
global_state_manager
```

**İyileştirme Gereken:**
```python
# Kısaltmalar
self._fs_lock_manager  # ✓ fs = filesystem, açık
self.env               # ⚠️ environment? Jinja Environment?
```

### 3.2 Functions Should Do One Thing

**İyi Örnek:**
```python
# orchestrator.py
def _initialize(self) -> None:
    """Initialize run state and discover plugins."""
    
def _execute_stages(self) -> None:
    """Execute all 3 stages in order."""
    
def _finalize(self, success: bool) -> None:
    """Finalize run and persist state."""
```

**Kötü Örnek:**
```python
# stage_executor.py - _execute_plugin_for_job (150+ satır)
# Validation + Execution + Caching + Event emission hepsi tek fonksiyonda
```

### 3.3 DRY (Don't Repeat Yourself)

**Tekrar Tespit Edilen:**
```python
# Birçok yerde benzer pattern
if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
    plugin_data = job.plugins.get('renamer', {})
```

**Öneri:** Helper fonksiyon:
```python
def get_job_plugin_data(job: JobState, plugin_name: str) -> dict:
    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
        return job.plugins.get(plugin_name, {})
    return {}
```

### 3.4 Error Handling

**İyi Pattern:**
```python
# orchestrator.py - Spesifik exception handling
except CriticalError as e:
    self._log("error", f"Critical error: {e}")
    self._emit_error(e, critical=True)
except PluginError as e:
    self._log("error", f"Plugin error: {e}")
except (OSError, IOError) as e:
    self._log("error", f"I/O error: {e}")
```

**Kötü Pattern:**
```python
# Bazı yerlerde çok geniş catch
except Exception as e:
    # Her şeyi yakala - spesifik hataları kaçırır
```

---

## 4. MAGIC STRINGS ve HARDCODED VALUES

### 4.1 Tespit Edilen Magic Strings

| Dosya | Satır | Magic String | Öneri |
|-------|-------|--------------|-------|
| stage_executor.py | 302 | `'all_success'` | Constant |
| stage_executor.py | 494 | `'per_job'` | Enum |
| loader.py | 73 | `'client.py'` | Constant |
| tasker/plugin.py | 29 | `'output'` | Constant |

### 4.2 Önerilen Constants

```python
# core/constants.py (yeni dosya)
class Defaults:
    ENTRY_POINT = "client.py"
    TRIGGER_RULE = "all_success"
    EXECUTION_MODE = "per_job"
    OUTPUT_DIR = "output"
    
class PluginCategory:
    INPUT = "input"
    OUTPUT = "output"
```

---

## 5. HARDCODED PLUGIN REFERANSLARI

### 5.1 Plugin-Agnostik Olmayan Kodlar

**tasker/plugin.py (line 185-196):**
```python
# KÖTÜ: Hardcoded renamer referansı
if 'renamer' in plugins_data:
    renamer_data = plugins_data['renamer']
    parsed = renamer_data.get('parsed', {})
    category = renamer_data.get('category', 'unknown')
    
    context['renamer'] = renamer_data
    if category == 'movie' and 'movie' in parsed:
        context['movie'] = parsed['movie']
```

**Öneri:**
```python
# Plugin-agnostik yaklaşım
for plugin_name, plugin_data in plugins_data.items():
    manifest = self._get_manifest(plugin_name)
    if manifest.get('provides_shortcuts'):
        self._add_shortcuts(context, plugin_name, plugin_data)
```

**tmdb/client.py (line 92-102):**
```python
# KÖTÜ: Hardcoded renamer dependency
renamer_data = job.plugins.get('renamer', {})
parsed_data = renamer_data.get('parsed', {})
```

**Öneri:** Manifest requires validation'a güven, dinamik çözüm kullan.

---

## 6. ASYNC/SYNC TUTARLILIĞI

### 6.1 Mevcut Durum

| Modül | Async | Sync | Not |
|-------|-------|------|-----|
| api/ | ✅ | - | FastAPI async |
| core/orchestrator.py | - | ✅ | Sync |
| core/plugins/executor.py | ✅ | ✅ | Karışık |
| events/bus.py | - | ✅ | Sync |
| plugins/ | ⚠️ | ✅ | setup() async, execute() sync |

### 6.2 Tutarsızlık

```python
# plugins/tmdb/client.py
async def setup(self) -> None:  # Async
    ...

def execute(self, job, services):  # Sync
    ...
```

**Öneri:** Tutarlı bir pattern belirlenmeli. Ya tamamen sync ya da tamamen async.

---

## 7. LOGGING PRATİKLERİ

### 7.1 Custom Debugger Sistemi

```python
# utils/debug.py - Custom logging
class Debugger:
    def debug(self, component: str, message: str, **kwargs): ...
    def info(self, component: str, message: str, **kwargs): ...
    def warn(self, component: str, message: str, **kwargs): ...
    def error(self, component: str, message: str, **kwargs): ...
```

**Avantajlar:**
- Structured logging
- Component-based filtering
- Keyword arguments

**Dezavantajlar:**
- Standart logging module kullanılmıyor
- Loguru gibi modern çözümler tercih edilebilir

---

## 8. TEST COVERAGE ANALİZİ

### 8.1 Mevcut Test Dosyaları

```
tests/
├── conftest.py
├── test_api.py
├── test_*.py (7 dosya)
├── e2e/
├── integration/
└── unit/
    ├── api/
    ├── core/
    └── infrastructure/
```

### 8.2 Eksik Test Coverage

**Kritik modüller için test yok/yetersiz:**
- `core/plugins/stage_executor.py`
- `core/orchestrator.py`
- `plugins/tmdb/client.py`
- `state/manager.py`

---

## 9. SECURITY ANALİZİ

### 9.1 İyi Pratikler

```python
# scanner/client.py - Path traversal koruması
if '..' in str(target_path):
    self.warn("Path traversal detected, skipping", path=target)
    continue
```

### 9.2 İyileştirme Gereken

```python
# config_loader.py - Env var expansion
# Potansiyel secret exposure riski
ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')
```

**Öneri:** Secret management için dedicated çözüm (python-dotenv + secret masking)

---

## 10. PERFORMANCE NOTLARI

### 10.1 Parallel Execution

```python
# stage_executor.py
with ThreadPoolExecutor(max_workers=min(len(plugins), 4)) as executor:
```

**İyi:** ThreadPoolExecutor kullanımı
**Öneri:** `max_workers` configurable olmalı

### 10.2 Caching

```python
# Plugin data caching mevcut
self._plugin_data_cache: dict[str, dict[str, dict[str, Any]]] = {}
```

---

## 11. ÖZET ve PUANLAMA

| Kategori | Puan (1-10) | Not |
|----------|-------------|-----|
| Type Hints | 8 | İyi kullanım, bazı Any'ler var |
| SOLID | 6.5 | SRP ihlalleri mevcut |
| Clean Code | 7 | İyi naming, bazı büyük fonksiyonlar |
| Error Handling | 7 | Spesifik exceptions var |
| DRY | 6 | Bazı tekrarlar mevcut |
| Security | 7 | Temel korumalar var |
| Testing | 3 | Yetersiz coverage |
| **TOPLAM** | **6.4/10** | **İyileştirme gerekli** |
