"""
Events Module - Event Bus for loose coupling

Inspired by:
- Sonarr's MessageAggregator
- Node.js EventEmitter
- Python asyncio patterns
"""

from .bus import Event, EventBus, Events

__all__ = ['EventBus', 'Event', 'Events']
