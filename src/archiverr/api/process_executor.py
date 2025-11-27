"""
Process-based Execution

Runs archiverr execution in isolated subprocess to avoid event loop conflicts.
This is the industry-standard approach for mixing async frameworks with sync code.

Why subprocess?
- FastAPI uses uvloop/asyncio event loop
- MongoDB Motor creates its own event loop
- These conflict when run in same process
- Subprocess provides complete isolation

Similar to how Celery, RQ, Dramatiq handle background tasks.

IMPORTANT: This module intentionally has minimal imports to avoid
triggering any asyncio event loop creation when loaded.
"""

# MINIMAL IMPORTS - avoid any module that might start an event loop
import subprocess
import json
import tempfile
import os
import time
from pathlib import Path


class ProcessExecutionResult:
    """Result from subprocess execution - plain class, no dataclass to avoid imports"""
    __slots__ = ['execution_id', 'success', 'total_matches', 'completed_matches', 
                 'failed_matches', 'duration_ms', 'error', 'api_response']
    
    def __init__(
        self,
        execution_id: str,
        success: bool,
        total_matches: int,
        completed_matches: int,
        failed_matches: int,
        duration_ms: int,
        error: str = None,
        api_response: dict = None
    ):
        self.execution_id = execution_id
        self.success = success
        self.total_matches = total_matches
        self.completed_matches = completed_matches
        self.failed_matches = failed_matches
        self.duration_ms = duration_ms
        self.error = error
        self.api_response = api_response


def run_archiverr_process(
    config: dict,
    targets: list = None,
    timeout: int = 300
) -> ProcessExecutionResult:
    """
    Run archiverr in subprocess - completely isolated from FastAPI's event loop.
    
    This mirrors exactly what happens when user runs `python -m archiverr`
    
    Args:
        config: Configuration dictionary
        targets: Optional target overrides
        timeout: Max execution time in seconds
        
    Returns:
        ProcessExecutionResult with execution details
    """
    # Import yaml here to avoid any early imports
    import yaml
    
    start_time = time.time()
    
    # Get the project root (where config.yml is)
    project_root = Path(__file__).parent.parent.parent.parent.parent
    
    # Create temporary config file with overrides
    temp_config_path = None
    try:
        # Apply target overrides if provided
        if targets:
            for plugin_name in ['scanner', 'file_reader', 'file-reader']:
                if plugin_name in config.get('plugins', {}):
                    config['plugins'][plugin_name]['targets'] = targets
            
            # Write temp config
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.yml', 
                delete=False,
                prefix='archiverr_api_',
                dir=str(project_root)
            ) as f:
                yaml.dump(config, f)
                temp_config_path = f.name
        
        # Build environment - inherit current env
        env = os.environ.copy()
        
        # Run archiverr as subprocess
        # This is EXACTLY like running `python -m archiverr` from terminal
        result = subprocess.run(
            ['python', '-m', 'archiverr'],
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Check for errors
        if result.returncode != 0:
            return ProcessExecutionResult(
                execution_id="error",
                success=False,
                total_matches=0,
                completed_matches=0,
                failed_matches=0,
                duration_ms=duration_ms,
                error=result.stderr[:500] if result.stderr else "Process failed"
            )
        
        # Find latest report file
        reports_dir = project_root / "reports"
        if reports_dir.exists():
            report_files = sorted(
                reports_dir.glob("api_response_full_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            if report_files:
                with open(report_files[0], 'r') as f:
                    api_response = json.load(f)
                
                # Extract execution info
                globals_data = api_response.get('globals', {})
                status = globals_data.get('status', {})
                
                return ProcessExecutionResult(
                    execution_id=globals_data.get('execution_id', 'unknown'),
                    success=status.get('success', True),
                    total_matches=status.get('matches', 0),
                    completed_matches=status.get('matches', 0),
                    failed_matches=status.get('errors', 0),
                    duration_ms=duration_ms,
                    api_response=api_response
                )
        
        # No report found but process succeeded
        return ProcessExecutionResult(
            execution_id="completed",
            success=True,
            total_matches=0,
            completed_matches=0,
            failed_matches=0,
            duration_ms=duration_ms
        )
        
    except subprocess.TimeoutExpired:
        return ProcessExecutionResult(
            execution_id="timeout",
            success=False,
            total_matches=0,
            completed_matches=0,
            failed_matches=0,
            duration_ms=timeout * 1000,
            error=f"Execution timed out after {timeout} seconds"
        )
    except Exception as e:
        return ProcessExecutionResult(
            execution_id="error",
            success=False,
            total_matches=0,
            completed_matches=0,
            failed_matches=0,
            duration_ms=int((time.time() - start_time) * 1000),
            error=str(e)
        )
    finally:
        # Cleanup temp config file
        if temp_config_path:
            try:
                os.unlink(temp_config_path)
            except:
                pass
