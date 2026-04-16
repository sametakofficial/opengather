"""Config module - Configuration management for Archiverr.

Exposes the path-aware interpolator, the 3-layer manifest merge,
and the scope-stack primitive.  The legacy ``AliasResolver`` was
removed in session 34 (WP-3); use ``compile_config`` on the whole
tree instead.
"""

from .interpolator import (
    InterpolationError,
    Interpolator,
    compile_config,
)
from .manifest_merge import apply_to_config, merge_plugin_layers
from .scope_stack import ScopeFrame, ScopeStack

__all__ = [
    "Interpolator",
    "InterpolationError",
    "compile_config",
    "ScopeFrame",
    "ScopeStack",
    "apply_to_config",
    "merge_plugin_layers",
]
