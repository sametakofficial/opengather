# PHASE 6: MIGRATION & ORCHESTRATOR

```yaml
öncelik: P3
tahmini_süre: 4-5 saat
bağımlılık: Phase 1-5 (tümü)
hedef: __main__.py simplification, Orchestrator
risk: ORTA (mevcut kod değişiyor)
```

---

## MEVCUT DURUM ANALİZİ

### **main**.py (392 satır)

```python
# MEVCUT YAPILAR
def cli_main():
    # Config load (~20 satır)
    # Debug init (~10 satır)
    # Event bus init (~10 satır)
    # State init (~10 satır)
    # Persistence init (~10 satır)
    # Plugin discovery (~10 satır)
    # Plugin loading (~10 satır)
    # Dependency resolution (~15 satır)
    # Input execution (~20 satır)
    # Output execution loop (~100 satır)  # ← BÜYÜK
    # Task execution (~30 satır)
    # API response build (~30 satır)
    # Report generation (~20 satır)
    # Cleanup (~10 satır)
```

### HEDEF YAPILAR

```python
# __main__.py (~50 satır)
def cli_main():
    config = load_config()
    orchestrator = Orchestrator(config)
    orchestrator.run()

# core/orchestrator.py
class Orchestrator:
    # Tüm koordinasyon burada
```

---

## TASK LİSTESİ

### 6.1 Orchestrator Class Skeleton

**Dosya:** `core/orchestrator.py` (YENİ)

**Ne yapılacak:**

```python
class Orchestrator:
    """
    Central coordinator - tüm execution flow'u yönetir.

    __main__.py'dan taşınan logic burada.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.debugger = None
        self.event_bus = None
        self.state = None
        self.persistence = None
        self.plugins = {}

    def setup(self):
        """Initialize all components"""
        pass

    def run(self) -> str:
        """Execute full run, return run_id"""
        pass

    def teardown(self):
        """Cleanup"""
        pass
```

---

### 6.2 Component Initialization

**Dosya:** `core/orchestrator.py`

**Nerede:** `setup` method içinde

**Ne yapılacak:**

```python
def setup(self):
    """Initialize all components in order"""

    # 1. Debug
    debug = self.config.get('options', {}).get('debug', False)
    self.debugger = init_debugger(enabled=debug)

    # 2. Event Bus
    self.event_bus = EventBus(debugger=self.debugger)
    self._register_event_handlers()

    # 3. State Manager
    self.state = StateManager()

    # 4. Persistence
    db_connection = DatabaseConnection.from_env()
    self.persistence = db_connection.connect()

    # 5. Configure State
    self.state.configure(
        persistence=self.persistence,
        debugger=self.debugger,
        event_bus=self.event_bus
    )

    # 6. Plugin Discovery
    self._discover_plugins()

    # 7. Validation
    self._validate_startup()
```

**Kaynak:** `__main__.py` lines 92-163

---

### 6.3 Plugin Discovery Integration

**Dosya:** `core/orchestrator.py`

**Nerede:** `_discover_plugins` method

**Ne yapılacak:**

```python
def _discover_plugins(self):
    """Discover and load plugins"""
    discovery = PluginDiscovery()
    self.all_plugins = discovery.discover()

    # Load enabled plugins
    loader = PluginLoader(self.all_plugins, self.config)

    # Group by stage (yeni sistem)
    self.stage_executor = StageExecutor(
        self.state,
        self.event_bus,
        self.config
    )
    self.plugins_by_stage = self.stage_executor.group_plugins_by_stage(
        self.all_plugins
    )

    self.debugger.info("orchestrator", "Plugins discovered",
                       total=len(self.all_plugins))
```

---

### 6.4 Validation Integration

**Dosya:** `core/orchestrator.py`

**Nerede:** `_validate_startup` method

**Ne yapılacak:**

```python
def _validate_startup(self):
    """Run startup validation"""
    from archiverr.core.validators import ValidationPipeline, display_validation_result

    pipeline = ValidationPipeline()
    result = pipeline.validate_startup(self.config, self.all_plugins)

    if not result.valid:
        display_validation_result(result)

        force = self.config.get('options', {}).get('force_conflicts', False)
        if not force:
            raise ValidationError("Startup validation failed")

        self.debugger.warn("orchestrator", "Validation failed but --force enabled")
```

---

### 6.5 Run Method (Main Execution)

**Dosya:** `core/orchestrator.py`

**Nerede:** `run` method

**Ne yapılacak:**

```python
def run(self) -> str:
    """
    Execute full run.

    Returns:
        run_id
    """
    try:
        # 1. Setup (if not done)
        if not self.debugger:
            self.setup()

        # 2. Execute via StageExecutor
        run_id = self.stage_executor.execute_run(self.loaded_plugins)

        # 3. Generate reports
        self._generate_reports(run_id)

        return run_id

    finally:
        self.teardown()
```

**Kaynak:** `__main__.py` lines 164-346

---

### 6.6 Report Generation

**Dosya:** `core/orchestrator.py`

**Nerede:** `_generate_reports` method

**Ne yapılacak:**

```python
def _generate_reports(self, run_id: str):
    """Generate API response and reports"""
    from archiverr.core.reports import generate_dual_reports
    from archiverr.models import APIResponseBuilder

    # Build API response from state
    api_response = self.state.build_api_response_for_templates()

    # Add additional info
    api_response['globals']['run_id'] = run_id

    # Generate files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_paths = generate_dual_reports(
        api_response,
        timestamp,
        debugger=self.debugger
    )

    self.debugger.info("orchestrator", "Reports generated",
                       full=report_paths['full'],
                       compact=report_paths['compact'])
```

