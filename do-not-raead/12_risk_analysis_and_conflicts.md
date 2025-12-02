# RISK ANALİZİ VE CONFLICT SENARYOLARI

```yaml
date: 2025-12-01
type: risk-analysis
status: in-progress
```

---

# BÖLÜM 1: DEPENDENCY SİSTEMİ CONFLICTLERİ

## 1.1 waits_for + provides DÖNGÜ PROBLEMİ

### Senaryo

```yaml
# Plugin A
name: file_processor
provides: [file.write]
waits_for: []

# Plugin B  
name: file_validator
provides: [file.write]      # AYNI CAPABILITY
waits_for: [file.write]     # KENDİ PROVIDES'INI BEKLİYOR
```

### Ne Olur?

```
1. Orchestrator başlar
2. file_validator çalışmak istiyor
3. waits_for: [file.write] → file.write provide eden tüm pluginler bitmeli
4. Ama file_validator kendisi de file.write provide ediyor
5. DEADLOCK - Kendini bekliyor
```

### Endüstri Çözümleri

**Gradle Yaklaşımı:**
```
Capability conflict = BUILD FAIL
Aynı capability'yi iki component provide edemez (varsayılan)
Eğer ederse, explicit resolution gerekir
```

**Airflow Yaklaşımı:**
```
Circular dependency = DAG validation error
DAG parse edilirken tespit edilir, runtime'a ulaşmaz
```

**Docker Compose Yaklaşımı:**
```
depends_on circular = ERROR at compose up
Compose dosyası validate edilirken hata verir
```

### ARCHİVERR İÇİN ÇÖZÜM

```python
# manifest_validator.py
class ManifestValidator:
    def validate_no_self_wait(self, manifest: PluginManifest) -> List[str]:
        """Plugin kendi provides'ını waits_for'a yazamaz"""
        errors = []
        overlap = set(manifest.provides) & set(manifest.waits_for)
        if overlap:
            errors.append(
                f"Plugin '{manifest.name}' cannot wait for capabilities it provides: {overlap}"
            )
        return errors
```

**Kural:** `provides ∩ waits_for = ∅` (kesişim boş olmalı)

---

## 1.2 CROSS-PLUGIN CIRCULAR DEPENDENCY

### Senaryo

```yaml
# Plugin A
name: metadata_enricher
provides: [metadata.enriched]
waits_for: [file.validated]

# Plugin B
name: file_validator  
provides: [file.validated]
waits_for: [metadata.enriched]
```

### Ne Olur?

```
A bekliyor → B'nin file.validated vermesini
B bekliyor → A'nın metadata.enriched vermesini
DEADLOCK
```

### Endüstri Çözümü: Topological Sort

```python
# dependency_resolver.py
def build_dependency_graph(plugins: List[PluginManifest]) -> Dict:
    """
    Kahn's Algorithm ile topological sort
    Circular dependency tespit edilirse HATA
    """
    # 1. Her plugin için in-degree hesapla
    in_degree = {p.name: 0 for p in plugins}
    
    # 2. provides → waits_for mapping
    capability_providers = {}  # capability -> [plugin_names]
    for p in plugins:
        for cap in p.provides:
            capability_providers.setdefault(cap, []).append(p.name)
    
    # 3. Adjacency list
    graph = {p.name: [] for p in plugins}
    for p in plugins:
        for wait_cap in p.waits_for:
            providers = capability_providers.get(wait_cap, [])
            for provider in providers:
                if provider != p.name:
                    graph[provider].append(p.name)
                    in_degree[p.name] += 1
    
    # 4. Kahn's algorithm
    queue = [p for p, deg in in_degree.items() if deg == 0]
    order = []
    
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    # 5. Circular dependency check
    if len(order) != len(plugins):
        remaining = [p.name for p in plugins if p.name not in order]
        raise CircularDependencyError(
            f"Circular dependency detected among: {remaining}"
        )
    
    return order
```

---

## 1.3 AYNI CAPABILITY'Yİ BİRDEN FAZLA PLUGİN PROVIDE ETME

### Senaryo

```yaml
# TMDb
provides: [metadata.movie]

# OMDb  
provides: [metadata.movie]   # AYNI!

# Tasker
waits_for: [metadata.movie]
```

### Ne Olur?

```
Tasker hangi plugin'i bekleyecek?
- Sadece TMDb mi?
- Sadece OMDb mi?
- İkisi de mi?
```

### Endüstri Yaklaşımları

**Gradle:** Conflict resolution stratejisi
```groovy
configurations.all {
    resolutionStrategy.capabilitiesResolution.withCapability("metadata:movie") {
        select("tmdb")  // Explicit seçim
    }
}
```

