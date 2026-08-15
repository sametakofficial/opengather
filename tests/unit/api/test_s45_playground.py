"""S45: run.data on RunResponse, reconstruct helpers, Jinja playground."""

from archiverr.api.v1.render.reconstruct import intify_digit_keys, job_from_doc, run_from_doc
from archiverr.api.v1.render.service import render_template
from archiverr.api.v1.runs.schemas import RunResponse


def _run_doc():
    return {
        "id": "abc",
        "status": {"state": "success", "success": True, "total_jobs": 1, "completed": 1, "failed": 0},
        "config": {"options": {"dry_run": True}},
        "data": {
            "0": {
                "show": {
                    "title": {"primary": "Breaking Bad"},
                    "identifiers": {"tmdb_id": "1396"},
                }
            }
        },
        "plugins": {},
    }


def _job_doc():
    return {
        "id": "job-abc-0",
        "run_id": "abc",
        "index": 0,
        "input": {"value": "/tmp/Breaking.Bad.S01E01.mkv", "data": {}},
        "output": {"values": [], "data": {}},
        "status": {"state": "success", "success": True, "plugins": {}},
        "plugins": {
            "renamer": {
                "category": "show",
                "parsed": {"show": {"name": "Breaking Bad", "season": 1, "episode": 1}},
            },
            "tmdb": {
                "show": {
                    "title": {"primary": "Breaking Bad"},
                    "identifiers": {"tmdb_id": "1396"},
                    "episode_title": "Pilot",
                }
            },
        },
    }


def test_run_response_carries_data_envelope():
    resp = RunResponse(id="abc", data={"0": {"show": {"title": {"primary": "Breaking Bad"}}}})
    dumped = resp.model_dump()
    assert dumped["data"]["0"]["show"]["title"]["primary"] == "Breaking Bad"


def test_intify_digit_keys():
    out = intify_digit_keys({"0": {"show": {"x": 1}}, "run": {}})
    assert 0 in out
    assert out[0]["show"]["x"] == 1
    assert "run" in out


def test_render_data_namespace():
    result = render_template(
        "{{ data[0].show.title.primary }} #{{ data[0].show.identifiers.tmdb_id }}",
        _run_doc(),
        [_job_doc()],
        job_index=0,
    )
    assert result["error"] is False
    assert result["rendered"] == "Breaking Bad #1396"
    assert result["job_id"] == "job-abc-0"


def test_render_jobs_plugin_path():
    result = render_template(
        "{{ jobs[job_id].plugins.tmdb.show.episode_title }}",
        _run_doc(),
        [_job_doc()],
        job_id="job-abc-0",
    )
    assert result["rendered"] == "Pilot"


def test_render_missing_path_is_empty():
    result = render_template(
        "{{ jobs[job_id].plugins.missing.field }}",
        _run_doc(),
        [_job_doc()],
    )
    assert result["error"] is False
    assert result["rendered"] == ""


def test_reconstruct_job_and_run():
    job = job_from_doc(_job_doc())
    run = run_from_doc(_run_doc())
    assert job.index == 0
    assert job.plugins["renamer"]["category"] == "show"
    assert 0 in run.data
    assert run.data[0]["show"]["title"]["primary"] == "Breaking Bad"
