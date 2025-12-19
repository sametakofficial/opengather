"""Archiverr - Config-Driven Media Organizer."""
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

from archiverr.core.config_validator import ConfigValidator
from archiverr.utils.config_loader import load_config_with_tracking
from archiverr.utils.debug import init_debugger


def serve_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        sys.stderr.write("ERROR: uvicorn not installed. Run: pip install uvicorn\n")
        sys.exit(1)

    # Use stderr for server info (not stdout which may be piped)
    sys.stderr.write(f"Archiverr API: http://{host}:{port} | Docs: http://{host}:{port}/docs\n")

    uvicorn.run(
        "archiverr.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


def cli_main(config_file: str = "config.yml"):
    """CLI entry point."""
    from archiverr.core.orchestrator import build_orchestrator

    config_path = Path(config_file)

    if not config_path.exists():
        sys.stderr.write(f"ERROR: {config_file} not found\n")
        sys.exit(1)

    try:
        config = load_config_with_tracking(str(config_path))
    except FileNotFoundError as e:
        sys.stderr.write(f"ERROR: Config file not found: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"ERROR: Invalid config format: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"ERROR: Failed to load config: {e}\n")
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

    debugger.info("system", "Archiverr starting")

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

    parser.add_argument("--config", default="config.yml", help="Path to config file (default: config.yml)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=False)

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
        cli_main(config_file=args.config)


if __name__ == "__main__":
    main()
