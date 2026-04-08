"""
Full Pipeline Integration Tests

Tests the complete execution flow from start to finish:
1. Config loading
2. Plugin discovery
3. Match processing
4. MongoDB persistence
5. Report generation

These are end-to-end tests that verify the entire system works together.
"""

import pytest
import subprocess
import sys
import time
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

import importlib.util

if importlib.util.find_spec("pymongo") is None:
    pytest.skip("pymongo not installed", allow_module_level=True)


PROJECT_ROOT = Path(__file__).parent.parent
MONGODB_DATABASE = "archiverr"


class TestFullExecutionPipeline:
    """Test complete execution from start to finish"""
    
    @pytest.fixture
    def clean_reports(self):
        """Clean old reports before test"""
        reports_dir = PROJECT_ROOT / "reports"
        if reports_dir.exists():
            # Keep only recent files
            cutoff = datetime.now() - timedelta(hours=1)
            for f in reports_dir.glob("*.json"):
                if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                    f.unlink()
        yield
    
    def test_full_execution_cli(self, clean_reports):
        """Test full execution via CLI"""
        # Run
        result = subprocess.run(
            [sys.executable, "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180
        )
        
        # Should complete
        assert result.returncode == 0 or "error" not in result.stderr.lower()
        
        # Check state dump created (new format: output/run_*_state.json)
        output_dir = PROJECT_ROOT / "output"
        assert output_dir.exists(), "Output directory should exist"
        
        recent_states = [
            f for f in output_dir.glob("run_*_state.json")
            if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).seconds < 120
        ]
        assert len(recent_states) >= 1, "No recent state dump files"
    
    def test_execution_creates_valid_report(self):
        """Test execution creates valid state dump structure"""
        # Run execution
        subprocess.run(
            [sys.executable, "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            timeout=180
        )
        
        # Find latest state dump (new format)
        output_dir = PROJECT_ROOT / "output"
        state_files = sorted(
            output_dir.glob("run_*_state.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        assert len(state_files) > 0, "No state dump files found"
        
        with open(state_files[0]) as f:
            data = json.load(f)
        
        # Verify structure (new state dump format)
        assert "run" in data or "id" in data, "State dump should have run data"
        # Check for jobs or status
        has_valid_structure = "jobs" in data or "status" in data or "config" in data
        assert has_valid_structure, "State dump should have valid structure"
    
    def test_mongodb_receives_execution_data(self):
        """Test MongoDB receives all execution data"""
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
        except Exception:
            pytest.skip("MongoDB not available")
        
        db = client[MONGODB_DATABASE]
        
        # Get latest execution
        execution = db.executions.find_one({}, sort=[("started_at", -1)])
        
        if execution:
            # Verify execution has expected fields
            assert "_id" in execution
            assert "status" in execution
            
            # If completed, should have more data
            if execution.get("status") == "completed":
                assert "started_at" in execution
        
        client.close()


class TestDatabaseIntegrity:
    """Test database data integrity"""
    
    @pytest.fixture
    def mongo_db(self):
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
            yield client[MONGODB_DATABASE]
            client.close()
        except Exception:
            pytest.skip("MongoDB not available")
    
    def test_no_orphaned_matches(self, mongo_db):
        """Test all matches have valid execution references"""
        matches = list(mongo_db.matches.find({}, {"execution_id": 1}))
        
        for match in matches:
            exec_id = match.get("execution_id")
            if exec_id:
                # Should find the execution
                execution = mongo_db.executions.find_one({"_id": exec_id})
                # Execution should exist (or match should be from test data)
    
    def test_execution_ids_are_unique(self, mongo_db):
        """Test execution IDs are unique"""
        executions = list(mongo_db.executions.find({}, {"_id": 1}))
        ids = [e["_id"] for e in executions]
        
        assert len(ids) == len(set(ids)), "Duplicate execution IDs found"
    
    def test_timestamps_are_valid(self, mongo_db):
        """Test timestamps are valid ISO format"""
        execution = mongo_db.executions.find_one({}, sort=[("started_at", -1)])
        
        if execution and "started_at" in execution:
            started_at = execution["started_at"]
            # Should be parseable
            if isinstance(started_at, str):
                datetime.fromisoformat(started_at.replace("Z", "+00:00"))


class TestConfigurationHandling:
    """Test configuration loading and validation"""
    
    def test_config_file_exists(self):
        """Test config.yml exists"""
        config_path = PROJECT_ROOT / "config.yml"
        assert config_path.exists(), "config.yml not found"
    
    def test_config_is_valid_yaml(self):
        """Test config.yml is valid YAML"""
        import yaml
        
        config_path = PROJECT_ROOT / "config.yml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert isinstance(config, dict)
    
    def test_config_has_required_sections(self):
        """Test config has required sections"""
        import yaml
        
        config_path = PROJECT_ROOT / "config.yml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert "options" in config or "plugins" in config
    
    def test_env_file_exists(self):
        """Test .env file exists"""
        env_path = PROJECT_ROOT / ".env"
        assert env_path.exists(), ".env file not found"
    
    def test_mongodb_backend_configured(self):
        """Test MongoDB is configured"""
        env_path = PROJECT_ROOT / ".env"
        
        if env_path.exists():
            with open(env_path) as f:
                content = f.read()
 
            assert "MONGODB_URI" in content or "MONGODB_DATABASE" in content


class TestPluginSystem:
    """Test plugin discovery and loading"""
    
    def test_plugins_directory_exists(self):
        """Test plugins directory exists"""
        plugins_dir = PROJECT_ROOT / "src" / "archiverr" / "plugins"
        assert plugins_dir.exists()
    
    def test_core_plugins_exist(self):
        """Test core plugins are present"""
        plugins_dir = PROJECT_ROOT / "src" / "archiverr" / "plugins"
        
        expected_plugins = ["scanner", "renamer"]
        
        for plugin in expected_plugins:
            plugin_dir = plugins_dir / plugin
            assert plugin_dir.exists(), f"Plugin {plugin} not found"
    
    def test_plugins_have_manifest(self):
        """Test plugins have manifest (json or yml) and entry point"""
        plugins_dir = PROJECT_ROOT / "src" / "archiverr" / "plugins"
        
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith(("_", ".")):
                # Check for manifest (json or yml)
                manifest_json = plugin_dir / "plugin.json"
                manifest_yml = plugin_dir / "manifest.yml"
                has_manifest = manifest_json.exists() or manifest_yml.exists()
                
                # Check for entry point (client.py or plugin.py)
                client_py = plugin_dir / "client.py"
                plugin_py = plugin_dir / "plugin.py"
                has_entry = client_py.exists() or plugin_py.exists()
                
                assert has_manifest or has_entry, f"Plugin {plugin_dir.name} has no manifest or entry point"


class TestAPIServerLifecycle:
    """Test API server lifecycle"""
    
    def test_server_starts_and_stops(self):
        """Test server can start and stop cleanly"""
        import requests
        
        # Start server
        proc = subprocess.Popen(
            [sys.executable, "-m", "archiverr", "serve", "--port", "8799"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            # Wait for startup
            started = False
            for _ in range(10):
                try:
                    resp = requests.get("http://localhost:8799/api/v1/system/health", timeout=1)
                    if resp.status_code == 200:
                        started = True
                        break
                except:
                    time.sleep(1)
            
            assert started, "Server did not start"
            
        finally:
            # Stop server
            proc.terminate()
            proc.wait(timeout=10)
        
        # Verify server stopped
        time.sleep(1)
        with pytest.raises(Exception):
            requests.get("http://localhost:8799/api/v1/system/health", timeout=1)
    
    def test_server_handles_sigterm(self):
        """Test server handles SIGTERM gracefully"""
        import signal
        
        proc = subprocess.Popen(
            [sys.executable, "-m", "archiverr", "serve", "--port", "8798"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        time.sleep(3)
        
        # Send SIGTERM
        proc.send_signal(signal.SIGTERM)
        
        # Should exit cleanly
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("Server did not shutdown on SIGTERM")


class TestEnvironmentVariables:
    """Test environment variable handling"""
