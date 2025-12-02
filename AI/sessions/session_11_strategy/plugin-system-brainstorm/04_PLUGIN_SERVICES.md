# PLUGIN SERVICES

```yaml
tarih: 2025-12-02
durum: final
kritik: Plugin'lerin core ile iletisim interface'i
```

---

## 1. CURRENT

```python
# Mevcut kaos
class TMDbPlugin(BasePlugin):
    def __init__(self, config):
        self.debugger = get_debugger()  # Global
        
    def execute(self, match_data):
        self.debugger.info(...)           # Debugger uzerinden
        self.context.event_bus.emit(...)  # Context uzerinden
        # State'e nasil erisilir? Belirsiz
```

Sorunlar:
- get_debugger() global state
- context.event_bus karisik erisim
- State erisimi belirsiz
- Farkli interface'ler karisik

---

## 2. FEATURE

```python
# Tek interface: PluginServices
class TMDbPlugin(BasePlugin):
    def execute(self, job: JobState, services: PluginServices):
        services.logger.info("Starting...")
        services.state.update(job.id, "tmdb.movie", data)
        services.events.emit("http.response", {...})
```

---

## 3. WHY

### Endustri Ornekleri

```
SISTEM              MERKEZI INTERFACE
--------------------------------------------------
VSCode              vscode.* API namespace
Obsidian            Plugin.app (App instance)
Home Assistant      hass object
Neovim              vim.* namespace
WordPress           $wp_query, $wpdb
Django              request object
Flask               g, current_app
```

Ortak Ozellik: Tek merkezi object/namespace uzerinden erisim.

### Archiverr Karari

```
+----------------------------------------------------------+
|              TEK INTERFACE KARARI                         |
+----------------------------------------------------------+
|                                                           |
|  SORU: Plugin core ile nasil iletisim kurar?             |
|                                                           |
|  CEVAP: PluginServices instance uzerinden                |
|                                                           |
|  NEDEN:                                                   |
|    - Tek giris noktasi (discoverability)                 |
|    - Test edilebilirlik (mock kolay)                     |
|    - Dependency injection (no globals)                   |
|    - API dokumantasyonu kolay                            |
|                                                           |
+----------------------------------------------------------+
```

---

## 4. SCHEMA

### PluginServices Structure

```
                    PluginServices
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
   StateService    EventService    LoggerService
        |                |                |
        v                v                v
   get_job()         emit()           info()
   update()          subscribe()      debug()
   get_run()                          error()
                                      warn()
        |
        v
   ConfigService
        |
        v
   get()
   get_plugin()
```

### Interface Tanimi

```python
@dataclass
class PluginServices:
    """
    Plugin'lerin core ile iletisim kurduklari tek interface.
    
    Her plugin execution'da bu object'i alir.
    Tum core islemleri bu interface uzerinden yapilir.
    """
    state: StateService
    events: EventService
    logger: LoggerService
    config: ConfigService

class StateService:
    """Job ve Run state islemleri"""
    
    def get_current_job(self) -> JobState:
        """Suanki job'u getir (per_job mode)"""
        
    def get_job(self, job_id: str) -> Optional[JobState]:
        """ID ile job getir"""
        
    def get_all_jobs(self) -> List[JobState]:
        """Tum job'lari getir"""
        
    def update(self, job_id: str, key: str, value: Any) -> None:
        """Job state'ine veri yaz"""
        
    def get_run(self) -> RunState:
        """Run state'i getir"""

class EventService:
    """EventBus islemleri"""
    
    def emit(self, event: str, data: Dict = None) -> None:
        """Event emit et"""
        
    def subscribe(self, event: str, handler: Callable) -> None:
        """Event'e subscribe ol"""

class LoggerService:
    """Loglama islemleri"""
    
    def debug(self, message: str, **kwargs) -> None:
        """Debug log"""
        
    def info(self, message: str, **kwargs) -> None:
        """Info log"""
        
    def warn(self, message: str, **kwargs) -> None:
        """Warning log"""
        
    def error(self, message: str, **kwargs) -> None:
        """Error log"""

class ConfigService:
    """Config erisimi"""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Config degeri getir"""
        
    def get_plugin(self, plugin_name: str) -> Dict:
        """Plugin config'i getir"""

Not: Direkt execution'da kullanilmaz, sadece
interface referansi icin yazilmistir.
```

---

## 5. PLUGIN SIGNATURE

### per_job Mode

```python
class TMDbPlugin(BasePlugin):
    def execute(self, job: JobState, services: PluginServices) -> PluginResult:
        # Loglama
        services.logger.info("Processing movie", title=job.input.path)
        
        # Onceki plugin verisine erisim
        parsed = job.plugins.get("renamer", {}).get("parsed", {})
        
        # API cagri
        movie = self.fetch_movie(parsed.get("movie", {}).get("name"))
        
        # State guncelle
        services.state.update(job.id, "tmdb.movie", movie)
        
        # Event emit
        services.events.emit("http.response", {
            "plugin": "tmdb",
            "job_id": job.id
        })
        
        return PluginResult.success({"movie": movie})

Not: Direkt execution'da kullanilmaz, sadece
pattern gosterimi icin yazilmistir.
```

### per_run Mode

