"""
Requires Validator - Plugin dependency validation

- Phase 5: Validates that plugin requirements are satisfied
before execution.

REQUIRES PREFIX SYSTEM (FINAL_DATASETS.yml / 10_STANDARD_TERMS.md):
- job.*       → State path (job.plugins.renamer.parsed)
- provides.*  → Provide completion (provides.http.request)
- events.*    → Event fired (events.plugin.completed)

PREFIX IS MANDATORY - implicit parsing rejected.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Protocol

if TYPE_CHECKING:
    from archiverr.core.provides_registry import ProvidesRegistry
    from archiverr.events import EventBus


class PluginDataProvider(Protocol):
    """Protocol for getting plugin data"""
    def get_plugin_data(self, job_id: str, plugin_name: str) -> dict[str, Any]:
        ...


@dataclass
class RequiresResult:
    """
    Result of requires validation.
    
    P1.1: Enhanced for trigger_rule support.
    
    Attributes:
        satisfied: True if all requirements are met (for backward compat)
        missing: List of missing requirement paths
        success_count: Number of satisfied requires
        failed_count: Number of failed requires
        total_count: Total number of requires
    """
    satisfied: bool
    missing: list[str]
    success_count: int = 0
    failed_count: int = 0
    total_count: int = 0

    def __bool__(self) -> bool:
        return self.satisfied

    def check_trigger_rule(self, rule: str = 'all_success') -> bool:
        """
        Check if trigger rule is satisfied.
        
        P1.1: Full trigger_rule implementation.
        
        Args:
            rule: Trigger rule (all_success, one_success, all_done, all_fail, none_fail)
            
        Returns:
            True if rule is satisfied, False otherwise
        """
        if self.total_count == 0:
            # No requires = always satisfied
            return True

        if rule == 'all_success':
            return self.success_count == self.total_count
        elif rule == 'one_success':
            return self.success_count >= 1
        elif rule == 'all_done':
            return (self.success_count + self.failed_count) == self.total_count
        elif rule == 'all_fail':
            return self.failed_count == self.total_count
        elif rule == 'none_fail':
            return self.failed_count == 0
        else:
            # Unknown rule, default to all_success
            return self.success_count == self.total_count


class RequiresValidator:
    """
    Validates plugin requirements before execution.
    
    Checks that all required data paths exist in job state,
    provides registry, or event bus before allowing a plugin to execute.
    
    REQUIRES PREFIX SYSTEM:
        - job.*       → State path (job.plugins.renamer.parsed)
        - provides.*  → Provide completion (provides.http.request)
        - events.*    → Event fired (events.plugin.completed)
    
    Usage:
        validator = RequiresValidator(provides_registry, event_bus)
        
        result = validator.validate(job, requires, plugin_cache)
        if not result.satisfied:
            print(f"Missing: {result.missing}")
            skip_plugin()
    """

    def __init__(
        self,
        provides_registry: Optional['ProvidesRegistry'] = None,
        event_bus: Optional['EventBus'] = None
    ):
        """
        Initialize validator with optional registries.
        
        Args:
            provides_registry: ProvidesRegistry for provides.* validation
            event_bus: EventBus for events.* validation
        """
        self._provides_registry = provides_registry
        self._event_bus = event_bus

    def validate(
        self,
        job: Any,  # JobState
        requires: list[str],
        plugin_data: dict[str, dict[str, Any]] | None = None
    ) -> RequiresResult:
        """
        Validate all requires paths exist.
        
        Args:
            job: JobState instance
            requires: List of required paths (must have prefix)
            plugin_data: Optional dict of plugin_name -> data (for testing/cache)
            
        Returns:
            RequiresResult with satisfaction status and missing paths
        """
        if not requires:
            return RequiresResult(satisfied=True, missing=[], total_count=0)

        # P1.1: Track success/failed/total for trigger_rule
        missing = []
        success_count = 0
        failed_count = 0

        for path in requires:
            if self._check_requirement(job, path, plugin_data or {}):
                success_count += 1
            else:
                missing.append(path)
                failed_count += 1

        return RequiresResult(
            satisfied=(len(missing) == 0),
            missing=missing,
            success_count=success_count,
            failed_count=failed_count,
            total_count=len(requires)
        )

    def _check_requirement(
        self,
        job: Any,
        path: str,
        plugin_data: dict[str, dict[str, Any]]
    ) -> bool:
        """
        Check if a requirement is satisfied based on its prefix.
        
        Args:
            job: JobState instance
            path: Requirement path with prefix
            plugin_data: Dict of plugin_name -> data
            
        Returns:
            True if requirement is satisfied
        """
        parts = path.split('.')
        if len(parts) < 2:
            return False

        prefix = parts[0]

        if prefix == 'job':
            return self._check_job_path(job, parts[1:], plugin_data)
        elif prefix == 'provides':
            return self._check_provides_path(parts[1:])
        elif prefix == 'events':
            return self._check_events_path(parts[1:])
        else:
            # Unknown prefix - log warning but treat as failed
            return False

    def _check_provides_path(self, path_parts: list[str]) -> bool:
        """
        Check if a provide is completed.
        
        Path format: provides.http.request → path_parts = ['http', 'request']
        """
        if not self._provides_registry:
            return False

        # Reconstruct provide value (e.g., 'http.request')
        provide = '.'.join(path_parts)
        return self._provides_registry.is_completed(provide)

    def _check_events_path(self, path_parts: list[str]) -> bool:
        """
        Check if an event has been fired.
        
        Path format: events.plugin.completed → path_parts = ['plugin', 'completed']
        """
        if not self._event_bus:
            return False

        # Reconstruct event name (e.g., 'plugin.completed')
        event_name = '.'.join(path_parts)
        return self._event_bus.has_fired(event_name)

    def _check_job_path(
        self,
        job: Any,
        path_parts: list[str],
        plugin_data: dict[str, dict[str, Any]]
    ) -> bool:
        """
        Check if a job state path exists.
        
        Path format: job.plugins.renamer.parsed → path_parts = ['plugins', 'renamer', 'parsed']
        """
        if not path_parts:
            return False

        root = path_parts[0]
        remaining = path_parts[1:]

        if root == 'plugins':
            return self._check_plugin_path(remaining, plugin_data)
        elif root == 'input':
            return self._check_object_path(job.input, remaining)
        elif root == 'output':
            return self._check_object_path(job.output, remaining)
        elif root == 'status':
            return self._check_object_path(job.status, remaining)
        elif root == 'id':
            return job.id is not None and job.id != ""
        elif root == 'run_id':
            return job.run_id is not None and job.run_id != ""
        elif root == 'index':
            return job.index is not None

        return False

    def _check_plugin_path(
        self,
        path_parts: list[str],
        plugin_data: dict[str, dict[str, Any]]
    ) -> bool:
        """
        Check path in plugin data.
        
        Path format: [plugin_name, ...rest]
        Example: ["renamer", "parsed", "movie"] for job.plugins.renamer.parsed.movie
        """
        if len(path_parts) < 1:
            return False

        plugin_name = path_parts[0]
        remaining = path_parts[1:]

        if plugin_name not in plugin_data:
            return False

        data = plugin_data[plugin_name]

        if not remaining:
            return data is not None

        return self._navigate_dict(data, remaining) is not None

    def _check_object_path(self, obj: Any, path_parts: list[str]) -> bool:
        """Check path exists in object (supports both attr and dict access)"""
        if not path_parts:
            return obj is not None

        current = obj
        for part in path_parts:
            if current is None:
                return False

            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False

        return current is not None

    def _navigate_dict(self, data: dict[str, Any], path_parts: list[str]) -> Any | None:
        """Navigate dict by path parts, return value or None"""
        current = data
        for part in path_parts:
            if not isinstance(current, dict):
                return None
            if part not in current:
                return None
            current = current[part]
        return current

    def extract_plugin_names(self, requires: list[str]) -> list[str]:
        """
        Extract plugin names from requires paths.
        
        Useful for dependency ordering.
        
        Args:
            requires: List of requires paths
            
        Returns:
            List of unique plugin names required
        """
        plugins = set()
        for path in requires:
            parts = path.split('.')
            if len(parts) >= 3 and parts[0] == 'job' and parts[1] == 'plugins':
                plugins.add(parts[2])
        return list(plugins)
