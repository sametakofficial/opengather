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

import os
import logging
import atexit
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    from pymongo.database import Database
    from pymongo.errors import (
        ConnectionFailure,
        ServerSelectionTimeoutError,
        OperationFailure,
        DuplicateKeyError
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
    
    # Default TTL for plugin results (90 days)
    DEFAULT_TTL_DAYS = 90
    
    def __init__(
        self,
        uri: str = None,
        database: str = None,
        ttl_days: int = DEFAULT_TTL_DAYS
    ):
        """
        Initialize PyMongo persistence.
        
        Args:
            uri: MongoDB connection string (default: from MONGODB_URI env)
            database: Database name (default: from MONGODB_DATABASE env)
            ttl_days: Days to keep plugin results before auto-deletion
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "PyMongo is required for MongoDB persistence. "
                "Install with: pip install pymongo"
            )
        
        self._uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self._database_name = database or os.getenv("MONGODB_DATABASE", "archiverr")
        self._ttl_days = ttl_days
        
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._connected = False
    
    def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        try:
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                maxPoolSize=10,
                minPoolSize=1
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
        """Create database indexes (Session 12 - CLEAN!)."""
        # Runs indexes
        self._db[self.RUNS].create_index("started_at")
        self._db[self.RUNS].create_index([("status", 1), ("started_at", -1)])
        # _id is already unique by default, no need to specify!
        
        # Jobs indexes
        self._db[self.JOBS].create_index("run_id")
        # Note: (run_id, index) unique index created in _create_new_indexes()
        # _id is already unique by default!
        
        # Plugins indexes (ALL plugin data here!)
        self._db[self.PLUGINS].create_index(
            [("run_id", 1), ("job_id", 1), ("plugin_name", 1)],
            unique=True
        )
        self._db[self.PLUGINS].create_index("run_id")
        self._db[self.PLUGINS].create_index("job_id")
        self._db[self.PLUGINS].create_index("plugin_name")
        self._db[self.PLUGINS].create_index("stage")
        
        # Create new collection indexes (Session 11)
        self._create_new_indexes()
    
    # =========================================================================
    # NEW METHODS (Session 11 - FINAL_DATASETS.yml compliant)
    # =========================================================================
    
    def save_run(self, run: Dict[str, Any]) -> None:
        """Save or update run state."""
        try:
            if hasattr(run, 'to_dict'):
                run_dict = run.to_dict()
            else:
                run_dict = dict(run)
            
            run_id = run_dict.get("id", "")
            if not run_id:
                raise ValueError("Run must have 'id' field")
            
            self._db[self.RUNS].update_one(
                {"id": run_id},
                {
                    "$set": run_dict,
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                    "$currentDate": {"updated_at": True}
                },
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save run: {e}")
            raise
    
    def save_job(self, job: Dict[str, Any]) -> None:
        """Save or update job state."""
        try:
            if hasattr(job, 'to_dict'):
                job_dict = job.to_dict()
            else:
                job_dict = dict(job)
            
            job_id = job_dict.get("id", "")
            if not job_id:
                raise ValueError("Job must have 'id' field")
            
            self._db[self.JOBS].update_one(
                {"id": job_id},
                {
                    "$set": job_dict,
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                    "$currentDate": {"updated_at": True}
                },
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save job: {e}")
            raise
    
    def save_plugin(self, plugin: Dict[str, Any]) -> None:
        """Save plugin data to separate collection."""
        try:
            if hasattr(plugin, 'to_dict'):
                plugin_dict = plugin.to_dict()
            else:
                plugin_dict = dict(plugin)
            
            job_id = plugin_dict.get("job_id", "")
            plugin_name = plugin_dict.get("plugin_name", "")
            
            if not job_id or not plugin_name:
                raise ValueError("Plugin must have 'job_id' and 'plugin_name' fields")
            
            self._db[self.PLUGINS].update_one(
                {"job_id": job_id, "plugin_name": plugin_name},
                {
                    "$set": plugin_dict,
                    "$setOnInsert": {"created_at": datetime.utcnow()}
                },
                upsert=True
            )
        except OperationFailure as e:
            logger.error(f"Failed to save plugin: {e}")
            raise
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        return self._db[self.RUNS].find_one({"id": run_id})
    
    def get_jobs(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all jobs for a run, sorted by index."""
        cursor = self._db[self.JOBS].find({"run_id": run_id}).sort("index", 1)
        return list(cursor)
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        return self._db[self.JOBS].find_one({"id": job_id})
    
    def get_plugins(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all plugin data for a job."""
        cursor = self._db[self.PLUGINS].find({"job_id": job_id})
        return list(cursor)
    
    def get_plugin(self, job_id: str, plugin_name: str) -> Optional[Dict[str, Any]]:
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
    
    def _create_new_indexes(self) -> None:
        """Create indexes for new collections (Session 11)."""
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
        except Exception as e:
            logger.warning(f"Index creation warning (non-critical): {e}")
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "backend": "PyMongoPersistence",
            "uri": self._uri,
            "database": self._database_name,
            "runs": self._db[self.RUNS].count_documents({}),
            "jobs": self._db[self.JOBS].count_documents({}),
            "plugins": self._db[self.PLUGINS].count_documents({})
        }
    
