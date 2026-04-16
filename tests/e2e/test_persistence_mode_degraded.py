"""E2E: persistence_mode contract.

Session 34 WP-6 makes ``options.persistence_mode`` explicit with three
modes:

* ``off``      - NullPersistence, no warning, recovery disabled.
* ``degraded`` - try Mongo; on failure fall back to NullPersistence with
                 an explicit warn log.  This is the default.
* ``full``     - Mongo required; any failure is fatal.
"""

import pytest

from archiverr.core.exceptions import CriticalError
from archiverr.core.orchestrator import (
    VALID_PERSISTENCE_MODES,
    _resolve_persistence_mode,
    build_orchestrator,
)
from archiverr.infrastructure.database.null_persistence import NullPersistence


class TestResolvePersistenceMode:
    def test_default_is_degraded(self):
        assert _resolve_persistence_mode({}) == "degraded"
        assert _resolve_persistence_mode({"options": {}}) == "degraded"

    def test_valid_modes(self):
        for mode in VALID_PERSISTENCE_MODES:
            cfg = {"options": {"persistence_mode": mode}}
            assert _resolve_persistence_mode(cfg) == mode

    def test_invalid_mode_raises_critical(self):
        cfg = {"options": {"persistence_mode": "swallow-everything"}}
        with pytest.raises(CriticalError):
            _resolve_persistence_mode(cfg)

    def test_case_insensitive(self):
        cfg = {"options": {"persistence_mode": "FULL"}}
        assert _resolve_persistence_mode(cfg) == "full"


class TestBuildOrchestrator:
    def test_mode_off_gives_null_persistence(self):
        cfg = {"options": {"persistence_mode": "off"}}
        orch = build_orchestrator(cfg)
        assert isinstance(orch._persistence, NullPersistence)
        assert orch._persistence_mode == "off"

    def test_degraded_falls_back_when_mongo_unavailable(self, monkeypatch):
        from archiverr.infrastructure.database.connection import DatabaseConnection

        def _broken(*a, **kw):
            raise RuntimeError("Mongo unreachable")

        monkeypatch.setattr(DatabaseConnection, "from_env", staticmethod(_broken))

        cfg = {"options": {"persistence_mode": "degraded"}}
        orch = build_orchestrator(cfg)
        assert isinstance(orch._persistence, NullPersistence)
        assert orch._persistence_mode == "degraded"

    def test_full_mode_mongo_unavailable_raises(self, monkeypatch):
        from archiverr.infrastructure.database.connection import DatabaseConnection

        def _broken(*a, **kw):
            raise RuntimeError("Mongo unreachable")

        monkeypatch.setattr(DatabaseConnection, "from_env", staticmethod(_broken))

        cfg = {"options": {"persistence_mode": "full"}}
        with pytest.raises(CriticalError):
            build_orchestrator(cfg)
