"""
Unit tests for core/orchestrator.py

Session 11 - Phase 4: Orchestrator tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from archiverr.core.orchestrator import Orchestrator, RunResult, build_orchestrator
from archiverr.core.plugins.registry import Stage
from archiverr.core.exceptions import CriticalError, StageError


class TestRunResult:
    """Test RunResult dataclass"""
    
    def test_basic_creation(self):
        result = RunResult(
            run_id="run_abc123",
            success=True,
            total_jobs=10,
            completed=10,
            failed=0,
            skipped=0,
            duration_ms=5000
        )
        assert result.run_id == "run_abc123"
        assert result.success is True
        assert result.total_jobs == 10
    
    def test_to_dict(self):
        result = RunResult(
            run_id="run_test",
            success=False,
            total_jobs=5,
            completed=3,
            failed=2,
            skipped=0,
            duration_ms=1000,
            error="Something failed"
        )
        d = result.to_dict()
        
        assert d["run_id"] == "run_test"
        assert d["success"] is False
        assert d["total_jobs"] == 5
        assert d["failed"] == 2
        assert d["error"] == "Something failed"
    
    def test_stages_lists(self):
        result = RunResult(
            run_id="run_test",
            success=True,
            total_jobs=0,
            completed=0,
            failed=0,
            skipped=0,
            duration_ms=0,
            stages_completed=["input", "parse"],
            stages_failed=["data"]
        )
        assert "input" in result.stages_completed
        assert "data" in result.stages_failed


class TestOrchestrator:
    """Test Orchestrator class"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for Orchestrator"""
        event_bus = Mock()
        event_bus.emit = Mock()
        event_bus.subscribe = Mock()
        
        state = Mock()
        state._execution = Mock()
        state._execution.total_matches = 10
        state._execution.completed_matches = 10
        state._execution.failed_matches = 0
        state.start_execution = Mock(return_value="run_test123")
        state.complete_execution = Mock()
        
        persistence = Mock()
        persistence.save_plugin = Mock()
        
        registry = Mock()
        registry.total_discovered = 5
        registry.total_loaded = 3
        registry.enabled_plugins = ["scanner", "renamer", "tmdb"]
        registry.discover_and_load = Mock()
        registry.validate_dependencies = Mock(return_value=[])
        registry.get_plugins_by_stage = Mock(return_value={})
        
        debugger = Mock()
        debugger.info = Mock()
        debugger.debug = Mock()
        debugger.warn = Mock()
        debugger.error = Mock()
        
        config = {"options": {"debug": True, "dry_run": True}}
        
        return {
            "event_bus": event_bus,
            "state": state,
            "persistence": persistence,
            "plugin_registry": registry,
            "config": config,
            "debugger": debugger
        }
    
    @pytest.fixture
    def orchestrator(self, mock_dependencies):
        return Orchestrator(**mock_dependencies)
    
    def test_creation(self, orchestrator):
        """Test orchestrator instantiation"""
        assert orchestrator._run_id is None
        assert orchestrator._start_time is None
    
    def test_run_success(self, orchestrator, mock_dependencies):
        """Test successful run"""
        result = orchestrator.run()
        
        assert result.success is True
        assert result.run_id == "run_test123"
        
        # Verify state lifecycle
        mock_dependencies["state"].start_execution.assert_called_once()
        mock_dependencies["state"].complete_execution.assert_called_once()
    
    def test_run_emits_events(self, orchestrator, mock_dependencies):
        """Test that run emits expected events"""
        orchestrator.run()
        
        event_bus = mock_dependencies["event_bus"]
        
        # Check run.started was emitted
        run_started_calls = [
            call for call in event_bus.emit.call_args_list
            if call[0][0] == "run.started"
        ]
        assert len(run_started_calls) == 1
        
        # Check run.completed was emitted
        run_completed_calls = [
            call for call in event_bus.emit.call_args_list
            if call[0][0] == "run.completed"
        ]
        assert len(run_completed_calls) == 1
    
    def test_run_emits_stage_events(self, orchestrator, mock_dependencies):
        """Test that stages emit started/completed events"""
        orchestrator.run()
        
        event_bus = mock_dependencies["event_bus"]
        
        # Check stage events for all 4 stages
        stage_started_calls = [
            call for call in event_bus.emit.call_args_list
            if call[0][0] == "stage.started"
        ]
        stage_completed_calls = [
            call for call in event_bus.emit.call_args_list
            if call[0][0] == "stage.completed"
        ]
        
        assert len(stage_started_calls) == 4  # input, parse, data, output
        assert len(stage_completed_calls) == 4
    
    def test_critical_error_stops_run(self, mock_dependencies):
        """Test that CriticalError stops the run"""
        mock_dependencies["plugin_registry"].total_loaded = 0
        mock_dependencies["plugin_registry"].total_discovered = 5
        
        orchestrator = Orchestrator(**mock_dependencies)
        result = orchestrator.run()
        
        assert result.success is False
        assert "No plugins loaded" in result.error
    
    def test_stage_error_continues(self, orchestrator, mock_dependencies):
        """Test that StageError allows run to continue"""
        def raise_stage_error(stage):
            if stage == Stage.PARSE:
                raise StageError("Parse stage failed", stage="parse")
            return {}
        
        mock_dependencies["plugin_registry"].get_plugins_by_stage = Mock(
            side_effect=raise_stage_error
        )
        
        result = orchestrator.run()
        
        # Run should complete (with partial success)
        assert mock_dependencies["state"].complete_execution.called
        assert "parse" in result.stages_failed
    
    def test_registers_event_handlers(self, orchestrator, mock_dependencies):
        """Test that event handlers are registered"""
        orchestrator.run()
        
        event_bus = mock_dependencies["event_bus"]
        subscribe_calls = event_bus.subscribe.call_args_list
        
        events_subscribed = [call[0][0] for call in subscribe_calls]
        assert "job.completed" in events_subscribed
        assert "plugin.completed" in events_subscribed
    
    def test_run_result_duration(self, orchestrator):
        """Test that duration_ms is calculated"""
        result = orchestrator.run()
        
        # Should have some positive duration
        assert result.duration_ms >= 0
    
    def test_stages_order(self, orchestrator):
        """Test that stages are in correct order"""
        assert orchestrator.STAGES == [
            Stage.INPUT,
            Stage.PARSE,
            Stage.DATA,
            Stage.OUTPUT
        ]


