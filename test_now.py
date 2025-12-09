#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

print("Testing archiverr...")
try:
    from archiverr.utils.config_loader import load_config_with_tracking
    from archiverr.utils.debug import init_debugger
    from archiverr.core.orchestrator_builder import build_orchestrator
    
    config = load_config_with_tracking('config.yml')
    log_level = config.get('options', {}).get('log_level', 'INFO')
    debugger = init_debugger(level=log_level)
    
    debugger.info("test", "Building orchestrator...")
    orchestrator = build_orchestrator(config, debugger=debugger)
    
    debugger.info("test", "Running...")
    result = orchestrator.run()
    
    print(f"\n✅ SUCCESS! Run ID: {result.run_id}, Jobs: {result.total_jobs}")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
