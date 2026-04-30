"""
Renamer Plugin - Parse filenames and extract metadata

Session 11 - Stage: PARSE, Mode: per_job
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

from .parser import parse_movie_name, parse_show_name

# Explicit show markers — patterns that strongly indicate a TV episode:
#   S01E02, s1e2, 1x02, 01x02. Used by the auto-detect branch as a
#   high-confidence signal so movie filenames without a year (e.g.
#   ``Inception.1080p.mkv``) are not misrouted to the show parser,
#   which today returns a default season=1/episode=1 even when no
#   episode markers are present (Session 38 B2 fix).
_SHOW_MARKER_RE = re.compile(r'(?:s\d{1,2}e\d{1,3}|\d{1,2}x\d{1,3})', re.IGNORECASE)


class RenamerPlugin(OutputPlugin):
    """
    PARSE stage plugin - extracts show/movie metadata from filenames.
    
    Provides:
    - job.plugins.renamer.parsed
    - job.plugins.renamer.category
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "renamer"
        self.media_type = config.get('media_type', 'auto')

    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Parse filename and extract metadata (Session 11 signature).
        
        Args:
            job: JobState with input.value
            services: PluginServices
            
        Returns:
            PluginResult with parsed data
        """
        started_at = datetime.now()

        # Get input path from job
        input_path = job.input.value if hasattr(job.input, 'value') else str(job.input)

        if not input_path:
            return PluginResult.error_result("No input path", started_at=started_at)

        filename = Path(input_path).stem

        self.debug("Parsing filename", filename=filename, mode=self.media_type)

        # Parse based on media_type config.
        #
        # Session 38 B2 fix: previously the auto branch tried movie first
        # and only fell through to show parsing when no year was extracted,
        # which misrouted any movie filename without a year (e.g.
        # ``Inception.1080p.mkv``) to the show parser. Naively flipping
        # the order doesn't work either, because ``parse_show_name``
        # returns a default season=1/episode=1 even on movie filenames.
        # The reliable signal is an explicit S##E## / NxNN marker in the
        # original filename — that is a strictly higher-confidence flag
        # than either parser's heuristic output.
        show_match = None
        movie_match = None

        if self.media_type == 'auto':
            if _SHOW_MARKER_RE.search(filename):
                show_match = self._parse_show(filename)
                if not show_match:
                    movie_match = self._parse_movie(filename)
            else:
                movie_match = self._parse_movie(filename)
                if not movie_match:
                    show_match = self._parse_show(filename)
        elif self.media_type == 'show':
            show_match = self._parse_show(filename)
        elif self.media_type == 'movie':
            movie_match = self._parse_movie(filename)

        # Determine category
        category = 'unknown'
        if movie_match and movie_match.get('name'):
            category = 'movie'
            self.info("Detected movie", name=movie_match['name'], year=movie_match.get('year'))
        elif show_match and show_match.get('name'):
            category = 'show'
            self.info("Detected show", name=show_match['name'],
                     season=show_match.get('season'), episode=show_match.get('episode'))
        else:
            self.warn("Could not detect category", filename=filename)

        # Session 12: Save to plugin.renamer.data.*
        result_data = {
            'parsed': {
                'show': show_match,
                'movie': movie_match
            },
            'category': category
        }

        # Update plugin state via services (Session 17: snake_case API)
        if hasattr(services, 'update_plugin'):
            services.update_plugin(data=result_data)

        return PluginResult.success_result(data=result_data, started_at=started_at)

    def _parse_show(self, filename: str) -> dict[str, Any]:
        """Parse TV show format using parser.py"""
        try:
            show_name, season, episode, failed = parse_show_name(filename)
            if failed or not show_name:
                return None

            return {
                'name': show_name,
                'season': season,
                'episode': episode
            }
        except Exception as e:
            self.warn("Show parse failed", filename=filename, error=str(e))
            return None

    def _parse_movie(self, filename: str) -> dict[str, Any]:
        """Parse movie format using parser.py"""
        try:
            movie_name, year = parse_movie_name(filename)
            if not movie_name:
                return None

            return {
                'name': movie_name,
                'year': year
            }
        except Exception as e:
            self.warn("Movie parse failed", filename=filename, error=str(e))
            return None

    # Session 38 B1: removed dead ``_error_result`` helper — error paths
    # now return ``PluginResult.error_result(...)`` directly via the
    # canonical SDK factory.
