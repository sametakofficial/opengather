"""Core render package — plugin-agnostic Jinja2 rendering.

Session 39 R15 Phase H — moved out of plugins/tasker into core so the
config tree itself can be rendered (the "live playground" model) and any
plugin/output consumer can ask for templates to be expanded without
importing jinja2 directly.
"""

from .render_engine import ConfigRenderEngine
from .template_dependency_validator import (
    ValidationWarning,
    validate_plugin_template_refs,
)

__all__ = [
    "ConfigRenderEngine",
    "ValidationWarning",
    "validate_plugin_template_refs",
]
