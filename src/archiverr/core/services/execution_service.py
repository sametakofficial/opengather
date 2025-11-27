"""
Execution Service - Shared execution logic for CLI and API

This service encapsulates the execution pipeline that was previously
only available through CLI. Now both CLI and API can use it.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, AsyncGenerator
from dataclasses import dataclass, field
import yaml


@dataclass
class ExecutionProgress:
    """Progress update during execution"""
    execution_id: str
    status: str  # pending, running, completed, failed
    current_match: int = 0
    total_matches: int = 0
    current_plugin: str = ""
    message: str = ""
    percent: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "status": self.status,
            "current_match": self.current_match,
            "total_matches": self.total_matches,
            "current_plugin": self.current_plugin,
            "message": self.message,
            "percent": self.percent,
            "timestamp": self.timestamp
        }


@dataclass
class ExecutionResult:
    """Final result of execution"""
    execution_id: str
    success: bool
    total_matches: int
    completed_matches: int
    failed_matches: int
    duration_ms: int
    api_response: Dict[str, Any]
    error: Optional[str] = None


class ExecutionService:
    """
    Service for running media processing executions.
    
    Can be used by both CLI and API.
    Supports progress callbacks for real-time updates.
    """
    
    def __init__(self, persistence=None, debugger=None):
        self.persistence = persistence
        self.debugger = debugger
        self._progress_callbacks: List[Callable] = []
    
    def add_progress_callback(self, callback: Callable[[ExecutionProgress], None]):
        """Add callback for progress updates"""
        self._progress_callbacks.append(callback)
    
    def _emit_progress(self, progress: ExecutionProgress):
        """Emit progress to all callbacks"""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception:
                pass
    
    async def _emit_progress_async(self, progress: ExecutionProgress):
        """Async version of emit progress"""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress)
                else:
                    callback(progress)
            except Exception:
                pass
    
    def run_execution(
        self,
        config: Dict[str, Any],
        targets: Optional[List[str]] = None
    ) -> ExecutionResult:
        """
        Run execution synchronously.
        
        Args:
            config: Full configuration dictionary
            targets: Optional override for targets (overrides config)
            
        Returns:
            ExecutionResult with full API response
        """
        # Create event loop FIRST, then initialize persistence
        # MongoDB's Motor driver needs the loop to exist when client is created
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Now initialize persistence - it will use this loop
            from archiverr.infrastructure.database import DatabaseConnection
            
            db_connection = DatabaseConnection.from_env()
            persistence = db_connection.connect()
            
            # Store for async method
            self.persistence = persistence
            self._db_connection = db_connection
            
            return loop.run_until_complete(self.run_execution_async(config, targets))
        finally:
            # Cleanup
            if hasattr(self, '_db_connection') and self._db_connection:
                self._db_connection.disconnect()
            loop.close()
    
    async def run_execution_async(
        self,
        config: Dict[str, Any],
        targets: Optional[List[str]] = None
    ) -> ExecutionResult:
        """
        Run execution asynchronously.
        
        This is the main execution method that implements the full pipeline.
        """
        from archiverr.core.plugins import (
            PluginDiscovery,
            PluginLoader,
            DependencyResolver,
            PluginExecutor
        )
        from archiverr.models import APIResponseBuilder
        from archiverr.core.tasks import TemplateManager, TaskManager
        from archiverr.state import GlobalStateManager, PluginResult
        from archiverr.events import EventBus, ProgressHandler, StatisticsHandler, Events
        from archiverr.utils.debug import init_debugger, get_debugger
        from archiverr.infrastructure.database import DatabaseConnection, MONGODB_AVAILABLE
        
        start_time = datetime.now()
        execution_id = self._generate_id()
        
        # Override targets if provided
        if targets:
            # Find the enabled input plugin and override its targets
            for plugin_name in ['scanner', 'file-reader', 'file_reader']:
                if plugin_name in config.get('plugins', {}):
                    config['plugins'][plugin_name]['targets'] = targets
        
        # Initialize debugger
        debug = config.get('options', {}).get('debug', False)
        dry_run = config.get('options', {}).get('dry_run', True)
        debugger = self.debugger or init_debugger(enabled=debug)
        
        # Emit starting progress
        await self._emit_progress_async(ExecutionProgress(
            execution_id=execution_id,
            status="running",
            message="Initializing execution..."
        ))
        
        try:
            # Initialize event bus for loose coupling
            event_bus = EventBus()
            event_bus.reset()
            event_bus.configure(debugger=debugger)
            
            # Register event handlers
            progress_handler = ProgressHandler()
            stats_handler = StatisticsHandler()
            event_bus.subscribe(Events.MATCH_COMPLETED, progress_handler)
            event_bus.subscribe(Events.MATCH_FAILED, progress_handler)
            event_bus.subscribe("*", stats_handler)
            
            # Initialize state management
            state = GlobalStateManager()
            state.reset()
            
            # Initialize persistence (MongoDB or Mock based on env var)
            # This mirrors CLI behavior exactly
            if self.persistence:
                persistence = self.persistence
                db_connection = None
            else:
                db_connection = DatabaseConnection.from_env()
                persistence = db_connection.connect()
            
            backend_type = os.getenv('ARCHIVERR_DB_BACKEND', 'mock')
            debugger.info("database", f"Using {backend_type} persistence",
                         mongodb_available=MONGODB_AVAILABLE)
            
            state.configure(persistence=persistence, debugger=debugger, event_bus=event_bus)
            
            # Start execution in state
            state.start_execution(config)
            
            # Phase 1: Discover plugins
            await self._emit_progress_async(ExecutionProgress(
                execution_id=execution_id,
                status="running",
                message="Discovering plugins..."
            ))
            
            discovery = PluginDiscovery()
            all_plugins = discovery.discover()
            
            # Phase 2: Load enabled plugins
            await self._emit_progress_async(ExecutionProgress(
                execution_id=execution_id,
                status="running",
                message=f"Loading plugins... ({len(all_plugins)} discovered)"
            ))
            
            loader = PluginLoader(all_plugins, config)
            input_plugins = loader.load_by_category('input')
            output_plugins = loader.load_by_category('output')
            
            # Phase 3: Resolve dependencies
            resolver = DependencyResolver(all_plugins)
            enabled_output = list(output_plugins.keys())
            execution_groups = resolver.resolve(enabled_output)
            
            # Phase 4: Execute input plugins
            await self._emit_progress_async(ExecutionProgress(
                execution_id=execution_id,
                status="running",
                message="Executing input plugins..."
            ))
            
            executor = PluginExecutor()
            input_matches = executor.execute_input_plugins(input_plugins)
            
            if not input_matches:
                return ExecutionResult(
                    execution_id=execution_id,
                    success=False,
                    total_matches=0,
                    completed_matches=0,
                    failed_matches=0,
                    duration_ms=0,
                    api_response={},
                    error="No matches found"
                )
            
            total_matches = len(input_matches)
            
            # Phase 5: Execute output plugins for each match
            processed_matches = []
            all_task_results = []
            match_task_results = {}
            
            template_manager = TemplateManager(config)
            template_manager.configure(config, loaded_plugins=all_plugins)
            task_manager = TaskManager(config, template_manager)
            builder = APIResponseBuilder()
            
            for index, match in enumerate(input_matches):
                percent = (index / total_matches) * 100
                
                await self._emit_progress_async(ExecutionProgress(
                    execution_id=execution_id,
                    status="running",
                    current_match=index,
                    total_matches=total_matches,
                    message=f"Processing match {index + 1}/{total_matches}",
                    percent=percent
                ))
                
                # Register match in state
                input_path = match.get('input', {}).get('path', '') if isinstance(match.get('input'), dict) else str(match.get('input', ''))
                state.register_match(index, input_path)
                
                # Execute output plugins
                result = executor.execute_output_pipeline(
                    output_plugins,
                    execution_groups,
                    match,
                    resolver
                )
                
                processed_matches.append(result)
                
                # Track plugin results
                status = result.get('status', {})
                success_plugins = status.get('success_plugins', [])
                failed_plugins = status.get('failed_plugins', [])
                not_supported_plugins = status.get('not_supported_plugins', [])
                
                # Track plugin results in state
                for plugin_name in success_plugins:
                    plugin_data = result.get(plugin_name, {})
                    plugin_result = PluginResult(
                        plugin_name=plugin_name,
                        success=True,
                        started_at=datetime.now(),
                        finished_at=datetime.now(),
                        data=plugin_data if isinstance(plugin_data, dict) else {}
                    )
                    state.update_plugin_result(index, plugin_name, plugin_result)
                
                for plugin_name in failed_plugins:
                    plugin_data = result.get(plugin_name, {})
                    plugin_result = PluginResult(
                        plugin_name=plugin_name,
                        success=False,
                        started_at=datetime.now(),
                        finished_at=datetime.now(),
                        data=plugin_data if isinstance(plugin_data, dict) else {},
                        error="Plugin failed"
                    )
                    state.update_plugin_result(index, plugin_name, plugin_result)
                
                # Execute tasks for this match
                total_plugins_run = len(success_plugins) + len(failed_plugins) + len(not_supported_plugins)
                if total_plugins_run == len(output_plugins):
                    temp_api_response = state.build_api_response_for_templates()
                    task_results = task_manager.execute_tasks_for_match(
                        temp_api_response,
                        index,
                        dry_run
                    )
                    all_task_results.extend(task_results)
                    match_task_results[index] = task_results
                    
                    for task_result in task_results:
                        state.add_task_result(index, task_result)
                    
                    state.complete_match(index)
            
            # Phase 6: Build final API response
            await self._emit_progress_async(ExecutionProgress(
                execution_id=execution_id,
                status="running",
                current_match=total_matches,
                total_matches=total_matches,
                message="Building API response...",
                percent=95
            ))
            
            api_response = builder.build(
                processed_matches,
                config=config,
                start_time=start_time,
                loaded_plugins=all_plugins
            )
            
            # Add task results to matches
            for match_index, task_results_list in match_task_results.items():
                if match_index < len(api_response['matches']):
                    match = api_response['matches'][match_index]
                    match_output = match.get('globals', {}).get('output', {})
                    
                    formatted_tasks = []
                    for task_result in task_results_list:
                        task_entry = {
                            'name': task_result.get('task_name'),
                            'type': task_result.get('type'),
                            'success': task_result.get('success', True)
                        }
                        if task_result.get('type') == 'print':
                            task_entry['rendered'] = task_result.get('output')
                        elif task_result.get('type') == 'save':
                            task_entry['destination'] = task_result.get('destination')
                        formatted_tasks.append(task_entry)
                    
                    match_output['tasks'] = formatted_tasks
            
            api_response['globals']['status']['tasks'] = len(all_task_results)
            
            # Complete execution
            state.complete_execution()
            
            # Disconnect persistence if we created it
            if db_connection is not None:
                db_connection.disconnect()
                debugger.debug("database", f"State persisted ({backend_type} backend)")
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Final progress
            await self._emit_progress_async(ExecutionProgress(
                execution_id=execution_id,
                status="completed",
                current_match=total_matches,
                total_matches=total_matches,
                message="Execution completed successfully",
                percent=100
            ))
            
            return ExecutionResult(
                execution_id=execution_id,
                success=True,
                total_matches=total_matches,
                completed_matches=api_response['globals']['status'].get('matches', total_matches),
                failed_matches=api_response['globals']['status'].get('errors', 0),
                duration_ms=duration_ms,
                api_response=api_response
            )
            
        except Exception as e:
            # Cleanup on error
            try:
                if 'db_connection' in dir() and db_connection is not None:
                    db_connection.disconnect()
            except:
                pass
            
            await self._emit_progress_async(ExecutionProgress(
                execution_id=execution_id,
                status="failed",
                message=f"Execution failed: {str(e)}"
            ))
            
            return ExecutionResult(
                execution_id=execution_id,
                success=False,
                total_matches=0,
                completed_matches=0,
                failed_matches=0,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                api_response={},
                error=str(e)
            )
    
    async def stream_execution(
        self,
        config: Dict[str, Any],
        targets: Optional[List[str]] = None
    ) -> AsyncGenerator[ExecutionProgress, None]:
        """
        Run execution and yield progress updates.
        
        This is ideal for WebSocket streaming.
        """
        progress_queue = asyncio.Queue()
        
        async def progress_callback(progress: ExecutionProgress):
            await progress_queue.put(progress)
        
        self.add_progress_callback(progress_callback)
        
        # Start execution in background
        task = asyncio.create_task(self.run_execution_async(config, targets))
        
        # Yield progress updates
        while not task.done():
            try:
                progress = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                yield progress
            except asyncio.TimeoutError:
                continue
        
        # Yield any remaining progress
        while not progress_queue.empty():
            yield await progress_queue.get()
        
        # Get final result
        result = task.result()
        
        # Yield final status
        yield ExecutionProgress(
            execution_id=result.execution_id,
            status="completed" if result.success else "failed",
            total_matches=result.total_matches,
            current_match=result.total_matches,
            message="Execution finished",
            percent=100
        )
    
    def _generate_id(self) -> str:
        """Generate unique execution ID"""
        from uuid import uuid4
        return str(uuid4())[:8]
    
    @staticmethod
    def load_config(config_path: str = "config.yml") -> Dict[str, Any]:
        """Load configuration from YAML file"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
