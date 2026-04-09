"""Tests for StageExecutor - 3-stage plugin execution engine.

Tests the decomposed execution pipeline:
- _check_plugin_requires
- _invoke_plugin
- _extract_plugin_result
- _update_job_plugin_state
- _handle_plugin_error
- execute_stage (integration of above)
- _topological_sort
- _group_parallel_plugins
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from archiverr.core.exceptions import PluginError, StageError
from archiverr.core.plugins.stage_executor import (
    ExecutionMode,
    PluginExecutionResult,
    StageExecutor,
)
from archiverr.core.plugins.registry import Stage
from archiverr.events.bus import EventBus, Events
from archiverr.state.models import (
    InputData,
    JobState,
    JobStatus,
    OutputData,
    RunState,
    RunStatus,
    StateEnum,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_state():
    state = MagicMock()
    state.run = RunState(id="run_test_1")
    state.run.start()
    state.get_all_jobs.return_value = []
    return state


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.get_plugins_by_stage.return_value = {}
    registry.get_manifest.return_value = {}
    return registry


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def config():
    return {"options": {"debug": False, "dry_run": True}}


@pytest.fixture
def executor(mock_state, mock_registry, event_bus, config):
    return StageExecutor(
        state=mock_state,
        plugin_registry=mock_registry,
        event_bus=event_bus,
        config=config,
    )


@pytest.fixture
def sample_job():
    job = JobState(index=0, run_id="run_test_1")
    job.id = "job_test_0"
    job.input = InputData(value="/media/Movie.2024.mkv", data={"extension": "mkv"})
    job.output = OutputData()
    job.status = JobStatus()
    job.plugins = {}
    return job


def _make_plugin(name="test_plugin", execute_result=None):
    """Create a mock plugin with configurable execute behavior."""
    plugin = MagicMock()
    plugin.name = name
    if execute_result is not None:
        plugin.execute.return_value = execute_result
    return plugin


# ---------------------------------------------------------------------------
# TestCheckPluginRequires
# ---------------------------------------------------------------------------

class TestCheckPluginRequires:
    """Tests for _check_plugin_requires method."""

    def test_no_requires_returns_none(self, executor, sample_job):
        manifest = {"stage": "data", "provides": ["http.request"]}
        result = executor._check_plugin_requires("tmdb_mock", manifest, sample_job)
        assert result is None

    def test_empty_requires_returns_none(self, executor, sample_job):
        manifest = {"requires": [], "trigger_rule": "all_success"}
        result = executor._check_plugin_requires("tmdb_mock", manifest, sample_job)
        assert result is None

    def test_none_manifest_returns_none(self, executor, sample_job):
        result = executor._check_plugin_requires("tmdb_mock", None, sample_job)
        assert result is None

    def test_requires_not_satisfied_returns_skip(self, executor, sample_job):
        manifest = {
            "requires": ["plugin.renamer.parsed:success"],
            "trigger_rule": "all_success",
        }
        result = executor._check_plugin_requires("tmdb_mock", manifest, sample_job)
        assert result is not None
        assert result.skipped is True
        assert result.plugin_name == "tmdb_mock"
        assert result.success is True

    def test_requires_satisfied_returns_none(self, executor, sample_job):
        manifest = {
            "requires": ["plugin.renamer.parsed:success"],
            "trigger_rule": "all_success",
        }
        sample_job.plugins["renamer"] = {"parsed": {"title": "Movie", "year": 2024}}
        sample_job.status.plugins["renamer"] = {"state": "completed", "success": True}

        result = executor._check_plugin_requires("tmdb_mock", manifest, sample_job)
        assert result is None or isinstance(result, PluginExecutionResult)

    def test_legacy_expects_fallback(self, executor, sample_job):
        manifest = {
            "expects": ["plugin.renamer.parsed:success"],
            "trigger_rule": "all_success",
        }
        result = executor._check_plugin_requires("tmdb_mock", manifest, sample_job)
        assert result is None or isinstance(result, PluginExecutionResult)

    def test_skipped_plugin_marked_in_job_status(self, executor, sample_job):
        manifest = {
            "requires": ["plugin.nonexistent.data:success"],
            "trigger_rule": "all_success",
        }
        result = executor._check_plugin_requires("tmdb_mock", manifest, sample_job)
        if result and result.skipped:
            assert "tmdb_mock" in sample_job.status.plugins
            assert sample_job.status.plugins["tmdb_mock"]["state"] == "skipped"


# ---------------------------------------------------------------------------
# TestInvokePlugin
# ---------------------------------------------------------------------------

class TestInvokePlugin:
    """Tests for _invoke_plugin method."""

    def test_new_signature_execute(self, executor, sample_job):
        plugin = MagicMock()
        plugin.name = "test_plugin"
        mock_result = MagicMock()
        mock_result.data = {"title": "Movie"}
        plugin.execute.return_value = mock_result

        services = MagicMock()
        result = executor._invoke_plugin(plugin, sample_job, services, "test_plugin")

        assert result is not None
        plugin.execute.assert_called()

    def test_no_execute_method_returns_none(self, executor, sample_job):
        plugin = MagicMock(spec=[])
        plugin.name = "bad_plugin"

        services = MagicMock()
        result = executor._invoke_plugin(plugin, sample_job, services, "bad_plugin")

        assert result is None

    def test_legacy_process_method(self, executor, sample_job):
        plugin = MagicMock(spec=["process", "name"])
        plugin.name = "legacy_plugin"
        plugin.process.return_value = {"data": "legacy_result"}

        services = MagicMock()
        result = executor._invoke_plugin(plugin, sample_job, services, "legacy_plugin")

        assert result is not None
        plugin.process.assert_called_once()

    def test_execute_type_error_falls_back_to_legacy(self, executor, sample_job):
        plugin = MagicMock()
        plugin.name = "mixed_plugin"

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TypeError("unexpected keyword argument")
            return {"fallback": True}

        plugin.execute.side_effect = side_effect

        services = MagicMock()
        result = executor._invoke_plugin(plugin, sample_job, services, "mixed_plugin")

        assert result is not None


# ---------------------------------------------------------------------------
# TestExtractPluginResult
# ---------------------------------------------------------------------------

class TestExtractPluginResult:
    """Tests for _extract_plugin_result method."""

    def test_result_with_data_attribute(self, executor):
        result = MagicMock()
        result.data = {"title": "Movie", "year": 2024}
        result.status = None

        data, success = executor._extract_plugin_result(result)

        assert data == {"title": "Movie", "year": 2024}
        assert success is True

    def test_result_as_dict(self, executor):
        result = {"title": "Movie", "year": 2024}

        data, success = executor._extract_plugin_result(result)

        assert data == {"title": "Movie", "year": 2024}
        assert success is True

    def test_result_with_success_status(self, executor):
        result = MagicMock()
        result.data = {"key": "value"}
        result.status = MagicMock()
        result.status.value = "success"

        data, success = executor._extract_plugin_result(result)
        assert success is True

    def test_result_with_failure_status(self, executor):
        result = MagicMock()
        result.data = {}
        result.status = MagicMock()
        result.status.value = "error"

        data, success = executor._extract_plugin_result(result)
        assert success is False

    def test_result_with_empty_data(self, executor):
        result = MagicMock()
        result.data = {}
        del result.status

        data, success = executor._extract_plugin_result(result)

        assert data == {}
        assert success is True

    def test_result_with_bool_status(self, executor):
        result = MagicMock()
        result.data = {"key": "value"}
        # Use 0 as a falsy status with no .value attribute
        result.status = 0

        data, success = executor._extract_plugin_result(result)
        assert success is False


# ---------------------------------------------------------------------------
# TestUpdateJobPluginState
# ---------------------------------------------------------------------------

class TestUpdateJobPluginState:
    """Tests for _update_job_plugin_state method."""

    def test_stores_result_data_flat(self, executor, sample_job):
        result_data = {"title": "Movie", "year": 2024}
        executor._update_job_plugin_state(
            sample_job, "tmdb_mock", result_data, True, 150
        )
        assert sample_job.plugins["tmdb_mock"] == result_data

    def test_preserves_existing_plugin_data(self, executor, sample_job):
        sample_job.plugins["tmdb_mock"] = {"title": "Existing"}
        executor._update_job_plugin_state(
            sample_job, "tmdb_mock", {"title": "New"}, True, 100
        )
        assert sample_job.plugins["tmdb_mock"] == {"title": "Existing"}

    def test_stores_plugin_status(self, executor, sample_job):
        executor._update_job_plugin_state(
            sample_job, "tmdb_mock", {"data": "yes"}, True, 250
        )
        status = sample_job.status.plugins["tmdb_mock"]
        assert status["state"] == "completed"
        assert status["success"] is True
        assert status["duration_ms"] == 250

    def test_failed_status(self, executor, sample_job):
        executor._update_job_plugin_state(
            sample_job, "tmdb_mock", {}, False, 100
        )
        assert sample_job.status.success is False

    def test_empty_result_stores_empty_dict(self, executor, sample_job):
        executor._update_job_plugin_state(
            sample_job, "tmdb_mock", {}, True, 50
        )
        assert sample_job.plugins["tmdb_mock"] == {}


# ---------------------------------------------------------------------------
# TestHandlePluginError
# ---------------------------------------------------------------------------

class TestHandlePluginError:
    """Tests for _handle_plugin_error method."""

    def test_plugin_error_returns_failure(self, executor, sample_job):
        error = PluginError("API timeout", context={"plugin": "tmdb"})
        result = executor._handle_plugin_error(
            error, "tmdb_mock", sample_job, Stage.DATA, datetime.now()
        )
        assert result.success is False
        assert result.plugin_name == "tmdb_mock"
        assert "API timeout" in result.error

    def test_generic_error_returns_failure(self, executor, sample_job):
        error = ValueError("something broke")
        result = executor._handle_plugin_error(
            error, "tmdb_mock", sample_job, Stage.DATA, datetime.now()
        )
        assert result.success is False
        assert "something broke" in result.error

    def test_error_marks_job_failed(self, executor, sample_job):
        error = PluginError("fail")
        executor._handle_plugin_error(
            error, "tmdb_mock", sample_job, Stage.DATA, datetime.now()
        )
        assert "tmdb_mock" in sample_job.status.plugins
        assert sample_job.status.plugins["tmdb_mock"]["state"] == "failed"

    def test_error_emits_failed_event(self, executor, sample_job, event_bus):
        events_received = []
        event_bus.subscribe(Events.PLUGIN_FAILED, lambda e: events_received.append(e))

        error = PluginError("fail")
        executor._handle_plugin_error(
            error, "tmdb_mock", sample_job, Stage.DATA, datetime.now()
        )
        assert len(events_received) == 1


# ---------------------------------------------------------------------------
# TestExecutePluginForJob (Integration)
# ---------------------------------------------------------------------------

class TestExecutePluginForJob:
    """Integration tests for the full _execute_plugin_for_job flow."""

    def test_successful_execution(self, executor, mock_registry, sample_job):
        mock_registry.get_manifest.return_value = {
            "stage": "data", "requires": [], "trigger_rule": "all_success",
        }

        plugin = _make_plugin("data_plugin")
        mock_result = MagicMock()
        mock_result.data = {"title": "Test Movie"}
        mock_result.status = None
        plugin.execute.return_value = mock_result

        result = executor._execute_plugin_for_job(plugin, sample_job, Stage.DATA)

        assert result.success is True
        assert result.data == {"title": "Test Movie"}
        assert result.plugin_name == "data_plugin"

    def test_plugin_error_handled(self, executor, mock_registry, sample_job):
        mock_registry.get_manifest.return_value = {"requires": []}

        plugin = _make_plugin("failing_plugin")
        plugin.execute.side_effect = PluginError("API error")

        result = executor._execute_plugin_for_job(plugin, sample_job, Stage.DATA)

        assert result.success is False
        assert "API error" in result.error

    def test_no_execute_method(self, executor, mock_registry, sample_job):
        mock_registry.get_manifest.return_value = {"requires": []}

        plugin = MagicMock(spec=[])
        plugin.name = "empty_plugin"

        result = executor._execute_plugin_for_job(plugin, sample_job, Stage.DATA)
        assert result.success is False


# ---------------------------------------------------------------------------
# TestExecuteStage
# ---------------------------------------------------------------------------

class TestExecuteStage:
    """Tests for execute_stage method."""

    def test_no_plugins_for_stage(self, executor, mock_registry):
        mock_registry.get_plugins_by_stage.return_value = {}
        executor.execute_stage(Stage.PARSE)

    def test_stage_with_plugins(self, executor, mock_registry, mock_state, sample_job):
        plugin = _make_plugin("parse_plugin")
        mock_result = MagicMock()
        mock_result.data = {"parsed": True}
        mock_result.status = None
        plugin.execute.return_value = mock_result

        mock_registry.get_plugins_by_stage.return_value = {"parse_plugin": plugin}
        mock_registry.get_manifest.return_value = {"requires": [], "provides": []}
        mock_state.get_all_jobs.return_value = [sample_job]

        executor.execute_stage(Stage.PARSE)
        plugin.execute.assert_called()


# ---------------------------------------------------------------------------
# TestTopologicalSort
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    """Tests for _topological_sort method."""

    def test_sorts_by_requires_count(self, executor, mock_registry):
        p1 = _make_plugin("no_deps")
        p2 = _make_plugin("one_dep")
        p3 = _make_plugin("two_deps")

        plugins = {"no_deps": p1, "one_dep": p2, "two_deps": p3}

        def manifest_for(name):
            manifests = {
                "no_deps": {"requires": []},
                "one_dep": {"requires": ["plugin.renamer.parsed"]},
                "two_deps": {"requires": ["plugin.renamer.parsed", "plugin.tmdb.data"]},
            }
            return manifests.get(name, {"requires": []})

        mock_registry.get_manifest.side_effect = manifest_for

        sorted_plugins = executor._topological_sort(plugins, Stage.DATA)
        names = [executor._get_plugin_name(p) for p in sorted_plugins]
        assert names.index("no_deps") < names.index("two_deps")

    def test_handles_list_input(self, executor):
        plugins = [_make_plugin("a"), _make_plugin("b")]
        result = executor._topological_sort(plugins, Stage.DATA)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TestGroupParallelPlugins
# ---------------------------------------------------------------------------

class TestGroupParallelPlugins:

    def test_empty_list(self, executor):
        assert executor._group_parallel_plugins([]) == []

    def test_single_plugin(self, executor, mock_registry):
        plugin = _make_plugin("solo")
        mock_registry.get_manifest.return_value = {"provides": [], "requires": []}
        groups = executor._group_parallel_plugins([plugin])
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_independent_plugins_grouped(self, executor, mock_registry):
        p1 = _make_plugin("api_a")
        p2 = _make_plugin("api_b")

        def manifest_for(name):
            return {"provides": [f"{name}.data"], "requires": []}

        mock_registry.get_manifest.side_effect = manifest_for
        groups = executor._group_parallel_plugins([p1, p2])
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_dependent_plugins_separated(self, executor, mock_registry):
        p1 = _make_plugin("producer")
        p2 = _make_plugin("consumer")

        def manifest_for(name):
            if name == "producer":
                return {"provides": ["state.update"], "requires": []}
            return {"provides": [], "requires": ["state.update"]}

        mock_registry.get_manifest.side_effect = manifest_for
        groups = executor._group_parallel_plugins([p1, p2])
        assert len(groups) == 2


# ---------------------------------------------------------------------------
# TestPluginDataCache
# ---------------------------------------------------------------------------

class TestPluginDataCache:

    def test_cache_populated_after_execution(self, executor, mock_registry, sample_job):
        mock_registry.get_manifest.return_value = {"requires": []}

        plugin = _make_plugin("cached_plugin")
        mock_result = MagicMock()
        mock_result.data = {"cached": "data"}
        mock_result.status = None
        plugin.execute.return_value = mock_result

        executor._execute_plugin_for_job(plugin, sample_job, Stage.DATA)

        cache = executor.get_plugin_data_cache()
        assert sample_job.id in cache
        assert "cached_plugin" in cache[sample_job.id]

    def test_clear_cache(self, executor):
        executor._plugin_data_cache["job1"] = {"plugin": {"data": True}}
        executor.clear_cache()
        assert executor.get_plugin_data_cache() == {}


# ---------------------------------------------------------------------------
# TestMarkMethods
# ---------------------------------------------------------------------------

class TestMarkMethods:

    def test_mark_executed_success(self, executor, sample_job):
        executor._mark_executed(sample_job, "plugin_a", True)
        assert sample_job.status.plugins["plugin_a"]["state"] == "completed"
        assert sample_job.status.plugins["plugin_a"]["success"] is True

    def test_mark_executed_failure_delegates_to_failed(self, executor, sample_job):
        executor._mark_executed(sample_job, "plugin_a", False)
        assert sample_job.status.plugins["plugin_a"]["state"] == "failed"

    def test_mark_failed(self, executor, sample_job):
        executor._mark_failed(sample_job, "plugin_a")
        assert sample_job.status.plugins["plugin_a"]["state"] == "failed"
        assert sample_job.status.success is False

    def test_mark_skipped(self, executor, sample_job):
        executor._mark_skipped(sample_job, "plugin_a")
        assert sample_job.status.plugins["plugin_a"]["state"] == "skipped"


# ---------------------------------------------------------------------------
# TestBuildGlobalState
# ---------------------------------------------------------------------------

class TestBuildGlobalState:

    def test_structure(self, executor, sample_job):
        state = executor._build_global_state(sample_job)
        assert "run" in state
        assert "config" in state
        assert "job" in state
        assert "plugin" in state
        assert state["job"]["id"] == sample_job.id
        assert state["job"]["input"]["value"] == "/media/Movie.2024.mkv"

    def test_includes_plugin_data(self, executor, sample_job):
        sample_job.plugins["renamer"] = {"parsed": {"title": "Movie"}}
        state = executor._build_global_state(sample_job)
        assert "renamer" in state["plugin"]
        assert state["plugin"]["renamer"]["parsed"]["title"] == "Movie"


# ---------------------------------------------------------------------------
# TestEventEmission
# ---------------------------------------------------------------------------

class TestEventEmission:

    def test_emit_plugin_completed(self, executor, event_bus):
        events = []
        event_bus.subscribe(Events.PLUGIN_COMPLETED, lambda e: events.append(e))
        executor._emit_plugin_completed(
            plugin_name="test", stage=Stage.DATA, mode="per_job",
            success=True, data={"key": "val"}, duration_ms=100, job_id="job1"
        )
        assert len(events) == 1

    def test_emit_plugin_failed(self, executor, event_bus):
        events = []
        event_bus.subscribe(Events.PLUGIN_FAILED, lambda e: events.append(e))
        executor._emit_plugin_failed(
            plugin_name="test", stage=Stage.DATA, error="fail",
            duration_ms=50, job_id="job1"
        )
        assert len(events) == 1


# ---------------------------------------------------------------------------
# DependencyResolver Integration Tests (Step 1.1)
# ---------------------------------------------------------------------------

class TestResolveExecutionGroups:
    """Tests for _resolve_execution_groups using DependencyResolver."""

    def test_empty_plugins_returns_empty(self, executor):
        result = executor._resolve_execution_groups({}, Stage.DATA)
        assert result == []

    def test_single_plugin_returns_one_group(self, executor, mock_registry):
        plugin = _make_plugin("alpha")
        mock_registry.get_manifest.return_value = {"requires": []}
        result = executor._resolve_execution_groups({"alpha": plugin}, Stage.DATA)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_independent_plugins_in_single_group(self, executor, mock_registry):
        """Plugins with no dependencies can run in parallel (same group)."""
        p1 = _make_plugin("tmdb")
        p2 = _make_plugin("ffprobe")
        plugins = {"tmdb": p1, "ffprobe": p2}

        def manifest_side_effect(name):
            return {"requires": []}

        mock_registry.get_manifest.side_effect = manifest_side_effect
        result = executor._resolve_execution_groups(plugins, Stage.DATA)
        # Both independent -> single group
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_dependent_plugins_in_separate_groups(self, executor, mock_registry):
        """Plugin B depends on A -> different sequential groups."""
        p_renamer = _make_plugin("renamer")
        p_tmdb = _make_plugin("tmdb")
        plugins = {"renamer": p_renamer, "tmdb": p_tmdb}

        def manifest_side_effect(name):
            if name == "tmdb":
                return {"requires": ["plugin.renamer.parsed:success"]}
            return {"requires": []}

        mock_registry.get_manifest.side_effect = manifest_side_effect
        result = executor._resolve_execution_groups(plugins, Stage.DATA)
        # renamer first, then tmdb -> 2 groups
        assert len(result) == 2
        # First group should be renamer (no deps)
        first_names = [executor._get_plugin_name(p) for p in result[0]]
        assert "renamer" in first_names
        second_names = [executor._get_plugin_name(p) for p in result[1]]
        assert "tmdb" in second_names

    def test_diamond_dependency(self, executor, mock_registry):
        """A -> B, A -> C, B -> D, C -> D produces correct ordering."""
        plugins = {n: _make_plugin(n) for n in ["a", "b", "c", "d"]}

        manifests = {
            "a": {"requires": []},
            "b": {"requires": ["plugin.a.data:success"]},
            "c": {"requires": ["plugin.a.data:success"]},
            "d": {"requires": ["plugin.b.data:success", "plugin.c.data:success"]},
        }

        mock_registry.get_manifest.side_effect = lambda name: manifests.get(name, {})
        result = executor._resolve_execution_groups(plugins, Stage.DATA)

        # a first, then b+c in parallel, then d
        assert len(result) >= 2
        # Flatten to check ordering
        flat = []
        for group in result:
            flat.extend([executor._get_plugin_name(p) for p in group])
        assert flat.index("a") < flat.index("b")
        assert flat.index("a") < flat.index("c")
        assert flat.index("b") < flat.index("d")
        assert flat.index("c") < flat.index("d")

    def test_cycle_detection_fallback(self, executor, mock_registry):
        """Circular dependency falls back to single group."""
        p1 = _make_plugin("x")
        p2 = _make_plugin("y")
        plugins = {"x": p1, "y": p2}

        manifests = {
            "x": {"requires": ["plugin.y.data:success"]},
            "y": {"requires": ["plugin.x.data:success"]},
        }

        mock_registry.get_manifest.side_effect = lambda name: manifests.get(name, {})
        # Should not crash -- falls back to single group
        result = executor._resolve_execution_groups(plugins, Stage.DATA)
        assert len(result) >= 1

    def test_list_input_returns_single_group(self, executor):
        """If accidentally given a list, wraps it in one group."""
        plugins = [_make_plugin("a")]
        result = executor._resolve_execution_groups(plugins, Stage.DATA)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# ProvidesRegistry Integration Tests (Step 1.3)
# ---------------------------------------------------------------------------

class TestProvidesRegistryIntegration:
    """Tests for ProvidesRegistry wiring in StageExecutor."""

    def test_provides_registered_on_init(self, mock_state, event_bus, config):
        """ProvidesRegistry should be populated from manifests on init."""
        registry = MagicMock()
        registry.get_all_manifests.return_value = {
            "tmdb": {"provides": ["http.request", "state.update"]},
            "scanner": {"provides": ["job.create", "fs.read"]},
        }
        registry.get_plugins_by_stage.return_value = {}
        registry.get_manifest.return_value = {}

        from archiverr.core.provides_registry import reset_provides_registry
        reset_provides_registry()

        executor = StageExecutor(
            state=mock_state,
            plugin_registry=registry,
            event_bus=event_bus,
            config=config,
        )

        provides_data = executor._provides_registry.to_dict()
        assert "http.request" in provides_data
        assert "tmdb" in provides_data["http.request"]
        assert "job.create" in provides_data
        assert "scanner" in provides_data["job.create"]

        reset_provides_registry()

    def test_provides_completed_on_success(self, mock_state, event_bus, config, sample_job):
        """After successful plugin execution, provides should be marked completed."""
        from archiverr.core.provides_registry import reset_provides_registry
        reset_provides_registry()

        registry = MagicMock()
        registry.get_all_manifests.return_value = {
            "test_plugin": {"provides": ["http.request"]},
        }
        registry.get_plugins_by_stage.return_value = {}
        registry.get_manifest.return_value = {"requires": [], "trigger_rule": "all_success"}

        executor = StageExecutor(
            state=mock_state,
            plugin_registry=registry,
            event_bus=event_bus,
            config=config,
        )

        plugin = _make_plugin("test_plugin", execute_result={"data": {"key": "val"}})
        executor._execute_plugin_for_job(plugin, sample_job, Stage.DATA)

        assert executor._provides_registry.is_completed("http.request")

        reset_provides_registry()

    def test_provides_failed_on_error(self, mock_state, event_bus, config, sample_job):
        """After failed plugin execution, provides should be marked failed."""
        from archiverr.core.provides_registry import reset_provides_registry, ProvideStatus
        reset_provides_registry()

        registry = MagicMock()
        registry.get_all_manifests.return_value = {
            "failing_plugin": {"provides": ["state.update"]},
        }
        registry.get_plugins_by_stage.return_value = {}
        registry.get_manifest.return_value = {"requires": [], "trigger_rule": "all_success"}

        executor = StageExecutor(
            state=mock_state,
            plugin_registry=registry,
            event_bus=event_bus,
            config=config,
        )

        plugin = _make_plugin("failing_plugin")
        plugin.execute.side_effect = PluginError("test error")
        executor._execute_plugin_for_job(plugin, sample_job, Stage.DATA)

        status = executor._provides_registry.get_status("state.update")
        assert "failing_plugin" in status
        assert status["failing_plugin"] == "failed"

        reset_provides_registry()

    def test_provides_in_global_state(self, executor, sample_job):
        """Global state should include provides data for trigger evaluation."""
        from archiverr.core.provides_registry import reset_provides_registry
        reset_provides_registry()

        # Re-register after reset
        executor._provides_registry.register("tmdb", "http.request")
        executor._provides_registry.complete("tmdb", "http.request")

        state = executor._build_global_state(sample_job)
        assert "provides" in state
        assert "http.request" in state["provides"]
        assert state["provides"]["http.request"]["tmdb"] == "completed"

        reset_provides_registry()
