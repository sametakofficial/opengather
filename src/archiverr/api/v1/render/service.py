"""Render a Jinja template against a persisted run/job (S45).

Uses the same ``TemplateContextBuilder`` + ``ConfigRenderEngine`` path
as tasker. Does not invoke plugins. Does not write disk.
"""

from __future__ import annotations

from typing import Any

from archiverr.core.render import ConfigRenderEngine
from archiverr.state.template_context import TemplateContextBuilder

from .reconstruct import job_from_doc, run_from_doc


def render_template(
    template: str,
    run_doc: dict[str, Any],
    job_docs: list[dict[str, Any]],
    *,
    job_id: str | None = None,
    job_index: int | None = None,
) -> dict[str, Any]:
    if not template:
        raise ValueError("template is empty")

    jobs = [job_from_doc(doc) for doc in job_docs]
    if not jobs:
        raise ValueError("run has no jobs")

    current = None
    if job_id:
        current = next((job for job in jobs if job.id == job_id), None)
    if current is None and job_index is not None:
        current = next((job for job in jobs if job.index == job_index), None)
    if current is None:
        current = jobs[0]

    run = run_from_doc(run_doc)
    context = TemplateContextBuilder().build_job_context(
        current, run=run, all_jobs=jobs, events={},
    )
    rendered = ConfigRenderEngine().render_string(template, context)
    return {
        "rendered": rendered,
        "run_id": run.id,
        "job_id": current.id,
        "job_index": current.index,
        "error": rendered.startswith("Template error:"),
    }
