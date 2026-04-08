"""
Plugin-Agnostic Core Tests

These tests verify core functionality WITHOUT depending on specific plugin names.
Use mock_input_plugin, mock_output_plugin fixtures instead of real plugins.

This pattern ensures:
1. Core tests don't break when plugins change
2. Tests run fast (no real plugin execution)
3. Plugin-agnostic architecture is maintained
"""

import re
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from archiverr.state import GlobalStateManager


# ============================================================================
# Static Analysis Guard - scans core source files for hardcoded plugin names
# ============================================================================

KNOWN_PLUGIN_NAMES = {
    'scanner', 'file-reader', 'file-input', 'renamer',
    'tmdb', 'tvdb', 'tvmaze', 'omdb', 'ffprobe', 'tasker', 'rclone',
}

# Pattern: dict literal mapping a known plugin name string to another string
# e.g. 'scanner': 'input' or "tmdb": "data"
HARDCODED_MAP_PATTERN = re.compile(
    r"""['"](%s)['"]\s*:\s*['"]""" % '|'.join(re.escape(n) for n in KNOWN_PLUGIN_NAMES)
)

CORE_DIR = Path(__file__).resolve().parents[3] / "src" / "archiverr" / "core"


class TestCorePluginAgnosticGuard:
    """Static analysis: ensure core source files don't contain hardcoded plugin names."""

    def _get_core_python_files(self) -> list[Path]:
        return sorted(CORE_DIR.rglob("*.py"))

    def test_no_hardcoded_plugin_name_maps_in_core(self):
        """Core must not contain dict mappings from known plugin names to values."""
        violations = []
        for path in self._get_core_python_files():
            rel = path.relative_to(CORE_DIR)
            in_docstring = False
            for i, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.lstrip()
                # Track triple-quoted docstrings
                if '"""' in stripped or "'''" in stripped:
                    count = stripped.count('"""') + stripped.count("'''")
                    if count == 1:
                        in_docstring = not in_docstring
                    continue
                if in_docstring or stripped.startswith('#'):
                    continue
                match = HARDCODED_MAP_PATTERN.search(line)
                if match:
                    violations.append(f"  {rel}:{i} -> {match.group(0)!r}")

        assert not violations, (
            "Hardcoded plugin name mappings found in core:\n"
            + "\n".join(violations)
            + "\n\nPlugins must declare stage/provides in their manifest.yml."
        )

    def test_manifest_normalizer_has_no_plugin_stage_map(self):
        """manifest_normalizer.py must not define PLUGIN_STAGE_MAP."""
        normalizer = CORE_DIR / "plugins" / "manifest_normalizer.py"
        content = normalizer.read_text()
        assert "PLUGIN_STAGE_MAP" not in content, (
            "PLUGIN_STAGE_MAP still exists in manifest_normalizer.py. "
            "Stage inference must be generic (category-based or explicit)."
        )


# ============================================================================
# Legacy test suite (skipped if old API removed)
# ============================================================================

_LEGACY_SKIP = not hasattr(GlobalStateManager, "start_execution")
_legacy_skip = pytest.mark.skipif(_LEGACY_SKIP, reason="Legacy GlobalStateManager execution API removed")


@_legacy_skip
class TestPluginAgnosticExecution:
    """Test execution flow without real plugins."""
    
    def test_state_manager_with_mock_plugin(self, mock_input_plugin, mock_output_plugin):
        """Test GlobalStateManager works with generic plugin data."""
        from archiverr.state import GlobalStateManager, PluginResult
        
        state = GlobalStateManager()
        state.reset()
        
        # Start execution
        config = {
            "options": {"debug": False},
            "plugins": {
                mock_input_plugin["name"]: {"enabled": True},
                mock_output_plugin["name"]: {"enabled": True}
            }
        }
        
        exec_id = state.start_execution(config)
        assert exec_id is not None
        
        # Register match
        match = state.register_match(0, "/path/test.mkv")
        assert match.index == 0
        
        # Update with mock plugin results (generic names)
        from datetime import datetime
        now = datetime.now()
        
        # Session 11: PluginResult without plugin_name and duration_ms in constructor
        input_result = PluginResult(
            success=True,
            started_at=now,
            finished_at=now,
            data={"matches": ["/path/test.mkv"]}
        )
        state.update_plugin_result(0, mock_input_plugin["name"], input_result)
        
        output_result = PluginResult(
            success=True,
            started_at=now,
            finished_at=now,
            data={"processed": True}
        )
        state.update_plugin_result(0, mock_output_plugin["name"], output_result)
        
        # Complete
        state.complete_match(0)
        run_state = state.complete_execution()
        
        # Session 11: Use run.status.total_jobs instead of execution.total_matches
        assert run_state.status.total_jobs == 1
        assert run_state.status.completed == 1
    
    def test_plugin_result_generic_structure(self, mock_output_plugin):
        """Test PluginResult works with any plugin data."""
        from archiverr.state import PluginResult
        from datetime import datetime, timedelta
        
        start = datetime.now()
        finish = start + timedelta(milliseconds=100)
        
        # Session 11: PluginResult without plugin_name, duration_ms is computed
        result = PluginResult(
            success=True,
            started_at=start,
            finished_at=finish,
            data=mock_output_plugin["execute_result"]["data"]
        )
        
        assert result.success is True
        assert result.duration_ms >= 100  # Computed property
        assert "title" in result.data
    
    def test_match_state_plugins_are_generic(self, mock_match_data):
        """Test JobState plugins dict is plugin-agnostic."""
        # Session 11: Use JobState from archiverr.state (not MatchState from models)
        from archiverr.state import JobState, InputData
        
        job = JobState(
            index=mock_match_data["index"],
            run_id="test-123",
            input=InputData(value=mock_match_data["input_path"])
        )
        
        # Add plugins using generic names from fixture
        for plugin_name, plugin_data in mock_match_data["plugins"].items():
            job.plugins[plugin_name] = plugin_data
        
        # Verify generically
        assert len(job.plugins) == 2
        for plugin_name in mock_match_data["plugins"]:
            assert plugin_name in job.plugins


