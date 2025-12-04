"""
Requires Validator - Plugin dependency validation

Session 11 - Phase 5: Validates that plugin requirements are satisfied
before execution.

Path Format:
- job.input.value - Job input value
- job.plugins.renamer.parsed.movie - Plugin data path
- job.output.values - Output values list
"""

from typing import List, Dict, Any, Optional, Protocol
from dataclasses import dataclass


class PluginDataProvider(Protocol):
    """Protocol for getting plugin data"""
    def get_plugin_data(self, job_id: str, plugin_name: str) -> Dict[str, Any]:
        ...


@dataclass
class RequiresResult:
    """
    Result of requires validation.
    
    Attributes:
        satisfied: True if all requirements are met
        missing: List of missing requirement paths
    """
    satisfied: bool
    missing: List[str]
    
    def __bool__(self) -> bool:
        return self.satisfied


class RequiresValidator:
    """
    Validates plugin requirements before execution.
    
    Checks that all required data paths exist in job state
    or plugin data before allowing a plugin to execute.
    
    Usage:
        validator = RequiresValidator()
        
        # With direct plugin data
        result = validator.validate(job, requires, plugin_cache)
        if not result.satisfied:
            print(f"Missing: {result.missing}")
            skip_plugin()
    
    Path Format:
        - job.input.value: Input path/value
        - job.input.data.filename: Input metadata
        - job.plugins.{name}.{path}: Plugin output data
        - job.output.values: Output paths list
    """
    
    def validate(
        self,
        job: Any,  # JobState
        requires: List[str],
        plugin_data: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> RequiresResult:
        """
        Validate all requires paths exist.
        
        Args:
            job: JobState instance
            requires: List of required paths
            plugin_data: Optional dict of plugin_name -> data (for testing/cache)
            
        Returns:
            RequiresResult with satisfaction status and missing paths
        """
        if not requires:
            return RequiresResult(satisfied=True, missing=[])
        
        missing = []
        for path in requires:
            if not self._path_exists(job, path, plugin_data or {}):
                missing.append(path)
        
        return RequiresResult(
            satisfied=len(missing) == 0,
            missing=missing
        )
    
    def _path_exists(
        self,
        job: Any,
        path: str,
        plugin_data: Dict[str, Dict[str, Any]]
    ) -> bool:
        """
        Check if path exists and has non-null value.
        
        Args:
            job: JobState instance
            path: Dot-notation path (e.g., "job.plugins.renamer.parsed")
            plugin_data: Dict of plugin_name -> data
            
        Returns:
            True if path exists and has value
        """
        parts = path.split('.')
        
        if len(parts) < 2:
            return False
        
        # Path must start with 'job'
        if parts[0] != 'job':
            return False
        
        root = parts[1]
        remaining = parts[2:]
        
        if root == 'plugins':
            return self._check_plugin_path(remaining, plugin_data)
        elif root == 'input':
            return self._check_object_path(job.input, remaining)
        elif root == 'output':
            return self._check_object_path(job.output, remaining)
        elif root == 'status':
            return self._check_object_path(job.status, remaining)
        elif root == 'id':
            return job.id is not None and job.id != ""
        elif root == 'run_id':
            return job.run_id is not None and job.run_id != ""
        elif root == 'index':
            return job.index is not None
        
        return False
    
    def _check_plugin_path(
        self,
        path_parts: List[str],
        plugin_data: Dict[str, Dict[str, Any]]
    ) -> bool:
        """
        Check path in plugin data.
        
        Path format: [plugin_name, ...rest]
        Example: ["renamer", "parsed", "movie"] for job.plugins.renamer.parsed.movie
        """
        if len(path_parts) < 1:
            return False
        
        plugin_name = path_parts[0]
        remaining = path_parts[1:]
        
        if plugin_name not in plugin_data:
            return False
        
        data = plugin_data[plugin_name]
        
        if not remaining:
            return data is not None
        
        return self._navigate_dict(data, remaining) is not None
    
    def _check_object_path(self, obj: Any, path_parts: List[str]) -> bool:
        """Check path exists in object (supports both attr and dict access)"""
        if not path_parts:
            return obj is not None
        
        current = obj
        for part in path_parts:
            if current is None:
                return False
            
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        
        return current is not None
    
    def _navigate_dict(self, data: Dict[str, Any], path_parts: List[str]) -> Optional[Any]:
        """Navigate dict by path parts, return value or None"""
        current = data
        for part in path_parts:
            if not isinstance(current, dict):
                return None
            if part not in current:
                return None
            current = current[part]
        return current
    
    def extract_plugin_names(self, requires: List[str]) -> List[str]:
        """
        Extract plugin names from requires paths.
        
        Useful for dependency ordering.
        
        Args:
            requires: List of requires paths
            
        Returns:
            List of unique plugin names required
        """
        plugins = set()
        for path in requires:
            parts = path.split('.')
            if len(parts) >= 3 and parts[0] == 'job' and parts[1] == 'plugins':
                plugins.add(parts[2])
        return list(plugins)
