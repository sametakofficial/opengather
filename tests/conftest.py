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


@pytest.fixture
def mock_db():
    """Mock database connection."""
    mock = MagicMock()
    mock.executions = MagicMock()
    mock.matches = MagicMock()
    mock.branches = MagicMock()
    mock.commits = MagicMock()
    return mock


# ==================== HTTP CLIENT ====================

@pytest.fixture
def anyio_backend():
    """Backend for anyio."""
    return "asyncio"


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