**OSGi:** İlk provide eden kazanır (veya version-based)

**Kubernetes:** Label selector ile spesifik hedefleme

### ARCHİVERR İÇİN ÇÖZÜM

**Seçenek A: ALL Semantics (Önerilen)**
```
waits_for: [metadata.movie]
= metadata.movie provide eden TÜM pluginler bitmeli
```

**Seçenek B: ANY Semantics**
```
waits_for_any: [metadata.movie]
= metadata.movie provide eden HERHANGİ BİRİ bitince başla
```

**Seçenek C: Explicit Plugin Reference**
```yaml
waits_for:
  - plugin: tmdb
    capability: metadata.movie
```

**Öneri:** Seçenek A (ALL) varsayılan olsun. Basit, anlaşılır, güvenli.

---

# BÖLÜM 2: STAGE VE EXECUTION MODE CONFLICTLERİ

## 2.1 per_run vs per_job AYNI STAGE'DE

### Senaryo

```yaml
# Duplicate Cleaner - tüm job'ları analiz etmeli
name: duplicate_cleaner
stage: process
mode: per_run
provides: [duplicates.cleaned]

# AI Detector - her job için ayrı çalışmalı
name: ai_detector
stage: process
mode: per_job
requires: [metadata.movie]
provides: [ai.detected]
```

### Ne Olur?

```
STAGE: process
├── duplicate_cleaner (per_run) → Tüm job'lar üzerinde çalışır
├── ai_detector (per_job) → Her job için ayrı çalışır

Soru: Hangisi önce?
```

### Çözüm: Hybrid Execution

```python
class StageExecutor:
    def execute_stage(self, stage: str, plugins: List[Plugin]):
        # 1. Topological sort by provides/waits_for
        sorted_plugins = self.topological_sort(plugins)
        
        # 2. Execute in order
        for plugin in sorted_plugins:
            if plugin.mode == 'per_run':
                result = plugin.execute_run(self.services)
                self.state.set_plugin_result(plugin.name, result)
            else:  # per_job
                for job in self.state.get_jobs():
                    result = plugin.execute(job, self.services)
                    self.state.set_job_plugin_result(job.id, plugin.name, result)
```

**Kural:** Stage içi sıralama = provides/waits_for DAG'ı

---

## 2.2 FINALIZE STAGE ZAMANLAMA PROBLEMİ

### Kullanıcının Vizyonu

```
MEVCUT DÜŞÜNCE:
input → parse → metadata → modify → finalize → output(tasks)

YENİ VİZYON:
input → parse → metadata → process → output(tasker) → sync(finalize)
```

### Neden Finalize Task'lardan Sonra?

```
Senaryo:
1. Tasker dosyaları kaydediyor (file.write)
2. Rclone sync yapacak

Eğer Rclone tasker'dan önce çalışırsa:
- Henüz kaydedilmemiş dosyaları sync edemez
- İşe yaramaz
```

### Yeni Stage Sıralaması

```
STAGES (sıralı):
1. input    → Scanner, FileReader (job oluşturma)
2. parse    → Renamer (dosya adı parse)
3. metadata → TMDb, FFProbe (metadata toplama)
4. process  → DuplicateCleaner, AIDetector, Tasker (işleme + kaydetme)
5. sync     → Rclone, Notification (son aşama, task'lardan sonra)
```

**"modify" yerine "process"** - Daha genel, metadata sonrası tüm işlemleri kapsar
**"finalize" yerine "sync"** - Daha spesifik, senkronizasyon aşaması

---

## 2.3 RCLONE vs DUPLICATE_CLEANER SONSUZ DÖNGÜ

### Senaryo

```yaml
# Duplicate Cleaner
name: duplicate_cleaner
stage: sync
mode: per_run
provides: [file.delete]
triggers_on: [file.created]   # Yeni dosya gelince çalış

# Rclone
name: rclone
stage: sync  
mode: per_run
provides: [file.sync]
triggers_on: [file.delete, file.created]  # Değişiklik olunca sync
```

### Potansiyel Döngü

```
1. Tasker dosya kaydeder → file.created event
2. Rclone tetiklenir → sync yapar → file.sync
3. DuplicateCleaner tetiklenir → duplicate bulur → siler → file.delete event
4. Rclone tekrar tetiklenir → sync yapar
5. ... SONSUZ DÖNGÜ
```

### Çözüm: Event Source Tracking

