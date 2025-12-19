"""
Custom YAML loader with !include directive support.

Session 11 - Phase 6: FlexGet-style config loading.

Features:
- !include ./file.yml - Single file include
- !include ./directory/ - Directory include (all .yml files)
- Circular include detection
- Nested include support
"""

import os
from pathlib import Path
from typing import Any

import yaml


class IncludeError(Exception):
    """Error during include processing."""
    pass


class IncludeLoader(yaml.SafeLoader):
    """
    YAML loader with !include directive support.
    
    Usage:
        config = load_yaml_with_includes("config.yml")
    
    Syntax in YAML:
        tasks: !include ./tasks/          # Directory include
        database: !include ./db.yml       # Single file include
    """

    # Track include stack to detect circular includes
    _include_stack: set[str] = set()

    def __init__(self, stream, base_path: str = None):
        self._base_path = base_path or os.getcwd()
        super().__init__(stream)


def _resolve_path(loader: IncludeLoader, path: str) -> str:
    """Resolve include path relative to base path."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(loader._base_path, path))


def _load_file(path: str, include_stack: set[str] = None) -> Any:
    """
    Load single YAML file with nested include support.
    
    Args:
        path: Absolute path to YAML file
        include_stack: Set of already included files (for circular detection)
    
    Returns:
        Parsed YAML content
    """
    include_stack = include_stack or set()

    # Normalize path for comparison
    norm_path = os.path.normpath(path)

    # Check for circular include
    if norm_path in include_stack:
        raise IncludeError(f"Circular include detected: {path}")

    if not os.path.exists(path):
        raise IncludeError(f"Include file not found: {path}")

    # Add to stack
    include_stack.add(norm_path)

    try:
        base_path = os.path.dirname(path)

        with open(path, encoding='utf-8') as f:
            # Create loader with correct base path for nested includes
            loader = IncludeLoader(f, base_path)
            loader._include_stack = include_stack
            try:
                return loader.get_single_data()
            finally:
                loader.dispose()
    finally:
        # Remove from stack when done
        include_stack.discard(norm_path)


def _load_directory(path: str, include_stack: set[str] = None) -> list[Any]:
    """
    Load all YAML files in directory.
    
    Files are sorted alphabetically for consistent ordering.
    Each file can contain a single object or a list of objects.
    
    Args:
        path: Directory path
        include_stack: Set of already included files
    
    Returns:
        List of all parsed content (flattened if files contain lists)
    """
    include_stack = include_stack or set()
    result = []

    if not os.path.isdir(path):
        raise IncludeError(f"Include directory not found: {path}")

    # Sort for consistent ordering
    for file in sorted(Path(path).glob('*.yml')):
        content = _load_file(str(file), include_stack)

        if content is None:
            continue
        elif isinstance(content, list):
            # Flatten list content
            result.extend(content)
        else:
            result.append(content)

    # Also check .yaml extension
    for file in sorted(Path(path).glob('*.yaml')):
        content = _load_file(str(file), include_stack)

        if content is None:
            continue
        elif isinstance(content, list):
            result.extend(content)
        else:
            result.append(content)

    return result


def include_constructor(loader: IncludeLoader, node: yaml.Node) -> dict | list | Any:
    """
    Handle !include directive.
    
    Syntax:
        !include ./file.yml      - Single file include
        !include ./directory/    - All .yml files in directory
    """
    path = loader.construct_scalar(node)
    full_path = _resolve_path(loader, path)

    # Get include stack from loader
    include_stack = getattr(loader, '_include_stack', set())

    if os.path.isdir(full_path):
        # Directory include
        return _load_directory(full_path, include_stack)
    elif os.path.isfile(full_path):
        # Single file include
        return _load_file(full_path, include_stack)
    else:
        raise IncludeError(f"Include path not found: {full_path}")


# Register constructor
IncludeLoader.add_constructor('!include', include_constructor)


def load_yaml_with_includes(path: str) -> dict[str, Any]:
    """
    Load YAML file with !include directive support.
    
    Args:
        path: Path to YAML file (absolute or relative to cwd)
    
    Returns:
        Loaded config dict
    
    Raises:
        FileNotFoundError: If main config file not found
        IncludeError: If include processing fails
        yaml.YAMLError: If YAML parsing fails
    
    Example:
        # config.yml:
        # options:
        #   debug: true
        # tasks: !include ./tasks/
        # database: !include ./db.yml
        
        config = load_yaml_with_includes("config.yml")
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    return _load_file(os.path.abspath(path), set())


def load_yaml_simple(path: str) -> dict[str, Any]:
    """
    Load YAML file without include support.
    
    Simple wrapper around yaml.safe_load for when includes aren't needed.
    
    Args:
        path: Path to YAML file
    
    Returns:
        Loaded dict or empty dict if file is empty
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}
