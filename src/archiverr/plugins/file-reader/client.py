"""File Reader Plugin - Read paths from .txt file"""
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import InputPlugin


class FileReaderPlugin(InputPlugin):
    """Input plugin that reads file paths from a text file.

    per_run mode: implements execute_run(services) protocol.
    Creates jobs via services.create_job() for each path found.
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # Session 38 A8 fix: previously "file_reader" (underscore) but the
        # manifest declares "file-reader" (kebab-case). The registry indexes
        # by manifest.name, so any internal log keyed off self.name was
        # diverging from the canonical plugin id.
        self.name = "file-reader"

    def execute_run(self, services: Any) -> dict[str, Any]:
        """
        Read paths from text file(s) and create jobs.

        Args:
            services: PluginServices instance

        Returns:
            dict with count of jobs created (key ``count`` mirrors scanner
            so per_run_executor's ``result.get('count', 0)`` summary
            reflects reality — Session 38 A10).
        """
        targets = self.config.get('targets', [])
        allow_virtual = self.config.get('allow_virtual_paths', False)

        self.debug("Reading targets", targets=len(targets), allow_virtual=allow_virtual)

        paths_found = []
        for target in targets:
            if target.endswith('.txt'):
                target_path = Path(target)
                if not target_path.exists():
                    self.warn("Target file not found", path=str(target_path))
                    continue

                self.debug("Reading file", path=str(target_path))

                with open(target_path, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            path_exists = Path(line).exists()
                            is_virtual = not path_exists

                            if not allow_virtual and is_virtual:
                                continue

                            paths_found.append({
                                'path': line,
                                'virtual': is_virtual
                            })
            else:
                path_exists = Path(target).exists()
                is_virtual = not path_exists

                if not allow_virtual and is_virtual:
                    continue

                self.debug("Direct path", path=target, virtual=is_virtual)
                paths_found.append({
                    'path': target,
                    'virtual': is_virtual
                })

        # Create jobs via services
        for path_info in paths_found:
            services.create_job(
                input_value=path_info['path'],
                input_data={'virtual': path_info['virtual']}
            )

        count = len(paths_found)
        self.info("Reading complete", found=count)

        # Session 38 A9 fix: previously file-reader skipped update_plugin,
        # leaving plugin.file-reader.data empty downstream. Mirroring scanner.
        services.update_plugin(
            target_id=services.run_id,
            plugin_name="file-reader",
            data={
                "count": count,
                "targets": targets,
                "allow_virtual_paths": allow_virtual,
            },
        )

        return {'count': count}

    def execute(self) -> list[dict[str, Any]]:
        """Per_run plugins use ``execute_run(services)``; this stub exists
        only because :class:`InputPlugin` declares ``execute`` as abstract.

        Calling it is a contract violation — the orchestrator dispatches
        on ``run_mode``. Session 38 B3: replaced the legacy warn-and-return
        path with an explicit error matching scanner's pattern.
        """
        raise NotImplementedError(
            "file-reader is per_run; call execute_run(services) instead"
        )
