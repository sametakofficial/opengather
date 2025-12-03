# PHASE 5: VALIDATION SYSTEM

```yaml
öncelik: P3
tahmini_süre: 4-5 saat
bağımlılık: Phase 2 (manifest), Phase 4 (executor)
hedef: Conflict detection, validation layers
risk: DÜŞÜK (additive, warning/error only)
```

---

## MEVCUT DURUM ANALİZİ

### Mevcut Validation

```python
# core/config_validator.py
class ConfigValidator:
    validate(config) → (bool, error_msg)
    # JSON Schema bazlı, basit
```

### HEDEF VALIDATION SİSTEMİ

```
STARTUP (config load):
├── Config syntax (YAML valid?)
├── Schema validation (required fields?)
├── Plugin discovery (manifest valid?)
├── Conflict detection (provides çakışma?)
└── Dynamic variable check (job.* yasak)

PRE-EXECUTION (stage başlangıcı):
├── Requires satisfaction (bağımlılıklar hazır?)
└── Plugin initialization (class yüklenebilir?)

RUNTIME: YOK (run durmasın)
```

---

## TASK LİSTESİ

### 5.1 ValidationResult Dataclass

**Dosya:** `core/validators/models.py` (YENİ DOSYA)

**Ne yapılacak:**

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class ErrorLevel(Enum):
    FATAL = "fatal"    # Exit
    ERROR = "error"    # Component disable
    WARNING = "warning" # Log and continue
    INFO = "info"      # Just log

@dataclass
class ValidationError:
    level: ErrorLevel
    code: str          # E001, E002, etc.
    message: str
    location: str      # config.yml:15, manifest.yml:3
    suggestion: Optional[str] = None

@dataclass
class ValidationResult:
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    def has_fatal(self) -> bool:
        return any(e.level == ErrorLevel.FATAL for e in self.errors)
```

**FINAL_DATASETS.yml Referansı:**

```yaml
error_codes:
  E001: config file not found
  E002: yaml parse error
  E003: required field missing
  E010: invalid manifest
  E020: conflict detected
  E021: dynamic variable in provides
  W001: unknown field
  W002: parent-child path overlap
```

---

### 5.2 Error Codes Registry

**Dosya:** `core/validators/codes.py` (YENİ)

**Ne yapılacak:**

```python
ERROR_CODES = {
    # Config errors (E00x)
    "E001": "Config file not found",
    "E002": "YAML parse error",
    "E003": "Required field missing",

    # Manifest errors (E01x)
    "E010": "Invalid manifest",
    "E011": "Plugin class not found",
    "E012": "Plugin import failed",

    # Conflict errors (E02x)
    "E020": "Conflict detected",
    "E021": "Dynamic variable in provides",

    # Warnings (W00x)
    "W001": "Unknown field",
    "W002": "Parent-child path overlap",
    "W003": "Generic provides (no path)",
}
```

---

### 5.3 Conflict Detector

**Dosya:** `core/validators/conflict_detector.py` (YENİ)

**Ne yapılacak:**

```python
class ConflictDetector:
    """Provides conflict tespiti"""

    LOCKABLE_PROVIDES = {
        'fs.write', 'fs.delete', 'fs.move',
        'fs.hardlink', 'fs.symlink'
    }

    def __init__(self):
        self._provides_registry = {}  # stage:provide → [plugins]

    def register_plugin(self, plugin_name: str, stage: str,
                        provides: List[str]):
        """Plugin provides'larını kaydet"""
        for provide in provides:
            base, path = self._parse_provide(provide)
            if base in self.LOCKABLE_PROVIDES:
                key = f"{stage}:{base}"
                self._provides_registry.setdefault(key, []).append({
                    'plugin': plugin_name,
                    'path': path
                })

    def detect_conflicts(self) -> List[ValidationError]:
        """Tüm conflict'leri tespit et"""
        conflicts = []
        for key, entries in self._provides_registry.items():
            if len(entries) < 2:
                continue
            # Path overlap kontrolü
            for i, a in enumerate(entries):
                for b in entries[i+1:]:
                    if self._paths_conflict(a['path'], b['path']):
                        conflicts.append(self._create_conflict_error(a, b, key))
        return conflicts
```

**FINAL_DATASETS.yml Referansı:**

```yaml
lockable_provides:
  - fs.write
  - fs.delete
  - fs.move
  - fs.hardlink
  - fs.symlink
