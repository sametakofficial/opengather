"""
Tests for Plugins API - Session 11 Phase 8

Tests the /v1/plugins endpoints.
"""

import pytest
from datetime import datetime
from archiverr.api.v1.plugins.schemas import (
    PluginInfo,
    PluginData,
    PluginListResponse,
    PluginDataListResponse
)


class TestPluginSchemas:
    """Test Plugin Pydantic schemas."""
    
    def test_plugin_info_defaults(self):
        """Test PluginInfo default values."""
        info = PluginInfo(name="test_plugin")
        assert info.name == "test_plugin"
        assert info.version == "1.0.0"
        assert info.stage == "output"
        assert info.requires == []
        assert info.provides == []
        assert info.trigger_rule == "all_success"
        assert info.enabled is True
    
    def test_plugin_info_full(self):
        """Test PluginInfo with all fields."""
        info = PluginInfo(
            name="tmdb",
            version="2.0.0",
            stage="data",
            requires=["job.plugins.renamer.parsed"],
            provides=["http.request"],
            trigger_rule="one_success",
            enabled=True,
            description="TMDB metadata fetcher"
        )
        assert info.name == "tmdb"
        assert info.version == "2.0.0"
        assert info.stage == "data"
        assert len(info.requires) == 1
        assert info.description == "TMDB metadata fetcher"
    
    def test_plugin_data_minimal(self):
        """Test PluginData with minimal data."""
        data = PluginData(
            job_id="job_run1_0",
            plugin_name="scanner"
        )
        assert data.job_id == "job_run1_0"
        assert data.plugin_name == "scanner"
        assert data.data == {}
        assert data.status == {}
    
    def test_plugin_data_full(self):
        """Test PluginData with full data."""
        data = PluginData(
            id="plugin_123",
            job_id="job_run1_5",
            run_id="run_test",
            plugin_name="tmdb",
            stage="data",
            data={
                "movie": {
                    "id": 12345,
                    "title": "Test Movie",
                    "year": 2023
                }
            },
            status={
                "success": True,
                "duration_ms": 500
            },
            created_at=datetime.now()
        )
        assert data.id == "plugin_123"
        assert data.plugin_name == "tmdb"
        assert data.stage == "data"
        assert data.data["movie"]["id"] == 12345
        assert data.status["success"] is True
    
    def test_plugin_list_response(self):
        """Test PluginListResponse."""
        response = PluginListResponse(
            items=[
                PluginInfo(name="scanner"),
                PluginInfo(name="renamer"),
                PluginInfo(name="tmdb")
            ],
            total=3
        )
        assert len(response.items) == 3
        assert response.total == 3
    
    def test_plugin_data_list_response(self):
        """Test PluginDataListResponse."""
        response = PluginDataListResponse(
            items=[
                PluginData(job_id="job_1", plugin_name="scanner"),
                PluginData(job_id="job_1", plugin_name="renamer")
            ],
            total=100,
            page=1,
            page_size=20
        )
        assert len(response.items) == 2
        assert response.total == 100
