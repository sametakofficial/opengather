"""
Plugin Manifest - Pydantic model for plugin.yml/plugin.json validation

Validates plugin manifest files at load time to catch errors early.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


class PluginManifest(BaseModel):
    """
    Pydantic model for plugin manifest validation.
    
    Example plugin.yml:
        name: tmdb
        version: 1.0.0
        description: TMDb metadata plugin
        category: output
        class_name: TMDbPlugin
        
        depends_on:
          - renamer
        
        expects:
          - renamer.parsed
        
        capabilities:
          - metadata.movie
          - metadata.show
          - validation.duration
        
        provides:
          - movie
          - show
          - episode
          - normalized
        
        hooks:
          - metadata.found
          - movie.matched
        
        config_schema:
          api_key:
            type: string
            required: true
            secret: true
    """
    
    # Core fields
    name: str = Field(..., description="Plugin name (lowercase, no spaces)")
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")
    description: Optional[str] = Field(None, description="Human-readable description")
    category: Literal["input", "output"] = Field(..., description="Plugin type")
    class_name: Optional[str] = Field(None, description="Python class name (inferred from name if not provided)")
    
    # Dependency system
    depends_on: List[str] = Field(default_factory=list, description="Plugin dependencies")
    expects: List[str] = Field(default_factory=list, description="Expected data paths")
    
    # Legacy field
    categories: List[str] = Field(default_factory=list, description="Supported media types")
    
    # NEW: Capability system (Stremio-inspired)
    capabilities: List[str] = Field(default_factory=list, description="What this plugin can do (metadata.movie, validation.duration)")
    provides: List[str] = Field(default_factory=list, description="Data fields this plugin produces")
    
    # NEW: Event system (Jellyfin-inspired)
    hooks: List[str] = Field(default_factory=list, description="Events this plugin emits")
    listens_to: List[str] = Field(default_factory=list, description="Events this plugin handles")
    
    # NEW: Config schema (Home Assistant-inspired)
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Configuration schema for validation")
    
    class Config:
        """Pydantic config"""
        extra = "ignore"  # Ignore unknown fields (e.g., aliases)
        
    @property
    def is_input(self) -> bool:
        """Check if this is an input plugin"""
        return self.category == "input"
    
    @property
    def is_output(self) -> bool:
        """Check if this is an output plugin"""
        return self.category == "output"
