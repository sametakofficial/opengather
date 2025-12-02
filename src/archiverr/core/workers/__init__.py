"""
Workers Module - Task Queue Integration

Provides async task execution using Taskiq + MongoDB.
Replaces subprocess-based execution for better scalability.

Usage:
    from archiverr.core.workers import broker, run_execution
    
    # Queue an execution
    task = await run_execution.kiq(config, targets)
    
    # Wait for result
    result = await task.wait_result()
"""

from .broker import broker
from .tasks import run_execution

__all__ = ['broker', 'run_execution']
