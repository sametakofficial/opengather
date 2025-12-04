# PHASE 7: VALIDATION SYSTEM

```yaml
phase: 7
öncelik: 🟡 ORTA
tahmini_süre: 4-6 saat
bağımlılık: P1-P6
strateji_belgesi: 05_validation_and_testing.md
test_türü: unit + e2e
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P1-P6 tamamlandı
- [ ] Config/Manifest normalizer çalışıyor
- [ ] StageExecutor çalışıyor
- [ ] Unit testler PASS

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Validator: `core/config_validator.py`

```python
# MEVCUT - Basit schema validation
class ConfigValidator:
    def __init__(self):
        self._schema_path = Path("config.schema.json")

    def is_available(self) -> bool:
        return self._schema_path.exists()

    def validate(self, config: dict) -> Tuple[bool, str]:
        # jsonschema kullanarak validate
        pass
```

### 1.2 Sorunlar

1. **Sadece Config:** Manifest validation yok
2. **Error Code Yok:** Generic error messages
3. **Conflict Detection Yok:** Provides çakışması kontrol edilmiyor
4. **Startup Only:** Pre-execution validation yok

---

## 2. HEDEF YAPI

### 2.1 Validation Katmanları

```
┌─────────────────────────────────────────────────────────────┐
│                    VALIDATION KATMANLARI                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  STARTUP (Uygulama başlangıcında)                            │
│  ├── Config schema validation                               │
│  ├── Plugin manifest validation                             │
│  ├── Dependency graph validation                            │
│  ├── Provides conflict detection                            │
│  └── Dynamic variable check (job.*/run.* YASAK)             │
│                                                              │
│  PRE-EXECUTION (Run başlamadan önce)                         │
│  ├── Requires path existence                                │
│  ├── Trigger rule validation                                │
│  ├── Stage assignment validation                            │
│  └── Plugin compatibility check                             │
│                                                              │
│  RUNTIME                                                     │
│  └── KALDIRILDI (v2 kararı - run asla durmasın)             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Error Code Sistemi

```python
# Error Codes
E001 = "E001: Invalid config schema"
E002 = "E002: Missing required config field"
E003 = "E003: Invalid config value type"
E004 = "E004: Environment variable not set"
E005 = "E005: Include file not found"

E011 = "E011: Invalid plugin manifest"
E012 = "E012: Missing required manifest field"
E013 = "E013: Invalid stage value"
E014 = "E014: Plugin dependency not found"
E015 = "E015: Circular dependency detected"
E016 = "E016: Provides conflict detected"
E017 = "E017: Dynamic variable in provides (job.*/run.* YASAK)"

E021 = "E021: Requires not satisfied"
E022 = "E022: Plugin initialization failed"
E023 = "E023: Plugin execution failed"

# Warning Codes
W001 = "W001: Deprecated config field used"
W002 = "W002: Performance warning"
W003 = "W003: Security warning (API key in config)"
W004 = "W004: No input plugins enabled"
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: ValidationResult Dataclass

**Dosya:** `src/archiverr/core/validation/result.py` (YENİ)

```python
"""Validation result types"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class ValidationLevel(Enum):
    FATAL = "fatal"      # Exit immediately
    ERROR = "error"      # Disable component
    WARNING = "warning"  # Log and continue
    INFO = "info"        # Log only


@dataclass
class ValidationError:
    """Single validation error"""
    code: str
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    path: Optional[str] = None  # e.g., "plugins.tmdb.api_key"

    def __str__(self) -> str:
        if self.path:
            return f"[{self.code}] {self.path}: {self.message}"
        return f"[{self.code}] {self.message}"


@dataclass
class ValidationResult:
    """Validation result with errors and warnings"""
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def add_error(self, code: str, message: str, path: str = None,
                  level: ValidationLevel = ValidationLevel.ERROR):
        error = ValidationError(code, message, level, path)
        self.errors.append(error)
        if level in (ValidationLevel.FATAL, ValidationLevel.ERROR):
            self.valid = False

    def add_warning(self, code: str, message: str, path: str = None):
        warning = ValidationError(code, message, ValidationLevel.WARNING, path)
        self.warnings.append(warning)

    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge another result into this one"""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False
        return self

    @classmethod
    def ok(cls) -> 'ValidationResult':
        return cls(valid=True)

    @classmethod
    def fail(cls, code: str, message: str, path: str = None) -> 'ValidationResult':
        result = cls(valid=False)
        result.add_error(code, message, path)
        return result

    def __bool__(self) -> bool:
        return self.valid
