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
        """Build dependency graph from each manifest's ``requires`` list.

        See ``_extract_plugin_from_requires`` for the recognised path
        shapes. Anything else (state, events, provides, malformed) is
        treated as a non-dependency and ignored.
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
        """Return the plugin name a ``requires`` entry depends on, or None.

        Recognised shapes:
            ``plugin.<name>.<path>[:success|fail]``        (modern)
            ``plugins.<name>.<path>[:success|fail]``       (alias of above)
            ``job.plugins.<name>.<path>``                  (normalised v1)

        Returns None for non-dependency paths:
            ``provides.<capability>[:state]``
            ``events.<name>[:fired]``
            ``job.input.*``, ``job.output.*``, ``run.*``

        The bare ``<plugin>.<path>`` legacy form was removed in
        session 35 — the matcher rejects ``:success`` on non-plugin
        paths, so the previous fallback was producing fake "plugin"
        dependencies (e.g. ``plugin`` and ``events``) that were
        downgraded to WARNINGs and quietly ignored.
        """
        # Strip optional ":check_value" suffix so prefix matching is clean.
        path = req.split(':', 1)[0].strip()

        # Non-plugin-dependency shapes
        if path.startswith('provides.') or path.startswith('events.'):
            return None
        if (
            path.startswith('job.input.')
            or path.startswith('job.output.')
            or path.startswith('run.')
        ):
            return None

        # Modern: plugin.<name>.<...>
        if path.startswith('plugin.') or path.startswith('plugins.'):
            parts = path.split('.')
            return parts[1] if len(parts) >= 2 and parts[1] else None

        # Normalised v1: job.plugins.<name>.<...>
        if path.startswith('job.plugins.'):
            parts = path.split('.')
            return parts[2] if len(parts) >= 3 and parts[2] else None

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

        Delegates to :class:`archiverr.core.plugins.resolver.DependencyResolver`
        — the single canonical ordering engine. The resolver returns
        dependency-grouped lists; we flatten into a stable topological order
        here.

        Note: Assumes no circular dependencies. Call :meth:`validate` first.

        Args:
            manifests: Dict of {plugin_name: manifest}

        Returns:
            Flat list of plugin names in execution order.
        """
        from archiverr.core.plugins.resolver import DependencyResolver

        available = sorted(manifests.keys())
        if not available:
            return []

        resolver = DependencyResolver(manifests)
        try:
            groups = resolver.resolve(available)
        except ValueError:
            # Circular dep — fallback to deterministic alpha order so validate()
            # can still report the cycle without this helper crashing.
            return available

        order: list[str] = []
        for group in groups:
            order.extend(group)

        remaining = [n for n in available if n not in order]
        order.extend(remaining)
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
