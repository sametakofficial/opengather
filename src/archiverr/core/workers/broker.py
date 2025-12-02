"""
Task Broker - MongoDB-backed task queue

Uses Taskiq with MongoDB for:
- Persistent task storage
- No Redis dependency
- Direct MongoDB integration (already in stack)

Note: Requires taskiq and taskiq-mongodb packages:
    pip install taskiq taskiq-mongodb
"""

import os
from typing import Optional

# Lazy import to avoid dependency errors if taskiq not installed
_broker: Optional['MongoDBBroker'] = None


def get_broker():
    """
    Get or create the MongoDB broker instance.
    
    Lazy initialization to avoid import errors when taskiq not installed.
    """
    global _broker
    
    if _broker is not None:
        return _broker
    
    try:
        from taskiq_mongodb import MongoDBBroker
    except ImportError:
        raise ImportError(
            "taskiq-mongodb not installed. Run: pip install taskiq taskiq-mongodb"
        )
    
    _broker = MongoDBBroker(
        uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        database=os.getenv("MONGODB_TASK_DATABASE", "archiverr_tasks")
    )
    
    return _broker


# Convenience export (will be None until get_broker() called)
broker = None


def init_broker():
    """Initialize the broker. Call this at application startup."""
    global broker
    broker = get_broker()
    return broker
