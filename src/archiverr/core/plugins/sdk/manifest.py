"""
Plugin Manifest - Pydantic model for manifest.yml validation.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# Valid stages
VALID_STAGES = Literal["input", "parse", "data", "output"]

# Valid trigger rules
VALID_TRIGGER_RULES = Literal["all_success", "one_success", "all_done", "all_fail", "none_fail"]


class PluginManifest(BaseModel):
    name: str = Field(..., description="Plugin name (lowercase, no spaces)")
    version: str = Field(default="1.0.0", description="Semantic version (e.g., 1.0.0)")
    description: str | None = Field(None, description="Human-readable description")
    class_name: str | None = Field(None, description="Python class name")
    entry_point: str | None = Field(default="client.py", description="Entry point file")

    stage: VALID_STAGES | None = Field(None, description="Execution stage (input, parse, data, output)")
    run_mode: Literal["per_run", "per_job"] | None = Field(None, description="Plugin execution mode")
    requires: list[str] = Field(default_factory=list, description="Required data paths (job.plugins.X.field)")
    trigger_rule: VALID_TRIGGER_RULES | None = Field(default="all_success", description="When to run")
    reactive: bool = Field(default=False, description="Whether plugin reacts to events")

    categories: list[str] = Field(default_factory=list, description="DEPRECATED — UI-summary only; superseded by `emits` field. To be removed in a future sprint.")
    provides: list[str] = Field(default_factory=list, description="What this plugin provides")

    # Data namespace contribution (S38 R15 §A1)
    # Plugin declares which data paths it emits, grouped by category.
    # Example: emits = {"show": ["title.primary", "identifiers.imdb_id"], "movie": ["title.primary"]}
    # Used by:
    #   - data_resolver (longest-prefix priority resolution in render context)
    #   - template_dependency_validator (parse-time WARN if config references undeclared plugin)
    # Optional — plugins can opt out of the data namespace by leaving this None/empty.
    emits: dict[str, list[str]] | None = Field(
        default=None,
        description="Data paths this plugin emits, grouped by category. "
                    "e.g. {'show': ['title.primary'], 'movie': ['title.primary']}. "
                    "Optional; opt-in for participation in `data.*` resolver namespace."
    )

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
    def require_stage_and_run_mode(self):
        if self.stage is None:
            raise ValueError(
                f"Plugin '{self.name}': manifest must declare 'stage' explicitly "
                f"(one of input, parse, data, output)"
            )
        if self.run_mode is None:
            raise ValueError(
                f"Plugin '{self.name}': manifest must declare 'run_mode' explicitly "
                f"(per_run or per_job)"
            )
        return self

    @property
    def effective_stage(self) -> str:
        return self.stage

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
