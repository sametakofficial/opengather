"""WP-9.1: services.events read-only EventService.

The plugin-facing API is read-only by shape: ``has_fired``, ``history``,
``snapshot`` — no ``emit`` / ``subscribe``. Anything else would create a
parallel ordering system that competes with the dependency resolver.
"""

import pytest

from archiverr.core.services.event_service import EventServiceImpl
from archiverr.core.services.plugin_services import PluginServices
from archiverr.events import Events
from archiverr.events.bus import EventBus


def _bus_with_events(*emits):
    bus = EventBus()
    for name, data in emits:
        bus.emit(name, data)
    return bus


def test_has_fired_true_after_emit():
    bus = _bus_with_events((Events.PLUGIN_COMPLETED, {"plugin_name": "tmdb"}))
    svc = EventServiceImpl(bus)

    assert svc.has_fired(Events.PLUGIN_COMPLETED) is True


def test_has_fired_false_when_never_emitted():
    svc = EventServiceImpl(EventBus())
    assert svc.has_fired("never.fired") is False


def test_history_returns_newest_first():
    bus = _bus_with_events(
        (Events.PLUGIN_COMPLETED, {"plugin_name": "ffprobe"}),
        (Events.PLUGIN_COMPLETED, {"plugin_name": "tmdb"}),
    )
    svc = EventServiceImpl(bus)

    history = svc.history(Events.PLUGIN_COMPLETED)

    assert len(history) == 2
    assert history[0].data["plugin_name"] == "tmdb"
    assert history[1].data["plugin_name"] == "ffprobe"


def test_history_no_filter_returns_all():
    bus = _bus_with_events(
        (Events.RUN_STARTED, {}),
        (Events.JOB_CREATED, {}),
    )
    svc = EventServiceImpl(bus)

    assert len(svc.history()) == 2


def test_snapshot_groups_by_event_name():
    bus = _bus_with_events(
        (Events.PLUGIN_COMPLETED, {"plugin_name": "tmdb"}),
        (Events.JOB_CREATED, {"job_id": "j1"}),
    )
    svc = EventServiceImpl(bus)

    snap = svc.snapshot()

    assert Events.PLUGIN_COMPLETED in snap
    assert Events.JOB_CREATED in snap
    assert snap[Events.PLUGIN_COMPLETED][0]["data"]["plugin_name"] == "tmdb"


def test_event_service_has_no_emit_method():
    """Read-only contract: plugins must not emit through services.events."""
    svc = EventServiceImpl(EventBus())
    assert not hasattr(svc, "emit")


def test_event_service_has_no_subscribe_method():
    """Read-only contract: plugins must not subscribe through services.events."""
    svc = EventServiceImpl(EventBus())
    assert not hasattr(svc, "subscribe")


def test_plugin_services_events_property_returns_event_service():
    bus = EventBus()
    services = PluginServices(
        state=None, event_bus=bus, logger=_NoopLogger(),
        config={}, mode="per_job",
    )

    assert isinstance(services.events, EventServiceImpl)


def test_plugin_services_events_cached():
    services = PluginServices(
        state=None, event_bus=EventBus(), logger=_NoopLogger(),
        config={}, mode="per_job",
    )

    first = services.events
    second = services.events

    assert first is second


def test_plugin_services_events_raises_when_bus_missing():
    from archiverr.core.exceptions import PluginError

    services = PluginServices(
        state=None, event_bus=None, logger=_NoopLogger(),
        config={}, mode="per_job",
    )

    with pytest.raises(PluginError, match="event_bus wiring"):
        _ = services.events


def test_plugin_services_no_emit_method():
    """services.emit() removed — plugins read events, they don't emit."""
    services = PluginServices(
        state=None, event_bus=EventBus(), logger=_NoopLogger(),
        config={}, mode="per_job",
    )

    assert not hasattr(services, "emit")


class _NoopLogger:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warn(self, *a, **k): pass
    def error(self, *a, **k): pass
