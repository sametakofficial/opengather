"""
Database Connection Manager

Centralized database connection handling for both sync and async backends.
Supports environment-based configuration.
"""

import os
from typing import Optional, Union
from dataclasses import dataclass

from .interface import PersistenceInterface
from .mock import MockPersistence


@dataclass
class DatabaseConfig:
    """Database configuration"""
    backend: str = "mock"  # "mock" or "mongodb"
    
    # Mock settings
    mock_path: str = "./mock_db"
    
    # MongoDB settings
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "archiverr"
    
    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Load configuration from environment variables.
        
        Environment Variables:
            ARCHIVERR_DB_BACKEND: "mock" or "mongodb" (default: mock)
            ARCHIVERR_MOCK_PATH: Path for mock database (default: ./mock_db)
            MONGODB_URI: MongoDB connection string (default: mongodb://localhost:27017)
            MONGODB_DATABASE: Database name (default: archiverr)
        """
        return cls(
            backend=os.getenv("ARCHIVERR_DB_BACKEND", "mock"),
            mock_path=os.getenv("ARCHIVERR_MOCK_PATH", "./mock_db"),
            mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            mongodb_database=os.getenv("MONGODB_DATABASE", "archiverr")
        )


class DatabaseConnection:
    """
    Database connection manager.
    
    Provides a unified interface for creating database connections
    regardless of the backend type.
    
    Usage:
        # From environment
        db = DatabaseConnection.from_env()
        persistence = db.get_persistence()
        
        # Manual configuration
        config = DatabaseConfig(backend="mongodb", mongodb_uri="...")
        db = DatabaseConnection(config)
        persistence = db.get_persistence()
    """
    
    _instance: Optional["DatabaseConnection"] = None
    _persistence: Optional[PersistenceInterface] = None
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Initialize database connection.
        
        Args:
            config: Database configuration. If None, uses defaults.
        """
        self.config = config or DatabaseConfig()
    
    @classmethod
    def from_env(cls) -> "DatabaseConnection":
        """Create connection from environment variables"""
        return cls(DatabaseConfig.from_env())
    
    @classmethod
    def get_instance(cls) -> "DatabaseConnection":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls.from_env()
        return cls._instance
    
    def get_persistence(self) -> PersistenceInterface:
        """
        Get persistence backend based on configuration.
        
        Returns:
            PersistenceInterface implementation
            
        Raises:
            ImportError: If MongoDB is requested but motor is not installed
            ValueError: If unknown backend is specified
        """
        if self._persistence is not None:
            return self._persistence
        
        if self.config.backend == "mock":
            self._persistence = MockPersistence(base_path=self.config.mock_path)
        
        elif self.config.backend == "mongodb":
            # Use new PyMongoPersistence (pure sync, no event loop issues)
            try:
                from .pymongo_persistence import PyMongoPersistence
                self._persistence = PyMongoPersistence(
                    uri=self.config.mongodb_uri,
                    database=self.config.mongodb_database
                )
            except ImportError as e:
                raise ImportError(
                    "MongoDB backend requires 'pymongo' package. "
                    "Install with: pip install pymongo"
                ) from e
        
        else:
            raise ValueError(f"Unknown database backend: {self.config.backend}")
        
        return self._persistence
    
    def connect(self) -> PersistenceInterface:
        """
        Get and connect to persistence backend.
        
        Returns:
            Connected PersistenceInterface implementation
        """
        persistence = self.get_persistence()
        persistence.connect()
        return persistence
    
    def disconnect(self) -> None:
        """Disconnect from persistence backend"""
        if self._persistence is not None:
            self._persistence.disconnect()
            self._persistence = None
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)"""
        if cls._instance is not None:
            cls._instance.disconnect()
        cls._instance = None
