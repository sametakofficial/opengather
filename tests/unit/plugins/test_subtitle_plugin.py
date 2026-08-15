"""Subtitle sidecar discovery + optional dry_run copy."""

from pathlib import Path
from types import SimpleNamespace

from archiverr.plugins.subtitle.client import SubtitlePlugin
from archiverr.plugins.subtitle.discover import discover_sidecars, language_of


def test_language_of_suffix():
    assert language_of("Movie.2010.en", "Movie.2010") == "en"
    assert language_of("Movie.2010.tr.forced", "Movie.2010") == "tr"
    assert language_of("Movie.2010", "Movie.2010") == ""


def test_discover_sidecars_matches_stem(tmp_path: Path):
    media = tmp_path / "Inception.2010.mkv"
    media.write_bytes(b"x")
    (tmp_path / "Inception.2010.en.srt").write_text("1")
    (tmp_path / "Inception.2010.tr.srt").write_text("2")
    (tmp_path / "Other.2010.en.srt").write_text("nope")
    tracks = discover_sidecars(media)
    names = {t["filename"] for t in tracks}
    assert names == {"Inception.2010.en.srt", "Inception.2010.tr.srt"}
    langs = {t["language"] for t in tracks}
    assert langs == {"en", "tr"}


def test_plugin_lists_tracks_without_copy(tmp_path: Path):
    media = tmp_path / "Dark.S01E01.mkv"
    media.write_bytes(b"")
    (tmp_path / "Dark.S01E01.srt").write_text("hi")
    job = SimpleNamespace(
        id="j1",
        index=0,
        input=SimpleNamespace(value=str(media), data={}),
        plugins={"renamer": {"category": "show", "parsed": {"show": {"name": "Dark"}}}},
    )
    patches = []
    services = SimpleNamespace(
        jobid="j1",
        run_safety={"dry_run": True, "hardlink": False, "no_delete": True},
        update_state=lambda patch, mode="merge": patches.append(patch),
    )
    result = SubtitlePlugin({}).execute(job, services)
    assert result.success
    assert result.data["count"] == 1
    assert result.data["tracks"][0]["filename"] == "Dark.S01E01.srt"
    assert result.data["copied"] == []
    assert patches


def test_copy_dry_run_does_not_write(tmp_path: Path):
    media = tmp_path / "Dark.S01E01.mkv"
    media.write_bytes(b"")
    (tmp_path / "Dark.S01E01.en.srt").write_text("hi")
    dest = tmp_path / "subs"
    dest.mkdir()
    job = SimpleNamespace(
        id="j1",
        index=0,
        input=SimpleNamespace(value=str(media), data={}),
        plugins={},
    )
    services = SimpleNamespace(
        jobid="j1",
        run_safety={"dry_run": True, "hardlink": False, "no_delete": True},
        update_state=lambda *a, **k: None,
    )
    result = SubtitlePlugin({"output_dir": str(dest), "copy": True}).execute(job, services)
    assert result.success
    assert result.data["copied"][0]["op"] == "skip"
    assert not list(dest.iterdir())
