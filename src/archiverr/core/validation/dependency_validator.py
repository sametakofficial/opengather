"""
Dependency Validator

- Phase 7: Plugin dependency graph validation.

Validates:
1. Missing dependencies (plugin requires unknown plugin)
2. Circular dependencies (A → B → A)
3. Topological sort validity
"""

from collections import defaultdict

from .error_codes import E014, E015
from .result import ValidationLevel, ValidationResult


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

    def validate(self, manifests: dict[str, dict]) -> ValidationResult:
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

    def _build_dependency_graph(self, manifests: dict[str, dict]) -> dict[str, set[str]]:
        """
        Build dependency graph from requires.
        
        Parses requires paths to extract plugin dependencies:
        - job.plugins.renamer.parsed → depends on 'renamer'
        - renamer.parsed → depends on 'renamer' (legacy)
        
        Returns:
            Dict mapping plugin_name → set of dependency plugin names
        """
        graph: dict[str, set[str]] = defaultdict(set)

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

    def _extract_plugin_from_requires(self, req: str) -> str | None:
        """
        Extract plugin name from requires path.
        
        Examples:
        - job.plugins.renamer.parsed → renamer
        - job.plugins.tmdb.movie.title → tmdb
        - renamer.parsed → renamer (legacy)
        - provides.state.update → None (not a plugin dependency)
        """
        # Skip provides-based requires
        if req.startswith('provides.'):
            return None

        # New format: job.plugins.{plugin}.{path}
        if req.startswith('job.plugins.'):
            parts = req.split('.')
            if len(parts) >= 3:
                return parts[2]  # The plugin name

        # Legacy format: {plugin}.{path}
        parts = req.split('.')
        if len(parts) >= 2:
            return parts[0]

        return None

    def _check_missing_deps(
        self,
        graph: dict[str, set[str]],
        available: set[str]
    ) -> ValidationResult:
        """Check for dependencies on non-existent plugins."""
        result = ValidationResult.ok()

        for plugin, deps in graph.items():
            for dep in deps:
                if dep not in available:
                    result.add_error(
                        E014,
                        f"Plugin '{plugin}' requires '{dep}' which is not available",
                        level=ValidationLevel.WARNING
                    )

        return result

    def _check_circular_deps(
        self,
        graph: dict[str, set[str]],
        available: set[str]
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
        color: dict[str, int] = dict.fromkeys(available, WHITE)

        def dfs(node: str, path: list[str]) -> list[str] | None:
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

    def get_execution_order(self, manifests: dict[str, dict]) -> list[str]:
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
        # in_degree[X] = number of dependencies X must wait for
        # If A requires B, then in_degree[A] += 1 (A must wait for B)
        in_degree: dict[str, int] = dict.fromkeys(available, 0)

        for node, deps in graph.items():
            # node requires each dep, so node must wait for len(deps) plugins
            in_degree[node] = len([d for d in deps if d in available])

        # Start with nodes that have no dependencies (in_degree == 0)
        # These are the "root" plugins that can run first
        queue = [n for n in available if in_degree[n] == 0]
        order: list[str] = []

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

    def get_dependencies(self, manifests: dict[str, dict], plugin_name: str) -> set[str]:
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

    def get_dependents(self, manifests: dict[str, dict], plugin_name: str) -> set[str]:
        """
        Get all plugins that depend on a specific plugin.
        
        Args:
            manifests: All manifests
            plugin_name: Plugin to find dependents for
            
        Returns:
            Set of plugin names that depend on this plugin
        """
        graph = self._build_dependency_graph(manifests)
        dependents: set[str] = set()

        for name, deps in graph.items():
            if plugin_name in deps:
                dependents.add(name)

        return dependents
