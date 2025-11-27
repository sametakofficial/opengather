"""
API Unit Tests

Tests for all API endpoints.
"""

import os
import pytest
from pathlib import Path

# Disable rate limiting for tests
os.environ["RATE_LIMIT_ENABLED"] = "false"

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent


@pytest.fixture
def client():
    """Create test client with lifespan support"""
    from archiverr.api.main import app
    # Use context manager to trigger lifespan events
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """Test health and system endpoints"""
    
    def test_health_check(self, client):
        """Test health endpoint"""
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data


class TestRunEndpoints:
    """Test run execution endpoints"""
    
    def test_run_endpoint_exists(self, client):
        """Test run endpoint is accessible"""
        response = client.post("/api/v1/run/", json={})
        assert response.status_code != 404
    
    def test_run_returns_json(self, client):
        """Test run endpoint returns JSON"""
        response = client.post("/api/v1/run/", json={})
        assert "application/json" in response.headers.get("content-type", "")


class TestExecutionsEndpoints:
    """Test executions endpoints"""
    
    def test_list_executions(self, client):
        """Test list executions endpoint"""
        response = client.get("/api/v1/executions/")
        # Should return 200 or 503 (if no MongoDB)
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "executions" in data
            assert "total" in data
    
    def test_get_execution_not_found(self, client):
        """Test get non-existent execution"""
        response = client.get("/api/v1/executions/nonexistent123")
        assert response.status_code in [404, 503]
    
    def test_get_execution_status(self, client):
        """Test get execution status"""
        response = client.get("/api/v1/executions/test123/status")
        assert response.status_code in [404, 503]


class TestMatchesEndpoints:
    """Test matches endpoints"""
    
    def test_list_matches(self, client):
        """Test list matches endpoint"""
        response = client.get("/api/v1/matches/")
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "matches" in data
            assert "total" in data
    
    def test_get_match_not_found(self, client):
        """Test get non-existent match"""
        response = client.get("/api/v1/matches/nonexistent123")
        assert response.status_code in [404, 503]


class TestVersioningEndpoints:
    """Test versioning/branches endpoints"""
    
    def test_list_branches(self, client):
        """Test list branches endpoint"""
        response = client.get("/api/v1/versioning/branches")
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "branches" in data
    
    def test_create_branch_invalid_name(self, client):
        """Test create branch with invalid name"""
        response = client.post(
            "/api/v1/versioning/branches",
            json={"name": ""}
        )
        assert response.status_code in [400, 422, 503]
    
    def test_get_branch_not_found(self, client):
        """Test get non-existent branch"""
        response = client.get("/api/v1/versioning/branches/nonexistent")
        assert response.status_code in [404, 503]


class TestErrorHandling:
    """Test error handling"""
    
    def test_invalid_endpoint_returns_404(self, client):
        """Test invalid endpoint returns 404"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_wrong_method_on_run(self, client):
        """Test GET on POST-only endpoint returns 405"""
        response = client.get("/api/v1/run/")
        assert response.status_code == 405


class TestOpenAPI:
    """Test OpenAPI documentation"""
    
    def test_openapi_json_available(self, client):
        """Test OpenAPI JSON is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
    
    def test_docs_available(self, client):
        """Test Swagger docs are accessible"""
        response = client.get("/docs")
        assert response.status_code == 200
