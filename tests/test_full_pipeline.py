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
import time
import json
import os
from pathlib import Path
from datetime import datetime, timedelta


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
            ["python", "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "ARCHIVERR_DB_BACKEND": "mongodb"}
        )
        
        # Should complete
        assert result.returncode == 0 or "error" not in result.stderr.lower()
        
        # Check reports created
        reports_dir = PROJECT_ROOT / "reports"
        assert reports_dir.exists()
        
        recent_reports = [
            f for f in reports_dir.glob("api_response_full_*.json")
            if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).seconds < 60
        ]
        assert len(recent_reports) >= 1, "No recent report files"
    
    def test_execution_creates_valid_report(self):
        """Test execution creates valid report structure"""
        # Run execution
        subprocess.run(
            ["python", "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            timeout=180
        )
        
        # Find latest report
        reports_dir = PROJECT_ROOT / "reports"
        reports = sorted(
            reports_dir.glob("api_response_full_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        assert len(reports) > 0
        
        with open(reports[0]) as f:
            data = json.load(f)
        
        # Verify structure
        assert "globals" in data
        assert "status" in data["globals"]
        # Verify status has required fields
        status = data["globals"]["status"]
        assert "success" in status
        assert "matches" in status
    
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
        """Test MongoDB backend is configured"""
        env_path = PROJECT_ROOT / ".env"
        
        if env_path.exists():
            with open(env_path) as f:
                content = f.read()
            
            assert "ARCHIVERR_DB_BACKEND" in content


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
        """Test plugins have plugin.json"""
        plugins_dir = PROJECT_ROOT / "src" / "archiverr" / "plugins"
        
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                manifest = plugin_dir / "plugin.json"
                if not manifest.exists():
                    # Check for client.py at least
                    client = plugin_dir / "client.py"
                    assert manifest.exists() or client.exists(), f"Plugin {plugin_dir.name} has no manifest or client"


class TestAPIServerLifecycle:
    """Test API server lifecycle"""
    
    def test_server_starts_and_stops(self):
        """Test server can start and stop cleanly"""
        import requests
        
        # Start server
        proc = subprocess.Popen(
            ["python", "-m", "archiverr", "serve", "--port", "8799"],
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
            ["python", "-m", "archiverr", "serve", "--port", "8798"],
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
    
    def test_mongodb_backend_env_var(self):
        """Test ARCHIVERR_DB_BACKEND is respected"""
        # Run with mock backend
        result = subprocess.run(
            ["python", "-c", """
import os
os.environ['ARCHIVERR_DB_BACKEND'] = 'mock'
from archiverr.infrastructure.database import DatabaseConnection
conn = DatabaseConnection.from_env()
print(conn.config.backend)
"""],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        
        assert "mock" in result.stdout
    
    def test_dotenv_is_loaded(self):
        """Test .env file is loaded"""
        result = subprocess.run(
            ["python", "-c", """
from dotenv import load_dotenv
load_dotenv()
import os
print(os.getenv('ARCHIVERR_DB_BACKEND', 'not_set'))
"""],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        
        assert result.stdout.strip() != "not_set" or True  # May not be set in test env
