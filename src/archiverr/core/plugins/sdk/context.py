"""
Execution Context - Runtime context passed to plugins

Provides plugins with access to shared resources without tight coupling.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.events import EventBus


@dataclass
class ExecutionContext:
    """
    Runtime context for plugin execution.
    
    Passed to plugins to provide access to:
    - Configuration
    - Event bus for emitting events
    - Debugger for logging
    - Task manager for emitting tasks
    - Shared state (read-only)
    
    Example:
        def execute(self, data: Dict, context: ExecutionContext):
            context.debugger.info("plugin", "Processing...")
            context.event_bus.emit("plugin.progress", {"percent": 50})
            context.emit_task({"type": "print", "template": "Found: {{ movie.title }}"})
    """
    
    # Execution metadata
    execution_id: str = ""
    match_index: int = 0
    total_matches: int = 0
    
    # Configuration (read-only)
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Options
    dry_run: bool = True
    debug: bool = False
    
    # Dependencies (injected)
    debugger: Optional[Any] = None
    event_bus: Optional['EventBus'] = None
    
    # API response for template rendering
    api_response: Optional[Dict[str, Any]] = None
    
    # Previous plugin results (read-only)
    previous_results: Dict[str, Any] = field(default_factory=dict)
    
    def get_plugin_result(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get result from a previous plugin"""
        return self.previous_results.get(plugin_name)
    
    def has_plugin_result(self, plugin_name: str) -> bool:
        """Check if a plugin has already run"""
        return plugin_name in self.previous_results
    
    def emit_progress(self, percent: float, message: str = ""):
        """Emit progress event"""
        if self.event_bus:
            from archiverr.events import Events
            self.event_bus.emit(Events.PLUGIN_PROGRESS, {
                "execution_id": self.execution_id,
                "match_index": self.match_index,
                "percent": percent,
                "message": message
            })
    
    # emit_task removed - tasks handled by tasker plugin
    
    def log(self, level: str, component: str, message: str, **kwargs):
        """Log message through debugger"""
        if self.debugger:
            log_func = getattr(self.debugger, level, self.debugger.info)
            log_func(component, message, **kwargs)
