"""
Value Matcher -

Matches state values against requirements with:
- Plugin path validation (success/fail semantics)
- Non-plugin path validation (exact value only)
- Nested path resolution
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from archiverr.events import EventBus


class ValueMatcher:
    """
    value matcher.
    
    Critical rule:
    - Plugin paths (plugin.* or plugins.*): Can use :success or :fail
    - Non-plugin paths: Only exact value matching allowed
    
    Examples:
        plugin.tmdb.data.movie:success  -> Check plugin.tmdb.status.success
        plugin.tmdb.data.title:"Inception" -> Check plugin.tmdb.data.title == "Inception"
        job.input.value:"/path/file.mkv" -> Check job.input.value == "/path/file.mkv"
    """

    @staticmethod
    def parse_requirement(requirement: str) -> tuple[str, str | None]:
        """
        Parse requirement into path and check value.
        
        Args:
            requirement: Path with optional :value
            
        Returns:
            (path, check_value) tuple
            
        Examples:
            "plugin.tmdb.data.movie:success" -> ("plugin.tmdb.data.movie", "success")
            "plugin.tmdb.data.title:Inception" -> ("plugin.tmdb.data.title", "Inception")
            "job.input.value" -> ("job.input.value", None)
        """
        if ':' in requirement:
            parts = requirement.split(':', 1)
            return parts[0].strip(), parts[1].strip()
        return requirement.strip(), None

    @staticmethod
    def is_plugin_path(path: str) -> bool:
        """
        Check if path is a plugin path.
        
        Plugin paths start with:
        - plugin.
        - plugins.
        
        Args:
            path: State path
            
        Returns:
            True if plugin path
        """
        return path.startswith('plugin.') or path.startswith('plugins.')

    @staticmethod
    def validate_requirement(requirement: str) -> tuple[bool, str | None]:
        """
        Validate requirement syntax.
        
        rules:
        - Plugin paths: Can use :success or :fail
        - Non-plugin paths: Can only use exact values (no :success/:fail)
        
        Args:
            requirement: Requirement string
            
        Returns:
            (is_valid, error_message) tuple
        """
        path, check_value = ValueMatcher.parse_requirement(requirement)

        # No check value is always valid
        if check_value is None:
            return True, None

        is_plugin = ValueMatcher.is_plugin_path(path)

        # Plugin paths: success/fail allowed
        if is_plugin:
            return True, None

        # Provides paths: completed/pending/failed allowed
        if path.startswith('provides.') and check_value in ('completed', 'pending', 'failed'):
            return True, None

        # Events paths: only :fired allowed
        if path.startswith('events.'):
            if check_value == 'fired':
                return True, None
            return False, (
                f"Event requirements only support ':fired' (got {check_value!r}). "
                f"Use 'events.<name>:fired' or 'events.<name>' (existence implies fired)."
            )

        # Non-plugin, non-provides paths: success/fail forbidden
        if check_value in ('success', 'fail'):
            return False, (
                f"Success/fail semantics only allowed for plugin paths. "
                f"Path '{path}' is not a plugin path. "
                f"Use exact value matching instead."
            )

        return True, None

    @staticmethod
    def resolve_value(state: dict[str, Any], path: str) -> tuple[bool, Any]:
        """
        Resolve value from state using dot notation.
        
        Args:
            state: Global state dict
            path: Dot-notation path (e.g., "plugin.tmdb.data.movie")
            
        Returns:
            (found, value) tuple
        """
        parts = path.split('.')
        current = state

        try:
            for part in parts:
                if isinstance(current, dict):
                    if part not in current:
                        return False, None
                    current = current[part]
                else:
                    return False, None

            return True, current

        except (KeyError, TypeError, AttributeError):
            return False, None

    @staticmethod
    def check_plugin_status(
        state: dict[str, Any],
        path: str,
        check_value: str
    ) -> tuple[bool, bool]:
        """
        Check plugin status (success/fail).
        
        Status moved to job.status.plugins.{name}
        For :success check, we verify:
        1. Plugin data exists at the path
        2. Plugin status in job.status.plugins.{name}.success
        
        Args:
            state: Global state dict
            path: Plugin data path (e.g., "plugin.renamer.parsed")
            check_value: "success" or "fail"
            
        Returns:
            (found, matches) tuple
        """
        # Extract plugin name from path
        # plugin.renamer.parsed -> renamer
        parts = path.split('.')

        if len(parts) < 2:
            return False, False

        plugin_name = parts[1]  # e.g., "renamer" from "plugin.renamer.parsed"

        # Check if plugin data exists at the path
        data_found, data_value = ValueMatcher.resolve_value(state, path)

        if not data_found or data_value is None:
            # Data doesn't exist - requirement not met
            return True, False

        # Check job.status.plugins.{name}.success
        status_path = f"job.status.plugins.{plugin_name}.success"
        found, status_value = ValueMatcher.resolve_value(state, status_path)

        if found:
            # Status found in job.status.plugins
            if check_value == 'success':
                return True, bool(status_value)
            elif check_value == 'fail':
                return True, not bool(status_value)

        # Fallback: Check old format plugin.{name}.status.success (backward compat)
        old_status_path = f"plugin.{plugin_name}.status.success"
        found, status_value = ValueMatcher.resolve_value(state, old_status_path)

        if found:
            if check_value == 'success':
                return True, bool(status_value)
            elif check_value == 'fail':
                return True, not bool(status_value)

        # Data exists but no status - consider it success if data is not empty
        if check_value == 'success':
            return True, bool(data_value)
        elif check_value == 'fail':
            return True, not bool(data_value)

        return False, False

    @staticmethod
    def check_provides_status(
        state: dict[str, Any],
        path: str,
        check_value: str
    ) -> tuple[bool, bool]:
        """
        Check provides status from global state.

        Provides data in state: {'provides': {'http.request': {'tmdb': 'completed', ...}}}
        Path format: provides.{capability} (e.g., provides.http.request)
        Check value: 'completed', 'pending', or 'failed'

        For :completed -- true if ANY plugin completed this provide.
        For :pending -- true if ALL plugins are still pending.
        For :failed -- true if ANY plugin failed this provide.

        Args:
            state: Global state dict (must contain 'provides' key)
            path: provides.{capability} path
            check_value: 'completed', 'pending', or 'failed'

        Returns:
            (found, matches) tuple
        """
        # Extract capability from path: provides.http.request -> http.request
        capability = path[len('provides.'):]
        if not capability:
            return False, False

        # Resolve provides data from state
        provides_data = state.get('provides', {})
        if not isinstance(provides_data, dict):
            return False, False

        plugin_statuses = provides_data.get(capability)
        if plugin_statuses is None:
            return True, False  # Capability not registered

        if not isinstance(plugin_statuses, dict) or not plugin_statuses:
            return True, False

        status_values = list(plugin_statuses.values())

        if check_value == 'completed':
            return True, any(s == 'completed' for s in status_values)
        elif check_value == 'pending':
            return True, all(s == 'pending' for s in status_values)
        elif check_value == 'failed':
            return True, any(s == 'failed' for s in status_values)

        return False, False

    @staticmethod
    def match(
        state: dict[str, Any],
        requirement: str,
        *,
        event_bus: 'EventBus | None' = None,
    ) -> tuple[bool, bool, str | None]:
        """
        Match requirement against state.

        Args:
            state: Global state dict
            requirement: Requirement string
            event_bus: Optional EventBus for ``events.*:fired`` resolution.
                When omitted, ``events.*`` requirements report a missing-
                context error rather than silently passing.

        Returns:
            (is_valid, matches, error) tuple

        Examples:
            plugin.tmdb.data.movie:success -> Check if tmdb plugin succeeded
            job.input.value:"/path/file.mkv" -> Check if input value matches
            plugin.tmdb.data.title:"Inception" -> Check exact value
            events.run.started:fired -> Check if RUN_STARTED has been emitted
        """
        # Validate requirement
        is_valid, error = ValueMatcher.validate_requirement(requirement)
        if not is_valid:
            return False, False, error

        # Parse requirement
        path, check_value = ValueMatcher.parse_requirement(requirement)

        # Events path resolves against the bus, not state. Falls through
        # to existence-only handling when no bus is wired so callers see
        # the configuration error instead of an opaque "not met" reason.
        if path.startswith('events.'):
            event_name = path[len('events.'):]
            if not event_name:
                return False, False, "Empty event name in 'events.' path"
            if event_bus is None:
                return False, False, (
                    f"events.* requirement '{requirement}' needs an event_bus; "
                    "the trigger manager was constructed without one."
                )
            fired = event_bus.has_fired(event_name)
            return True, fired, None

        # No check value - just check existence
        if check_value is None:
            found, _ = ValueMatcher.resolve_value(state, path)
            return True, found, None

        # Plugin path with success/fail check
        is_plugin = ValueMatcher.is_plugin_path(path)
        if is_plugin and check_value in ('success', 'fail'):
            found, matches = ValueMatcher.check_plugin_status(state, path, check_value)
            return True, matches, None

        # Provides path: provides.{capability}:completed/pending/failed
        if path.startswith('provides.') and check_value in ('completed', 'pending', 'failed'):
            found, matches = ValueMatcher.check_provides_status(state, path, check_value)
            return True, matches, None

        # Exact value match
        found, actual_value = ValueMatcher.resolve_value(state, path)

        if not found:
            return True, False, None

        # Compare values
        matches = str(actual_value) == str(check_value)
        return True, matches, None
