"""
Unit tests for stage_executor.py

Session 11 - Phase 5: StageExecutor tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Dict, Any

from archiverr.core.plugins.stage_executor import (
    StageExecutor,
    ExecutionMode,
    STAGE_MODES,
    PluginExecutionResult,
)
from archiverr.core.plugins.registry import Stage


@dataclass
class MockJobStatus:
    success: bool = True
    executed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)


@dataclass
class MockInputData:
    value: str = "/path/to/file.mkv"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockJobState:
    id: str = "job_test_0"
    run_id: str = "run_test"
    index: int = 0
    input: MockInputData = field(default_factory=MockInputData)
    status: MockJobStatus = field(default_factory=MockJobStatus)
    
    def add_executed(self, plugin_name: str):
        self.status.executed.append(plugin_name)
    
    def add_failed(self, plugin_name: str):
        self.status.failed.append(plugin_name)
        self.status.success = False
    
    def add_skipped(self, plugin_name: str):
        self.status.skipped.append(plugin_name)


class TestExecutionMode:
    """Test ExecutionMode enum"""
    
    def test_per_run_value(self):
        assert ExecutionMode.PER_RUN.value == "per_run"
    
    def test_per_job_value(self):
        assert ExecutionMode.PER_JOB.value == "per_job"


class TestStageModes:
    """Test STAGE_MODES mapping"""
    
    def test_input_is_per_run(self):
        assert STAGE_MODES[Stage.INPUT] == ExecutionMode.PER_RUN
    
    def test_parse_is_per_job(self):
        assert STAGE_MODES[Stage.PARSE] == ExecutionMode.PER_JOB
    
    def test_data_is_per_job(self):
        assert STAGE_MODES[Stage.DATA] == ExecutionMode.PER_JOB
    
    def test_output_is_per_job(self):
        assert STAGE_MODES[Stage.OUTPUT] == ExecutionMode.PER_JOB


class TestPluginExecutionResult:
    """Test PluginExecutionResult dataclass"""
    
    def test_success_result(self):
        result = PluginExecutionResult(
            plugin_name="tmdb",
            success=True,
            data={"movie": {"id": 123}}
        )
        assert result.success is True
        assert result.plugin_name == "tmdb"
        assert result.error is None
    
    def test_failed_result(self):
        result = PluginExecutionResult(
            plugin_name="tmdb",
            success=False,
            data={},
            error="API timeout"
        )
        assert result.success is False
        assert result.error == "API timeout"
    
    def test_skipped_result(self):
        result = PluginExecutionResult(
            plugin_name="tmdb",
            success=True,
            data={},
            skipped=True,
            skip_reason="Missing: job.plugins.renamer.parsed"
        )
        assert result.skipped is True
        assert "Missing" in result.skip_reason


class TestStageExecutor:
    """Test StageExecutor class"""
    
    @pytest.fixture
    def mock_state(self):
        state = Mock()
        state.get_all_jobs = Mock(return_value=[])
        return state
    
    @pytest.fixture
    def mock_registry(self):
        registry = Mock()
        registry.get_plugins_by_stage = Mock(return_value={})
        registry.get_manifest = Mock(return_value={})
        return registry
    
    @pytest.fixture
    def mock_event_bus(self):
        bus = Mock()
        bus.emit = Mock()
        return bus
    
    @pytest.fixture
    def mock_debugger(self):
        debugger = Mock()
        debugger.info = Mock()
        debugger.debug = Mock()
        debugger.warn = Mock()
        debugger.error = Mock()
        return debugger
    
    @pytest.fixture
    def executor(self, mock_state, mock_registry, mock_event_bus, mock_debugger):
        return StageExecutor(
            state=mock_state,
            plugin_registry=mock_registry,
            event_bus=mock_event_bus,
            config={"options": {"debug": True}},
            debugger=mock_debugger
        )
    
    def test_creation(self, executor):
        assert executor is not None
        assert executor._plugin_data_cache == {}
    
    def test_execute_stage_no_plugins(self, executor, mock_registry):
        mock_registry.get_plugins_by_stage.return_value = {}
        
        executor.execute_stage(Stage.INPUT)
        
        mock_registry.get_plugins_by_stage.assert_called_once_with(Stage.INPUT)
    
    def test_execute_input_stage_calls_per_run(self, executor, mock_registry):
        mock_plugin = Mock()
        mock_plugin.name = "scanner"
        mock_plugin.execute_run = Mock(return_value=Mock(data={}))
        
        mock_registry.get_plugins_by_stage.return_value = {"scanner": mock_plugin}
        
        executor.execute_stage(Stage.INPUT)
        
        mock_plugin.execute_run.assert_called_once()
    
    def test_execute_parse_stage_calls_per_job(self, executor, mock_registry, mock_state):
        mock_plugin = Mock()
        mock_plugin.name = "renamer"
        mock_plugin.execute = Mock(return_value=Mock(data={}, status=Mock(value="success")))
        
        mock_job = MockJobState()
        mock_state.get_all_jobs.return_value = [mock_job]
        mock_registry.get_plugins_by_stage.return_value = {"renamer": mock_plugin}
        mock_registry.get_manifest.return_value = {"requires": []}
        
        executor.execute_stage(Stage.PARSE)
        
        mock_plugin.execute.assert_called_once()
    
    def test_requires_not_satisfied_skips_plugin(self, executor, mock_registry, mock_state):
        mock_plugin = Mock()
        mock_plugin.name = "tmdb"
        
        mock_job = MockJobState()
        mock_state.get_all_jobs.return_value = [mock_job]
        mock_registry.get_plugins_by_stage.return_value = {"tmdb": mock_plugin}
        mock_registry.get_manifest.return_value = {
            "requires": ["job.plugins.renamer.parsed.movie"]
        }
        
        executor.execute_stage(Stage.DATA)
        
        # Plugin should not be called (requires not satisfied)
        mock_plugin.execute.assert_not_called()
        
        # Job should be marked as skipped
        assert "tmdb" in mock_job.status.skipped
    
    def test_plugin_data_cached(self, executor, mock_registry, mock_state):
        mock_plugin = Mock()
        mock_plugin.name = "renamer"
        mock_plugin.execute = Mock(return_value=Mock(
            data={"parsed": {"movie": {"name": "Test"}}},
            status=Mock(value="success")
        ))
        
        mock_job = MockJobState()
        mock_state.get_all_jobs.return_value = [mock_job]
        mock_registry.get_plugins_by_stage.return_value = {"renamer": mock_plugin}
        mock_registry.get_manifest.return_value = {"requires": []}
        
        executor.execute_stage(Stage.PARSE)
        
        # Check cache
        cache = executor.get_plugin_data_cache()
        assert mock_job.id in cache
        assert "renamer" in cache[mock_job.id]
    
    def test_plugin_failure_continues(self, executor, mock_registry, mock_state, mock_event_bus):
        mock_plugin1 = Mock()
        mock_plugin1.name = "renamer"
        mock_plugin1.execute = Mock(side_effect=Exception("Parse error"))
        
        mock_plugin2 = Mock()
        mock_plugin2.name = "ffprobe"
        mock_plugin2.execute = Mock(return_value=Mock(data={}, status=Mock(value="success")))
        
        mock_job = MockJobState()
        mock_state.get_all_jobs.return_value = [mock_job]
        mock_registry.get_plugins_by_stage.return_value = {
            "renamer": mock_plugin1,
            "ffprobe": mock_plugin2
        }
        mock_registry.get_manifest.return_value = {"requires": []}
        
        executor.execute_stage(Stage.PARSE)
        
        # Both plugins should be called despite first one failing
        mock_plugin1.execute.assert_called_once()
        mock_plugin2.execute.assert_called_once()
        
        # First plugin should be marked as failed
        assert "renamer" in mock_job.status.failed
    
    def test_event_emitted_on_success(self, executor, mock_registry, mock_state, mock_event_bus):
        mock_plugin = Mock()
        mock_plugin.name = "renamer"
        mock_plugin.execute = Mock(return_value=Mock(data={}, status=Mock(value="success")))
        
        mock_job = MockJobState()
        mock_state.get_all_jobs.return_value = [mock_job]
        mock_registry.get_plugins_by_stage.return_value = {"renamer": mock_plugin}
        mock_registry.get_manifest.return_value = {"requires": []}
        
        executor.execute_stage(Stage.PARSE)
        
        # Check plugin.completed event was emitted
        emit_calls = [c for c in mock_event_bus.emit.call_args_list if c[0][0] == "plugin.completed"]
        assert len(emit_calls) >= 1
    
    def test_event_emitted_on_failure(self, executor, mock_registry, mock_state, mock_event_bus):
        mock_plugin = Mock()
        mock_plugin.name = "renamer"
        mock_plugin.execute = Mock(side_effect=Exception("Error"))
        
        mock_job = MockJobState()
        mock_state.get_all_jobs.return_value = [mock_job]
        mock_registry.get_plugins_by_stage.return_value = {"renamer": mock_plugin}
        mock_registry.get_manifest.return_value = {"requires": []}
        
        executor.execute_stage(Stage.PARSE)
        
        # Check plugin.failed event was emitted
        emit_calls = [c for c in mock_event_bus.emit.call_args_list if c[0][0] == "plugin.failed"]
        assert len(emit_calls) >= 1


class TestStageExecutorMixedMode:
    """Test OUTPUT stage mixed mode execution"""
    
    @pytest.fixture
    def executor_deps(self):
        state = Mock()
        state.get_all_jobs = Mock(return_value=[MockJobState()])
        
        registry = Mock()
        registry.get_plugins_by_stage = Mock(return_value={})
        registry.get_manifest = Mock(return_value={"requires": []})
        
        event_bus = Mock()
        event_bus.emit = Mock()
        
        debugger = Mock()
        debugger.info = Mock()
        debugger.debug = Mock()
        debugger.warn = Mock()
        debugger.error = Mock()
        
        return state, registry, event_bus, debugger
    
    def test_mixed_mode_separates_plugins(self, executor_deps):
        state, registry, event_bus, debugger = executor_deps
        
        per_job_plugin = Mock()
        per_job_plugin.name = "tasker"
        per_job_plugin.execute = Mock(return_value=Mock(data={}, status=Mock(value="success")))
        
        per_run_plugin = Mock()
        per_run_plugin.name = "rclone"
        per_run_plugin.execute_run = Mock(return_value=Mock(data={}))
        
        def get_manifest(name):
            if name == "rclone":
                return {"execution_mode": "per_run", "requires": []}
            return {"execution_mode": "per_job", "requires": []}
        
        registry.get_plugins_by_stage.return_value = {
            "tasker": per_job_plugin,
            "rclone": per_run_plugin
        }
        registry.get_manifest = Mock(side_effect=get_manifest)
        
        executor = StageExecutor(
            state=state,
            plugin_registry=registry,
            event_bus=event_bus,
            config={},
            debugger=debugger
        )
        
        executor.execute_stage(Stage.OUTPUT)
        
        # Both plugins should be called with correct mode
        per_job_plugin.execute.assert_called()
        per_run_plugin.execute_run.assert_called()


class TestStageExecutorTopologicalSort:
    """Test plugin ordering by dependencies"""
    
    @pytest.fixture
    def executor_deps(self):
        state = Mock()
        registry = Mock()
        event_bus = Mock()
        debugger = Mock()
        return state, registry, event_bus, debugger
    
    def test_plugins_with_no_requires_first(self, executor_deps):
        state, registry, event_bus, debugger = executor_deps
        
        def get_manifest(name):
            if name == "tmdb":
                return {"requires": ["job.plugins.renamer.parsed"]}
            return {"requires": []}
        
        registry.get_manifest = Mock(side_effect=get_manifest)
        
        executor = StageExecutor(
            state=state,
            plugin_registry=registry,
            event_bus=event_bus,
            config={},
            debugger=debugger
        )
        
        plugin_a = Mock()
        plugin_a.name = "tmdb"
        
        plugin_b = Mock()
        plugin_b.name = "renamer"
        
        plugins = {"tmdb": plugin_a, "renamer": plugin_b}
        
        sorted_plugins = executor._topological_sort(plugins, Stage.DATA)
        
        # renamer (no requires) should come before tmdb
        names = [executor._get_plugin_name(p) for p in sorted_plugins]
        assert names.index("renamer") < names.index("tmdb")


class TestStageExecutorLegacySupport:
    """Test legacy plugin method support"""
    
    @pytest.fixture
    def executor(self):
        state = Mock()
        state.register_match = Mock()
        
        registry = Mock()
        registry.get_plugins_by_stage = Mock(return_value={})
        registry.get_manifest = Mock(return_value={})
        
        event_bus = Mock()
        event_bus.emit = Mock()
        
        debugger = Mock()
        debugger.info = Mock()
        debugger.debug = Mock()
        debugger.warn = Mock()
        debugger.error = Mock()
        
        return StageExecutor(
            state=state,
            plugin_registry=registry,
            event_bus=event_bus,
            config={},
            debugger=debugger
        )
    
    def test_get_matches_legacy_support(self, executor):
        """Test that get_matches() is supported for input plugins"""
        mock_plugin = Mock()
        mock_plugin.name = "scanner"
        mock_plugin.get_matches = Mock(return_value=[
            {"input": {"path": "/file1.mkv"}},
            {"input": {"path": "/file2.mkv"}}
        ])
        # No execute_run method
        del mock_plugin.execute_run
        
        executor._registry.get_plugins_by_stage.return_value = {"scanner": mock_plugin}
        
        executor.execute_stage(Stage.INPUT)
        
        mock_plugin.get_matches.assert_called_once()
    
    def test_process_legacy_support(self, executor):
        """Test that process() is supported for output plugins"""
        mock_plugin = Mock()
        mock_plugin.name = "renamer"
        mock_plugin.process = Mock(return_value={"parsed": {"movie": {}}})
        # No execute method
        if hasattr(mock_plugin, 'execute'):
            del mock_plugin.execute
        
        mock_job = MockJobState()
        executor._state.get_all_jobs = Mock(return_value=[mock_job])
        executor._registry.get_plugins_by_stage.return_value = {"renamer": mock_plugin}
        executor._registry.get_manifest.return_value = {"requires": []}
        
        executor.execute_stage(Stage.PARSE)
        
        mock_plugin.process.assert_called_once()