@_legacy_skip
class TestPluginAgnosticConfiguration:
    """Test configuration without hardcoded plugin names."""
    
    def test_config_with_mock_plugins(self, mock_plugin_config):
        """Test config structure is plugin-agnostic."""
        assert "options" in mock_plugin_config
        assert "plugins" in mock_plugin_config
        
        # Don't assert specific plugin names exist
        # Instead verify the structure
        for plugin_name, plugin_conf in mock_plugin_config["plugins"].items():
            assert "enabled" in plugin_conf
    
    def test_config_plugins_are_dictionaries(self, mock_plugin_config):
        """Test all plugin configs are valid dictionaries."""
        for plugin_name, plugin_conf in mock_plugin_config["plugins"].items():
            assert isinstance(plugin_conf, dict)
            assert isinstance(plugin_name, str)


@_legacy_skip
class TestPluginAgnosticMetadata:
    """Test plugin metadata handling without specific plugins."""
    
    def test_metadata_has_required_fields(self, mock_plugin_metadata):
        """Test plugin metadata structure."""
        for category, metadata in mock_plugin_metadata.items():
            assert "name" in metadata
            assert "version" in metadata
            assert "category" in metadata
            assert "class_name" in metadata
            assert "depends_on" in metadata
            assert "expects" in metadata
    
    def test_input_plugin_has_no_dependencies(self, mock_plugin_metadata):
        """Test input plugins typically have no dependencies."""
        input_meta = mock_plugin_metadata["input"]
        assert input_meta["category"] == "input"
        assert input_meta["depends_on"] == []
    
    def test_output_plugin_depends_on_input(self, mock_plugin_metadata):
        """Test output plugins depend on input plugins."""
        output_meta = mock_plugin_metadata["output"]
        assert output_meta["category"] == "output"
        assert len(output_meta["depends_on"]) > 0


@_legacy_skip
class TestPluginAgnosticDiscovery:
    """Test plugin discovery with mock data."""
    
    def test_dependency_resolver_with_mock_plugins(self, mock_plugin_metadata):
        """Test DependencyResolver works with any plugin structure."""
        from archiverr.core.plugins.resolver import DependencyResolver
        
        # Build plugins dict from mock metadata
        plugins = {
            mock_plugin_metadata["input"]["name"]: mock_plugin_metadata["input"],
            mock_plugin_metadata["output"]["name"]: mock_plugin_metadata["output"]
        }
        
        resolver = DependencyResolver(plugins)
        enabled = list(plugins.keys())
        groups = resolver.resolve(enabled)
        
        # Generic assertions: groups are lists, dependencies respected
        assert isinstance(groups, list)
        assert len(groups) > 0
        
        # Input should come before output (no specific plugin name check)
        input_name = mock_plugin_metadata["input"]["name"]
        output_name = mock_plugin_metadata["output"]["name"]
        
        input_index = None
        output_index = None
        
        for i, group in enumerate(groups):
            if input_name in group:
                input_index = i
            if output_name in group:
                output_index = i
        
        assert input_index is not None, "Input plugin not found in groups"
        assert output_index is not None, "Output plugin not found in groups"
        assert input_index <= output_index, "Input should execute before output"


@_legacy_skip
class TestNoHardcodedPluginNames:
    """Verify tests don't use hardcoded plugin names."""
    
    FORBIDDEN_PLUGIN_NAMES = ["scanner", "renamer", "tmdb", "tvdb", "omdb", "ffprobe", "tvmaze"]
    
    def test_mock_input_has_generic_name(self, mock_input_plugin):
        """Test mock_input_plugin doesn't use real plugin name."""
        assert mock_input_plugin["name"] not in self.FORBIDDEN_PLUGIN_NAMES
    
    def test_mock_output_has_generic_name(self, mock_output_plugin):
        """Test mock_output_plugin doesn't use real plugin name."""
        assert mock_output_plugin["name"] not in self.FORBIDDEN_PLUGIN_NAMES
    
    def test_mock_match_data_uses_generic_names(self, mock_match_data):
        """Test mock_match_data doesn't use real plugin names."""
        for plugin_name in mock_match_data["plugins"]:
            assert plugin_name not in self.FORBIDDEN_PLUGIN_NAMES
