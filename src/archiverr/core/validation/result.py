"""
Validation Result Types

- Phase 7: Structured validation results.

Provides:
- ValidationLevel: Severity levels (FATAL, ERROR, WARNING, INFO)
- ValidationError: Single validation error with code, message, path
- ValidationResult: Collection of errors/warnings with merge support
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationLevel(Enum):
    """
    Validation error severity levels.
    
    - FATAL: Exit immediately, cannot continue
    - ERROR: Component disabled, but continue with others
    - WARNING: Log and continue normally
    - INFO: Log only, informational
    """
    FATAL = "fatal"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """
    Single validation error or warning.
    
    Attributes:
        code: Error code (e.g., "E001", "W002")
        message: Human-readable error message
        level: Severity level
        path: Optional path to the problematic config/manifest element
        context: Optional additional context for debugging
    """
    code: str
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    path: str | None = None
    context: dict[str, Any] | None = None

    def __str__(self) -> str:
        """Format as [CODE] path: message"""
        if self.path:
            return f"[{self.code}] {self.path}: {self.message}"
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return f"ValidationError({self.code}, {self.message!r}, {self.level.value})"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "code": self.code,
            "message": self.message,
            "level": self.level.value,
        }
        if self.path:
            result["path"] = self.path
        if self.context:
            result["context"] = self.context
        return result


@dataclass
class ValidationResult:
    """
    Validation result with errors and warnings.
    
    Usage:
        result = ValidationResult.ok()
        result.add_error("E001", "Schema invalid")
        result.add_warning("W001", "Deprecated field")
        
        if not result:  # or if not result.valid:
            for error in result.errors:
                print(error)
    """
    valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(
        self,
        code: str,
        message: str,
        path: str | None = None,
        level: ValidationLevel = ValidationLevel.ERROR,
        context: dict[str, Any] | None = None
    ) -> "ValidationResult":
        """
        Add an error to the result.
        
        Sets valid=False for FATAL and ERROR levels.
        Returns self for chaining.
        """
        error = ValidationError(
            code=code,
            message=message,
            level=level,
            path=path,
            context=context
        )
        self.errors.append(error)

        if level in (ValidationLevel.FATAL, ValidationLevel.ERROR):
            self.valid = False

        return self

    def add_warning(
        self,
        code: str,
        message: str,
        path: str | None = None,
        context: dict[str, Any] | None = None
    ) -> "ValidationResult":
        """
        Add a warning to the result.
        
        Warnings don't affect validity.
        Returns self for chaining.
        """
        warning = ValidationError(
            code=code,
            message=message,
            level=ValidationLevel.WARNING,
            path=path,
            context=context
        )
        self.warnings.append(warning)
        return self

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """
        Merge another result into this one.
        
        Combines errors and warnings, updates validity.
        Returns self for chaining.
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

        if not other.valid:
            self.valid = False

        return self

    @classmethod
    def ok(cls) -> "ValidationResult":
        """Create a valid (ok) result."""
        return cls(valid=True)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        path: str | None = None,
        level: ValidationLevel = ValidationLevel.ERROR
    ) -> "ValidationResult":
        """Create a failed result with one error."""
        result = cls(valid=False)
        result.add_error(code, message, path, level)
        return result

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.valid

    def has_fatal(self) -> bool:
        """Check if result contains any FATAL level errors."""
        return any(e.level == ValidationLevel.FATAL for e in self.errors)

    def error_count(self) -> int:
        """Count of errors (FATAL + ERROR levels)."""
        return len([e for e in self.errors if e.level in (ValidationLevel.FATAL, ValidationLevel.ERROR)])

    def warning_count(self) -> int:
        """Count of warnings."""
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
        }

    def format_errors(self) -> list[str]:
        """Get list of formatted error strings."""
        return [str(e) for e in self.errors]

    def format_warnings(self) -> list[str]:
        """Get list of formatted warning strings."""
        return [str(w) for w in self.warnings]
