"""
Events Module - Event Bus for loose coupling

Inspired by:
- Sonarr's MessageAggregator
- Node.js EventEmitter
- Python asyncio patterns
"""

from .bus import EventBus, Event, Events
from .handlers import DebugHandler, ProgressHandler, ConsoleProgressHandler, StatisticsHandler

__all__ = [
    'EventBus', 'Event', 'Events',
    'DebugHandler', 'ProgressHandler', 'ConsoleProgressHandler', 'StatisticsHandler'
]
