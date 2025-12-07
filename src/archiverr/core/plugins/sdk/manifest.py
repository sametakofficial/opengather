"""
Plugin Manifest - Pydantic model for plugin.yml/plugin.json validation

Session 11: Updated to support stage-based format.

Validates plugin manifest files at load time to catch errors early.
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Literal, Optional, Dict, Any


# Valid stages
VALID_STAGES = Literal["input", "parse", "data", "output"]

# Valid trigger rules
VALID_TRIGGER_RULES = Literal["all_success", "one_success", "all_done", "all_fail", "none_fail"]


class PluginManifest(BaseModel):
    """
    Pydantic model for plugin manifest validation.
    
    Session 11: Supports both legacy (category) and new (stage) format.
    
    New format example (manifest.yml):
        name: tmdb
        version: 1.0.0
        description: TMDb metadata plugin
        stage: data
        class_name: TMDbPlugin
        entry_point: client.py
        
        requires:
          - job.plugins.renamer.parsed
        
        provides:
          - http.request
          - state.update
        
        trigger_rule: all_success
        
        config_schema:
          api_key:
            type: string
            required: true
            secret: true
    
    Legacy format (still supported):
        name: tmdb
        category: output
        depends_on:
          - renamer
        expects:
          - renamer.parsed
    """
    
    # Core fields
    name: str = Field(..., description="Plugin name (lowercase, no spaces)")
    version: str = Field(default="1.0.0", description="Semantic version (e.g., 1.0.0)")
    description: Optional[str] = Field(None, description="Human-readable description")
    class_name: Optional[str] = Field(None, description="Python class name")
    entry_point: Optional[str] = Field(default="client.py", description="Entry point file")
    
    # NEW: Stage-based system (Session 11)
    stage: Optional[VALID_STAGES] = Field(None, description="Execution stage (input, parse, data, output)")
    run_mode: Optional[Literal["per_run", "per_job"]] = Field(None, description="Session 12: Plugin execution mode")
    requires: List[str] = Field(default_factory=list, description="Required data paths (job.plugins.X.field)")
    trigger_rule: Optional[VALID_TRIGGER_RULES] = Field(default="all_success", description="When to run")
    reactive: bool = Field(default=False, description="Whether plugin reacts to events")
    
    # LEGACY: Category-based system (backward compat)
    category: Optional[Literal["input", "output"]] = Field(None, description="Legacy plugin type")
    depends_on: List[str] = Field(default_factory=list, description="Legacy plugin dependencies")
    expects: List[str] = Field(default_factory=list, description="Legacy expected data paths")
    
    # Shared fields
    categories: List[str] = Field(default_factory=list, description="Supported media types (movie, show)")
    provides: List[str] = Field(default_factory=list, description="What this plugin provides")
    
    # Capability system
    capabilities: List[str] = Field(default_factory=list, description="Plugin capabilities")
    
    # Event system
    hooks: List[str] = Field(default_factory=list, description="Events this plugin emits")
    listens_to: List[str] = Field(default_factory=list, description="Events this plugin handles")
    
    # Config schema
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Configuration schema")
    
    # Session 12: FS lock system
    fs_lock: List[str] = Field(default_factory=list, description="Static file paths to lock (no variables)")
    
    class Config:
        """Pydantic config"""
        extra = "ignore"  # Ignore unknown fields
    
    @model_validator(mode='after')
    def ensure_stage_or_category(self):
        """Ensure either stage or category is set."""
        if self.stage is None and self.category is None:
            # Default to data stage for unknown plugins
            self.stage = "data"
        return self
        
    @property
    def effective_stage(self) -> str:
        """Get effective stage (stage or mapped category)."""
        if self.stage:
            return self.stage
        # Map legacy category to stage
        if self.category == "input":
            return "input"
        return "data"  # Default for output category
    
    @property
    def is_input(self) -> bool:
        """Check if this is an input plugin"""
        return self.effective_stage == "input"
    
    @property
    def is_output(self) -> bool:
        """Check if this is an output stage plugin"""
        return self.effective_stage == "output"
    
    @property
    def is_data(self) -> bool:
        """Check if this is a data stage plugin"""
        return self.effective_stage == "data"
    
    @property
    def is_parse(self) -> bool:
        """Check if this is a parse stage plugin"""
        return self.effective_stage == "parse"
