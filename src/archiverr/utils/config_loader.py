"""
Config Loader with Environment Variable Support

Features:
- Load config.yml with ${ENV_VAR} expansion
- Mask sensitive values back to env var names for storage
- Support for nested env vars in any field

Usage:
    # In config.yml:
    tmdb:
      api_key: ${TMDB_API_KEY}
    
    # In .env:
    TMDB_API_KEY=abc123
    
    # Load with expansion:
    config = load_config("config.yml")
    # config['tmdb']['api_key'] == 'abc123'
    
    # Create snapshot with masked values:
    snapshot = create_config_snapshot(config)
    # snapshot['plugins']['tmdb']['api_key'] == '${TMDB_API_KEY}'
"""

import os
import re
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import yaml


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


def load_config(path: str = "config.yml", expand: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load config from YAML file.
    
    Args:
        path: Path to config file
        expand: Whether to expand environment variables
        
    Returns:
        Tuple of (expanded_config, original_config)
        - expanded_config: Config with env vars expanded (for runtime use)
        - original_config: Config with ${ENV_VAR} syntax preserved (for snapshots)
    """
    config_path = Path(path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        original_config = yaml.safe_load(f)
    
    if expand:
        expanded_config = expand_env_vars(original_config)
        return expanded_config, original_config
    
    return original_config, original_config


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


def load_config_with_tracking(path: str = "config.yml") -> Dict[str, Any]:
    """
    Load config and track original for later snapshotting.
    
    Returns:
        Expanded config for runtime use
    """
    global _original_config
    expanded, original = load_config(path)
    _original_config = original
    return expanded


def get_tracked_original() -> Dict[str, Any]:
    """Get the tracked original config (with ${ENV_VAR} syntax)"""
    return _original_config
