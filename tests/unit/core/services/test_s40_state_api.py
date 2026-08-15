"""S40 read_state / update_state / jobid."""

from unittest.mock import MagicMock, Mock

import pytest

from archiverr.core.services.plugin_services import PluginServices
from archiverr.state.manager import GlobalStateManager


def _make_state():
    state = GlobalStateManager()
    persistence = MagicMock()
    persistence.save_run = MagicMock()
    persistence.save_plugin = MagicMock()
    persistence.save_job = MagicMock()
    state.configure(persistence=persistence)
    return state


def _services(state, *, job_id=None, plugin="tmdb", mode="per_job"):
    return PluginServices(
        state=state,
        event_bus=None,
        logger=Mock(),
        config={},
        mode=mode,
        current_job_id=job_id,
        current_plugin_name=plugin,
        run_safety={"dry_run": True, "hardlink": False, "no_delete": True},
    )


def test_create_job_then_update_state_and_read():
    state = _make_state()
    state.start_run({})
    services = _services(state, plugin="scanner", mode="per_run")
    job_id = services.create_job("/x.mkv", {"source": "scanner"})
    job_services = _services(state, job_id=job_id, plugin="tmdb")
    assert job_services.jobid == job_id

    job_services.update_state({
        "jobs": {job_id: {"plugins": {"tmdb": {"show": {"title": {"primary": "BB"}}}}}}
    })
    snapshot = job_services.read_state()
    assert snapshot["jobs"][job_id]["plugins"]["tmdb"]["show"]["title"]["primary"] == "BB"
    assert job_services.read_state(f"jobs.{job_id}.input.value") == "/x.mkv"


def test_update_state_refuses_unknown_job():
    state = _make_state()
    state.start_run({})
    services = _services(state, plugin="tmdb")
    with pytest.raises(ValueError, match="create_job"):
        services.update_state({
            "jobs": {"job_missing_0": {"plugins": {"tmdb": {"x": 1}}}}
        })


def test_per_run_plugin_write_and_jobid_none():
    state = _make_state()
    state.start_run({})
    services = _services(state, job_id=None, plugin="scanner", mode="per_run")
    assert services.jobid is None
    services.update_state({"plugins": {"scanner": {"count": 2}}})
    assert services.read_state("plugins.scanner.count") == 2


def test_merge_keeps_existing_plugin_fields():
    state = _make_state()
    state.start_run({})
    job_id = state.create_job("/x.mkv", {})
    services = _services(state, job_id=job_id)
    services.update_state({
        "jobs": {job_id: {"plugins": {"tmdb": {"show": {"title": "A", "year": 2008}}}}}
    })
    services.update_state({
        "jobs": {job_id: {"plugins": {"tmdb": {"show": {"year": 2009}}}}}
    })
    show = services.read_state(f"jobs.{job_id}.plugins.tmdb.show")
    assert show == {"title": "A", "year": 2009}
