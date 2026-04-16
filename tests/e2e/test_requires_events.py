"""WP-9.3: ``requires: events.<name>:fired`` resolves through the matcher.

Closes the silent-pass bug — before this WP, the resolver explicitly
skipped events.* (correct: it's not a topo dependency) but the matcher
never resolved them either, so a manifest could declare an event
prerequisite and the executor would silently treat it as met.

The matcher now reads the live EventBus for events.* paths, with
``:fired`` as the only allowed check value.
"""

from archiverr.core.triggers.manager import TriggerRuleManager
from archiverr.core.triggers.matcher import ValueMatcher
from archiverr.events import Events
from archiverr.events.bus import EventBus


def _bus_with(*names):
    bus = EventBus()
    for n in names:
        bus.emit(n, {})
    return bus


def test_match_returns_true_when_event_fired():
    bus = _bus_with(Events.RUN_STARTED)
    is_valid, matches, error = ValueMatcher.match(
        {}, "events.run.started:fired", event_bus=bus
    )
    assert is_valid is True
    assert matches is True
    assert error is None


def test_match_returns_false_when_event_never_fired():
    bus = EventBus()
    is_valid, matches, error = ValueMatcher.match(
        {}, "events.run.started:fired", event_bus=bus
    )
    assert is_valid is True
    assert matches is False
    assert error is None


def test_match_without_check_value_uses_existence():
    """``events.run.started`` (no :fired) treats existence as the check."""
    bus = _bus_with(Events.RUN_STARTED)
    is_valid, matches, error = ValueMatcher.match(
        {}, "events.run.started", event_bus=bus
    )
    assert is_valid is True
    assert matches is True


def test_match_rejects_non_fired_check_value():
    """Only :fired is allowed; :completed / :success etc. fail validation."""
    bus = EventBus()
    is_valid, matches, error = ValueMatcher.match(
        {}, "events.run.started:completed", event_bus=bus
    )
    assert is_valid is False
    assert matches is False
    assert "fired" in error


def test_match_without_event_bus_reports_missing_context():
    """No bus wired = configuration error, not a silent pass."""
    is_valid, matches, error = ValueMatcher.match({}, "events.run.started:fired")
    assert is_valid is False
    assert matches is False
    assert "event_bus" in error


def test_validate_requirement_accepts_events_fired():
    is_valid, error = ValueMatcher.validate_requirement("events.run.started:fired")
    assert is_valid is True
    assert error is None


def test_validate_requirement_rejects_events_completed():
    is_valid, error = ValueMatcher.validate_requirement(
        "events.run.started:completed"
    )
    assert is_valid is False
    assert "fired" in error


def test_trigger_manager_threads_event_bus_to_matcher():
    bus = _bus_with(Events.RUN_STARTED)
    mgr = TriggerRuleManager(event_bus=bus)

    is_valid, matches, error = mgr.check_requirement(
        "events.run.started:fired", state={}
    )
    assert is_valid is True
    assert matches is True


def test_trigger_manager_all_success_with_events():
    bus = _bus_with(Events.RUN_STARTED, Events.JOB_CREATED)
    mgr = TriggerRuleManager(event_bus=bus)

    should_run, reason = mgr.should_execute(
        trigger_rule="all_success",
        requirements=[
            "events.run.started:fired",
            "events.job.created:fired",
        ],
        state={},
    )
    assert should_run is True


def test_trigger_manager_all_success_skips_when_event_missing():
    bus = _bus_with(Events.RUN_STARTED)  # no JOB_CREATED
    mgr = TriggerRuleManager(event_bus=bus)

    should_run, reason = mgr.should_execute(
        trigger_rule="all_success",
        requirements=[
            "events.run.started:fired",
            "events.job.created:fired",
        ],
        state={},
    )
    assert should_run is False


def test_trigger_manager_no_bus_treats_events_requirement_as_invalid():
    """Configuration mistake is loud, not silent."""
    mgr = TriggerRuleManager()  # no event_bus

    should_run, reason = mgr.should_execute(
        trigger_rule="all_success",
        requirements=["events.run.started:fired"],
        state={},
    )
    assert should_run is False
    assert "event_bus" in reason
