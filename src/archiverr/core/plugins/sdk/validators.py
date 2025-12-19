"""
Plugin Config Validators - Schema-based configuration validation

Plugins define their config_schema in manifest.yml, and this module
validates user config against that schema at load time.

This keeps the core plugin-agnostic while allowing plugins to define
their own validation rules.

Supported Schema Fields:
- type: string, integer, float, boolean, list, dict
- required: true/false
- default: default value
- pattern: regex pattern (strings only)
- min_length, max_length: length constraints (strings/lists)
- min, max: numeric constraints
- enum: list of allowed values
- not_contains: forbidden characters/substrings
- secret: marks as sensitive (for logging)
- description: human-readable description

Example manifest.yml config_schema:
    config_schema:
      api_key:
        type: string
        required: true
        min_length: 10
        pattern: "^[a-zA-Z0-9_-]+$"
        not_contains: ['"', "'", " "]
        secret: true
        description: API key (no quotes or spaces)
      timeout:
        type: integer
        min: 1
        max: 120
        default: 30
      language:
        type: string
        pattern: "^[a-z]{2}-[A-Z]{2}$"
        default: en-US
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    """Represents a single validation error"""
    field: str
    message: str
    value: Any = None

    def __str__(self) -> str:
        if self.value is not None:
            return f"{self.field}: {self.message} (got: {self._safe_value()})"
        return f"{self.field}: {self.message}"

    def _safe_value(self) -> str:
        """Return safe representation of value (hide secrets)"""
        if self.value is None:
            return "None"
        val_str = str(self.value)
        if len(val_str) > 50:
            return val_str[:47] + "..."
        return val_str


@dataclass
class ValidationResult:
    """Result of config validation"""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)  # Validated config with defaults applied

    def __bool__(self) -> bool:
        return self.valid

    def error_messages(self) -> list[str]:
        """Get list of error messages"""
        return [str(e) for e in self.errors]


class ConfigValidator:
    """
    Validates plugin configuration against schema defined in manifest.yml.
    
    Plugin-agnostic: Core doesn't know what fields mean, just validates them.
    
    Usage:
        validator = ConfigValidator()
        result = validator.validate(user_config, schema)
        if not result.valid:
            for error in result.errors:
                print(f"Config error: {error}")
    """

    # Type mapping for validation
    TYPE_MAP = {
        'string': str,
        'str': str,
        'integer': int,
        'int': int,
        'float': float,
        'number': (int, float),
        'boolean': bool,
        'bool': bool,
        'list': list,
        'array': list,
        'dict': dict,
        'object': dict,
    }

    def validate(
        self,
        config: dict[str, Any],
        schema: dict[str, Any],
        plugin_name: str = "plugin"
    ) -> ValidationResult:
        """
        Validate config against schema.
        
        Args:
            config: User-provided configuration dict
            schema: Schema from manifest.yml config_schema
            plugin_name: Plugin name for error messages
            
        Returns:
            ValidationResult with valid flag, errors, and processed config
        """
        if not schema:
            # No schema defined = no validation
            return ValidationResult(valid=True, config=config.copy())

        errors: list[ValidationError] = []
        warnings: list[str] = []
        validated_config: dict[str, Any] = {}

        # Validate each field defined in schema
        for field_name, field_schema in schema.items():
            if not isinstance(field_schema, dict):
                # Simple type definition (e.g., api_key: string)
                field_schema = {'type': field_schema}

            value = config.get(field_name)
            is_required = field_schema.get('required', False)
            default = field_schema.get('default')
            is_secret = field_schema.get('secret', False)

            # Handle missing value
            if value is None or value == '':
                if is_required:
                    errors.append(ValidationError(
                        field=f"{plugin_name}.{field_name}",
                        message="Required field is missing"
                    ))
                    continue
                elif default is not None:
                    value = default
                else:
                    continue  # Optional field not provided

            # Validate the value
            field_errors = self._validate_field(
                value=value,
                field_name=field_name,
                field_schema=field_schema,
                plugin_name=plugin_name,
                is_secret=is_secret
            )
            errors.extend(field_errors)

            # Add to validated config (only if no errors for this field)
            if not field_errors:
                validated_config[field_name] = value

        # Copy any extra config fields not in schema (plugin might use them)
        for key, value in config.items():
            if key not in validated_config:
                validated_config[key] = value

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            config=validated_config
        )

    def _validate_field(
        self,
        value: Any,
        field_name: str,
        field_schema: dict[str, Any],
        plugin_name: str,
        is_secret: bool = False
    ) -> list[ValidationError]:
        """Validate a single field against its schema"""
        errors: list[ValidationError] = []
        full_field_name = f"{plugin_name}.{field_name}"

        # Don't include secret values in error messages
        safe_value = "***" if is_secret else value

        # Type validation
        expected_type = field_schema.get('type')
        if expected_type:
            type_errors = self._validate_type(value, expected_type, full_field_name, safe_value)
            if type_errors:
                return type_errors  # Stop if type is wrong

        # String validations
        if isinstance(value, str):
            errors.extend(self._validate_string(value, field_schema, full_field_name, safe_value))

        # Numeric validations
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            errors.extend(self._validate_number(value, field_schema, full_field_name, safe_value))

        # List validations
        if isinstance(value, list):
            errors.extend(self._validate_list(value, field_schema, full_field_name, safe_value))

        # Enum validation
        enum_values = field_schema.get('enum')
        if enum_values and value not in enum_values:
            errors.append(ValidationError(
                field=full_field_name,
                message=f"Must be one of: {enum_values}",
                value=safe_value
            ))

        return errors

    def _validate_type(
        self,
        value: Any,
        expected_type: str,
        field_name: str,
        safe_value: Any
    ) -> list[ValidationError]:
        """Validate value type"""
        errors = []

        expected = self.TYPE_MAP.get(expected_type.lower())
        if expected is None:
            # Unknown type, skip validation
            return errors

        if not isinstance(value, expected):
            errors.append(ValidationError(
                field=field_name,
                message=f"Expected type '{expected_type}', got '{type(value).__name__}'",
                value=safe_value
            ))

        return errors

    def _validate_string(
        self,
        value: str,
        schema: dict[str, Any],
        field_name: str,
        safe_value: Any
    ) -> list[ValidationError]:
        """Validate string-specific rules"""
        errors = []

        # min_length
        min_len = schema.get('min_length')
        if min_len is not None and len(value) < min_len:
            errors.append(ValidationError(
                field=field_name,
                message=f"Minimum length is {min_len}, got {len(value)}",
                value=safe_value
            ))

        # max_length
        max_len = schema.get('max_length')
        if max_len is not None and len(value) > max_len:
            errors.append(ValidationError(
                field=field_name,
                message=f"Maximum length is {max_len}, got {len(value)}",
                value=safe_value
            ))

        # pattern (regex)
        pattern = schema.get('pattern')
        if pattern:
            try:
                if not re.match(pattern, value):
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"Does not match required pattern: {pattern}",
                        value=safe_value
                    ))
            except re.error as e:
                # Invalid regex in schema - this is a plugin developer error
                errors.append(ValidationError(
                    field=field_name,
                    message=f"Invalid pattern in schema: {e}",
                    value=safe_value
                ))

        # not_contains (forbidden characters/substrings)
        not_contains = schema.get('not_contains', [])
        if isinstance(not_contains, list):
            for forbidden in not_contains:
                if forbidden in value:
                    errors.append(ValidationError(
                        field=field_name,
                        message=f"Must not contain '{forbidden}'",
                        value=safe_value
                    ))

        # starts_with
        starts_with = schema.get('starts_with')
        if starts_with and not value.startswith(starts_with):
            errors.append(ValidationError(
                field=field_name,
                message=f"Must start with '{starts_with}'",
                value=safe_value
            ))

        # ends_with
        ends_with = schema.get('ends_with')
        if ends_with and not value.endswith(ends_with):
            errors.append(ValidationError(
                field=field_name,
                message=f"Must end with '{ends_with}'",
                value=safe_value
            ))

        return errors

    def _validate_number(
        self,
        value: float,
        schema: dict[str, Any],
        field_name: str,
        safe_value: Any
    ) -> list[ValidationError]:
        """Validate numeric rules"""
        errors = []

        # min
        min_val = schema.get('min')
        if min_val is not None and value < min_val:
            errors.append(ValidationError(
                field=field_name,
                message=f"Minimum value is {min_val}",
                value=safe_value
            ))

        # max
        max_val = schema.get('max')
        if max_val is not None and value > max_val:
            errors.append(ValidationError(
                field=field_name,
                message=f"Maximum value is {max_val}",
                value=safe_value
            ))

        return errors

    def _validate_list(
        self,
        value: list,
        schema: dict[str, Any],
        field_name: str,
        safe_value: Any
    ) -> list[ValidationError]:
        """Validate list rules"""
        errors = []

        # min_length
        min_len = schema.get('min_length')
        if min_len is not None and len(value) < min_len:
            errors.append(ValidationError(
                field=field_name,
                message=f"Minimum items is {min_len}, got {len(value)}",
                value=safe_value
            ))

        # max_length
        max_len = schema.get('max_length')
        if max_len is not None and len(value) > max_len:
            errors.append(ValidationError(
                field=field_name,
                message=f"Maximum items is {max_len}, got {len(value)}",
                value=safe_value
            ))

        # items_type (validate each item type)
        items_type = schema.get('items_type')
        if items_type:
            expected = self.TYPE_MAP.get(items_type.lower())
            if expected:
                for i, item in enumerate(value):
                    if not isinstance(item, expected):
                        errors.append(ValidationError(
                            field=f"{field_name}[{i}]",
                            message=f"Item must be type '{items_type}'",
                            value=item
                        ))

        return errors


# Singleton instance for convenience
_validator = ConfigValidator()


def validate_plugin_config(
    config: dict[str, Any],
    schema: dict[str, Any],
    plugin_name: str = "plugin"
) -> ValidationResult:
    """
    Convenience function to validate plugin config.
    
    Args:
        config: User config from config.yml
        schema: Schema from plugin's manifest.yml
        plugin_name: Plugin name for error messages
        
    Returns:
        ValidationResult
    """
    return _validator.validate(config, schema, plugin_name)
