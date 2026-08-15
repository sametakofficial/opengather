"""Config (read) + Jinja playground. No writes. No plugin invoke."""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from archiverr.api.deps import DatabaseDep
from archiverr.utils.config_loader import mask_sensitive_fields

from .schemas import ConfigResponse, RenderRequest, RenderResponse
from .service import render_template

try:
    from pymongo.errors import OperationFailure, PyMongoError
except ImportError:  # pragma: no cover
    OperationFailure = Exception
    PyMongoError = Exception

router = APIRouter()


def _load_live_config() -> tuple[dict, str]:
    path = Path("config.yml")
    if not path.exists():
        raise HTTPException(status_code=404, detail="config.yml not found")
    raw = path.read_text(encoding="utf-8")
    original = yaml.safe_load(raw) or {}
    if not isinstance(original, dict):
        original = {}
    masked = mask_sensitive_fields(original, original)
    text = yaml.safe_dump(masked, sort_keys=False, allow_unicode=True)
    return masked, text


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Masked live ``config.yml``. Secrets stay as ``${ENV}``. Not writable."""
    config, text = _load_live_config()
    return ConfigResponse(path="config.yml", writable=False, config=config, text=text)


async def _find_run(db, run_id: str) -> dict:
    ids = [run_id]
    if not run_id.startswith("run_"):
        ids.append(f"run_{run_id}")
    for variant in ids:
        doc = await db["runs"].find_one({"id": variant})
        if doc:
            return doc
    raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")


async def _jobs_for_run(db, run_id: str) -> list[dict]:
    variants = [run_id]
    if not run_id.startswith("run_"):
        variants.append(f"run_{run_id}")
    for variant in variants:
        cursor = db["jobs"].find({"run_id": variant}).sort("index", 1)
        docs = await cursor.to_list(length=500)
        if docs:
            return docs
    return []


@router.post("/render", response_model=RenderResponse)
async def post_render(body: RenderRequest, db: DatabaseDep):
    """Render a Jinja template against a persisted run/job.

    Same engine and context as tasker. Does not start a run, invoke a
    plugin, or write files.
    """
    try:
        run_doc = await _find_run(db, body.run_id)
        job_docs = await _jobs_for_run(db, run_doc.get("id") or body.run_id)
        result = render_template(
            body.template,
            run_doc,
            job_docs,
            job_id=body.job_id,
            job_index=body.job_index,
        )
        return RenderResponse(**result)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationFailure as exc:
        raise HTTPException(status_code=500, detail=f"Database operation failed: {exc}") from exc
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {exc}") from exc
