"""E2E: startup recovery scan marks orphan non-terminal executions as
``crashed``.

WP-6 slim contract: no lease / heartbeat / atomic claim. The only recovery
surface is a one-shot startup scan (``Orchestrator._recover_crashed``)
that transitions any stale ``started`` / ``running`` plugin_execution
record to ``crashed``.
"""

from datetime import datetime, timedelta

from archiverr.core.orchestrator import Orchestrator


class _RecordingPersistence:
    """Tiny in-memory persistence stub for recovery assertions."""

    def __init__(self, unfinished):
        self._unfinished = list(unfinished)
        self.saved: list[dict] = []

    def get_unfinished_plugin_executions(self, run_id=None):
        return list(self._unfinished)

    def save_plugin_execution(
        self,
        run_id,
        job_id,
        plugin_name,
        state,
        attempt=1,
        error=None,
        timestamp=None,
    ):
        self.saved.append(
            {
                "run_id": run_id,
                "job_id": job_id,
                "plugin_name": plugin_name,
                "state": state,
                "attempt": attempt,
                "error": error,
                "timestamp": timestamp,
            }
        )


def _make_orch(persistence, mode="full"):
    orch = Orchestrator.__new__(Orchestrator)
    orch._persistence = persistence
    orch._persistence_mode = mode

    class _Logger:
        def warn(self, *a, **k):
            pass

        def debug(self, *a, **k):
            pass

        def info(self, *a, **k):
            pass

    orch._debugger = _Logger()
    return orch


def test_orphans_are_marked_crashed():
    stale_time = datetime.utcnow() - timedelta(minutes=10)
    orphans = [
        {
            "run_id": "run_old",
            "job_id": "job_old_0",
            "plugin_name": "tmdb",
            "state": "running",
            "attempt": 1,
            "updated_at": stale_time,
        },
        {
            "run_id": "run_old",
            "job_id": "job_old_1",
            "plugin_name": "ffprobe",
            "state": "started",
            "attempt": 1,
            "updated_at": stale_time,
        },
    ]
    persistence = _RecordingPersistence(orphans)
    orch = _make_orch(persistence)

    orch._recover_crashed()

    assert len(persistence.saved) == 2
    states = {rec["state"] for rec in persistence.saved}
    assert states == {"crashed"}
    plugins = {rec["plugin_name"] for rec in persistence.saved}
    assert plugins == {"tmdb", "ffprobe"}


def test_recovery_is_noop_when_no_orphans():
    persistence = _RecordingPersistence([])
    orch = _make_orch(persistence)
    orch._recover_crashed()
    assert persistence.saved == []


def test_recovery_skips_when_persistence_none():
    orch = _make_orch(persistence=None)
    # Should not raise.
    orch._recover_crashed()


def test_recovery_swallows_persistence_errors():
    class _Broken:
        def get_unfinished_plugin_executions(self, run_id=None):
            raise RuntimeError("connection lost")

    orch = _make_orch(_Broken())
    # Must not bubble up — the run continues.
    orch._recover_crashed()
