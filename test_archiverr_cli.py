#!/usr/bin/env python3
"""
Test script to verify archiverr CLI functionality
Tests both CLI mode and API mode without needing MongoDB
"""

import sys
import subprocess
from pathlib import Path

def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and report result"""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/home/samet/Workspace/archiverr"
        )
        
        print("STDOUT:")
        print(result.stdout if result.stdout else "(empty)")
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nExit code: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ SUCCESS")
            return True
        else:
            print("❌ FAILED")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("ARCHIVERR CLI VERIFICATION TESTS")
    print("="*60)
    
    results = []
    
    # Test 1: Check if archiverr command exists
    results.append(run_command(
        [".venv/bin/archiverr", "--help"],
        "Check if archiverr command exists and shows help"
    ))
    
    # Test 2: Test Python module execution
    results.append(run_command(
        [".venv/bin/python", "-m", "archiverr", "--help"],
        "Check if archiverr module can be executed"
    ))
    
    # Test 3: Check serve command help
    results.append(run_command(
        [".venv/bin/archiverr", "serve", "--help"],
        "Check if serve command is available"
    ))
    
    # Test 4: Check package info
    results.append(run_command(
        [".venv/bin/pip", "show", "archiverr"],
        "Check if archiverr package is installed"
    ))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
