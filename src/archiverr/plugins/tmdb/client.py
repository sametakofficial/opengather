"""TMDb Plugin - Clean orchestration layer"""
from typing import Dict, Any, Optional
from datetime import datetime
from .extras import TMDbExtras
from .normalize.normalizer import TMDbNormalizer
from .utils.api import TMDbAPI
from .utils.fetchers import TMDbMovieFetcher, TMDbShowFetcher
from archiverr.core.plugins.sdk import OutputPlugin, PluginResult


class TMDbPlugin(OutputPlugin):
    """
    TMDb metadata plugin - Orchestrates data fetching, extras, and normalization
    
    Architecture:
    - utils/api.py: Low-level API requests
    - utils/fetchers.py: High-level data fetching + extras
    - normalize/normalizer.py: Response normalization to community standard
    - extras.py: Raw endpoint calls
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "tmdb"
        self.api_key = config.get('api_key', '')
        self.lang = config.get('language', config.get('lang', 'en-US'))
        self.region = config.get('region', 'TR')
        self.include_raw = config.get('include-raw', False)  # Default: no raw data
        
        # Components initialized in setup() - None until then
        self.api: Optional[TMDbAPI] = None
        self.extras_client: Optional[TMDbExtras] = None
        self.normalizer: Optional[TMDbNormalizer] = None
        self.movie_fetcher: Optional[TMDbMovieFetcher] = None
        self.show_fetcher: Optional[TMDbShowFetcher] = None
        
        # Get extras configuration
        self.extras_config = config.get('extras', {})
    
    async def setup(self) -> None:
        """Initialize API clients and fetchers (called once on load)"""
        self.api = TMDbAPI(self.api_key, self.lang, self.region)
        self.extras_client = TMDbExtras(self.api_key, self.lang)
        self.normalizer = TMDbNormalizer()
        
        # Initialize fetchers - pass None for debugger, they should use self.log too
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
    
    def _sync_setup(self) -> None:
        """Synchronous setup for backwards compatibility"""
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
    
    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Fetch metadata from TMDb (Session 11 signature).
        
        Args:
            job: JobState with plugins.renamer.parsed
            services: PluginServices
            
        Returns:
            PluginResult with movie/show/episode/season/extras/normalized data
        """
        started_at = datetime.now()
        
        if not self._initialized:
            self._sync_setup()
        
        # Get parsed data from job.plugins or services.state
        parsed_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            renamer_data = job.plugins.get('renamer', {})
            parsed_data = renamer_data.get('parsed', {})
        
        # Fallback: try services.state
        if not parsed_data and hasattr(services, 'state'):
            renamer_data = services.state.get_plugin_data(job.id, 'renamer')
            parsed_data = renamer_data.get('parsed', {})
        
        if not parsed_data:
            return PluginResult.error_result("No parsed data available", started_at=started_at)
        
        # Route to appropriate fetcher
        movie_data = parsed_data.get('movie')
        show_data = parsed_data.get('show')
        
        try:
            result = None
            if movie_data and movie_data.get('name'):
                result = self.movie_fetcher.fetch(
                    movie_data.get('name'),
                    movie_data.get('year')
                )
            elif show_data and show_data.get('name'):
                result = self.show_fetcher.fetch(
                    show_data.get('name'),
                    show_data.get('season'),
                    show_data.get('episode')
                )
            else:
                return PluginResult.error_result("No movie or show data", started_at=started_at)
            
            # Add validation if result successful
            if result and result.get('status', {}).get('success'):
                # Get ffprobe data for validation
                ffprobe_data = {}
                if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
                    ffprobe_data = job.plugins.get('ffprobe', {})
                elif hasattr(services, 'state'):
                    ffprobe_data = services.state.get_plugin_data(job.id, 'ffprobe')
                result['validation'] = self._perform_validation(ffprobe_data, result)
                
                # Emit task example - notify about found metadata
                if result.get('movie'):
                    movie = result['movie']
                    # Handle both dict titles (normalized) and string titles (raw)
                    title = movie.get('title', {})
                    if isinstance(title, dict):
                        movie_title = title.get('primary') or title.get('original') or 'Unknown'
                    else:
                        movie_title = title or 'Unknown'
                    # Year can be in release.year (normalized) or release_date (raw)
                    release = movie.get('release', {})
                    if isinstance(release, dict):
                        movie_year = release.get('year', '')
                    else:
                        movie_year = str(movie.get('release_date', ''))[:4]
                    self.emit_task({
                        "type": "print",
                        "template": f"  ✓ TMDb: {movie_title} ({movie_year})"
                    })
                elif result.get('show'):
                    show = result['show']
                    # Handle both dict names (normalized) and string names (raw)
                    name = show.get('name', {})
                    if isinstance(name, dict):
                        show_name = name.get('primary') or name.get('original') or 'Unknown'
                    else:
                        show_name = name or 'Unknown'
                    self.emit_task({
                        "type": "print",
                        "template": f"  ✓ TMDb: {show_name}"
                    })
            
            # Convert dict result to PluginResult
            # Remove status from data (PluginResult handles it)
            data = {k: v for k, v in result.items() if k != 'status'}
            return PluginResult.success_result(data=data, started_at=started_at)
                
        except Exception as e:
            self.error("Execution failed", error=str(e))
            return PluginResult.error_result(str(e), started_at=started_at)
    
    def _perform_validation(self, ffprobe_data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform validation tests (e.g., duration matching)
        
        Args:
            ffprobe_data: FFProbe plugin result data
            result: TMDb fetch result
            
        Returns:
            {tests_passed, tests_total, details}
        """
        tests = {}
        tests_passed = 0
        tests_total = 0
        
        # Duration validation (for movies and episodes)
        container = ffprobe_data.get('container', {})
        ffprobe_duration = container.get('duration', 0)
        
        if ffprobe_duration > 0:
            # Get runtime from result
            runtime_minutes = None
            if result.get('movie'):
                runtime_minutes = result['movie'].get('runtime')
            elif result.get('episode'):
                runtime_minutes = result['episode'].get('runtime')
            
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
    
    # _error_result() removed - using PluginResult.error_result() instead
