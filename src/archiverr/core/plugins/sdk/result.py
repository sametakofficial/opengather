"""
Plugin Result - Standardized result format for all plugins

Provides consistent structure for plugin outputs with timing info.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime


class PluginResult(BaseModel):
    """
    Standardized result format for all plugins.
    
    Example:
        result = PluginResult(
            success=True,
            data={"movie": {"title": "...", "year": 2024}},
            started_at=datetime.now(),
            finished_at=datetime.now()
        )
        print(result.duration_ms)  # 1234
        
    Factory Methods:
        result = PluginResult.success_result(data={"movie": {...}}, metadata={...})
        result = PluginResult.error_result("API connection failed")
    """
    
    success: bool = Field(..., description="Whether plugin execution succeeded")
    data: Dict[str, Any] = Field(default_factory=dict, description="Plugin output data")
    error: Optional[str] = Field(None, description="Error message if failed")
    started_at: datetime = Field(..., description="Execution start time")
    finished_at: datetime = Field(..., description="Execution end time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Plugin metadata (api_calls, cache_hits, etc.)")
    
    @property
    def duration_ms(self) -> int:
        """Calculate execution duration in milliseconds"""
        return int((self.finished_at - self.started_at).total_seconds() * 1000)
    
    def to_status_dict(self) -> Dict[str, Any]:
        """Convert to status dict format used in API response"""
        return {
            "success": self.success,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_ms": self.duration_ms
        }
    
    def to_response_dict(self) -> Dict[str, Any]:
        """
        Convert to full API response format.
        
        Returns:
            Dict with 'status' key and all data fields flattened
        """
        return {
            "status": self.to_status_dict(),
            **self.data
        }
    
    @classmethod
    def success_result(
        cls,
        data: Dict[str, Any],
        started_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'PluginResult':
        """
        Factory for successful results.
        
        Args:
            data: Plugin output data
            started_at: When execution started (defaults to now)
            metadata: Optional metadata (api_calls, etc.)
            
        Returns:
            PluginResult with success=True
        """
        now = datetime.now()
        return cls(
            success=True,
            data=data,
            started_at=started_at or now,
            finished_at=now,
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(
        cls,
        error: str,
        started_at: Optional[datetime] = None
    ) -> 'PluginResult':
        """
        Factory for error results.
        
        Args:
            error: Error message
            started_at: When execution started (defaults to now)
            
        Returns:
            PluginResult with success=False
        """
        now = datetime.now()
        return cls(
            success=False,
            error=error,
            started_at=started_at or now,
            finished_at=now
        )
    
    @classmethod
    def skipped_result(
        cls,
        reason: str = "",
        started_at: Optional[datetime] = None
    ) -> 'PluginResult':
        """
        Factory for skipped results (e.g., virtual paths, unsupported media).
        
        Args:
            reason: Why plugin was skipped
            started_at: When execution started (defaults to now)
            
        Returns:
            PluginResult with success=True, skipped=True in metadata
        """
        now = datetime.now()
        return cls(
            success=True,  # Skipped is not a failure
            data={},
            started_at=started_at or now,
            finished_at=now,
            metadata={'skipped': True, 'skip_reason': reason}
        )
    
    class Config:
        """Pydantic config"""
        # Allow arbitrary types for datetime
        arbitrary_types_allowed = True
