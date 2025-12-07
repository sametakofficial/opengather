"""
Alias resolution for template context.

Session 11 - Phase 6: Template shorthand support.

Aliases allow users to define shortcuts for template access:
    aliases:
      m: job.plugins.tmdb.movie
      s: job.plugins.tmdb.show

Then in templates:
    {{ m.title }} instead of {{ job.plugins.tmdb.movie.title }}

Priority (high to low):
1. Inline (Jinja2 {% set %})
2. User-defined (config.aliases)
3. Short aliases (j, r, o)
4. System aliases (job, run, options)
"""

from typing import Dict, Any, List, Optional


# System-injected aliases - always available, cannot be overridden
# TRUTH SOURCE: HUMAN/FINAL_DATASETS.yml default_aliases.system
# EXACTLY 8 aliases - NO MORE, NO LESS
SYSTEM_ALIASES: Dict[str, str] = {
    'run': 'run',            # Run state
    'job': 'job',            # Current job state
    'jobs': 'jobs',          # All jobs list
    'plugins': 'plugins',    # All plugins for current job
    'config': 'config',      # Frozen config snapshot (readonly)
    'options': 'options',    # config.options shortcut (readonly)
    'provides': 'provides',  # Active provides registry (readonly)
    'events': 'events',      # Event bus (readonly)
}

# NO SHORT ALIASES PROVIDED BY SYSTEM
# Users define their own aliases in config.aliases
# See FINAL_DATASETS.yml default_aliases.user: config.aliases
SHORT_ALIASES: Dict[str, str] = {}


class AliasResolver:
    """
    Resolve aliases for template context.
    
    Usage:
        config_aliases = {"m": "job.plugins.tmdb.movie"}
        resolver = AliasResolver(config_aliases)
        
        # Resolve single alias
        path = resolver.resolve("m")  # "job.plugins.tmdb.movie"
        
        # Build context with aliases injected
        context = resolver.build_context({"job": {...}})
        # context["m"] = job.plugins.tmdb.movie value
    """
    
    def __init__(self, user_aliases: Dict[str, str] = None):
        """
        Initialize resolver with user-defined aliases.
        
        Args:
            user_aliases: Dict of alias -> path mappings from config.aliases
        """
        self._user_aliases = user_aliases or {}
        
        # Validate user aliases don't override system aliases
        for alias in self._user_aliases:
            if alias in SYSTEM_ALIASES:
                import warnings
                warnings.warn(
                    f"Alias '{alias}' shadows a system alias and will be ignored"
                )
    
    def resolve(self, alias: str) -> str:
        """
        Resolve an alias to its full path.
        
        Args:
            alias: Alias name
        
        Returns:
            Full path string, or alias itself if not found
        
        Example:
            resolver.resolve("m") → "job.plugins.tmdb.movie"
            resolver.resolve("j") → "job"
            resolver.resolve("unknown") → "unknown"
        """
        # Check user aliases first (highest priority)
        if alias in self._user_aliases:
            return self._user_aliases[alias]
        
        # Check short aliases
        if alias in SHORT_ALIASES:
            return SHORT_ALIASES[alias]
        
        # Check system aliases
        if alias in SYSTEM_ALIASES:
            return SYSTEM_ALIASES[alias]
        
        # No alias found, return as-is
        return alias
    
    def build_context(self, base_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build template context with aliases injected.
        
        Alias values are resolved from base_context using dot notation.
        
        Args:
            base_context: Base context with job, run, etc.
        
        Returns:
            New context dict with alias shortcuts added
        
        Example:
            base = {"job": {"plugins": {"tmdb": {"movie": {"title": "Test"}}}}}
            resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})
            context = resolver.build_context(base)
            # context["m"]["title"] == "Test"
            # context["j"] == base["job"]
        """
        context = base_context.copy()
        
        # Inject user aliases
        for alias, path in self._user_aliases.items():
            # Skip if would override system alias
            if alias in SYSTEM_ALIASES:
                continue
            
            value = self._get_value_by_path(base_context, path)
            if value is not None:
                context[alias] = value
        
        # Inject short aliases (if not overridden by user)
        for alias, path in SHORT_ALIASES.items():
            if alias not in context and alias not in self._user_aliases:
                value = self._get_value_by_path(base_context, path)
                if value is not None:
                    context[alias] = value
        
        return context
    
    def _get_value_by_path(self, context: Dict[str, Any], path: str) -> Any:
        """
        Get value from context using dot notation path.
        
        Args:
            context: Context dict
            path: Dot-separated path like "job.plugins.tmdb.movie"
        
        Returns:
            Value at path or None if not found
        """
        if not path:
            return None
        
        parts = path.split('.')
        current = context
        
        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return None
            elif hasattr(current, part):
                current = getattr(current, part)
            elif hasattr(current, '__getitem__'):
                try:
                    current = current[part]
                except (KeyError, TypeError):
                    return None
            else:
                return None
        
        return current
    
    def get_all_aliases(self) -> Dict[str, str]:
        """
        Get all available aliases (user + short + system).
        
        Returns:
            Dict of alias -> path mappings
        """
        all_aliases = {}
        
        # Add in reverse priority order (so higher priority overwrites)
        all_aliases.update(SYSTEM_ALIASES)
        all_aliases.update(SHORT_ALIASES)
        all_aliases.update(self._user_aliases)
        
        return all_aliases
    
    @property
    def user_aliases(self) -> Dict[str, str]:
        """Get user-defined aliases."""
        return self._user_aliases.copy()


def create_alias_resolver(config: Dict[str, Any]) -> AliasResolver:
    """
    Create AliasResolver from config.
    
    Args:
        config: Application config with optional 'aliases' key
    
    Returns:
        Configured AliasResolver instance
    
    Example:
        config = {"aliases": {"m": "job.plugins.tmdb.movie"}}
        resolver = create_alias_resolver(config)
    """
    user_aliases = config.get('aliases', {})
    
    # Validate alias format
    validated = {}
    for alias, path in user_aliases.items():
        if not isinstance(alias, str) or not isinstance(path, str):
            import warnings
            warnings.warn(f"Invalid alias definition: {alias}={path}")
            continue
        validated[alias] = path
    
    return AliasResolver(validated)


def expand_alias_in_path(path: str, resolver: AliasResolver) -> str:
    """
    Expand alias at the start of a path.
    
    Args:
        path: Path that may start with an alias
        resolver: AliasResolver instance
    
    Returns:
        Path with alias expanded
    
    Example:
        # With alias m = job.plugins.tmdb.movie
        expand_alias_in_path("m.title", resolver)
        # Returns: "job.plugins.tmdb.movie.title"
    """
    if not path:
        return path
    
    parts = path.split('.', 1)
    first = parts[0]
    
    resolved = resolver.resolve(first)
    
    if len(parts) == 1:
        return resolved
    else:
        return f"{resolved}.{parts[1]}"
