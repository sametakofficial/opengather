# SESSION 11 STRATEGY v6 - DEEP INVESTIGATION

```yaml
date: 2025-11-29
type: strategy
status: investigation
focus: 
  - Session 7-10 Hallucination Detection (DETAILED)
  - SDK Concept Questioning
  - Core Execution Manager Gap
  - Free Plugin System Design
  - Conflict/Race Condition Analysis
```

---

## PART 1: SESSION 7-10 HALÜSİNASYON TESPİTİ (DETAYLİ)

### 1.1 Session 7 Halüsinasyonları

**CLAIM:** "SDK oluşturuldu ve entegre edildi"

**KOD ANALİZİ:**
```
Session 7 Execution:
- plugins/sdk/ klasörü oluşturuldu ✓
- Ama plugins/ altına konuldu (YANLIŞ YER)
- Hiçbir plugin import etmiyor
- workers/broker.py oluşturuldu ama KULLANILMIYOR
```

**GERÇEK DURUM:**
| İddia | Kod | Tespit |
|-------|-----|--------|
| SDK entegre | Hayır | ❌ HALÜSİNASYON |
| Workers ready | Skeleton var | ⚠️ KISMEN |
| EventBus DI done | Yapıldı | ✅ DOĞRU |

---

### 1.2 Session 8 Halüsinasyonları

**CLAIM:** "SDK core/plugin_sdk/'ye taşındı ve 6 phase tamamlandı"

**KOD ANALİZİ:**
```python
# Session 8 şunu iddia etti:
"core/plugin_sdk/ created"

# Ama gerçek lokasyon:
core/plugins/sdk/  # ← FARKLI!
```

**GERÇEK DURUM:**
| İddia | Kod | Tespit |
|-------|-----|--------|
| SDK at core/plugin_sdk/ | core/plugins/sdk/ | ❌ YANLIŞ LOKASYON |
| 74 tests passed | SDK testleri YOK | ❌ HALÜSİNASYON |
| All plugins migrated | Import değişti sadece | ⚠️ KISMEN |

---

### 1.3 Session 9 Halüsinasyonları

**CLAIM:** "TMDb PluginResult döndürüyor, emit_task() çalışıyor"

**KOD ANALİZİ (Session 9 sonrası):**
```python
# plugins/tmdb/client.py - Session 9 SONRASI
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    # ...
    return {                    # ← HALA Dict döndürüyor!
        'status': {...},
        'movie': {...}
    }
```

**Session 10 Summary (Line 29-42) DOĞRULADI:**
```
Session 9 Sorunları:
- ❌ "TMDb returns PluginResult" - YANLIŞ, hala Dict döndürüyordu
- ❌ "emit_task() used" - YANLIŞ, hiç çağrılmıyordu
```

**GERÇEK DURUM:**
| İddia | Kod | Tespit |
|-------|-----|--------|
| TMDb returns PluginResult | Dict döndürüyor | ❌ HALÜSİNASYON |
| emit_task() working | Çağrılmıyor | ❌ HALÜSİNASYON |
| get_debugger() removed | 9 yerde hala var | ❌ HALÜSİNASYON |
| Lifecycle hooks working | Var ama test yok | ⚠️ KISMEN |
| Capability system added | Manifest'e eklendi, kullanılmıyor | ⚠️ KISMEN |

---

### 1.4 Halüsinasyon Pattern Analizi

**Ortak Pattern:**
1. Dosya oluşturuldu → "Tamamlandı" denildi
2. Import değiştirildi → "Entegre edildi" denildi
3. Kod yazıldı ama çağrılmadı → "Çalışıyor" denildi
4. Test yazılmadı → Doğrulama yapılamadı

**Root Cause:**
- Verification komutu çalıştırılmadı
- grep sonuçları kontrol edilmedi
- `python -m archiverr` output'u analiz edilmedi

---

## PART 2: "SDK" KAVRAMININ SORGULANMASI

### 2.1 SDK Ne Demek?

**Tanım:** Software Development Kit - Geliştiricilere verilen araç seti

**Kullanıcının Sorusu:**
> "SDK bana pluginlere verilecek bir şey gibi gelmiyor... Supabase'de kullandım, pluginlerle alakası var mı bilmem"

