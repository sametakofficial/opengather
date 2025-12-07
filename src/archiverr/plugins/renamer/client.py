"""
Renamer Plugin - Parse filenames and extract metadata

Session 11 - Stage: PARSE, Mode: per_job
"""
from typing import Dict, Any
from datetime import datetime
from pathlib import Path
from .parser import parse_show_name, parse_movie_name
from archiverr.core.plugins.sdk import OutputPlugin, PluginResult


class RenamerPlugin(OutputPlugin):
    """
    PARSE stage plugin - extracts show/movie metadata from filenames.
    
    Provides:
    - job.plugins.renamer.parsed
    - job.plugins.renamer.category
    """
    
    def __init__(self, config: Dict[str, Any]):
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
        
        # Parse based on media_type config
        show_match = None
        movie_match = None
        
        if self.media_type == 'auto':
            movie_match = self._parse_movie(filename)
            if not (movie_match and movie_match.get('year')):
                show_match = self._parse_show(filename)
                movie_match = None
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
        
        # Update plugin state via services (Session 12)
        if hasattr(services, 'updatePlugin'):
            services.updatePlugin(data=result_data)
        elif hasattr(services, 'state'):
            # Fallback for legacy
            services.state.save_plugin_data(
                job_id=job.id,
                plugin_name='renamer',
                stage='parse',
                data=result_data
            )
        
        return PluginResult.success_result(data=result_data, started_at=started_at)
    
    def _parse_show(self, filename: str) -> Dict[str, Any]:
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
        except Exception:
            return None
    
    def _parse_movie(self, filename: str) -> Dict[str, Any]:
        """Parse movie format using parser.py"""
        try:
            movie_name, year = parse_movie_name(filename)
            if not movie_name:
                return None
            
            return {
                'name': movie_name,
                'year': year
            }
        except Exception:
            return None
    
    def _error_result(self) -> Dict[str, Any]:
        """Return error result"""
        now = datetime.now().isoformat()
        return {
            'status': {
                'success': False,
                'started_at': now,
                'finished_at': now,
                'duration_ms': 0
            },
            'parsed': {
                'show': None,
                'movie': None
            }
        }
