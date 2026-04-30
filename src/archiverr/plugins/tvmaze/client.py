"""TVMaze Plugin - Clean orchestration layer"""
from datetime import datetime
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

from .extras import TVMazeExtras
from .normalize.normalizer import TVMazeNormalizer
from .utils.api import TVMazeAPI


class TVMazePlugin(OutputPlugin):
    """TVMaze metadata plugin"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.include_raw = config.get('include-raw', False)  # Default: no raw data

        # Initialize components
        self.api = TVMazeAPI(timeout=5)
        self.extras_client = TVMazeExtras()
        self.normalizer = TVMazeNormalizer()
        self.extras_config = config.get('extras', {})

    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Fetch metadata from TVMaze.

        Args:
            job: JobState with plugins.renamer.data.parsed
            services: PluginServices

        Returns:
            PluginResult with show/episode/season data
        """
        started_at = datetime.now()

        # Get parsed data from job.plugins.renamer.parsed (flat structure)
        parsed_data = {}
        if hasattr(job, 'plugins') and isinstance(job.plugins, dict):
            renamer_data = job.plugins.get('renamer', {})
            parsed_data = renamer_data.get('parsed', {})

        # Fallback: try services.state
        if not parsed_data and hasattr(services, 'state'):
            renamer_data = services.state.get_plugin_data(job.id, 'renamer')
            if renamer_data:
                parsed_data = renamer_data.get('parsed', {})

        if not parsed_data:
            return PluginResult.error_result("No parsed data available", started_at=started_at)

        # TVMaze only supports TV shows
        show_data = parsed_data.get('show')
        if not show_data or not show_data.get('name'):
            self.debug("Not a TV show, skipping")
            return PluginResult.skipped_result(reason="Not a TV show", started_at=started_at)

        try:
            result = self._fetch_show(show_data, started_at)
            # Mirror normalized payload onto plugin.tvmaze.data so downstream
            # Jinja templates can reach `{{ plugin.tvmaze.data.show.* }}`
            # consistently with tmdb (Session 38 A3 fix per audit §1).
            if result.success and result.data:
                services.update_plugin(data=result.data)
            return result
        except Exception as e:
            self.error("Execution failed", error=str(e))
            return PluginResult.error_result(str(e), started_at=started_at)

    def _fetch_show(self, show_data: dict[str, Any], started_at: datetime) -> PluginResult:
        """Fetch TV show metadata"""
        show_name = show_data.get('name')
        season_num = show_data.get('season')
        episode_num = show_data.get('episode')

        # Search show
        self.info("Searching TVMaze for show", name=show_name, season=season_num, episode=episode_num)
        search_results = self.api.search_shows(show_name)

        if not search_results or len(search_results) == 0:
            self.warn("Show not found on TVMaze", name=show_name)
            return PluginResult.error_result("No search results", started_at=started_at)

        show_info = search_results[0]['show']
        show_id = show_info.get('id')
        self.info("TV show found", tvmaze_id=show_id, title=show_info.get('name'))

        # Get episode if provided
        episode_info = None
        if season_num and episode_num:
            try:
                episode_info = self.api.get_episode_by_number(show_id, season_num, episode_num)
            except Exception as e:
                # Episode lookup is best-effort; surface failure in debug log
                # so it isn't silently lost (Session 38 A4: was bare `pass`).
                self.debug("Episode lookup failed", error=str(e),
                           season=season_num, episode=episode_num)

        # Fetch extras
        raw_extras = self._fetch_extras(show_id, episode_info)

        # Normalize (DEFAULT OUTPUT)
        normalized_show = self.normalizer.normalize_show(show_info, raw_extras)
        # Session 38 A4 fix: episode_info was fetched above but never written
        # to data['episode']. Now normalized via normalize_episode().
        normalized_episode = (
            self.normalizer.normalize_episode(episode_info, show_id=show_id)
            if episode_info else None
        )

        # Build result data
        data = {
            'show': normalized_show,  # NORMALIZED by default
            'episode': normalized_episode,
            'season': None,  # TVMaze has no /season endpoint shape we normalize today
            'movie': None,
        }

        # Add RAW data ONLY if requested
        if self.include_raw:
            data['raw'] = {
                'show': {
                    'name': show_info.get('name'),
                    'tvmaze_id': show_info.get('id'),
                    'url': show_info.get('url'),
                    'type': show_info.get('type'),
                    'language': show_info.get('language'),
                    'status': show_info.get('status'),
                    'premiered': show_info.get('premiered'),
                    'rating': show_info.get('rating', {}).get('average'),
                    'network': show_info.get('network', {}).get('name') if show_info.get('network') else None,
                    'summary': show_info.get('summary')
                },
                'episode': {
                    'id': episode_info.get('id'),
                    'name': episode_info.get('name'),
                    'season': episode_info.get('season'),
                    'number': episode_info.get('number'),
                    'airdate': episode_info.get('airdate'),
                    'runtime': episode_info.get('runtime'),
                    'summary': episode_info.get('summary')
                } if episode_info else None,
                'extras': raw_extras
            }

        self.debug("TV show normalized",
                   tvmaze_id=show_id,
                   title=normalized_show['title']['primary'],
                   cast_count=len(normalized_show.get('people', {}).get('cast', [])),
                   include_raw=self.include_raw)

        return PluginResult.success_result(data=data, started_at=started_at)

    def _fetch_extras(self, show_id: int, episode_info: dict[str, Any] = None) -> dict[str, Any]:
        """Fetch all enabled extras"""
        extras = {}

        # Shows Cast
        if self.extras_config.get('shows_cast'):
            data = self.extras_client.shows_cast(show_id)
            if data:
                extras['shows_cast'] = data
                self.debug("Fetched shows_cast",
                                   endpoint="/shows/{id}/cast",
                                   count=len(data))

        # Shows Crew
        if self.extras_config.get('shows_crew'):
            data = self.extras_client.shows_crew(show_id)
            if data:
                extras['shows_crew'] = data
                self.debug("Fetched shows_crew",
                                   endpoint="/shows/{id}/crew",
                                   count=len(data))

        # Shows Images
        if self.extras_config.get('shows_images'):
            data = self.extras_client.shows_images(show_id)
            if data:
                extras['shows_images'] = data
                self.debug("Fetched shows_images",
                                   endpoint="/shows/{id}/images",
                                   count=len(data))

        # Episode extras
        if episode_info:
            episode_id = episode_info.get('id')

            if self.extras_config.get('episodes_single'):
                data = self.extras_client.episodes_single(episode_id)
                if data:
                    extras['episodes_single'] = data
                    self.debug("Fetched episodes_single",
                                       endpoint="/episodes/{id}")

            if self.extras_config.get('episodes_guestcast'):
                data = self.extras_client.episodes_guestcast(episode_id)
                if data:
                    extras['episodes_guestcast'] = data
                    self.debug("Fetched episodes_guestcast",
                                       endpoint="/episodes/{id}/guestcast",
                                       count=len(data))

            if self.extras_config.get('episodes_guestcrew'):
                data = self.extras_client.episodes_guestcrew(episode_id)
                if data:
                    extras['episodes_guestcrew'] = data
                    self.debug("Fetched episodes_guestcrew",
                                       endpoint="/episodes/{id}/guestcrew",
                                       count=len(data))

        return extras

    # _not_supported_result() removed - using PluginResult.skipped_result() instead
    # _error_result() removed - using PluginResult.error_result() instead
