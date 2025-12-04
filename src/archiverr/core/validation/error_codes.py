"""
Validation Error Codes

Session 11 - Phase 7: Standardized error codes for validation.

Error Code Format:
- E0XX: Config errors (E001-E009)
- E01X: Manifest errors (E011-E019)
- E02X: Execution errors (E021-E029)
- W0XX: Warnings (W001-W009)

Each code should have a unique, descriptive message that helps
users understand and fix the issue.
"""

# =============================================================================
# CONFIG ERRORS (E001-E009)
# =============================================================================

E001 = "E001"  # Invalid config schema
E002 = "E002"  # Missing required config field
E003 = "E003"  # Invalid config value type
E004 = "E004"  # Environment variable not set
E005 = "E005"  # Include file not found

# =============================================================================
# MANIFEST ERRORS (E011-E019)
# =============================================================================

E011 = "E011"  # Invalid plugin manifest
E012 = "E012"  # Missing required manifest field
E013 = "E013"  # Invalid stage value
E014 = "E014"  # Plugin dependency not found
E015 = "E015"  # Circular dependency detected
E016 = "E016"  # Provides conflict detected
E017 = "E017"  # Dynamic variable in provides (job.*/run.* FORBIDDEN)

# =============================================================================
# EXECUTION ERRORS (E021-E029)
# =============================================================================

E021 = "E021"  # Requires not satisfied
E022 = "E022"  # Plugin initialization failed
E023 = "E023"  # Plugin execution failed

# =============================================================================
# WARNINGS (W001-W009)
# =============================================================================

W001 = "W001"  # Deprecated config/manifest field used
W002 = "W002"  # Performance warning (e.g., jsonschema not installed)
W003 = "W003"  # Security warning (API key hardcoded in config)
W004 = "W004"  # No input plugins enabled


# =============================================================================
# ERROR MESSAGES
# =============================================================================

ERROR_MESSAGES = {
    # Config
    E001: "Invalid config schema: {detail}",
    E002: "Missing required config field: {field}",
    E003: "Invalid config value type at '{path}': expected {expected}, got {got}",
    E004: "Environment variable not set: ${{{var}}}",
    E005: "Include file not found: {path}",
    
    # Manifest
    E011: "Invalid plugin manifest: {detail}",
    E012: "Missing required manifest field: {field}",
    E013: "Invalid stage value: '{stage}'. Must be one of: input, parse, data, output",
    E014: "Plugin dependency not found: '{plugin}' requires '{dependency}'",
    E015: "Circular dependency detected: {cycle}",
    E016: "Provides conflict: '{capability}' declared by both '{plugin1}' and '{plugin2}'",
    E017: "Dynamic variable in provides: '{value}' (job.*/run.* forbidden in provides)",
    
    # Execution
    E021: "Requires not satisfied: {plugin} needs {missing}",
    E022: "Plugin initialization failed: {plugin} - {error}",
    E023: "Plugin execution failed: {plugin} - {error}",
    
    # Warnings
    W001: "Deprecated {type} used: {name}",
    W002: "Performance warning: {detail}",
    W003: "Security warning: API key appears hardcoded at '{path}'",
    W004: "No input plugins enabled - no jobs will be created",
}


def format_error(code: str, **kwargs) -> str:
    """Format error message with parameters."""
    template = ERROR_MESSAGES.get(code, f"{code}: Unknown error")
    try:
        return template.format(**kwargs)
    except KeyError:
        # Missing parameter - return template with placeholders
        return template
