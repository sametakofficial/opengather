"""
Config normalization for FlexGet-style config support.

Session 11 - Phase 6: Dual format support for config.yml

Supports both:
1. FlexGet style (plugin as top-level key)
2. Legacy style (plugins: wrapper with enabled: field)

Detection Logic:
- Key varsa ve false değilse → ENABLED
- Key: false ise → DISABLED
- enabled: false ise → DISABLED
- Key yoksa → DISABLED
"""

from typing import Any

# Reserved top-level keys (not plugins)
RESERVED_KEYS: set[str] = {
    'options', 'aliases', 'database', 'logging', 'tasks',
    'plugins',  # Legacy wrapper
    '_plugins', '_enabled_plugins',  # Internal
}

# Known plugin names (for FlexGet style detection)
# This helps detect plugins even when they have minimal config
KNOWN_PLUGINS: set[str] = {
    'scanner', 'file-input', 'file-reader',
    'renamer',
    'tmdb', 'tvdb', 'tvmaze', 'omdb',
    'ffprobe',
    'tasker', 'rclone',
}


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize config to internal format with _plugins dict.
    
    Handles:
    - FlexGet style (plugin at top-level)
    - Legacy style (plugins: wrapper)
    - Enabled detection based on multiple rules
    
    Args:
        config: Raw config dict from YAML
    
    Returns:
        Normalized config with _plugins and _enabled_plugins
    
    Example:
        # FlexGet style
        config = {
            "options": {"debug": True},
            "tmdb": {"api_key": "xxx"},
            "tvdb": False
        }
        
        normalized = normalize_config(config)
        # normalized["_enabled_plugins"] == ["tmdb"]
        # normalized["_plugins"]["tmdb"]["_enabled"] == True
    """
    normalized = config.copy()

    # Detect format and extract plugins
    config_format = detect_config_format(config)

    if config_format == 'legacy':
        plugins = _normalize_legacy_plugins(config.get('plugins', {}))
    else:
        plugins = _extract_flexget_plugins(config)

    # Add internal normalized structures
    normalized['_plugins'] = plugins
    normalized['_enabled_plugins'] = [
        name for name, cfg in plugins.items()
        if _is_enabled(cfg)
    ]
    normalized['_config_format'] = config_format

    return normalized


def detect_config_format(config: dict[str, Any]) -> str:
    """
    Detect config format.
    
    Returns:
        'flexget' or 'legacy'
    """
    # If plugins: key exists with dict value, it's legacy
    if 'plugins' in config and isinstance(config.get('plugins'), dict):
        return 'legacy'
    return 'flexget'


def _normalize_legacy_plugins(plugins_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize legacy plugins: format.
    
    Legacy format:
        plugins:
          tmdb:
            enabled: true
            api_key: xxx
    """
    result = {}

    for name, config in plugins_dict.items():
        if config is False:
            # Explicit disable: tmdb: false
            result[name] = {'_enabled': False}
        elif config is None or config is True:
            # Minimal enable: tmdb: true or tmdb:
            result[name] = {'_enabled': True}
        elif isinstance(config, dict):
            # Full config
            enabled = config.get('enabled', True)  # Default enabled
            result[name] = {
                **{k: v for k, v in config.items() if k != 'enabled'},
                '_enabled': enabled
            }
        else:
            # Unknown format, treat as enabled
            result[name] = {'_enabled': True, '_raw': config}

    return result


def _extract_flexget_plugins(config: dict[str, Any]) -> dict[str, Any]:
    """
    Extract plugins from FlexGet-style top-level keys.
    
    FlexGet format:
        tmdb:
          api_key: xxx
        tvdb: false
    """
    result = {}

    for key, value in config.items():
        # Skip reserved keys
        if key in RESERVED_KEYS:
            continue

        # Skip private/internal keys
        if key.startswith('_'):
            continue

        # Check if it's a known plugin or looks like one
        if key in KNOWN_PLUGINS or _looks_like_plugin(key, value):
            if value is False:
                # Explicit disable
                result[key] = {'_enabled': False}
            elif value is None or value is True:
                # Minimal enable
                result[key] = {'_enabled': True}
            elif isinstance(value, dict):
                # Full config - check for nested enabled field
                enabled = value.get('enabled', True)
                result[key] = {
                    **{k: v for k, v in value.items() if k != 'enabled'},
                    '_enabled': enabled
                }
            else:
                # Unknown value type
                result[key] = {'_enabled': True, '_raw': value}

    return result


def _looks_like_plugin(key: str, value: Any) -> bool:
    """
    Heuristic to detect if a top-level key is a plugin.
    
    A key is considered a plugin if:
    - It's lowercase with optional hyphens
    - Value is dict with plugin-like keys
    - Value is False (disabled plugin marker)
    """
    # Plugin names are lowercase, may contain hyphens
    if not all(c.islower() or c.isdigit() or c in '-_' for c in key):
        return False

    # Spaces not allowed in plugin names
    if ' ' in key:
        return False

    # False means disabled plugin
    if value is False:
        return True

    # Dict with plugin-like keys
    if isinstance(value, dict):
        plugin_keys = {
            'enabled', 'api_key', 'apikey', 'targets', 'timeout',
            'language', 'extras', 'include-raw', 'recursive'
        }
        return bool(set(value.keys()) & plugin_keys)

    return False


def _is_enabled(plugin_config: dict[str, Any]) -> bool:
    """Check if plugin is enabled."""
    return plugin_config.get('_enabled', True)


def get_plugin_config(config: dict[str, Any], plugin_name: str) -> dict[str, Any]:
    """
    Get normalized config for a specific plugin.
    
    Args:
        config: Normalized config
        plugin_name: Plugin name
    
    Returns:
        Plugin config dict (without _enabled key) or empty dict
    """
    plugins = config.get('_plugins', {})
    plugin_conf = plugins.get(plugin_name, {})

    # Return config without internal keys
    return {k: v for k, v in plugin_conf.items() if not k.startswith('_')}


def is_plugin_enabled(config: dict[str, Any], plugin_name: str) -> bool:
    """
    Check if plugin is enabled in config.
    
    Args:
        config: Normalized config
        plugin_name: Plugin name
    
    Returns:
        True if plugin is enabled
    """
    enabled = config.get('_enabled_plugins', [])
    return plugin_name in enabled


def get_enabled_plugins(config: dict[str, Any]) -> list[str]:
    """
    Get list of enabled plugin names.
    
    Args:
        config: Normalized config
    
    Returns:
        List of enabled plugin names
    """
    return config.get('_enabled_plugins', [])


def get_all_plugins(config: dict[str, Any]) -> dict[str, Any]:
    """
    Get all plugins (enabled and disabled).
    
    Args:
        config: Normalized config
    
    Returns:
        Dict of plugin_name -> plugin_config
    """
    return config.get('_plugins', {})
