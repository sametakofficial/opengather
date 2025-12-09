"""
Config Loader with full feature support.

Session 11 - Phase 6: Enhanced config loading.

Features:
- Load config.yml with ${ENV_VAR} expansion
- !include directive for file/directory includes
- FlexGet-style config normalization (plugin as top-level key)
- Legacy format support (plugins: wrapper)
- Mask sensitive values back to env var names for storage

Usage:
    # In config.yml:
    tmdb:
      api_key: ${TMDB_API_KEY}
    tasks: !include ./tasks/
    
    # Load with all features:
    config = load_config_with_tracking("config.yml")
    # config['_enabled_plugins'] == ['tmdb', 'scanner', ...]
    # config['_plugins']['tmdb']['api_key'] == 'actual_key'
"""

import os
import re
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import yaml

# Import new Phase 6 modules
from .yaml_loader import load_yaml_with_includes, IncludeError
from .config_normalizer import normalize_config, detect_config_format


# Pattern to match ${ENV_VAR} or $ENV_VAR
ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')

# Known sensitive field names (will be masked in snapshots)
SENSITIVE_FIELDS = {
    'api_key', 'apikey', 'api-key',
    'secret', 'password', 'token',
    'access_token', 'refresh_token',
    'private_key', 'auth_key'
}


def expand_env_vars(value: Any) -> Any:
    """
    Recursively expand environment variables in config values.
    
    Supports:
    - ${ENV_VAR} syntax
    - $ENV_VAR syntax
    - Nested dicts and lists
    
    Args:
        value: Config value (string, dict, list, or primitive)
        
    Returns:
        Value with env vars expanded
    """
    if isinstance(value, str):
        def replace_env(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))
        
        return ENV_VAR_PATTERN.sub(replace_env, value)
    
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    
    elif isinstance(value, list):
        return [expand_env_vars(v) for v in value]
    
    return value


def mask_env_vars(value: Any, original_value: Any = None) -> Any:
    """
    Reverse of expand_env_vars - restore env var syntax from expanded values.
    
    Args:
        value: Expanded config value
        original_value: Original config with ${ENV_VAR} syntax
        
    Returns:
        Value with env vars masked back to ${VAR} syntax
    """
    if original_value is None:
        return value
    
    if isinstance(value, str) and isinstance(original_value, str):
        # Check if original had env var syntax
        if ENV_VAR_PATTERN.search(original_value):
            return original_value
        return value
    
    elif isinstance(value, dict) and isinstance(original_value, dict):
        result = {}
        for k, v in value.items():
            orig_v = original_value.get(k)
            result[k] = mask_env_vars(v, orig_v)
        return result
    
    elif isinstance(value, list) and isinstance(original_value, list):
        if len(value) == len(original_value):
            return [mask_env_vars(v, orig_v) for v, orig_v in zip(value, original_value)]
        return value
    
    return value


def find_env_var_for_value(value: str) -> Optional[str]:
    """
    Find an environment variable that matches the given value.
    
    Used when we don't have original config but need to mask.
    """
    for env_name, env_value in os.environ.items():
        if env_value == value and len(value) > 8:  # Only match non-trivial values
            return f"${{{env_name}}}"
    return None


