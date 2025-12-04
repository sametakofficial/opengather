"""
Manifest Validator

Session 11 - Phase 7: Plugin manifest validation.

Validates:
1. Required fields (name, stage, class_name)
2. Stage validity (input, parse, data, output)
3. Trigger rule validity
4. Provides format (no dynamic variables)
5. Provides conflicts between plugins
"""

from typing import Dict, Any, List, Set, Optional

from .result import ValidationResult, ValidationLevel
from .error_codes import E011, E012, E013, E016, E017, W001


# Valid stage values
VALID_STAGES: Set[str] = {'input', 'parse', 'data', 'output'}

# Valid trigger rules (v2: 'always' removed)
VALID_TRIGGER_RULES: Set[str] = {'all_success', 'one_success', 'all_done', 'all_fail', 'none_fail'}

# Valid provides prefixes (static capabilities)
VALID_PROVIDES_PREFIXES: tuple = (
    'http.',      # HTTP capabilities
    'fs.',        # Filesystem capabilities
    'state.',     # State modification
    'process.',   # Process execution
    'output.',    # Output capabilities
    'metadata.',  # Metadata capabilities
    'custom.',    # Custom capabilities
)


class ManifestValidator:
    """
    Plugin manifest validation.
    
    Validates individual manifests and checks for conflicts
    across all manifests.
    
    Usage:
        validator = ManifestValidator()
        
        # Single manifest
        result = validator.validate(manifest)
        
        # All manifests with conflict detection
        result = validator.validate_all(manifests)
    """
    
    def validate(self, manifest: Dict[str, Any], plugin_name: Optional[str] = None) -> ValidationResult:
        """
        Validate single manifest.
        
        Args:
            manifest: Normalized manifest dict
            plugin_name: Optional plugin name for error paths
            
        Returns:
            ValidationResult
        """
        result = ValidationResult.ok()
        name = plugin_name or manifest.get('name', 'unknown')
        
        # Required fields
        required_fields = ['name', 'stage', 'class_name']
        for field in required_fields:
            if field not in manifest or not manifest[field]:
                result.add_error(
                    E012,
                    f"Missing required field: {field}",
                    path=f"{name}.{field}"
                )
        
        # If required fields missing, stop here
        if not result.valid:
            return result
        
        # Validate stage
        stage = manifest.get('stage', '')
        if stage not in VALID_STAGES:
            result.add_error(
                E013,
                f"Invalid stage: '{stage}'. Must be one of: {', '.join(sorted(VALID_STAGES))}",
                path=f"{name}.stage"
            )
        
        # Validate trigger_rule
        trigger_rule = manifest.get('trigger_rule', 'all_success')
        if trigger_rule not in VALID_TRIGGER_RULES:
            result.add_error(
                E013,
                f"Invalid trigger_rule: '{trigger_rule}'. Must be one of: {', '.join(sorted(VALID_TRIGGER_RULES))}",
                path=f"{name}.trigger_rule"
            )
        
        # Validate requires format
        requires = manifest.get('requires', [])
        if isinstance(requires, list):
            for req in requires:
                if isinstance(req, str):
                    # Requires should reference job.* or run.* or just plugin.path
                    if not self._is_valid_requires_path(req):
                        result.add_warning(
                            W001,
                            f"Requires '{req}' should have job. or run. prefix for clarity",
                            path=f"{name}.requires"
                        )
        
        # Validate provides - no dynamic variables allowed
        provides = manifest.get('provides', [])
        if isinstance(provides, list):
            for prov in provides:
                if isinstance(prov, str):
                    if prov.startswith('job.') or prov.startswith('run.'):
                        result.add_error(
                            E017,
                            f"Provides cannot use dynamic variables: '{prov}'. "
                            f"Use static capability names like http.request, fs.write, etc.",
                            path=f"{name}.provides"
                        )
        
        return result
    
    def validate_all(self, manifests: Dict[str, Dict]) -> ValidationResult:
        """
        Validate all manifests and check for conflicts.
        
        Args:
            manifests: Dict of {plugin_name: manifest}
            
        Returns:
            Combined ValidationResult
        """
        result = ValidationResult.ok()
        
        # Validate each manifest
        for name, manifest in manifests.items():
            manifest_result = self.validate(manifest, plugin_name=name)
            result.merge(manifest_result)
        
        # Check for provides conflicts
        conflict_result = self._check_provides_conflicts(manifests)
        result.merge(conflict_result)
        
        return result
    
    def _check_provides_conflicts(self, manifests: Dict[str, Dict]) -> ValidationResult:
        """Check for duplicate provides values."""
        result = ValidationResult.ok()
        
        # Map: provides_value -> plugin_name
        provides_map: Dict[str, str] = {}
        
        for name, manifest in manifests.items():
            provides = manifest.get('provides', [])
            
            if not isinstance(provides, list):
                continue
            
            for prov in provides:
                if not isinstance(prov, str):
                    continue
                
                if prov in provides_map:
                    existing = provides_map[prov]
                    result.add_error(
                        E016,
                        f"Provides conflict: '{prov}' declared by both '{existing}' and '{name}'",
                        path=f"{name}.provides"
                    )
                else:
                    provides_map[prov] = name
        
        return result
    
    def _is_valid_requires_path(self, path: str) -> bool:
        """
        Check if requires path has valid format.
        
        Valid formats:
        - job.plugins.renamer.parsed
        - job.input.path
        - run.config.options
        - renamer.parsed (legacy, but warned)
        """
        if path.startswith('job.') or path.startswith('run.'):
            return True
        
        # Legacy format: plugin_name.path - still works but warned
        parts = path.split('.')
        return len(parts) >= 2
