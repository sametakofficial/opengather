"""
Event Bus - Async event system for loose coupling

Design:
- Synchronous by default (works with current sync codebase)
- Async-ready (can be used with asyncio when MongoDB/FastAPI added)
- Non-blocking event emission
- Wildcard subscription support
- Event history for debugging

Usage:
    bus = EventBus()
    
    # Subscribe to specific event
    bus.subscribe(Events.MATCH_COMPLETED, my_handler)
    
    # Subscribe to all events (wildcard)
    bus.subscribe("*", log_all_events)
    
    # Emit event
    bus.emit(Events.MATCH_COMPLETED, {"index": 0, "success": True})
"""

from typing import Dict, Set, Callable, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from enum import Enum


@dataclass
class Event:
    """
    Immutable event object.
    
    Attributes:
        name: Event name (from Events enum)
        data: Event payload
        timestamp: When event was emitted
        source: Component that emitted the event
    """
    name: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    
    def __str__(self) -> str:
        return f"Event({self.name}, source={self.source})"


class Events:
    """
    Event name constants for type safety.
    
    Naming convention: COMPONENT_ACTION
    """
    
    # ==================== EXECUTION LIFECYCLE ====================
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    
    # ==================== MATCH LIFECYCLE ====================
    MATCH_STARTED = "match.started"
    MATCH_COMPLETED = "match.completed"
    MATCH_FAILED = "match.failed"
    
    # ==================== PLUGIN LIFECYCLE ====================
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_SKIPPED = "plugin.skipped"  # Not supported for this match
    PLUGIN_PROGRESS = "plugin.progress"  # For long-running plugins
    
    # ==================== TASK LIFECYCLE ====================
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # ==================== STATE CHANGES ====================
    STATE_CHANGED = "state.changed"
    
    # ==================== PERSISTENCE ====================
    DB_CONNECTED = "db.connected"
    DB_DISCONNECTED = "db.disconnected"
    DB_SYNCED = "db.synced"
    DB_ERROR = "db.error"
    
    # ==================== VALIDATION ====================
    VALIDATION_PASSED = "validation.passed"
    VALIDATION_FAILED = "validation.failed"


# Type alias for event handlers
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Synchronous event bus with async-ready design.
    
    Features:
    - Subscribe/unsubscribe to events
    - Wildcard subscription ("*")
    - Event history for debugging
    - Thread-safe with locking
    - Error isolation (handler errors don't crash system)
    
    Design Notes:
    - Currently synchronous for compatibility with existing code
    - Can be converted to async by changing emit() to async
    - Handlers are called in order of subscription
    - Uses dependency injection (no singleton pattern)
    """
    
    def __init__(self, debugger=None, max_history: int = 1000):
        """
        Initialize event bus with dependencies.
        
        Args:
            debugger: Debug logger instance for event logging
            max_history: Maximum events to keep in history (default: 1000)
        """
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._history: List[Event] = []
        self._max_history = max_history
        self._lock = Lock()
        self._debugger = debugger
    
    def configure(self, debugger=None, max_history: int = None):
        """
        Reconfigure event bus (backward compatibility).
        
        Args:
            debugger: Debug logger instance
            max_history: Maximum events to keep in history
        """
        if debugger is not None:
            self._debugger = debugger
        if max_history is not None:
            self._max_history = max_history
    
    def reset(self):
        """Reset event bus state (for testing)"""
        with self._lock:
            self._handlers = {}
            self._history = []
    
    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: Event name or "*" for all events
            handler: Callable that receives Event object
            
        Example:
            def my_handler(event: Event):
                print(f"Got event: {event.name}")
            
            bus.subscribe(Events.MATCH_COMPLETED, my_handler)
        """
        with self._lock:
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            
            if handler not in self._handlers[event_name]:
                self._handlers[event_name].append(handler)
                
                if self._debugger:
                    handler_name = getattr(handler, '__name__', str(handler))
                    self._debugger.debug("event_bus", f"Subscribed to {event_name}",
                                       handler=handler_name)
    
    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """
        Unsubscribe from an event.
        
        Args:
            event_name: Event name
            handler: Handler to remove
        """
        with self._lock:
            if event_name in self._handlers:
                try:
                    self._handlers[event_name].remove(handler)
                except ValueError:
                    pass  # Handler not found, ignore
    
    def emit(self, event_name: str, data: Dict[str, Any] = None, source: str = "system") -> Event:
        """
        Emit an event to all subscribers.
        
        Args:
            event_name: Event name
            data: Event payload
            source: Component emitting the event
            
        Returns:
            The emitted Event object
            
        Example:
            bus.emit(Events.MATCH_COMPLETED, {
                "index": 0,
                "success": True,
                "duration_ms": 1234
            })
        """
        event = Event(
            name=event_name,
            data=data or {},
            timestamp=datetime.now(),
            source=source
        )
        
        # Store in history
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)
        
        # Log event
        if self._debugger:
            self._debugger.debug("event_bus", f"Emitting {event_name}",
                               data_keys=list(event.data.keys()))
        
        # Get handlers (copy to avoid lock during execution)
        with self._lock:
            specific_handlers = self._handlers.get(event_name, []).copy()
            wildcard_handlers = self._handlers.get("*", []).copy()
        
        # Call all handlers (with error isolation)
        all_handlers = specific_handlers + wildcard_handlers
        for handler in all_handlers:
            self._safe_call(handler, event)
        
        return event
    
    def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """
        Call handler with error protection.
        
        Ensures one handler's error doesn't affect others.
        """
        try:
            handler(event)
        except Exception as e:
            handler_name = getattr(handler, '__name__', str(handler))
            if self._debugger:
                self._debugger.error("event_bus", f"Handler error: {handler_name}",
                                   error=str(e), event=event.name)
    
    def get_history(self, event_name: str = None, limit: int = 100) -> List[Event]:
        """
        Get event history for debugging.
        
        Args:
            event_name: Filter by event name (None = all)
            limit: Maximum events to return
            
        Returns:
            List of Event objects (newest first)
        """
        with self._lock:
            events = self._history.copy()
        
        if event_name:
            events = [e for e in events if e.name == event_name]
        
        return list(reversed(events[-limit:]))
    
    def get_subscribers(self, event_name: str = None) -> Dict[str, int]:
        """
        Get subscriber counts for debugging.
        
        Args:
            event_name: Specific event or None for all
            
        Returns:
            Dict of event_name -> handler count
        """
        with self._lock:
            if event_name:
                return {event_name: len(self._handlers.get(event_name, []))}
            return {name: len(handlers) for name, handlers in self._handlers.items()}
