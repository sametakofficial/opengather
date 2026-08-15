"""S40 Phase E — job.output aggregated from plugin slots on complete."""

from unittest.mock import MagicMock

from archiverr.state.manager import GlobalStateManager


def _state():
    state = GlobalStateManager()
    persistence = MagicMock()
    persistence.save_run = MagicMock()
    persistence.save_plugin = MagicMock()
    persistence.save_job = MagicMock()
    state.configure(persistence=persistence)
    return state


def test_complete_job_aggregates_tasker_output_values():
    state = _state()
    state.start_run({})
    job_id = state.create_job("/x.mkv", {})
    state.apply_state_patch({
        "jobs": {
            job_id: {
                "plugins": {
                    "tasker": {
                        "output_values": ["/out/a.mkv"],
                        "tasks": {"save": {"success": True}},
                    }
                }
            }
        }
    })
    job = state.get_job_by_id(job_id)
    assert job.output.values == []
    state.complete_job(job.index)
    job = state.get_job_by_id(job_id)
    assert job.output.values == ["/out/a.mkv"]
    assert job.output.data["tasks"]["save"]["success"] is True
