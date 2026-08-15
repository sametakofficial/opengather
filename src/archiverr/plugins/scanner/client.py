"""
Scanner Plugin - File/Directory Discovery

Per-run input plugin that discovers media files from configured targets.
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import InputPlugin

DEFAULT_EXTENSIONS = ['.mkv', '.mp4', '.avi', '.m4v', '.ts']


class ScannerPlugin(InputPlugin):
    """Input plugin that discovers media files from configured targets."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "scanner"

    def execute(self) -> list[dict[str, Any]]:
        """
        Abstract method implementation - not used directly.
        Scanner uses execute_run() which is called by orchestrator.
        """
        raise NotImplementedError("Scanner uses execute_run() instead")

    def execute_run(self, services: Any) -> dict[str, Any]:
        """Execute scanner - discovers files and creates jobs."""
        # S39 R15 §H4b: read live (template-rendered) config via services
        # so config authors can use ``${env:...}``, ``${.field}`` and
        # Jinja markers in scanner.targets / scanner.extensions etc. The
        # frozen ``self.config`` (set at registry load time) is the
        # fallback when services hasn't wired a render engine.
        runtime_config = self._get_effective_config(services)
        targets = runtime_config.get('targets', [])
        recursive = runtime_config.get('recursive', True)
        allow_virtual = runtime_config.get('allow_virtual_paths', False)
        extensions = runtime_config.get('extensions', DEFAULT_EXTENSIONS)

        self.debug("Starting scan", targets=len(targets), recursive=recursive)

        created_jobs = 0

        for target in targets:
            self.info("Scanning target", path=target)

            if target.endswith('.txt'):
                continue

            # Security: Validate and sanitize path
            try:
                target_path = Path(target).resolve()
                # Prevent path traversal attacks
                if '..' in str(target_path):
                    self.warn("Path traversal detected, skipping", path=target)
                    continue
            except (ValueError, OSError) as e:
                self.warn("Invalid path, skipping", path=target, error=str(e))
                continue

            if target_path.is_file():
                self._create_job_for_file(services, target_path)
                created_jobs += 1

            elif target_path.is_dir() and recursive:
                for ext in extensions:
                    for file in target_path.rglob(f'*{ext}'):
                        if file.is_file():
                            self._create_job_for_file(services, file)
                            created_jobs += 1

            elif allow_virtual and not target_path.exists():
                self._create_job_for_virtual(services, target)
                created_jobs += 1

        self.info("Scan complete", jobs_created=created_jobs)

        services.update_state({
            "plugins": {
                self.name: {
                    "count": created_jobs,
                    "targets": targets,
                    "recursive": recursive,
                    "allow_virtual_paths": allow_virtual,
                }
            }
        })

        return {
            'success': True,
            'count': created_jobs
        }

    def _get_effective_config(self, services: Any) -> dict[str, Any]:
        """Return rendered runtime config with frozen-config fallback.

        Tries ``services.get_runtime_config()`` first (S39 R15 §H3 — live
        Jinja-rendered view). Falls back to the frozen plugin config
        passed at construction when services hasn't wired a render
        engine (test fixtures / stub paths). Either branch returns a
        dict; we never raise on missing config.
        """
        if hasattr(services, "get_runtime_config"):
            try:
                rendered = services.get_runtime_config()
                if isinstance(rendered, dict) and rendered:
                    return rendered
            except Exception as exc:  # noqa: BLE001 — fall back, don't crash
                self.debug("get_runtime_config fallback", error=str(exc))
        return self.config or {}

    def _create_job_for_file(self, services: Any, file_path: Path) -> None:
        """Create a job for a filesystem file."""
        stat = file_path.stat()
        input_data = {
            'source': 'scanner',
            'filename': file_path.name,
            'extension': file_path.suffix.lstrip('.'),
            'size_bytes': stat.st_size,
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'filesystem': True
        }
        services.create_job(input_value=str(file_path), input_data=input_data)

    def _create_job_for_virtual(self, services: Any, path: str) -> None:
        """Create a job for a virtual path."""
        input_data = {
            'source': 'scanner',
            'filename': Path(path).name,
            'extension': Path(path).suffix.lstrip('.') if '.' in path else '',
            'size_bytes': 0,
            'modified_at': None,
            'filesystem': False,
            'virtual': True
        }
        services.create_job(input_value=path, input_data=input_data)

