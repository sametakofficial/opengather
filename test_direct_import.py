#!/usr/bin/env python3
"""Direct import test to verify package is working"""

import sys
sys.path.insert(0, '/home/samet/Workspace/archiverr/src')

try:
    # Test imports
    import archiverr
    print(f"✅ archiverr package imported: version {archiverr.__version__}")
    
    from archiverr.__main__ import main, cli_main, serve_api
    print("✅ Main functions imported successfully")
    
    from archiverr.core.orchestrator import Orchestrator, build_orchestrator
    print("✅ Orchestrator imported successfully")
    
    from archiverr.api.main import app
    print("✅ FastAPI app imported successfully")
    
    from archiverr.core.plugins.registry import PluginRegistry
    print("✅ Plugin registry imported successfully")
    
    from archiverr.state.manager import GlobalStateManager
    print("✅ State manager imported successfully")
    
    print("\n✅ ALL IMPORTS SUCCESSFUL - Package is working!")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
