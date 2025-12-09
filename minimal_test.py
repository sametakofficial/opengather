#!/usr/bin/env python
"""Minimal test to find get_debugger error"""
import sys
sys.path.insert(0, 'src')

print("=" * 60)
print("MINIMAL TEST - Finding get_debugger error")
print("=" * 60)

try:
    print("\n1. Import utils.debug...")
    from archiverr.utils import debug
    print(f"   debug module: {debug}")
    print(f"   get_debugger: {debug.get_debugger}")
    
    print("\n2. Call get_debugger()...")
    debugger = debug.get_debugger()
    print(f"   ✅ Debugger: {debugger}")
    
    print("\n3. Test debugger methods...")
    debugger.info("test", "Test message")
    print("   ✅ Logging works")
    
    print("\n4. Import orchestrator...")
    from archiverr.core import orchestrator
    print("   ✅ Orchestrator module imported")
    
    print("\n5. Check build_orchestrator...")
    print(f"   build_orchestrator: {orchestrator.build_orchestrator}")
    
    print("\n6. Import state manager...")
    from archiverr.state import GlobalStateManager
    print("   ✅ GlobalStateManager imported")
    
    print("\n7. Create state manager...")
    state = GlobalStateManager()
    print(f"   ✅ State created: {state}")
    
    print("\n8. Configure state (THIS MIGHT FAIL)...")
    state.configure(
        persistence=None,
        debugger=debugger,
        event_bus=None
    )
    print("   ✅ State configured")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR at step above: {e}")
    import traceback
    print("\nFULL TRACEBACK:")
    traceback.print_exc()
    sys.exit(1)
