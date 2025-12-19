"""
Archiverr Exception Hierarchy

- Phase 4: Orchestrator exceptions for structured error handling.

Exception Levels:
- CriticalError: Stops entire run (config failure, no plugins, db connection failure)
- StageError: Stage failed but run continues (all plugins in stage failed)
- PluginError: Single plugin failed, job may continue (API timeout, parse error)
- ValidationError: Config or manifest validation failed
"""

from typing import Any


class ArchiverrError(Exception):
    """
    Base exception for all Archiverr errors.
    
    All custom exceptions inherit from this to enable:
    - Consistent error handling patterns
    - Easy filtering in exception handlers
    - Structured error context
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            ctx = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for API responses and logging"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "context": self.context
        }


class CriticalError(ArchiverrError):
    """
    Run-stopping critical error.
    
    When raised, the entire run is aborted.
    These are unrecoverable errors that make further execution pointless.
    
    Examples:
    - Config could not be loaded
    - Database connection failed
    - No plugins could be loaded
    - Required environment variable missing
    
    Usage:
        if not config:
            raise CriticalError("Config not found", {"path": "config.yml"})
    """
    pass


class StageError(ArchiverrError):
    """
    Stage execution failed but run can continue.
    
    When raised during a stage, the orchestrator logs the error
    and continues with the next stage (best-effort execution).
    
    Examples:
    - All plugins in a stage failed
    - Dependency resolution failed for stage
    - Stage timeout exceeded
    
    Usage:
        raise StageError("Input stage failed", {"stage": "input", "failed_plugins": 3})
    """

    def __init__(
        self,
        message: str,
        stage: str | None = None,
        context: dict[str, Any] | None = None
    ):
        ctx = context or {}
        if stage:
            ctx["stage"] = stage
        super().__init__(message, ctx)
        self.stage = stage


class PluginError(ArchiverrError):
    """
    Single plugin execution failed.
    
    Job continues with remaining plugins.
    The failed plugin is marked as failed in job status.
    
    Examples:
    - API timeout
    - Parse error
    - Requires not satisfied
    - Plugin runtime exception
    
    Usage:
        raise PluginError(
            "TMDB API timeout",
            plugin_name="tmdb",
            context={"timeout_ms": 5000, "endpoint": "/movie/search"}
        )
    """

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        context: dict[str, Any] | None = None
    ):
        ctx = context or {}
        if plugin_name:
            ctx["plugin"] = plugin_name
        super().__init__(message, ctx)
        self.plugin_name = plugin_name


class ValidationError(ArchiverrError):
    """
    Configuration or manifest validation failed.
    
    Examples:
    - Invalid YAML syntax
    - Missing required field
    - Type mismatch
    - Schema validation failure
    
    Usage:
        raise ValidationError(
            "Missing required field 'api_key'",
            context={"plugin": "tmdb", "field": "api_key"}
        )
    """

    def __init__(
        self,
        message: str,
        errors: list | None = None,
        context: dict[str, Any] | None = None
    ):
        ctx = context or {}
        if errors:
            ctx["validation_errors"] = errors
        super().__init__(message, ctx)
        self.errors = errors or []


class ConfigError(ValidationError):
    """Config file error (subclass of ValidationError)"""
    pass


class ManifestError(ValidationError):
    """Plugin manifest error (subclass of ValidationError)"""
    pass


class DependencyError(ArchiverrError):
    """
    Plugin dependency resolution failed.
    
    Examples:
    - Circular dependency detected
    - Required plugin not found
    - Provides conflict between plugins
    
    Usage:
        raise DependencyError(
            "Circular dependency detected",
            context={"plugins": ["tmdb", "renamer"], "cycle": "tmdb->renamer->tmdb"}
        )
    """
    pass


class RequiresError(PluginError):
    """
    Plugin requires not satisfied.
    
    Special case of PluginError where the plugin was skipped
    because its requires were not met.
    
    Usage:
        raise RequiresError(
            "Missing required data: renamer.parsed",
            plugin_name="tmdb",
            context={"requires": ["renamer.parsed"], "missing": ["renamer.parsed"]}
        )
    """
    pass


class PersistenceError(ArchiverrError):
    """
    Database/persistence operation failed.
    
    Non-critical - the main workflow continues but data may not be persisted.
    
    Examples:
    - Database write failed
    - Connection timeout
    - Document update failed
    
    Usage:
        raise PersistenceError(
            "Failed to save plugin data",
            context={"job_id": "abc123", "plugin": "tmdb"}
        )
    """
    pass


# Backward compatibility - StateError used in some existing code
StateError = StageError
