"""TMDb Plugin - Clean orchestration layer"""
from datetime import datetime
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

from .extras import TMDbExtras
from .normalize.normalizer import TMDbNormalizer
from .utils.api import TMDbAPI
from .utils.fetchers import TMDbMovieFetcher, TMDbShowFetcher


class TMDbPlugin(OutputPlugin):
    """
    TMDb metadata plugin - Orchestrates data fetching, extras, and normalization
    
    Architecture:
    - utils/api.py: Low-level API requests
    - utils/fetchers.py: High-level data fetching + extras
    - normalize/normalizer.py: Response normalization to community standard
    - extras.py: Raw endpoint calls
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "tmdb"
        self.api_key = config.get('api_key', '')
        self.lang = config.get('language', config.get('lang', 'en-US'))
        self.region = config.get('region', 'TR')
        self.include_raw = config.get('include-raw', False)  # Default: no raw data

        # Components initialized in setup() - None until then
        self.api: TMDbAPI | None = None
        self.extras_client: TMDbExtras | None = None
        self.normalizer: TMDbNormalizer | None = None
        self.movie_fetcher: TMDbMovieFetcher | None = None
        self.show_fetcher: TMDbShowFetcher | None = None

        # Get extras configuration
        self.extras_config = config.get('extras', {})

    def setup(self) -> None:
        """Initialize API clients and fetchers (called once on load)."""
        self.api = TMDbAPI(self.api_key, self.lang, self.region)
        self.extras_client = TMDbExtras(self.api_key, self.lang)
        self.normalizer = TMDbNormalizer()

        self.movie_fetcher = TMDbMovieFetcher(
            self.api, self.extras_client, self.normalizer,
            self.extras_config, self.include_raw, None
        )
        self.show_fetcher = TMDbShowFetcher(
            self.api, self.extras_client, self.normalizer,
            self.extras_config, self.include_raw, None
        )
        self._initialized = True
        self.info("TMDb plugin initialized", api_key_set=bool(self.api_key))

    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Fetch metadata from TMDb (Session 12).
        
        Args:
            job: JobState with plugins.renamer.data.parsed
            services: PluginServices
            
        Returns:
            PluginResult with movie/show/episode/season/extras/normalized data
        """
        started_at = datetime.now()

        if not self._initialized:
            self.setup()

        # Session 17: Get parsed data from plugin.renamer.parsed (flat structure)
        parsed_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            renamer_data = job.plugins.get('renamer', {})
            # Session 17: Flat structure - parsed is directly in renamer data
            parsed_data = renamer_data.get('parsed', {})

        # Fallback: try services.state
        if not parsed_data and hasattr(services, 'state'):
            renamer_data = services.state.get_plugin_data(job.id, 'renamer')
            if renamer_data:
                parsed_data = renamer_data.get('parsed', {})

        if not parsed_data:
            return PluginResult.error_result("No parsed data available", started_at=started_at)

        # Route to appropriate fetcher
        movie_data = parsed_data.get('movie')
        show_data = parsed_data.get('show')

        try:
            result = None
            if movie_data and movie_data.get('name'):
                # LIVE LOGGING: Log movie search
                self.info("Searching TMDb for movie", name=movie_data.get('name'), year=movie_data.get('year'))
                result = self.movie_fetcher.fetch(
                    movie_data.get('name'),
                    movie_data.get('year')
                )
                if result:
                    self.info("Movie found on TMDb", tmdb_id=result.get('movie', {}).get('identifiers', {}).get('tmdb_id'))
                else:
                    self.warn("Movie not found on TMDb", name=movie_data.get('name'))
            elif show_data and show_data.get('name'):
                # LIVE LOGGING: Log show search
                self.info("Searching TMDb for show", name=show_data.get('name'), season=show_data.get('season'), episode=show_data.get('episode'))
                result = self.show_fetcher.fetch(
                    show_data.get('name'),
                    show_data.get('season'),
                    show_data.get('episode')
                )
                if result and result.get('show'):
                    show_info = result['show']
                    tmdb_id = show_info.get('identifiers', {}).get('tmdb_id') if isinstance(show_info.get('identifiers'), dict) else None
                    self.info("Show found on TMDb", tmdb_id=tmdb_id)
                    if result.get('episode'):
                        self.info("Episode data fetched", episode_count=1)
                else:
                    self.warn("Show not found on TMDb", name=show_data.get('name'))
            else:
                return PluginResult.error_result("No movie or show data", started_at=started_at)

            # S39 §B2 — top-level ``validation`` field removed; live
            # validation tests are out of scope for the metadata
            # contract. Audit found the original implementation was
            # essentially anonymous (no test surface) and tightly
            # coupled to the legacy nested episode/season shape.
            # If/when validation comes back, it lives in a dedicated
            # plugin under the data stage, not piggybacked onto tmdb.
            if result and result.get('status', {}).get('success'):
                if result.get('movie'):
                    movie = result['movie']
                    title = movie.get('title', {})
                    if isinstance(title, dict):
                        movie_title = title.get('primary') or title.get('original') or 'Unknown'
                    else:
                        movie_title = title or 'Unknown'
                    release = movie.get('release', {})
                    if isinstance(release, dict):
                        movie_year = release.get('year', '')
                    else:
                        movie_year = str(movie.get('release_date', ''))[:4]
                    self.info(f"TMDb: {movie_title} ({movie_year})")
                elif result.get('show'):
                    show = result['show']
                    title = show.get('title', {})
                    if isinstance(title, dict):
                        show_name = title.get('primary') or title.get('original') or 'Unknown'
                    else:
                        show_name = title or 'Unknown'
                    self.info(f"TMDb: {show_name}")

            # Convert dict result to PluginResult
            # Remove status from data (PluginResult handles it)
            data = {k: v for k, v in result.items() if k != 'status'}

            # Update plugin state via services (Session 17: snake_case API)
            if services.jobid:
                services.update_state({
                    "jobs": {services.jobid: {"plugins": {self.name: data}}}
                })
            self.debug("TMDb data updated", data_keys=list(data.keys()))

            return PluginResult.success_result(data=data, started_at=started_at)

        except Exception as e:
            self.error("Execution failed", error=str(e))
            return PluginResult.error_result(str(e), started_at=started_at)

    # S39 §B2: ``_perform_validation`` and ``_validate_duration`` REMOVED.
    # The legacy duration-match test was anonymous (no caller test
    # coverage) and tightly coupled to the deprecated nested
    # ``episode``/``season`` shape. Reintroduce in a dedicated
    # validation plugin if/when the contract is reopened.
    # _error_result() removed - using PluginResult.error_result() instead
