"""
Base Repository

Abstract base class for repository pattern implementations.
Provides common CRUD operations interface.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository.
    
    All repositories should inherit from this class and implement
    the required CRUD operations.
    """
    
    @abstractmethod
    def save(self, entity: T) -> None:
        """Save entity to storage"""
        pass
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """Get all entities"""
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        """Delete entity by ID"""
        pass
    
    def exists(self, entity_id: str) -> bool:
        """Check if entity exists"""
        return self.get_by_id(entity_id) is not None
