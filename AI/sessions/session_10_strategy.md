# SESSION 10 STRATEGY

```yaml
date: 2025-11-28
type: strategy
status: in_progress
previous_session: 9
focus: Critical Analysis & Industrial Plugin System Research
```

---

# PART 1: SESSION 7-8-9 KRİTİK ANALİZİ (LOKAL ARAŞTIRMA)

## 1.1 Genel Değerlendirme Özeti

| Session | İddia Edilen | Gerçekleşen | Doğruluk Oranı |
|---------|--------------|-------------|----------------|
| Session 7 | EventBus DI, SDK Structure, Workers | EventBus partial, SDK dosyaları oluşturuldu, Workers skeleton | ~50% |
| Session 8 | SDK Relocation, Discovery Integration, Plugin Migration, Cleanup | SDK taşındı ama yanlış yere, Pydantic eklendi, Import'lar güncellendi | ~60% |
| Session 9 | Context-First, PluginResult, Lifecycle, Capability, Docs | Context methods eklendi, PluginResult kullanılmıyor, Lifecycle eklendi | ~70% |

**Toplam Gerçek İlerleme: ~60%**

---

## 1.2 SESSION 7 DETAYLI ANALİZ

### İddia Edilen vs Gerçekleşen

| Task | İddia | Gerçek Durum | Kanıt |
|------|-------|--------------|-------|
| EventBus DI Refactor | ✅ Tamamlandı | ⚠️ Kısmen | Singleton kaldırıldı ama test edilmedi |
| Plugin SDK Structure | ✅ Oluşturuldu | ⚠️ Dosyalar var | `plugins/sdk/` oluşturuldu ama entegre edilmedi |
| Subprocess Removal Prep | ✅ Hazırlandı | ⚠️ Skeleton | `core/workers/` var ama kullanılmıyor |

### Sorunlar
1. **SDK Wrong Location**: `plugins/sdk/` oluşturuldu, core infrastructure olmalıydı
2. **No Integration**: SDK dosyaları var ama hiçbir plugin kullanmadı
3. **Untested**: Değişiklikler test edilmedi

---

## 1.3 SESSION 8 DETAYLI ANALİZ

### İddia Edilen vs Gerçekleşen

| Task | İddia | Gerçek Durum | Kanıt |
|------|-------|--------------|-------|
| SDK Relocation | `core/plugin_sdk/` | ❌ YANLIŞ | Aslında `core/plugins/sdk/` |
| Discovery Integration | ✅ Pydantic validation | ✅ Doğru | `discovery.py` Pydantic kullanıyor |
| Plugin Migration | ✅ 6 plugin | ⚠️ Sadece import | İnheritance var ama actual usage yok |
| ExecutionContext Integration | ✅ Wired | ⚠️ Kısmen | Context pass ediliyor ama pluginler kullanmıyor |

### Session 8 Halüsinasyonları

1. **SDK Location Yalan:**
   - Session 8 execution: `"core/plugin_sdk/` dizini oluşturuldu"`
   - **Gerçek:** `core/plugins/sdk/` dizini var, `core/plugin_sdk/` YOK
   - **Kanıt:** `ls src/archiverr/core/` → plugin_sdk klasörü yok

2. **"SDK Integrated" Yanıltıcı:**
   - Session 8: "All plugins inherit from SDK base classes"
   - **Gerçek:** Import değişti ama actual SDK features (context, emit_task) kullanılmıyor

3. **Verification Claims Şüpheli:**
   - "74 tests passed" - ama SDK için hiç test yazılmadı
   - Mevcut testler SDK öncesinden kalma

---

## 1.4 SESSION 9 DETAYLI ANALİZ

### İddia Edilen vs Gerçekleşen

| Task | İddia | Gerçek Durum | Kanıt |
|------|-------|--------------|-------|
| Context-First | ✅ get_debugger() kaldırıldı | ✅ Aktif pluginlerde doğru | `grep "get_debugger" plugins/{scanner,renamer,tmdb,ffprobe}` → 0 sonuç |
| PluginResult | ✅ TMDb returns PluginResult | ❌ YANLIŞ | TMDb hala `Dict[str, Any]` döndürüyor |
| Lifecycle Hooks | ✅ setup/teardown eklendi | ✅ Doğru | `base.py` içinde async setup/teardown var |
| Capability System | ✅ Manifest güncellendi | ✅ Kısmen | `tmdb/plugin.yml` capabilities var ama kullanılmıyor |
| Documentation | ✅ PLUGIN_SDK.md | ✅ Doğru | 334 satır dokümantasyon var |

### Session 9 Kısmen Başarılı Kısımlar

1. **Context Logging ÇALIŞIYOR:**
```python
# scanner/client.py - Line 24
self.debug("Starting scan", targets=len(targets), recursive=recursive)

# tmdb/client.py - Line 56  
self.info("TMDb plugin initialized", api_key_set=bool(self.api_key))
```
Bu doğru implemente edilmiş.

2. **Lifecycle Hooks MEVCUT:**
```python
# base.py - Lines 154-166
async def setup(self) -> None:
    self._initialized = True

async def teardown(self) -> None:
    pass
```

3. **TMDb setup() ÇALIŞIYOR:**
```python
# tmdb/client.py - Lines 40-56
async def setup(self) -> None:
    self.api = TMDbAPI(...)
    self.extras_client = TMDbExtras(...)
    # ...
    self.info("TMDb plugin initialized", api_key_set=bool(self.api_key))
```

### Session 9 Başarısız/Yarım Kalan Kısımlar

1. **PluginResult KULLANILMIYOR:**
   - Session 9 claim: "TMDb returns PluginResult"
   - **Gerçek kod (tmdb/client.py line 73):**
   ```python
   def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
   ```
   - Return type hala `Dict[str, Any]`, `PluginResult` değil

2. **emit_task() HİÇ ÇAĞIRILMIYOR:**
   - `grep -r "emit_task" src/archiverr/plugins/` → 0 actual call
   - Method tanımlı ama hiçbir plugin kullanmıyor

3. **Capability System KULLANILMIYOR:**
   - `tmdb/plugin.yml` içinde `capabilities`, `provides`, `hooks` tanımlı
   - Ama core sistem bunları hiç okumıyor/kullanmıyor

