"""
Tests for Legacy Redirects - Session 11 Phase 8

Tests backward compatibility redirects.
"""

import pytest


class TestLegacyRedirects:
    """Test legacy endpoint redirects."""
    
    def test_executions_redirect_url(self):
        """Test /executions redirects to /runs."""
        # The actual redirect is handled by FastAPI
        # Here we just verify the router is correctly defined
        from archiverr.api.v1.legacy.router import router
        
        routes = [r.path for r in router.routes]
        assert "/executions" in routes
        assert "/executions/{execution_id}" in routes
        assert "/executions/{execution_id}/status" in routes
        assert "/executions/{execution_id}/matches" in routes
    
    def test_matches_redirect_url(self):
        """Test /matches redirects to /jobs."""
        from archiverr.api.v1.legacy.router import router
        
        routes = [r.path for r in router.routes]
        assert "/matches" in routes
        assert "/matches/{match_id}" in routes
        assert "/matches/{match_id}/plugins" in routes
    
    def test_all_legacy_routes_deprecated(self):
        """Test all legacy routes are marked deprecated."""
        from archiverr.api.v1.legacy.router import router
        
        for route in router.routes:
            if hasattr(route, 'deprecated'):
                assert route.deprecated is True, f"Route {route.path} should be deprecated"
