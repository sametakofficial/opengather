"""Event Emitter - Extracted from GlobalStateManager.

This module handles event emission logic.
Follows Single Responsibility Principle by separating event emission from state management.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from archiverr.events import EventBus


class StateEventEmitter:
    """
    Handles event emission for state changes.
    
    Extracted from GlobalStateManager to follow SRP.
    Centralizes all state-related event emission logic.
    """

    def __init__(self, event_bus: Optional['EventBus'] = None, source: str = "state"):
        """
        Initialize event emitter.
        
        Args:
            event_bus: Optional EventBus instance
            source: Default source name for events
        """
        self._event_bus = event_bus
        self._source = source

    def configure(self, event_bus: 'EventBus' = None):
        """Reconfigure event bus."""
        if event_bus is not None:
            self._event_bus = event_bus

    def emit(self, event_name: str, data: dict[str, Any] = None, source: str = None) -> None:
        """
        Emit an event if event bus is configured.
        
        Args:
            event_name: Name of the event (use Events constants)
            data: Event data dictionary
            source: Optional source override
        """
        if self._event_bus:
            self._event_bus.emit(event_name, data or {}, source or self._source)

    @property
    def is_configured(self) -> bool:
        """Check if event bus is configured."""
        return self._event_bus is not None
