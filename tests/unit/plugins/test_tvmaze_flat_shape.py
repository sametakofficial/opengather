"""TVMaze writes TMDb-style flat show keys (S40)."""

from archiverr.plugins.tvmaze.normalize.normalizer import TVMazeNormalizer
from archiverr.plugins.tvmaze.client import TVMazePlugin


def test_episode_fields_bake_into_show(monkeypatch):
    plugin = TVMazePlugin({"include-raw": False, "extras": {}})
    plugin.name = "tvmaze"
    plugin.extras_config = {}
    plugin.normalizer = TVMazeNormalizer()
    plugin.api = type("API", (), {})()
    plugin.api.search_shows = lambda name: [{"show": {"id": 1, "name": "Breaking Bad"}}]
    plugin.api.get_episode_by_number = lambda *a, **k: {
        "id": 9, "name": "Pilot", "season": 1, "number": 1,
        "airdate": "2008-01-20", "runtime": 58, "summary": "chemist",
    }
    plugin._fetch_extras = lambda *a, **k: {}

    result = plugin._fetch_show(
        {"name": "Breaking Bad", "season": 1, "episode": 1},
        started_at=__import__("datetime").datetime.now(),
    )
    assert result.success
    assert "episode" not in result.data
    show = result.data["show"]
    assert show["episode_title"] == "Pilot"
    assert show["season_number"] == 1
    assert show["episode_number"] == 1