### 2.2 Endüstri Örnekleri

**FlexGet Plugin Sistemi:**
```yaml
# FlexGet: Plugin types
- Input    # Entry üretir
- Filter   # Entry filtreler
- Output   # Entry işler
- Metadata # Entry zenginleştirir
- Modification # Entry değiştirir
```

**Stremio Addon Sistemi:**
```json
{
  "id": "my.addon",
  "version": "1.0.0",
  "name": "My Addon",
  "resources": ["catalog", "stream", "meta"],  // Ne sağlıyor
  "types": ["movie", "series"]                  // Ne türleri destekliyor
}
```

**Kodi Addon Sistemi:**
```xml
<!-- addon.xml -->
<addon id="plugin.video.example" version="1.0.0">
  <requires>
    <import addon="xbmc.python" version="3.0.0"/>
  </requires>
  <extension point="xbmc.python.pluginsource" library="main.py">
    <provides>video</provides>
  </extension>
</addon>
```

### 2.3 Archiverr İçin Doğru Terminoloji

| Mevcut Terim | Endüstri Eşdeğeri | Öneri |
|--------------|-------------------|-------|
| SDK | Plugin API / Plugin Interface | **Plugin Services** |
| InputPlugin | Entry Producer | **JobCreator** |
| OutputPlugin | Entry Enricher | **DataProvider** |
| PluginResult | Response | **PluginResponse** |
| ExecutionContext | Runtime Context | **PluginContext** |

**Öneri: "SDK" yerine "Plugin Services" kullan**

```
core/plugins/
├── services/           # ESKİ: sdk/
│   ├── __init__.py
│   ├── context.py      # PluginContext
│   ├── response.py     # PluginResponse
│   └── base.py         # BasePlugin (kategorisiz!)
├── discovery.py
├── loader.py
└── executor.py
```

---

## PART 3: CORE EXECUTION MANAGER EKSİKLİĞİ

### 3.1 Kullanıcının Tespiti

> "Plugin System neden task'larla ilgileniyor? Sistemde bir BAŞKAN eksik!"

### 3.2 Mevcut Akış (YANLIŞ)

```
┌──────────────────────────────────────────────────────────────┐
│                      __main__.py                             │
│  (Config yükle + Plugin discovery + Plugin execution +       │
│   Task execution + State management + Everything!)           │
└──────────────────────────────────────────────────────────────┘
```

**Problem:** `__main__.py` HER ŞEYİ yapıyor - 392 satır!

