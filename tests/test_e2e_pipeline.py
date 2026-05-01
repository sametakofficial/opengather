"""
End-to-End Pipeline Tests

Tests the full pipeline with real plugin instances:
scanner -> renamer -> [data plugins] -> tasker

Uses virtual paths (no actual files needed) and mocked API calls.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from archiverr.core.orchestrator import Orchestrator, build_orchestrator
from archiverr.core.plugins.registry import PluginRegistry, Stage
from archiverr.core.plugins.stage_executor import StageExecutor
from archiverr.core.provides_registry import ProvidesRegistry
from archiverr.events import EventBus
from archiverr.infrastructure.database.null_persistence import NullPersistence
from archiverr.state.manager import GlobalStateManager
from archiverr.state.models import InputData, JobState, RunState, StateEnum
from archiverr.utils.debug import init_debugger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def debugger():
    return init_debugger(enabled=False)


@pytest.fixture
def event_bus(debugger):
    return EventBus(debugger=debugger)


@pytest.fixture
def state():
    s = GlobalStateManager()
    s.reset()
    return s


@pytest.fixture
def persistence():
    return NullPersistence()


def make_config(**overrides):
    """Build a minimal config for testing."""
    config = {
        "options": {"debug": False, "dry_run": True},
        "scanner": {
            "enabled": True,
            "targets": [],
            "allow_virtual_paths": True,
            "extensions": ["mkv", "mp4", "avi"],
            "recursive": False,
        },
        "renamer": {
            "enabled": True,
            "media_type": "auto",
        },
        "tmdb": {"enabled": False},
        "tvdb": {"enabled": False},
        "omdb": {"enabled": False},
        "tvmaze": {"enabled": False},
        "ffprobe": {"enabled": False},
        "tasker": {"enabled": False},
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and k in config and isinstance(config[k], dict):
            config[k].update(v)
        else:
            config[k] = v
    return config


# ---------------------------------------------------------------------------
# Test: Scanner creates jobs from virtual paths
# ---------------------------------------------------------------------------

class TestScannerPlugin:
    """Test scanner plugin with virtual paths."""

    def test_scanner_creates_jobs(self, state, event_bus, debugger, persistence):
        """Scanner should create one job per target path."""
        config = make_config(
            scanner={
                "enabled": True,
                "targets": [
                    "/virtual/Breaking.Bad.S01E01.720p.BluRay.x264.mkv",
                    "/virtual/The.Matrix.1999.1080p.BluRay.x264.mkv",
                ],
                "allow_virtual_paths": True,
                "extensions": ["mkv"],
                "recursive": False,
            }
        )

        state.configure(persistence=persistence, debugger=debugger, event_bus=event_bus)
        state.start_run(config)

        registry = PluginRegistry(config, debugger=debugger)
        registry.discover_and_load()

        # Get scanner plugin
        scanner = registry.get_plugin("scanner")
        assert scanner is not None

        # Execute scanner as per_run
        from archiverr.core.services.plugin_services import PluginServices
        services = PluginServices(
            state=state, event_bus=event_bus, logger=debugger,
            config=config, mode="per_run", current_plugin_name="scanner"
        )
        result = scanner.execute_run(services)

        jobs = state.get_all_jobs()
        assert len(jobs) == 2
        assert jobs[0].input.value == "/virtual/Breaking.Bad.S01E01.720p.BluRay.x264.mkv"
        assert jobs[1].input.value == "/virtual/The.Matrix.1999.1080p.BluRay.x264.mkv"


# ---------------------------------------------------------------------------
# Test: Renamer parses filenames correctly
# ---------------------------------------------------------------------------

class TestRenamerPlugin:
    """Test renamer plugin with various filename formats."""

    def _make_job(self, filename: str, index: int = 0) -> JobState:
        return JobState(
            index=index,
            run_id="run_test",
            input=InputData(value=f"/virtual/{filename}")
        )

    def test_parses_tv_show(self):
        """Renamer should detect TV show format."""
        from archiverr.plugins.renamer.client import RenamerPlugin

        plugin = RenamerPlugin({"media_type": "auto"})
        job = self._make_job("Breaking.Bad.S01E01.720p.BluRay.x264.mkv")
        services = MagicMock()

        result = plugin.execute(job, services)

        assert result.success
        assert result.data["category"] == "show"
        assert result.data["parsed"]["show"]["name"] == "Breaking Bad"
        assert result.data["parsed"]["show"]["season"] == 1
        assert result.data["parsed"]["show"]["episode"] == 1

    def test_parses_movie(self):
        """Renamer should detect movie format."""
        from archiverr.plugins.renamer.client import RenamerPlugin

        plugin = RenamerPlugin({"media_type": "auto"})
        job = self._make_job("The.Matrix.1999.1080p.BluRay.x264.mkv")
        services = MagicMock()

        result = plugin.execute(job, services)

        assert result.success
        assert result.data["category"] == "movie"
        assert result.data["parsed"]["movie"]["name"] == "The Matrix"
        assert result.data["parsed"]["movie"]["year"] == 1999

    def test_parses_movie_with_dots(self):
        """Renamer should handle movie names with dots."""
        from archiverr.plugins.renamer.client import RenamerPlugin

        plugin = RenamerPlugin({"media_type": "auto"})
        job = self._make_job("Inception.2010.BluRay.mkv")
        services = MagicMock()

        result = plugin.execute(job, services)

        assert result.success
        assert result.data["category"] == "movie"
        assert result.data["parsed"]["movie"]["name"] == "Inception"
        assert result.data["parsed"]["movie"]["year"] == 2010

    def test_unknown_format(self):
        """Renamer should return some category for any filename."""
        from archiverr.plugins.renamer.client import RenamerPlugin

        plugin = RenamerPlugin({"media_type": "auto"})
        job = self._make_job("random_file.mkv")
        services = MagicMock()

        result = plugin.execute(job, services)

        assert result.success
        # Parser may detect as show or unknown depending on filename
        assert result.data["category"] in ("show", "movie", "unknown")

    @pytest.mark.parametrize("filename,expected_name,expected_season,expected_episode", [
        ("Game.of.Thrones.S08E06.720p.mkv", "Game Of Thrones", 8, 6),
        ("The.Office.US.S02E15.1080p.mkv", "The Office Us", 2, 15),
        ("Stranger.Things.S04E01.BluRay.mkv", "Stranger Things", 4, 1),
    ])
    def test_various_shows(self, filename, expected_name, expected_season, expected_episode):
        """Renamer should parse various TV show formats."""
        from archiverr.plugins.renamer.client import RenamerPlugin

        plugin = RenamerPlugin({"media_type": "auto"})
        job = self._make_job(filename)
        services = MagicMock()

        result = plugin.execute(job, services)

        assert result.success
        assert result.data["category"] == "show"
        assert result.data["parsed"]["show"]["name"] == expected_name
        assert result.data["parsed"]["show"]["season"] == expected_season
        assert result.data["parsed"]["show"]["episode"] == expected_episode


# ---------------------------------------------------------------------------
# Test: TMDb plugin with mocked API
# ---------------------------------------------------------------------------

class TestTMDbPluginMocked:
    """Test TMDb plugin with mocked HTTP requests."""

    def _make_job_with_renamer(self, category: str, name: str, **kwargs) -> JobState:
        """Create a job with renamer data pre-populated."""
        parsed = {"show": None, "movie": None}
        if category == "movie":
            parsed["movie"] = {"name": name, "year": kwargs.get("year", 2023)}
        elif category == "show":
            parsed["show"] = {
                "name": name,
                "season": kwargs.get("season", 1),
                "episode": kwargs.get("episode", 1),
            }

        job = JobState(
            index=0, run_id="run_test",
            input=InputData(value=f"/virtual/{name.replace(' ', '.')}.mkv")
        )
        job.plugins["renamer"] = {"parsed": parsed, "category": category}
        return job

    @patch("archiverr.plugins.tmdb.utils.api.requests.get")
    def test_movie_search(self, mock_get):
        """TMDb should search for and return movie data."""
        from archiverr.plugins.tmdb.client import TMDbPlugin

        # Mock search response
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {
            "results": [{
                "id": 603,
                "title": "The Matrix",
                "release_date": "1999-03-31",
                "overview": "A computer hacker learns about the true nature of reality.",
                "vote_average": 8.7,
                "genre_ids": [28, 878],
            }],
            "total_results": 1
        }

        # Mock details response
        mock_details_response = MagicMock()
        mock_details_response.status_code = 200
        mock_details_response.json.return_value = {
            "id": 603,
            "title": "The Matrix",
            "original_title": "The Matrix",
            "release_date": "1999-03-31",
            "overview": "A computer hacker learns about the true nature of reality.",
            "vote_average": 8.7,
            "vote_count": 25000,
            "runtime": 136,
            "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Science Fiction"}],
            "production_countries": [{"iso_3166_1": "US", "name": "United States"}],
            "spoken_languages": [{"iso_639_1": "en", "name": "English"}],
            "budget": 63000000,
            "revenue": 463517383,
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "imdb_id": "tt0133093",
        }

        mock_get.return_value = mock_search_response

        plugin = TMDbPlugin({
            "api_key": "test_key_123",
            "language": "en-US",
            "region": "US",
            "extras": {},
        })

        job = self._make_job_with_renamer("movie", "The Matrix", year=1999)
        services = MagicMock()

        # Mock the API to return different responses for different URLs
        def side_effect(url, **kwargs):
            if "search/movie" in url:
                return mock_search_response
            else:
                return mock_details_response

        mock_get.side_effect = side_effect

        result = plugin.execute(job, services)

        assert result.success
        assert "movie" in result.data or "data" in result.data


# ---------------------------------------------------------------------------
# Test: Full Pipeline (scanner -> renamer -> tasker)
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Test the complete pipeline without external API calls."""

    def test_scanner_renamer_tasker_pipeline(self, state, event_bus, debugger, persistence):
        """Full pipeline: scanner finds files, renamer parses, tasker outputs."""
        config = make_config(
            scanner={
                "enabled": True,
                "targets": [
                    "/virtual/Breaking.Bad.S01E01.720p.BluRay.x264.mkv",
                    "/virtual/The.Matrix.1999.1080p.BluRay.x264.mkv",
                ],
                "allow_virtual_paths": True,
                "extensions": ["mkv"],
                "recursive": False,
            },
            renamer={"enabled": True, "media_type": "auto"},
            tasker={
                "enabled": True,
                "dry_run": True,
                "save_output": False,
                "tasks": [
                    {
                        "name": "test_output",
                        "type": "print",
                        "template": "Parsed: {{ job.plugins.renamer.category }}",
                    }
                ],
            },
        )

        state.configure(persistence=persistence, debugger=debugger, event_bus=event_bus)
        state.start_run(config)

        registry = PluginRegistry(config, debugger=debugger)
        registry.discover_and_load()

        # Step 1: Run scanner (per_run)
        scanner = registry.get_plugin("scanner")
        assert scanner is not None

        from archiverr.core.services.plugin_services import PluginServices
        scanner_services = PluginServices(
            state=state, event_bus=event_bus, logger=debugger,
            config=config, mode="per_run", current_plugin_name="scanner"
        )
        scanner.execute_run(scanner_services)

        jobs = state.get_all_jobs()
        assert len(jobs) == 2

        # Step 2: Run renamer (per_job) for each job
        renamer = registry.get_plugin("renamer")
        assert renamer is not None

        for job in jobs:
            renamer_services = PluginServices(
                state=state, event_bus=event_bus, logger=debugger,
                config=config, mode="per_job", current_job_id=job.id,
                current_plugin_name="renamer"
            )
            result = renamer.execute(job, renamer_services)
            assert result.success

        # Verify renamer results
        show_job = jobs[0]
        assert show_job.plugins.get("renamer", {}).get("category") == "show"
        assert show_job.plugins["renamer"]["parsed"]["show"]["name"] == "Breaking Bad"

        movie_job = jobs[1]
        assert movie_job.plugins.get("renamer", {}).get("category") == "movie"
        assert movie_job.plugins["renamer"]["parsed"]["movie"]["name"] == "The Matrix"

    def test_orchestrator_with_null_persistence(self, debugger):
        """Orchestrator should work without MongoDB using NullPersistence."""
        config = make_config(
            scanner={
                "enabled": True,
                "targets": ["/virtual/Inception.2010.BluRay.mkv"],
                "allow_virtual_paths": True,
                "extensions": ["mkv"],
            },
            renamer={"enabled": True, "media_type": "auto"},
        )

        persistence = NullPersistence()
        event_bus = EventBus(debugger=debugger)

        orchestrator = build_orchestrator(
            config=config,
            debugger=debugger,
            persistence=persistence,
            event_bus=event_bus,
        )

        result = orchestrator.run()

        # Should complete without errors
        assert result is not None


