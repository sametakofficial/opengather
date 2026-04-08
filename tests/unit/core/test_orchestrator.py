"""Tests for Orchestrator - Main execution coordinator.

Tests the orchestrator lifecycle:
- run() happy path and error paths
- _initialize (plugin discovery, validation)
- _execute_stages (3-stage best-effort execution)
- _finalize (state completion, events)
- build_orchestrator factory
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch, PropertyMock

from archiverr.core.exceptions import CriticalError, PluginError, StageError
from archiverr.core.orchestrator import Orchestrator, build_orchestrator
from archiverr.core.plugins.registry import Stage
from archiverr.core.result_builder import RunResult
from archiverr.events.bus import EventBus, Events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.start_run.return_value = "run_test_1"
    state.run = MagicMock()
    state.run.status = MagicMock()
    state.run.status.total_jobs = 0
    state.run.status.completed = 0
    state.run.status.failed = 0
    return state


@pytest.fixture
def mock_persistence():
    return MagicMock()


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.total_loaded = 3
    registry.total_discovered = 3
    registry.enabled_plugins = ["plugin_a", "plugin_b", "plugin_c"]
    registry.get_all_manifests.return_value = {}
    registry.validate_dependencies.return_value = []
    return registry


@pytest.fixture
def config():
    return {
        "options": {"debug": False, "dry_run": True},
        "plugins": {"plugin_a": {"enabled": True}},
    }


@pytest.fixture
def orchestrator(event_bus, mock_state, mock_persistence, mock_registry, config):
    return Orchestrator(
        event_bus=event_bus,
        state=mock_state,
        persistence=mock_persistence,
        plugin_registry=mock_registry,
        config=config,
    )


# ---------------------------------------------------------------------------
# TestOrchestratorInit
# ---------------------------------------------------------------------------

class TestOrchestratorInit:

    def test_accepts_all_dependencies(
        self, event_bus, mock_state, mock_persistence, mock_registry, config
    ):
        orch = Orchestrator(
            event_bus=event_bus,
            state=mock_state,
            persistence=mock_persistence,
            plugin_registry=mock_registry,
            config=config,
        )
        assert orch._event_bus is event_bus
        assert orch._state is mock_state
        assert orch._persistence is mock_persistence
        assert orch._plugin_registry is mock_registry
        assert orch._config is config

    def test_initial_state_is_clean(self, orchestrator):
        assert orchestrator._run_id is None
        assert orchestrator._start_time is None
        assert orchestrator._stages_completed == []
        assert orchestrator._stages_failed == []


# ---------------------------------------------------------------------------
# TestOrchestratorRun
# ---------------------------------------------------------------------------

class TestOrchestratorRun:

    def test_run_happy_path(self, orchestrator, mock_registry, mock_state):
        """Full successful run lifecycle."""
        mock_registry.get_all_manifests.return_value = {}

        # Mock FSLockManager to pass validation
        orchestrator._fs_lock_manager = MagicMock()
        orchestrator._fs_lock_manager.validate_all_manifests.return_value = (True, [])
        orchestrator._fs_lock_manager.detect_conflicts.return_value = []

        # Mock state dumper
        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        # Mock stage executor
        with patch.object(orchestrator, '_execute_stages'):
            with patch.object(orchestrator, '_execute_per_run_plugins'):
                result = orchestrator.run()

        assert isinstance(result, RunResult)
        mock_state.start_run.assert_called_once()
        mock_state.complete_run.assert_called_once()

    def test_run_emits_events(self, orchestrator, event_bus, mock_registry):
        """Run should emit RUN_STARTED and RUN_COMPLETED events."""
        events = []
        event_bus.subscribe(Events.RUN_STARTED, lambda e: events.append(("start", e)))
        event_bus.subscribe(Events.RUN_COMPLETED, lambda e: events.append(("complete", e)))

        orchestrator._fs_lock_manager = MagicMock()
        orchestrator._fs_lock_manager.validate_all_manifests.return_value = (True, [])
        orchestrator._fs_lock_manager.detect_conflicts.return_value = []
        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        with patch.object(orchestrator, '_execute_stages'):
            with patch.object(orchestrator, '_execute_per_run_plugins'):
                orchestrator.run()

        event_names = [e[0] for e in events]
        assert "start" in event_names
        assert "complete" in event_names


# ---------------------------------------------------------------------------
# TestOrchestratorInitialize
# ---------------------------------------------------------------------------

class TestOrchestratorInitialize:

    def test_no_plugins_raises_critical_error(self, orchestrator, mock_registry):
        """Zero loaded plugins should raise CriticalError."""
        mock_registry.total_loaded = 0
        mock_registry.total_discovered = 5

        with pytest.raises(CriticalError) as exc_info:
            orchestrator._initialize()

        assert "No plugins loaded" in str(exc_info.value)

    def test_discovers_plugins(self, orchestrator, mock_registry):
        """Initialize should call discover_and_load."""
        orchestrator._fs_lock_manager = MagicMock()
        orchestrator._fs_lock_manager.validate_all_manifests.return_value = (True, [])
        orchestrator._fs_lock_manager.detect_conflicts.return_value = []

        orchestrator._initialize()

        mock_registry.discover_and_load.assert_called_once()

    def test_creates_stage_executor(self, orchestrator, mock_registry):
        """Initialize should create a StageExecutor."""
        orchestrator._fs_lock_manager = MagicMock()
        orchestrator._fs_lock_manager.validate_all_manifests.return_value = (True, [])
        orchestrator._fs_lock_manager.detect_conflicts.return_value = []

        orchestrator._initialize()

        assert orchestrator._stage_executor is not None

    def test_fs_lock_validation_failure(self, orchestrator, mock_registry):
        """FS Lock validation failure should raise CriticalError."""
        orchestrator._fs_lock_manager = MagicMock()
        orchestrator._fs_lock_manager.validate_all_manifests.return_value = (
            False, ["Path contains variable: {output_dir}"]
        )

        with pytest.raises(CriticalError) as exc_info:
            orchestrator._initialize()

        assert "FS Lock validation failed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestOrchestratorExecuteStages
# ---------------------------------------------------------------------------

class TestOrchestratorExecuteStages:

    def _setup_orchestrator(self, orchestrator, mock_registry, mock_state):
        orchestrator._run_id = "run_test_1"
        orchestrator._fs_lock_manager = MagicMock()
        orchestrator._fs_lock_manager.validate_all_manifests.return_value = (True, [])
        orchestrator._fs_lock_manager.detect_conflicts.return_value = []
        orchestrator._initialize()

    def test_all_stages_executed(self, orchestrator, mock_registry, mock_state):
        """All 3 stages (PARSE, DATA, OUTPUT) should be executed."""
        self._setup_orchestrator(orchestrator, mock_registry, mock_state)

        mock_executor = MagicMock()
        orchestrator._stage_executor = mock_executor

        orchestrator._execute_stages()

        assert mock_executor.execute_stage.call_count == 3
        assert orchestrator._stages_completed == ["parse", "data", "output"]
        assert orchestrator._stages_failed == []

    def test_stage_error_continues(self, orchestrator, mock_registry, mock_state):
        """StageError in one stage should not stop other stages."""
        self._setup_orchestrator(orchestrator, mock_registry, mock_state)

        mock_executor = MagicMock()
        # DATA stage fails, others succeed
        def execute_side_effect(stage):
            if stage == Stage.DATA:
                raise StageError("API down", stage="data")
        mock_executor.execute_stage.side_effect = execute_side_effect
        orchestrator._stage_executor = mock_executor

        orchestrator._execute_stages()

        assert "parse" in orchestrator._stages_completed
        assert "data" in orchestrator._stages_failed
        assert "output" in orchestrator._stages_completed

    def test_unexpected_error_continues(self, orchestrator, mock_registry, mock_state):
        """Unexpected exception should also continue to next stage."""
        self._setup_orchestrator(orchestrator, mock_registry, mock_state)

        mock_executor = MagicMock()
        call_count = 0
        def execute_side_effect(stage):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("unexpected")
        mock_executor.execute_stage.side_effect = execute_side_effect
        orchestrator._stage_executor = mock_executor

        orchestrator._execute_stages()

        # First stage failed, other 2 should have been attempted
        assert len(orchestrator._stages_failed) == 1
        assert mock_executor.execute_stage.call_count == 3

    def test_stage_events_emitted(self, orchestrator, mock_registry, mock_state, event_bus):
        """Stage start/complete events should be emitted."""
        self._setup_orchestrator(orchestrator, mock_registry, mock_state)

        events = []
        event_bus.subscribe(Events.STAGE_STARTED, lambda e: events.append("start"))
        event_bus.subscribe(Events.STAGE_COMPLETED, lambda e: events.append("complete"))

        mock_executor = MagicMock()
        orchestrator._stage_executor = mock_executor

        orchestrator._execute_stages()

        assert events.count("start") == 3
        assert events.count("complete") == 3


# ---------------------------------------------------------------------------
# TestOrchestratorFinalize
# ---------------------------------------------------------------------------

class TestOrchestratorFinalize:

    def test_finalize_completes_run(self, orchestrator, mock_state):
        orchestrator._run_id = "run_test_1"
        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        orchestrator._finalize(success=True)

        mock_state.complete_run.assert_called_once()

    def test_finalize_emits_run_completed(self, orchestrator, event_bus):
        events = []
        event_bus.subscribe(Events.RUN_COMPLETED, lambda e: events.append(e))

        orchestrator._run_id = "run_test_1"
        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        orchestrator._finalize(success=True)

        assert len(events) == 1

    def test_finalize_called_on_critical_error(self, orchestrator, mock_state, mock_registry):
        """Finalize should be called even when CriticalError occurs."""
        mock_registry.total_loaded = 0

        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        result = orchestrator.run()

        assert result.success is False
        # complete_run should still be called (via finalize)
        mock_state.complete_run.assert_called()


# ---------------------------------------------------------------------------
# TestOrchestratorErrorHandling
# ---------------------------------------------------------------------------

class TestOrchestratorErrorHandling:

    def test_critical_error_returns_failed_result(self, orchestrator, mock_registry):
        """CriticalError should return RunResult with success=False."""
        mock_registry.total_loaded = 0

        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        result = orchestrator.run()

        assert result.success is False
        assert result.error is not None

    def test_error_emits_run_error_event(self, orchestrator, event_bus, mock_registry):
        """Errors should emit RUN_ERROR event."""
        events = []
        event_bus.subscribe(Events.RUN_ERROR, lambda e: events.append(e))

        mock_registry.total_loaded = 0

        orchestrator._state_dumper = MagicMock()
        orchestrator._state_dumper.dump.return_value = None

        orchestrator.run()

        assert len(events) >= 1


# ---------------------------------------------------------------------------
# TestOrchestratorHelpers
# ---------------------------------------------------------------------------

class TestOrchestratorHelpers:

    def test_summarize_config_excludes_secrets(self, orchestrator, mock_registry):
        orchestrator._config = {
            "options": {"debug": True},
            "api_keys": {"tmdb": "secret123"},
        }
        summary = orchestrator._summarize_config()

        assert "options" in summary
        assert "enabled_plugins" in summary
        assert "api_keys" not in summary

    def test_emit_error(self, orchestrator, event_bus):
        events = []
        event_bus.subscribe(Events.RUN_ERROR, lambda e: events.append(e))

        orchestrator._run_id = "run_test_1"
        orchestrator._emit_error(ValueError("test"), critical=True)

        assert len(events) == 1

    def test_stages_constant(self):
        """Orchestrator should define exactly 3 stages."""
        assert Orchestrator.STAGES == [Stage.PARSE, Stage.DATA, Stage.OUTPUT]


# ---------------------------------------------------------------------------
# TestBuildOrchestratorFactory
# ---------------------------------------------------------------------------

class TestBuildOrchestratorFactory:

    def test_raises_without_mongodb(self):
        """Factory should raise if MongoDB is not available."""
        config = {"options": {"debug": False}}

        with patch("archiverr.infrastructure.database.DatabaseConnection") as mock_db:
            mock_db.from_env.return_value.connect.return_value = None

            with pytest.raises(ImportError):
                build_orchestrator(config)

    def test_creates_orchestrator_with_persistence(self):
        """Factory should return Orchestrator when all deps available."""
        config = {"options": {"debug": False}}

        with patch("archiverr.infrastructure.database.DatabaseConnection") as mock_db:
            with patch("archiverr.state.GlobalStateManager") as mock_gsm:
                mock_persistence = MagicMock()
                mock_db.from_env.return_value.connect.return_value = mock_persistence

                mock_state_instance = MagicMock()
                mock_gsm.return_value = mock_state_instance

                result = build_orchestrator(config)

                assert isinstance(result, Orchestrator)
                mock_state_instance.reset.assert_called_once()
                mock_state_instance.configure.assert_called_once()
