"""Unit tests for TMDb normalizer flat shape (S39 R15 §B1)."""

from archiverr.plugins.tmdb.normalize.normalizer import TMDbNormalizer


def _normalizer():
    return TMDbNormalizer()


class TestMovieFlatShape:
    def test_no_media_type(self):
        out = _normalizer().normalize_movie(
            {"id": 1, "title": "Inception", "release_date": "2010-07-16"}
        )
        assert "media_type" not in out

    def test_canonical_keys(self):
        out = _normalizer().normalize_movie(
            {"id": 1, "title": "Inception", "release_date": "2010-07-16",
             "runtime": 148, "vote_average": 8.4, "vote_count": 30000}
        )
        assert out["title"]["primary"] == "Inception"
        assert out["release"]["year"] == 2010
        assert out["runtime"] == 148
        assert out["ratings"]["tmdb"]["score"] == 8.4

    def test_empty_input_returns_empty(self):
        assert _normalizer().normalize_movie({}) == {}


class TestShowFlatShape:
    def test_no_media_type(self):
        out = _normalizer().normalize_show(
            {"id": 2, "name": "Show", "first_air_date": "2010-01-01"}
        )
        assert "media_type" not in out

    def test_show_only_canonical_keys(self):
        out = _normalizer().normalize_show(
            {"id": 2, "name": "Breaking Bad",
             "first_air_date": "2008-01-20",
             "number_of_seasons": 5, "number_of_episodes": 62}
        )
        assert out["title"]["primary"] == "Breaking Bad"
        assert out["air_dates"]["year"] == 2008
        assert out["seasons"]["total"] == 5
        assert out["episodes"]["total"] == 62
        # No flat episode fields when no episode_data passed.
        assert "season_number" not in out
        assert "episode_title" not in out

    def test_episode_baked_flat(self):
        out = _normalizer().normalize_show(
            show_data={"id": 2, "name": "Breaking Bad",
                       "first_air_date": "2008-01-20"},
            episode_data={
                "season_number": 1,
                "episode_number": 1,
                "name": "Pilot",
                "overview": "Walter White learns he has cancer.",
                "air_date": "2008-01-20",
                "runtime": 58,
                "still_path": "/abc.jpg",
            },
        )
        assert out["season_number"] == 1
        assert out["episode_number"] == 1
        assert out["episode_title"] == "Pilot"
        assert out["episode_overview"].startswith("Walter")
        assert out["episode_air_date"] == "2008-01-20"
        assert out["episode_runtime"] == 58
        assert out["images"]["episode_still"] == "/abc.jpg"

    def test_season_baked_flat(self):
        out = _normalizer().normalize_show(
            show_data={"id": 2, "name": "Show",
                       "first_air_date": "2010-01-01"},
            season_data={
                "name": "Season 1",
                "overview": "S1 overview",
                "air_date": "2010-01-01",
                "episodes": [{}, {}, {}],
                "poster_path": "/s1.jpg",
            },
        )
        assert out["season_name"] == "Season 1"
        assert out["season_overview"] == "S1 overview"
        assert out["season_air_date"] == "2010-01-01"
        assert out["season_episode_count"] == 3
        assert out["images"]["season_poster"] == "/s1.jpg"

    def test_no_episode_object_at_top_level(self):
        """S39 §B1: episode is FLAT inside show, never a top-level key."""
        out = _normalizer().normalize_show(
            show_data={"id": 2, "name": "S",
                       "first_air_date": "2010-01-01"},
            episode_data={"season_number": 1, "episode_number": 1,
                          "name": "P"},
        )
        assert "episode" not in out
        assert "season" not in out


class TestRemovedMethods:
    def test_normalize_episode_method_gone(self):
        assert not hasattr(TMDbNormalizer, "normalize_episode")

    def test_normalize_season_method_gone(self):
        assert not hasattr(TMDbNormalizer, "normalize_season")
