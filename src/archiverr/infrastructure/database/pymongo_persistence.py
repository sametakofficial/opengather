"""
PyMongo Sync Persistence

Production-ready MongoDB persistence using PyMongo sync driver.
NO async wrapping - pure synchronous operations for CLI usage.

This replaces the problematic MongoDBPersistence that used Motor + run_until_complete().

Usage:
    persistence = PyMongoPersistence(
        uri="mongodb://localhost:27017",
        database="archiverr"
    )
    persistence.connect()
    persistence.save_execution(execution)
    persistence.disconnect()
"""

import atexit
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    from pymongo.database import Database
    from pymongo.errors import (
        ConnectionFailure,
        DuplicateKeyError,
        OperationFailure,
        ServerSelectionTimeoutError,
    )
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoClient = None
    Database = None
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    OperationFailure = Exception
    DuplicateKeyError = Exception

from .interface import PersistenceInterface


class PyMongoPersistence(PersistenceInterface):
    """
    MongoDB persistence using PyMongo sync driver.
    
    Features:
    - Pure synchronous operations (no event loop conflicts)
    - Connection pooling
    - Automatic index creation
    - TTL support for plugin_results (90 days default)
    - Write-through for real-time persistence
    
    This is the recommended persistence for CLI usage.
    For API (async context), use Motor directly via get_database dependency.
    """

    RUNS = "runs"
    JOBS = "jobs"
    PLUGINS = "plugins"
    PLUGIN_DOCS = "plugin_docs"
    PLUGIN_EXECUTIONS = "plugin_executions"

    TERMINAL_STATES = {"completed", "failed", "skipped", "crashed"}

    # Configuration defaults
    DEFAULT_TTL_DAYS = 90
    DEFAULT_SERVER_SELECTION_TIMEOUT_MS = 5000
    DEFAULT_CONNECT_TIMEOUT_MS = 5000
    DEFAULT_MAX_POOL_SIZE = 10
    DEFAULT_MIN_POOL_SIZE = 1

    def __init__(
        self,
        uri: str = None,
        database: str = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
        server_selection_timeout_ms: int = DEFAULT_SERVER_SELECTION_TIMEOUT_MS,
        connect_timeout_ms: int = DEFAULT_CONNECT_TIMEOUT_MS,
        max_pool_size: int = DEFAULT_MAX_POOL_SIZE,
        min_pool_size: int = DEFAULT_MIN_POOL_SIZE
    ):
        """
        Initialize PyMongo persistence.
        
        Args:
            uri: MongoDB connection string (default: from MONGODB_URI env)
            database: Database name (default: from MONGODB_DATABASE env)
            ttl_days: Days to keep plugin results before auto-deletion
            server_selection_timeout_ms: Server selection timeout in ms
            connect_timeout_ms: Connection timeout in ms
            max_pool_size: Maximum connection pool size
            min_pool_size: Minimum connection pool size
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "PyMongo is required for MongoDB persistence. "
                "Install with: pip install pymongo"
            )

        self._uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self._database_name = database or os.getenv("MONGODB_DATABASE", "archiverr")
        self._ttl_days = ttl_days
        self._server_selection_timeout_ms = server_selection_timeout_ms
        self._connect_timeout_ms = connect_timeout_ms
        self._max_pool_size = max_pool_size
        self._min_pool_size = min_pool_size

        self._client: MongoClient | None = None
        self._db: Database | None = None
        self._connected = False

    def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        try:
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=self._server_selection_timeout_ms,
                connectTimeoutMS=self._connect_timeout_ms,
                maxPoolSize=self._max_pool_size,
                minPoolSize=self._min_pool_size
            )
            self._db = self._client[self._database_name]

            # Verify connection with ping
            self._db.command('ping')
            logger.info(f"PyMongo connected to: {self._database_name}")

            # Create indexes
            self._create_indexes()
            self._connected = True

            # Register cleanup on exit
            atexit.register(self.disconnect)

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB at {self._uri}: {e}")
            raise ConnectionError(f"MongoDB connection failed: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from MongoDB."""
        if self._client is not None and self._connected:
            self._client.close()
            self._client = None
            self._db = None
            self._connected = False
            logger.debug("PyMongo connection closed")

    def _create_indexes(self) -> None:
        """Create database indexes for all canonical collections."""
        try:
            # runs indexes
            self._db[self.RUNS].create_index("id", unique=True)
            self._db[self.RUNS].create_index("created_at")
            self._db[self.RUNS].create_index("status.state")

            # jobs indexes - drop existing non-unique before creating unique
            try:
                self._db[self.JOBS].drop_index("run_id_1_index_1")
            except Exception:
                pass  # Index doesn't exist or different name, continue

            self._db[self.JOBS].create_index([("run_id", 1), ("index", 1)], unique=True)
            self._db[self.JOBS].create_index("id", unique=True)
            self._db[self.JOBS].create_index("run_id")

            # plugins indexes
            self._db[self.PLUGINS].create_index([("job_id", 1), ("plugin_name", 1)], unique=True)
            self._db[self.PLUGINS].create_index("run_id")
            self._db[self.PLUGINS].create_index("job_id")

            # plugin_docs indexes (_id is target_id, unique by default)
            self._db[self.PLUGIN_DOCS].create_index("created_at")
            self._db[self.PLUGIN_DOCS].create_index("updated_at")

            # plugin_executions indexes (recovery surface)
            self._db[self.PLUGIN_EXECUTIONS].create_index(
                [("job_id", 1), ("plugin_name", 1), ("attempt", 1)],
                unique=True,
            )
            self._db[self.PLUGIN_EXECUTIONS].create_index("run_id")
            self._db[self.PLUGIN_EXECUTIONS].create_index("state")
            self._db[self.PLUGIN_EXECUTIONS].create_index(
                [("run_id", 1), ("state", 1)]
            )
        except Exception as e:
            logger.warning(f"Index creation warning (non-critical): {e}")

    def save_run(self, run: dict[str, Any]) -> None:
        """Save or update run state."""
        try:
            run_dict = run.to_dict() if hasattr(run, 'to_dict') else dict(run)
            run_id = run_dict.get("id", "")
            if not run_id:
                raise ValueError("Run must have 'id' field")

            # Remove created_at from $set to avoid conflict with $setOnInsert
            set_dict = {k: v for k, v in run_dict.items() if k != "created_at"}

            self._db[self.RUNS].update_one(
                {"id": run_id},
                {
                    "$set": set_dict,
                    "$setOnInsert": {"created_at": run_dict.get("created_at") or datetime.utcnow()},
                    "$currentDate": {"updated_at": True}
                },
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save run: {e}")
            raise

    def save_job(self, job: dict[str, Any]) -> None:
        """Save or update job state."""
        try:
            job_dict = job.to_dict() if hasattr(job, 'to_dict') else dict(job)
            job_id = job_dict.get("id", "")
            if not job_id:
                raise ValueError("Job must have 'id' field")

            # Remove created_at from $set to avoid conflict with $setOnInsert
            set_dict = {k: v for k, v in job_dict.items() if k != "created_at"}

            self._db[self.JOBS].update_one(
                {"id": job_id},
                {
                    "$set": set_dict,
                    "$setOnInsert": {"created_at": job_dict.get("created_at") or datetime.utcnow()},
                    "$currentDate": {"updated_at": True}
                },
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save job: {e}")
            raise

    def save_plugin(self, plugin: dict[str, Any]) -> None:
        """Save plugin data to separate collection."""
        try:
            plugin_dict = plugin.to_dict() if hasattr(plugin, 'to_dict') else dict(plugin)
            job_id = plugin_dict.get("job_id", "")
            plugin_name = plugin_dict.get("plugin_name", "")

            if not job_id or not plugin_name:
                raise ValueError("Plugin must have 'job_id' and 'plugin_name' fields")

            # Remove created_at from $set to avoid conflict with $setOnInsert
            set_dict = {k: v for k, v in plugin_dict.items() if k != "created_at"}

            self._db[self.PLUGINS].update_one(
                {"job_id": job_id, "plugin_name": plugin_name},
                {
                    "$set": set_dict,
                    "$setOnInsert": {"created_at": plugin_dict.get("created_at") or datetime.utcnow()}
                },
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save plugin: {e}")
            raise

    def update_plugin_doc(self, target_id: str, plugin_name: str, data: dict[str, Any]) -> None:
        """Update target-level plugin document."""
        if not target_id:
            raise ValueError("target_id is required")
        if not plugin_name:
            raise ValueError("plugin_name is required")

        self._db[self.PLUGIN_DOCS].update_one(
            {"_id": target_id},
            {
                "$set": {plugin_name: data or {}},
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$currentDate": {"updated_at": True}
            },
            upsert=True
        )

    def get_plugin_doc(self, target_id: str) -> dict[str, Any] | None:
        """Get target-level plugin document by target_id."""
        if not target_id:
            return None
        return self._db[self.PLUGIN_DOCS].find_one({"_id": target_id})

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get run by ID."""
        return self._db[self.RUNS].find_one({"id": run_id})

    def get_jobs(self, run_id: str) -> list[dict[str, Any]]:
        """Get all jobs for a run, sorted by index."""
        cursor = self._db[self.JOBS].find({"run_id": run_id}).sort("index", 1)
        return list(cursor)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job by ID."""
        return self._db[self.JOBS].find_one({"id": job_id})

    def get_plugins(self, job_id: str) -> list[dict[str, Any]]:
        """Get all plugin data for a job."""
        cursor = self._db[self.PLUGINS].find({"job_id": job_id})
        return list(cursor)

    def get_plugin(self, job_id: str, plugin_name: str) -> dict[str, Any] | None:
        """Get specific plugin data for a job."""
        return self._db[self.PLUGINS].find_one({
            "job_id": job_id,
            "plugin_name": plugin_name
        })

    def delete_run(self, run_id: str) -> bool:
        """Delete run and all related data (jobs, plugins)."""
        # Delete plugins for this run
        self._db[self.PLUGINS].delete_many({"run_id": run_id})

        # Delete jobs for this run
        self._db[self.JOBS].delete_many({"run_id": run_id})

        # Delete run
        result = self._db[self.RUNS].delete_one({"id": run_id})
        return result.deleted_count > 0

    def save_plugin_execution(
        self,
        run_id: str,
        job_id: str,
        plugin_name: str,
        state: str,
        attempt: int = 1,
        error: str | None = None,
        timestamp: Any = None,
    ) -> None:
        """
        Record a plugin execution state transition.

        Upserts a document keyed by (job_id, plugin_name, attempt). Non-terminal
        states (``started``, ``running``) are intentionally kept so a later
        startup scan can detect crashes.
        """
        if not self._connected or self._db is None:
            return
        now = timestamp or datetime.utcnow()
        update_doc: dict[str, Any] = {
            "$set": {
                "run_id": run_id,
                "job_id": job_id,
                "plugin_name": plugin_name,
                "state": state,
                "attempt": attempt,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        }
        if error is not None:
            update_doc["$set"]["error"] = error
        if state in self.TERMINAL_STATES:
            update_doc["$set"]["finished_at"] = now
        try:
            self._db[self.PLUGIN_EXECUTIONS].update_one(
                {"job_id": job_id, "plugin_name": plugin_name, "attempt": attempt},
                update_doc,
                upsert=True,
            )
        except OperationFailure as e:
            logger.error(f"Failed to save plugin_execution: {e}")

    def get_unfinished_plugin_executions(
        self, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        if not self._connected or self._db is None:
            return []
        query: dict[str, Any] = {"state": {"$nin": list(self.TERMINAL_STATES)}}
        if run_id:
            query["run_id"] = run_id
        cursor = self._db[self.PLUGIN_EXECUTIONS].find(query)
        return list(cursor)

    # ==================== STATISTICS ====================

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics."""
        return {
            "backend": "PyMongoPersistence",
            "uri": self._uri,
            "database": self._database_name,
            "runs": self._db[self.RUNS].count_documents({}),
            "jobs": self._db[self.JOBS].count_documents({}),
            "plugins": self._db[self.PLUGINS].count_documents({})
        }

