"""
Run Router - Simple subprocess-based execution
"""

import subprocess
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Project root - where config.yml is
PROJECT_ROOT = Path("/home/samet/Workspace/archiverr")


class RunResponse(BaseModel):
    execution_id: str
    success: bool
    total_matches: int
    completed_matches: int
    failed_matches: int
    duration_ms: int
    error: Optional[str] = None
    api_response: Optional[Dict[str, Any]] = None


@router.post("/", response_model=RunResponse)
def run_default():
    """Run archiverr - subprocess based, no async issues"""
    
    start_time = time.time()
    
    # Check config exists
    config_path = PROJECT_ROOT / "config.yml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"config.yml not found at {config_path}")
    
    try:
        # Run archiverr as subprocess - EXACTLY like CLI
        result = subprocess.run(
            ['python', '-m', 'archiverr'],
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if result.returncode != 0:
            return RunResponse(
                execution_id="error",
                success=False,
                total_matches=0,
                completed_matches=0,
                failed_matches=0,
                duration_ms=duration_ms,
                error=result.stderr[:500] if result.stderr else "Process failed"
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
                with open(report_files[0], 'r') as f:
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