---

### 6.7 Teardown Method

**Dosya:** `core/orchestrator.py`

**Nerede:** `teardown` method

**Ne yapılacak:**

```python
def teardown(self):
    """Cleanup resources"""
    # Complete run in state
    if self.state and self.state.execution:
        self.state.complete_run()

    # Disconnect persistence
    if hasattr(self, '_db_connection') and self._db_connection:
        self._db_connection.disconnect()

    self.debugger.debug("orchestrator", "Teardown complete")
```

---

### 6.8 Simplified **main**.py

**Dosya:** `__main__.py`

**Ne yapılacak:**

```python
# YENI __main__.py (~50 satır)

def cli_main():
    """CLI entry point - simplified"""
    config_path = Path("config.yml")

    if not config_path.exists():
        print("ERROR: config.yml not found", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config_with_tracking(str(config_path))
    except Exception as e:
        print(f"ERROR: Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    # NEW: Orchestrator handles everything
    orchestrator = Orchestrator(config)

    try:
        run_id = orchestrator.run()
        print(f"Run completed: {run_id}")
    except ValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Execution error: {e}", file=sys.stderr)
        sys.exit(1)
```

**NOT:** Bu değişiklik SONRA yapılacak, önce Orchestrator test edilecek

---

### 6.9 Plugin Manifest Migration Script

**Dosya:** `scripts/migrate_manifests.py` (YENİ)

**Ne yapılacak:**

```python
"""Plugin manifest migration: category → stage"""

import yaml
from pathlib import Path

CATEGORY_TO_STAGE = {
    'input': 'input',
    'output': 'output',  # default, manual güncelleme gerekebilir
}

def migrate_manifest(manifest_path: Path):
    """Single manifest migration"""
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    # Skip if already has stage
    if 'stage' in manifest:
        return False

    # Migrate category → stage
    if 'category' in manifest:
        category = manifest['category']
        manifest['stage'] = CATEGORY_TO_STAGE.get(category, 'output')
        # Keep category for backward compat

    # Migrate depends_on + expects → requires
    requires = []
    for dep in manifest.get('depends_on', []):
        requires.append(f"provides.state.update")
    for exp in manifest.get('expects', []):
        requires.append(f"job.{exp}")

    if requires:
        manifest['requires'] = requires

    # Add new fields with defaults
    manifest.setdefault('trigger_rule', 'all_success')
    manifest.setdefault('reactive', False)
    manifest.setdefault('entry_point', 'client.py')

    # Write back
    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False)

    return True

if __name__ == '__main__':
    plugins_dir = Path('src/archiverr/plugins')
    for manifest in plugins_dir.glob('*/manifest.yml'):
        if migrate_manifest(manifest):
            print(f"Migrated: {manifest}")
```

---

### 6.10 Unit/Integration Tests

**Dosya:** `tests/integration/test_orchestrator.py` (YENİ)

**Ne yapılacak:**

```
Test cases:
1. test_orchestrator_setup
2. test_orchestrator_run_minimal
3. test_orchestrator_validation_failure
4. test_orchestrator_force_validation
5. test_orchestrator_teardown
6. test_orchestrator_report_generation
7. test_full_e2e_with_mock_plugins
8. test_migration_script
```

---

## BAĞIMLILIK GRAFİ

```
6.1 Orchestrator Skeleton
     │
     ├──→ 6.2 Component Init
     │         │
     │         └──→ 6.3 Plugin Discovery
     │                   │
     │                   └──→ 6.4 Validation
     │
     └──→ 6.5 Run Method
              │
              ├──→ 6.6 Report Generation
              │
              └──→ 6.7 Teardown

6.5 Orchestrator Ready ──→ 6.8 Simplified __main__.py

6.9 Migration Script (paralel)

6.8 + 6.9 ──→ 6.10 Tests
```

---

## MIGRATION STRATEJİSİ

### Aşama 1: Orchestrator Parallel Development

```
__main__.py (MEVCUT) ─────────────────→ ÇALIŞMAYA DEVAM
                                              ↑
core/orchestrator.py (YENİ) ── test ──→ HAZIR OLDUĞUNDA SWITCH
```

### Aşama 2: Switch

```python
# __main__.py değişikliği
# ESKİ: cli_main() içinde 300+ satır
# YENİ: Orchestrator(config).run()
```

### Aşama 3: Plugin Migration

```bash
# Her plugin için (tek tek)
python scripts/migrate_manifests.py --plugin tmdb
pytest tests/plugins/test_tmdb.py
```

---

## TAMAMLAMA KRİTERİ

Phase 6 TAMAMLANDI sayılır eğer:

- [ ] Orchestrator class implement edildi
- [ ] Tüm **main**.py logic'i Orchestrator'a taşındı
- [ ] **main**.py ~50 satıra indi
- [ ] Migration script çalışıyor
- [ ] En az 1 plugin migrate edildi (test için)
- [ ] E2E test geçiyor
- [ ] Mevcut functionality KORUNDU

---

## SONRASI: POST-MIGRATION

Phase 6 sonrası yapılacaklar (ayrı session):

1. **Tüm pluginlerin migration'ı**

   - scanner → stage: input
   - renamer → stage: parse
   - tmdb, tvdb, ffprobe → stage: data
   - tasker → stage: output

2. **Memory Management implementasyonu**

   - MemoryTracker
   - FlushManager
   - LazyLoader

3. **PluginServices tam implementasyonu**
   - StateService
   - EventService
   - FileSystemService
   - HTTPService

---

**SESSION 11 TODO LİSTESİ SONU**
