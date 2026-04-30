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

# Pattern: equality conditional against a known plugin name string.
# e.g. ``if name == "tmdb":`` or ``"tmdb" == plugin_name`` (S37 audit
# extension — the dict-mapping guard alone missed if-ladder sneak-ins).
_PLUGIN_NAME_ALT = '|'.join(re.escape(n) for n in KNOWN_PLUGIN_NAMES)
HARDCODED_EQUALITY_PATTERN = re.compile(
    rf"""(?:==|!=)\s*['"]({_PLUGIN_NAME_ALT})['"]|['"]({_PLUGIN_NAME_ALT})['"]\s*(?:==|!=)"""
)

# Pattern: ``in (...)`` / ``in [...]`` / ``in {...}`` membership test against
# a literal containing a known plugin name string. Catches set/list/tuple
# literals like ``if name in ("tmdb", "tvdb"):`` (S37 audit extension).
HARDCODED_MEMBERSHIP_PATTERN = re.compile(
    rf"""\bin\s*[\(\[\{{][^\)\]\}}\n]*['"]({_PLUGIN_NAME_ALT})['"]"""
)

CORE_DIR = Path(__file__).resolve().parents[3] / "src" / "archiverr" / "core"


class TestCorePluginAgnosticGuard:
    """Static analysis: ensure core source files don't contain hardcoded plugin names."""

    def _get_core_python_files(self) -> list[Path]:
        return sorted(CORE_DIR.rglob("*.py"))

    def _scan_core_for_pattern(self, pattern: re.Pattern) -> list[str]:
        """Scan core/ files for a regex pattern, skipping docstrings & comments.

        Returns a list of formatted ``rel:line -> match`` strings. Used by all
        three guard tests below so the docstring-tracking loop stays in one
        place (S37 audit extension).
        """
        violations = []
        for path in self._get_core_python_files():
            rel = path.relative_to(CORE_DIR)
            in_docstring = False
            for i, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.lstrip()
                # Track triple-quoted docstrings (single-line docstrings via
                # paired """ on the same line do NOT toggle state).
                if '"""' in stripped or "'''" in stripped:
                    count = stripped.count('"""') + stripped.count("'''")
                    if count == 1:
                        in_docstring = not in_docstring
                    continue
                if in_docstring or stripped.startswith('#'):
                    continue
                match = pattern.search(line)
                if match:
                    violations.append(f"  {rel}:{i} -> {match.group(0)!r}")
        return violations

    def test_no_hardcoded_plugin_name_maps_in_core(self):
        """Core must not contain dict mappings from known plugin names to values."""
        violations = self._scan_core_for_pattern(HARDCODED_MAP_PATTERN)
        assert not violations, (
            "Hardcoded plugin name dict-mappings found in core:\n"
            + "\n".join(violations)
            + "\n\nPlugins must declare stage/provides in their manifest.yml."
        )

    def test_no_hardcoded_plugin_name_equality_in_core(self):
        """Core must not branch on equality against a hardcoded plugin name.

        Catches ``if name == "tmdb":`` / ``plugin == 'tasker'`` style sneaks
        that the dict-mapping pattern alone missed (S37 audit extension).
        """
        violations = self._scan_core_for_pattern(HARDCODED_EQUALITY_PATTERN)
        assert not violations, (
            "Hardcoded plugin-name equality conditionals found in core:\n"
            + "\n".join(violations)
            + "\n\nDispatch generically via manifest stage/provides; do not "
              "branch on plugin name string."
        )

    def test_no_hardcoded_plugin_name_membership_in_core(self):
        """Core must not test membership in a literal list/tuple/set of plugin names.

        Catches ``if name in ('tmdb', 'tvdb'):`` style sneaks (S37 audit
        extension). KNOWN_PLUGIN_NAMES set inside the test module itself is
        fine — the scanner skips test files (only ``CORE_DIR`` is walked).
        """
        violations = self._scan_core_for_pattern(HARDCODED_MEMBERSHIP_PATTERN)
        assert not violations, (
            "Hardcoded plugin-name membership literals found in core:\n"
            + "\n".join(violations)
            + "\n\nResolve dispatch by manifest stage/provides, not by name set."
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
# Plugin-agnostic runtime guard test suite (rewired to canonical API in S36)
# ============================================================================


class TestPluginAgnosticExecution:
    """Test execution flow without real plugins (canonical API)."""

    def test_state_manager_with_mock_plugin(self, mock_input_plugin, mock_output_plugin):
        """GlobalStateManager works with generic plugin data via canonical update_plugin path."""
        from archiverr.state import GlobalStateManager

        state = GlobalStateManager()
        state.reset()

        # Start run with generic plugin config
        config = {
            "options": {"debug": False},
            "plugins": {
                mock_input_plugin["name"]: {"enabled": True},
                mock_output_plugin["name"]: {"enabled": True}
            }
        }
        run_id = state.start_run(config)
        assert run_id is not None

        # Create job (replaces legacy register_match)
        state.create_job("/path/test.mkv")
        job = state.get_job(0)
        assert job.index == 0

        # Write generic plugin data via canonical writer
        # (services.update_plugin -> GlobalStateManager.update_plugin -> _update_job_plugin -> save_plugin)
        state.update_plugin(job.id, mock_input_plugin["name"], {"matches": ["/path/test.mkv"]})
        state.update_plugin(job.id, mock_output_plugin["name"], {"processed": True})

        # Complete
        state.complete_job(0)
        run_state = state.complete_run()

        assert run_state.status.total_jobs == 1
        assert run_state.status.completed == 1

    def test_plugin_result_generic_structure(self, mock_output_plugin):
        """PluginResult works with any plugin data (no plugin name coupling)."""
        from archiverr.state import PluginResult
        from datetime import datetime, timedelta

        start = datetime.now()
        finish = start + timedelta(milliseconds=100)

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
        """JobState.plugins dict is plugin-agnostic (string keys)."""
        from archiverr.state import JobState, InputData

        job = JobState(
            index=mock_match_data["index"],
            run_id="test-123",
            input=InputData(value=mock_match_data["input_path"])
        )

        for plugin_name, plugin_data in mock_match_data["plugins"].items():
            job.plugins[plugin_name] = plugin_data

        assert len(job.plugins) == 2
        for plugin_name in mock_match_data["plugins"]:
            assert plugin_name in job.plugins


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