```python
@dataclass
class Event:
    name: str
    data: Dict
    source_plugin: str    # Hangi plugin emit etti
    source_stage: str     # Hangi stage'de emit edildi
    run_id: str           # Hangi run'da

class EventBus:
    def emit(self, event: Event):
        for subscriber in self.subscribers[event.name]:
            # Aynı stage'deki plugin'leri tetikleme
            if subscriber.stage == event.source_stage:
                continue  # Skip - döngü önleme
            
            subscriber.on_event(event)
```

**Kural:** Aynı stage içinde event-triggered execution yasak.

### Alternatif: Stage-Bound Events

```yaml
# manifest.yml
triggers_on:
  - event: file.created
    from_stage: process   # Sadece process stage'den gelen eventler
```

---

# BÖLÜM 3: TASKER PLUGIN DÖNÜŞÜMÜ RİSKLERİ

## 3.1 TEMPLATE DEPENDENCY PROBLEMİ

### Senaryo

```yaml
# config.yml
tasker:
  tasks:
    - name: print_with_ai
      template: "{{ job.plugins.ai_detector.result }}"
```

### Problem

```
Tasker template'de ai_detector kullanıyor
Ama ai_detector Tasker'dan SONRA çalışırsa?
Template'de job.plugins.ai_detector = undefined
```

### Çözüm: Implicit Dependency from Template

```python
class TaskerPlugin:
    def __init__(self, config):
        self.config = config
        self._extract_template_dependencies()
    
    def _extract_template_dependencies(self) -> Set[str]:
        """Template'lerden plugin bağımlılıklarını çıkar"""
        deps = set()
        pattern = r'\{\{\s*job\.plugins\.(\w+)\.'
        
        for task in self.config.get('tasks', []):
            template = task.get('template', '')
            matches = re.findall(pattern, template)
            deps.update(matches)
        
        return deps
    
    @property
    def waits_for(self) -> List[str]:
        """Manifest waits_for + template dependencies"""
        manifest_waits = self.manifest.waits_for or []
        template_deps = self._extract_template_dependencies()
        
        # Template'deki her plugin için o plugin'in provides'ını bekle
        implicit_waits = []
        for plugin_name in template_deps:
            # Bu plugin ne provide ediyor?
            plugin_manifest = self.registry.get_manifest(plugin_name)
            if plugin_manifest:
                implicit_waits.extend(plugin_manifest.provides)
        
        return list(set(manifest_waits + implicit_waits))
```

---

## 3.2 CORE DUMB OLUNCA NE KALIR?

### Mevcut Core Sorumlulukları

```
CORE ŞU AN:
├── Config loading
├── Plugin discovery
├── Plugin loading
├── Dependency resolution
├── Stage execution
├── Task execution (print/save)  ← Tasker'a taşınacak
├── State management
├── Event bus
└── Persistence
```

### Tasker Plugin Olduktan Sonra Core

```
CORE SONRA:
├── Config loading
├── Plugin discovery
├── Plugin loading  
├── Dependency resolution (DAG)
├── Stage execution (orchestration)
├── State management
├── Event bus
└── Persistence

TASKER:
├── Template rendering
├── Print actions
├── Save actions (file copy/hardlink)
├── File operations
└── Emit events (file.created, etc.)
```

### Risk: Save İşlemi Event Emit Etmeli

```python
class TaskerPlugin:
    def execute(self, job, services):
        for task in self.config['tasks']:
            if task['type'] == 'save':
                dest = self.render_template(task['destination'], job)
                services.filesystem.copy(job.input.path, dest)
                
                # KRITIK: Event emit et
                services.events.emit('file.created', {
                    'path': dest,
                    'job_id': job.id,
                    'source_plugin': self.name
                })
```

---

# BÖLÜM 4: FLEXGET-STYLE CONFIG RİSKLERİ

## 4.1 NAMESPACE COLLISION

### FlexGet Config Style

```yaml
# FlexGet - tasks altında
tasks:
  download_movies:
    rss:
      url: http://...
    series:
      - Breaking Bad
```

### Archiverr Önerilen Style

```yaml
# plugins: parent yok, direkt plugin adları
scanner:
  targets: [/downloads]

tmdb:
  api_key: ${TMDB_API_KEY}

tasker:
  tasks:
    - name: print_movie
      template: "..."
```

### Risk: Reserved Words

```yaml
# config.yml
name: test        # ← Bu bir plugin mi yoksa config metadata mı?
version: 1.0      # ← Plugin mi, config version mı?
```

### Çözüm: Config Schema

```yaml
# config.yml
_config:           # Reserved prefix
  version: 1.0
  name: my_config

# Plugin configs (no prefix)
scanner:
  targets: [/downloads]
```

**Kural:** `_` prefix = reserved for config metadata

---

## 4.2 PLUGIN ENABLE/DISABLE

### Problem

