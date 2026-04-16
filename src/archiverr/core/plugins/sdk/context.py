"""
Execution Context - Runtime context passed to plugins.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from archiverr.events import EventBus


@dataclass
class ExecutionContext:
    config: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = True
    debug: bool = False
    debugger: Any | None = None
    event_bus: Optional['EventBus'] = None

    def log(self, level: str, component: str, message: str, **kwargs):
        if self.debugger:
            log_func = getattr(self.debugger, level, self.debugger.info)
            log_func(component, message, **kwargs)
