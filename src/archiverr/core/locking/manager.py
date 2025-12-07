"""
FS Lock Manager - Session 12

Manages file system locks for plugins:
- Validates static paths at startup
- Tracks locked paths per plugin
- Prevents concurrent access to same paths
- Detects conflicts between plugins
"""

from typing import Dict, List, Set, Tuple, Optional
from threading import Lock
from .validator import FSLockValidator


class FSLockManager:
    """
    Session 12 FS Lock Manager.
    
    Manages file system locks to prevent plugins from accessing
    the same paths concurrently.
    
    Features:
    - Startup validation (all paths must be static)
    - Lock acquisition with conflict detection
    - Lock release
    - Query which plugins are locking paths
    
    Usage:
        manager = FSLockManager()
        
        # Validate at startup
        is_valid, errors = manager.validate_all_manifests(manifests)
        
        # Acquire locks
        success, conflicts = manager.acquire_lock("tasker", ["/srv/archive"])
        
        # Release locks
        manager.release_lock("tasker")
    """
    
    def __init__(self):
        self.validator = FSLockValidator()
        
        # Plugin name -> set of locked paths
        self._locks: Dict[str, Set[str]] = {}
        
        # Path -> plugin name (for quick lookup)
        self._path_owners: Dict[str, str] = {}
        
        # Thread safety
        self._lock = Lock()
    
    def validate_all_manifests(
        self,
        manifests: Dict[str, dict]
    ) -> Tuple[bool, List[str]]:
        """
        Validate fs_lock paths in all manifests (startup check).
        
        Args:
            manifests: Dict of plugin_name -> manifest
            
        Returns:
            (all_valid, errors) tuple
        """
        all_errors = []
        
        for plugin_name, manifest in manifests.items():
            is_valid, errors = self.validator.validate_manifest(manifest)
            if not is_valid:
                for error in errors:
                    all_errors.append(f"{plugin_name}: {error}")
        
        return len(all_errors) == 0, all_errors
    
    def acquire_lock(
        self,
        plugin_name: str,
        paths: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Acquire locks for paths.
        
        Args:
            plugin_name: Plugin requesting locks
            paths: List of paths to lock
            
        Returns:
            (success, conflicts) tuple
            
        Examples:
            success, conflicts = manager.acquire_lock("tasker", ["/srv/archive"])
            if not success:
                print(f"Conflicts: {conflicts}")
        """
        with self._lock:
            conflicts = []
            
            # Check for conflicts
            for path in paths:
                if path in self._path_owners:
                    owner = self._path_owners[path]
                    if owner != plugin_name:
                        conflicts.append(f"{path} locked by {owner}")
            
            if conflicts:
                return False, conflicts
            
            # Acquire locks
            if plugin_name not in self._locks:
                self._locks[plugin_name] = set()
            
            for path in paths:
                self._locks[plugin_name].add(path)
                self._path_owners[path] = plugin_name
            
            return True, []
    
    def release_lock(self, plugin_name: str) -> None:
        """
        Release all locks for a plugin.
        
        Args:
            plugin_name: Plugin releasing locks
        """
        with self._lock:
            if plugin_name not in self._locks:
                return
            
            # Remove from path_owners
            for path in self._locks[plugin_name]:
                if path in self._path_owners:
                    del self._path_owners[path]
            
            # Remove plugin locks
            del self._locks[plugin_name]
    
    def is_path_locked(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if path is locked.
        
        Args:
            path: File system path
            
        Returns:
            (is_locked, owner_plugin) tuple
        """
        with self._lock:
            if path in self._path_owners:
                return True, self._path_owners[path]
            return False, None
    
    def get_locked_paths(self, plugin_name: str) -> Set[str]:
        """
        Get all paths locked by a plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Set of locked paths
        """
        with self._lock:
            return self._locks.get(plugin_name, set()).copy()
    
    def get_all_locks(self) -> Dict[str, Set[str]]:
        """
        Get all current locks.
        
        Returns:
            Dict of plugin_name -> set of paths
        """
        with self._lock:
            return {
                plugin: paths.copy()
                for plugin, paths in self._locks.items()
            }
    
    def detect_conflicts(
        self,
        manifests: Dict[str, dict]
    ) -> List[str]:
        """
        Detect potential conflicts between plugin fs_lock declarations.
        
        This checks if multiple plugins declare locks on the same paths.
        
        Args:
            manifests: Dict of plugin_name -> manifest
            
        Returns:
            List of conflict descriptions
        """
        path_plugins: Dict[str, List[str]] = {}
        
        # Collect all path -> plugin mappings
        for plugin_name, manifest in manifests.items():
            fs_lock = manifest.get('fs_lock', [])
            for path in fs_lock:
                if path not in path_plugins:
                    path_plugins[path] = []
                path_plugins[path].append(plugin_name)
        
        # Find conflicts (paths used by multiple plugins)
        conflicts = []
        for path, plugins in path_plugins.items():
            if len(plugins) > 1:
                conflicts.append(
                    f"Path {path} declared by multiple plugins: {', '.join(plugins)}"
                )
        
        return conflicts
    
    def reset(self) -> None:
        """Reset all locks (for testing)."""
        with self._lock:
            self._locks.clear()
            self._path_owners.clear()
