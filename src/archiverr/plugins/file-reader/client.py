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
        self.name = "file_reader"

    def execute_run(self, services: Any) -> dict[str, Any]:
        """
        Read paths from text file(s) and create jobs.

        Args:
            services: PluginServices instance

        Returns:
            dict with count of jobs created
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

        self.info("Reading complete", found=len(paths_found))
        return {'jobs_created': len(paths_found)}

    def execute(self) -> list[dict[str, Any]]:
        """Legacy execute -- kept for backward compatibility but should not be called."""
        self.warn("Legacy execute() called on file_reader -- use execute_run(services) instead")
        return []
