"""End-to-end tests for the data envelope flow (S39 R15 §F2).

Drives the full pipeline through ``GlobalStateManager`` so we
catch wiring regressions between:
  - DataResolver / DataResolverProxy (D1)
  - RunState.data field (D2)
  - PluginDataManager._recompute_data_envelope + save_run (D3)
  - GlobalStateManager.configure_resolver (D3 wiring)
  - The render context's `data` namespace (C1+C4)

These do NOT hit the real registry / orchestrator wiring (which
would require plugins on disk + manifest discovery); they cover
the data flow that the orchestrator's _configure_data_resolver
ultimately drives.
"""

from unittest.mock import MagicMock

from archiverr.core.render import ConfigRenderEngine
from archiverr.state.data_resolver import DataResolver, DataResolverProxy
from archiverr.state.manager import GlobalStateManager
from archiverr.state.template_context import TemplateContextBuilder


def _make_state():
    state = GlobalStateManager()
    persistence = MagicMock()
    persistence.save_run = MagicMock()
    persistence.save_plugin = MagicMock()
    persistence.save_job = MagicMock()
    state.configure(persistence=persistence)
    return state, persistence


def _make_emits():
    return {
        "tmdb": {"show": ["title.primary", "identifiers.tmdb_id",
                          "episode_title", "season_number"]},
        "omdb": {"show": ["title.primary"], "movie": ["title.primary"]},
    }


class TestEndToEnd:
    def test_envelope_populates_after_plugin_update(self):
        state, persistence = _make_state()
        state.start_run({})
        state.configure_resolver(
            data_priority={"data.<jobindex>.show": ["tmdb", "omdb"]},
            emits_map=_make_emits(),
        )
        # Create a job + write tmdb data
        job_id = state.create_job(input_value="/test.mkv", input_data={})
        state.update_plugin(
            target_id=job_id,
            plugin_name="tmdb",
            data={"show": {"title": {"primary": "Inception"},
                          "identifiers": {"tmdb_id": "27205"}}},
        )

        run = state.run
        # Envelope contains tmdb's flat values under jobindex 0.
        assert run.data == {
            0: {
                "show": {
                    "title": {"primary": "Inception"},
                    "identifiers": {"tmdb_id": "27205"},
                }
            }
        }
        # H12: save_run was called from the per_job update path.
        persistence.save_run.assert_called()

    def test_resolver_priority_first_plugin_wins(self):
        state, persistence = _make_state()
        state.start_run({})
        state.configure_resolver(
            data_priority={"data.<jobindex>.show": ["tmdb", "omdb"]},
            emits_map=_make_emits(),
        )
        job_id = state.create_job(input_value="/x.mkv", input_data={})

        # tmdb writes first, omdb second; tmdb wins per priority.
        state.update_plugin(
            target_id=job_id, plugin_name="tmdb",
            data={"show": {"title": {"primary": "TMDb"}}},
        )
        state.update_plugin(
            target_id=job_id, plugin_name="omdb",
            data={"show": {"title": {"primary": "OMDb"}}},
        )
        run = state.run
        assert run.data[0]["show"]["title"]["primary"] == "TMDb"

    def test_resolver_falls_through_when_tmdb_misses(self):
        state, persistence = _make_state()
        state.start_run({})
        state.configure_resolver(
            data_priority={"data.<jobindex>.show": ["tmdb", "omdb"]},
            emits_map=_make_emits(),
        )
        job_id = state.create_job(input_value="/x.mkv", input_data={})

        # tmdb omits title; omdb fills it in.
        state.update_plugin(
            target_id=job_id, plugin_name="tmdb",
            data={"show": {}},
        )
        state.update_plugin(
            target_id=job_id, plugin_name="omdb",
            data={"show": {"title": {"primary": "OMDb"}}},
        )
        run = state.run
        assert run.data[0]["show"]["title"]["primary"] == "OMDb"

    def test_envelope_empty_when_priority_unset(self):
        state, _ = _make_state()
        state.start_run({})
        # No configure_resolver call.
        job_id = state.create_job(input_value="/x.mkv", input_data={})
        state.update_plugin(
            target_id=job_id, plugin_name="tmdb",
            data={"show": {"title": {"primary": "X"}}},
        )
        # Resolver disabled -> envelope stays empty.
        assert state.run.data == {}

    def test_per_run_scope_envelope(self):
        state, _ = _make_state()
        state.start_run({})
        state.configure_resolver(
            data_priority={"scanner": ["scanner"]},
            emits_map={"scanner": {"scanner": ["count", "targets"]}},
            run_modes={"scanner": "per_run"},
        )
        # Per-run plugin update — note the run_<id> target convention.
        run_id = state.run.id
        state.update_plugin(
            target_id=run_id,
            plugin_name="scanner",
            data={"scanner": {"count": 3, "targets": ["a", "b", "c"]}},
        )
        run = state.run
        assert run.data == {
            "run": {"scanner": {"count": 3, "targets": ["a", "b", "c"]}},
        }


