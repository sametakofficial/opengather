#!/usr/bin/env python
"""Get full traceback"""
import sys
import traceback
sys.path.insert(0, 'src')

try:
    print("1. Loading config...")
    from archiverr.utils.config_loader import load_config_with_tracking
    config = load_config_with_tracking('config.yml')
    print("✅ Config loaded")
    
    print("\n2. Initializing debugger...")
    from archiverr.utils.debug import init_debugger
    log_level = config.get('options', {}).get('log_level', 'INFO')
    debugger = init_debugger(level=log_level)
    print("✅ Debugger initialized")
    
    print("\n3. Building orchestrator...")
    from archiverr.core.orchestrator_builder import build_orchestrator
    orchestrator = build_orchestrator(config, debugger=debugger)
    print("✅ Orchestrator built")
    
    print("\n4. Running orchestrator...")
    result = orchestrator.run()
    print(f"\n✅ SUCCESS! Run: {result.run_id}")
    
except Exception as e:
    print(f"\n❌ EXCEPTION: {e}")
    print("\nFULL TRACEBACK:")
    print("=" * 60)
    traceback.print_exc()
    print("=" * 60)
    sys.exit(1)
