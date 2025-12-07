"""Template Manager - Jinja2 rendering with alias support and template functions"""
from jinja2 import Environment, BaseLoader
from typing import Dict, Any, Optional
import re


class TemplateManager:
    """
    Template manager using Jinja2 for variable resolution.
    
    Features:
    - Alias system: User-defined shortcuts in config.yml and plugin.yml
    - Template functions: index:, count:matches, count:path.to.data
    - Plugin data flat access: {{ tmdb.movie.title }}
    
    Alias Resolution:
    1. User aliases from config.yml (highest priority)
    2. Plugin aliases from plugin.yml (self → plugin output)
    3. Default aliases (execution, match, globals, index)
    4. Auto plugin aliases (enabled plugins → match.plugins.X)
    """
    
    # Compile regex patterns once at class level for performance
    _FUNCTION_PATTERN = re.compile(r'\b(index|count):([a-zA-Z0-9_.\[\]]*)')
    _DOLLAR_PATTERN = re.compile(r'\$([a-zA-Z0-9_\.]+)')
    
    # NO DEFAULT ALIASES - System provides only SYSTEM_ALIASES
    # Users define their own aliases in config.aliases
    # Inline aliases via Jinja2: {% set m = job.plugins.tmdb.movie %}
    # See FINAL_DATASETS.yml default_aliases
    DEFAULT_ALIASES = {}
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        provides_registry: Optional[Any] = None,
        event_bus: Optional[Any] = None
    ):
        self.env = Environment(loader=BaseLoader())
        
        # Store full config for template access ({{ config.ffprobe.timeout }})
        self._config: Dict[str, Any] = config or {}
        
        # Provides registry for {{ provides }} alias (Session 11)
        self._provides_registry = provides_registry
        
        # Event bus for {{ events }} alias (Session 11)
        self._event_bus = event_bus
        
        # User-defined aliases from config.yml
        self._user_aliases: Dict[str, str] = {}
        
        # Plugin aliases from plugin.yml files
        self._plugin_aliases: Dict[str, Dict[str, str]] = {}
        
        # Loaded plugin names (for auto-aliasing)
        self._loaded_plugins: set = set()
        
        # Load user aliases if config provided
        if config:
            self._load_user_aliases(config)
    
    def configure(self, config: Dict[str, Any], loaded_plugins: Dict[str, Any] = None):
        """
        Configure template manager with aliases.
        
        Args:
            config: Full config.yml content
            loaded_plugins: Dict of plugin_name -> plugin metadata
        """
        # Store full config for template access
        self._config = config
        self._load_user_aliases(config)
        
        if loaded_plugins:
            for plugin_name, plugin_meta in loaded_plugins.items():
                self._loaded_plugins.add(plugin_name)
                
                # Load plugin-specific aliases
                plugin_aliases = plugin_meta.get('aliases', {})
                if plugin_aliases:
                    self._plugin_aliases[plugin_name] = plugin_aliases
    
    def _load_user_aliases(self, config: Dict[str, Any]):
        """Load user-defined aliases from config.yml"""
        aliases = config.get('aliases', {})
        if isinstance(aliases, dict):
            self._user_aliases = aliases.copy()
    
    def _resolve_alias_path(self, path: str, context: Dict[str, Any]) -> Any:
        """
        Resolve a dot-notation path in context.
        
        Examples:
            "execution" → context["execution"]
            "renamer.parsed.movie" → context["renamer"]["parsed"]["movie"]
            "globals.status.matches" → context["globals"]["status"]["matches"]
        
        Args:
            path: Dot-notation path string
            context: Template context dict
            
        Returns:
            Resolved value or None if not found
        """
        # Clean up path (remove {{ }} if present)
        path = path.strip('{ }').strip()
        
        # Simple path (no dots)
        if '.' not in path:
            return context.get(path)
        
        # Dot-notation path
        return self._get_nested_value(context, path)
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get nested value from dict using dot-notation.
        
        Args:
            data: Source dict
            path: Dot-notation path (e.g., "parsed.movie.name")
            
        Returns:
            Value at path or None if not found
        """
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            else:
                return None
        
        return current
    
    def render(self, template: str, context: Dict[str, Any], current_index: int = 0) -> str:
        """
        Render template with context data.
        
        NEW Variable resolution (v2):
        - $tmdb.movie.title → match.plugins.tmdb.movie.title
        - $tmdb.globals.status → match.plugins.tmdb.globals.status
        - $globals.status → match.globals.status
        - $options.debug → match.options.debug
        - $tasks → match.tasks
        - $apiresponse.globals.summary → API root globals
        - $100.tmdb.movie → matches[100].plugins.tmdb.movie
        
        Smart routing:
        - Plugin name (tmdb, omdb, etc.) → match.plugins[plugin_name]
        - 'globals' → match.globals
        - 'options' → match.options
        - 'tasks' → match.tasks
        - 'apiresponse' → API root
        
        Args:
            template: Jinja2 template string
            context: Full API response {globals, matches}
            current_index: Current match index
            
        Returns:
            Rendered string
        """
        # Build template context
        matches = context.get('matches', [])
        
        if current_index >= len(matches):
            return ""
        
        current_match = matches[current_index]
        
        # Create Jinja2 context
        api_globals = context.get('globals', {})
        match_globals = current_match.get('globals', {})
        match_output = match_globals.get('output', {})
        match_plugins = current_match.get('plugins', {})
        
        # Get options from api_response.globals.config
        api_config = api_globals.get('config', {})
        global_options = api_config.get('options', {})
        
        # =================================================================
        # SYSTEM ALIASES - EXACTLY 8 (FINAL_DATASETS.yml default_aliases)
        # =================================================================
        # These are the ONLY system-provided aliases. Users define their
        # own aliases in config.aliases or inline with {% set %}
        # =================================================================
        
        jinja_context = {
            # 1. run - Run state
            'run': {
                'id': api_globals.get('status', {}).get('execution_id'),
                'status': api_globals.get('status', {}),
                'config': self._config,
            },
            
            # 2. job - Current job state
            'job': {
                'index': current_index,
                'id': match_globals.get('job_id', f'job_{current_index}'),
                'input': match_globals.get('input', {}),
                'output': match_output,
                'status': match_globals.get('status', {}),
                'plugins': match_plugins,
            },
            
            # 3. jobs - All jobs list
            'jobs': matches,
            
            # 4. plugins - All plugins for current job
            'plugins': match_plugins,
            
            # 5. config - Frozen config snapshot (readonly)
            'config': self._config,
            
            # 6. options - config.options shortcut
            'options': self._config.get('options', {}),
            
            # 7. provides - Active provides registry (readonly)
            'provides': self._get_provides_dict(),
            
            # 8. events - Event bus history (readonly)
            'events': self._get_events_dict(),
            
            # =================================================================
            # ADDITIONAL CONTEXT (not system aliases, but needed for compat)
            # =================================================================
            'index': current_index,
            'total': len(matches),
            'globals': api_globals,  # Legacy compat
            'match_globals': match_globals,  # Legacy compat
            'output': match_output,  # Legacy compat
        }
        
        # Add default aliases (e, m, g)
        for alias, target in self.DEFAULT_ALIASES.items():
            if target in jinja_context:
                jinja_context[alias] = jinja_context[target]
        
        # Add all plugin data from current match FIRST (needed for alias resolution)
        # {{ tmdb.movie }} → match.plugins.tmdb.movie
        # {{ scanner.category }} → match.plugins.scanner.category
        for plugin_name, plugin_data in match_plugins.items():
            jinja_context[plugin_name] = plugin_data
        
        # Add user-defined aliases from config.yml
        # Supports dot-notation: "renamer.parsed.movie" → resolve path in context
        for alias, target in self._user_aliases.items():
            resolved = self._resolve_alias_path(target, jinja_context)
            if resolved is not None:
                jinja_context[alias] = resolved
        
        # Add plugin-specific aliases from plugin.yml files
        for plugin_name, plugin_aliases in self._plugin_aliases.items():
            plugin_data = match_plugins.get(plugin_name, {})
            for alias, target in plugin_aliases.items():
                # Replace "self" with actual plugin data
                if 'self' in target:
                    target_clean = target.replace('{{ self.', '').replace(' }}', '').replace('{{self.', '')
                    resolved = self._get_nested_value(plugin_data, target_clean)
                    if resolved is not None:
                        # Namespace alias: tmdb_movie instead of just movie
                        namespaced_alias = f"{plugin_name}_{alias}"
                        jinja_context[namespaced_alias] = resolved
        
        try:
            # Process template functions first (index:, count:)
            processed_template = self._process_functions(template, context, current_index)
            
            # Then convert $ prefix to Jinja2 syntax (legacy support)
            processed_template = self._process_dollar_syntax(processed_template)
            
            tmpl = self.env.from_string(processed_template)
            return tmpl.render(**jinja_context)
        except Exception as e:
            return f"Template error: {e}"
    
    def _process_functions(self, template: str, context: Dict[str, Any], current_index: int) -> str:
        """
        Process template functions and replace with actual values.
        
        Functions:
        - index: → current match index (0-based)
        - count:matches → total number of matches
        - count:path.to.data → count elements in list at path
        
        Examples:
        - "{{ index: }}" → "{{ 0 }}"
        - "{{ count:matches }}" → "{{ 2 }}"
        - "{{ count:tmdb.movie.genres }}" → "{{ 3 }}"
        - "{{ count:matches[0].tmdb.movie.people.cast }}" → "{{ 15 }}"
        
        Args:
            template: Template string with functions
            context: Full API response
            current_index: Current match index
            
        Returns:
            Template with functions replaced by values
        """
        def function_replacer(match):
            func_name = match.group(1)
            func_arg = match.group(2) if match.lastindex >= 2 else ''
            
            if func_name == 'index':
                # index: returns current index (no arg needed)
                return str(current_index)
            
            elif func_name == 'count':
                # count:matches returns total matches
                if func_arg == 'matches':
                    matches = context.get('matches', [])
                    return str(len(matches))
                
                # count:path.to.data returns element count at path
                try:
                    value = self._resolve_path(func_arg, context, current_index)
                    if isinstance(value, list):
                        return str(len(value))
                    elif isinstance(value, dict):
                        return str(len(value))
                    else:
                        return '0'
                except Exception:
                    return '0'
            
            return match.group(0)  # Unknown function, keep original
        
        # Use pre-compiled pattern for performance
        # Pattern matches: index:, count:matches, count:tmdb.movie.genres, count:matches[0].data
        # Note: index: has no arg (optional group), count: requires arg
        return self._FUNCTION_PATTERN.sub(function_replacer, template)
    
    def _resolve_path(self, path: str, context: Dict[str, Any], current_index: int) -> Any:
        """
        Resolve a path to data in context.
        
        Paths:
        - $.field → context['matches'][current_index]['field']
        - matches[0].field → context['matches'][0]['field']
        - field.subfield → context['matches'][current_index]['field']['subfield']
        
        Args:
            path: Path to resolve
            context: Full API response
            current_index: Current match index
            
        Returns:
            Value at path
        """
        matches = context.get('matches', [])
        
        # Replace $ with current match reference
        if path.startswith('$.'):
            path = path[2:]  # Remove $.
            if current_index >= len(matches):
                return None
            current_data = matches[current_index]
        elif path.startswith('matches['):
            # Handle matches[N].path
            idx_end = path.index(']')
            idx = int(path[8:idx_end])
            if idx >= len(matches):
                return None
            current_data = matches[idx]
            path = path[idx_end + 2:] if idx_end + 1 < len(path) and path[idx_end + 1] == '.' else ''
        else:
            # No prefix, assume current match
            if current_index >= len(matches):
                return None
            current_data = matches[current_index]
        
        # Navigate path
        if not path:
            return current_data
        
        parts = path.split('.')
        for part in parts:
            if isinstance(current_data, dict):
                current_data = current_data.get(part)
                if current_data is None:
                    return None
            else:
                return None
        
        return current_data
    
    def _process_dollar_syntax(self, template: str) -> str:
        """
        Convert $ prefix to Jinja2 syntax with smart routing.
        
        Smart routing logic:
        - $apiresponse.globals.summary → {{ apiresponse.globals.summary }}
        - $globals.status → {{ globals.status }} (match globals)
        - $tmdb.movie.title → {{ tmdb.movie.title }} (plugin data)
        - $100.tmdb.movie → {{ matches[100].plugins.tmdb.movie }}
        - $100.globals.status → {{ matches[100].globals.status }}
        
        Args:
            template: Template with $ syntax
            
        Returns:
            Template with Jinja2 syntax
        """
        def replacer(match):
            var_path = match.group(1)
            
            # Check for indexed access ($100.tmdb.movie)
            if '.' in var_path:
                parts = var_path.split('.')
                first = parts[0]
                
                # Indexed access: $100.tmdb.movie
                if first.isdigit():
                    index = first
                    second = parts[1] if len(parts) > 1 else ''
                    remaining = '.'.join(parts[2:]) if len(parts) > 2 else ''
                    
                    # Route based on second part
                    if second == 'globals':
                        # $100.globals.status → matches[100].globals.status
                        path = f'matches[{index}].globals'
                        if remaining:
                            path += f'.{remaining}'
                        return f'{{{{ {path} }}}}'
                    else:
                        # $100.tmdb.movie → matches[100].plugins.tmdb.movie
                        path = f'matches[{index}].plugins.{second}'
                        if remaining:
                            path += f'.{remaining}'
                        return f'{{{{ {path} }}}}'
                
                # Current match access: $tmdb.movie or $globals.status or $apiresponse.globals
                # Already routed in jinja_context, just pass through
                # - $globals → globals (match.globals)
                # - $tmdb → tmdb (match.plugins.tmdb)
                # - $apiresponse → apiresponse (full API response)
            
            # Normal variable access (no routing needed, context already set up)
            return f'{{{{ {var_path} }}}}'
        
        # Use pre-compiled pattern for performance
        return self._DOLLAR_PATTERN.sub(replacer, template)
    
    def evaluate_condition(self, condition: str, context: Dict[str, Any], current_index: int = 0) -> bool:
        """
        Evaluate Jinja2 condition.
        
        Args:
            condition: Jinja2 condition string
            context: Full API response
            current_index: Current match index
            
        Returns:
            True if condition passes
        """
        if not condition:
            return True
        
        try:
            # Render condition as template
            result = self.render(condition, context, current_index)
            # If template error occurred, condition fails
            if result.startswith("Template error:"):
                return False
            # Empty string or whitespace = False
            return bool(result.strip())
        except Exception:
            return False
    
    def _get_provides_dict(self) -> Dict[str, Any]:
        """
        Get provides registry as dict for template context.
        
        Returns:
            Dict structure: {provide: {plugin: status, ...}, ...}
            Example: {'http.request': {'tmdb': 'completed'}, 'fs.read': {'scanner': 'completed'}}
        """
        if self._provides_registry is None:
            return {}
        
        if hasattr(self._provides_registry, 'to_dict'):
            return self._provides_registry.to_dict()
        
        return {}
    
    def _get_events_dict(self) -> Dict[str, Any]:
        """
        Get event bus history as dict for template context.
        
        Returns:
            Dict structure: {event_type: [event_data, ...], ...}
            Example: {'plugin.completed': [{'plugin_name': 'tmdb', ...}, ...]}
        """
        if self._event_bus is None:
            return {}
        
        # Use get_history_dict for grouped format
        if hasattr(self._event_bus, 'get_history_dict'):
            return self._event_bus.get_history_dict()
        
        return {}
    
    def set_provides_registry(self, provides_registry: Any) -> None:
        """Set the provides registry for template injection."""
        self._provides_registry = provides_registry
    
    def set_event_bus(self, event_bus: Any) -> None:
        """Set the event bus for template injection."""
        self._event_bus = event_bus
