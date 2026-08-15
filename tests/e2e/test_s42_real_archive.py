"""S42: 16-file dry-run proof on real filesystem paths.

G1 already proved one virtual Breaking Bad fixture through Mongo.
S42 asks a different question: given a small mixed archive of *real*
files (empty containers are enough — scanner stats them), does the
locked PARSE → DATA pipeline still identify the work?

Parse assertions always run. Live TMDb assertions run only when
``TMDB_API_KEY`` is set (same skip rule as ``test_tmdb_smoke``).
Persistence is ``off`` so this file does not need pymongo.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import pytest

from archiverr.core.orchestrator import build_orchestrator
from archiverr.infrastructure.database.null_persistence import NullPersistence

# (filename, category, parsed_name, year_or_(season, episode), tmdb_id)
ARCHIVE = (
    ("Breaking.Bad.S01E01.720p.BluRay.x264.mkv", "show", "Breaking Bad", (1, 1), "1396"),
    ("Breaking.Bad.S01E02.720p.BluRay.x264.mkv", "show", "Breaking Bad", (1, 2), "1396"),
    ("Breaking.Bad.S02E01.720p.BluRay.x264.mkv", "show", "Breaking Bad", (2, 1), "1396"),
    ("Game.of.Thrones.S01E01.1080p.BluRay.mkv", "show", "Game Of Thrones", (1, 1), "1399"),
    ("Better.Call.Saul.S01E01.720p.WEBRip.mkv", "show", "Better Call Saul", (1, 1), "60059"),
    ("Chernobyl.S01E01.1080p.AMZN.WEB-DL.mkv", "show", "Chernobyl", (1, 1), "87108"),
    ("Dark.S01E01.GERMAN.720p.WEB.mkv", "show", "Dark", (1, 1), "70523"),
    ("The.Wire.S01E01.720p.BluRay.x264.mkv", "show", "The Wire", (1, 1), "1438"),
    ("The.Matrix.1999.1080p.BluRay.x264.mkv", "movie", "The Matrix", 1999, "603"),
    ("Inception.2010.1080p.BluRay.x264.mkv", "movie", "Inception", 2010, "27205"),
    ("Pulp.Fiction.1994.1080p.BluRay.mkv", "movie", "Pulp Fiction", 1994, "680"),
    ("The.Godfather.1972.1080p.BluRay.mkv", "movie", "The Godfather", 1972, "238"),
    ("Parasite.2019.1080p.BluRay.mkv", "movie", "Parasite", 2019, "496243"),
    ("Spirited.Away.2001.1080p.BluRay.mkv", "movie", "Spirited Away", 2001, "129"),
    ("Interstellar.2014.1080p.BluRay.mkv", "movie", "Interstellar", 2014, "157336"),
    ("Whiplash.2014.1080p.BluRay.mkv", "movie", "Whiplash", 2014, "244786"),
)

TMDB_TITLES = {
    "1396": "Breaking Bad",
    "1399": "Game of Thrones",
    "60059": "Better Call Saul",
    "87108": "Chernobyl",
    "70523": "Dark",
    "1438": "The Wire",
    "603": "The Matrix",
    "27205": "Inception",
    "680": "Pulp Fiction",
    "238": "The Godfather",
    "496243": "Parasite",
    "129": "Spirited Away",
    "157336": "Interstellar",
    "244786": "Whiplash",
}


def _touch_archive(root: Path) -> list[Path]:
    paths = []
    for name, *_rest in ARCHIVE:
        path = root / name
        path.write_bytes(b"")
        paths.append(path)
    return paths


def _s42_config(archive_dir: Path, *, tmdb_key: str | None) -> dict:
    tmdb_enabled = bool(tmdb_key)
    return {
        "options": {
            "debug": False,
            "log_level": "WARNING",
            "dry_run": True,
            "hardlink": True,
            "persistence_mode": "off",
        },
        "data_priority": {
            "show": ["tmdb"],
            "movie": ["tmdb"],
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
        "tasker": {"enabled": False},
        "tmdb": {
            "enabled": tmdb_enabled,
            "api_key": tmdb_key or "",
            "language": "en-US",
            "region": "US",
            "include-raw": False,
            "extras": {},
        },
    }


def _jobs_by_name(state) -> dict[str, object]:
    out = {}
    for job in state.get_all_jobs():
        out[Path(job.input.value).name] = job
    return out


def _renamer(job) -> dict:
    return (job.plugins or {}).get("renamer") or {}


def _tmdb(job) -> dict:
    return (job.plugins or {}).get("tmdb") or {}


@pytest.fixture
def s42_archive(tmp_path: Path) -> Path:
    archive = tmp_path / "s42-archive"
    archive.mkdir()
    _touch_archive(archive)
    return archive


def test_s42_parses_sixteen_real_files(s42_archive: Path):
    """Scanner sees 16 real paths; renamer names every one correctly."""
    orch = build_orchestrator(
        _s42_config(s42_archive, tmdb_key=None),
        persistence=NullPersistence(),
    )
    result = orch.run()

    assert result.error is None, result.error
    assert result.total_jobs == len(ARCHIVE)
    jobs = _jobs_by_name(orch._state)
    assert set(jobs) == {row[0] for row in ARCHIVE}

    for name, category, parsed_name, extra, _tmdb_id in ARCHIVE:
        job = jobs[name]
        ren = _renamer(job)
        assert job.input.data.get("filesystem") is True, name
        assert Path(job.input.value).is_file(), name
        assert ren.get("category") == category, (name, ren)
        parsed = ren.get("parsed") or {}
        if category == "show":
            show = parsed.get("show") or {}
            season, episode = extra
            assert show.get("name") == parsed_name, (name, show)
            assert show.get("season") == season, (name, show)
            assert show.get("episode") == episode, (name, show)
        else:
            movie = parsed.get("movie") or {}
            assert movie.get("name") == parsed_name, (name, movie)
            assert movie.get("year") == extra, (name, movie)


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("TMDB_API_KEY"), reason="TMDB_API_KEY not set")
def test_s42_tmdb_recognizes_archive(s42_archive: Path):
    """Live TMDb: each parsed name maps to the known work (id + title)."""
    orch = build_orchestrator(
        _s42_config(s42_archive, tmdb_key=os.environ["TMDB_API_KEY"]),
        persistence=NullPersistence(),
    )
    result = orch.run()

    assert result.error is None, result.error
    assert result.total_jobs == len(ARCHIVE)
    jobs = _jobs_by_name(orch._state)
    failures: list[str] = []

    for name, category, _parsed_name, extra, tmdb_id in ARCHIVE:
        payload = _tmdb(jobs[name])
        entity = (payload.get("show") if category == "show" else payload.get("movie")) or {}
        got_id = str((entity.get("identifiers") or {}).get("tmdb_id") or "")
        title = ((entity.get("title") or {}).get("primary") or "")
        expect_title = TMDB_TITLES[tmdb_id]
        if got_id != tmdb_id or title != expect_title:
            failures.append(
                f"{name}: expected {expect_title} #{tmdb_id}, got {title!r} #{got_id or '?'}"
            )
            continue
        if category == "show":
            season, episode = extra
            if entity.get("season_number") != season or entity.get("episode_number") != episode:
                failures.append(
                    f"{name}: episode bake "
                    f"S{entity.get('season_number')}E{entity.get('episode_number')} "
                    f"!= S{season}E{episode}"
                )

    bb = _tmdb(jobs["Breaking.Bad.S01E01.720p.BluRay.x264.mkv"]).get("show") or {}
    if (bb.get("episode_title") or "").strip().lower() != "pilot":
        failures.append(
            f"Breaking Bad S01E01 episode_title={bb.get('episode_title')!r} (want Pilot)"
        )

    assert not failures, "S42 recognition failures:\n" + "\n".join(failures)