---

## 1.5 KOD BAZLI KANITLAR

### ✅ Gerçekten Çalışan Şeyler

```python
# 1. Context-based logging (scanner/client.py)
self.debug("Starting scan", targets=len(targets), recursive=recursive)
# ÇALIŞIYOR - context.debugger üzerinden log yapıyor

# 2. Lifecycle hooks (tmdb/client.py)
async def setup(self) -> None:
    self.api = TMDbAPI(self.api_key, self.lang, self.region)
    self._initialized = True
# ÇALIŞIYOR - setup() çağrılıyor

# 3. ExecutionContext injection (executor.py lines 92-106)
context = ExecutionContext(
    execution_id=self.execution_id,
    match_index=match_index,
    # ...
)
plugin.set_context(context)
# ÇALIŞIYOR - context pluginlere geçiriliyor
```

### ❌ Çalışmayan/Yarım Kalan Şeyler

```python
# 1. PluginResult NOT USED (tmdb/client.py line 73)
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    # ...
    return {
        'status': {...},
        'movie': {...}
    }
# SORUN: Dict döndürüyor, PluginResult değil

# 2. emit_task() NEVER CALLED
# base.py'de tanımlı ama hiç çağrılmıyor
# grep -r "self.emit_task" plugins/ → 0 sonuç

# 3. Capabilities NOT USED
# tmdb/plugin.yml'de tanımlı ama:
# - discovery.py sadece okuyor, validate etmiyor
# - loader.py kullanmıyor
# - executor.py routing için kullanmıyor
```

---

## 1.6 SDK LOCATION CONFUSION

### Session 8'in İddiası:
```
MOVE: plugins/sdk/* -> core/plugin_sdk/*
```

### Gerçek Durum:
```
src/archiverr/
├── core/
│   ├── plugins/          # Mevcut
│   │   ├── sdk/          # SDK BURDA ✅
│   │   ├── discovery.py
│   │   ├── executor.py
│   │   └── ...
│   └── plugin_sdk/       # YOK ❌
└── plugins/
    └── ...               # Plugin implementasyonları
```

**Import Path:**
```python
# Doğru çalışan import
from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

# Session 8'in iddia ettiği (VAR OLMAYAN)
from archiverr.core.plugin_sdk import ...
```

---

## 1.7 DISABLED PLUGINS DURUMU

### Hala get_debugger() Kullanan Pluginler:
```bash
$ grep -r "get_debugger" plugins/
plugins/omdb/client.py:from archiverr.utils.debug import get_debugger
plugins/omdb/client.py:        self.debugger = get_debugger()
plugins/tvdb/client.py:from archiverr.utils.debug import get_debugger  
plugins/tvdb/client.py:        self.debugger = get_debugger()
plugins/tvmaze/client.py:from archiverr.utils.debug import get_debugger
plugins/tvmaze/client.py:        self.debugger = get_debugger()
```

Bu pluginler "disabled" olduğu için görmezden gelindi ama yine de teknik borç.

---

## 1.8 EKSIK TEST COVERAGE

| Bileşen | Mevcut Test | Olması Gereken |
|---------|-------------|----------------|
| PluginResult | ❌ Yok | Factory methods, serialization |
| PluginManifest | ❌ Yok | Validation, required fields |
| ExecutionContext | ❌ Yok | emit_task, emit_progress |
| BasePlugin | ❌ Yok | log methods, lifecycle |
| Discovery | ⚠️ Kısmi | Pydantic validation |
| Executor | ⚠️ Kısmi | Context injection |

---

## 1.9 ARCHITECTURE ISSUES

### Issue 1: Executor Still Uses get_debugger()
```python
# executor.py line 21
self.debugger = get_debugger()
```
Executor, pluginlere context inject ediyor ama kendisi hala global debugger kullanıyor.

### Issue 2: No Config Schema Validation
```yaml
# tmdb/plugin.yml - config_schema tanımlı
config_schema:
  api_key:
    type: string
    required: true
```
Ama `PluginLoader` bu şemayı validate ETMİYOR.

### Issue 3: Capability System Dead Code
```yaml
# tmdb/plugin.yml
capabilities:
  - metadata.movie
  - metadata.show
provides:
  - movie
  - show
hooks:
  - metadata.found
```
Bu alanlar tanımlı ama:
- Hiçbir yerde okunmuyor
- Routing için kullanılmıyor
- Event system yok

---

## 1.10 SESSION 7-8-9 ÖZET BULGULAR

### Gerçek İlerleme:
1. ✅ SDK dosya yapısı oluşturuldu (`core/plugins/sdk/`)
2. ✅ Pydantic manifest validation eklendi
3. ✅ Context-based logging aktif pluginlerde çalışıyor
4. ✅ Lifecycle hooks (setup/teardown) tanımlı ve TMDb'de kullanılıyor
5. ✅ PLUGIN_SDK.md dokümantasyonu oluşturuldu
6. ✅ BasePlugin convenience methods (debug, info, warn, error) çalışıyor

### Yarım Kalan/Yapılmamış:
1. ❌ PluginResult hiçbir plugin tarafından kullanılmıyor
2. ❌ emit_task() hiç çağrılmıyor
3. ❌ Capability system tamamen dead code
4. ❌ Config schema validation yok
5. ❌ Event/hook system implementasyonu yok
6. ❌ SDK unit testleri yok
7. ❌ Disabled plugins (omdb, tvdb, tvmaze) refactor edilmedi

### Halüsinasyonlar:
1. SDK location `core/plugin_sdk/` → Gerçekte `core/plugins/sdk/`
2. "TMDb returns PluginResult" → Gerçekte Dict döndürüyor
3. "All 6 phases completed" → Sadece 3-4 phase gerçekten tamamlandı
4. Test count claims → SDK için test yazılmadı

---

# PART 2: PLUGIN SİSTEMİ SORUNLARI ANALİZİ

## 2.1 Mevcut Plugin System Architecture