```

---

### ADIM 2: ConfigValidator Güncelle

**Dosya:** `src/archiverr/core/validation/config_validator.py` (YENİ)

```python
"""Config validation with error codes"""

from typing import Dict, Any, Optional
from pathlib import Path
import json

from .result import ValidationResult, ValidationLevel


class ConfigValidator:
    """
    Config validation with schema and semantic checks.
    """

    def __init__(self, schema_path: str = "config.schema.json"):
        self._schema_path = Path(schema_path)
        self._schema: Optional[Dict] = None

    def is_available(self) -> bool:
        """Check if schema validation is available"""
        return self._schema_path.exists()

    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate config against schema and semantic rules.

        Args:
            config: Loaded config dict

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult.ok()

        # Schema validation (if available)
        if self.is_available():
            schema_result = self._validate_schema(config)
            result.merge(schema_result)

        # Semantic validation
        semantic_result = self._validate_semantic(config)
        result.merge(semantic_result)

        # Security checks
        security_result = self._check_security(config)
        result.merge(security_result)

        return result

    def _validate_schema(self, config: Dict) -> ValidationResult:
        """Validate against JSON schema"""
        try:
            import jsonschema
        except ImportError:
            result = ValidationResult.ok()
            result.add_warning("W002", "jsonschema not installed, skipping schema validation")
            return result

        result = ValidationResult.ok()

        try:
            with open(self._schema_path) as f:
                schema = json.load(f)

            jsonschema.validate(config, schema)

        except jsonschema.ValidationError as e:
            result.add_error(
                "E001",
                f"Schema validation failed: {e.message}",
                path=".".join(str(p) for p in e.absolute_path)
            )
        except Exception as e:
            result.add_error("E001", f"Schema validation error: {e}")

        return result

    def _validate_semantic(self, config: Dict) -> ValidationResult:
        """Validate semantic rules"""
        result = ValidationResult.ok()

        # Check at least one plugin enabled
        plugins = config.get('_enabled_plugins', [])
        if not plugins:
            result.add_error("E002", "No plugins enabled")

        # Check options structure
        options = config.get('options', {})
        if not isinstance(options, dict):
            result.add_error("E003", "options must be a dict", path="options")

        # Check aliases structure
        aliases = config.get('aliases', {})
        if not isinstance(aliases, dict):
            result.add_error("E003", "aliases must be a dict", path="aliases")

        # Validate alias paths
        for name, path in aliases.items():
            if not path.startswith('job.') and not path.startswith('run.'):
                result.add_warning(
                    "W001",
                    f"Alias '{name}' should start with job. or run.",
                    path=f"aliases.{name}"
                )

        return result

    def _check_security(self, config: Dict) -> ValidationResult:
        """Check for security issues"""
        result = ValidationResult.ok()

        # Check for hardcoded API keys (not env vars)
        plugins = config.get('_plugins', {})
        for name, plugin_config in plugins.items():
            api_key = plugin_config.get('api_key', '')
            if api_key and not api_key.startswith('${'):
                result.add_warning(
                    "W003",
                    f"API key appears to be hardcoded, use ${{ENV_VAR}} instead",
                    path=f"{name}.api_key"
                )

        return result
```

---

### ADIM 3: ManifestValidator Oluştur

**Dosya:** `src/archiverr/core/validation/manifest_validator.py` (YENİ)

```python
"""Plugin manifest validation"""

from typing import Dict, Any, List, Set
from .result import ValidationResult, ValidationLevel


# Valid stage values
VALID_STAGES = {'input', 'parse', 'data', 'output'}

# Valid trigger rules
VALID_TRIGGER_RULES = {'all_success', 'one_success', 'all_done', 'all_fail', 'none_fail'}

# Valid provides prefixes
VALID_PROVIDES_PREFIXES = {'http.', 'fs.', 'state.', 'process.', 'output.', 'custom.'}


