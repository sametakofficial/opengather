"""TVDb Plugin - Clean orchestration layer"""
from datetime import datetime
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

from .extras import TVDbExtras
from .normalize.normalizer import TVDbNormalizer
from .utils.api import TVDbAPI


class TVDbPlugin(OutputPlugin):
    """TVDb metadata plugin"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "tvdb"
        self.api_key = config.get('api_key', '')
        self.timeout = 10
        self.include_raw = config.get('include-raw', False)  # Default: no raw data

        # Initialize components
        self.api = TVDbAPI(self.api_key, self.timeout)
        self.extras_client = TVDbExtras(self.api.token, self.timeout)
        self.normalizer = TVDbNormalizer()
        self.extras_config = config.get('extras', {})

    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Fetch metadata from TVDb.

        Args:
            job: JobState with plugins.renamer.data.parsed
            services: PluginServices

        Returns:
            PluginResult with movie/show/season/episode data
        """
        started_at = datetime.now()

        # Get parsed data from job.plugins.renamer
        parsed_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            renamer_data = job.plugins.get('renamer', {})
            parsed_data = renamer_data.get('parsed', {})

        if not parsed_data:
            return PluginResult.error_result("No parsed data available", started_at=started_at)

        movie_data = parsed_data.get('movie')
        show_data = parsed_data.get('show')

        try:
            if movie_data and movie_data.get('name'):
                result = self._fetch_movie(movie_data, started_at)

                # Add validation for movies
                if result.get('status', {}).get('success'):
                    # Get ffprobe data from job.plugins
                    ffprobe_data = {}
                    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                        ffprobe_data = job.plugins.get('ffprobe', {})
                    result['validation'] = self._perform_validation(ffprobe_data, result)

                # Convert dict result to PluginResult
                data = {k: v for k, v in result.items() if k != 'status'}
                return PluginResult.success_result(data=data, started_at=started_at)

            elif show_data and show_data.get('name'):
                result = self._fetch_show(show_data, started_at)

                # Add validation for episodes (if episode data available)
                if result.get('status', {}).get('success') and result.get('episode'):
                    # Get ffprobe data from job.plugins
                    ffprobe_data = {}
                    if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                        ffprobe_data = job.plugins.get('ffprobe', {})
                    result['validation'] = self._perform_validation(ffprobe_data, result)

                # Convert dict result to PluginResult
                data = {k: v for k, v in result.items() if k != 'status'}
                return PluginResult.success_result(data=data, started_at=started_at)

            else:
                return PluginResult.error_result("No movie or show data", started_at=started_at)
        except Exception as e:
            self.error("Execution failed", error=str(e))
            return PluginResult.error_result(str(e), started_at=started_at)

    def _fetch_movie(self, movie_data: dict[str, Any], start_time: datetime) -> dict[str, Any]:
        """Fetch movie metadata"""
        movie_name = movie_data.get('name')
        year = movie_data.get('year')

        # Search movie
        search_results = self.api.search_movie(movie_name)

        if not search_results.get('data'):
            return {'status': {'success': False}}

        movie_id = search_results['data'][0]['tvdb_id']
        self.info("Movie found", tvdb_id=movie_id, title=movie_name)

        # Get extended info
        raw_movie_extended = self.api.get_movie_extended(movie_id)

        # Fetch extras
        raw_extras = {}
        if self.extras_config.get('movies_extended'):
            raw_extras['movies_extended'] = raw_movie_extended
            self.debug("Fetched movies_extended", endpoint="/movies/{id}/extended")

        # Normalize (DEFAULT OUTPUT)
        normalized_movie = self.normalizer.normalize_movie(raw_movie_extended)

        end_time = datetime.now()
        result = {
            'status': {
                'success': True,
                'started_at': start_time.isoformat(),
                'finished_at': end_time.isoformat(),
                'duration_ms': int((end_time - start_time).total_seconds() * 1000)
            },
            'movie': normalized_movie,  # NORMALIZED by default
            'show': None,
            'season': None,
            'episode': None
        }

        # Add RAW data ONLY if requested
        if self.include_raw:
            result['raw'] = {
                'movie': {
                    'name': raw_movie_extended.get('data', {}).get('name'),
                    'year': year,
                    'tvdb_id': movie_id,
                    'overview': raw_movie_extended.get('data', {}).get('overview'),
                    'runtime': raw_movie_extended.get('data', {}).get('runtime')
                },
                'extras': raw_extras
            }

        self.debug("Movie normalized",
                   tvdb_id=movie_id,
                   title=normalized_movie['title']['primary'],
                   include_raw=self.include_raw)

        return result

    def _perform_validation(self, ffprobe_data: dict[str, Any], tvdb_result: dict[str, Any]) -> dict[str, Any]:
        """
        Perform validation tests (duration matching)

        Args:
            ffprobe_data: FFProbe plugin result data
            tvdb_result: TVDb fetch result

        Returns:
            {tests_passed, tests_total, details}
        """
        tests = {}
        tests_passed = 0
        tests_total = 0

        # Get ffprobe duration
        container = ffprobe_data.get('container', {})
        ffprobe_duration = container.get('duration', 0)

        if ffprobe_duration > 0:
            runtime_minutes = None

            # Check movie runtime
            if tvdb_result.get('movie'):
                runtime_minutes = tvdb_result['movie'].get('runtime')

            # Check episode runtime
            elif tvdb_result.get('episode'):
                runtime_minutes = tvdb_result['episode'].get('runtime')

            # Perform validation if runtime available
            if runtime_minutes:
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

    def _fetch_show(self, show_data: dict[str, Any], start_time: datetime) -> dict[str, Any]:
        """Fetch TV show metadata"""
        show_name = show_data.get('name')
        season_num = show_data.get('season')
        episode_num = show_data.get('episode')

        # Search series
        search_results = self.api.search_series(show_name)

        if not search_results.get('data'):
            return {'status': {'success': False}}

        series_id = search_results['data'][0]['tvdb_id']
        self.info("TV show found", tvdb_id=series_id, title=show_name)

        # Get extended info
        raw_series_extended = self.api.get_series_extended(series_id)

        # Fetch extras
        raw_extras = {}
        if self.extras_config.get('series_extended'):
            raw_extras['series_extended'] = raw_series_extended
            self.debug("Fetched series_extended", endpoint="/series/{id}/extended")

        if self.extras_config.get('series_artworks'):
            artworks = self.extras_client.series_artworks(series_id)
            if artworks:
                raw_extras['series_artworks'] = artworks
                self.debug("Fetched series_artworks", endpoint="/series/{id}/artworks")

        # Normalize (DEFAULT OUTPUT)
        normalized_show = self.normalizer.normalize_show(raw_series_extended)

        # Build result
        end_time = datetime.now()
        result = {
            'status': {
                'success': True,
                'started_at': start_time.isoformat(),
                'finished_at': end_time.isoformat(),
                'duration_ms': int((end_time - start_time).total_seconds() * 1000)
            },
            'show': normalized_show,  # NORMALIZED by default
            'season': None,
            'episode': None,
            'movie': None
        }

        # Add RAW data ONLY if requested
        if self.include_raw:
            result['raw'] = {
                'show': {
                    'name': raw_series_extended.get('data', {}).get('name'),
                    'tvdb_id': str(series_id)
                },
                'season': {'number': season_num},
                'episode': {'number': episode_num},
                'extras': raw_extras
            }

        self.debug("TV show normalized",
                   tvdb_id=series_id,
                   title=normalized_show['title']['primary'],
                   include_raw=self.include_raw)

        return result

    # _error_result() removed - using PluginResult.error_result() instead