class TestRenderContextIntegration:
    """The render context exposes ``data`` from RunState.data; the proxy
    walks the same shape via the resolver. Both paths should produce
    identical leaf values for the same lookup."""

    def test_template_renders_via_jobs_descent(self):
        state, _ = _make_state()
        state.start_run({})
        state.configure_resolver(
            data_priority={"data.<jobindex>.show": ["tmdb"]},
            emits_map=_make_emits(),
        )
        job_id = state.create_job(input_value="/x.mkv", input_data={})
        state.update_plugin(
            target_id=job_id, plugin_name="tmdb",
            data={"show": {"title": {"primary": "Inception"}}},
        )

        ctx_builder = TemplateContextBuilder()
        ctx = ctx_builder.build_job_context(
            state.get_job_by_id(job_id),
            run=state.run,
            all_jobs=state.get_all_jobs(),
        )
        # Direct descent path resolves.
        engine = ConfigRenderEngine()
        out = engine.render_string(
            "{{ jobs[job_id].plugins.tmdb.show.title.primary }}", ctx,
        )
        assert out == "Inception"

    def test_data_namespace_via_proxy(self):
        state, _ = _make_state()
        state.start_run({})
        priority = {"data.<jobindex>.show": ["tmdb"]}
        state.configure_resolver(priority, _make_emits())

        job_id = state.create_job(input_value="/x.mkv", input_data={})
        state.update_plugin(
            target_id=job_id, plugin_name="tmdb",
            data={"show": {"title": {"primary": "Resolver-Title"}}},
        )

        # Build a proxy directly (the resolver-priority namespace).
        resolver = DataResolver(priority)
        job = state.get_job_by_id(job_id)
        run = state.run

        def _lookup(scope, plugin_name):
            if scope == "run":
                return run.plugins.get(plugin_name) if run else None
            if isinstance(scope, int) and job.index == scope:
                return job.plugins.get(plugin_name)
            return None

        proxy = DataResolverProxy(
            resolver, _lookup, active_index=job.index,
        )
        # Render via the proxy — same leaf value as direct descent.
        assert str(proxy["<jobindex>"].show.title.primary) == "Resolver-Title"

    def test_missing_chain_renders_empty(self):
        state, _ = _make_state()
        state.start_run({})
        state.configure_resolver(
            {"data.<jobindex>.show": ["tmdb"]}, _make_emits(),
        )
        job_id = state.create_job(input_value="/x.mkv", input_data={})
        # tmdb writes nothing.
        ctx = TemplateContextBuilder().build_job_context(
            state.get_job_by_id(job_id),
            run=state.run,
            all_jobs=state.get_all_jobs(),
        )
        engine = ConfigRenderEngine()
        out = engine.render_string(
            "{{ jobs[job_id].plugins.tmdb.show.title.primary }}", ctx,
        )
        # ChainableUndefined => "" (graceful empty).
        assert out == ""
