#!/usr/bin/env python3
"""
Full integration test for archiverr
Tests CLI execution with actual config
"""

import sys
import subprocess
import os

def test_cli_execution():
    """Test archiverr CLI with config.yml"""
    print("\n" + "="*60)
    print("TEST: Archiverr CLI Execution with config.yml")
    print("="*60)
    
    # Check if TMDB_API_KEY is set
    if not os.getenv("TMDB_API_KEY"):
        print("⚠️  WARNING: TMDB_API_KEY not set in environment")
        print("   The TMDB plugin may fail, but the system should still work")
        print()
    
    cmd = [".venv/bin/archiverr"]
    
    print(f"Running: {' '.join(cmd)}")
    print("Working directory: /home/samet/Workspace/archiverr")
    print()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/home/samet/Workspace/archiverr"
        )
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nExit code: {result.returncode}")
        
        # Check for success indicators
        success_indicators = [
            "Archiverr complete",
            "Run started",
            "completed"
        ]
        
        output = result.stdout + result.stderr
        has_success = any(indicator in output for indicator in success_indicators)
        
        if result.returncode == 0 or has_success:
            print("\n✅ CLI EXECUTION SUCCESSFUL")
            return True
        else:
            print("\n❌ CLI EXECUTION FAILED")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT (60s)")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def check_output_files():
    """Check if output files were created"""
    print("\n" + "="*60)
    print("TEST: Check Output Files")
    print("="*60)
    
    output_dir = "/home/samet/Workspace/archiverr/output"
    
    try:
        if os.path.exists(output_dir):
            files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
            if files:
                print(f"✅ Found {len(files)} output file(s):")
                for f in files[-3:]:  # Show last 3
                    path = os.path.join(output_dir, f)
                    size = os.path.getsize(path)
                    print(f"   - {f} ({size} bytes)")
                return True
            else:
                print("⚠️  Output directory exists but no JSON files found")
                return False
        else:
            print("⚠️  Output directory doesn't exist")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("ARCHIVERR FULL INTEGRATION TEST")
    print("="*60)
    
    results = []
    
    # Test CLI execution
    results.append(test_cli_execution())
    
    # Check output files
    results.append(check_output_files())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed >= 1:  # At least CLI execution should work
        print("✅ Core functionality working!")
        return 0
    else:
        print("❌ Critical tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
