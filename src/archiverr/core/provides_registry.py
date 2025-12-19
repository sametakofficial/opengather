"""
Provides Registry - Tracks plugin provides status

Implements the provides tracking system for:
- Tracking which plugins have completed which provides
- Enables requires validation (provides.* prefix)
- Enables early completion (complete_provide)
- Conflict detection for lockable provides

TRUTH SOURCE: HUMAN/FINAL_DATASETS.yml
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any


class ProvideStatus(Enum):
    """Status of a provide."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# Lockable provides - require conflict detection
# Per FINAL_DATASETS.yml lockable_provides
LOCKABLE_PROVIDES: set[str] = {
    'fs.write',
    'fs.delete',
    'fs.move',
    'fs.hardlink',
    'fs.symlink',
}

# Non-lockable provides - can run in parallel
NON_LOCKABLE_PROVIDES: set[str] = {
    'fs.read',
    'fs.copy',
    'fs.mkdir',
    'fs.chmod',
    'http.request',
    'job.create',
    'state.update',
    'process.spawn',
    'process.exec',
    'input.value',
    'input.data',
    'output.values',
    'output.data',
}


@dataclass
class ProvideEntry:
    """Single provide entry."""
    provide: str
    plugin_name: str
    status: ProvideStatus = ProvideStatus.PENDING
    path_constraint: str | None = None  # e.g., fs.write:/srv/media
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'provide': self.provide,
            'plugin_name': self.plugin_name,
            'status': self.status.value,
            'path_constraint': self.path_constraint,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class ProvidesRegistry:
    """
    Registry for tracking plugin provides.
    
    Usage:
        registry = ProvidesRegistry()
        
        # Register provides from plugin manifest
        registry.register("tmdb", "http.request")
        registry.register("tasker", "fs.write:/srv/media")
        
        # Mark as completed
        registry.complete("tmdb", "http.request")
        
        # Check if a provide is completed
        registry.is_completed("http.request")  # True
        
        # Get all provides for template context
        registry.to_dict()  # {'http.request': {'tmdb': 'completed'}, ...}
    """

    def __init__(self):
        self._entries: dict[str, list[ProvideEntry]] = {}  # provide -> [entries]
        self._lock = Lock()

    def register(self, plugin_name: str, provide: str) -> None:
        """
        Register a provide from a plugin.
        
        Args:
            plugin_name: Name of the plugin
            provide: Provide value (e.g., "http.request", "fs.write:/srv/media")
        """
        # Parse provide and path constraint
        base_provide, path_constraint = self._parse_provide(provide)

        entry = ProvideEntry(
            provide=base_provide,
            plugin_name=plugin_name,
            path_constraint=path_constraint,
        )

        with self._lock:
            if base_provide not in self._entries:
                self._entries[base_provide] = []
            self._entries[base_provide].append(entry)

    def register_from_manifest(self, plugin_name: str, provides: list[str]) -> None:
        """
        Register all provides from a plugin manifest.
        
        Args:
            plugin_name: Name of the plugin
            provides: List of provide values from manifest
        """
        for provide in provides:
            self.register(plugin_name, provide)

    def complete(self, plugin_name: str, provide: str) -> None:
        """
        Mark a provide as completed.
        
        Args:
            plugin_name: Name of the plugin
            provide: Provide value (base, without path constraint)
        """
        base_provide, _ = self._parse_provide(provide)

        with self._lock:
            if base_provide in self._entries:
                for entry in self._entries[base_provide]:
                    if entry.plugin_name == plugin_name:
                        entry.status = ProvideStatus.COMPLETED
                        entry.completed_at = datetime.now()
                        break

    def fail(self, plugin_name: str, provide: str) -> None:
        """
        Mark a provide as failed.
        
        Args:
            plugin_name: Name of the plugin
            provide: Provide value
        """
        base_provide, _ = self._parse_provide(provide)

        with self._lock:
            if base_provide in self._entries:
                for entry in self._entries[base_provide]:
                    if entry.plugin_name == plugin_name:
                        entry.status = ProvideStatus.FAILED
                        break

    def complete_all(self, plugin_name: str) -> None:
        """
        Mark all provides from a plugin as completed.
        
        Args:
            plugin_name: Name of the plugin
        """
        with self._lock:
            for entries in self._entries.values():
                for entry in entries:
                    if entry.plugin_name == plugin_name and entry.status == ProvideStatus.PENDING:
                        entry.status = ProvideStatus.COMPLETED
                        entry.completed_at = datetime.now()

    def fail_all(self, plugin_name: str) -> None:
        """
        Mark all provides from a plugin as failed.
        
        Args:
            plugin_name: Name of the plugin
        """
        with self._lock:
            for entries in self._entries.values():
                for entry in entries:
                    if entry.plugin_name == plugin_name and entry.status == ProvideStatus.PENDING:
                        entry.status = ProvideStatus.FAILED

    def is_completed(self, provide: str) -> bool:
        """
        Check if a provide is completed (by any plugin).
        
        Args:
            provide: Provide value (e.g., "http.request")
            
        Returns:
            True if at least one plugin has completed this provide
        """
        base_provide, _ = self._parse_provide(provide)

        with self._lock:
            if base_provide not in self._entries:
                return False

            return any(
                entry.status == ProvideStatus.COMPLETED
                for entry in self._entries[base_provide]
            )

    def is_completed_by(self, provide: str, plugin_name: str) -> bool:
        """
        Check if a specific plugin has completed a provide.
        
        Args:
            provide: Provide value
            plugin_name: Name of the plugin
            
        Returns:
            True if the specific plugin has completed this provide
        """
        base_provide, _ = self._parse_provide(provide)

        with self._lock:
            if base_provide not in self._entries:
                return False

            return any(
                entry.plugin_name == plugin_name and entry.status == ProvideStatus.COMPLETED
                for entry in self._entries[base_provide]
            )

    def get_status(self, provide: str) -> dict[str, str]:
        """
        Get status of a provide from all plugins.
        
        Args:
            provide: Provide value
            
        Returns:
            Dict of plugin_name -> status
        """
        base_provide, _ = self._parse_provide(provide)

        with self._lock:
            if base_provide not in self._entries:
                return {}

            return {
                entry.plugin_name: entry.status.value
                for entry in self._entries[base_provide]
            }

    def get_completed_plugins(self, provide: str) -> list[str]:
        """
        Get list of plugins that have completed a provide.
        
        Args:
            provide: Provide value
            
        Returns:
            List of plugin names
        """
        base_provide, _ = self._parse_provide(provide)

        with self._lock:
            if base_provide not in self._entries:
                return []

            return [
                entry.plugin_name
                for entry in self._entries[base_provide]
                if entry.status == ProvideStatus.COMPLETED
            ]

    def to_dict(self) -> dict[str, dict[str, str]]:
        """
        Convert registry to dict for template context.
        
        Returns:
            Dict structure: {provide: {plugin_name: status, ...}, ...}
            
        Example:
            {
                'http.request': {'tmdb': 'completed', 'tvdb': 'pending'},
                'fs.read': {'scanner': 'completed'},
            }
        """
        with self._lock:
            result = {}
            for provide, entries in self._entries.items():
                result[provide] = {
                    entry.plugin_name: entry.status.value
                    for entry in entries
                }
            return result

    def get_all_entries(self) -> list[ProvideEntry]:
        """Get all entries as list."""
        with self._lock:
            entries = []
            for provide_entries in self._entries.values():
                entries.extend(provide_entries)
            return entries

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """
        Detect conflicts for lockable provides.
        
        Returns:
            List of conflict dicts with provide, plugins, and paths
        """
        conflicts = []

        with self._lock:
            for provide, entries in self._entries.items():
                # Only check lockable provides
                if provide not in LOCKABLE_PROVIDES:
                    continue

                # Check for overlapping paths
                path_plugins: dict[str, list[str]] = {}  # path -> [plugins]

                for entry in entries:
                    path = entry.path_constraint or '*'
                    if path not in path_plugins:
                        path_plugins[path] = []
                    path_plugins[path].append(entry.plugin_name)

                # Detect conflicts
                for path, plugins in path_plugins.items():
                    if len(plugins) > 1:
                        conflicts.append({
                            'provide': provide,
                            'path': path,
                            'plugins': plugins,
                            'severity': 'error',
                        })

                # Check for generic vs specific path conflicts
                if '*' in path_plugins and len(path_plugins) > 1:
                    generic_plugins = path_plugins['*']
                    for path, plugins in path_plugins.items():
                        if path != '*':
                            conflicts.append({
                                'provide': provide,
                                'conflict_type': 'generic_vs_specific',
                                'generic_plugins': generic_plugins,
                                'specific_path': path,
                                'specific_plugins': plugins,
                                'severity': 'warning',
                            })

        return conflicts

    def reset(self) -> None:
        """Reset the registry."""
        with self._lock:
            self._entries.clear()

    def _parse_provide(self, provide: str) -> tuple:
        """
        Parse provide string into base and path constraint.
        
        Args:
            provide: Full provide string (e.g., "fs.write:/srv/media")
            
        Returns:
            Tuple of (base_provide, path_constraint)
        """
        if ':' in provide:
            parts = provide.split(':', 1)
            return parts[0], parts[1]
        return provide, None


# Singleton instance for global access
_provides_registry: ProvidesRegistry | None = None


def get_provides_registry() -> ProvidesRegistry:
    """Get the global provides registry instance."""
    global _provides_registry
    if _provides_registry is None:
        _provides_registry = ProvidesRegistry()
    return _provides_registry


def reset_provides_registry() -> None:
    """Reset the global provides registry."""
    global _provides_registry
    if _provides_registry is not None:
        _provides_registry.reset()
    _provides_registry = None