```yaml
# tmdb'yi disable etmek istiyorum
tmdb:
  enabled: false    # Çalışmasın ama config kalsın
  api_key: xxx
```

### Alternatif Syntax'lar

```yaml
# Option A: enabled field
tmdb:
  enabled: false
  api_key: xxx

# Option B: false value
tmdb: false

# Option C: null/empty
tmdb: ~

# Option D: Prefix
_disabled_tmdb:
  api_key: xxx
```

### FlexGet Yaklaşımı

```yaml
# FlexGet - plugin: no ile disable
tasks:
  my_task:
    rss:
      url: http://...
    series: no       # Disabled
```

### Öneri: Option A + Option B

```yaml
# Full disable
tmdb: false

# Disable with config preserved
tmdb:
  enabled: false
  api_key: xxx
```

---

# BÖLÜM 5: PROVIDES/WAITS_FOR/TRIGGERS_ON KOMBİNASYONLARI

## 5.1 ÜÇ DEĞER NASIL ETKİLEŞİR?

```yaml
# Manifest değerleri
provides: [X, Y]        # Bu plugin X ve Y sağlar
requires: [A, B]        # Bu plugin A ve B VERİSİNE ihtiyaç duyar
waits_for: [M, N]       # Bu plugin M ve N CAPABILITY'sini provide eden tüm pluginler bitince çalışır
triggers_on: [E, F]     # Bu plugin E veya F EVENT'i emit edilince (tekrar) çalışır
```

### Farklılıklar

| Değer | Ne Bekler | Semantik | Kullanım |
|-------|-----------|----------|----------|
| `requires` | Data path | `job.plugins.X.Y` var mı? | Data dependency |
| `waits_for` | Capability | Bu cap'i provide edenler bitti mi? | Execution order |
| `triggers_on` | Event | Bu event emit edildi mi? | Reactive execution |

### Örnek Kombinasyonlar

```yaml
# TMDb - requires kullanır (data gerekli)
name: tmdb
requires: [renamer.parsed.movie]   # renamer'ın parse ettiği data lazım
provides: [metadata.movie, online.action]

# Tasker - waits_for kullanır (sıralama)
name: tasker
waits_for: [metadata.movie]   # metadata sağlayanlar bitsin
provides: [file.write]

# FileLogger - triggers_on kullanır (reactive)
name: file_logger
triggers_on: [file.created, file.deleted]   # Her file event'inde çalış
provides: [log.file_changes]

# Rclone - waits_for + stage kullanır
name: rclone
stage: sync
waits_for: [file.write]   # Dosya yazanlar bitsin
provides: [remote.synced]
```

---

## 5.2 ONLINE_ACTION vs API_CALL vs FETCH

### Mevcut Problem

```yaml
provides:
  - api.call    # ← Çok spesifik, sadece API
```

### Gerçek Kullanım Senaryoları

```
1. TMDb → REST API çağrısı
2. Subtitle downloader → HTTP GET ile .srt indirme
3. AI Detector → OpenRouter API çağrısı
4. RSS Reader → HTTP GET ile XML okuma
5. WebSocket Logger → WS connection
```

### Doğru İsimlendirme

```yaml
# Option A: online.action (geniş)
provides:
  - online.action   # Herhangi bir internet işlemi

# Option B: Kategorize (daha spesifik)
provides:
  - network.http    # HTTP request (GET/POST/etc)
  - network.ws      # WebSocket
  - network.api     # API call (JSON response)
```

### Öneri: online.action (Basit)

```yaml
provides:
  - online.action   # Tek değer, tüm network işlemleri
```

Neden? Archiverr'ın amacı dosya organizasyonu. Network işlemlerinin detayı önemli değil, sadece "internet işlemi yaptı" bilgisi yeterli.

---

# BÖLÜM 6: RİSK MATRİSİ

| Risk | Olasılık | Etki | Çözüm |
|------|----------|------|-------|
| Self-wait deadlock | Yüksek | Kritik | Manifest validation |
| Cross-plugin circular | Orta | Kritik | Topological sort |
| Multi-provider ambiguity | Orta | Orta | ALL semantics |
| Stage event loop | Düşük | Kritik | Same-stage event block |
| Template missing dep | Yüksek | Orta | Auto-extract deps |
| Config namespace collision | Düşük | Düşük | _ prefix for meta |

---

# BÖLÜM 7: SONRAKI ADIMLAR

1. ✅ Risk analizi tamamlandı
2. ⏳ Final architecture kararları (ayrı dosya)
3. ⏳ Manifest schema finalize
4. ⏳ Validation rules implementation plan

---

**Status: COMPLETE - Risk analizi bitti, final kararlar dosyasına geçiliyor**

