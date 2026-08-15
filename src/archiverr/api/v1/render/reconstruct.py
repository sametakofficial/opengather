"""Rebuild in-memory run/job objects from persisted Mongo docs.

API-only. Core models stay the source of truth; this is the persistence
edge going the other way so ``ConfigRenderEngine`` can use the same
template context as tasker.
"""

from __future__ import annotations

from typing import Any

from archiverr.state.models import (
    InputData,
    JobState,
    JobStatus,
    OutputData,
    RunState,
    StateEnum,
)


def intify_digit_keys(value: Any) -> Any:
    """Undo G1 stringification so ``data[0].show`` works in Jinja."""
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            new_key: Any = key
            if isinstance(key, str) and key.isdigit():
                new_key = int(key)
            out[new_key] = intify_digit_keys(item)
        return out
    if isinstance(value, list):
        return [intify_digit_keys(item) for item in value]
    return value


def _enum(value: Any, default: StateEnum = StateEnum.PENDING) -> StateEnum:
    if isinstance(value, StateEnum):
        return value
    try:
        return StateEnum(str(value))
    except ValueError:
        return default


def job_from_doc(doc: dict[str, Any]) -> JobState:
    incoming = doc.get("input") or {}
    outgoing = doc.get("output") or {}
    values = outgoing.get("values")
    if isinstance(values, dict):
        values = list(values.values())
    status_doc = doc.get("status") or {}
    job = JobState(
        index=int(doc.get("index") or 0),
        run_id=str(doc.get("run_id") or ""),
        id=str(doc.get("id") or ""),
        input=InputData(
            value=str(incoming.get("value") or ""),
            data=incoming.get("data") or {},
        ),
        output=OutputData(
            values=list(values or []),
            data=outgoing.get("data") or {},
        ),
        plugins=doc.get("plugins") or {},
    )
    job.status = JobStatus(
        state=_enum(status_doc.get("state")),
        success=bool(status_doc.get("success", True)),
        plugins=status_doc.get("plugins") or {},
        duration_ms=int(status_doc.get("duration_ms") or 0),
    )
    return job


def run_from_doc(doc: dict[str, Any]) -> RunState:
    status_doc = doc.get("status") or {}
    run = RunState(id=str(doc.get("id") or ""))
    run.config = doc.get("config") or {}
    run.plugins = doc.get("plugins") or {}
    run.data = intify_digit_keys(doc.get("data") or {})
    run.persistence_mode = str(doc.get("persistence_mode") or "degraded")
    run.status.success = bool(status_doc.get("success", True))
    run.status.total_jobs = int(status_doc.get("total_jobs") or 0)
    run.status.completed = int(status_doc.get("completed") or 0)
    run.status.failed = int(status_doc.get("failed") or 0)
    run.status.duration_ms = int(status_doc.get("duration_ms") or 0)
    run.status.state = _enum(status_doc.get("state"), StateEnum.SUCCESS)
    return run
