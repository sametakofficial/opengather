"""
Validation System - Comprehensive validation for config, manifests, and dependencies

- Phase 7: Startup and pre-execution validation.

Validation Layers:
1. STARTUP: Config schema, plugin manifests, dependency graph, provides conflicts
2. PRE-EXECUTION: Requires paths, trigger rules, stage assignment

Note: Runtime validation is intentionally omitted (v2 decision: run never stops mid-execution)
"""

from .config_validator import ConfigValidator
from .dependency_validator import DependencyValidator
from .error_codes import (
    # Config errors
    E001,
    E002,
    E003,
    E004,
    E005,
    # Manifest errors
    E011,
    E012,
    E013,
    E014,
    E015,
    E016,
    E017,
    # Execution errors
    E021,
    E022,
    E023,
    # Warnings
    W001,
    W002,
    W003,
    W004,
)
from .manifest_validator import ManifestValidator
from .result import (
    ValidationError,
    ValidationLevel,
    ValidationResult,
)
from .startup_validator import StartupValidator, validate_at_startup

__all__ = [
    # Result types
    "ValidationLevel",
    "ValidationError",
    "ValidationResult",
    # Validators
    "ConfigValidator",
    "ManifestValidator",
    "DependencyValidator",
    "StartupValidator",
    # Convenience functions
    "validate_at_startup",
]
