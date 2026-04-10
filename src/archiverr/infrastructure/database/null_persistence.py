"""
Null Persistence - No-op implementation for running without MongoDB.

Used when MongoDB is not available (CLI-only mode, CI/CD, testing).
All writes are silently accepted, all reads return empty results.
"""

from typing import Any

from .interface import PersistenceInterface


class NullPersistence(PersistenceInterface):
    """
    No-op persistence backend.

    Implements PersistenceInterface with no-op writes and empty reads.
    Used as fallback when MongoDB is not available.
    """

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def save_run(self, run: dict[str, Any]) -> None:
        pass

    def save_job(self, job: dict[str, Any]) -> None:
        pass

    def save_plugin(self, plugin: dict[str, Any]) -> None:
        pass

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return None

    def get_jobs(self, run_id: str) -> list[dict[str, Any]]:
        return []

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return None

    def get_plugins(self, job_id: str) -> list[dict[str, Any]]:
        return []

    def get_plugin(self, job_id: str, plugin_name: str) -> dict[str, Any] | None:
        return None

    def get_statistics(self) -> dict[str, Any]:
        return {
            "backend": "NullPersistence",
            "runs": 0,
            "jobs": 0,
            "plugins": 0
        }
