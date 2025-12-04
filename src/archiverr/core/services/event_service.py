"""
Event Service Implementation

Wraps EventBus to provide clean interface for plugins.
"""

from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from archiverr.events import EventBus


class EventServiceImpl:
    """
    EventService implementation that wraps EventBus.
    
    Provides simplified event emission and subscription for plugins.
    """
    
    def __init__(self, event_bus: 'EventBus', source: str = "plugin"):
        """
        Initialize event service.
        
        Args:
            event_bus: EventBus instance
            source: Default source for emitted events
        """
        self._bus = event_bus
        self._source = source
    
    def emit(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an event.
        
        Args:
            event: Event name (e.g., "plugin.completed")
            data: Event payload
        """
        self._bus.emit(event, data or {}, source=self._source)
    
    def subscribe(self, event: str, handler: Callable) -> None:
        """
        Subscribe to an event.
        
        Args:
            event: Event name pattern
            handler: Callback function
        """
        self._bus.subscribe(event, handler)
    
    @property
    def bus(self) -> 'EventBus':
        """Get underlying EventBus (for advanced usage)."""
        return self._bus
