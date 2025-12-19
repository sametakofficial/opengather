"""
Events Module - Event Bus for loose coupling

Inspired by:
- Sonarr's MessageAggregator
- Node.js EventEmitter
- Python asyncio patterns
"""

from .bus import Event, EventBus, Events
from .handlers import ConsoleProgressHandler, DebugHandler, ProgressHandler, StatisticsHandler

__all__ = [
    'EventBus', 'Event', 'Events',
    'DebugHandler', 'ProgressHandler', 'ConsoleProgressHandler', 'StatisticsHandler'
]