```
Current Flow:
┌─────────────────┐
│   config.yml    │
└────────┬────────┘
         │
┌────────▼────────┐
│ PluginDiscovery │ → Scans plugins/*/plugin.yml
└────────┬────────┘
         │
┌────────▼────────┐
│  PluginLoader   │ → Loads enabled plugins
└────────┬────────┘
         │
┌────────▼────────┐
│DependencyResolver│ → Topological sort
└────────┬────────┘
         │
┌────────▼────────┐
│ PluginExecutor  │ → Execute with context
└─────────────────┘
```

## 2.2 Eksiklikler Listesi

### A. Plugin Registration/Discovery
| Eksik | Açıklama | Öncelik |
|-------|----------|---------|
| Entry point support | pip install ile otomatik kayıt yok | LOW |
| Hot reload | Runtime'da plugin reload yok | LOW |
| Version compatibility | Plugin/core version uyumu kontrolü yok | MEDIUM |
| Plugin validation | Load time'da tam validation yok | HIGH |

### B. Plugin Communication
| Eksik | Açıklama | Öncelik |
|-------|----------|---------|
| Event system | Plugin arası event/hook yok | MEDIUM |
| Shared state | Pluginler arası veri paylaşımı limited | LOW |
| Message passing | Async message queue yok | LOW |

### C. Plugin Configuration
| Eksik | Açıklama | Öncelik |
|-------|----------|---------|
| Schema validation | config_schema tanımlı ama kullanılmıyor | HIGH |
| Type coercion | String→int gibi dönüşümler yok | MEDIUM |
| Default values | Schema'dan default değer çekme yok | MEDIUM |
| Secret handling | Secret marking var ama encryption yok | MEDIUM |

### D. Plugin Lifecycle
| Eksik | Açıklama | Öncelik |
|-------|----------|---------|
| Pre/post hooks | on_before_execute, on_after_execute yok | MEDIUM |
| Health checks | Plugin health monitoring yok | LOW |
| Graceful shutdown | Timeout ile zorla kapatma yok | LOW |

### E. Plugin Output
| Eksik | Açıklama | Öncelik |
|-------|----------|---------|
| Output schema | Response schema validation yok | HIGH |
| PluginResult enforcement | Pluginler hala Dict döndürebiliyor | HIGH |
| Streaming output | Large data için streaming yok | LOW |

---

## 2.3 Kritik Yapılması Gerekenler (Short-term)

### 1. PluginResult Enforcement
```python
# executor.py'de zorunlu kılınmalı
if not isinstance(result, PluginResult):
    raise TypeError(f"Plugin {name} must return PluginResult")
```

### 2. Config Schema Validation
```python
# loader.py'de
def _validate_config(self, plugin_name: str, config: dict):
    schema = self.manifests[plugin_name].config_schema
    if schema:
        for key, spec in schema.items():
            if spec.get('required') and key not in config:
                raise ValueError(f"Missing required config: {key}")
```

### 3. emit_task() Usage Example
```python
# tmdb/client.py'de örnek
if result.get('movie'):
    self.emit_task({
        "type": "print",
        "template": "✓ {{ tmdb.movie.title }} ({{ tmdb.movie.release_date[:4] }})"
    })
```

---

# PART 3: ONLINE ARAŞTIRMA İÇİN HAZIRLIK

## 3.1 Araştırılacak Sistemler

| Sistem | Dil | Neden |
|--------|-----|-------|
| Jellyfin | C# | Media server plugin architecture |
| Stremio | Node.js | Media addon/manifest system |
| Kodi | Python/C++ | Addon repository system |
| Home Assistant | Python | Integration manifest + config flow |
| Pluggy (pytest) | Python | Hook-based plugin system |
| Stevedore | Python | Entry point based discovery |
| MkDocs | Python | Event-based plugins |

## 3.2 Araştırma Soruları

1. **Discovery**: Pluginler nasıl bulunuyor?
2. **Registration**: Pluginler nasıl kaydediliyor?
3. **Dependency**: Bağımlılıklar nasıl yönetiliyor?
4. **Configuration**: Plugin config nasıl validate ediliyor?
5. **Lifecycle**: Setup/teardown/error handling nasıl?
6. **Communication**: Pluginler arası iletişim nasıl?
7. **Versioning**: Version compatibility nasıl sağlanıyor?
8. **Testing**: Plugin testleri nasıl yazılıyor?

---

# PART 4: MEVCUT SİSTEM GÜÇLÜ YANLARI

Sadece olumsuzluk değil, mevcut sistemin güçlü yanları:

1. **Plugin-Agnostic Core**: Core sistem plugin-specific code içermiyor ✅
2. **Dependency Resolution**: Topological sort ile doğru execution order ✅
3. **Expects System**: Data availability kontrolü ✅
4. **Manifest-Driven**: plugin.yml ile deklaratif tanım ✅
5. **Context Injection**: ExecutionContext DI pattern ✅
6. **Parallel Execution**: Bağımsız pluginler paralel çalışabiliyor ✅

---

# PART 5: MEVCUT TEST COVERAGE ANALİZİ

## 5.1 Mevcut Test Dosyaları

```
tests/unit/core/
├── test_plugin_agnostic.py    # 8280 bytes - Plugin-agnostic tests
├── test_plugin_discovery.py   # 8276 bytes - Discovery/Loader/Resolver tests
└── __init__.py
```

## 5.2 Test Coverage Detayı

### test_plugin_discovery.py Analizi

| Test Class | Test Count | Test Target |
|------------|------------|-------------|
| TestPluginDiscovery | 5 | Plugin discovery (mock plugin.json) |
| TestPluginLoader | 2 | Loader enabled/disabled config |
| TestDependencyResolver | 4 | Dependency resolution, circular detection |

**Mevcut Testler:**
- ✅ Discovery finds valid plugins
- ✅ Metadata parsing
- ✅ Skips invalid plugins
- ✅ Empty directory handling
- ✅ Category filtering
- ✅ Loader respects enabled config
- ✅ Dependency resolution ordering
- ✅ Circular dependency detection
- ✅ Expects checking

### EKSIK SDK TESTLERI