### 3.3 Olması Gereken Akış

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CORE EXECUTION MANAGER                              │
│                      (BAŞKAN - Orchestrator)                                 │
│                                                                              │
│  Sorumluluklar:                                                             │
│  1. Config okuma ve validation                                              │
│  2. Run lifecycle yönetimi (start → complete)                               │
│  3. Job iteration (her job için plugin + task)                              │
│  4. Task execution (config.yml'den)                                         │
│  5. Final report oluşturma                                                  │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   PLUGIN SYSTEM     │  │    STATE MANAGER    │  │    TASK SYSTEM      │
│                     │  │                     │  │                     │
│ Sorumluluklar:      │  │ Sorumluluklar:      │  │ Sorumluluklar:      │
│ - Manifest okuma    │  │ - Run state         │  │ - Template render   │
│ - Plugin yükleme    │  │ - Job state         │  │ - Print task exec   │
│ - Dependency sort   │  │ - Plugin results    │  │ - Save task exec    │
│ - Plugin execution  │  │ - MongoDB persist   │  │                     │
│ - Conflict detect   │  │ - Event emission    │  │                     │
│                     │  │                     │  │                     │
│ TASK İLE İLGİLENMEZ │  │ TASK İLE İLGİLENMEZ │  │ PLUGIN İLE İLGİLENMEZ│
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
```

### 3.4 Önerilen Dosya Yapısı

```
core/
├── orchestrator.py         # YENİ: Core Execution Manager (BAŞKAN)
├── plugins/
│   ├── discovery.py
│   ├── loader.py
│   ├── executor.py         # SADECE plugin execution
│   ├── resolver.py
│   └── services/           # ESKİ: sdk/
│       ├── context.py
│       ├── response.py
│       └── base.py
├── tasks/
│   ├── task_manager.py     # SADECE task execution
│   └── template_manager.py
└── state/
    ├── manager.py
    └── models.py
```

---

## PART 4: ÖZGÜR PLUGİN SİSTEMİ TASARIMI

### 4.1 Kullanıcının Vizyonu

> "Plugin kategorisi YOK. Plugin'ler ne gönderdiği önemli. Plugin'ler hangi job'a eklemek istediklerini belirtmek zorunda."

### 4.2 Mevcut Sistem vs Yeni Sistem

| Özellik | Mevcut | Yeni |
|---------|--------|------|
| Kategori | input/output zorunlu | YOK |
| Job oluşturma | Sadece input plugin | Herhangi plugin |
| Job'a veri ekleme | Sadece output plugin | Herhangi plugin |
| Execution order | Kategoriye göre | requires'a göre |
| Plugin başına job | 1 input = N job | Plugin karar verir |

### 4.3 Yeni Plugin Manifest

```yaml
# plugins/scanner/manifest.yml
name: scanner
version: 1.0.0
description: Scans directories for media files

# Kategori YOK!

# Ne sağlıyor?
provides:
  - job.create      # Job oluşturabilir
  - data.input      # Input verisi sağlayabilir

# Ne gerektiriyor?
requires: []        # Hiçbir şey (ilk çalışan)

# Config schema
config_schema:
  targets:
    type: list
    required: true
```

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
description: Fetches metadata from TMDb

provides:
  - data.output     # Output verisi sağlayabilir

requires:
  - renamer.parsed  # Renamer'ın parsed verisine ihtiyaç duyar

config_schema:
  api_key:
    type: string
    required: true
    secret: true
```

```yaml
# plugins/hypothetical-splitter/manifest.yml
name: splitter
version: 1.0.0
description: Splits multi-episode files into separate jobs

provides:
  - job.create      # Yeni job oluşturabilir
  - data.input      # Input verisi sağlayabilir
  - data.output     # Output verisi de sağlayabilir

requires:
  - renamer.parsed  # Önce renamer çalışmalı
```

### 4.4 Plugin Services (ESKİ SDK)

```python
# core/plugins/services/job_service.py

class JobService:
    """Plugin'lerin job'larla etkileşimi için servis"""
    
    def __init__(self, state_manager, plugin_name: str):
        self._state = state_manager
        self._plugin_name = plugin_name
    
    # ==================== JOB OLUŞTURMA ====================
    
    def create_job(self, input_path: str, metadata: dict = None) -> Job:
        """
        Yeni job oluştur.
        
        Returns:
            Job object with job_id and index
        """
        index = self._state.next_job_index()
        job_id = f"job_{self._state.run_id}_{index}"
        
        job = self._state.register_job(
            index=index,
            job_id=job_id,
            input_path=input_path,
            created_by=self._plugin_name,
            metadata=metadata
        )
        
        return job
    
    # ==================== JOB'A VERİ EKLEME ====================
    
    def add_input(self, job_id: str, data: dict) -> bool:
        """
        Mevcut job'a input verisi ekle.
        
        KISITLAMA: Bir job sadece 1 input alabilir!
        
        Returns:
            True if successful, False if job already has input
        """
        job = self._state.get_job(job_id)
        
        if job.has_input:
            # Conflict! Job zaten input'a sahip
            self._emit_conflict("input_already_exists", job_id)
            return False
        
        job.input = data
        job.input_provider = self._plugin_name
        self._state.update_job(job)
        
        return True
    
    def add_output(self, job_id: str, data: dict) -> bool:
        """
        Mevcut job'a output verisi ekle.
        
        Birden fazla plugin output ekleyebilir (conflict yok).
        """
        job = self._state.get_job(job_id)
        
        # Output namespace = plugin name
        job.outputs[self._plugin_name] = data
        self._state.update_job(job)
        
        return True
    
    # ==================== JOB'LARA ERİŞİM ====================
    
    def get_all_jobs(self) -> List[Job]:
        """Tüm job'ları al"""
        return self._state.get_all_jobs()
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Belirli job'u al"""
        return self._state.get_job(job_id)
    
    def get_jobs_without_plugin_data(self, plugin_name: str) -> List[Job]:
        """Bu plugin'in henüz veri eklemediği job'ları al"""
        return [
            job for job in self._state.get_all_jobs()
            if plugin_name not in job.outputs
        ]
    
    # ==================== CONFLICT HANDLING ====================
    
    def _emit_conflict(self, conflict_type: str, job_id: str):
        """Conflict event'i yayınla"""
        self._state.event_bus.emit("plugin.conflict", {
            "type": conflict_type,
            "plugin": self._plugin_name,
            "job_id": job_id
        })
```

### 4.5 Plugin Base Class (Kategorisiz)

```python
# core/plugins/services/base.py

class BasePlugin(ABC):
    """
    Kategorisiz plugin base class.
    
    Plugin'ler ne yapabileceklerini manifest'te belirtir:
    - provides: [job.create, data.input, data.output]
    - requires: [plugin.field, ...]
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.name: str = None
        self._context: PluginContext = None
    
    def set_context(self, context: PluginContext):
        """Orchestrator tarafından çağrılır"""
        self._context = context
    
    @property
    def jobs(self) -> JobService:
        """Job service'e erişim"""
        return self._context.job_service
    
    @abstractmethod
    def execute(self) -> PluginResponse:
        """
        Plugin'i çalıştır.
        
        Plugin kendi içinde karar verir:
        - Yeni job oluşturacak mı? (jobs.create_job)
        - Mevcut job'a input ekleyecek mi? (jobs.add_input)
        - Mevcut job'a output ekleyecek mi? (jobs.add_output)
        
        Returns:
            PluginResponse with status and optional data
        """
        pass
```

### 4.6 Örnek Plugin Implementasyonları

**Scanner Plugin (Job Oluşturucu):**
```python
class ScannerPlugin(BasePlugin):
    def execute(self) -> PluginResponse:
        created_jobs = []
        
        for target in self.config['targets']:
            for file_path in self._scan_directory(target):
                # Yeni job oluştur
                job = self.jobs.create_job(
                    input_path=file_path,
                    metadata={'scanned_at': datetime.now()}
                )
                
                # Input verisi ekle
                self.jobs.add_input(job.job_id, {
                    'path': file_path,
                    'size': os.path.getsize(file_path),
                    'virtual': False
                })
                
                created_jobs.append(job.job_id)
        
        return PluginResponse.success(
            data={'created_jobs': len(created_jobs)}
        )
```

**TMDb Plugin (Output Ekleyici):**
```python
class TMDbPlugin(BasePlugin):
    def execute(self) -> PluginResponse:
        processed = 0
        
        # Bu plugin'in henüz işlemediği job'ları al
        for job in self.jobs.get_jobs_without_plugin_data('tmdb'):
            # Renamer verisine ihtiyacımız var
            renamer_data = job.outputs.get('renamer', {})
            parsed = renamer_data.get('parsed', {})
            
            if not parsed:
                continue  # Skip - no parsed data
            
            # TMDb'den veri çek
            if parsed.get('movie'):
                tmdb_data = self._fetch_movie(parsed['movie'])
            elif parsed.get('show'):
                tmdb_data = self._fetch_show(parsed['show'])
            else:
                continue
            
            # Job'a output ekle
            self.jobs.add_output(job.job_id, tmdb_data)
            processed += 1
        
        return PluginResponse.success(
            data={'processed_jobs': processed}
        )
```

**Hypothetical Splitter Plugin (Hem Oluşturucu Hem Ekleyici):**
```python
class SplitterPlugin(BasePlugin):
    """
    Multi-episode dosyaları ayırır.
    Örnek: "Show S01E01-E03.mkv" → 3 ayrı job
    """
    
    def execute(self) -> PluginResponse:
        split_count = 0
        
        for job in self.jobs.get_all_jobs():
            renamer_data = job.outputs.get('renamer', {})
            parsed = renamer_data.get('parsed', {})
            
            # Multi-episode mi kontrol et
            episodes = parsed.get('episodes', [])
            if len(episodes) <= 1:
                continue  # Tek episode, split gerekmez
            
            # Her episode için yeni job oluştur
            for ep in episodes:
                new_job = self.jobs.create_job(
                    input_path=job.input['path'],
                    metadata={
                        'split_from': job.job_id,
                        'episode': ep
                    }
                )
                
                # Yeni job'a input ekle
                self.jobs.add_input(new_job.job_id, {
                    'path': job.input['path'],
                    'virtual': True,  # Sanal - fiziksel dosya aynı
                    'episode_offset': ep['number']
                })
                
                split_count += 1
        
        return PluginResponse.success(
            data={'split_jobs': split_count}
        )
```

---

## PART 5: CONFLICT VE RACE CONDITION ANALİZİ

### 5.1 Potansiyel Conflict'ler

**1. Aynı Job'a Birden Fazla Input:**
```
Job-0:
  ├── scanner → add_input() ✓
  └── file_reader → add_input() ✗ CONFLICT!
```

**Çözüm:** `add_input()` ikinci çağrıda `False` döner + event emit eder.

**2. Requires Zincirinde Döngü:**
```
plugin_a requires: [plugin_b.data]
plugin_b requires: [plugin_a.data]
```

**Çözüm:** Topological sort sırasında tespit → Error fırlat.

**3. Paralel Execution'da Race Condition:**
```
Thread-1: plugin_a → jobs.add_output(job_0, {...})
Thread-2: plugin_b → jobs.add_output(job_0, {...})
```

**Çözüm:** State manager lock kullanıyor (mevcut sistemde var).

### 5.2 Event-Based Debug System

```python
# Plugin conflict event'leri
class PluginEvents:
    # Conflict events
    CONFLICT_INPUT_EXISTS = "plugin.conflict.input_exists"
    CONFLICT_CIRCULAR_DEP = "plugin.conflict.circular_dependency"
    CONFLICT_MISSING_REQ = "plugin.conflict.missing_requirement"
    
    # Debug events
    DEBUG_JOB_CREATED = "plugin.debug.job_created"
    DEBUG_INPUT_ADDED = "plugin.debug.input_added"
    DEBUG_OUTPUT_ADDED = "plugin.debug.output_added"
    DEBUG_PLUGIN_SKIPPED = "plugin.debug.skipped"
```

### 5.3 Plugin System Metabolizması

Kullanıcının dediği gibi:
> "Plugin system kendi içinde yaşayan bir canlı gibi, metabolizmasına kabul edebileceği/edemeyeceği şeyler"

```python
class PluginSystemHealth:
    """Plugin system sağlık kontrolü"""
    
    def check_manifest_validity(self, manifest: dict) -> List[str]:
        """Manifest geçerli mi?"""
        errors = []
        
        # provides kontrolü
        provides = manifest.get('provides', [])
        valid_provides = ['job.create', 'data.input', 'data.output']
        for p in provides:
            if p not in valid_provides:
                errors.append(f"Invalid provides: {p}")
        
        # requires kontrolü
        requires = manifest.get('requires', [])
        for r in requires:
            if '.' not in r:
                errors.append(f"Invalid requires format: {r} (expected: plugin.field)")
        
        return errors
    
    def check_execution_possibility(self, plugins: List[dict]) -> bool:
        """Bu plugin seti çalıştırılabilir mi?"""
        
        # En az bir job oluşturucu var mı?
        has_job_creator = any(
            'job.create' in p.get('provides', [])
            for p in plugins
        )
        
        if not has_job_creator:
            return False, "No plugin can create jobs"
        
        # Circular dependency var mı?
        try:
            self._topological_sort(plugins)
        except CircularDependencyError as e:
            return False, str(e)
        
        return True, "OK"
```

---

## PART 6: interface.py VE mock.py AÇIKLAMASI

### 6.1 interface.py Nedir?

```python
# infrastructure/database/interface.py
class PersistenceInterface(ABC):
    """
    Abstract base class for all persistence backends.
    
    Dependency Inversion Principle:
    - Core depends on interface, not implementation
    - Implementations: MongoDB, Mock, SQLite (future)
    """
    
    @abstractmethod
    def save_execution(self, execution) -> None: ...
    
    @abstractmethod
    def save_match(self, match) -> None: ...
    
    @abstractmethod
    def get_execution(self, execution_id: str) -> Optional[Dict]: ...
```

**Neden Var?**
- Test yazarken gerçek MongoDB'ye ihtiyaç duymamak
- Farklı storage backend'leri desteklemek (MongoDB, SQLite, file-based)

### 6.2 mock.py Nedir?

```python
# infrastructure/database/mock.py
class MockPersistence(PersistenceInterface):
    """
    In-memory persistence for testing.
    Data is lost when process exits.
    """
    
    def __init__(self):
        self._executions = {}
        self._matches = {}
    
    def save_execution(self, execution) -> None:
        self._executions[execution['_id']] = execution
```

**Kullanıcı Sorusu:**
> "mock.py'yi kaldırabiliriz"

**Analiz:**
- mock.py test için kullanışlı
- MongoDB olmadan development yapılabilir
- Unit testlerde kullanılıyor olabilir

**Öneri:** Kaldırmadan önce kullanım yerlerini kontrol et.

```bash
grep -r "MockPersistence" src/
```

---

## PART 7: EXECUTION FLOW - YENİ MİMARİ

### 7.1 Core Orchestrator (BAŞKAN)

```python
# core/orchestrator.py

class Orchestrator:
    """
    Core Execution Manager - BAŞKAN
    
    Sorumluluklar:
    1. Config yükle ve validate et
    2. Run başlat
    3. Plugin'leri keşfet ve yükle
    4. Plugin'leri sırayla çalıştır
    5. Her job tamamlandığında task'ları çalıştır
    6. Run'ı tamamla
    """
    
    def __init__(
        self,
        config: Dict,
        state_manager: StateManager,
        plugin_system: PluginSystem,
        task_system: TaskSystem,
        event_bus: EventBus
    ):
        self.config = config
        self.state = state_manager
        self.plugins = plugin_system
        self.tasks = task_system
        self.events = event_bus
    
    def run(self) -> RunResult:
        """Ana execution akışı"""
        
        # 1. Run başlat
        run_id = self.state.start_run(self.config)
        self.events.emit("run.started", {"run_id": run_id})
        
        try:
            # 2. Plugin'leri keşfet ve yükle
            loaded_plugins = self.plugins.discover_and_load()
            
            # 3. Execution order hesapla
            execution_order = self.plugins.resolve_order(loaded_plugins)
            
            # 4. Plugin'leri sırayla çalıştır
            for plugin in execution_order:
                self._execute_plugin(plugin)
            
            # 5. Tüm job'lar için task'ları çalıştır
            self._execute_tasks()
            
            # 6. Run'ı tamamla
            self.state.complete_run()
            self.events.emit("run.completed", {"run_id": run_id})
            
        except Exception as e:
            self.state.fail_run(str(e))
            self.events.emit("run.failed", {"run_id": run_id, "error": str(e)})
            raise
        
        return self.state.get_run_result()
    
    def _execute_plugin(self, plugin: BasePlugin):
        """Tek plugin'i çalıştır"""
        
        # Context oluştur
        context = PluginContext(
            job_service=JobService(self.state, plugin.name),
            event_bus=self.events,
            debugger=self.debugger
        )
        
        plugin.set_context(context)
        
        self.events.emit("plugin.started", {"plugin": plugin.name})
        
        try:
            response = plugin.execute()
            self.events.emit("plugin.completed", {
                "plugin": plugin.name,
                "response": response.to_dict()
            })
        except Exception as e:
            self.events.emit("plugin.failed", {
                "plugin": plugin.name,
                "error": str(e)
            })
    
    def _execute_tasks(self):
        """Config'deki task'ları çalıştır"""
        
        for job in self.state.get_all_jobs():
            context = self.state.build_template_context(job.index)
            
            for task_config in self.config.get('tasks', []):
                self.tasks.execute_task(task_config, context, job.index)
```

### 7.2 Yeni Execution Flow Şeması

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR (BAŞKAN)                              │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. CONFIG LOAD                                                         │ │
│  │    config.yml → Validation → Merged Config                             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 2. RUN START                                                           │ │
│  │    state.start_run() → event: run.started                              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 3. PLUGIN DISCOVERY & LOADING                                          │ │
│  │                                                                        │ │
│  │    ┌──────────────────┐    ┌──────────────────┐    ┌────────────────┐ │ │
│  │    │ Scan manifests   │───►│ Load enabled     │───►│ Sort by        │ │ │
│  │    │ plugins/*/       │    │ plugins          │    │ requires       │ │ │
│  │    └──────────────────┘    └──────────────────┘    └────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 4. PLUGIN EXECUTION (sequential by requires)                           │ │
│  │                                                                        │ │
│  │    for plugin in sorted_plugins:                                       │ │
│  │        ┌──────────────────────────────────────────────────────────┐   │ │
│  │        │ Plugin Context:                                           │   │ │
│  │        │   - job_service: JobService(state, plugin.name)          │   │ │
│  │        │   - event_bus: EventBus                                   │   │ │
│  │        │   - debugger: Debugger                                    │   │ │
│  │        └──────────────────────────────────────────────────────────┘   │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │        ┌──────────────────────────────────────────────────────────┐   │ │
│  │        │ plugin.execute()                                          │   │ │
│  │        │                                                           │   │ │
│  │        │ Plugin içinde:                                            │   │ │
│  │        │   - self.jobs.create_job()     → Yeni job oluştur        │   │ │
│  │        │   - self.jobs.add_input()      → Job'a input ekle        │   │ │
│  │        │   - self.jobs.add_output()     → Job'a output ekle       │   │ │
│  │        │   - self.jobs.get_all_jobs()   → Tüm job'lara eriş       │   │ │
│  │        └──────────────────────────────────────────────────────────┘   │ │
│  │                              │                                         │ │
│  │                              ▼                                         │ │
│  │        event: plugin.completed / plugin.failed                         │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 5. TASK EXECUTION (per job)                                            │ │
│  │                                                                        │ │
│  │    for job in state.get_all_jobs():                                    │ │
│  │        context = state.build_template_context(job.index)               │ │
│  │                                                                        │ │
│  │        for task in config['tasks']:                                    │ │
│  │            if task.condition passes:                                   │ │
│  │                if task.type == 'print':                                │ │
│  │                    template_manager.render() → print()                 │ │
│  │                if task.type == 'save' and not dry_run:                 │ │
│  │                    template_manager.render() → shutil.copy()           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ 6. RUN COMPLETE                                                        │ │
│  │    state.complete_run() → event: run.completed                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## PART 8: TERMİNOLOJİ GÜNCELLEMELERİ

### 8.1 Final Terminoloji

| Eski | Yeni | Açıklama |
|------|------|----------|
| execution | run | Bir çalışma |
| match | job | Bir iş birimi |
| SDK | Plugin Services | Plugin'lere sağlanan servisler |
| InputPlugin | - | Kategori yok |
| OutputPlugin | - | Kategori yok |
| category | provides | Plugin ne sağlıyor |
| depends_on | requires | Plugin neye ihtiyaç duyuyor |
| not_supported | skipped | Atlandı |

### 8.2 Proje Genelinde Değişiklikler

```bash
# Tüm "match" kelimelerini "job" ile değiştir
# Tüm "execution" kelimelerini "run" ile değiştir
# Tüm "SDK" kelimelerini "Plugin Services" ile değiştir
# "InputPlugin" ve "OutputPlugin" kaldır
```

---

## PART 9: SONUÇ VE ÖNCELİKLENDİRME

### 9.1 Kritik Değişiklikler (Öncelik Sırasıyla)

1. **Orchestrator Oluştur** - Core execution manager (BAŞKAN)
2. **Plugin Kategorilerini Kaldır** - provides/requires sistemi
3. **JobService Implement Et** - Plugin'lerin job'larla etkileşimi
4. **Conflict Detection Ekle** - Aynı job'a birden fazla input engelleme
5. **Terminoloji Güncelle** - match→job, execution→run

### 9.2 Tahmini Süre

| Görev | Süre |
|-------|------|
| Orchestrator | 2-3 saat |
| Plugin Services refactor | 2-3 saat |
| JobService | 1-2 saat |
| Conflict detection | 1 saat |
| Terminoloji | 1 saat |
| **TOPLAM** | **7-10 saat** |

### 9.3 Risk Analizi

| Risk | Olasılık | Etki | Mitigation |
|------|----------|------|------------|
| Breaking changes | Yüksek | Yüksek | Incremental migration |
| Test coverage düşük | Yüksek | Orta | Test yazarak ilerle |
| Plugin uyumsuzluğu | Orta | Yüksek | Adapter pattern |

---

**Tarih:** 2025-11-29
**Analyst:** Deep Investigation