def mask_sensitive_fields(config: Dict[str, Any], original_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Mask sensitive fields in config.
    
    - If original config has ${ENV_VAR} syntax, preserve it
    - Otherwise, try to find matching env var
    - Fields with names in SENSITIVE_FIELDS are masked
    
    Args:
        config: Expanded config
        original_config: Original config with ${ENV_VAR} syntax (optional)
        
    Returns:
        Config with sensitive values masked
    """
    if original_config:
        return mask_env_vars(config, original_config)
    
    # No original - try to detect and mask
    return _mask_sensitive_recursive(config)


def _mask_sensitive_recursive(obj: Any, field_name: str = None) -> Any:
    """Recursively mask sensitive fields"""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            result[k] = _mask_sensitive_recursive(v, k)
        return result
    
    elif isinstance(obj, list):
        return [_mask_sensitive_recursive(item) for item in obj]
    
    elif isinstance(obj, str):
        # Check if this is a sensitive field
        if field_name and field_name.lower() in SENSITIVE_FIELDS:
            # Try to find matching env var
            env_ref = find_env_var_for_value(obj)
            if env_ref:
                return env_ref
        return obj
    
    return obj


def load_config(
    path: str = "config.yml",
    expand: bool = True,
    use_includes: bool = True,
    normalize: bool = False
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load config from YAML file.
    
    Args:
        path: Path to config file
        expand: Whether to expand environment variables
        use_includes: Whether to process !include directives
        normalize: Whether to normalize config (FlexGet style detection)
        
    Returns:
        Tuple of (expanded_config, original_config)
        - expanded_config: Config with env vars expanded (for runtime use)
        - original_config: Config with ${ENV_VAR} syntax preserved (for snapshots)
    """
    config_path = Path(path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    # Load with or without include support
    if use_includes:
        try:
            original_config = load_yaml_with_includes(str(config_path))
        except IncludeError as e:
            raise ValueError(f"Config include error: {e}")
    else:
        with open(config_path, 'r', encoding='utf-8') as f:
            original_config = yaml.safe_load(f)
    
    if original_config is None:
        original_config = {}
    
    if expand:
        expanded_config = expand_env_vars(original_config)
    else:
        expanded_config = original_config.copy()
    
    # Normalize if requested
    if normalize:
        expanded_config = normalize_config(expanded_config)
    
    return expanded_config, original_config


def create_config_snapshot(
    config: Dict[str, Any], 
    original_config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create config snapshot for storage (MongoDB, API response).
    
    - Preserves full plugin configuration
    - Masks API keys and sensitive values
    - Returns env var syntax instead of actual values
    
    Args:
        config: Expanded config (runtime config)
        original_config: Original config with ${ENV_VAR} syntax
        
    Returns:
        Config snapshot safe for storage
    """
    # Start with full config copy
    snapshot = {
        "options": config.get("options", {}),
        "plugins": {},
        "tasks": config.get("tasks", [])
    }
    
    # Get original plugins if available
    orig_plugins = original_config.get("plugins", {}) if original_config else {}
    
    # Copy all plugin configs with masked sensitive values
    for plugin_name, plugin_config in config.get("plugins", {}).items():
        if isinstance(plugin_config, dict):
            orig_plugin = orig_plugins.get(plugin_name, {})
            
            # Mask sensitive fields
            masked_config = mask_env_vars(plugin_config, orig_plugin)
            
            # Also try to detect and mask any remaining sensitive values
            masked_config = _mask_sensitive_recursive(masked_config)
            
            snapshot["plugins"][plugin_name] = masked_config
        else:
            snapshot["plugins"][plugin_name] = plugin_config
    
    return snapshot


# Convenience functions for __main__.py

def load_config_simple(path: str = "config.yml") -> Dict[str, Any]:
    """
    Simple config loader - returns only expanded config.
    Use when you don't need original config reference.
    """
    expanded, _ = load_config(path)
    return expanded


# Store original config in module for snapshot access
_original_config: Dict[str, Any] = {}


def resolve_aliases(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve all aliases in config.
    
    Aliases allow shorthand notation in templates:
    - m.title → plugin.tmdb.movie.title
    - movie.name → renamer.parsed.movie.name
    
    This runs during config merge, before any plugin execution.
    After this, no part of the system needs to know about aliases.
    
    Args:
        config: Config with potential alias usage
        
    Returns:
        Config with all aliases resolved to full paths
    """
    aliases = config.get('aliases', {})
    if not aliases:
        return config
    
    # Build replacement map: alias_prefix → full_path
    # Sort by length descending to match longest first
    replacements = sorted(aliases.items(), key=lambda x: len(x[0]), reverse=True)
    
    def resolve_value(value: Any) -> Any:
        """Recursively resolve aliases in any value"""
        if isinstance(value, str):
            # Replace aliases in string (templates, paths, etc.)
            result = value
            for alias, target in replacements:
                # Match alias patterns:
                # 1. {{ alias.field }} or {{ alias }}
                # 2. At start of line or after whitespace: alias.field
                # But NOT: something.alias.field (don't match in middle of path)
                
                # Pattern 1: alias.field → target.field
                # Use negative lookbehind to avoid matching .alias (in middle of path)
                pattern_with_dot = r'(?<![.\w])' + re.escape(alias) + r'\.'
                result = re.sub(pattern_with_dot, target + '.', result)
                
                # Pattern 2: Standalone alias ({{ alias }} or {% if alias %})
                # Replace only if it's a whole word, not part of larger identifier
                standalone_pattern = r'(?<![.\w])' + re.escape(alias) + r'(?![.\w])'
                result = re.sub(standalone_pattern, target, result)
            return result
        elif isinstance(value, dict):
            return {k: resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [resolve_value(v) for v in value]
        return value
    
    # Resolve aliases in entire config (except aliases section itself)
    resolved = {}
    for key, value in config.items():
        if key == 'aliases':
            # Keep aliases section for reference but it won't be used by system
            resolved[key] = value
        else:
            resolved[key] = resolve_value(value)
    
    return resolved


def load_config_with_tracking(
    path: str = "config.yml",
    normalize: bool = True
) -> Dict[str, Any]:
    """
    Load config and track original for later snapshotting.
    
    This is the recommended way to load config for the application.
    It:
    - Processes !include directives
    - Expands environment variables
    - Normalizes config (FlexGet style detection)
    - Resolves aliases (m.title → plugin.tmdb.movie.title)
    - Tracks original for snapshot creation
    
    Args:
        path: Path to config file
        normalize: Whether to normalize (detect FlexGet style)
    
    Returns:
        Expanded and normalized config for runtime use
    """
    global _original_config
    expanded, original = load_config(path, expand=True, use_includes=True, normalize=normalize)
    
    # Resolve aliases after expand/normalize
    expanded = resolve_aliases(expanded)
    
    _original_config = original
    return expanded


def get_tracked_original() -> Dict[str, Any]:
    """Get the tracked original config (with ${ENV_VAR} syntax)"""
    return _original_config


# Re-export for convenience
__all__ = [
    'load_config',
    'load_config_simple',
    'load_config_with_tracking',
    'get_tracked_original',
    'create_config_snapshot',
    'expand_env_vars',
    'mask_env_vars',
    'mask_sensitive_fields',
    'IncludeError',
]
