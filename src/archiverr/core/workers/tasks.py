"""
Task Definitions - Async tasks for background execution

Defines tasks that can be queued and executed asynchronously.

Usage:
    # Queue a task
    task = await run_execution.kiq(config, targets)
    
    # Get result
    result = await task.wait_result()
    
    # Or stream progress
    async for progress in stream_execution(config, targets):
        print(progress)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


# Note: Tasks are decorated with @broker.task
# But since broker is lazy-loaded, we define tasks as regular functions
# and register them when broker is initialized


async def run_execution_task(
    config: Dict[str, Any],
    targets: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run media processing execution as a background task.
    
    Args:
        config: Full configuration dictionary
        targets: Optional list of targets to process (overrides config)
        
    Returns:
        ExecutionResult as dictionary
    """
    from archiverr.core.services.execution_service import ExecutionService
    
    service = ExecutionService()
    result = await service.run_execution_async(config, targets)
    
    return {
        "execution_id": result.execution_id,
        "success": result.success,
        "total_matches": result.total_matches,
        "completed_matches": result.completed_matches,
        "failed_matches": result.failed_matches,
        "duration_ms": result.duration_ms,
        "error": result.error
    }


def register_tasks(broker):
    """
    Register tasks with the broker.
    
    Called after broker initialization.
    
    Args:
        broker: Initialized MongoDBBroker instance
    """
    global run_execution
    
    # Register the task with decorator
    run_execution = broker.task(run_execution_task)
    
    return {
        "run_execution": run_execution
    }


# Placeholder - will be set by register_tasks()
run_execution = None


# ============== Task Status Helpers ==============

async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get status of a queued task.
    
    Args:
        task_id: Task ID returned when task was queued
        
    Returns:
        Task status dict with state, result, error
    """
    from .broker import get_broker
    
    broker = get_broker()
    result = await broker.result_backend.get_result(task_id)
    
    if result is None:
        return {
            "task_id": task_id,
            "status": "pending",
            "result": None,
            "error": None
        }
    
    if result.is_err:
        return {
            "task_id": task_id,
            "status": "failed",
            "result": None,
            "error": str(result.error)
        }
    
    return {
        "task_id": task_id,
        "status": "completed",
        "result": result.return_value,
        "error": None
    }
