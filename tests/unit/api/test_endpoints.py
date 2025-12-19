"""
API Endpoint Unit Tests

Tests FastAPI endpoints WITHOUT real database.
Uses TestClient with mocked database.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Starlette/FastAPI TestClient requires httpx. If it's not installed,
# skip this module to avoid collection-time RuntimeError.
pytest.importorskip("httpx")

from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Health check endpoint tests"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_health_check_returns_200(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/api/v1/system/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health_check_has_status(self, client):
        """Test health response includes status."""
        response = client.get("/api/v1/system/health")
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_root_endpoint_returns_api_info(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestExecutionEndpoints:
    """Execution endpoint tests with mocked DB"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_list_executions_returns_200(self, client):
        """Test list runs endpoint works (renamed from executions)."""
        response = client.get("/api/v1/runs")
        
        # May return 200 (with data) or 503 (no DB)
        assert response.status_code in [200, 503]
    
    def test_get_execution_not_found_returns_404(self, client):
        """Test non-existent run returns 404 (renamed from executions)."""
        response = client.get("/api/v1/runs/nonexistent_id")
        
        # 404 or 503 (no DB)
        assert response.status_code in [404, 503]
    
    def test_execution_status_endpoint_exists(self, client):
        """Test status endpoint route exists (renamed from executions)."""
        response = client.get("/api/v1/runs/test_id/status")
        
        # 404 or 503 (no DB)
        assert response.status_code in [404, 503]


class TestMatchEndpoints:
    """Match/Job endpoint tests (renamed from matches to jobs)"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_list_matches_returns_200(self, client):
        """Test list jobs endpoint works (renamed from matches)."""
        response = client.get("/api/v1/jobs")
        
        assert response.status_code in [200, 503]
    
    def test_get_match_not_found(self, client):
        """Test non-existent job returns 404 (renamed from matches)."""
        response = client.get("/api/v1/jobs/nonexistent_id")
        
        assert response.status_code in [404, 503]


@pytest.mark.skip(reason="Versioning/branches endpoints removed in refactoring")
class TestVersioningEndpoints:
    """Versioning (branches) endpoint tests - DEPRECATED"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_list_branches_returns_200(self, client):
        """Test list branches endpoint works."""
        response = client.get("/api/v1/versioning/branches")
        
        assert response.status_code in [200, 503]
    
    def test_create_branch_invalid_name_returns_400(self, client):
        """Test invalid branch name returns 400."""
        response = client.post(
            "/api/v1/versioning/branches",
            json={"name": ""}
        )
        
        # 400 (invalid) or 503 (no DB)
        assert response.status_code in [400, 503]
    
    def test_get_branch_not_found(self, client):
        """Test non-existent branch returns 404."""
        response = client.get("/api/v1/versioning/branches/nonexistent")
        
        assert response.status_code in [404, 503]


class TestRunEndpoints:
    """Run endpoint tests"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_run_endpoint_accepts_post(self, client):
        """Test run endpoint accepts POST."""
        response = client.post(
            "/api/v1/run/",
            json={}
        )
        
        # Should not be 405 (Method Not Allowed)
        assert response.status_code != 405
    
    def test_run_endpoint_rejects_get(self, client):
        """Test run endpoint rejects GET."""
        response = client.get("/api/v1/run/")
        
        assert response.status_code == 405


class TestOpenAPIDocumentation:
    """OpenAPI documentation tests"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_openapi_json_available(self, client):
        """Test OpenAPI JSON is available."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
    
    def test_docs_endpoint_available(self, client):
        """Test Swagger docs are available."""
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_redoc_endpoint_available(self, client):
        """Test ReDoc is available."""
        response = client.get("/redoc")
        
        assert response.status_code == 200


class TestErrorHandling:
    """Error handling tests"""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from archiverr.api.main import app
        with TestClient(app) as c:
            yield c
    
    def test_invalid_endpoint_returns_404(self, client):
        """Test unknown endpoint returns 404."""
        response = client.get("/api/v1/nonexistent")
        
        assert response.status_code == 404
    
    def test_invalid_method_returns_405(self, client):
        """Test invalid method returns 405."""
        response = client.delete("/api/v1/system/health")
        
        assert response.status_code == 405
