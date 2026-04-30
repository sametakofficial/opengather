"""
Diagnostics Logging - MongoDB Persistence for Debug Logs

Industry-standard diagnostics logging pattern:
- Structured log entries stored in MongoDB
- TTL index for automatic cleanup (7 days default)
- Query support for filtering by level, component, time range
- Real-time monitoring capability

Usage:
    from archiverr.infrastructure.database.diagnostics import DiagnosticsLogger
    
    logger = DiagnosticsLogger(db)
    await logger.log("INFO", "system", "Execution started", execution_id="abc123")
    
    # Query recent errors
    errors = await logger.query(level="ERROR", limit=100)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from pymongo.asynchronous.database import AsyncDatabase
    ASYNC_PYMONGO_AVAILABLE = True
except ImportError:
    ASYNC_PYMONGO_AVAILABLE = False
    AsyncDatabase = None


class DiagnosticsLogger:
    """
    Async diagnostics logger with MongoDB persistence.
    
    Features:
    - Structured logging with context fields
    - TTL-based automatic cleanup
    - Query support for analysis
    - Batch writing for performance
    """

    COLLECTION = "diagnostics"
    DEFAULT_TTL_DAYS = 7

    def __init__(
        self,
        db: AsyncDatabase,
        ttl_days: int = DEFAULT_TTL_DAYS,
        batch_size: int = 100,
        flush_interval_seconds: float = 5.0
    ):
        """
        Initialize diagnostics logger.
        
        Args:
            db: PyMongo AsyncDatabase instance
            ttl_days: Days to keep logs (default 7)
            batch_size: Batch size for writes
            flush_interval_seconds: Auto-flush interval
        """
        self._db = db
        self._ttl_days = ttl_days
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._buffer: list[dict[str, Any]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize collection with indexes"""
        if self._initialized:
            return

        # Create TTL index for automatic cleanup
        await self._db[self.COLLECTION].create_index(
            "expires_at",
            expireAfterSeconds=0
        )

        # Create indexes for common queries
        await self._db[self.COLLECTION].create_index("timestamp")
        await self._db[self.COLLECTION].create_index("level")
        await self._db[self.COLLECTION].create_index("component")
        await self._db[self.COLLECTION].create_index(
            [("execution_id", 1), ("timestamp", 1)]
        )

        self._initialized = True

    async def log(
        self,
        level: str,
        component: str,
        message: str,
        execution_id: str | None = None,
        **fields
    ) -> None:
        """
        Log a diagnostics entry.
        
        Args:
            level: Log level (DEBUG, INFO, WARN, ERROR)
            component: Component name (plugin name or system component)
            message: Log message
            execution_id: Optional execution ID for correlation
            **fields: Additional context fields
        """
        now = datetime.now(timezone.utc)

        entry = {
            "timestamp": now.isoformat(),
            "level": level.upper(),
            "component": component,
            "message": message,
            "execution_id": execution_id,
            "fields": {k: v for k, v in fields.items() if v is not None},
            "expires_at": now + timedelta(days=self._ttl_days)
        }

        self._buffer.append(entry)

        # Flush if buffer is full
        if len(self._buffer) >= self._batch_size:
            await self.flush()

    async def flush(self) -> int:
        """
        Flush buffered logs to MongoDB.
        
        Returns:
            Number of entries written
        """
        if not self._buffer:
            return 0

        entries = self._buffer.copy()
        self._buffer.clear()

        try:
            result = await self._db[self.COLLECTION].insert_many(entries)
            return len(result.inserted_ids)
        except Exception:
            # Re-add to buffer on failure
            self._buffer.extend(entries)
            raise

    async def query(
        self,
        level: str | None = None,
        component: str | None = None,
        execution_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Query diagnostics logs.
        
        Args:
            level: Filter by log level
            component: Filter by component
            execution_id: Filter by execution ID
            since: Filter logs after this time
            until: Filter logs before this time
            limit: Max entries to return
            
        Returns:
            List of log entries
        """
        query = {}

        if level:
            query["level"] = level.upper()
        if component:
            query["component"] = component
        if execution_id:
            query["execution_id"] = execution_id
        if since or until:
            query["timestamp"] = {}
            if since:
                query["timestamp"]["$gte"] = since.isoformat()
            if until:
                query["timestamp"]["$lte"] = until.isoformat()

        cursor = self._db[self.COLLECTION].find(query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_stats(self) -> dict[str, Any]:
        """Get diagnostics statistics"""
        pipeline = [
            {"$group": {
                "_id": "$level",
                "count": {"$sum": 1}
            }}
        ]

        cursor = self._db[self.COLLECTION].aggregate(pipeline)
        level_counts = {doc["_id"]: doc["count"] async for doc in cursor}

        total = sum(level_counts.values())

        return {
            "total_entries": total,
            "by_level": level_counts,
            "buffer_size": len(self._buffer),
            "ttl_days": self._ttl_days
        }

    async def clear(self, before: datetime | None = None) -> int:
        """
        Clear diagnostics logs.
        
        Args:
            before: Only clear logs before this time (default: all)
            
        Returns:
            Number of entries deleted
        """
        query = {}
        if before:
            query["timestamp"] = {"$lte": before.isoformat()}

        result = await self._db[self.COLLECTION].delete_many(query)
        return result.deleted_count


# Sync wrapper for CLI usage
class SyncDiagnosticsLogger:
    """
    Sync wrapper for DiagnosticsLogger.
    
    Used in CLI mode where we have a sync event loop.
    """

    def __init__(self, db, ttl_days: int = 7):
        self._async_logger = DiagnosticsLogger(db, ttl_days)
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run(self, coro):
        loop = self._get_loop()
        if loop.is_running():
            # Already in async context - can't use run_until_complete
            # Return a future that will be awaited later
            return asyncio.ensure_future(coro)
        return loop.run_until_complete(coro)

    def initialize(self):
        return self._run(self._async_logger.initialize())

    def log(self, level: str, component: str, message: str, **fields):
        return self._run(self._async_logger.log(level, component, message, **fields))

    def flush(self):
        return self._run(self._async_logger.flush())

    def query(self, **kwargs):
        return self._run(self._async_logger.query(**kwargs))
