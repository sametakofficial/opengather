"""OMDb Plugin - Movie & Show Metadata"""
from datetime import datetime
from typing import Any

import requests

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

from .normalize.normalizer import OMDbNormalizer


class OMDbPlugin(OutputPlugin):
    """Output plugin that fetches metadata from OMDb API"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "omdb"
        self.api_key = config.get('api_key', '')
        self.include_raw = config.get('include-raw', False)  # Default: no raw data
        self.normalizer = OMDbNormalizer()

    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Fetch metadata from OMDb.

        Args:
            job: JobState with plugins.renamer.data.parsed
            services: PluginServices

        Returns:
            PluginResult with movie/show data
        """
        started_at = datetime.now()

        if not self.api_key:
            return PluginResult.skipped_result(reason="No API key configured", started_at=started_at)

        # Get renamer data from job.plugins (new protocol)
        renamer_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            renamer_data = job.plugins.get('renamer', {})

        category = renamer_data.get('category', 'unknown')

        # Check category - OMDb only supports movie and show
        if category not in ['movie', 'show']:
            self.debug("Category not supported", category=category)
            return PluginResult.skipped_result(reason=f"Category '{category}' not supported", started_at=started_at)

        parsed = renamer_data.get('parsed', {})
        movie_data = parsed.get('movie')
        show_data = parsed.get('show')

        self.debug("Processing request", category=category)

        result_data: dict[str, Any] = {
            'movie': None,
            'show': None
        }

        # Search movie
        if category == 'movie' and movie_data and movie_data.get('name'):
            movie_name = movie_data.get('name')
            year = movie_data.get('year')

            try:
                params = {'apikey': self.api_key, 't': movie_name, 'type': 'movie'}
                if year:
                    params['y'] = year

                response = requests.get('https://www.omdbapi.com/', params=params, timeout=5)
                data = response.json()

                if data.get('Response') == 'True':
                    # Normalize (DEFAULT OUTPUT)
                    normalized_movie = self.normalizer.normalize_movie(data)
                    result_data['movie'] = normalized_movie

                    # Add RAW data ONLY if requested (ALL OMDb fields)
                    if self.include_raw:
                        result_data['raw'] = {
                            'movie': data  # Complete raw response
                        }

                    self.info("Movie found", title=data.get('Title'), imdb_rating=data.get('imdbRating'))
                    self.debug("Movie normalized", imdb_id=data.get('imdbID'), title=normalized_movie['title']['primary'], include_raw=self.include_raw)
                else:
                    # Movie not found in OMDb - this is expected, not an error
                    self.debug("Movie not found in OMDb", title=movie_name)
            except Exception as e:
                # Real error (network, timeout, etc.)
                self.error("Movie fetch failed", error=str(e))
                return PluginResult.error_result(str(e), started_at=started_at)

        # Search show
        elif category == 'show' and show_data and show_data.get('name'):
            show_name = show_data.get('name')

            try:
                params = {'apikey': self.api_key, 't': show_name, 'type': 'series'}

                response = requests.get('https://www.omdbapi.com/', params=params, timeout=5)
                data = response.json()

                if data.get('Response') == 'True':
                    # Normalize (DEFAULT OUTPUT)
                    normalized_show = self.normalizer.normalize_show(data)
                    result_data['show'] = normalized_show

                    # Add RAW data ONLY if requested (ALL OMDb fields)
                    if self.include_raw:
                        result_data['raw'] = {
                            'show': data  # Complete raw response
                        }

                    self.debug("TV show normalized", imdb_id=data.get('imdbID'), title=normalized_show['title']['primary'], include_raw=self.include_raw)
                else:
                    # Show not found in OMDb - this is expected, not an error
                    self.debug("Show not found in OMDb", title=show_name)
            except Exception as e:
                # Real error (network, timeout, etc.)
                self.error("Show fetch failed", error=str(e))
                return PluginResult.error_result(str(e), started_at=started_at)

        # Mirror normalized payload onto plugin.omdb.data so downstream Jinja
        # templates can reach `{{ plugin.omdb.data.movie.title.primary }}`
        # consistently with tmdb (Session 38 A1 fix per audit §1).
        if services.jobid:
            services.update_state({
                "jobs": {services.jobid: {"plugins": {self.name: result_data}}}
            })
        return PluginResult.success_result(data=result_data, started_at=started_at)

    def _perform_validation(self, job: Any, omdb_data: dict[str, Any]) -> dict[str, Any]:
        """
        Perform validation tests (duration matching)

        Args:
            job: JobState with plugins dict
            omdb_data: Raw OMDb API response

        Returns:
            {tests_passed, tests_total, details}
        """
        tests = {}
        tests_passed = 0
        tests_total = 0

        # Duration validation - get ffprobe data from job.plugins
        ffprobe_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            ffprobe_data = job.plugins.get('ffprobe', {})

        container = ffprobe_data.get('container', {})
        ffprobe_duration = container.get('duration', 0)

        if ffprobe_duration > 0:
            # Parse runtime from OMDb ("120 min" -> 120)
            runtime_str = omdb_data.get('Runtime', '')
            runtime_minutes = None

            if runtime_str and 'min' in runtime_str:
                try:
                    runtime_minutes = int(runtime_str.replace('min', '').strip())
                except (ValueError, AttributeError):
                    pass

            # Perform validation
            validation_result = self._validate_duration(
                ffprobe_duration,
                runtime_minutes,
                tolerance_seconds=600  # 10 minutes
            )

            tests['duration_match'] = validation_result.details
            tests_total += 1
            if validation_result.passed:
                tests_passed += 1

        return {
            'tests_passed': tests_passed,
            'tests_total': tests_total,
            'details': tests
        }
