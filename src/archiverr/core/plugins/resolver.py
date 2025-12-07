"""Dependency Resolver - Build execution graph"""
from typing import Dict, List, Set, Any


class DependencyResolver:
    """Resolves plugin dependencies and creates execution order"""
    
    def __init__(self, plugin_metadata: Dict[str, Dict[str, Any]]):
        self.plugin_metadata = plugin_metadata
    
    def resolve(self, enabled_plugins: List[str]) -> List[List[str]]:
        """
        Resolve dependencies and return execution groups.
        Plugins in same group can run in parallel.
        
        Args:
            enabled_plugins: List of enabled plugin names
            
        Returns:
            List of groups, each group is list of plugin names
        """
        # Build dependency graph
        graph = {}
        for plugin_name in enabled_plugins:
            metadata = self.plugin_metadata.get(plugin_name, {})
            
            # Session 11: Use 'requires' instead of 'depends_on'
            # Support both for backward compatibility
            requires = metadata.get('requires', []) or metadata.get('depends_on', [])
            
            # Extract plugin names from requires paths
            # Examples:
            #   'job.plugins.renamer.parsed' -> 'renamer'
            #   'provides.http.request' -> None (not a plugin dependency)
            #   'renamer' -> 'renamer' (legacy format)
            deps = []
            for req in requires:
                plugin_dep = self._extract_plugin_from_requires(req)
                if plugin_dep and plugin_dep in enabled_plugins:
                    deps.append(plugin_dep)
            
            graph[plugin_name] = deps
        
        # Check for cycles
        if self._has_cycle(graph):
            raise ValueError("Circular dependency detected in plugins")
        
        # Topological sort into groups
        groups = []
        remaining = set(enabled_plugins)
        
        while remaining:
            # Find plugins with no unresolved dependencies
            ready = set()
            for plugin in remaining:
                deps = set(graph[plugin])
                if deps.issubset(set([p for g in groups for p in g])):
                    ready.add(plugin)
            
            if not ready:
                # Should not happen if no cycles
                break
            
            groups.append(sorted(ready))
            remaining -= ready
        
        return groups
    
    def _has_cycle(self, graph: Dict[str, List[str]]) -> bool:
        """Check if dependency graph has cycles using DFS"""
        visited = set()
        rec_stack = set()
        
        def visit(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if visit(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if visit(node):
                return True
        
        return False
    
    def _extract_plugin_from_requires(self, require: str) -> str:
        """
        Extract plugin name from a requires path.
        
        Session 11 format examples:
            'job.plugins.renamer.parsed' -> 'renamer'
            'job.plugins.tmdb.movie' -> 'tmdb'
            'provides.http.request' -> None (capability, not plugin)
            'events.job.created' -> None (event, not plugin)
            'renamer' -> 'renamer' (legacy direct plugin name)
            
        Returns:
            Plugin name or None if not a plugin dependency
        """
        if not require:
            return None
        
        # Check for job.plugins.{plugin_name}.{path} format
        if require.startswith('job.plugins.'):
            parts = require.split('.')
            if len(parts) >= 3:
                return parts[2]  # job.plugins.{plugin_name}
        
        # Skip provides.* and events.* (not plugin dependencies)
        if require.startswith('provides.') or require.startswith('events.'):
            return None
        
        # Skip job.input.* and job.output.* (not plugin dependencies)
        if require.startswith('job.input.') or require.startswith('job.output.'):
            return None
        
        # Legacy format: direct plugin name
        # Only if it doesn't contain dots (to avoid false positives)
        if '.' not in require:
            return require
        
        return None
    
    def get_dependencies(self, plugin_name: str) -> List[str]:
        """Get direct dependencies of a plugin"""
        metadata = self.plugin_metadata.get(plugin_name, {})
        requires = metadata.get('requires', []) or metadata.get('depends_on', [])
        
        deps = []
        for req in requires:
            plugin_dep = self._extract_plugin_from_requires(req)
            if plugin_dep:
                deps.append(plugin_dep)
        
        return deps
    
    def check_expects(self, plugin_name: str, available_data: Set[str]) -> bool:
        """
        Check if plugin's expects are satisfied.
        
        Args:
            plugin_name: Plugin to check
            available_data: Set of available data keys (e.g., {'input', 'ffprobe.video'})
            
        Returns:
            True if all expects are satisfied
        """
        metadata = self.plugin_metadata.get(plugin_name, {})
        expects = metadata.get('expects', [])
        
        for expect in expects:
            if expect not in available_data:
                return False
        
        return True
