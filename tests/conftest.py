"""
Pytest fixtures and configuration for Archiverr tests.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, AsyncMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ==================== PYTEST CONFIGURATION ====================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (may require API running)")
    config.addinivalue_line("markers", "slow: Slow tests")


# ==================== EVENT LOOP ====================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ==================== TEST CONFIGURATION ====================

@pytest.fixture
def test_config() -> dict:
    """Basic test configuration."""
    return {
        "options": {
            "debug": False,
            "dry_run": True,
            "hardlink": False
        },
        "plugins": {
            "scanner": {
                "enabled": True,
                "targets": ["/tmp/test_media"],
                "recursive": False
            },
            "renamer": {
                "enabled": True
            },
            "tmdb": {
                "enabled": False
            }
        },
        "tasks": []
    }


# ==================== HTTP CLIENT ====================

@pytest.fixture
def anyio_backend():
    """Backend for anyio."""
    return "asyncio"


# ==================== PLUGIN-AGNOSTIC FIXTURES ====================

@pytest.fixture
def mock_input_plugin():
    """
    Generic input plugin for testing - NO REAL PLUGIN DEPENDENCY.
    
    Use this instead of referencing specific plugins like 'scanner'.
    """
    return {
        "name": "mock_input",
        "category": "input",
        "version": "1.0.0",
        "enabled": True,
        "class_name": "MockInputPlugin",
        "depends_on": [],
        "expects": [],
        "execute_result": {
            "status": {"success": True, "duration_ms": 10},
            "matches": ["/path/file1.mkv", "/path/file2.mkv"]
        }
    }


@pytest.fixture
def mock_output_plugin():
    """
    Generic output plugin for testing - NO REAL PLUGIN DEPENDENCY.
    
    Use this instead of referencing specific plugins like 'renamer', 'tmdb'.
    """
    return {
        "name": "mock_output",
        "category": "output",
        "version": "1.0.0",
        "enabled": True,
        "class_name": "MockOutputPlugin",
        "depends_on": ["mock_input"],
        "expects": ["mock_input.matches"],
        "execute_result": {
            "status": {"success": True, "duration_ms": 50},
            "processed": True,
            "data": {"title": "Test Title", "year": 2025}
        }
    }


@pytest.fixture
def mock_plugin_config(mock_input_plugin, mock_output_plugin):
    """
    Config with mock plugins only - NO REAL PLUGINS.
    
    Use this for unit tests that should not depend on real plugins.
    """
    return {
        "options": {"debug": False, "dry_run": True},
        "plugins": {
            mock_input_plugin["name"]: {"enabled": True},
            mock_output_plugin["name"]: {"enabled": True},
        },
        "tasks": []
    }


@pytest.fixture
def mock_plugin_metadata():
    """
    Mock plugin.json metadata for testing discovery/loading.
    """
    return {
        "input": {
            "name": "mock_input",
            "version": "1.0.0",
            "category": "input",
            "class_name": "MockInputPlugin",
            "depends_on": [],
            "expects": []
        },
        "output": {
            "name": "mock_output",
            "version": "1.0.0",
            "category": "output",
            "class_name": "MockOutputPlugin",
            "depends_on": ["mock_input"],
            "expects": ["mock_input.matches"]
        }
    }


@pytest.fixture
def mock_match_data():
    """
    Mock match data structure - plugin-agnostic.
    
    Contains generic plugin output format without specific plugin names.
    """
    return {
        "index": 0,
        "input_path": "/path/to/test_file.mkv",
        "status": "completed",
        "success": True,
        "plugins": {
            "mock_input": {
                "status": {"success": True},
                "input": "/path/to/test_file.mkv",
                "category": "movie"
            },
            "mock_output": {
                "status": {"success": True},
                "data": {"title": "Test Movie", "year": 2025}
            }
        }
    }


# ==================== MOCK FIXTURES ====================

@pytest.fixture
def mock_execution_result():
    """Mock execution result."""
    return {
        "execution_id": "test-123",
        "success": True,
        "total_matches": 5,
        "completed_matches": 5,
        "failed_matches": 0,
        "duration_ms": 1500,
        "error": None,
        "api_response": {
            "globals": {
                "status": {
                    "success": True,
                    "matches": 5,
                    "tasks": 10,
                    "errors": 0
                }
            },
            "items": []
        }
    }


@pytest.fixture
def mock_branch():
    """Mock branch data."""
    return {
        "name": "main",
        "description": "Main branch",
        "created_at": "2025-01-01T00:00:00Z",
        "head_commit_id": None,
        "metadata": {}
    }


@pytest.fixture
def mock_execution():
    """Mock execution data."""
    return {
        "execution_id": "exec-123",
        "status": "completed",
        "started_at": "2025-01-01T00:00:00Z",
        "finished_at": "2025-01-01T00:01:00Z",
        "config": {},
        "total_matches": 5,
        "completed_matches": 5,
        "failed_matches": 0,
        "duration_ms": 60000
    }
