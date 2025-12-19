"""
Config Validator

- Phase 7: Config validation with error codes.

Validates:
1. JSON Schema (if jsonschema available)
2. Semantic rules (at least one plugin, options structure)
3. Security checks (hardcoded API keys)
"""

import json
from pathlib import Path
from typing import Any

from .error_codes import E001, E002, E003, W002, W003
from .result import ValidationLevel, ValidationResult


class ConfigValidator:
    """
    Config validation with schema and semantic checks.
    
    Validates config.yml against:
    1. JSON Schema (config.schema.json) - structural validation
    2. Semantic rules - logical constraints
    3. Security checks - no hardcoded secrets
    
    Usage:
        validator = ConfigValidator()
        result = validator.validate(config)
        if not result:
            for error in result.errors:
                print(error)
    """

    def __init__(self, schema_path: str | None = None):
        """
        Initialize validator.
        
        Args:
            schema_path: Path to JSON schema file. Defaults to project root.
        """
        if schema_path:
            self._schema_path = Path(schema_path)
        else:
            # Default: config.schema.json in project root
            self._schema_path = Path(__file__).parent.parent.parent.parent.parent / "config.schema.json"

        self._schema: dict | None = None
        self._jsonschema_available = self._check_jsonschema()

    def _check_jsonschema(self) -> bool:
        """Check if jsonschema library is available."""
        import importlib.util
        return importlib.util.find_spec("jsonschema") is not None

    def is_available(self) -> bool:
        """Check if schema validation is available."""
        return self._jsonschema_available and self._schema_path.exists()

    def validate(self, config: dict[str, Any]) -> ValidationResult:
        """
        Validate config against schema and semantic rules.
        
        Args:
            config: Loaded config dict
            
        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult.ok()

        # 1. Schema validation (if available)
        if self.is_available():
            schema_result = self._validate_schema(config)
            result.merge(schema_result)
        elif not self._jsonschema_available:
            result.add_warning(
                W002,
                "jsonschema not installed, skipping schema validation. Install with: pip install jsonschema"
            )

        # 2. Semantic validation
        semantic_result = self._validate_semantic(config)
        result.merge(semantic_result)

        # 3. Security checks
        security_result = self._check_security(config)
        result.merge(security_result)

        return result

    def _validate_schema(self, config: dict) -> ValidationResult:
        """Validate against JSON schema."""
        result = ValidationResult.ok()

        try:
            import jsonschema

            # Load schema if not cached
            if self._schema is None:
                with open(self._schema_path, encoding='utf-8') as f:
                    self._schema = json.load(f)

            # Validate
            jsonschema.validate(config, self._schema)

        except jsonschema.ValidationError as e:
            path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            result.add_error(
                E001,
                f"Schema validation failed: {e.message}",
                path=path
            )
        except json.JSONDecodeError as e:
            result.add_error(
                E001,
                f"Invalid JSON schema file: {e}",
                level=ValidationLevel.FATAL
            )
        except Exception as e:
            result.add_error(
                E001,
                f"Schema validation error: {e}"
            )

        return result

    def _validate_semantic(self, config: dict) -> ValidationResult:
        """Validate semantic rules."""
        result = ValidationResult.ok()

        # Check for enabled plugins
        # Support both FlexGet style (plugin = top-level) and wrapped style (plugins:)
        enabled_plugins = config.get('_enabled_plugins', [])

        # Also check for plugins directly in config
        if not enabled_plugins:
            # Try to detect plugins from top-level keys
            plugins_section = config.get('plugins', {})
            if isinstance(plugins_section, dict):
                for name, plugin_config in plugins_section.items():
                    if isinstance(plugin_config, dict) and plugin_config.get('enabled', False):
                        enabled_plugins.append(name)

        if not enabled_plugins:
            result.add_error(
                E002,
                "No plugins enabled in config",
                path="plugins"
            )

        # Check options structure
        options = config.get('options')
        if options is not None and not isinstance(options, dict):
            result.add_error(
                E003,
                f"options must be a dict, got {type(options).__name__}",
                path="options"
            )

        # Check aliases structure
        aliases = config.get('aliases')
        if aliases is not None and not isinstance(aliases, dict):
            result.add_error(
                E003,
                f"aliases must be a dict, got {type(aliases).__name__}",
                path="aliases"
            )

        # Validate alias paths
        if isinstance(aliases, dict):
            for name, path in aliases.items():
                if isinstance(path, str) and not path.startswith('job.') and not path.startswith('run.'):
                    result.add_warning(
                        "W001",
                        f"Alias '{name}' should start with job. or run. for clarity",
                        path=f"aliases.{name}"
                    )

        return result

    def _check_security(self, config: dict) -> ValidationResult:
        """Check for security issues."""
        result = ValidationResult.ok()

        # Check for hardcoded API keys (not env vars)
        plugins = config.get('plugins', {})

        if isinstance(plugins, dict):
            for name, plugin_config in plugins.items():
                if isinstance(plugin_config, dict):
                    self._check_api_key(result, name, plugin_config)

        # Also check top-level plugin configs (FlexGet style)
        for key, value in config.items():
            if isinstance(value, dict) and key not in ('options', 'plugins', 'aliases', 'tasks'):
                self._check_api_key(result, key, value)

        return result

    def _check_api_key(self, result: ValidationResult, name: str, config: dict) -> None:
        """Check single plugin config for hardcoded API key."""
        api_key = config.get('api_key', '')

        # Check if it's a hardcoded key (not an env var reference)
        if (api_key and isinstance(api_key, str) and 
                not api_key.startswith('${') and not api_key.startswith('$')):
            result.add_warning(
                W003,
                "API key appears to be hardcoded. Use ${ENV_VAR} instead for security.",
                path=f"{name}.api_key"
            )