```python
class ScannerPlugin(BasePlugin):
    def execute_run(self, services: PluginServices) -> PluginResult:
        # Config'den hedefleri al
        targets = services.config.get_plugin("scanner").get("targets", [])
        
        # Tarama
        files = self.scan(targets)
        
        # Her dosya icin job olustur
        for path in files:
            job_id = services.state.create_job(path)
            services.logger.debug("Job created", job_id=job_id)
        
        return PluginResult.success({"count": len(files)})

Not: Direkt execution'da kullanilmaz, sadece
pattern gosterimi icin yazilmistir.
```

---

## 6. MEVCUT KOD MIGRATION

### Onceki (Karisik)

```python
# executor.py (mevcut)
context = ExecutionContext(
    execution_id=...,
    match_index=...,
    config=...,
    debugger=...,
    event_bus=...,
    task_manager=...,
    api_response=...,
    previous_results=...
)
plugin.set_context(context)
result = plugin.execute(match_data)
```

### Sonraki (Temiz)

```python
# executor.py (yeni)
services = PluginServices(
    state=StateService(state_manager),
    events=EventService(event_bus),
    logger=LoggerService(debugger, plugin.name),
    config=ConfigService(config)
)

if plugin.mode == "per_job":
    job = state_manager.get_job(index)
    result = plugin.execute(job, services)
else:
    result = plugin.execute_run(services)
```

---

## 7. BAGIMLILIKLARDAN KURTULMA

```
                DEPENDENCY ELIMINATION

MEVCUT:
+----------------------------------------------------------+
|  Plugin                                                   |
|     |                                                     |
|     +---> get_debugger()          # Global import        |
|     +---> context.event_bus       # Context field        |
|     +---> context.task_manager    # Context field        |
|     +---> state??                 # Belirsiz             |
+----------------------------------------------------------+

YENİ:
+----------------------------------------------------------+
|  Plugin                                                   |
|     |                                                     |
|     +---> services.logger         # Tek interface        |
|     +---> services.events         # Tek interface        |
|     +---> services.state          # Tek interface        |
|     +---> services.config         # Tek interface        |
+----------------------------------------------------------+
```

---

## 8. TEST EDILEBILIRLIK

```python
# Test icin mock services
def test_tmdb_plugin():
    mock_services = PluginServices(
        state=MockStateService(),
        events=MockEventService(),
        logger=MockLoggerService(),
        config=MockConfigService({"api_key": "test"})
    )
    
    job = JobState(
        id="job_123",
        index=0,
        input=InputData(path="/test.mkv")
    )
    
    plugin = TMDbPlugin(config={})
    result = plugin.execute(job, mock_services)
    
    assert result.success
    assert "movie" in result.data

Not: Direkt execution'da kullanilmaz, sadece
test pattern gosterimi icin yazilmistir.
```

---

## 9. SERVICES BUILD

```
              SERVICES FACTORY

+----------------------------------------------------------+
|                    ORCHESTRATOR                           |
|                                                           |
|  def build_services(plugin: BasePlugin) -> PluginServices:|
|      return PluginServices(                              |
|          state=StateService(                             |
|              state_manager=self.state_manager,           |
|              current_job_index=self.current_index        |
|          ),                                              |
|          events=EventService(                            |
|              event_bus=self.event_bus,                   |
|              source=plugin.name                          |
|          ),                                              |
|          logger=LoggerService(                           |
|              debugger=self.debugger,                     |
|              component=plugin.name                       |
|          ),                                              |
|          config=ConfigService(                           |
|              config=self.config,                         |
|              plugin_name=plugin.name                     |
|          )                                               |
|      )                                                   |
|                                                           |
+----------------------------------------------------------+
```

---

## 10. PROVIDES EARLY COMPLETION (Services Uzerinden)

```python
# Phase 2 feature
class ProvidesService:
    """Provides tamamlama islemleri"""
    
    def complete(self, provide: str) -> None:
        """Bir provide degerini erken tamamla"""
        
# Kullanim
services.provides.complete("http.response")

Not: Phase 2 feature. Ilk versiyonda olmayabilir.
```

---

## 11. TASK EMISSION (Services Uzerinden)

```python
# Tasker disindaki plugin'ler de task emit edebilir
class TaskService:
    """Task emission islemleri"""
    
    def emit(self, task: Dict) -> Optional[Dict]:
        """Task emit et ve calistir"""

# Kullanim
services.tasks.emit({
    "type": "print",
    "template": "Found: {{ tmdb.movie.title }}"
})

Not: Mevcut emit_task() fonksiyonu
services.tasks.emit() olarak tasindi.
```

---

## 12. PHILOSOPHY EKLENTISI

```
+----------------------------------------------------------+
|              PHILOSOPHY.md - PLUGIN SERVICES              |
+----------------------------------------------------------+
|                                                           |
|  5.1 Plugin Services                                      |
|  Her plugin su servislere erisebilir:                    |
|  - services.state  : State okuma/yazma                   |
|  - services.events : Event emit/subscribe                |
|  - services.logger : Loglama                             |
|  - services.config : Config erisimi                      |
|                                                           |
|  5.2 Global Erişim Yasak                                 |
|  - get_debugger() kullanilmaz                            |
|  - Direkt state erisimi yasak                            |
|  - Tum erisim services uzerinden                         |
|                                                           |
|  5.3 Neden Tek Interface?                                |
|  - Discoverability: Ne var ne yok belli                  |
|  - Testability: Mock kolay                               |
|  - Documentation: API dokumante edilebilir               |
|                                                           |
+----------------------------------------------------------+
```
