# plugins/tmdb/normalizer.py
"""
TMDb Response Normalizer

Converts RAW TMDb API responses to standardized normalized format.
Uses normalized_schema.json for field mappings.

S39 R15 §B1 — flat shape:
- Top-level result objects are ONLY ``show`` and ``movie``.
- ``episode`` / ``season`` are NOT separate top-level objects; the
  episode info (``season_number``, ``episode_number``, ``episode_title``,
  ``episode_overview``, ``episode_air_date``) is BAKED FLAT into the
  ``show`` shape when an episode lookup happened.
- ``media_type`` field removed (the ana key conveys the same info).
"""
from typing import Any


class TMDbNormalizer:
    """Normalize TMDb API responses to community standard format."""

    def normalize_movie(self, movie_data: dict[str, Any], extras: dict[str, Any] = None) -> dict[str, Any]:
        """Normalize movie response (S39 §B1 — flat shape, no media_type)."""
        if not movie_data:
            return {}

        normalized = {
            'identifiers': {
                'tmdb_id': str(movie_data.get('id', '')),
                'imdb_id': movie_data.get('imdb_id')
            },
            'title': {
                'primary': movie_data.get('title'),
                'original': movie_data.get('original_title'),
                'localized': movie_data.get('title')
            },
            'release': {
                'date': movie_data.get('release_date'),
                'year': int(movie_data.get('release_date', '0000')[:4]) if movie_data.get('release_date') else None,
                'status': movie_data.get('status')
            },
            'runtime': movie_data.get('runtime'),
            'ratings': {
                'tmdb': {
                    'score': movie_data.get('vote_average'),
                    'votes': movie_data.get('vote_count')
                }
            },
            'overview': movie_data.get('overview'),
            'genres': [g.get('name') for g in movie_data.get('genres', [])],
            'financial': {
                'budget': movie_data.get('budget'),
                'revenue': movie_data.get('revenue')
            },
            'images': {
                'poster': movie_data.get('poster_path'),
                'backdrop': movie_data.get('backdrop_path')
            }
        }

        # Add extras if provided
        if extras:
            if extras.get('movie_credits'):
                normalized['people'] = self._normalize_credits(extras['movie_credits'])

            if extras.get('movie_images'):
                normalized['images'].update(self._normalize_images(extras['movie_images']))

            if extras.get('movie_videos'):
                normalized['videos'] = self._normalize_videos(extras['movie_videos'])

            if extras.get('movie_keywords'):
                normalized['keywords'] = self._normalize_keywords(extras['movie_keywords'])

        return normalized

    def normalize_show(
        self,
        show_data: dict[str, Any],
        season_data: dict[str, Any] | None = None,
        episode_data: dict[str, Any] | None = None,
        extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Normalize TV show response (S39 §B1 — flat shape).

        Episode info is baked into the show object as flat fields:
            ``season_number``, ``episode_number``, ``episode_title``,
            ``episode_overview``, ``episode_air_date``.
        Season info likewise: ``season_name``, ``season_overview``,
            ``season_air_date``, ``season_episode_count``.
        """
        if not show_data:
            return {}

        normalized = {
            'identifiers': {
                'tmdb_id': str(show_data.get('id', ''))
            },
            'title': {
                'primary': show_data.get('name'),
                'original': show_data.get('original_name'),
                'localized': show_data.get('name')
            },
            'air_dates': {
                'first': show_data.get('first_air_date'),
                'last': show_data.get('last_air_date'),
                'year': int(show_data.get('first_air_date', '0000')[:4]) if show_data.get('first_air_date') else None
            },
            'status': show_data.get('status'),
            'runtime': show_data.get('episode_run_time', [None])[0] if show_data.get('episode_run_time') else None,
            'ratings': {
                'tmdb': {
                    'score': show_data.get('vote_average'),
                    'votes': show_data.get('vote_count')
                }
            },
            'overview': show_data.get('overview'),
            'genres': [g.get('name') for g in show_data.get('genres', [])],
            'network': {
                'name': show_data.get('networks')[0].get('name') if show_data.get('networks') and len(show_data.get('networks')) > 0 else None,
                'id': str(show_data.get('networks')[0].get('id', '')) if show_data.get('networks') and len(show_data.get('networks')) > 0 else None
            } if show_data.get('networks') and len(show_data.get('networks')) > 0 else {},
            'seasons': {
                'total': show_data.get('number_of_seasons')
            },
            'episodes': {
                'total': show_data.get('number_of_episodes')
            },
            'images': {
                'poster': show_data.get('poster_path'),
                'backdrop': show_data.get('backdrop_path')
            }
        }

        # S39 §B1: bake episode fields flat into show.
        if episode_data:
            normalized['season_number'] = episode_data.get('season_number')
            normalized['episode_number'] = episode_data.get('episode_number')
            normalized['episode_title'] = episode_data.get('name')
            normalized['episode_overview'] = episode_data.get('overview')
            normalized['episode_air_date'] = episode_data.get('air_date')
            normalized['episode_runtime'] = episode_data.get('runtime')
            ep_still = episode_data.get('still_path')
            if ep_still:
                normalized['images']['episode_still'] = ep_still

        # S39 §B1: bake season fields flat into show.
        if season_data:
            normalized['season_name'] = season_data.get('name')
            normalized['season_overview'] = season_data.get('overview')
            normalized['season_air_date'] = season_data.get('air_date')
            normalized['season_episode_count'] = (
                len(season_data.get('episodes', []))
                if isinstance(season_data.get('episodes'), list)
                else season_data.get('episode_count')
            )
            season_poster = season_data.get('poster_path')
            if season_poster:
                normalized['images']['season_poster'] = season_poster

        # Add extras if provided
        if extras:
            if extras.get('tv_credits'):
                normalized['people'] = self._normalize_credits(extras['tv_credits'])

            if extras.get('tv_images'):
                normalized['images'].update(self._normalize_images(extras['tv_images']))

            if extras.get('tv_videos'):
                normalized['videos'] = self._normalize_videos(extras['tv_videos'])

            if extras.get('tv_keywords'):
                normalized['keywords'] = self._normalize_keywords(extras['tv_keywords'])

            # Episode-scoped extras still apply when an episode lookup
            # happened — surface them flat under episode-prefixed keys.
            if extras.get('tv_episode_credits'):
                normalized['episode_people'] = self._normalize_episode_credits(
                    extras['tv_episode_credits']
                )
            if extras.get('tv_episode_images'):
                normalized['images'].update(
                    self._normalize_episode_images(extras['tv_episode_images'])
                )

        return normalized

    # S39 §B1: ``normalize_episode`` and ``normalize_season`` have been
    # REMOVED. Episode/season info is now flat-merged into the ``show``
    # object via ``normalize_show(season_data=..., episode_data=...)``.

    def _normalize_credits(self, credits: dict[str, Any]) -> dict[str, Any]:
        """Normalize cast and crew"""
        return {
            'cast': [
                {
                    'id': str(p.get('id', '')),
                    'name': p.get('name'),
                    'character': p.get('character'),
                    'order': p.get('order'),
                    'profile_image': p.get('profile_path')
                }
                for p in credits.get('cast', [])
            ],
            'crew': [
                {
                    'id': str(p.get('id', '')),
                    'name': p.get('name'),
                    'job': p.get('job'),
                    'department': p.get('department'),
                    'profile_image': p.get('profile_path')
                }
                for p in credits.get('crew', [])
            ]
        }

    def _normalize_episode_credits(self, credits: dict[str, Any]) -> dict[str, Any]:
        """Normalize episode credits including guest stars."""
        result = self._normalize_credits(credits)
        result['guest_stars'] = [
            {
                'id': str(p.get('id', '')),
                'name': p.get('name'),
                'character': p.get('character'),
                'order': p.get('order'),
                'profile_image': p.get('profile_path')
            }
            for p in credits.get('guest_stars', [])
        ]
        return result

    def _normalize_images(self, images: dict[str, Any]) -> dict[str, Any]:
        """Normalize images."""
        return {
            'posters': [
                {
                    'url': img.get('file_path'),
                    'width': img.get('width'),
                    'height': img.get('height'),
                    'aspect_ratio': img.get('aspect_ratio'),
                    'language': img.get('iso_639_1'),
                    'rating': img.get('vote_average')
                }
                for img in images.get('posters', [])
            ],
            'backdrops': [
                {
                    'url': img.get('file_path'),
                    'width': img.get('width'),
                    'height': img.get('height'),
                    'aspect_ratio': img.get('aspect_ratio')
                }
                for img in images.get('backdrops', [])
            ]
        }

    def _normalize_episode_images(self, images: dict[str, Any]) -> dict[str, Any]:
        """Normalize episode stills."""
        return {
            'stills': [
                {
                    'url': img.get('file_path'),
                    'width': img.get('width'),
                    'height': img.get('height'),
                    'aspect_ratio': img.get('aspect_ratio')
                }
                for img in images.get('stills', [])
            ]
        }

    def _normalize_videos(self, videos: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize videos."""
        return [
            {
                'id': v.get('id'),
                'key': v.get('key'),
                'name': v.get('name'),
                'site': v.get('site'),
                'type': v.get('type'),
                'size': v.get('size')
            }
            for v in videos.get('results', [])
        ]

    def _normalize_keywords(self, keywords: dict[str, Any]) -> list[str]:
        """Normalize keywords."""
        kw_list = keywords.get('keywords', keywords.get('results', []))
        return [k.get('name') for k in kw_list if k.get('name')]
