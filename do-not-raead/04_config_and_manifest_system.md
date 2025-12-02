# CONFIG & MANIFEST SYSTEM

```yaml
date: 2025-11-30
sources: v4, v5-part2
status: final
```

---

## 1. İKİ SİSTEM KARŞILAŞTIRMASI

```
config.yml                          manifest.yml
─────────────────────────────────────────────────────────────
Runtime configuration               Static plugin metadata
User edits                          Developer defines
Per-installation                    Per-plugin
Loaded at startup                   Loaded at discovery
Plugin-specific values              Plugin identity + deps
```

---

## 2. CONFIG.YML YAPISI

### 2.1 Schema

```yaml
# config.yml

options:
  debug: bool                    # Default: false
  dry_run: bool                  # Default: false
  hardlink: bool                 # Default: false

plugins:
  {plugin_name}:
    enabled: bool                # Required
    # Plugin-specific config...

tasks:
  - name: string
    type: print | save | summary
    condition: string            # Optional, Jinja2 expression
    template: string             # For print type
    destination: string          # For save type

memory:                          # Optional
  max_state_mb: int              # Default: 500
  flush_strategy: string         # write_through | write_back
  flush_threshold: float         # Default: 0.8
```

### 2.2 Örnek

```yaml
options:
  debug: true
  dry_run: true

plugins:
  scanner:
    enabled: true
    targets:
      - /media/downloads
    recursive: true
    
  renamer:
    enabled: true
    
  tmdb:
    enabled: true
    api_key: ${TMDB_API_KEY}    # .env reference
    language: tr-TR
    
  ffprobe:
    enabled: false

tasks:
  - name: print_movie
    type: print
    condition: "job.plugins.renamer.parsed.movie"
    template: |
      MOVIE: {{ job.plugins.tmdb.movie.title }} ({{ job.plugins.tmdb.movie.release_date[:4] }})
      
  - name: save_movie
    type: save
    condition: "job.plugins.renamer.parsed.movie"
    destination: |
      {{ options.movies_dst }}/{{ job.plugins.tmdb.movie.title }} ({{ job.plugins.tmdb.movie.release_date[:4] }})/{{ job.input.path | basename }}
```

---

## 3. MANIFEST.YML YAPISI

### 3.1 Schema

```yaml
# plugins/{name}/manifest.yml

# Identity
name: string                     # Unique, lowercase, no spaces
version: string                  # Semver (1.0.0)
description: string              # Human readable

# Execution
phase: input | parse | metadata | modify
execution_mode: per_job | batch  # Default: per_job

# Dependencies
requires: List[string]           # Data paths, e.g., "renamer.parsed.movie"

# Implementation
class_name: string               # Python class name
entry_point: string              # Default: "client.py"

# Config schema (optional)
config_schema:
  {field_name}:
    type: string | int | bool | list
    required: bool
    default: any
    description: string
```

### 3.2 Örnek

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
version: 1.0.0
description: Fetches metadata from TMDB API

phase: metadata
execution_mode: batch

requires:
  - renamer.parsed.movie
  - renamer.parsed.show

class_name: TMDbPlugin
entry_point: client.py

config_schema:
  api_key:
    type: string
    required: true
    description: TMDB API key
  language:
    type: string
    required: false
    default: en-US
    description: Response language
```

---

## 4. LOADING FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    CONFIG LOADING                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. load_dotenv()                                            │
│     └── .env → os.environ                                    │
│                                                              │
│  2. raw_config = yaml.load('config.yml')                     │
│                                                              │
│  3. config = resolve_env_vars(raw_config)                    │
│     └── ${VAR} → os.environ['VAR']                           │
│                                                              │
│  4. validate_config(config)                                  │
│     └── Schema validation                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    MANIFEST LOADING                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Scan: plugins/*/manifest.yml                             │
│                                                              │
│  2. For each manifest:                                       │
│     ├── Parse YAML                                           │
│     ├── Validate schema                                      │
│     └── Create PluginManifest object                         │
│                                                              │
│  3. Filter by config:                                        │
│     └── Only plugins with enabled: true                      │
│                                                              │
│  4. Build registry:                                          │
│     └── name → PluginManifest                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. CONFIG + MANIFEST MERGE

```
┌─────────────────────────────────────────────────────────────┐
│                    PLUGIN CONFIGURATION                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  manifest.yml (static)                                       │
│  ├── name: tmdb                                              │
│  ├── phase: metadata                                         │
│  ├── requires: [renamer.parsed.movie]                        │
│  └── config_schema:                                          │
│      ├── api_key: {required: true}                           │
│      └── language: {default: en-US}                          │
│                                                              │
│                         +                                    │
│                                                              │
│  config.yml (runtime)                                        │
│  └── plugins.tmdb:                                           │
│      ├── enabled: true                                       │
│      ├── api_key: ${TMDB_API_KEY}                            │
│      └── language: tr-TR                                     │
│                                                              │
│                         =                                    │
│                                                              │
│  Plugin Instance                                             │
│  ├── manifest: PluginManifest                                │
│  └── config:                                                 │
│      ├── enabled: true                                       │
│      ├── api_key: "abc123..."  (resolved)                    │
│      └── language: "tr-TR"                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. VALIDATION

### 6.1 Config Validation

