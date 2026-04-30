"""
Run Router - Simple subprocess-based execution
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from .schemas import RunRequest

logger = logging.getLogger(__name__)
router = APIRouter()

# Project root - where config.yml is (dynamically determined)
# Go up from: src/archiverr/api/v1/run/router.py -> project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent


class RunResponse(BaseModel):
    execution_id: str
    success: bool
    total_matches: int
    completed_matches: int
    failed_matches: int
    duration_ms: int
    error: str | None = None
    api_response: dict[str, Any] | None = None


@router.post("/", response_model=RunResponse)
def run_default(request: RunRequest = Body(None)):
    """Run archiverr with optional custom config - FLEXIBLE!"""

    start_time = time.time()

    # Default config path
    config_path = PROJECT_ROOT / "config.yml"
    temp_config_file = None

    # If custom config provided, use it!
    if request and request.config_override:
        try:
            # Load default config
            with open(config_path) as f:
                base_config = yaml.safe_load(f)

            # Merge with override (override wins!)
            base_config.update(request.config_override)

            # Create temp config file
            temp_config_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.yml',
                prefix='archiverr_api_',
                dir=str(PROJECT_ROOT),
                delete=False
            )
            yaml.dump(base_config, temp_config_file, default_flow_style=False)
            temp_config_file.close()

            config_path = Path(temp_config_file.name)
        except Exception as e:
            if temp_config_file:
                try:
                    os.unlink(temp_config_file.name)
                except OSError:
                    pass
            raise HTTPException(status_code=400, detail=f"Failed to process custom config: {str(e)}")

    # Check config exists
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"config.yml not found at {config_path}")

    try:
        # Run archiverr as subprocess - EXACTLY like CLI
        cmd = [sys.executable, '-m', 'archiverr']

        # Pass config path if we're using a temp config
        if temp_config_file:
            cmd.extend(['--config', str(config_path)])

        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=300
        )

        duration_ms = int((time.time() - start_time) * 1000)

        if result.returncode != 0:
            # AGENT.md §5: no silent failures. Log full stderr; truncate only the
            # response body for client convenience.
            full_stderr = result.stderr or ""
            full_stdout = result.stdout or ""
            logger.error(
                "Subprocess archiverr run failed (returncode=%s, duration_ms=%s)\n"
                "STDERR (full):\n%s\nSTDOUT (full):\n%s",
                result.returncode, duration_ms, full_stderr, full_stdout,
            )
            return RunResponse(
                execution_id="error",
                success=False,
                total_matches=0,
                completed_matches=0,
                failed_matches=0,
                duration_ms=duration_ms,
                error=(full_stderr[:500] if full_stderr else "Process failed")
            )

        # Read latest report
        reports_dir = PROJECT_ROOT / "reports"
        if reports_dir.exists():
            report_files = sorted(
                reports_dir.glob("api_response_full_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            if report_files:
                with open(report_files[0]) as f:
                    api_response = json.load(f)

                globals_data = api_response.get('globals', {})
                status = globals_data.get('status', {})

                return RunResponse(
                    execution_id=globals_data.get('execution_id', 'ok'),
                    success=status.get('success', True),
                    total_matches=status.get('matches', 0),
                    completed_matches=status.get('matches', 0),
                    failed_matches=status.get('errors', 0),
                    duration_ms=duration_ms,
                    api_response=api_response
                )

        return RunResponse(
            execution_id="ok",
            success=True,
            total_matches=0,
            completed_matches=0,
            failed_matches=0,
            duration_ms=duration_ms
        )

    except subprocess.TimeoutExpired:
        return RunResponse(
            execution_id="timeout",
            success=False,
            total_matches=0,
            completed_matches=0,
            failed_matches=0,
            duration_ms=300000,
            error="Timeout after 300 seconds"
        )
    except Exception as e:
        return RunResponse(
            execution_id="error",
            success=False,
            total_matches=0,
            completed_matches=0,
            failed_matches=0,
            duration_ms=int((time.time() - start_time) * 1000),
            error=str(e)
        )
    finally:
        # Cleanup temp config
        if temp_config_file and Path(temp_config_file.name).exists():
            try:
                os.unlink(temp_config_file.name)
            except OSError:
                pass
