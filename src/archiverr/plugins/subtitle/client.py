"""Subtitle plugin — discover sidecars; optionally copy via safe_copy."""

from datetime import datetime
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult
from archiverr.core.safety import safe_copy

from .discover import discover_sidecars, normalize_extensions


class SubtitlePlugin(OutputPlugin):
    """OUTPUT stage. Lists sidecar tracks next to the media file."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "subtitle"
        self.extensions = normalize_extensions(config.get("extensions"))
        self.output_dir = str(config.get("output_dir") or "").strip()
        self.copy = bool(config.get("copy", False))

    def execute(self, job: Any, services: Any) -> PluginResult:
        started_at = datetime.now()
        dry_run = bool((getattr(services, "run_safety", None) or {}).get("dry_run", True))
        hardlink = bool((getattr(services, "run_safety", None) or {}).get("hardlink", False))

        source = job.input.value if hasattr(job.input, "value") else str(job.input)
        if not source:
            return PluginResult.skipped_result("no input path", started_at=started_at)

        tracks = discover_sidecars(source, self.extensions)
        planned: list[dict[str, Any]] = []

        if self.copy and self.output_dir:
            dest_dir = Path(self.output_dir)
            for track in tracks:
                dest = dest_dir / Path(track["path"]).name
                result = safe_copy(
                    track["path"],
                    dest,
                    hardlink=hardlink,
                    dry_run=dry_run,
                    overwrite=False,
                )
                planned.append(result.to_dict())
                track["destination"] = str(dest)
                track["planned"] = result.to_dict()

        payload = {
            "count": len(tracks),
            "tracks": tracks,
            "dry_run": dry_run,
            "copied": planned,
        }
        if services.jobid:
            services.update_state({
                "jobs": {services.jobid: {"plugins": {self.name: payload}}},
            })
        return PluginResult.success_result(data=payload, started_at=started_at)
