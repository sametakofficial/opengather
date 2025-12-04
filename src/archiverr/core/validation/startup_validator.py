"""
Startup Validator

Session 11 - Phase 7: Orchestrates all startup validations.

Combines:
1. Config validation (schema, semantic, security)
2. Manifest validation (fields, stages, provides)
3. Dependency validation (circular, missing)
4. Additional startup checks (input plugins)
"""

from typing import Dict, Any, List, Optional

from .result import ValidationResult
from .config_validator import ConfigValidator
from .manifest_validator import ManifestValidator
from .dependency_validator import DependencyValidator
from .error_codes import W004


class StartupValidator:
    """
    Orchestrates all startup validations.
    
    Runs validations in order:
    1. Config validation (stops if invalid)
    2. Manifest validation (for all enabled plugins)
    3. Dependency validation (circular deps, missing deps)
    4. Additional checks (input plugins, warnings)
    
    Usage:
        validator = StartupValidator()
        result = validator.validate_startup(config, manifests)
        
        if not result:
            for error in result.errors:
                print(error)
            sys.exit(1)
        
        for warning in result.warnings:
            print(warning)
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize with optional custom schema path.
        
        Args:
            schema_path: Path to config.schema.json
        """
        self._config_validator = ConfigValidator(schema_path)
        self._manifest_validator = ManifestValidator()
        self._dependency_validator = DependencyValidator()
    
    def validate_startup(
        self,
        config: Dict[str, Any],
        manifests: Dict[str, Dict],
        enabled_plugins: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Run all startup validations.
        
        Args:
            config: Loaded config dict
            manifests: Dict of {plugin_name: manifest} for all discovered plugins
            enabled_plugins: Optional list of enabled plugin names (filters manifests)
            
        Returns:
            Combined ValidationResult with all errors and warnings
        """
        result = ValidationResult.ok()
        
        # 1. Config validation
        config_result = self._config_validator.validate(config)
        result.merge(config_result)
        
        # Stop early if config has fatal errors
        if result.has_fatal():
            return result
        
        # 2. Filter manifests to only enabled plugins
        if enabled_plugins is not None:
            filtered_manifests = {
                name: manifest
                for name, manifest in manifests.items()
                if name in enabled_plugins
            }
        else:
            filtered_manifests = manifests
        
        # 3. Manifest validation
        manifest_result = self._manifest_validator.validate_all(filtered_manifests)
        result.merge(manifest_result)
        
        # 4. Dependency validation
        dep_result = self._dependency_validator.validate(filtered_manifests)
        result.merge(dep_result)
        
        # 5. Additional startup checks
        additional_result = self._additional_checks(config, filtered_manifests)
        result.merge(additional_result)
        
        return result
    
    def _additional_checks(
        self,
        config: Dict[str, Any],
        manifests: Dict[str, Dict]
    ) -> ValidationResult:
        """Additional startup checks and warnings."""
        result = ValidationResult.ok()
        
        # Check for input plugin
        input_plugins = [
            name for name, m in manifests.items()
            if m.get('stage') == 'input'
        ]
        
        if not input_plugins:
            result.add_warning(
                W004,
                "No input plugins enabled - no jobs will be created"
            )
        
        # Check for output plugin
        output_plugins = [
            name for name, m in manifests.items()
            if m.get('stage') == 'output'
        ]
        
        if not output_plugins:
            result.add_warning(
                "W005",
                "No output plugins enabled - results won't be persisted"
            )
        
        return result
    
    def get_execution_order(self, manifests: Dict[str, Dict]) -> List[str]:
        """
        Get plugin execution order based on dependencies.
        
        Delegates to DependencyValidator.
        
        Args:
            manifests: Dict of {plugin_name: manifest}
            
        Returns:
            List of plugin names in execution order
        """
        return self._dependency_validator.get_execution_order(manifests)


def validate_at_startup(
    config: Dict[str, Any],
    manifests: Dict[str, Dict],
    enabled_plugins: Optional[List[str]] = None,
    schema_path: Optional[str] = None
) -> ValidationResult:
    """
    Convenience function for startup validation.
    
    Usage:
        result = validate_at_startup(config, manifests)
        if not result:
            raise CriticalError("Validation failed")
    
    Args:
        config: Loaded config
        manifests: All plugin manifests
        enabled_plugins: Optional filter for enabled plugins
        schema_path: Optional custom schema path
        
    Returns:
        ValidationResult
    """
    validator = StartupValidator(schema_path)
    return validator.validate_startup(config, manifests, enabled_plugins)