```

---

### 5.4 Path Overlap Algorithm

**Dosya:** `core/validators/conflict_detector.py`

**Nerede:** `ConflictDetector` class içinde

**Ne yapılacak:**

```python
def _paths_conflict(self, path_a: Optional[str],
                    path_b: Optional[str]) -> bool:
    """İki path çakışıyor mu?"""
    # Generic provides (path yok)
    if not path_a or not path_b:
        return True  # Potansiyel conflict

    # Tam eşleşme
    if path_a == path_b:
        return True

    # Parent-child (WARNING, error değil)
    if path_a.startswith(path_b + '/') or path_b.startswith(path_a + '/'):
        return True  # W002 olarak işaretlenecek

    return False
```

---

### 5.5 Dynamic Variable Checker

**Dosya:** `core/validators/dynamic_checker.py` (YENİ)

**Ne yapılacak:**

```python
import re

class DynamicVariableChecker:
    """Provides içinde job.*/run.* yasak kontrolü"""

    # Geçerli: {{config.*}}
    # Geçersiz: {{job.*}}, {{run.*}}

    INVALID_PATTERNS = [
        r'\{\{\s*job\.',      # {{job.
        r'\{\{\s*run\.',      # {{run.
    ]

    def check_provides(self, provides: List[str]) -> List[ValidationError]:
        errors = []
        for provide in provides:
            for pattern in self.INVALID_PATTERNS:
                if re.search(pattern, provide):
                    errors.append(ValidationError(
                        level=ErrorLevel.ERROR,
                        code="E021",
                        message=f"Dynamic variable in provides: {provide}",
                        location="manifest.yml",
                        suggestion="Use {{config.*}} or static path"
                    ))
        return errors
