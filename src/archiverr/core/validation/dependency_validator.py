"""
Dependency Validator

Session 11 - Phase 7: Plugin dependency graph validation.

Validates:
1. Missing dependencies (plugin requires unknown plugin)
2. Circular dependencies (A → B → A)
3. Topological sort validity
"""

from typing import Dict, Any, List, Set, Tuple, Optional
from collections import defaultdict

from .result import ValidationResult, ValidationLevel
from .error_codes import E014, E015


class DependencyValidator:
    """
    Validate plugin dependencies.
    
    Checks:
    - Circular dependencies using DFS
    - Missing dependencies (plugin not found)
    - Topological sort validity for execution order
    
    Usage:
        validator = DependencyValidator()
        result = validator.validate(manifests)
        
        # Get execution order
        order = validator.get_execution_order(manifests)
    """
    
    def validate(self, manifests: Dict[str, Dict]) -> ValidationResult:
        """
        Validate dependency graph.
        
        Args:
            manifests: Dict of {plugin_name: manifest}
            
        Returns:
            ValidationResult
        """
        result = ValidationResult.ok()
        
        # Build dependency graph
        graph = self._build_dependency_graph(manifests)
        
        # Available plugins
        available = set(manifests.keys())
        
        # Check for missing dependencies
        missing_result = self._check_missing_deps(graph, available)
        result.merge(missing_result)
        
        # Check for circular dependencies
        circular_result = self._check_circular_deps(graph, available)
        result.merge(circular_result)
        
        return result
    
    def _build_dependency_graph(self, manifests: Dict[str, Dict]) -> Dict[str, Set[str]]:
        """
        Build dependency graph from requires.
        
        Parses requires paths to extract plugin dependencies:
        - job.plugins.renamer.parsed → depends on 'renamer'
        - renamer.parsed → depends on 'renamer' (legacy)
        
        Returns:
            Dict mapping plugin_name → set of dependency plugin names
        """
        graph: Dict[str, Set[str]] = defaultdict(set)
        
        for name, manifest in manifests.items():
            requires = manifest.get('requires', [])
            
            if not isinstance(requires, list):
                continue
            
            for req in requires:
                if not isinstance(req, str):
                    continue
                
                dep_plugin = self._extract_plugin_from_requires(req)
                if dep_plugin and dep_plugin != name:
                    graph[name].add(dep_plugin)
        
        return dict(graph)
    
    def _extract_plugin_from_requires(self, req: str) -> Optional[str]:
        """
        Extract plugin name from requires path.
        
        Examples:
        - job.plugins.renamer.parsed → renamer
        - job.plugins.tmdb.movie.title → tmdb
        - renamer.parsed → renamer (legacy)
        - job.input.path → None (not a plugin dependency)
        - run.config.option → None (not a plugin dependency)
        """
        parts = req.split('.')
        
        if len(parts) < 2:
            return None
        
        # New format: job.plugins.{name}.{path}
        if parts[0] == 'job' and parts[1] == 'plugins' and len(parts) >= 3:
            return parts[2]
        
        # job.input.* or job.output.* - not a plugin dependency
        if parts[0] == 'job' and parts[1] in ('input', 'output', 'status'):
            return None
        
        # run.* - not a plugin dependency
        if parts[0] == 'run':
            return None
        
        # Legacy format: {plugin_name}.{path}
        return parts[0]
    
    def _check_missing_deps(
        self,
        graph: Dict[str, Set[str]],
        available: Set[str]
    ) -> ValidationResult:
        """Check for dependencies on non-existent plugins."""
        result = ValidationResult.ok()
        
        for plugin, deps in graph.items():
            for dep in deps:
                if dep not in available:
                    result.add_error(
                        E014,
                        f"Plugin '{plugin}' depends on unknown plugin '{dep}'",
                        path=f"{plugin}.requires"
                    )
        
        return result
    
    def _check_circular_deps(
        self,
        graph: Dict[str, Set[str]],
        available: Set[str]
    ) -> ValidationResult:
        """
        Check for circular dependencies using DFS.
        
        Uses three-color marking:
        - WHITE (not visited)
        - GRAY (in current path)
        - BLACK (fully processed)
        """
        result = ValidationResult.ok()
        
        # Colors
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {node: WHITE for node in available}
        
        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            """
            DFS to detect cycle.
            Returns cycle path if found, None otherwise.
            """
            color[node] = GRAY
            path.append(node)
            
            for neighbor in graph.get(node, set()):
                if neighbor not in color:
                    # Unknown plugin - already caught by missing deps
                    continue
                
                if color[neighbor] == GRAY:
                    # Found cycle - return the cycle portion
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                
                if color[neighbor] == WHITE:
                    cycle = dfs(neighbor, path.copy())
                    if cycle:
                        return cycle
            
            color[node] = BLACK
            return None
        
        # Check all nodes
        for node in available:
            if color[node] == WHITE:
                cycle = dfs(node, [])
                if cycle:
                    cycle_str = " → ".join(cycle)
                    result.add_error(
                        E015,
                        f"Circular dependency detected: {cycle_str}",
                        level=ValidationLevel.FATAL
                    )
                    # One cycle is enough - stop checking
                    return result
        
        return result
    
    def get_execution_order(self, manifests: Dict[str, Dict]) -> List[str]:
        """
        Get topological execution order.
        
        Uses Kahn's algorithm for topological sort.
        Plugins with no dependencies come first.
        
        Note: This assumes no circular dependencies exist.
        Call validate() first to check.
        
        Args:
            manifests: Dict of {plugin_name: manifest}
            
        Returns:
            List of plugin names in execution order
        """
        graph = self._build_dependency_graph(manifests)
        available = set(manifests.keys())
        
        # Calculate in-degrees
        in_degree: Dict[str, int] = {node: 0 for node in available}
        
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1
        
        # Start with nodes that have no incoming edges (no dependencies)
        # These are the "root" plugins that can run first
        queue = [n for n in available if in_degree[n] == 0]
        order: List[str] = []
        
        while queue:
            # Sort for deterministic ordering
            queue.sort()
            node = queue.pop(0)
            order.append(node)
            
            # Reduce in-degree for nodes that depend on this node
            for dependent, deps in graph.items():
                if node in deps:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        # Nodes not in order are part of cycles (shouldn't happen if validate passed)
        remaining = available - set(order)
        if remaining:
            order.extend(sorted(remaining))
        
        return order
    
    def get_dependencies(self, manifests: Dict[str, Dict], plugin_name: str) -> Set[str]:
        """
        Get all dependencies for a specific plugin.
        
        Args:
            manifests: All manifests
            plugin_name: Plugin to get dependencies for
            
        Returns:
            Set of plugin names this plugin depends on
        """
        graph = self._build_dependency_graph(manifests)
        return graph.get(plugin_name, set())
    
    def get_dependents(self, manifests: Dict[str, Dict], plugin_name: str) -> Set[str]:
        """
        Get all plugins that depend on a specific plugin.
        
        Args:
            manifests: All manifests
            plugin_name: Plugin to find dependents for
            
        Returns:
            Set of plugin names that depend on this plugin
        """
        graph = self._build_dependency_graph(manifests)
        dependents: Set[str] = set()
        
        for name, deps in graph.items():
            if plugin_name in deps:
                dependents.add(name)
        
        return dependents