```python
class ConfigValidator:
    def validate(self, config: Dict) -> List[ValidationError]:
        errors = []
        
        # Options section
        if 'options' in config:
            errors.extend(self._validate_options(config['options']))
        
        # Plugins section
        if 'plugins' in config:
            for name, plugin_config in config['plugins'].items():
                errors.extend(self._validate_plugin_config(name, plugin_config))
        
        # Tasks section
        if 'tasks' in config:
            for i, task in enumerate(config['tasks']):
                errors.extend(self._validate_task(i, task))
        
        return errors
```

### 6.2 Manifest Validation

```python
class ManifestValidator:
    REQUIRED_FIELDS = ['name', 'version', 'phase', 'class_name']
    VALID_PHASES = ['input', 'parse', 'metadata', 'modify']
    VALID_MODES = ['per_job', 'batch']
    
    def validate(self, manifest: Dict) -> List[ValidationError]:
        errors = []
        
        # Required fields
        for field in self.REQUIRED_FIELDS:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")
        
        # Phase validation
        if manifest.get('phase') not in self.VALID_PHASES:
            errors.append(f"Invalid phase: {manifest.get('phase')}")
        
        # Execution mode
        mode = manifest.get('execution_mode', 'per_job')
        if mode not in self.VALID_MODES:
            errors.append(f"Invalid execution_mode: {mode}")
        
        return errors
```

### 6.3 Config Schema Validation

```python
class ConfigSchemaValidator:
    """Validate plugin config against manifest.config_schema"""
    
    def validate(self, plugin_config: Dict, schema: Dict) -> List[str]:
        errors = []
        
        for field, rules in schema.items():
            value = plugin_config.get(field)
            
            # Required check
            if rules.get('required') and value is None:
                errors.append(f"Missing required config: {field}")
                continue
            
            # Type check
            if value is not None:
                expected_type = rules.get('type', 'string')
                if not self._check_type(value, expected_type):
                    errors.append(f"Invalid type for {field}: expected {expected_type}")
        
        return errors
```

---

## 7. ENV VARIABLE RESOLUTION

```python
import os
import re

def resolve_env_vars(config: Dict) -> Dict:
    """Resolve ${VAR} patterns in config values"""
    
    def resolve_value(value):
        if isinstance(value, str):
            # Match ${VAR} or ${VAR:-default}
            pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
            
            def replacer(match):
                var_name = match.group(1)
                default = match.group(2) or ''
                return os.environ.get(var_name, default)
            
            return re.sub(pattern, replacer, value)
        
        elif isinstance(value, dict):
            return {k: resolve_value(v) for k, v in value.items()}
        
        elif isinstance(value, list):
            return [resolve_value(v) for v in value]
        
        return value
    
    return resolve_value(config)
```

---

## 8. DATACLASS MODELS

```python
@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    phase: str
    execution_mode: str
    requires: List[str]
    class_name: str
    entry_point: str
    config_schema: Dict[str, Any]
    
    @classmethod
    def from_yaml(cls, path: Path) -> 'PluginManifest':
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls(
            name=data['name'],
            version=data['version'],
            description=data.get('description', ''),
            phase=data['phase'],
            execution_mode=data.get('execution_mode', 'per_job'),
            requires=data.get('requires', []),
            class_name=data['class_name'],
            entry_point=data.get('entry_point', 'client.py'),
            config_schema=data.get('config_schema', {})
        )

@dataclass
class TaskConfig:
    name: str
    type: str                    # print, save, summary
    condition: Optional[str]
    template: Optional[str]
    destination: Optional[str]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskConfig':
        return cls(
            name=data['name'],
            type=data['type'],
            condition=data.get('condition'),
            template=data.get('template'),
            destination=data.get('destination')
        )
```

---

## 9. MEVCUT vs YENİ

### plugin.json (mevcut)

```json
{
  "name": "tmdb",
  "version": "1.0.0",
  "category": "output",
  "class_name": "TMDbPlugin",
  "depends_on": ["renamer"],
  "expects": ["renamer.parsed.movie"]
}
```

### manifest.yml (yeni)

```yaml
name: tmdb
version: 1.0.0
description: TMDB metadata fetcher
phase: metadata
execution_mode: batch
requires:
  - renamer.parsed.movie
  - renamer.parsed.show
class_name: TMDbPlugin
config_schema:
  api_key:
    type: string
    required: true
```

**Değişiklikler:**
- JSON → YAML (tutarlılık, config.yml ile aynı format)
- `category` → `phase` (5-phase system)
- `depends_on` kaldırıldı (gereksiz)
- `expects` → `requires`
- `+execution_mode`
- `+config_schema`
- `+description`

---

## 10. MİGRASYON

### 10.1 plugin.json → manifest.yml

```python
def migrate_plugin_json(json_path: Path) -> None:
    with open(json_path) as f:
        data = json.load(f)
    
    # Map category to phase
    phase_map = {
        'input': 'input',
        'output': 'metadata'    # Most outputs are metadata
    }
    
    manifest = {
        'name': data['name'],
        'version': data['version'],
        'description': '',
        'phase': phase_map.get(data.get('category', 'output'), 'metadata'),
        'execution_mode': 'per_job',
        'requires': data.get('expects', []),
        'class_name': data['class_name'],
        'entry_point': 'client.py'
    }
    
    manifest_path = json_path.parent / 'manifest.yml'
    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False)
```

---

**Son Güncelleme:** 2025-11-30
