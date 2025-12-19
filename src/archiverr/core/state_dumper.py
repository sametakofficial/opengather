"""
StateDumper - Handles state persistence to JSON files.

Extracted from Orchestrator for Single Responsibility Principle.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from archiverr.state.manager import GlobalStateManager
    from archiverr.utils.debug import Debugger


class StateDumper:
    """Dumps run state to JSON files for debugging and analysis."""

    def __init__(self, output_dir: str = "output", debugger: 'Debugger' = None):
        self._output_dir = Path(output_dir)
        self._debugger = debugger

    def dump(self, run_id: str, state: 'GlobalStateManager') -> Path | None:
        """
        Dump complete global state to output folder.
        
        Args:
            run_id: Current run ID
            state: GlobalStateManager instance
            
        Returns:
            Path to dumped file or None on failure
        """
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)

            run = state.run
            if not run:
                return None

            run_dict = run.to_dict() if hasattr(run, 'to_dict') else {}

            jobs_dict = {}
            for job in state.get_all_jobs():
                job_dict = job.to_dict() if hasattr(job, 'to_dict') else {
                    "id": job.id,
                    "index": job.index,
                    "input": {"value": job.input.value, "data": job.input.data} if hasattr(job, 'input') else {},
                    "output": {"values": job.output.values, "data": job.output.data} if hasattr(job, 'output') else {},
                    "status": job.status.to_dict() if hasattr(job.status, 'to_dict') else {},
                    "plugins": job.plugins if hasattr(job, 'plugins') else {}
                }
                jobs_dict[job.id] = job_dict

            plugins_data = {}
            if hasattr(state, 'plugins') and isinstance(state.plugins, dict):
                plugins_data = dict(state.plugins)

            # Include run-level plugin data
            if hasattr(run, 'plugins') and isinstance(run.plugins, dict) and run.plugins:
                run_target_id = f"run_{run.id}" if not str(run.id).startswith("run_") else str(run.id)
                plugins_data.setdefault(run_target_id, {}).update(run.plugins)

            # Include job plugin data
            for job in state.get_all_jobs():
                if hasattr(job, 'plugins') and isinstance(job.plugins, dict) and job.plugins:
                    plugins_data.setdefault(job.id, {}).update(job.plugins)

            state_dump = {
                "dump_type": "global_state",
                "timestamp": datetime.now().isoformat(),
                "run": run_dict,
                "jobs": jobs_dict,
                "plugins": plugins_data
            }

            filename = f"run_{run_id}_state.json"
            filepath = self._output_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state_dump, f, indent=2, ensure_ascii=False, default=str)

            self._log("info", f"Global state dumped: {filepath}")
            return filepath

        except (OSError, IOError) as e:
            self._log("warn", f"Failed to dump global state: {e}")
            return None

    def _log(self, level: str, message: str) -> None:
        """Log with debugger if available."""
        if self._debugger:
            log_func = getattr(self._debugger, level, self._debugger.info)
            log_func("state_dumper", message)
