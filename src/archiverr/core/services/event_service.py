"""Read-only EventService for plugins.

Plugins MUST NOT emit or subscribe — that would create a parallel ordering
system that competes with the dependency resolver and lifecycle hooks.

The read surface here covers the documented contract in
``datasets/08-services.yml``:
  - ``has_fired(name)`` for ``requires: events.*:fired`` style checks
  - ``history(name)`` for inspecting past events
  - ``snapshot()`` for template-context injection ({{ events }})
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from archiverr.events import Event, EventBus


class EventServiceImpl:
    """Read-only view over the EventBus exposed to plugins."""

    def __init__(self, event_bus: 'EventBus'):
        self._bus = event_bus

    def has_fired(self, name: str) -> bool:
        """True if an event with this name has been emitted at least once."""
        return self._bus.has_fired(name)

    def history(self, name: str | None = None, limit: int = 100) -> list['Event']:
        """Return past events, newest first. ``name=None`` returns all."""
        return self._bus.get_history(event_name=name, limit=limit)

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Event history grouped by name, suitable for template injection."""
        return self._bus.get_history_dict()