```

**PHILOSOPHY.md Referansı:**

```
PROVIDES LOCK ICIN:
  {{config.*}} → GECERLI (startup'ta cozulur)
  {{job.*}}    → GECERSIZ (runtime degeri)
  {{run.*}}    → GECERSIZ (runtime degeri)
```

---

### 5.6 Manifest Validator

**Dosya:** `core/validators/manifest_validator.py` (YENİ)

**Ne yapılacak:**

```python
class ManifestValidator:
    """Manifest schema validation"""

    REQUIRED_FIELDS = ['name', 'version']
    VALID_STAGES = ['input', 'parse', 'data', 'output']
    VALID_TRIGGER_RULES = ['all_success', 'one_success', 'all_done',
                           'all_fail', 'none_fail']

    def validate(self, manifest: Dict) -> ValidationResult:
        errors = []
        warnings = []

        # Required fields
        for field in self.REQUIRED_FIELDS:
            if field not in manifest:
                errors.append(...)

        # Stage validation
        stage = manifest.get('stage') or manifest.get('category')
        if stage and stage not in self.VALID_STAGES + ['input', 'output']:
            errors.append(...)

        # Trigger rule validation
        rule = manifest.get('trigger_rule', 'all_success')
        if rule not in self.VALID_TRIGGER_RULES:
            errors.append(...)

        return ValidationResult(valid=len(errors)==0, errors=errors,
                               warnings=warnings)
```

---

### 5.7 Requires Validator

**Dosya:** `core/validators/requires_validator.py` (YENİ)

**Ne yapılacak:**

```python
class RequiresValidator:
    """Requires prefix validation"""

    VALID_PREFIXES = ['job.', 'provides.', 'events.']

    def validate_requires(self, requires: List[str]) -> List[ValidationError]:
        warnings = []
        for req in requires:
            # Prefix kontrolü
            has_valid_prefix = any(req.startswith(p) for p in self.VALID_PREFIXES)

            if not has_valid_prefix:
                warnings.append(ValidationError(
                    level=ErrorLevel.WARNING,
                    code="W004",
                    message=f"Requires without prefix: {req}",
                    suggestion=f"Use 'job.{req}' or 'provides.{req}'"
                ))

        return warnings
```

**PHILOSOPHY.md Referansı:**

```
HARDCODED YASAK:
  YANLIS: requires: [renamer]
  DOGRU:  requires: [provides.data.parsed]
  DOGRU:  requires: [job.plugins.renamer.parsed]
```

---

### 5.8 Validation Pipeline

**Dosya:** `core/validators/__init__.py`

**Ne yapılacak:**

```python
class ValidationPipeline:
    """Tüm validation'ları sırayla çalıştır"""

    def __init__(self):
        self.manifest_validator = ManifestValidator()
        self.conflict_detector = ConflictDetector()
        self.dynamic_checker = DynamicVariableChecker()
        self.requires_validator = RequiresValidator()

    def validate_startup(self, config: Dict,
                         plugins: Dict) -> ValidationResult:
        """Startup validation: config load sonrası"""
        all_errors = []
        all_warnings = []

        # 1. Manifest validation
        for name, meta in plugins.items():
            result = self.manifest_validator.validate(meta)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        # 2. Dynamic variable check
        for name, meta in plugins.items():
            errors = self.dynamic_checker.check_provides(
                meta.get('provides', [])
            )
            all_errors.extend(errors)

        # 3. Conflict detection
        for name, meta in plugins.items():
            self.conflict_detector.register_plugin(
                name,
                meta.get('_effective_stage', 'output'),
                meta.get('provides', [])
            )
        conflicts = self.conflict_detector.detect_conflicts()
        all_errors.extend(conflicts)

        return ValidationResult(
            valid=len([e for e in all_errors if e.level != ErrorLevel.WARNING]) == 0,
            errors=all_errors,
            warnings=all_warnings
        )
```

---

### 5.9 CLI Error Display

**Dosya:** `core/validators/display.py` (YENİ)

**Ne yapılacak:**

```python
def display_validation_result(result: ValidationResult):
    """Validation sonuçlarını CLI'da göster"""

    if result.errors:
        for error in result.errors:
            if error.level == ErrorLevel.FATAL:
                print(f"FATAL [{error.code}]: {error.message}")
            elif error.level == ErrorLevel.ERROR:
                print(f"ERROR [{error.code}]: {error.message}")

            if error.suggestion:
                print(f"  Suggestion: {error.suggestion}")

    if result.warnings:
        for warning in result.warnings:
            print(f"WARNING [{warning.code}]: {warning.message}")

    if result.valid:
        print("✓ Validation passed")
    else:
        print("✗ Validation failed")
```

---

### 5.10 Unit Tests

**Dosya:** `tests/unit/validators/test_validation.py` (YENİ)

**Ne yapılacak:**

```
Test cases:
1. test_validation_result_has_fatal
2. test_error_codes_exist
3. test_conflict_detector_same_path
4. test_conflict_detector_parent_child
5. test_conflict_detector_different_paths_no_conflict
6. test_dynamic_checker_job_variable
7. test_dynamic_checker_config_variable_ok
8. test_manifest_validator_required_fields
9. test_requires_validator_missing_prefix
10. test_validation_pipeline_integration
```

---

## BAĞIMLILIK GRAFİ

```
5.1 ValidationResult
     │
     └──→ 5.2 Error Codes

5.3 ConflictDetector
     │
     └──→ 5.4 Path Overlap Algorithm

5.5 DynamicChecker ─────┐
                        │
5.6 ManifestValidator ──┼──→ 5.8 Validation Pipeline
                        │
5.7 RequiresValidator ──┘
                        │
                        └──→ 5.9 CLI Display
                                  │
                                  └──→ 5.10 Tests
```

---

## **MAIN**.PY ENTEGRASYONU (Opsiyonel)

```python
# __main__.py'da validation ekleme (Phase 6'da)
from archiverr.core.validators import ValidationPipeline

# Plugin discovery sonrası
pipeline = ValidationPipeline()
result = pipeline.validate_startup(config, all_plugins)

if not result.valid and not config.get('options', {}).get('force_conflicts'):
    display_validation_result(result)
    sys.exit(1)
```

---

## TAMAMLAMA KRİTERİ

Phase 5 TAMAMLANDI sayılır eğer:

- [ ] ValidationResult ve ErrorLevel oluşturuldu
- [ ] Error codes registry tanımlandı
- [ ] ConflictDetector çalışıyor
- [ ] DynamicVariableChecker çalışıyor
- [ ] ManifestValidator çalışıyor
- [ ] ValidationPipeline tüm validators'ı birleştiriyor
- [ ] CLI display formatı oluşturuldu
- [ ] Tüm testler geçiyor

---

**SONRAKİ PHASE:** `06_PHASE6_MIGRATION.md`