| Component | Test Needed | Priority |
|-----------|-------------|----------|
| PluginResult.success_result() | Factory method test | HIGH |
| PluginResult.error_result() | Factory method test | HIGH |
| PluginResult.to_response_dict() | Serialization test | HIGH |
| PluginResult.duration_ms | Property test | MEDIUM |
| PluginManifest validation | Required fields test | HIGH |
| PluginManifest.is_input/is_output | Property test | LOW |
| ExecutionContext.emit_task() | Integration test | HIGH |
| ExecutionContext.emit_progress() | Integration test | MEDIUM |
| BasePlugin.log() | Logging method test | MEDIUM |
| BasePlugin.debug/info/warn/error() | Convenience methods test | LOW |
| BasePlugin.set_context() | Context injection test | MEDIUM |

---

## 5.3 Mevcut Kodda Bulunan Ek Sorunlar

### Issue 1: Discovery ve Loader get_debugger() Kullanıyor

```python
# discovery.py line 35
self.debugger = get_debugger()

# loader.py line 14
self.debugger = get_debugger()

# executor.py line 21
self.debugger = get_debugger()
```

**Sorun:** Plugin'ler context kullanıyor ama core bileşenler hala global debugger.

**Çözüm:** Core bileşenler de constructor'dan debugger almalı (DI).

### Issue 2: Loader Config Schema Validation Yapmıyor

```python
# loader.py - load_plugin() method
# Plugin config'i SADECE plugin_config olarak geçiriliyor
# config_schema KONTROL EDİLMİYOR

instance = plugin_class(plugin_config)
```

**Eksik Kod:**
```python
# Olması gereken
def _validate_plugin_config(self, plugin_name: str, plugin_config: dict):
    schema = self.plugin_metadata[plugin_name].get('config_schema')
    if schema:
        for key, spec in schema.items():
            if spec.get('required') and key not in plugin_config:
                raise ValueError(f"Missing required config '{key}' for {plugin_name}")
            # Type checking, default values, etc.
```

### Issue 3: __main__.py Karmaşıklığı

```python
# __main__.py - 392 satır
# cli_main() fonksiyonu 276 satır (72-348)
```

**Sorunlar:**
- Çok fazla responsibility tek fonksiyonda
- State management, plugin execution, task execution, report generation hepsi burada
- Test edilmesi zor
- Refactoring'e ihtiyaç var

---

# PART 6: CODE SMELL VE TEKNİK BORÇ DETAYI

## 6.1 Global State Kullanımları

| File | Line | Issue |
|------|------|-------|
| discovery.py | 35 | `self.debugger = get_debugger()` |
| loader.py | 14 | `self.debugger = get_debugger()` |
| executor.py | 21 | `self.debugger = get_debugger()` |
| __main__.py | 30 | `from archiverr.utils.debug import get_debugger` |

**Toplam:** 4 core bileşen hala global debugger kullanıyor.

## 6.2 Duplicate Code Patterns

### Pattern 1: Error Result Generation
```python
# tmdb/client.py
def _error_result(self) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    return {'status': {'success': False, ...}}

# renamer/client.py
def _error_result(self) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    return {'status': {'success': False, ...}}

# ffprobe/client.py
def _error_result(self) -> Dict[str, Any]:
    now = datetime.now()
    return {'status': {'success': False, ...}}
```

