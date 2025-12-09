#!/usr/bin/env python
"""Direct test of archiverr"""
import sys
import traceback

print("=" * 60)
print("DIRECT ARCHIVERR TEST")
print("=" * 60)

try:
    print("\n1. Testing import...")
    sys.path.insert(0, 'src')
    
    print("2. Importing config loader...")
    from archiverr.utils.config_loader import load_config_with_tracking
    print("   ✅ Config loader OK")
    
    print("3. Importing debug...")
    from archiverr.utils.debug import init_debugger
    print("   ✅ Debug OK")
    
    print("4. Loading config...")
    config = load_config_with_tracking('config.yml')
    print(f"   ✅ Config loaded: {len(config)} keys")
    
    print("5. Initializing debugger...")
    options = config.get('options', {})
    log_level = options.get('log_level', 'INFO')
    print(f"   Log level: {log_level}")
    debugger = init_debugger(level=log_level)
    print("   ✅ Debugger initialized")
    
    print("6. Testing debug output...")
    debugger.info("test", "This is a test message")
    print("   ✅ Debug output OK")
    
    print("\n7. Importing orchestrator...")
    from archiverr.core.orchestrator_builder import build_orchestrator
    print("   ✅ Orchestrator import OK")
    
    print("\n8. Building orchestrator...")
    orchestrator = build_orchestrator(config, debugger=debugger)
    print("   ✅ Orchestrator built")
    
    print("\n" + "=" * 60)
    print("✅ ALL IMPORTS SUCCESSFUL!")
    print("=" * 60)
    print("\nNow running orchestrator...")
    print("=" * 60)
    
    result = orchestrator.run()
    
    print("\n" + "=" * 60)
    print("✅ EXECUTION COMPLETE!")
    print(f"Run ID: {result.run_id}")
    print(f"Success: {result.success}")
    print(f"Total jobs: {result.total_jobs}")
    print("=" * 60)
    
except Exception as e:
    print("\n" + "=" * 60)
    print("❌ ERROR!")
    print("=" * 60)
    print(f"Error: {e}")
    print("\nTraceback:")
    traceback.print_exc()
    print("=" * 60)
    sys.exit(1)