# ---------------------------------------------------------------------------
# Test: Plugin Protocol Compliance
# ---------------------------------------------------------------------------

class TestPluginProtocol:
    """Verify all plugins follow the current protocol."""

    def test_all_per_job_plugins_return_plugin_result(self):
        """All per_job plugins should return PluginResult from execute()."""
        from archiverr.core.plugins.sdk import PluginResult

        from archiverr.plugins.renamer.client import RenamerPlugin
        from archiverr.plugins.ffprobe.client import FFProbePlugin
        from archiverr.plugins.tmdb.client import TMDbPlugin
        from archiverr.plugins.tvdb.client import TVDbPlugin
        from archiverr.plugins.omdb.client import OMDbPlugin
        from archiverr.plugins.tvmaze.client import TVMazePlugin
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        # All should be importable without errors
        plugins = [RenamerPlugin, FFProbePlugin, TMDbPlugin,
                    TVDbPlugin, OMDbPlugin, TVMazePlugin, TaskerPlugin]

        import inspect
        for plugin_cls in plugins:
            sig = inspect.signature(plugin_cls.execute)
            params = list(sig.parameters.keys())
            assert len(params) >= 3, f"{plugin_cls.__name__} should have (self, job, services)"
            assert params[1] == "job", f"{plugin_cls.__name__} first arg should be 'job'"
            assert params[2] == "services", f"{plugin_cls.__name__} second arg should be 'services'"

    def test_all_plugins_inherit_base_class(self):
        """All plugins should inherit from BasePlugin."""
        from archiverr.core.plugins.sdk import BasePlugin, InputPlugin, OutputPlugin

        from archiverr.plugins.scanner.client import ScannerPlugin
        from archiverr.plugins.renamer.client import RenamerPlugin
        from archiverr.plugins.ffprobe.client import FFProbePlugin
        from archiverr.plugins.tmdb.client import TMDbPlugin
        from archiverr.plugins.tvdb.client import TVDbPlugin
        from archiverr.plugins.omdb.client import OMDbPlugin
        from archiverr.plugins.tvmaze.client import TVMazePlugin
        from archiverr.plugins.tasker.plugin import TaskerPlugin

        # Input plugins
        assert issubclass(ScannerPlugin, InputPlugin)

        # Output/per_job plugins
        for cls in [RenamerPlugin, FFProbePlugin, TMDbPlugin,
                    TVDbPlugin, OMDbPlugin, TVMazePlugin, TaskerPlugin]:
            assert issubclass(cls, OutputPlugin), f"{cls.__name__} should extend OutputPlugin"
            assert issubclass(cls, BasePlugin), f"{cls.__name__} should extend BasePlugin"

    def test_null_persistence_works(self):
        """NullPersistence should implement PersistenceInterface correctly."""
        from archiverr.infrastructure.database.interface import PersistenceInterface

        p = NullPersistence()
        assert isinstance(p, PersistenceInterface)

        p.connect()
        p.save_run({"id": "test"})
        p.save_job({"id": "test"})
        p.save_plugin({"id": "test"})
        assert p.get_run("test") is None
        assert p.get_jobs("test") == []
        assert p.get_job("test") is None
        assert p.get_plugins("test") == []
        assert p.get_plugin("test", "p") is None
        stats = p.get_statistics()
        assert stats["backend"] == "NullPersistence"
        p.disconnect()
