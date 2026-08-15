"""NfoPlugin execute: dry_run plans a write, live write uses safe_write."""

from pathlib import Path
from types import SimpleNamespace

from archiverr.plugins.nfo.client import NfoPlugin


def _job(tmp_path: Path, name="Inception.2010.mkv"):
    media = tmp_path / name
    media.write_bytes(b"")
    return SimpleNamespace(
        id="job-1",
        index=0,
        input=SimpleNamespace(value=str(media), data={"filesystem": True}),
        plugins={
            "renamer": {
                "category": "movie",
                "parsed": {"movie": {"name": "Inception", "year": 2010}},
            },
            "tmdb": {
                "movie": {
                    "title": {"primary": "Inception"},
                    "identifiers": {"tmdb_id": "27205"},
                    "release": {"year": 2010},
                }
            },
        },
    )


def _services(*, dry_run=True, jobid="job-1", envelope=None):
    patches = []

    def update_state(patch, mode="merge"):
        patches.append(patch)

    return SimpleNamespace(
        jobid=jobid,
        run_safety={"dry_run": dry_run, "hardlink": False, "no_delete": True},
        read_state=lambda path=None: envelope if path == "data" else None,
        update_state=update_state,
        patches=patches,
    )


def test_dry_run_does_not_write(tmp_path: Path):
    job = _job(tmp_path)
    services = _services(dry_run=True)
    result = NfoPlugin({}).execute(job, services)
    assert result.success
    target = Path(job.input.value).with_suffix(".nfo")
    assert not target.exists()
    assert result.data["planned"]["op"] == "skip"
    assert result.data["planned"]["dry_run"] is True
    assert "<title>Inception</title>" in result.data["xml"]
    assert services.patches


def test_live_write_creates_sidecar(tmp_path: Path):
    job = _job(tmp_path)
    services = _services(dry_run=False)
    result = NfoPlugin({"overwrite": True}).execute(job, services)
    target = Path(job.input.value).with_suffix(".nfo")
    assert result.success
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "<movie>" in text
    assert "27205" in text


def test_output_dir_redirects(tmp_path: Path):
    dest = tmp_path / "out"
    dest.mkdir()
    job = _job(tmp_path)
    services = _services(dry_run=False)
    NfoPlugin({"output_dir": str(dest), "overwrite": True}).execute(job, services)
    written = dest / "Inception.2010.nfo"
    assert written.exists()
    assert not Path(job.input.value).with_suffix(".nfo").exists()


def test_skip_when_no_entity(tmp_path: Path):
    job = _job(tmp_path)
    job.plugins = {}
    result = NfoPlugin({}).execute(job, _services())
    assert result.success
    assert result.metadata.get("skipped") is True
