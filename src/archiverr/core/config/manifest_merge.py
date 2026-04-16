"""3-layer plugin config merge.

Produces the canonical per-plugin structure:

    _plugins[<name>] = {
        "_manifest":  <raw manifest fields (read-only reference)>,
        "_defaults":  <manifest.defaults + config_schema.default values>,
        "user":       <config.yml plugin branch, authoritative>,
        "_resolved":  <final compiled config: user > _defaults>,
        "_enabled":   <bool, carried over from normalized config>,
    }

Precedence for ``_resolved``:  ``user > _defaults > manifest.config_schema.default``.

``_manifest`` is never mutated by later stages.  ``_resolved`` is computed once
and then frozen (the freezing itself is enforced by convention, not by type).

Consumers:

* the plugin loader uses ``_resolved`` as the plugin's effective config,
* the interpolator (WP-3) uses ``_manifest`` for ``${plugin.<name>._manifest.*}``
  references,
* debug dumps keep all four layers so we can tell where a value came from.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

INTERNAL_MARKER_PREFIX = "_"
RESERVED_LAYER_KEYS = {"_manifest", "_defaults", "user", "_resolved"}


def merge_plugin_layers(
    plugin_configs: dict[str, dict[str, Any]],
    manifests: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the 3-layer structure for every known plugin.

    Args:
        plugin_configs: ``config['_plugins']`` as produced by
            :func:`archiverr.utils.config_normalizer.normalize_config`.  Each
            value is the user-supplied config dict for a plugin, optionally
            carrying internal keys like ``_enabled``.
        manifests: mapping of plugin name to the validated manifest dict
            produced by :class:`PluginDiscovery`.

    Returns:
        A new dict keyed by plugin name whose values are the 3-layer structure
        described in the module docstring.  The input dicts are not mutated.
    """
    merged: dict[str, dict[str, Any]] = {}

    all_names = set(plugin_configs) | set(manifests)
    for name in all_names:
        user_raw = plugin_configs.get(name, {}) or {}
        manifest_raw = manifests.get(name, {}) or {}

        manifest_block = _extract_manifest_block(manifest_raw)
        defaults_block = _extract_defaults_block(manifest_raw)
        user_block = _extract_user_block(user_raw)
        resolved = _compute_resolved(defaults_block, user_block)

        entry: dict[str, Any] = {
            "_manifest": manifest_block,
            "_defaults": defaults_block,
            "user": user_block,
            "_resolved": resolved,
        }

        for key, value in user_raw.items():
            if not isinstance(key, str):
                continue
            if key in RESERVED_LAYER_KEYS:
                continue
            if key.startswith(INTERNAL_MARKER_PREFIX):
                entry[key] = value

        merged[name] = entry

    return merged


def _extract_manifest_block(manifest: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy the manifest so _manifest stays read-only wrt later edits."""
    return deepcopy(manifest)


def _extract_defaults_block(manifest: dict[str, Any]) -> dict[str, Any]:
    """Combine explicit ``defaults:`` block with ``config_schema`` defaults.

    Explicit defaults override schema defaults because the manifest author
    chose to write them out.
    """
    schema_defaults = _collect_schema_defaults(manifest.get("config_schema") or {})
    explicit = manifest.get("defaults") or {}
    if not isinstance(explicit, dict):
        explicit = {}
    return _deep_merge(schema_defaults, explicit)


def _collect_schema_defaults(schema: Any) -> dict[str, Any]:
    """Walk ``config_schema`` pulling ``default`` values.

    Supports nested ``type: object/dict`` schemas with ``properties``.
    """
    if not isinstance(schema, dict):
        return {}
    defaults: dict[str, Any] = {}
    for field, spec in schema.items():
        if not isinstance(spec, dict):
            continue
        if "default" in spec:
            defaults[field] = deepcopy(spec["default"])
            continue
        if spec.get("type") in {"object", "dict"} and isinstance(spec.get("properties"), dict):
            nested = _collect_schema_defaults(spec["properties"])
            if nested:
                defaults[field] = nested
    return defaults


def _extract_user_block(user_config: dict[str, Any]) -> dict[str, Any]:
    """Return the user-facing slice: drops internal ``_*`` and layer keys."""
    out: dict[str, Any] = {}
    for key, value in user_config.items():
        if not isinstance(key, str):
            out[key] = deepcopy(value)
            continue
        if key in RESERVED_LAYER_KEYS:
            continue
        if key.startswith(INTERNAL_MARKER_PREFIX):
            continue
        out[key] = deepcopy(value)
    return out


def _compute_resolved(
    defaults_block: dict[str, Any],
    user_block: dict[str, Any],
) -> dict[str, Any]:
    """User overrides defaults; dicts deep-merged, scalars replaced."""
    return _deep_merge(defaults_block, user_block)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursive dict merge: override wins, dicts merged one level deeper."""
    result = deepcopy(base) if base else {}
    if not override:
        return result
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def apply_to_config(
    config: dict[str, Any],
    manifests: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Enrich ``config['_plugins']`` with the 3-layer structure in place.

    Returns the same config object for chaining.  If ``_plugins`` is absent,
    this is a no-op.
    """
    plugins = config.get("_plugins")
    if not isinstance(plugins, dict):
        return config

    merged = merge_plugin_layers(plugins, manifests)

    for name, layered in merged.items():
        existing = plugins.get(name, {}) or {}
        enabled_marker = existing.get("_enabled")
        plugins[name] = layered
        if enabled_marker is not None:
            plugins[name]["_enabled"] = enabled_marker

    return config
