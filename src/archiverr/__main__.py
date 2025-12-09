"""
Archiverr - Config-Driven Media Organizer

Session 11 Architecture - 4-Stage Plugin System:
  INPUT  → File discovery (per_run)
  PARSE  → Filename parsing (per_job)
  DATA   → External data fetching (per_job)
  OUTPUT → Output generation (per_job)

Usage:
    python -m archiverr           # CLI mode (default)
    python -m archiverr serve     # API server mode
    python -m archiverr serve --port 8080 --reload
"""
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

from archiverr.utils.config_loader import load_config_with_tracking
from archiverr.utils.debug import init_debugger
from archiverr.core.config_validator import ConfigValidator


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
    """
    CLI entry point - Session 11 architecture.
    
    Uses Orchestrator for 4-stage execution:
    1. INPUT: File discovery (scanner) - per_run
    2. PARSE: Filename parsing (renamer) - per_job
    3. DATA: External data fetching (tmdb, tvdb) - per_job
    4. OUTPUT: Output generation (tasker) - per_job
    """
    from archiverr.core.orchestrator import build_orchestrator
    
    config_path = Path("config.yml")
    
    if not config_path.exists():
        print("ERROR: config.yml not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Load config with env var expansion and tracking for snapshots
        config = load_config_with_tracking(str(config_path))
    except Exception as e:
        print(f"ERROR: Failed to load config.yml: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize debug system with log level support
    options = config.get('options', {})
    
    # Support both log_level (new) and debug (legacy)
    log_level = options.get('log_level')
    if not log_level:
        # Legacy: debug: true/false → convert to log level
        debug = options.get('debug', False)
        log_level = 'DEBUG' if debug else 'INFO'
    
    debugger = init_debugger(level=log_level)
    
    # Validate config structure
    validator = ConfigValidator()
    if validator.is_available():
        is_valid, error_msg = validator.validate(config)
        if not is_valid:
            debugger.error("config", "Invalid configuration", error=error_msg)
            sys.exit(1)
        debugger.debug("config", "Configuration validated")
    
    debugger.info("system", "Archiverr starting (Session 11 - 4-stage architecture)")
    
    try:
        # Build orchestrator with all dependencies
        orchestrator = build_orchestrator(config, debugger=debugger)
        
        # Execute 4-stage pipeline: INPUT → PARSE → DATA → OUTPUT
        result = orchestrator.run()
        
        # Log result
        debugger.info("system", "Archiverr complete",
                     run_id=result.run_id,
                     success=result.success,
                     total_jobs=result.total_jobs,
                     completed=result.completed,
                     failed=result.failed,
                     stages_completed=result.stages_completed,
                     duration_ms=result.duration_ms)
        
        if result.error:
            debugger.error("system", "Run error", error=result.error)
            sys.exit(1)
        
        if not result.success:
            sys.exit(1)
            
    except Exception as e:
        debugger.error("system", "Fatal error", error=str(e))
        sys.exit(1)


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
