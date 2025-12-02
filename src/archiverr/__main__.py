"""Archiverr - Config-Driven Media Organizer

Usage:
    python -m archiverr           # CLI mode (default)
    python -m archiverr serve     # API server mode
    python -m archiverr serve --port 8080 --reload
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

from archiverr.utils.config_loader import load_config_with_tracking
from archiverr.core.plugins import (
    PluginDiscovery,
    PluginLoader,
    DependencyResolver,
    PluginExecutor
)
from archiverr.models import APIResponseBuilder
from archiverr.core.tasks import TemplateManager, TaskManager
from archiverr.core.reports import generate_dual_reports
from archiverr.utils.debug import init_debugger, get_debugger
from archiverr.core.config_validator import ConfigValidator

# State management
from archiverr.state import GlobalStateManager, PluginResult

# Infrastructure layer (database, repositories)
from archiverr.infrastructure.database import DatabaseConnection, MONGODB_AVAILABLE

# Event bus for loose coupling
from archiverr.events import EventBus, Events, ProgressHandler, StatisticsHandler


def serve_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Start FastAPI server.
    
    Args:
        host: Bind address
        port: Port number
        reload: Enable auto-reload for development
    """
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed. Run: pip install uvicorn", file=sys.stderr)
        sys.exit(1)
    
    print(f"Starting Archiverr API server on http://{host}:{port}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"OpenAPI: http://{host}:{port}/openapi.json")
    print()
    
    uvicorn.run(
        "archiverr.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


def cli_main():
    """CLI entry point - original behavior"""
    # Record start time (single timestamp for entire execution)
    start_time = datetime.now()
    
    config_path = Path("config.yml")
    
    if not config_path.exists():
        print("ERROR: config.yml not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Load config with env var expansion and tracking for snapshots
        config = load_config_with_tracking(str(config_path))
    except Exception as e:
        # Pre-debug error - use print
        print(f"ERROR: Failed to load config.yml: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize debug system
    debug = config.get('options', {}).get('debug', False)
    dry_run = config.get('options', {}).get('dry_run', True)
    debugger = init_debugger(enabled=debug)
    
    # Validate config structure
    validator = ConfigValidator()
    if validator.is_available():
        is_valid, error_msg = validator.validate(config)
        if not is_valid:
            debugger.error("config", "Invalid configuration", error=error_msg)
            sys.exit(1)
        debugger.debug("config", "Configuration validated")
    else:
        debugger.debug("config", "Schema validation unavailable (jsonschema not installed)")
    
    debugger.info("system", "Archiverr starting", debug=debug, dry_run=dry_run)
    
    # Initialize event bus for loose coupling (DI pattern)
    event_bus = EventBus(debugger=debugger)
    
    # Register event handlers
    progress_handler = ProgressHandler()
    stats_handler = StatisticsHandler()
    event_bus.subscribe(Events.MATCH_COMPLETED, progress_handler)
    event_bus.subscribe(Events.MATCH_FAILED, progress_handler)
    event_bus.subscribe("*", stats_handler)  # Collect all stats
    
    # NEW: Initialize state management (parallel to existing system)
    state = GlobalStateManager()
    state.reset()  # Clean state for new execution
    
    # Initialize persistence (MongoDB or Mock based on ARCHIVERR_DB_BACKEND env var)
    db_connection = DatabaseConnection.from_env()
    persistence = db_connection.connect()
    
    backend_type = os.getenv('ARCHIVERR_DB_BACKEND', 'mock')
    debugger.info("database", f"Using {backend_type} persistence", 
                  mongodb_available=MONGODB_AVAILABLE)
    
    state.configure(persistence=persistence, debugger=debugger, event_bus=event_bus)
    
    # Start execution in state
    execution_id = state.start_execution(config)
    debugger.debug("state", "Execution started", id=execution_id)
    
    # Phase 1: Discover plugins
    debugger.debug("system", "Starting plugin discovery")
    discovery = PluginDiscovery()
    all_plugins = discovery.discover()
    debugger.info("discovery", "Plugin discovery complete", total=len(all_plugins))
    
    # Phase 2: Load enabled plugins
    debugger.debug("system", "Loading enabled plugins")
    loader = PluginLoader(all_plugins, config)
    input_plugins = loader.load_by_category('input')
    output_plugins = loader.load_by_category('output')
    debugger.info("loader", "Plugins loaded", input=len(input_plugins), output=len(output_plugins))
    
    # Phase 3: Resolve dependencies
    debugger.debug("system", "Resolving dependencies")
    resolver = DependencyResolver(all_plugins)
    enabled_output = list(output_plugins.keys())
    
    try:
        execution_groups = resolver.resolve(enabled_output)
        debugger.info("resolver", "Dependency resolution complete", groups=len(execution_groups))
        for i, group in enumerate(execution_groups):
            debugger.debug("resolver", f"Group {i}", plugins=", ".join(group))
    except ValueError as e:
        debugger.error("resolver", "Dependency resolution failed", error=str(e))
        sys.exit(1)
    
    # Phase 4: Execute input plugins
    debugger.debug("system", "Executing input plugins")
    executor = PluginExecutor()
    
    # Configure executor with runtime dependencies (for ExecutionContext)
    executor.configure(
        event_bus=event_bus,
        execution_id=execution_id,
        config=config,
        dry_run=dry_run,
        debug=debug
    )
    
    input_matches = executor.execute_input_plugins(input_plugins)
    
    if not input_matches:
        debugger.warn("executor", "No matches found")
        sys.exit(0)
    
    debugger.info("executor", "Input plugins complete", matches=len(input_matches))
    
    # Phase 5: Execute output plugins and tasks for each match
    processed_matches = []
    all_task_results = []
    match_task_results = {}  # Track task results per match {index: [results]}
    
    # Initialize template manager with aliases from config
    template_manager = TemplateManager(config)
    template_manager.configure(config, loaded_plugins=all_plugins)
    
    task_manager = TaskManager(config, template_manager)
    builder = APIResponseBuilder()
    
    # Inject task_manager into executor for per-plugin task emission
    executor.task_manager = task_manager
    
    debugger.debug("system", "Starting per-match processing")
    for index, match in enumerate(input_matches):
        debugger.info("executor", f"Processing match {index + 1}/{len(input_matches)}")
        
        # NEW: Register match in state
        input_path = match.get('input', {}).get('path', '') if isinstance(match.get('input'), dict) else str(match.get('input', ''))
        state_match = state.register_match(index, input_path)
        
        # Build partial API response for ExecutionContext (for per-plugin task emission)
        temp_api_response = state.build_api_response_for_templates()
        
        # Execute output plugins with expectations checking
        result = executor.execute_output_pipeline(
            output_plugins,
            execution_groups,
            match,
            resolver,  # Pass resolver for expectations validation
            match_index=index,
            total_matches=len(input_matches),
            api_response=temp_api_response
        )
        
        processed_matches.append(result)
        
        # Check if match is complete (all output plugins finished)
        status = result.get('status', {})
        success_plugins = status.get('success_plugins', [])
        failed_plugins = status.get('failed_plugins', [])
        not_supported_plugins = status.get('not_supported_plugins', [])
        total_plugins_run = len(success_plugins) + len(failed_plugins) + len(not_supported_plugins)
        
        # NEW: Track plugin results in state
        for plugin_name in success_plugins:
            plugin_data = result.get(plugin_name, {})
            plugin_result = PluginResult(
                plugin_name=plugin_name,
                success=True,
                started_at=datetime.now(),  # Approximate
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
        
        for plugin_name in not_supported_plugins:
            state.mark_plugin_not_supported(index, plugin_name)
        
        debugger.debug("executor", f"Match {index} complete", 
                      success=len(success_plugins),
                      failed=len(failed_plugins),
                      not_supported=len(not_supported_plugins))
        
        # If all enabled output plugins finished, execute tasks for this match
        if total_plugins_run == len(output_plugins):
            # NEW: Use state-based template context (fast, no rebuild)
            # This replaces expensive builder.build() call every iteration
            temp_api_response = state.build_api_response_for_templates()
            
            # Execute tasks for this match
            debugger.debug("tasks", f"Executing tasks for match {index}")
            task_results = task_manager.execute_tasks_for_match(
                temp_api_response,
                index,
                dry_run
            )
            all_task_results.extend(task_results)
            match_task_results[index] = task_results
            
            # NEW: Track task results in state
            for task_result in task_results:
                state.add_task_result(index, task_result)
            
            # NEW: Complete match in state
            state.complete_match(index)
            
            debugger.debug("tasks", f"Tasks complete for match {index}", executed=len(task_results))
    
    # Phase 6: Build final API response
    debugger.debug("system", "Building final API response")
    api_response = builder.build(
        processed_matches,
        config=config,
        start_time=start_time,
        loaded_plugins=all_plugins
    )
    
    # Phase 6.1: Add task results to match.globals.output.tasks
    for match_index, task_results_list in match_task_results.items():
        if match_index < len(api_response['matches']):
            match = api_response['matches'][match_index]
            match_output = match.get('globals', {}).get('output', {})
            
            # Format task results for storage
            formatted_tasks = []
            
            for task_result in task_results_list:
                task_entry = {
                    'name': task_result.get('task_name'),
                    'type': task_result.get('type'),
                    'success': task_result.get('success', True)
                }
                
                # Add type-specific fields
                if task_result.get('type') == 'print':
                    task_entry['rendered'] = task_result.get('output')
                elif task_result.get('type') == 'save':
                    task_entry['destination'] = task_result.get('destination')
                
                formatted_tasks.append(task_entry)
            
            # Update match.globals.output.tasks (NO paths - redundant)
            match_output['tasks'] = formatted_tasks
    
    # Update globals with task count
    api_response['globals']['status']['tasks'] = len(all_task_results)
    
    # Phase 7: Generate dual reports (full + compact + debug log)
    debugger.debug("system", "Generating API response reports")
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    report_paths = generate_dual_reports(api_response, timestamp, debugger=debugger)
    
    # Log report paths
    debugger.debug("system", "Reports generated", 
                  full=report_paths['full'], 
                  compact=report_paths['compact'],
                  debug_log=report_paths.get('debug_log', 'N/A'))
    
    debugger.info("system", "Archiverr complete", 
                 matches=len(processed_matches),
                 tasks=len(all_task_results),
                 errors=api_response['globals']['status']['errors'])
    
    # NEW: Complete execution in state and disconnect persistence
    state.complete_execution()
    db_connection.disconnect()
    
    debugger.debug("state", f"State persisted ({backend_type} backend)")


def main():
    """
    Main entry point - handles both CLI and API modes.
    
    Usage:
        python -m archiverr           # CLI mode
        python -m archiverr serve     # API mode (default port 8000)
        python -m archiverr serve --port 8080 --reload
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Archiverr - Config-Driven Media Organizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m archiverr                    # Run CLI (process config.yml)
  python -m archiverr serve              # Start API server
  python -m archiverr serve --port 8080  # Custom port
  python -m archiverr serve --reload     # Development mode
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        serve_api(host=args.host, port=args.port, reload=args.reload)
    else:
        # Default: CLI mode
        cli_main()


if __name__ == "__main__":
    main()
