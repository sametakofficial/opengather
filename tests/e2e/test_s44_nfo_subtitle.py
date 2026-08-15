"""S44: nfo + subtitle plugins on the locked output stage.

Parse is enough (no TMDb). Dry-run: nfo plans a sidecar, subtitle
lists tracks next to the file. Nothing is written to disk.
"""

from pathlib import Path

from archiverr.core.orchestrator import build_orchestrator
from archiverr.infrastructure.database.null_persistence import NullPersistence


def _config(archive_dir: Path) -> dict:
    return {
        "options": {
            "debug": False,
            "log_level": "WARNING",
            "dry_run": True,
            "hardlink": False,
            "persistence_mode": "off",
        },
        "scanner": {
            "enabled": True,
            "targets": [str(archive_dir)],
            "allow_virtual_paths": False,
            "extensions": [".mkv"],
            "recursive": True,
        },
        "renamer": {"enabled": True, "media_type": "auto"},
        "ffprobe": {"enabled": False},
        "omdb": {"enabled": False},
        "tvdb": {"enabled": False},
        "tvmaze": {"enabled": False},
        "tmdb": {"enabled": False},
        "tasker": {"enabled": False},
        "nfo": {"enabled": True},
        "subtitle": {"enabled": True},
    }


def test_s44_nfo_and_subtitle_dry_run(tmp_path: Path):
    media = tmp_path / "Breaking.Bad.S01E01.720p.BluRay.x264.mkv"
    media.write_bytes(b"")
    (tmp_path / "Breaking.Bad.S01E01.720p.BluRay.x264.en.srt").write_text("1")
    (tmp_path / "Inception.2010.1080p.BluRay.x264.mkv").write_bytes(b"")

    orch = build_orchestrator(_config(tmp_path), persistence=NullPersistence())
    result = orch.run()
    assert result.error is None, result.error
    assert result.total_jobs == 2

    jobs = {Path(j.input.value).name: j for j in orch._state.get_all_jobs()}
    show = jobs["Breaking.Bad.S01E01.720p.BluRay.x264.mkv"]
    movie = jobs["Inception.2010.1080p.BluRay.x264.mkv"]

    show_nfo = (show.plugins or {}).get("nfo") or {}
    movie_nfo = (movie.plugins or {}).get("nfo") or {}
    assert show_nfo.get("category") == "show"
    assert movie_nfo.get("category") == "movie"
    assert "<episodedetails>" in (show_nfo.get("xml") or "")
    assert "<showtitle>Breaking Bad</showtitle>" in show_nfo["xml"]
    assert "<movie>" in (movie_nfo.get("xml") or "")
    assert "<title>Inception</title>" in movie_nfo["xml"]
    assert show_nfo.get("planned", {}).get("op") == "skip"
    assert not Path(show_nfo["path"]).exists()
    assert not Path(movie_nfo["path"]).exists()

    tracks = ((show.plugins or {}).get("subtitle") or {}).get("tracks") or []
    assert len(tracks) == 1
    assert tracks[0]["language"] == "en"
    movie_tracks = ((movie.plugins or {}).get("subtitle") or {}).get("tracks") or []
    assert movie_tracks == []
