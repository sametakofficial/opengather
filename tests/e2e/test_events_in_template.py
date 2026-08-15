"""WP-9.2: ``{{ events }}`` is available in tasker template context.

Closes the datasets/04-template-context.yml ``events: event_bus_snapshot``
contract. The bus snapshot is grouped by event name; each entry is a
dict with ``data``, ``timestamp``, ``source`` keys (see
EventBus.get_history_dict).
"""

from unittest.mock import Mock

from archiverr.events import Events
from archiverr.events.bus import EventBus
from archiverr.plugins.tasker.plugin import TaskerPlugin
from archiverr.state.template_context import TemplateContextBuilder


def _make_job(plugins=None):
    job = Mock()
    job.index = 0
    job.id = "job-1"
    job.input.value = "/x.mkv"
    job.input.data = {}
    job.output.values = []
    job.output.data = {}
    job.status.success = True
    job.status.plugins = {}
    job.plugins = plugins or {}
    return job


def _services_with_bus(bus, plugins_data=None):
    plugins_data = plugins_data or {}
    services = Mock()
    services._state = Mock()
    services._state.run = None
    services._state.jobs = []
    services.run_safety = {"dry_run": True, "hardlink": False, "no_delete": True}
    services.events.snapshot.return_value = bus.get_history_dict()
    services.jobid = None
    services.update_state = Mock()
    services.state.get_job_plugin_names.return_value = list(plugins_data.keys())
    services.state.get_plugin_data.side_effect = (
        lambda job_id, name: plugins_data.get(name, {})
    )
    return services


def test_events_key_in_template_context():
    """TemplateContextBuilder injects events kwarg as 'events' key."""
    job = _make_job()
    snapshot = {"plugin.completed": [{"data": {"plugin_name": "tmdb"}}]}

    ctx = TemplateContextBuilder().build_job_context(job, events=snapshot)

    assert ctx["events"] == snapshot


def test_events_default_is_empty_dict_not_none():
    """Templates can safely iterate `events.get(...)` without None checks."""
    ctx = TemplateContextBuilder().build_job_context(_make_job())

    assert ctx["events"] == {}


def test_render_event_data_field_in_tasker():
    bus = EventBus()
    bus.emit(Events.PLUGIN_COMPLETED, {"plugin_name": "tmdb"})

    plugin = TaskerPlugin({
        "tasks": [{
            "name": "evt", "type": "print",
            "template": "{{ events['plugin.completed'][0].data.plugin_name }}",
        }]
    })

    result = plugin.execute(_make_job(), _services_with_bus(bus))

    assert result.data["tasks"]["evt"]["rendered"] == "tmdb"


def test_render_count_filter_on_never_fired_event():
    bus = EventBus()  # nothing fired

    plugin = TaskerPlugin({
        "tasks": [{
            "name": "cnt", "type": "print",
            "template": "{{ events.get('never.fired', []) | count }}",
        }]
    })

    result = plugin.execute(_make_job(), _services_with_bus(bus))

    assert result.data["tasks"]["cnt"]["rendered"] == "0"


def test_render_count_filter_after_multiple_emits():
    bus = EventBus()
    bus.emit(Events.PLUGIN_COMPLETED, {"plugin_name": "ffprobe"})
    bus.emit(Events.PLUGIN_COMPLETED, {"plugin_name": "tmdb"})

    plugin = TaskerPlugin({
        "tasks": [{
            "name": "cnt", "type": "print",
            "template": "{{ events['plugin.completed'] | count }}",
        }]
    })

    result = plugin.execute(_make_job(), _services_with_bus(bus))

    assert result.data["tasks"]["cnt"]["rendered"] == "2"
