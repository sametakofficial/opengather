"""Unit tests for nfo XML builder — no orchestrator."""

from archiverr.plugins.nfo.builder import build_nfo, pick_entity, title_of


def test_movie_nfo_contains_title_and_tmdb_id():
    xml = build_nfo("movie", {
        "title": {"primary": "Inception", "original": "Inception"},
        "identifiers": {"tmdb_id": "27205", "imdb_id": "tt1375666"},
        "release": {"year": 2010},
        "overview": "A thief who steals corporate secrets.",
        "runtime": 148,
        "genres": ["Action", "Science Fiction"],
    })
    assert xml.startswith("<?xml")
    assert "<movie>" in xml
    assert "<title>Inception</title>" in xml
    assert "<year>2010</year>" in xml
    assert 'type="tmdb">27205</uniqueid>' in xml
    assert "<genre>Action</genre>" in xml


def test_episode_nfo_bakes_show_and_episode():
    xml = build_nfo("show", {
        "title": {"primary": "Breaking Bad"},
        "identifiers": {"tmdb_id": "1396"},
        "season_number": 1,
        "episode_number": 1,
        "episode_title": "Pilot",
        "episode_overview": "Walter White.",
    })
    assert "<episodedetails>" in xml
    assert "<showtitle>Breaking Bad</showtitle>" in xml
    assert "<title>Pilot</title>" in xml
    assert "<season>1</season>" in xml
    assert "<episode>1</episode>" in xml


def test_xml_escapes_ampersand():
    xml = build_nfo("movie", {"title": {"primary": "Tom & Jerry"}})
    assert "Tom &amp; Jerry" in xml


def test_pick_entity_prefers_envelope_over_plugin_payload():
    plugins = {
        "tmdb": {"movie": {"title": {"primary": "Wrong"}}},
    }
    envelope = {0: {"movie": {"title": {"primary": "Inception"}}}}
    picked = pick_entity(plugins, envelope, 0)
    assert picked is not None
    assert picked[0] == "movie"
    assert title_of(picked[1]) == "Inception"


def test_pick_entity_falls_back_to_renamer_parsed():
    plugins = {
        "renamer": {
            "category": "show",
            "parsed": {"show": {"name": "Dark", "season": 1, "episode": 1}},
        }
    }
    picked = pick_entity(plugins, None, 0)
    assert picked is not None
    assert picked[0] == "show"
    assert title_of(picked[1]) == "Dark"
    assert picked[1]["season_number"] == 1
