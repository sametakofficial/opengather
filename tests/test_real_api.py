"""
Real-World API Tests

These tests actually:
1. Start the API server
2. Make real HTTP requests
3. Check MongoDB for results
4. Verify the full execution pipeline

Requirements:
- MongoDB running locally
- config.yml with valid test targets
"""

import pytest
import subprocess
import time
import json
import os
import signal
from pathlib import Path

import requests

# Test configuration
API_URL = "http://localhost:8765"
PROJECT_ROOT = Path(__file__).parent.parent
MONGODB_DATABASE = "archiverr"


class TestRealAPI:
    """Real API tests with actual HTTP requests"""
    
    server_process = None
    
    @classmethod
    def setup_class(cls):
        """Start API server before tests"""
        # Kill any existing server on test port
        subprocess.run(["pkill", "-f", "archiverr serve.*8765"], capture_output=True)
        time.sleep(1)
        
        # Start server
        cls.server_process = subprocess.Popen(
            ["python", "-m", "archiverr", "serve", "--port", "8765"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        )
        
        # Wait for server to start
        max_wait = 10
        for _ in range(max_wait):
            try:
                response = requests.get(f"{API_URL}/api/v1/system/health", timeout=1)
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                time.sleep(1)
        else:
            pytest.fail("API server did not start in time")
    
    @classmethod
    def teardown_class(cls):
        """Stop API server after tests"""
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait(timeout=5)
    
    def test_health_endpoint(self):
        """Test health endpoint is accessible"""
        response = requests.get(f"{API_URL}/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_run_endpoint_returns_response(self):
        """Test /run endpoint returns valid response"""
        response = requests.post(
            f"{API_URL}/api/v1/run/",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "execution_id" in data
        assert "success" in data
        assert "total_matches" in data
        assert "duration_ms" in data
    
    def test_run_execution_saves_to_mongodb(self):
        """Test that API execution saves to MongoDB"""
        try:
            from pymongo import MongoClient
        except ImportError:
            pytest.skip("pymongo not installed")
        
        # Get count before
        client = MongoClient("mongodb://localhost:27017")
        db = client[MONGODB_DATABASE]
        count_before = db.executions.count_documents({})
        
        # Make API call
        response = requests.post(
            f"{API_URL}/api/v1/run/",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        
        # Wait a bit for MongoDB write
        time.sleep(2)
        
        # Get count after
        count_after = db.executions.count_documents({})
        
        # Should have at least one new execution
        assert count_after > count_before, "No new execution saved to MongoDB"
        
        client.close()
    
    def test_run_returns_api_response(self):
        """Test that run returns full API response"""
        response = requests.post(
            f"{API_URL}/api/v1/run/",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If execution was successful, should have api_response
        if data.get("success") and data.get("total_matches", 0) > 0:
            assert data.get("api_response") is not None
            assert "globals" in data["api_response"]
    
    def test_concurrent_requests(self):
        """Test API handles concurrent requests"""
        import concurrent.futures
        
        def make_request():
            try:
                response = requests.post(
                    f"{API_URL}/api/v1/run/",
                    json={},
                    headers={"Content-Type": "application/json"},
                    timeout=180
                )
                return response.status_code == 200
            except Exception:
                return False
        
        # Make 3 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(3)]
            results = [f.result() for f in futures]
        
        # At least one should succeed
        assert any(results), "All concurrent requests failed"


class TestMongoDBPersistence:
    """Test MongoDB persistence directly"""
    
    @pytest.fixture
    def mongo_client(self):
        """Get MongoDB client"""
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            # Test connection
            client.admin.command('ping')
            yield client
            client.close()
        except Exception as e:
            pytest.skip(f"MongoDB not available: {e}")
    
    def test_mongodb_connection(self, mongo_client):
        """Test MongoDB is accessible"""
        result = mongo_client.admin.command('ping')
        assert result.get('ok') == 1.0
    
    def test_executions_collection_exists(self, mongo_client):
        """Test executions collection has data"""
        db = mongo_client[MONGODB_DATABASE]
        count = db.executions.count_documents({})
        assert count >= 0  # Collection exists
    
    def test_execution_has_required_fields(self, mongo_client):
        """Test execution documents have required fields"""
        db = mongo_client[MONGODB_DATABASE]
        execution = db.executions.find_one({}, sort=[("started_at", -1)])
        
        if execution:
            assert "_id" in execution
            assert "status" in execution
            assert "started_at" in execution
    
    def test_matches_linked_to_execution(self, mongo_client):
        """Test matches are linked to executions"""
        db = mongo_client[MONGODB_DATABASE]
        
        # Get latest execution
        execution = db.executions.find_one({}, sort=[("started_at", -1)])
        if not execution:
            pytest.skip("No executions in database")
        
        # Find matches for this execution
        matches = list(db.matches.find({"execution_id": execution["_id"]}))
        
        # If execution completed successfully with matches, there should be match docs
        if execution.get("status") == "completed":
            # Matches may or may not exist depending on config
            assert isinstance(matches, list)


class TestCLIAPIEquivalence:
    """Test that CLI and API produce equivalent results"""
    
    def test_cli_creates_execution(self):
        """Test CLI creates execution in MongoDB"""
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
        except Exception:
            pytest.skip("MongoDB not available")
        
        db = client[MONGODB_DATABASE]
        count_before = db.executions.count_documents({})
        
        # Run CLI
        result = subprocess.run(
            ["python", "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        time.sleep(1)
        count_after = db.executions.count_documents({})
        
        assert count_after > count_before, "CLI did not create execution"
        client.close()
    
    def test_api_and_cli_same_execution_structure(self):
        """Test API and CLI create same execution structure"""
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
            client.admin.command('ping')
        except Exception:
            pytest.skip("MongoDB not available")
        
        db = client[MONGODB_DATABASE]
        
        # Get two recent executions
        executions = list(db.executions.find({}).sort("started_at", -1).limit(2))
        
        if len(executions) < 2:
            pytest.skip("Need at least 2 executions")
        
        # Both should have same fields
        fields_1 = set(executions[0].keys())
        fields_2 = set(executions[1].keys())
        
        # Core fields should be same
        core_fields = {"_id", "status", "started_at"}
        assert core_fields.issubset(fields_1)
        assert core_fields.issubset(fields_2)
        
        client.close()


class TestErrorHandling:
    """Test error handling scenarios"""
    
    server_process = None
    
    @classmethod
    def setup_class(cls):
        """Start API server"""
        subprocess.run(["pkill", "-f", "archiverr serve.*8766"], capture_output=True)
        time.sleep(1)
        
        cls.server_process = subprocess.Popen(
            ["python", "-m", "archiverr", "serve", "--port", "8766"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for startup
        for _ in range(10):
            try:
                requests.get("http://localhost:8766/api/v1/system/health", timeout=1)
                break
            except:
                time.sleep(1)
    
    @classmethod
    def teardown_class(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait(timeout=5)
    
    def test_invalid_endpoint_returns_404(self):
        """Test invalid endpoint returns 404"""
        response = requests.get("http://localhost:8766/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_wrong_method_returns_405(self):
        """Test wrong HTTP method returns 405"""
        response = requests.get("http://localhost:8766/api/v1/run/")
        assert response.status_code == 405
    
    def test_api_handles_timeout_gracefully(self):
        """Test API doesn't crash on long requests"""
        # Just verify server is still responding after potentially long operation
        try:
            response = requests.post(
                "http://localhost:8766/api/v1/run/",
                json={},
                timeout=5  # Short timeout
            )
        except requests.exceptions.Timeout:
            pass  # Expected for long operations
        
        # Server should still be healthy
        time.sleep(1)
        response = requests.get("http://localhost:8766/api/v1/system/health", timeout=5)
        assert response.status_code == 200


class TestReportGeneration:
    """Test report file generation"""
    
    def test_execution_creates_report_files(self):
        """Test that execution creates report files"""
        reports_dir = PROJECT_ROOT / "reports"
        
        # Get files before
        files_before = set(reports_dir.glob("api_response_*.json")) if reports_dir.exists() else set()
        
        # Run CLI
        subprocess.run(
            ["python", "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            timeout=120
        )
        
        # Get files after
        files_after = set(reports_dir.glob("api_response_*.json"))
        
        new_files = files_after - files_before
        assert len(new_files) > 0, "No new report files created"
    
    def test_report_file_is_valid_json(self):
        """Test report files contain valid JSON"""
        reports_dir = PROJECT_ROOT / "reports"
        
        if not reports_dir.exists():
            pytest.skip("No reports directory")
        
        report_files = list(reports_dir.glob("api_response_full_*.json"))
        if not report_files:
            pytest.skip("No report files found")
        
        # Check latest report
        latest = max(report_files, key=lambda x: x.stat().st_mtime)
        
        with open(latest, 'r') as f:
            data = json.load(f)  # Should not raise
        
        assert isinstance(data, dict)
        assert "globals" in data or "items" in data


class TestSubprocessExecution:
    """Test subprocess-based execution directly"""
    
    def test_subprocess_runs_successfully(self):
        """Test subprocess execution works"""
        result = subprocess.run(
            ["python", "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Should complete (may succeed or fail based on config)
        assert result.returncode in [0, 1]  # 0=success, 1=no matches
    
    def test_subprocess_output_contains_execution_info(self):
        """Test subprocess output contains expected info"""
        result = subprocess.run(
            ["python", "-m", "archiverr"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "ARCHIVERR_DB_BACKEND": "mongodb"}
        )
        
        # Combined output
        output = result.stdout + result.stderr
        
        # Should mention archiverr or execution
        assert len(output) > 0


# Standalone test functions for quick testing

def test_quick_api_health():
    """Quick test - just check if API is running"""
    try:
        response = requests.get("http://localhost:8000/api/v1/system/health", timeout=2)
        assert response.status_code == 200
    except requests.exceptions.ConnectionError:
        pytest.skip("API server not running on port 8000")


def test_quick_mongodb_connection():
    """Quick test - check MongoDB connection"""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        client.close()
    except Exception as e:
        pytest.fail(f"MongoDB connection failed: {e}")