class ManifestValidator:
    """
    Plugin manifest validation.
    """

    def validate(self, manifest: Dict[str, Any]) -> ValidationResult:
        """
        Validate single manifest.

        Args:
            manifest: Normalized manifest dict

        Returns:
            ValidationResult
        """
        result = ValidationResult.ok()

        # Required fields
        required = ['name', 'stage', 'class_name']
        for field in required:
            if field not in manifest:
                result.add_error(
                    "E012",
                    f"Missing required field: {field}",
                    path=f"manifest.{field}"
                )

        if not result.valid:
            return result

        # Validate stage
        stage = manifest.get('stage', '')
        if stage not in VALID_STAGES:
            result.add_error(
                "E013",
                f"Invalid stage: {stage}. Must be one of {VALID_STAGES}",
                path="manifest.stage"
            )

        # Validate trigger_rule
        trigger_rule = manifest.get('trigger_rule', 'all_success')
        if trigger_rule not in VALID_TRIGGER_RULES:
            result.add_error(
                "E013",
                f"Invalid trigger_rule: {trigger_rule}",
                path="manifest.trigger_rule"
            )

        # Validate requires format
        for req in manifest.get('requires', []):
            if not req.startswith('job.') and not req.startswith('run.'):
                result.add_warning(
                    "W001",
                    f"Requires '{req}' should have job. or run. prefix",
                    path="manifest.requires"
                )

        # Validate provides - no dynamic variables
        for prov in manifest.get('provides', []):
            if prov.startswith('job.') or prov.startswith('run.'):
                result.add_error(
                    "E017",
                    f"Provides cannot use dynamic variables: {prov}",
                    path="manifest.provides"
                )

        return result

    def validate_all(self, manifests: Dict[str, Dict]) -> ValidationResult:
        """
        Validate all manifests and check for conflicts.

        Args:
            manifests: Dict of {plugin_name: manifest}

        Returns:
            ValidationResult
        """
        result = ValidationResult.ok()

        # Validate each manifest
        for name, manifest in manifests.items():
            manifest_result = self.validate(manifest)
            if not manifest_result.valid:
                for error in manifest_result.errors:
                    error.path = f"{name}.{error.path}" if error.path else name
                result.merge(manifest_result)

        # Check for provides conflicts
        conflict_result = self._check_provides_conflicts(manifests)
        result.merge(conflict_result)

        return result

    def _check_provides_conflicts(self, manifests: Dict[str, Dict]) -> ValidationResult:
        """Check for duplicate provides values"""
        result = ValidationResult.ok()

        provides_map: Dict[str, str] = {}  # provides_value -> plugin_name

        for name, manifest in manifests.items():
            for prov in manifest.get('provides', []):
                if prov in provides_map:
                    existing = provides_map[prov]
                    result.add_error(
                        "E016",
                        f"Provides conflict: '{prov}' declared by both '{existing}' and '{name}'",
                        path=f"{name}.provides"
                    )
                else:
                    provides_map[prov] = name

        return result
```

---

### ADIM 4: DependencyValidator Oluştur

**Dosya:** `src/archiverr/core/validation/dependency_validator.py` (YENİ)

```python
"""Dependency graph validation"""

from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict
from .result import ValidationResult


