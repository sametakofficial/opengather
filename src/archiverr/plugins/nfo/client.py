"""NFO plugin — write a sidecar next to the media file via safe_write."""

from datetime import datetime
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult
from archiverr.core.safety import safe_write

from .builder import build_nfo, pick_entity


class NfoPlugin(OutputPlugin):
    """OUTPUT stage. Plans or writes ``{stem}.nfo`` from resolved metadata."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "nfo"
        self.output_dir = str(config.get("output_dir") or "").strip()
        self.overwrite = bool(config.get("overwrite", False))

    def execute(self, job: Any, services: Any) -> PluginResult:
        started_at = datetime.now()
        dry_run = bool((getattr(services, "run_safety", None) or {}).get("dry_run", True))

        source = job.input.value if hasattr(job.input, "value") else str(job.input)
        if not source:
            return PluginResult.skipped_result("no input path", started_at=started_at)

        plugins = getattr(job, "plugins", None) or {}
        envelope = None
        if hasattr(services, "read_state"):
            try:
                envelope = services.read_state("data")
            except Exception:  # noqa: BLE001 — envelope is optional
                envelope = None

        picked = pick_entity(plugins, envelope, getattr(job, "index", None))
        if not picked:
            return PluginResult.skipped_result("no show/movie entity", started_at=started_at)

        category, entity = picked
        xml = build_nfo(category, entity)
        target = self._target_path(source)

        planned = safe_write(
            target,
            xml,
            dry_run=dry_run,
            overwrite=self.overwrite,
        )

        payload = {
            "category": category,
            "path": str(target),
            "xml": xml,
            "dry_run": dry_run,
            "planned": planned.to_dict(),
        }
        if services.jobid:
            services.update_state({
                "jobs": {services.jobid: {"plugins": {self.name: payload}}},
            })

        if planned.op == "error":
            return PluginResult.error_result(planned.reason, started_at=started_at)
        return PluginResult.success_result(data=payload, started_at=started_at)

    def _target_path(self, source: str) -> Path:
        src = Path(source)
        if self.output_dir:
            return Path(self.output_dir) / f"{src.stem}.nfo"
        return src.with_suffix(".nfo")
