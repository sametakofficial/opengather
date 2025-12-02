# CONFIG SYSTEM - FLEXGET-STYLE

```yaml
date: 2025-12-02
type: technical-spec
status: final
```

---

## 1. CURRENT STATE

```yaml
# config.yml (current)
plugins:
  scanner:
    enabled: true
    targets: [/downloads]
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}

tasks:
  - name: print_movie
    type: print
    template: "{{ job.plugins.tmdb.movie.title }}"
```

**Problems:**
- `plugins:` wrapper is verbose
- `enabled: true` is redundant (presence = enabled)
- Not FlexGet-style

---

## 2. PROPOSED CONFIG STYLE

```yaml
# config.yml (FlexGet-inspired)

# Global options
options:
  debug: true
  dry_run: false

# Plugin configs (no wrapper, presence = enabled)
scanner:
  targets: [/downloads]
  recursive: true

renamer: {}  # Empty = use defaults

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

tasker:
  tasks:
    - name: print_movie
      type: print
      template: "{{ job.plugins.tmdb.movie.title }}"

# Disable a plugin explicitly
ffprobe: false
```

---

## 3. CONFIG SCHEMA

```
+------------------------------------------------------------------+
|                      CONFIG STRUCTURE                             |
+------------------------------------------------------------------+
|                                                                   |
|  options:           # Global options                             |
|    debug: bool                                                   |
|    dry_run: bool                                                 |
|    output_dir: string                                            |
|                                                                   |
|  {plugin_name}:     # Per-plugin config                          |
|    {...}            # Plugin-specific fields                     |
|    OR                                                            |
|    false            # Explicitly disabled                        |
|    OR                                                            |
|    {}               # Enabled with defaults                      |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 4. ENABLE/DISABLE LOGIC

```python
def is_plugin_enabled(config: Dict, plugin_name: str) -> bool:
    """
    Determine if plugin is enabled based on config.
    
    Rules:
    1. Not in config -> disabled
    2. value is False -> disabled
    3. value is {} or {...} -> enabled
    """
    if plugin_name not in config:
        return False
    
    value = config[plugin_name]
    
    if value is False:
        return False
    
    if value is None:
        return True  # Presence = enabled
    
    if isinstance(value, dict):
        # Check for explicit enabled: false
        if value.get('enabled') is False:
            return False
        return True
    
    return False
```

```
EXAMPLES:

  scanner:                  # ENABLED (has config)
    targets: [/downloads]

  renamer: {}               # ENABLED (empty dict)
  
  renamer: null             # ENABLED (null = use defaults)
  
  renamer:                  # ENABLED (implicit null)
  
  ffprobe: false            # DISABLED
  
  omdb:                     # DISABLED (explicitly)
    enabled: false
    api_key: xxx
  
  # Not in config           # DISABLED
```

---

## 5. ENV VAR RESOLUTION

```yaml
# Syntax
tmdb:
  api_key: ${TMDB_API_KEY}
  fallback: ${OPTIONAL_KEY:-default_value}

# Resolution order
1. ${VAR}           -> os.environ['VAR'] or error
2. ${VAR:-default}  -> os.environ.get('VAR', 'default')
```

```python
def resolve_env_vars(config: Dict) -> Dict:
    """Recursively resolve ${VAR} patterns"""
    
    pattern = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')
    
    def resolve(value):
        if isinstance(value, str):
            def replacer(match):
                var_name = match.group(1)
                default = match.group(2)
                env_value = os.environ.get(var_name)
                if env_value is not None:
                    return env_value
                if default is not None:
                    return default
                raise ConfigError(f"Missing env var: {var_name}")
            return pattern.sub(replacer, value)
        elif isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [resolve(v) for v in value]
        return value
    
    return resolve(config)
```

---

## 6. CONFIG LOADING FLOW

```
+------------------------------------------------------------------+
|                    CONFIG LOADING                                 |
+------------------------------------------------------------------+
|                                                                   |
|  1. READ                                                         |
|     config.yml -> raw YAML                                       |
|                                                                   |
|  2. ENV RESOLUTION                                               |
|     ${TMDB_API_KEY} -> actual value                              |
|     Store original for snapshot                                  |
|                                                                   |
|  3. PLUGIN DISCOVERY                                             |
|     for key in config:                                           |
|         if key in discovered_plugins:                            |
|             mark as enabled                                      |
|                                                                   |
|  4. MANIFEST MERGE                                               |
|     for plugin in enabled_plugins:                               |
|         manifest = load_manifest(plugin)                         |
|         merged = {**manifest.defaults, **config[plugin]}         |
|                                                                   |
|  5. VALIDATION                                                   |
|     for plugin in enabled_plugins:                               |
|         validate(config[plugin], manifest.config_schema)         |
|                                                                   |
|  6. RETURN                                                       |
|     resolved config                                              |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 7. TASKER CONFIG (Replaces tasks:)