class DependencyValidator:
    """
    Validate plugin dependencies.

    Checks:
    - Circular dependencies
    - Missing dependencies
    - Topological sort validity
    """

    def validate(self, manifests: Dict[str, Dict]) -> ValidationResult:
        """
        Validate dependency graph.

        Args:
            manifests: Dict of {plugin_name: manifest}

        Returns:
            ValidationResult
        """
        result = ValidationResult.ok()

        # Build dependency graph
        graph = self._build_dependency_graph(manifests)

        # Check for missing dependencies
        missing_result = self._check_missing_deps(graph, set(manifests.keys()))
        result.merge(missing_result)

        # Check for circular dependencies
        circular_result = self._check_circular_deps(graph)
        result.merge(circular_result)

        return result

    def _build_dependency_graph(self, manifests: Dict[str, Dict]) -> Dict[str, Set[str]]:
        """Build dependency graph from requires"""
        graph = defaultdict(set)

        for name, manifest in manifests.items():
            requires = manifest.get('requires', [])
            for req in requires:
                # Extract plugin name from path: job.plugins.renamer.parsed → renamer
                parts = req.split('.')
                if len(parts) >= 3 and parts[0] == 'job' and parts[1] == 'plugins':
                    dep_plugin = parts[2]
                    graph[name].add(dep_plugin)

        return dict(graph)

    def _check_missing_deps(self, graph: Dict[str, Set[str]],
                            available: Set[str]) -> ValidationResult:
        """Check for dependencies on non-existent plugins"""
        result = ValidationResult.ok()

        for plugin, deps in graph.items():
            for dep in deps:
                if dep not in available:
                    result.add_error(
                        "E014",
                        f"Plugin '{plugin}' depends on unknown plugin '{dep}'",
                        path=f"{plugin}.requires"
                    )

        return result

    def _check_circular_deps(self, graph: Dict[str, Set[str]]) -> ValidationResult:
        """Check for circular dependencies using DFS"""
        result = ValidationResult.ok()

        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> Tuple[bool, List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    found, cycle = dfs(neighbor, path.copy())
                    if found:
                        return True, cycle
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return True, path[cycle_start:] + [neighbor]

            rec_stack.remove(node)
            return False, []

        for node in graph:
            if node not in visited:
                found, cycle = dfs(node, [])
                if found:
                    result.add_error(
                        "E015",
                        f"Circular dependency detected: {' → '.join(cycle)}",
                        level=ValidationLevel.FATAL
                    )
                    break  # One cycle is enough

        return result

    def get_execution_order(self, manifests: Dict[str, Dict]) -> List[str]:
        """
        Get topological execution order.

        Returns:
            List of plugin names in execution order
        """
        graph = self._build_dependency_graph(manifests)

        # Kahn's algorithm for topological sort
        in_degree = defaultdict(int)
        for deps in graph.values():
            for dep in deps:
                in_degree[dep] += 1

        # Start with nodes that have no dependencies
        queue = [n for n in manifests.keys() if in_degree[n] == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)

            for dep in graph.get(node, set()):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        return order
```

---

### ADIM 5: StartupValidator (Ana Validator)

**Dosya:** `src/archiverr/core/validation/startup_validator.py` (YENİ)

```python
"""Startup validation orchestrator"""

from typing import Dict, Any, List
from .result import ValidationResult
from .config_validator import ConfigValidator
from .manifest_validator import ManifestValidator
from .dependency_validator import DependencyValidator


class StartupValidator:
    """
    Orchestrates all startup validations.

    Runs:
    1. Config validation
    2. Manifest validation
    3. Dependency validation
    4. Pre-execution checks
    """

    def __init__(self):
        self._config_validator = ConfigValidator()
        self._manifest_validator = ManifestValidator()
        self._dependency_validator = DependencyValidator()

    def validate_startup(
        self,
        config: Dict[str, Any],
        manifests: Dict[str, Dict]
    ) -> ValidationResult:
        """
        Run all startup validations.

        Args:
            config: Loaded config
            manifests: All plugin manifests

        Returns:
            Combined ValidationResult
        """
        result = ValidationResult.ok()

        # 1. Config validation
        config_result = self._config_validator.validate(config)
        result.merge(config_result)

        # Stop if config is invalid
        if not config_result.valid:
            return result

        # 2. Manifest validation
        manifest_result = self._manifest_validator.validate_all(manifests)
        result.merge(manifest_result)

        # 3. Dependency validation
        dep_result = self._dependency_validator.validate(manifests)
        result.merge(dep_result)

        # 4. Additional startup checks
        additional_result = self._additional_checks(config, manifests)
        result.merge(additional_result)

        return result

    def _additional_checks(
        self,
        config: Dict,
        manifests: Dict[str, Dict]
    ) -> ValidationResult:
        """Additional startup checks"""
        result = ValidationResult.ok()

        # Check for input plugin
        input_plugins = [
            name for name, m in manifests.items()
            if m.get('stage') == 'input'
        ]
        enabled = config.get('_enabled_plugins', [])
        enabled_input = [p for p in input_plugins if p in enabled]

        if not enabled_input:
            result.add_warning(
                "W004",
                "No input plugins enabled - no jobs will be created"
            )

        return result


def validate_at_startup(config: Dict, manifests: Dict[str, Dict]) -> ValidationResult:
    """Convenience function for startup validation"""
    validator = StartupValidator()
    return validator.validate_startup(config, manifests)
```

---

## 4. INTEGRATION WITH ORCHESTRATOR

### 4.1 Orchestrator'da Validation Ekleme

```python
# core/orchestrator.py

from archiverr.core.validation import validate_at_startup

class Orchestrator:
    def _initialize(self) -> None:
        # ... existing code ...

        # Validate before starting
        manifests = self._plugin_registry.get_all_manifests()
        validation = validate_at_startup(self._config, manifests)

        if not validation.valid:
            # Log all errors
            for error in validation.errors:
                self._log("error", str(error))
            raise CriticalError("Validation failed, see errors above")

        # Log warnings
        for warning in validation.warnings:
            self._log("warn", str(warning))

        # ... continue with run ...
```

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests

```python
# tests/unit/core/validation/test_validators.py

import pytest
from archiverr.core.validation import (
    ValidationResult,
    ConfigValidator,
    ManifestValidator,
    DependencyValidator
)


class TestValidationResult:
    def test_ok_result(self):
        result = ValidationResult.ok()
        assert result.valid == True
        assert len(result.errors) == 0

    def test_fail_result(self):
        result = ValidationResult.fail("E001", "Test error")
        assert result.valid == False
        assert len(result.errors) == 1

    def test_merge(self):
        r1 = ValidationResult.ok()
        r1.add_warning("W001", "Warning 1")

        r2 = ValidationResult.fail("E001", "Error 1")

        r1.merge(r2)

        assert r1.valid == False
        assert len(r1.errors) == 1
        assert len(r1.warnings) == 1


class TestManifestValidator:
    @pytest.fixture
    def validator(self):
        return ManifestValidator()

    def test_valid_manifest(self, validator):
        manifest = {
            "name": "test",
            "stage": "data",
            "class_name": "TestPlugin",
            "requires": ["job.plugins.renamer.parsed"],
            "provides": ["state.update"]
        }
        result = validator.validate(manifest)
        assert result.valid == True

    def test_missing_required_field(self, validator):
        manifest = {"name": "test"}  # Missing stage, class_name
        result = validator.validate(manifest)
        assert result.valid == False
        assert any("E012" in e.code for e in result.errors)

    def test_invalid_stage(self, validator):
        manifest = {
            "name": "test",
            "stage": "invalid",
            "class_name": "Test"
        }
        result = validator.validate(manifest)
        assert result.valid == False
        assert any("E013" in e.code for e in result.errors)

    def test_provides_conflict_detection(self, validator):
        manifests = {
            "plugin1": {
                "name": "plugin1",
                "stage": "data",
                "class_name": "P1",
                "provides": ["http.request"]
            },
            "plugin2": {
                "name": "plugin2",
                "stage": "data",
                "class_name": "P2",
                "provides": ["http.request"]  # Conflict!
            }
        }
        result = validator.validate_all(manifests)
        assert any("E016" in e.code for e in result.errors)


class TestDependencyValidator:
    @pytest.fixture
    def validator(self):
        return DependencyValidator()

    def test_no_circular_deps(self, validator):
        manifests = {
            "a": {"name": "a", "requires": ["job.plugins.b.data"]},
            "b": {"name": "b", "requires": []}
        }
        result = validator.validate(manifests)
        assert result.valid == True

    def test_circular_dependency_detected(self, validator):
        manifests = {
            "a": {"name": "a", "requires": ["job.plugins.b.data"]},
            "b": {"name": "b", "requires": ["job.plugins.a.data"]}  # Cycle!
        }
        result = validator.validate(manifests)
        assert result.valid == False
        assert any("E015" in e.code for e in result.errors)

    def test_missing_dependency(self, validator):
        manifests = {
            "a": {"name": "a", "requires": ["job.plugins.nonexistent.data"]}
        }
        result = validator.validate(manifests)
        assert any("E014" in e.code for e in result.errors)
```

---

## 6. PHASE 7 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `ValidationResult` dataclass oluşturuldu
- [ ] `ValidationError` dataclass oluşturuldu
- [ ] `ConfigValidator` error code sistemiyle güncellendi
- [ ] `ManifestValidator` oluşturuldu
- [ ] `DependencyValidator` oluşturuldu
- [ ] Circular dependency detection çalışıyor
- [ ] Provides conflict detection çalışıyor
- [ ] `StartupValidator` orchestrator oluşturuldu
- [ ] Orchestrator entegrasyonu tamamlandı
- [ ] Unit testler PASS
- [ ] E2E testler PASS

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ Runtime validation (v2 kararı: KALDIRILDI)
- ❌ Schema auto-generation
- ❌ Validation cache

---

## 7. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                    | Belirti                  | Çözüm                        |
| ------------------------ | ------------------------ | ---------------------------- |
| jsonschema not installed | Warning, no validation   | pip install jsonschema       |
| False positive circular  | Valid graph rejected     | Graph building logic kontrol |
| Missing manifest field   | E012 error               | Manifest normalizer kontrol  |
| All plugins disabled     | No enabled plugins error | Config kontrol               |
| Provides conflict false  | Same plugin twice        | Plugin registry dedup        |

---

## 8. SONRAKİ PHASE'E GEÇİŞ

Phase 7 tamamlandığında:

1. Git commit: `feat(validation): add comprehensive validation system with error codes`
2. Git tag: `v0.x.x-phase7`
3. `08_PHASE8_FASTAPI.md` dosyasını oku
4. API refactoring'e başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/core/validation/` çalıştır
- Invalid config startup'ta reddediliyor mu test et
- Circular dependency tespit ediliyor mu test et
- Error code'lar doğru mu kontrol et
