"""
Manifest normalization for stage-based plugin system.

- Phase 6: Normalize legacy manifests to new stage-based format.

Converts:
- category → stage
- depends_on → (removed)
- expects → requires (with job.plugins. prefix)
- Adds provides if missing
- Adds trigger_rule if missing

P2.1: Jinja2 template rendering in manifest fields (requires, provides).
"""

import warnings
from typing import Any

# Category to stage mapping (for backward compatibility)
CATEGORY_TO_STAGE: dict[str, str] = {
    'input': 'input',
    'output': 'data',  # Most legacy output plugins do data fetching
}

# Known plugins with their correct stages
PLUGIN_STAGE_MAP: dict[str, str] = {
    # Input stage - file discovery
    'scanner': 'input',
    'file-input': 'input',
    'file-reader': 'input',

    # Parse stage - filename parsing
    'renamer': 'parse',

    # Data stage - external API calls
    'tmdb': 'data',
    'tvdb': 'data',
    'tvmaze': 'data',
    'omdb': 'data',
    'ffprobe': 'data',

    # Output stage - results
    'tasker': 'output',
    'rclone': 'output',
}

# Valid stages
VALID_STAGES = {'input', 'parse', 'data', 'output'}

# Valid trigger rules (Airflow-style)
VALID_TRIGGER_RULES = {
    'all_success',   # Default: all upstream must succeed
    'one_success',   # At least one upstream must succeed
    'all_done',      # All upstream finished (any state)
    'all_fail',      # All upstream must fail
    'none_fail',     # No upstream can fail
}


def normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize manifest to new stage-based format.
    
    This function:
    1. Converts category to stage
    2. Converts expects to requires with proper prefixes
    3. Infers provides if not specified
    4. Sets default trigger_rule
    5. Removes deprecated fields
    
    Args:
        manifest: Raw manifest dict from YAML
    
    Returns:
        Normalized manifest
    
    Example:
        # Old format
        old = {
            "name": "tmdb",
            "category": "output",
            "depends_on": ["renamer"],
            "expects": ["renamer.parsed.movie"],
            "class_name": "TMDbPlugin"
        }
        
        # After normalization
        new = normalize_manifest(old)
        # new["stage"] == "data"
        # new["requires"] == ["job.plugins.renamer.parsed.movie"]
        # "category" not in new
    """
    normalized = manifest.copy()
    name = manifest.get('name', 'unknown')

    # Normalize stage
    if 'stage' not in normalized:
        normalized['stage'] = _infer_stage(manifest)
    elif normalized['stage'] not in VALID_STAGES:
        warnings.warn(
            f"Plugin '{name}' has invalid stage '{normalized['stage']}', "
            f"valid stages are: {VALID_STAGES}"
        )
        normalized['stage'] = _infer_stage(manifest)

    # Normalize requires
    if 'requires' not in normalized:
        normalized['requires'] = _convert_expects_to_requires(manifest)
    else:
        # Ensure proper prefix for existing requires
        normalized['requires'] = _normalize_requires_paths(normalized['requires'])

    # Add provides if missing
    if 'provides' not in normalized:
        normalized['provides'] = _infer_provides(manifest, normalized['stage'])

    # Add default trigger_rule if missing
    if 'trigger_rule' not in normalized:
        normalized['trigger_rule'] = 'all_success'
    elif normalized['trigger_rule'] not in VALID_TRIGGER_RULES:
        warnings.warn(
            f"Plugin '{name}' has invalid trigger_rule '{normalized['trigger_rule']}'"
        )
        normalized['trigger_rule'] = 'all_success'

    # Remove deprecated fields but keep category for backward compat
    normalized.pop('depends_on', None)
    normalized.pop('expects', None)

    # Mark as normalized
    normalized['_normalized'] = True

    return normalized


def _infer_stage(manifest: dict[str, Any]) -> str:
    """
    Infer stage from manifest fields.
    
    Priority:
    1. Known plugin mapping
    2. Category mapping
    3. Default to 'output'
    """
    name = manifest.get('name', '')

    # Check known plugin mapping first
    if name in PLUGIN_STAGE_MAP:
        return PLUGIN_STAGE_MAP[name]

    # Fall back to category mapping
    category = manifest.get('category', 'output')
    return CATEGORY_TO_STAGE.get(category, 'data')


def _convert_expects_to_requires(manifest: dict[str, Any]) -> list[str]:
    """
    Convert old expects format to new requires format.
    
    Old: expects: ["renamer.parsed.movie"]
    New: requires: ["job.plugins.renamer.parsed.movie"]
    
    Also checks depends_on for plugin names.
    """
    expects = manifest.get('expects', [])
    depends_on = manifest.get('depends_on', [])
    requires = []

    # Convert expects entries
    for expect in expects:
        requires.append(_add_requires_prefix(expect))

    # Add depends_on as plugin-level requires
    for dep in depends_on:
        dep_path = f"job.plugins.{dep}"
        if dep_path not in requires:
            requires.append(dep_path)

    return requires


def _normalize_requires_paths(requires: list[str]) -> list[str]:
    """Ensure all requires paths have proper prefixes."""
    return [_add_requires_prefix(req) for req in requires]


def _add_requires_prefix(path: str) -> str:
    """
    Add job.plugins. prefix if not present.
    
    Examples:
        "renamer.parsed.movie" → "job.plugins.renamer.parsed.movie"
        "job.plugins.renamer" → "job.plugins.renamer" (unchanged)
        "job.input.value" → "job.input.value" (unchanged)
    """
    if path.startswith('job.'):
        return path
    return f"job.plugins.{path}"


def _infer_provides(manifest: dict[str, Any], stage: str) -> list[str]:
    """
    Infer provides based on stage and plugin type.
    
    Provides indicate:
    - Technical effects (http.request, fs.write)
    - Data availability (state.update)
    """
    name = manifest.get('name', '')

    # Plugin-specific provides
    plugin_provides: dict[str, list[str]] = {
        'scanner': ['job.create', 'fs.read'],
        'file-input': ['job.create', 'fs.read'],
        'file-reader': ['job.create', 'fs.read'],
        'renamer': ['state.update'],
        'tmdb': ['http.request', 'state.update'],
        'tvdb': ['http.request', 'state.update'],
        'tvmaze': ['http.request', 'state.update'],
        'omdb': ['http.request', 'state.update'],
        'ffprobe': ['process.execute', 'state.update'],
        'tasker': ['output.render'],
        'rclone': ['fs.write', 'process.execute'],
    }

    if name in plugin_provides:
        return plugin_provides[name]

    # Stage-based defaults
    stage_provides: dict[str, list[str]] = {
        'input': ['job.create', 'fs.read'],
        'parse': ['state.update'],
        'data': ['state.update'],
        'output': ['output.render'],
    }

    return stage_provides.get(stage, ['state.update'])


def validate_manifest(manifest: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate manifest structure.
    
    Args:
        manifest: Manifest dict (preferably normalized)
    
    Returns:
        (is_valid, error_message)
        - is_valid: True if manifest is valid
        - error_message: Error description or None
    """
    required_fields = ['name', 'class_name']

    for field in required_fields:
        if field not in manifest:
            return False, f"Missing required field: {field}"

    # Validate stage if present
    stage = manifest.get('stage')
    if stage and stage not in VALID_STAGES:
        return False, f"Invalid stage: {stage}. Valid stages: {VALID_STAGES}"

    # Validate trigger_rule if present
    rule = manifest.get('trigger_rule')
    if rule and rule not in VALID_TRIGGER_RULES:
        return False, f"Invalid trigger_rule: {rule}. Valid rules: {VALID_TRIGGER_RULES}"

    # Validate requires is a list
    requires = manifest.get('requires')
    if requires is not None and not isinstance(requires, list):
        return False, f"requires must be a list, got {type(requires).__name__}"

    # Validate provides is a list
    provides = manifest.get('provides')
    if provides is not None and not isinstance(provides, list):
        return False, f"provides must be a list, got {type(provides).__name__}"

    return True, None


def is_manifest_normalized(manifest: dict[str, Any]) -> bool:
    """Check if manifest has been normalized."""
    return manifest.get('_normalized', False)


def get_manifest_format(manifest: dict[str, Any]) -> str:
    """
    Detect manifest format version.
    
    Returns:
        'new' if manifest uses stage field
        'legacy' if manifest uses category field
    """
    if 'stage' in manifest:
        return 'new'
    if 'category' in manifest:
        return 'legacy'
    return 'new'  # Assume new if neither present


def extract_plugin_dependencies(manifest: dict[str, Any]) -> list[str]:
    """
    Extract plugin names from requires.
    
    Args:
        manifest: Normalized manifest
    
    Returns:
        List of plugin names this plugin depends on
    
    Example:
        requires = ["job.plugins.renamer.parsed", "job.input.value"]
        # Returns: ["renamer"]
    """
    requires = manifest.get('requires', [])
    dependencies = []

    for req in requires:
        if req.startswith('job.plugins.'):
            # Extract plugin name: job.plugins.renamer.parsed → renamer
            parts = req.split('.')
            if len(parts) >= 3:
                plugin_name = parts[2]
                if plugin_name not in dependencies:
                    dependencies.append(plugin_name)

    return dependencies