class TestPluginRegistryIntegration:
    """Test Orchestrator with PluginRegistry"""
    
    @pytest.fixture
    def full_mock_setup(self):
        """More realistic mock setup"""
        from archiverr.core.plugins.registry import PluginRegistry
        
        event_bus = Mock()
        event_bus.emit = Mock()
        event_bus.subscribe = Mock()
        
        state = Mock()
        state._execution = Mock()
        state._execution.total_matches = 0
        state._execution.completed_matches = 0
        state._execution.failed_matches = 0
        state.start_execution = Mock(return_value="run_int_test")
        state.complete_execution = Mock()
        
        persistence = Mock()
        
        # Create a mock registry that returns real Stage enums
        registry = Mock(spec=PluginRegistry)
        registry.total_discovered = 2
        registry.total_loaded = 2
        registry.enabled_plugins = ["scanner", "renamer"]
        registry.discover_and_load = Mock()
        registry.validate_dependencies = Mock(return_value=[])
        
        # Return empty dict for each stage
        def get_stage_plugins(stage):
            if stage == Stage.INPUT:
                return {"scanner": Mock()}
            return {}
        
        registry.get_plugins_by_stage = Mock(side_effect=get_stage_plugins)
        
        debugger = Mock()
        debugger.info = Mock()
        debugger.debug = Mock()
        debugger.warn = Mock()
        debugger.error = Mock()
        
        return {
            "event_bus": event_bus,
            "state": state,
            "persistence": persistence,
            "plugin_registry": registry,
            "config": {},
            "debugger": debugger
        }
    
    def test_input_stage_has_plugins(self, full_mock_setup):
        """Test input stage plugin execution"""
        orchestrator = Orchestrator(**full_mock_setup)
        result = orchestrator.run()
        
        registry = full_mock_setup["plugin_registry"]
        
        # Should have called get_plugins_by_stage for each stage
        get_calls = registry.get_plugins_by_stage.call_args_list
        stages_called = [call[0][0] for call in get_calls]
        
        assert Stage.INPUT in stages_called
        assert Stage.PARSE in stages_called
        assert Stage.DATA in stages_called
        assert Stage.OUTPUT in stages_called


class TestBuildOrchestrator:
    """Test build_orchestrator factory function"""
    
    @patch('archiverr.utils.debug.init_debugger')
    @patch('archiverr.state.GlobalStateManager')
    @patch('archiverr.infrastructure.database.DatabaseConnection')
    def test_creates_orchestrator(
        self,
        mock_db_class,
        mock_state_class,
        mock_debugger_fn
    ):
        """Test factory creates orchestrator with dependencies"""
        # Setup mocks
        mock_debugger = Mock()
        mock_debugger.info = Mock()
        mock_debugger.debug = Mock()
        mock_debugger.warn = Mock()
        mock_debugger.error = Mock()
        mock_debugger_fn.return_value = mock_debugger
        
        mock_state = Mock()
        mock_state_class.return_value = mock_state
        
        mock_db = Mock()
        mock_persistence = Mock()
        mock_db.connect.return_value = mock_persistence
        mock_db_class.from_env.return_value = mock_db
        
        config = {"options": {"debug": True}}
        
        # Create orchestrator
        with patch('archiverr.core.orchestrator.PluginRegistry') as mock_registry_class:
            mock_registry = Mock()
            mock_registry_class.return_value = mock_registry
            
            orchestrator = build_orchestrator(config)
        
        # Verify
        assert orchestrator is not None
        assert orchestrator._config == config
        
        # Verify state was configured
        mock_state.configure.assert_called_once()
    
    def test_uses_provided_dependencies(self):
        """Test factory uses provided dependencies when given"""
        # Setup provided dependencies
        provided_debugger = Mock()
        provided_debugger.info = Mock()
        provided_debugger.debug = Mock()
        provided_debugger.warn = Mock()
        provided_debugger.error = Mock()
        
        provided_event_bus = Mock()
        provided_event_bus.emit = Mock()
        provided_event_bus.subscribe = Mock()
        
        provided_persistence = Mock()
        
        config = {}
        
        with patch('archiverr.state.GlobalStateManager') as mock_state_class:
            mock_state = Mock()
            mock_state_class.return_value = mock_state
            
            with patch('archiverr.core.orchestrator.PluginRegistry') as mock_registry_class:
                mock_registry = Mock()
                mock_registry_class.return_value = mock_registry
                
                # Create orchestrator with provided deps
                orchestrator = build_orchestrator(
                    config,
                    debugger=provided_debugger,
                    persistence=provided_persistence,
                    event_bus=provided_event_bus
                )
        
        # Should use provided
        assert orchestrator._debugger == provided_debugger
        assert orchestrator._event_bus == provided_event_bus
        assert orchestrator._persistence == provided_persistence