```yaml
# OLD STYLE
tasks:
  - name: print_movie
    type: print
    template: "..."

# NEW STYLE (tasker is a plugin)
tasker:
  tasks:
    - name: print_movie
      type: print
      template: "..."
    
    - name: save_movie
      type: save
      condition: "{{ job.plugins.tmdb.movie }}"
      destination: "{{ options.movies_dst }}/{{ job.plugins.tmdb.movie.title }}"
```

**Rationale:** Tasker as plugin = consistent model, can be replaced with alternative.

---

## 8. EXTERNAL CONFIG IMPORT

```yaml
# Main config with imports
scanner:
  !include ./scanner.yml

tasker:
  tasks:
    !include_list ./tasks/
```

```yaml
# ./scanner.yml
targets:
  - /downloads/movies
  - /downloads/shows
recursive: true
```

```yaml
# ./tasks/movie.yml
name: save_movie
type: save
condition: "{{ job.plugins.renamer.parsed.movie }}"
destination: "/movies/{{ job.plugins.tmdb.movie.title }}"
```

---

## 9. CONFIG LOADER IMPLEMENTATION

```python
class ConfigLoader:
    def load(self, path: Path) -> Config:
        # 1. Load raw YAML with include support
        raw = self._load_with_includes(path)
        
        # 2. Store original for snapshot (with ${VAR})
        self._original = copy.deepcopy(raw)
        
        # 3. Resolve env vars
        resolved = self._resolve_env_vars(raw)
        
        # 4. Extract sections
        options = resolved.pop('options', {})
        
        # 5. Identify plugins
        plugins = {}
        for key, value in resolved.items():
            if self._is_plugin(key):
                if value is False:
                    continue  # Disabled
                plugins[key] = value or {}
        
        # 6. Merge with manifests
        for name, config in plugins.items():
            manifest = self._load_manifest(name)
            plugins[name] = self._merge(manifest.defaults, config)
        
        # 7. Validate
        for name, config in plugins.items():
            self._validate(name, config)
        
        return Config(options=options, plugins=plugins)
    
    def _load_with_includes(self, path: Path) -> Dict:
        """Load YAML with !include and !include_list support"""
        yaml.add_constructor('!include', self._include_constructor)
        yaml.add_constructor('!include_list', self._include_list_constructor)
        
        with open(path) as f:
            return yaml.safe_load(f)
```

---

## 10. VALIDATION ERROR MESSAGES

```
CONFIG VALIDATION ERRORS:

[ERROR] tmdb.api_key: required field missing
[ERROR] scanner.targets: must be a list
[ERROR] tasker.tasks[0].type: invalid value 'unknown', expected one of: print, save
[WARN]  ffprobe: plugin not found, will be ignored
```

---

## 11. FULL CONFIG EXAMPLE

```yaml
# config.yml

options:
  debug: true
  dry_run: false
  movies_dst: /media/movies
  shows_dst: /media/shows

# Input plugin
scanner:
  targets:
    - /downloads
  recursive: true

# Parse plugin (use defaults)
renamer: {}

# Metadata plugins
tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

ffprobe: {}

# Disabled
tvdb: false
omdb: false

# Output plugin
tasker:
  tasks:
    - name: print_movie
      type: print
      condition: "{{ job.plugins.renamer.parsed.movie }}"
      template: |
        MOVIE: {{ job.plugins.tmdb.movie.title }}
        YEAR: {{ job.plugins.tmdb.movie.release_date[:4] }}
    
    - name: save_movie
      type: save
      condition: "{{ job.plugins.tmdb.movie }}"
      destination: |
        {{ options.movies_dst }}/{{ job.plugins.tmdb.movie.title }} ({{ job.plugins.tmdb.movie.release_date[:4] }})/{{ job.input.path | basename }}
```

---

## CHANGELOG

```
- Removed: plugins: wrapper
- Removed: enabled: true (presence = enabled)
- Changed: tasks: -> tasker.tasks
- Added: {plugin}: false for explicit disable
- Added: !include and !include_list support
- Added: ${VAR:-default} syntax for optional env vars
```

---

**Status: FINAL - Ready for implementation**
