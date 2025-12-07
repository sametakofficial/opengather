"""
FS Lock Validator - Session 12

Validates fs_lock paths to ensure they are static (no variables).
"""

import re
from typing import List, Tuple


class FSLockValidator:
    """
    Session 12 FS Lock Validator.
    
    Critical rule: fs_lock paths must be static (no variables).
    
    Forbidden patterns:
    - {{ ... }} (Jinja2 templates)
    - ${ ... } (environment variables)
    - $ (shell variables)
    
    Valid examples:
        /srv/archive
        /mnt/media/movies
        /tmp/processing
    
    Invalid examples:
        /srv/{{ config.path }}
        /mnt/${USER}/media
        $HOME/archive
    """
    
    # Patterns that indicate variable usage
    VARIABLE_PATTERNS = [
        r'\{\{.*?\}\}',      # Jinja2: {{ var }}
        r'\$\{.*?\}',        # Env vars: ${VAR}
        r'\$[A-Z_][A-Z0-9_]*',  # Shell vars: $VAR
        r'%[A-Z_]+%',        # Windows: %VAR%
    ]
    
    @staticmethod
    def is_static_path(path: str) -> Tuple[bool, str]:
        """
        Check if path is static (no variables).
        
        Args:
            path: File system path
            
        Returns:
            (is_static, error_message) tuple
        """
        if not path:
            return False, "Empty path"
        
        # Check for variable patterns
        for pattern in FSLockValidator.VARIABLE_PATTERNS:
            if re.search(pattern, path):
                return False, f"Path contains variables (pattern: {pattern}): {path}"
        
        # Must be absolute path (starts with /)
        if not path.startswith('/'):
            return False, f"Path must be absolute (start with /): {path}"
        
        return True, ""
    
    @staticmethod
    def validate_paths(paths: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate list of fs_lock paths.
        
        Args:
            paths: List of file system paths
            
        Returns:
            (all_valid, errors) tuple
        """
        errors = []
        
        for path in paths:
            is_static, error = FSLockValidator.is_static_path(path)
            if not is_static:
                errors.append(f"{path}: {error}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_manifest(manifest: dict) -> Tuple[bool, List[str]]:
        """
        Validate fs_lock field in plugin manifest.
        
        Args:
            manifest: Plugin manifest dict
            
        Returns:
            (is_valid, errors) tuple
        """
        fs_lock = manifest.get('fs_lock', [])
        
        # Empty is valid
        if not fs_lock:
            return True, []
        
        # Must be list
        if not isinstance(fs_lock, list):
            return False, ["fs_lock must be a list"]
        
        # Validate each path
        return FSLockValidator.validate_paths(fs_lock)
