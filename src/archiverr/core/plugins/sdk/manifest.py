"""
Plugin Manifest - Pydantic model for plugin.yml/plugin.json validation

Updated to support stage-based format.

Validates plugin manifest files at load time to catch errors early.
"""

import warnings
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# Valid stages
VALID_STAGES = Literal["input", "parse", "data", "output"]

# Valid trigger rules
VALID_TRIGGER_RULES = Literal["all_success", "one_success", "all_done", "all_fail", "none_fail"]


class PluginManifest(BaseModel):
    """
    Pydantic model for plugin manifest validation.
    
    Supports both legacy (category) and new (stage) format.
    
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
    description: str | None = Field(None, description="Human-readable description")
    class_name: str | None = Field(None, description="Python class name")
    entry_point: str | None = Field(default="client.py", description="Entry point file")

    # NEW: Stage-based system ()
    stage: VALID_STAGES | None = Field(None, description="Execution stage (input, parse, data, output)")
    run_mode: Literal["per_run", "per_job"] | None = Field(None, description="Plugin execution mode")
    requires: list[str] = Field(default_factory=list, description="Required data paths (job.plugins.X.field)")
    trigger_rule: VALID_TRIGGER_RULES | None = Field(default="all_success", description="When to run")
    reactive: bool = Field(default=False, description="Whether plugin reacts to events")

    # LEGACY: Category-based system (backward compat)
    category: Literal["input", "output"] | None = Field(None, description="Legacy plugin type")
    depends_on: list[str] = Field(default_factory=list, description="Legacy plugin dependencies")
    expects: list[str] = Field(default_factory=list, description="Legacy expected data paths")

    # Shared fields
    categories: list[str] = Field(default_factory=list, description="Supported media types (movie, show)")
    provides: list[str] = Field(default_factory=list, description="What this plugin provides")

    # Capability system
    capabilities: list[str] = Field(default_factory=list, description="Plugin capabilities")

    # Event system
    hooks: list[str] = Field(default_factory=list, description="Events this plugin emits")
    listens_to: list[str] = Field(default_factory=list, description="Events this plugin handles")

    # Config schema
    config_schema: dict[str, Any] | None = Field(None, description="Configuration schema")

    # FS lock system
    fs_lock: list[str] = Field(default_factory=list, description="Static file paths to lock (no variables)")

    class Config:
        """Pydantic config"""
        extra = "ignore"  # Ignore unknown fields

    @model_validator(mode='after')
    def ensure_stage_or_category(self):
        """Ensure either stage or category is set."""
        if self.stage is None and self.category is not None:
            warnings.warn(
                f"Plugin '{self.name}': 'category' is deprecated, "
                f"use 'stage' in manifest.yml instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        if self.stage is None and self.category is None:
            self.stage = "data"
        if self.run_mode is None:
            self.run_mode = "per_run" if self.effective_stage == "input" else "per_job"
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
