"""Unit tests for the data envelope recompute (S39 R15 §D3)."""

from unittest.mock import MagicMock

from archiverr.state.context import ExecutionContext
from archiverr.state.models import (
    InputData, JobState, RunState,
)
from archiverr.state.plugin_data_manager import PluginDataManager


def _make_manager():
    persistence = MagicMock()
    persistence.save_plugin = MagicMock()
    persistence.save_run = MagicMock()
    ctx = ExecutionContext()
    mgr = PluginDataManager(context=ctx, persistence=persistence)
    return mgr, ctx, persistence


def _add_job(ctx: ExecutionContext, job_id: str, index: int) -> JobState:
    job = JobState(index=index, run_id="run-1", id=job_id, input=InputData(value=f"/{job_id}.mkv"))
    ctx.add_job(job)
    return job


class TestRecomputeEnvelope:
    def test_no_priority_no_envelope(self):
        mgr, ctx, persistence = _make_manager()
        run = RunState(id="run-1")
        _add_job(ctx, "job-1", 0)

        mgr._update_job_plugin(
            "job-1", "tmdb",
            {"show": {"title": {"primary": "X"}}},
            ctx.get_job, run,
        )
        assert run.data == {}

    def test_envelope_populated_when_priority_set(self):
        mgr, ctx, persistence = _make_manager()
        run = RunState(id="run-1")
        _add_job(ctx, "job-1", 0)

        mgr.set_resolver_config(
            data_priority={"data.<jobindex>.show": ["tmdb", "omdb"]},
            emits_map={
                "tmdb": {"show": ["title.primary", "identifiers.tmdb_id"]},
                "omdb": {"show": ["title.primary"]},
            },
        )
        mgr._update_job_plugin(
            "job-1", "tmdb",
            {"show": {"title": {"primary": "Inception"},
                      "identifiers": {"tmdb_id": "27205"}}},
            ctx.get_job, run,
        )
        assert run.data == {
            0: {
                "show": {
                    "title": {"primary": "Inception"},
                    "identifiers": {"tmdb_id": "27205"},
                }
            }
        }

    def test_priority_first_plugin_wins(self):
        mgr, ctx, persistence = _make_manager()
        run = RunState(id="run-1")
        job = _add_job(ctx, "job-1", 0)

        mgr.set_resolver_config(
            data_priority={"data.<jobindex>.show": ["tmdb", "omdb"]},
            emits_map={
                "tmdb": {"show": ["title.primary"]},
                "omdb": {"show": ["title.primary"]},
            },
        )
        # tmdb wrote first; omdb second. tmdb wins per priority.
        mgr._update_job_plugin(
            "job-1", "tmdb",
            {"show": {"title": {"primary": "TMDb"}}}, ctx.get_job, run,
        )
        mgr._update_job_plugin(
            "job-1", "omdb",
            {"show": {"title": {"primary": "OMDb"}}}, ctx.get_job, run,
        )
        assert run.data[0]["show"]["title"]["primary"] == "TMDb"

    def test_per_run_scope(self):
        mgr, ctx, persistence = _make_manager()
        run = RunState(id="run-1")

        mgr.set_resolver_config(
            data_priority={"data.run.scanner": ["scanner"]},
            emits_map={"scanner": {"scanner": ["count", "targets"]}},
        )
        mgr._update_run_plugin(
            "run-1", "scanner",
            {"scanner": {"count": 3, "targets": ["a", "b", "c"]}}, run,
        )
        assert run.data["run"]["scanner"]["count"] == 3
        assert run.data["run"]["scanner"]["targets"] == ["a", "b", "c"]

    def test_save_run_called_on_job_plugin_update(self):
        """Audit H12 fix: per_job updates must persist run.data."""
        mgr, ctx, persistence = _make_manager()
        run = RunState(id="run-1")
        _add_job(ctx, "job-1", 0)

        mgr.set_resolver_config(
            data_priority={"data.<jobindex>.show": ["tmdb"]},
            emits_map={"tmdb": {"show": ["title.primary"]}},
        )
        mgr._update_job_plugin(
            "job-1", "tmdb",
            {"show": {"title": {"primary": "X"}}}, ctx.get_job, run,
        )
        persistence.save_run.assert_called()

    def test_save_run_skipped_when_run_none(self):
        """Don't fail when run isn't passed (legacy callsites)."""
        mgr, ctx, persistence = _make_manager()
        _add_job(ctx, "job-1", 0)

        mgr._update_job_plugin(
            "job-1", "tmdb",
            {"show": {"x": "y"}}, ctx.get_job, run=None,
        )
        persistence.save_run.assert_not_called()


class TestMultipleJobs:
    def test_envelope_updates_for_correct_jobindex(self):
        mgr, ctx, persistence = _make_manager()
        run = RunState(id="run-1")
        _add_job(ctx, "job-A", 0)
        _add_job(ctx, "job-B", 1)

        mgr.set_resolver_config(
            data_priority={"data.<jobindex>.show": ["tmdb"]},
            emits_map={"tmdb": {"show": ["title.primary"]}},
        )

        mgr._update_job_plugin(
            "job-A", "tmdb",
            {"show": {"title": {"primary": "A-show"}}}, ctx.get_job, run,
        )
        mgr._update_job_plugin(
            "job-B", "tmdb",
            {"show": {"title": {"primary": "B-show"}}}, ctx.get_job, run,
        )
        assert run.data[0]["show"]["title"]["primary"] == "A-show"
        assert run.data[1]["show"]["title"]["primary"] == "B-show"


class TestThreadSafety:
    def test_lock_present(self):
        mgr, _, _ = _make_manager()
        # The lock attribute exists and is a real threading.Lock.
        import threading
        assert isinstance(mgr._envelope_lock, type(threading.Lock()))