**Çözüm:** PluginResult.error_result() kullanılmalı (SDK'da var, kullanılmıyor).

### Pattern 2: Timing Calculation
```python
# Her plugin'de tekrar tekrar:
start_time = datetime.now()
# ... work ...
end_time = datetime.now()
duration_ms = int((end_time - start_time).total_seconds() * 1000)
```

**Çözüm:** PluginResult otomatik timing hesaplıyor.

## 6.3 Dead Code

| File | Code | Status |
|------|------|--------|
| tmdb/plugin.yml | capabilities, provides, hooks | Tanımlı ama hiç okunmuyor |
| tmdb/plugin.yml | config_schema | Tanımlı ama validate edilmiyor |
| sdk/result.py | metadata field | Hiçbir plugin kullanmıyor |
| sdk/context.py | emit_progress() | Çağrılmıyor |
| sdk/base.py | emit_task() | Çağrılmıyor |

---

# PART 7: WORKFLOW DOSYASI ANALİZİ

## 7.1 AI/WORKFLOW.md Değerlendirmesi

```yaml
# WORKFLOW.md'de tanımlı
Current Session: Session 10
- Status: Strategy Ready - Industrial Data Flow Architecture
- Focus: DataEnvelope, ExecutionStore (XCom), Hook System, Streaming
```

**Sorun:** do-not-raead/session_10_strategy.md farklı bir şey söylüyor (KISS yaklaşımı).

**Çakışan Belgeler:**
1. `AI/WORKFLOW.md` → "Industrial Data Flow Architecture" diyor
2. `do-not-raead/session_10_strategy.md` → "KISS - Keep It Simple" diyor

**Önerim:** AI/WORKFLOW.md güncellenmeli, tek bir gerçek kaynak olmalı.

## 7.2 Session 9 "Completed" İddiası

```yaml
# WORKFLOW.md
Previous: Session 9 ✅
- Status: COMPLETED
- Results: Context-based logging, Lifecycle hooks, Capability system, PLUGIN_SDK.md
- Incomplete: TMDb still returns Dict (not PluginResult), emit_task() unused
```

Bu en azından dürüst - "Incomplete" kısmı gerçeği yansıtıyor.

---

# PART 8: ÖNCELİKLENDİRİLMİŞ TODO LİSTESİ

## 8.1 CRITICAL (Önce Yapılmalı)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 1 | TMDb execute() → PluginResult döndürmeli | tmdb/client.py | 30 min |
| 2 | SDK Unit Tests yazılmalı | tests/unit/core/test_plugin_sdk.py | 1 hour |
| 3 | emit_task() çalışan örneği | tmdb/client.py | 15 min |

## 8.2 HIGH (Haftaya)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 4 | Config schema validation | loader.py | 1 hour |
| 5 | Disabled plugins refactor | omdb, tvdb, tvmaze | 2 hours |
| 6 | Core DI refactor (get_debugger kaldır) | discovery, loader, executor | 1 hour |

## 8.3 MEDIUM (Bu Sprint)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 7 | Capability system activate | resolver.py | 2 hours |
| 8 | __main__.py refactor | __main__.py | 2 hours |
| 9 | Duplicate _error_result() temizliği | All plugins | 30 min |

## 8.4 LOW (Backlog)

| # | Task | File | Est. Time |
|---|------|------|-----------|
| 10 | Event/hook system | New files | 4 hours |
| 11 | Hot reload support | loader.py | 4 hours |
| 12 | Plugin marketplace arch | New files | 8 hours |

---

# PART 9: SOMUT İMPLEMENTASYON PLANI (Session 10)

## 9.1 Minimum Viable Completion

Session 10 başarılı sayılması için MUTLAKA yapılması gerekenler:

### Task 1: TMDb PluginResult (30 dk)
```python
# tmdb/client.py - Değişiklik
def execute(self, match_data: Dict[str, Any]) -> PluginResult:
    started_at = datetime.now()
    
    try:
        # ... mevcut logic ...
        return PluginResult.success_result(
            data={
                'movie': movie,
                'show': show,
                'episode': episode,
                'season': season,
                'extras': extras,
                'normalized': normalized,
                'validation': validation
            },
            started_at=started_at,
            metadata={'tmdb_id': tmdb_id}
        )
    except Exception as e:
        return PluginResult.error_result(str(e), started_at=started_at)
```

### Task 2: emit_task() Örneği (15 dk)
```python
# tmdb/client.py - execute() içine ekle
if result.data.get('movie'):
    self.emit_task({
        "type": "print",
        "template": "✓ Found: {{ tmdb.movie.title }} ({{ tmdb.movie.release_date[:4] }})"
    })
```

### Task 3: SDK Unit Tests (1 saat)
```python
# tests/unit/core/test_plugin_sdk.py
import pytest
from datetime import datetime
from archiverr.core.plugins.sdk import PluginResult, PluginManifest

class TestPluginResult:
    def test_success_result_factory(self):
        result = PluginResult.success_result(
            data={"movie": {"title": "Test"}}
        )
        assert result.success is True
        assert result.data["movie"]["title"] == "Test"
    
    def test_error_result_factory(self):
        result = PluginResult.error_result("API failed")
        assert result.success is False
        assert result.error == "API failed"
    
    def test_duration_ms_calculation(self):
        start = datetime(2024, 1, 1, 12, 0, 0)
        end = datetime(2024, 1, 1, 12, 0, 1, 500000)
        result = PluginResult(
            success=True,
            started_at=start,
            finished_at=end
        )
        assert result.duration_ms == 1500
    
    def test_to_response_dict(self):
        result = PluginResult.success_result(
            data={"movie": {"title": "Test"}}
        )
        response = result.to_response_dict()
        assert "status" in response
        assert response["movie"]["title"] == "Test"

class TestPluginManifest:
    def test_valid_manifest(self):
        manifest = PluginManifest(
            name="test",
            version="1.0.0",
            category="output"
        )
        assert manifest.name == "test"
        assert manifest.is_output is True
    
    def test_manifest_rejects_invalid_category(self):
        with pytest.raises(ValueError):
            PluginManifest(
                name="test",
                version="1.0.0",
                category="invalid"
            )
```

---

# BÖLÜM SONU

Bu dosya Session 10 Part 1: Lokal Araştırma sonuçlarını içermektedir.

**Toplam Analiz:**
- 3 session incelendi (7, 8, 9)
- ~60% gerçek ilerleme tespit edildi
- Kritik eksikler belirlendi
- Öncelikli TODO listesi oluşturuldu

**Sonraki Adım (Part 2):** Online araştırma - Jellyfin, Stremio, Kodi, Home Assistant, Pluggy, Stevedore, MkDocs plugin sistemleri hakkında detaylı kaynak araştırması.

**Son Adım (Part 3):** Karşılaştırmalı analiz ve archiverr için optimal plugin sistemi tasarımı.

---

# PART 10: ONLINE ARAŞTIRMA HAZIRLIK (Part 2 için)

## 10.1 Araştırılacak Sistemler ve Kaynaklar

### A. Python Plugin Systems

| Sistem | URL | Araştırma Fokus |
|--------|-----|-----------------|
| Pluggy | https://github.com/pytest-dev/pluggy | Hook specification pattern |
| Stevedore | https://github.com/openstack/stevedore | Entry point based discovery |
| MkDocs | https://github.com/mkdocs/mkdocs | Event-based plugins + config |
| Home Assistant | https://github.com/home-assistant/core | Manifest + config flow |

### B. Media Application Plugin Systems

| Sistem | URL | Araştırma Fokus |
|--------|-----|-----------------|
| Jellyfin | https://github.com/jellyfin/jellyfin-plugin-template | Interface-based DI |
| Stremio | https://github.com/Stremio/stremio-addon-sdk | Manifest-driven + handler pattern |
| Kodi | https://github.com/xbmc/xbmc | Addon repository + XML manifest |
| Plex | https://github.com/plexinc/plex-plugin-framework | Agent-based metadata |

### C. Build Tools Plugin Systems

| Sistem | URL | Araştırma Fokus |
|--------|-----|-----------------|
| Webpack Tapable | https://github.com/webpack/tapable | Hook + tap pattern |
| Gulp | https://github.com/gulpjs/gulp | Pipeline + stream |
| Rollup | https://github.com/rollup/rollup | Hook lifecycle |

## 10.2 Araştırma Soruları

Her sistem için cevaplanması gereken sorular:

### Discovery & Registration
1. Pluginler nasıl keşfediliyor? (directory scan, entry points, registry)
2. Manifest formatı nedir? (JSON, YAML, Python)
3. Pluginler nasıl kaydediliyor? (automatic, manual, decorator)

### Dependency Management
4. Plugin bağımlılıkları nasıl tanımlanıyor?
5. Circular dependency nasıl önleniyor?
6. Optional dependency desteği var mı?

### Configuration
7. Plugin config nasıl validate ediliyor? (schema, pydantic, custom)
8. Default değerler nasıl yönetiliyor?
9. Secret handling var mı?

### Lifecycle
10. Lifecycle hooks nelerdir? (setup, teardown, on_config, etc.)
11. Error handling nasıl yapılıyor?
12. Graceful shutdown var mı?

### Communication
13. Plugin arası iletişim nasıl? (events, shared state, direct call)
14. Core-plugin iletişimi nasıl?
15. Async support var mı?

### Testing
16. Plugin testleri nasıl yazılıyor?
17. Mock/fixture support var mı?
18. Integration test pattern?

## 10.3 Karşılaştırma Matrisi Şablonu

```
| Feature              | Pluggy | Stevedore | MkDocs | HA   | Jellyfin | Stremio | Archiverr |
|---------------------|--------|-----------|--------|------|----------|---------|-----------|
| Discovery Method    |        |           |        |      |          |         | Dir scan  |
| Manifest Format     |        |           |        |      |          |         | YAML      |
| Dependency System   |        |           |        |      |          |         | depends_on|
| Config Validation   |        |           |        |      |          |         | ❌        |
| Lifecycle Hooks     |        |           |        |      |          |         | ⚠️        |
| Event System        |        |           |        |      |          |         | ❌        |
| Async Support       |        |           |        |      |          |         | ⚠️        |
| Test Framework      |        |           |        |      |          |         | ❌        |
| Hot Reload          |        |           |        |      |          |         | ❌        |
```

## 10.4 Beklenen Online Araştırma Çıktıları

Part 2 sonunda elde edilecekler:

1. **Kaynak Listesi**: Her sistem için official docs, blog posts, examples
2. **Pattern Analizi**: Her sistemin kullandığı patternler
3. **Code Samples**: Gerçek dünya örnekleri
4. **Karşılaştırma Tablosu**: Doldurulmuş feature matrix
5. **Best Practices**: Endüstri standartları
6. **Anti-patterns**: Kaçınılması gerekenler

---

# PART 11: ARCHIVERR İÇİN MEVCUT EN İYİ PRATİKLER

## 11.1 Zaten Doğru Yapılan Şeyler

### 1. Plugin-Agnostic Core ✅
```python
# Core ASLA plugin ismi bilmiyor
# Sadece category (input/output) biliyor
for plugin_name, metadata in self.plugin_metadata.items():
    if metadata.get('category') != category:
        continue
```

### 2. Manifest-Driven Discovery ✅
```yaml
# plugin.yml - Declarative metadata
name: tmdb
version: 1.0.0
category: output
depends_on: [renamer]
expects: [renamer.parsed]
```

### 3. Dependency Resolution ✅
```python
# Topological sort + parallel execution
execution_groups = resolver.resolve(enabled_output)
# Group 1: [scanner] - parallel
# Group 2: [renamer, ffprobe] - parallel
# Group 3: [tmdb] - depends on renamer
```

### 4. Expects System ✅
```python
# Runtime data validation
ready_plugins = [p for p in group if resolver.check_expects(p, available_data)]
```

### 5. Context Injection ✅
```python
# ExecutionContext passed to plugins
context = ExecutionContext(
    execution_id=execution_id,
    match_index=match_index,
    debugger=self.debugger,
    event_bus=self.event_bus
)
plugin.set_context(context)
```

## 11.2 Eksik Ama Kolay Eklenebilecek Şeyler

### 1. Config Schema Validation
```python
# loader.py'ye eklenebilir
def _validate_config(self, name, config):
    schema = self.manifests[name].get('config_schema')
    # Validate against schema
```

### 2. PluginResult Enforcement
```python
# executor.py'de
if not isinstance(result, PluginResult):
    result = PluginResult.success_result(data=result)
```

### 3. emit_task() Usage
```python
# Herhangi bir plugin'de
self.emit_task({"type": "print", "template": "Found: {{ movie.title }}"})
```

## 11.3 Eksik ve Karmaşık Olan Şeyler

### 1. Event/Hook System
```python
# Henüz yok - Inter-plugin communication
await self.emit_event('metadata.found', data)
```

### 2. Hot Reload
```python
# Henüz yok - Runtime plugin reload
loader.reload_plugin('tmdb')
```

### 3. Plugin Marketplace
```python
# Henüz yok - Remote plugin installation
installer.install_from_url('https://...')
```

---

# PART 12: SESSION 10 EXECUTION PREVIEW

## 12.1 Part 2 (Online Araştırma) Planı

```
1. Pluggy araştır (30 dk)
   - Hook specification pattern
   - pytest nasıl kullanıyor
   
2. Stevedore araştır (30 dk)
   - Entry point based discovery
   - OpenStack nasıl kullanıyor
   
3. MkDocs araştır (30 dk)
   - Event-based plugins
   - Config scheme pattern
   
4. Home Assistant araştır (30 dk)
   - manifest.json schema
   - Config flow pattern
   
5. Jellyfin araştır (30 dk)
   - Interface-based DI
   - Metadata provider pattern
   
6. Stremio araştır (30 dk)
   - Manifest-driven addons
   - Handler pattern
```

## 12.2 Part 3 (Karşılaştırma & Tasarım) Planı

```
1. Feature matrix doldur
2. Archiverr için optimal pattern belirle
3. Implementation roadmap oluştur
4. Execution tasks yaz
```

---

# SESSION 10 PART 1 TAMAMLANDI ✅

---

# PART 13: ONLİNE ARAŞTIRMA SONUÇLARI (Hızlı)

## 13.1 Stremio Manifest Yapısı

**Kaynak:** https://stremio.github.io/stremio-addon-guide/step1

```json
{
  "id": "my.first.stremio.add-on",
  "version": "1.0.0",
  "name": "Hello, World",
  "description": "My first Stremio add-on",
  "resources": ["catalog", "stream", "meta"],
  "types": ["movie", "series"]
}
```

**Önemli Noktalar:**
- `manifest.json` dosya adı (bizde plugin.yml)
- Basit ve minimal yapı
- `resources` = ne sağlıyor (catalog, stream, meta)
- `types` = ne türü destekliyor (movie, series)

## 13.2 Home Assistant Manifest Yapısı

**Kaynak:** https://developers.home-assistant.io/docs/creating_integration_manifest/

```json
{
  "domain": "my_integration",
  "name": "My Integration",
  "version": "1.0.0",
  "integration_type": "hub",
  "documentation": "https://...",
  "dependencies": ["mqtt"],
  "after_dependencies": ["stream"],
  "requirements": ["some-package==1.0.0"]
}
```

**Önemli Noktalar:**
- `dependencies` = ÖNCE yüklenmesi ZORUNLU
- `after_dependencies` = varsa önce yükle, yoksa sorun değil (OPTIONAL)
- `requirements` = Python paket bağımlılıkları
- `integration_type` = hub, device, service, helper, system

## 13.3 Pluggy Hook Sistemi

**Kaynak:** https://pluggy.readthedocs.io/

```python
import pluggy

hookspec = pluggy.HookspecMarker("myproject")
hookimpl = pluggy.HookimplMarker("myproject")

class MySpec:
    @hookspec
    def myhook(self, arg1, arg2):
        """My hook specification."""

class Plugin_1:
    @hookimpl
    def myhook(self, arg1, arg2):
        return arg1 + arg2
```

**Önemli Noktalar:**
- Hook specification (spec) = arayüz tanımı
- Hook implementation (impl) = gerçek kod
- pytest bunu kullanıyor
- Bizim için şimdilik GEREKSIZ - overengineering

---

# PART 14: MEVCUT plugin.yml ANALİZİ VE TEMİZLİK

## 14.1 TMDb plugin.yml Sorunları

```yaml
# ❌ SAÇMALIK - Kaldırılacak
aliases:
  movie: "{{ self.movie }}"    # self.movie = self.movie ??? Anlamsız
  show: "{{ self.show }}"      # Circular referans
  episode: "{{ self.episode }}"
  season: "{{ self.season }}"
  credits: "{{ self.credits }}"
  images: "{{ self.images }}"

# ❌ DEAD CODE - Kullanılmıyor, kaldırılacak
capabilities:
  - metadata.movie
  - metadata.show
  
provides:
  - movie
  - show

hooks:
  - metadata.found
  - movie.matched
```

## 14.2 Temiz Manifest Yapısı Önerisi

**Dosya adı:** `manifest.yml` (plugin.yml yerine - endüstri standardı)

```yaml
# manifest.yml - TMDb Output Plugin
name: tmdb
version: 1.0.0
description: The Movie Database metadata provider
category: output
class_name: TMDbPlugin

# Bağımlılıklar (Home Assistant tarzı)
depends_on:
  - renamer                 # ZORUNLU - önce çalışmalı

# Veri beklentileri (Jinja2 syntax ile!)
expects:
  - "{{ renamer.parsed }}"  # Artık Jinja2 ile erişilebilir!

# Desteklenen medya türleri
types:
  - movie
  - show

# Config şeması (validation için)
config_schema:
  api_key:
    type: string
    required: true
    secret: true
  language:
    type: string
    default: en-US
```

## 14.3 Kaldırılacaklar (Overengineering)

| Alan | Neden Kaldırılıyor |
|------|-------------------|
| `aliases` | Anlamsız self referans |
| `capabilities` | Hiçbir yerde kullanılmıyor |
| `provides` | Hiçbir yerde kullanılmıyor |
| `hooks` | Event system yok |
| `categories` | `types` ile birleştirildi |

---

# PART 15: ORTAK ALTYAPI - config.yml = manifest.yml

## 15.1 KRİTİK PRENSİP

```
┌─────────────────────────────────────────────────────────────┐
│  config.yml VE manifest.yml AYNI ALTYAPIYI KULLANMALI      │
│                                                             │
│  • Aynı YAML Parser                                         │
│  • Aynı Jinja2 Engine                                       │
│  • Aynı Variable Resolution                                 │
│  • Aynı Template Manager                                    │
└─────────────────────────────────────────────────────────────┘
```

## 15.2 Mevcut Altyapilar (YAN YANA)

| Bilesen | config.yml | manifest.yml |
|---------|------------|--------------|
| Parser | PyYAML | PyYAML |
| Schema Validation | JSON Schema (config.schema.json) | Pydantic (PluginManifest) |
| Template Engine | Jinja2 | YOK |
| Variable Access | `$tmdb.movie.title` | YOK |
| State Access | TemplateManager | YOK |

**Validation Turleri:**
1. **Schema/Syntax Validation** - Yapi kontrolu (ikisinde de VAR)
2. **Semantic/Logic Validation** - Is mantigi kontrolu (KISMI)
   - Ornek: "En az bir input plugin enabled olmali"
   - Ornek: "tmdb.api_key bos olamaz"

**Jinja2 validation yapmaz** - sadece template render eder.
Eger template icinde olmayan bir degisken kullanirsan, bos string doner (hata vermez).

## 15.3 HEDEF: Unified Infrastructure

```python
# core/config/ klasörü altında ORTAK altyapı
core/config/
├── yaml_loader.py      # Ortak YAML parser
├── template_engine.py  # Ortak Jinja2 engine  
└── variable_resolver.py # Ortak $ syntax resolver

# KULLANIM:
# 1. config.yml yüklerken
config = ConfigLoader.load("config.yml")

# 2. manifest.yml yüklerken  
manifest = ConfigLoader.load("plugins/tmdb/manifest.yml")

# İKİSİ DE AYNI ALTYAPIYI KULLANIR
```

## 15.4 Şu An İçin Minimal Değişiklik

expects için Jinja2 ŞU AN gerekmez. Mevcut string path sistemi çalışıyor.

**AMA** gelecekte manifest.yml içinde:
```yaml
expects:
  - "{{ renamer.parsed }}"  # Jinja2 syntax
```
kullanılabilmesi için altyapı HAZIR olmalı.

## 15.5 Execution AI İçin Talimat

```
⚠️ ŞU AN YAPILMAYACAK:
- expects Jinja2 dönüşümü
- Variable resolver değişikliği
- Template engine birleştirme

✅ ŞU AN YAPILACAK:
- manifest.yml dosya adı değişikliği
- Overengineering temizliği
- PluginResult kullanımı
- Unit tests

📋 GELECEK SESSION İÇİN NOT:
config.yml ve manifest.yml altyapı birleştirmesi
ayrı bir session'da ele alınacak.
```

---

# PART 16: EXECUTABLE PLAN (Session 10 Execution)

## 16.1 Scope: SADECE TMDb

Diğer pluginler (omdb, tvdb, tvmaze) dokunulmayacak. Önce bir plugin düzgün çalışsın.

## 16.2 Görevler (Öncelik Sırasıyla)

### TASK 1: manifest.yml Migration (15 dk)
```
1. plugins/tmdb/plugin.yml → plugins/tmdb/manifest.yml (rename)
2. Overengineering alanları kaldır (aliases, capabilities, provides, hooks)
3. categories → types olarak yeniden adlandır
4. discovery.py güncelle: plugin.yml + manifest.yml ara
```

### TASK 2: TMDb PluginResult (30 dk)
```python
# tmdb/client.py
def execute(self, match_data: Dict[str, Any]) -> PluginResult:
    started_at = datetime.now()
    try:
        # ... mevcut logic ...
        return PluginResult.success_result(
            data={'movie': movie, 'show': show, ...},
            started_at=started_at
        )
    except Exception as e:
        return PluginResult.error_result(str(e), started_at=started_at)
```

### TASK 3: emit_task() Örneği (10 dk)
```python
# tmdb/client.py - execute() sonunda
if result.data.get('movie'):
    self.emit_task({
        "type": "print",
        "template": "✓ {{ tmdb.movie.title }} ({{ tmdb.movie.release_date[:4] }})"
    })
```

### TASK 4: SDK Unit Tests (45 dk)
```python
# tests/unit/core/test_plugin_sdk.py
class TestPluginResult:
    def test_success_result_factory(self): ...
    def test_error_result_factory(self): ...
    def test_to_response_dict(self): ...

class TestPluginManifest:
    def test_valid_manifest(self): ...
```

### TASK 5: Scanner manifest.yml (10 dk)
```
1. plugins/scanner/plugin.yml → manifest.yml
2. aliases kaldır
3. Minimal yapı bırak
```

---

# PART 17: KOD ÖRNEKLERİ (Execution AI için)

## 17.1 TMDb manifest.yml (Temiz Versiyon)

```yaml
# plugins/tmdb/manifest.yml
# TMDb Plugin - The Movie Database metadata provider

name: tmdb
version: 1.0.0
description: Fetches movie and TV show metadata from TMDb API
category: output
class_name: TMDbPlugin

# Execution order
depends_on:
  - renamer

# Required data
expects:
  - renamer.parsed

# Supported media types
types:
  - movie
  - show

# Configuration schema
config_schema:
  api_key:
    type: string
    required: true
    secret: true
    description: TMDb API key (v3)
  language:
    type: string
    default: en-US
  region:
    type: string
    default: TR
```

## 17.2 Scanner manifest.yml (Temiz Versiyon)

```yaml
# plugins/scanner/manifest.yml
# Scanner Plugin - File discovery input plugin

name: scanner
version: 1.0.0
description: Scans directories and files for media content
category: input
class_name: ScannerPlugin

# Input plugins have no dependencies
depends_on: []
expects: []

# Supports all media types
types: []
```

## 17.3 TMDb client.py Değişiklik (PluginResult)

```python
# ÖNCE (line 73):
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
    ...
    return {
        'status': {'success': True, ...},
        'movie': movie,
        'show': show,
    }

# SONRA:
from archiverr.core.plugins.sdk import PluginResult

def execute(self, match_data: Dict[str, Any]) -> PluginResult:
    started_at = datetime.now()
    
    try:
        # ... mevcut tüm logic aynı kalıyor ...
        
        # Sonuç oluştur
        data = {
            'movie': movie,
            'show': show,
            'episode': episode,
            'season': season,
            'extras': extras,
            'normalized': normalized,
            'validation': validation,
        }
        
        # emit_task örneği
        if movie:
            self.emit_task({
                "type": "print",
                "template": "✓ TMDb: {{ tmdb.movie.title }}"
            })
        
        return PluginResult.success_result(data=data, started_at=started_at)
        
    except Exception as e:
        self.error("TMDb execution failed", error=str(e))
        return PluginResult.error_result(str(e), started_at=started_at)
```

## 17.4 discovery.py Değişiklik (manifest.yml desteği)

```python
# ÖNCE (line 93-95):
plugin_yml = plugin_dir / 'plugin.yml'
plugin_yaml = plugin_dir / 'plugin.yaml'
plugin_json = plugin_dir / 'plugin.json'

# SONRA:
# Manifest dosyaları (öncelik sırasına göre)
manifest_yml = plugin_dir / 'manifest.yml'
manifest_yaml = plugin_dir / 'manifest.yaml'
manifest_json = plugin_dir / 'manifest.json'
# Legacy support
plugin_yml = plugin_dir / 'plugin.yml'
plugin_yaml = plugin_dir / 'plugin.yaml'
plugin_json = plugin_dir / 'plugin.json'

# Try manifest first, then legacy plugin files
for yaml_file in [manifest_yml, manifest_yaml, plugin_yml, plugin_yaml]:
    ...
```

---

# PART 18: BAŞARI KRİTERLERİ

## Session 10 Execution Başarılı Sayılır Eğer:

1. ✅ `plugins/tmdb/manifest.yml` oluşturuldu (temiz, overengineering yok)
2. ✅ `plugins/scanner/manifest.yml` oluşturuldu
3. ✅ TMDb `PluginResult` döndürüyor
4. ✅ `emit_task()` çalışan örneği var
5. ✅ SDK unit testleri yazıldı ve geçiyor
6. ✅ `discovery.py` manifest.yml destekliyor
7. ✅ `python -m archiverr` hatasız çalışıyor

## Dokunulmayacaklar:

- ❌ omdb, tvdb, tvmaze pluginleri
- ❌ Event/hook system
- ❌ Capability system
- ❌ expects Jinja2 dönüşümü (mevcut sistem yeterli)

---

# SESSION 10 PART 2 TAMAMLANDI ✅

**Tarih:** 2025-11-28
**Çıktı:** Executable strateji + kod örnekleri

**Durum:** Part 2 (online araştırma) ve Part 3 (plan) BİRLEŞTİRİLDİ.
**Sonraki:** Execution chat için hazır.
