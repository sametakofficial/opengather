# PHASE 6: CONFIG & MANIFEST

```yaml
phase: 6
öncelik: 🟡 ORTA
tahmini_süre: 4-6 saat
bağımlılık: P3 (Plugin Services), P5 (Stage Executor)
strateji_belgesi: 04_config_manifest_and_external_tasks.md
test_türü: unit + integration
```

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P3 tamamlandı (PluginServices çalışıyor)
- [ ] P5 tamamlandı (StageExecutor stage bazlı çalışıyor)
- [ ] Manifest'te stage field gerekli
- [ ] Unit testler PASS

---

## 1. MEVCUT DURUM

### 1.1 Mevcut Config Yapısı: `config.yml`

```yaml
# MEVCUT config.yml
options:
  debug: true
  dry_run: false

plugins: # ← KALDIRILACAK wrapper
  scanner:
    enabled: true # ← KALDIRILACAK
    targets:
      - /downloads/movies

  tmdb:
    enabled: true # ← KALDIRILACAK
    api_key: ${TMDB_API_KEY}

  tvdb: false # Disabled plugin
```

### 1.2 Mevcut Manifest Yapısı

```yaml
# plugins/tmdb/manifest.yml (MEVCUT)
name: tmdb
version: 1.0.0
category: output # ← stage olacak
depends_on: [renamer] # ← kaldırılacak
expects: # ← requires olacak
  - renamer.parsed.movie
  - renamer.parsed.show
class_name: TMDbPlugin
entry_point: client.py
```

### 1.3 Mevcut Config Loader

```python
# utils/config_loader.py (MEVCUT)
def load_config_with_tracking(path: str) -> dict:
    with open(path) as f:
        config = yaml.safe_load(f)

    # Env var expansion
    config = expand_env_vars(config)

    return config
```

### 1.4 Sorunlar

1. **Gereksiz Nesting:** `plugins:` wrapper
2. **Verbose:** Her plugin için `enabled: true`
3. **Eksik !include:** Dizin include yok
4. **Manifest Uyumsuz:** category vs stage, expects vs requires

---

## 2. HEDEF YAPI

### 2.1 Yeni Config Yapısı (FlexGet Style)

```yaml
# config.yml (YENİ - FlexGet style)

# Global options
options:
  debug: true
  dry_run: false
  hardlink: false

# Aliases for templates
aliases:
  m: job.plugins.tmdb.movie
  s: job.plugins.tmdb.show
  p: job.plugins.renamer.parsed
  video: job.plugins.ffprobe.video

# Plugins (top-level, no wrapper)
scanner: # Var = enabled
  targets:
    - /downloads/movies
    - /downloads/shows
  recursive: true

renamer: # Var = enabled
  media_type: auto

tmdb:
  api_key: ${TMDB_API_KEY}
  language: tr-TR

ffprobe:
  timeout: 30

tasker:
  tasks: !include ./tasks/ # Include directive

# Disabled plugins
tvdb: false # Explicit disabled
omdb:
  enabled: false # Alt. disable method
```

### 2.2 Yeni Manifest Yapısı

```yaml
# plugins/tmdb/manifest.yml (YENİ)
name: tmdb
version: 1.0.0
description: TMDb metadata provider

# Stage system (replaces category)
stage: data # input | parse | data | output

# Dependency system (replaces depends_on + expects)
requires:
  - job.plugins.renamer.parsed # Explicit prefix
provides:
  - http.request
  - state.update

# Execution control
trigger_rule: all_success # all_success | one_success | all_done | all_fail | none_fail

# Implementation
class_name: TMDbPlugin
entry_point: client.py

# Config validation (optional)
config_schema:
  api_key:
    type: string
    required: true
  language:
    type: string
    default: en-US
```

### 2.3 Enabled Detection Logic

```
┌─────────────────────────────────────────────────────────────┐
│                    PLUGIN ENABLED DETECTION                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  KURAL 1: Key varsa → ENABLED                               │
│  tmdb:                                                       │
│    api_key: xxx                                             │
│  --> tmdb ENABLED                                           │
│                                                              │
│  KURAL 2: false ise → DISABLED                              │
│  tvdb: false                                                │
│  --> tvdb DISABLED                                          │
│                                                              │
│  KURAL 3: enabled: false ise → DISABLED                     │
│  omdb:                                                       │
│    enabled: false                                           │
│    api_key: xxx                                             │
│  --> omdb DISABLED                                          │
│                                                              │
│  KURAL 4: Key yoksa → DISABLED                              │
│  # ffprobe hiç tanımlı değil                                │
│  --> ffprobe DISABLED                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: Include Directive Loader

**Dosya:** `src/archiverr/utils/yaml_loader.py` (YENİ)

```python
"""Custom YAML loader with !include directive"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Union


class IncludeLoader(yaml.SafeLoader):
    """YAML loader with !include directive support"""

    def __init__(self, stream, base_path: str = None):
        self._base_path = base_path or os.getcwd()
        super().__init__(stream)


def include_constructor(loader: IncludeLoader, node: yaml.Node) -> Union[Dict, List]:
    """
    Handle !include directive.

    Syntax:
      !include ./file.yml      - Single file
      !include ./directory/    - All .yml files in directory
    """
    path = loader.construct_scalar(node)
    full_path = os.path.join(loader._base_path, path)

    if os.path.isdir(full_path):
        # Directory include - load all .yml files
        return _load_directory(full_path)
    elif os.path.isfile(full_path):
        # Single file include
        return _load_file(full_path)
    else:
        raise yaml.YAMLError(f"Include path not found: {full_path}")


def _load_file(path: str) -> Dict:
    """Load single YAML file"""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _load_directory(path: str) -> List[Dict]:
    """Load all YAML files in directory"""
    result = []
    for file in sorted(Path(path).glob('*.yml')):
        content = _load_file(str(file))
        if isinstance(content, list):
            result.extend(content)
        elif content:
            result.append(content)
    return result


# Register constructor
IncludeLoader.add_constructor('!include', include_constructor)


def load_yaml_with_includes(path: str) -> Dict:
    """
    Load YAML file with !include directive support.

    Args:
        path: Path to YAML file

    Returns:
        Loaded config dict
    """
    base_path = os.path.dirname(os.path.abspath(path))

    with open(path, 'r', encoding='utf-8') as f:
        # Create loader with base path for relative includes
        loader = IncludeLoader(f, base_path)
        try:
            return loader.get_single_data() or {}
        finally:
            loader.dispose()
```

**Test:**

```python
def test_include_single_file(tmp_path):
    # Create included file
    db_yml = tmp_path / "db.yml"
    db_yml.write_text("host: localhost\nport: 27017")

    # Create main config
    config_yml = tmp_path / "config.yml"
    config_yml.write_text("database: !include ./db.yml")

    config = load_yaml_with_includes(str(config_yml))

    assert config["database"]["host"] == "localhost"
    assert config["database"]["port"] == 27017

def test_include_directory(tmp_path):
    # Create tasks directory
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    (tasks_dir / "task1.yml").write_text("- name: task1\n  type: print")
    (tasks_dir / "task2.yml").write_text("- name: task2\n  type: save")

    # Create main config
    config_yml = tmp_path / "config.yml"
    config_yml.write_text("tasks: !include ./tasks/")

    config = load_yaml_with_includes(str(config_yml))

    assert len(config["tasks"]) == 2
```

---

### ADIM 2: FlexGet Style Config Normalizer

**Dosya:** `src/archiverr/utils/config_normalizer.py` (YENİ)

```python
"""Config normalization for FlexGet-style config"""

from typing import Dict, Any, List, Set


# Reserved top-level keys (not plugins)
RESERVED_KEYS = {'options', 'aliases', 'database', 'logging'}

# Known plugin names (for detection)
KNOWN_PLUGINS = {
    'scanner', 'file-input', 'renamer', 'tmdb', 'tvdb',
    'omdb', 'ffprobe', 'tasker', 'rclone'
}


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize config to internal format.

    Handles:
    - FlexGet style (plugin at top-level)
    - Legacy style (plugins: wrapper)
    - Enabled detection

    Args:
        config: Raw config dict

    Returns:
        Normalized config with _plugins dict
    """
    normalized = config.copy()

    # Check for legacy format
    if 'plugins' in config and isinstance(config['plugins'], dict):
        # Legacy format - extract plugins
        plugins = _normalize_legacy_plugins(config['plugins'])
    else:
        # FlexGet style - extract top-level plugins
        plugins = _extract_top_level_plugins(config)

    # Add normalized plugins
    normalized['_plugins'] = plugins
    normalized['_enabled_plugins'] = [
        name for name, cfg in plugins.items()
        if _is_enabled(cfg)
    ]

    return normalized


def _normalize_legacy_plugins(plugins_dict: Dict) -> Dict[str, Any]:
    """Normalize legacy plugins: format"""
    result = {}
    for name, config in plugins_dict.items():
        if config is False:
            result[name] = {'_enabled': False}
        elif isinstance(config, dict):
            result[name] = {
                **config,
                '_enabled': config.get('enabled', True)
            }
        else:
            result[name] = {'_enabled': True}
    return result


def _extract_top_level_plugins(config: Dict) -> Dict[str, Any]:
    """Extract plugins from FlexGet-style top-level keys"""
    result = {}

    for key, value in config.items():
        # Skip reserved keys
        if key in RESERVED_KEYS:
            continue

        # Skip private keys
        if key.startswith('_'):
            continue

        # Check if it's a known plugin or looks like one
        if key in KNOWN_PLUGINS or _looks_like_plugin(key, value):
            if value is False:
                result[key] = {'_enabled': False}
            elif isinstance(value, dict):
                result[key] = {
                    **value,
                    '_enabled': value.get('enabled', True)
                }
            else:
                result[key] = {'_enabled': True}

    return result


def _looks_like_plugin(key: str, value: Any) -> bool:
    """Heuristic to detect if a key is a plugin"""
    # Plugin names are lowercase with optional hyphens
    if not key.islower() or ' ' in key:
        return False

    # If value is dict with plugin-like keys
    if isinstance(value, dict):
        plugin_keys = {'enabled', 'api_key', 'targets', 'timeout', 'language'}
        return bool(set(value.keys()) & plugin_keys)

    # If value is False, it's a disabled plugin
    if value is False:
        return True

    return False


def _is_enabled(plugin_config: Dict) -> bool:
    """Check if plugin is enabled"""
    return plugin_config.get('_enabled', True)


def get_plugin_config(config: Dict, plugin_name: str) -> Dict[str, Any]:
    """Get normalized config for a plugin"""
    plugins = config.get('_plugins', {})
    return plugins.get(plugin_name, {})


def is_plugin_enabled(config: Dict, plugin_name: str) -> bool:
    """Check if plugin is enabled in config"""
    enabled = config.get('_enabled_plugins', [])
    return plugin_name in enabled
```

**Test:**

```python
def test_flexget_style_detection():
    config = {
        "options": {"debug": True},
        "tmdb": {"api_key": "xxx"},
        "tvdb": False
    }

    normalized = normalize_config(config)

    assert "tmdb" in normalized["_enabled_plugins"]
    assert "tvdb" not in normalized["_enabled_plugins"]
    assert normalized["_plugins"]["tmdb"]["_enabled"] == True
    assert normalized["_plugins"]["tvdb"]["_enabled"] == False

def test_legacy_format_support():
    config = {
        "plugins": {
            "tmdb": {"enabled": True, "api_key": "xxx"},
            "tvdb": {"enabled": False}
        }
    }

    normalized = normalize_config(config)

    assert "tmdb" in normalized["_enabled_plugins"]
    assert "tvdb" not in normalized["_enabled_plugins"]
```

---

### ADIM 3: Manifest Normalizer

**Dosya:** `src/archiverr/core/plugins/manifest_normalizer.py` (YENİ)

```python
"""Manifest normalization for stage-based system"""

from typing import Dict, Any, List, Optional


# Category → Stage mapping (for backward compat)
CATEGORY_TO_STAGE = {
    'input': 'input',
    'output': 'data',  # Most output plugins are data stage
}

# Special mappings for known plugins
PLUGIN_STAGE_MAP = {
    'scanner': 'input',
    'file-input': 'input',
    'renamer': 'parse',
    'tmdb': 'data',
    'tvdb': 'data',
    'omdb': 'data',
    'ffprobe': 'data',
    'tasker': 'output',
    'rclone': 'output',
}


def normalize_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize manifest to new stage-based format.

    Converts:
    - category → stage
    - depends_on → (removed, use requires)
    - expects → requires (with job.plugins. prefix)

    Args:
        manifest: Raw manifest dict

    Returns:
        Normalized manifest
    """
    normalized = manifest.copy()

    # Normalize stage
    if 'stage' not in normalized:
        normalized['stage'] = _infer_stage(manifest)

    # Normalize requires
    if 'requires' not in normalized:
        normalized['requires'] = _convert_expects_to_requires(manifest)

    # Add default provides if missing
    if 'provides' not in normalized:
        normalized['provides'] = _infer_provides(manifest)

    # Add default trigger_rule if missing
    if 'trigger_rule' not in normalized:
        normalized['trigger_rule'] = 'all_success'

    # Remove deprecated fields
    normalized.pop('category', None)
    normalized.pop('depends_on', None)
    normalized.pop('expects', None)

    return normalized


def _infer_stage(manifest: Dict) -> str:
    """Infer stage from category or plugin name"""
    name = manifest.get('name', '')

    # Check known plugin mapping first
    if name in PLUGIN_STAGE_MAP:
        return PLUGIN_STAGE_MAP[name]

    # Fall back to category mapping
    category = manifest.get('category', 'output')
    return CATEGORY_TO_STAGE.get(category, 'data')


def _convert_expects_to_requires(manifest: Dict) -> List[str]:
    """Convert old expects format to new requires format"""
    expects = manifest.get('expects', [])
    requires = []

    for expect in expects:
        # "renamer.parsed.movie" → "job.plugins.renamer.parsed.movie"
        if not expect.startswith('job.'):
            requires.append(f"job.plugins.{expect}")
        else:
            requires.append(expect)

    return requires


def _infer_provides(manifest: Dict) -> List[str]:
    """Infer provides based on stage and plugin type"""
    stage = manifest.get('stage', _infer_stage(manifest))
    name = manifest.get('name', '')

    # Stage-based defaults
    provides_map = {
        'input': ['job.create', 'fs.read'],
        'parse': ['state.update'],
        'data': ['state.update'],
        'output': ['fs.write', 'output.values'],
    }

    # Plugin-specific provides
    plugin_provides = {
        'tmdb': ['http.request', 'state.update'],
        'tvdb': ['http.request', 'state.update'],
        'ffprobe': ['process.execute', 'state.update'],
        'rclone': ['fs.write', 'process.execute'],
    }

    if name in plugin_provides:
        return plugin_provides[name]

    return provides_map.get(stage, ['state.update'])


def validate_manifest(manifest: Dict) -> tuple[bool, Optional[str]]:
    """
    Validate manifest structure.

    Returns:
        (is_valid, error_message)
    """
    required_fields = ['name', 'stage', 'class_name']

    for field in required_fields:
        if field not in manifest:
            return False, f"Missing required field: {field}"

    # Validate stage value
    valid_stages = {'input', 'parse', 'data', 'output'}
    if manifest.get('stage') not in valid_stages:
        return False, f"Invalid stage: {manifest.get('stage')}"

    # Validate trigger_rule value
    valid_rules = {'all_success', 'one_success', 'all_done', 'all_fail', 'none_fail'}
    rule = manifest.get('trigger_rule', 'all_success')
    if rule not in valid_rules:
        return False, f"Invalid trigger_rule: {rule}"

    return True, None
```

**Test:**

```python
def test_manifest_normalization():
    old_manifest = {
        "name": "tmdb",
        "category": "output",
        "depends_on": ["renamer"],
        "expects": ["renamer.parsed.movie"],
        "class_name": "TMDbPlugin"
    }

    normalized = normalize_manifest(old_manifest)

    assert normalized["stage"] == "data"
    assert "job.plugins.renamer.parsed.movie" in normalized["requires"]
    assert "category" not in normalized
    assert "depends_on" not in normalized

def test_manifest_validation():
    valid = {"name": "test", "stage": "data", "class_name": "Test"}
    is_valid, error = validate_manifest(valid)
    assert is_valid == True

    invalid = {"name": "test"}  # Missing stage, class_name
    is_valid, error = validate_manifest(invalid)
    assert is_valid == False
```

---

### ADIM 4: Alias System

**Dosya:** `src/archiverr/core/config/alias_resolver.py` (YENİ)

> **NOT:** AliasResolver config modülünde, core/tasks YOK!
> Task sistemi = tasker plugin (stage: output)

```python
"""Alias resolution for template context"""

from typing import Dict, Any, List


# System-injected aliases (cannot be overridden)
SYSTEM_ALIASES = {
    'job': 'job',
    'jobs': 'jobs',
    'run': 'run',
    'options': 'options',
    'index': 'index',
}

# Short aliases (can be overridden by user)
SHORT_ALIASES = {
    'j': 'job',
    'r': 'run',
    'o': 'options',
}


class AliasResolver:
    """
    Resolve aliases for template context.

    Priority (high to low):
    1. Inline (Jinja2 set)
    2. User (config.aliases)
    3. Short (j, r, o)
    4. System (job, run, options)
    """

    def __init__(self, user_aliases: Dict[str, str] = None):
        self._user_aliases = user_aliases or {}

    def resolve(self, alias: str) -> str:
        """Resolve an alias to its full path"""
        # Check user aliases first
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

        Args:
            base_context: Base context with job, run, etc.

        Returns:
            Context with aliases resolved and injected
        """
        context = base_context.copy()

        # Inject user aliases
        for alias, path in self._user_aliases.items():
            value = self._get_value_by_path(base_context, path)
            if value is not None:
                context[alias] = value

        # Inject short aliases (if not overridden)
        for alias, path in SHORT_ALIASES.items():
            if alias not in context:
                value = self._get_value_by_path(base_context, path)
                if value is not None:
                    context[alias] = value

        return context

    def _get_value_by_path(self, context: Dict, path: str) -> Any:
        """Get value from context using dot notation path"""
        parts = path.split('.')
        current = context

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

        return current


def create_alias_resolver(config: Dict) -> AliasResolver:
    """Create AliasResolver from config"""
    user_aliases = config.get('aliases', {})
    return AliasResolver(user_aliases)
```

**Test:**

```python
def test_alias_resolution():
    resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})

    assert resolver.resolve("m") == "job.plugins.tmdb.movie"
    assert resolver.resolve("j") == "job"
    assert resolver.resolve("unknown") == "unknown"

def test_context_building():
    resolver = AliasResolver({"m": "job.plugins.tmdb.movie"})

    base_context = {
        "job": {
            "plugins": {
                "tmdb": {"movie": {"title": "Test Movie"}}
            }
        }
    }

    context = resolver.build_context(base_context)

    assert context["m"]["title"] == "Test Movie"
    assert context["j"] == base_context["job"]
```

---

### ADIM 5: Updated Config Loader

**Dosya:** `src/archiverr/utils/config_loader.py` (güncelle)

```python
"""Config loading with all features"""

import os
import re
from typing import Dict, Any

from .yaml_loader import load_yaml_with_includes
from .config_normalizer import normalize_config


def load_config_with_tracking(path: str) -> Dict[str, Any]:
    """
    Load and normalize config file.

    Features:
    - !include directive
    - Env var expansion
    - FlexGet style normalization
    - Alias extraction

    Args:
        path: Path to config.yml

    Returns:
        Normalized config dict
    """
    # Load with includes
    config = load_yaml_with_includes(path)

    # Expand environment variables
    config = expand_env_vars(config)

    # Normalize (FlexGet style support)
    config = normalize_config(config)

    return config


def expand_env_vars(config: Any) -> Any:
    """
    Recursively expand environment variables.

    Patterns:
    - ${VAR_NAME}           Required
    - ${VAR_NAME:-default}  With default
    """
    if isinstance(config, str):
        return _expand_string(config)
    elif isinstance(config, dict):
        return {k: expand_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [expand_env_vars(v) for v in config]
    else:
        return config


def _expand_string(value: str) -> str:
    """Expand env vars in a string"""
    # Pattern: ${VAR} or ${VAR:-default}
    pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'

    def replace(match):
        var_name = match.group(1)
        default = match.group(2)

        env_value = os.getenv(var_name)
        if env_value is not None:
            return env_value
        elif default is not None:
            return default
        else:
            raise ValueError(f"Environment variable not set: {var_name}")

    return re.sub(pattern, replace, value)
```

---

## 4. BACKWARD COMPATIBILITY

### 4.1 Config Format Detection

```python
def detect_config_format(config: Dict) -> str:
    """Detect config format: 'flexget' or 'legacy'"""
    if 'plugins' in config and isinstance(config['plugins'], dict):
        return 'legacy'
    return 'flexget'
```

### 4.2 Manifest Format Detection

```python
def detect_manifest_format(manifest: Dict) -> str:
    """Detect manifest format: 'new' or 'legacy'"""
    if 'stage' in manifest:
        return 'new'
    if 'category' in manifest:
        return 'legacy'
    return 'new'  # Assume new if neither
```

### 4.3 Dual Support Period

- Config: Her iki format da desteklenir
- Manifest: `category` varsa `stage`'e dönüştürülür
- Deprecation warning loglanır

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests

```python
# tests/unit/utils/test_config_loader.py

class TestIncludeDirective:
    def test_single_file_include(self, tmp_path):
        """!include ./file.yml çalışmalı"""
        pass

    def test_directory_include(self, tmp_path):
        """!include ./dir/ tüm yml'leri yüklemeli"""
        pass

    def test_nested_include(self, tmp_path):
        """Include içinde include çalışmalı"""
        pass

    def test_missing_include_raises(self, tmp_path):
        """Olmayan dosya hata vermeli"""
        pass


class TestFlexGetStyle:
    def test_top_level_plugin_detection(self):
        """Top-level key plugin olarak algılanmalı"""
        pass

    def test_false_disables_plugin(self):
        """plugin: false → disabled"""
        pass

    def test_enabled_false_disables(self):
        """enabled: false → disabled"""
        pass

    def test_reserved_keys_not_plugins(self):
        """options, aliases, database plugin değil"""
        pass


class TestManifestNormalization:
    def test_category_to_stage(self):
        """category: output → stage: data"""
        pass

    def test_expects_to_requires(self):
        """expects prefix eklenmeli"""
        pass

    def test_provides_inference(self):
        """provides yoksa stage'e göre çıkarılmalı"""
        pass
```

### 5.2 Integration Tests

```python
# tests/integration/config/test_config_loading.py

def test_full_config_loading(tmp_path):
    """Full config loading with all features"""
    # Create config with includes, aliases, FlexGet style
    pass

def test_legacy_config_still_works(tmp_path):
    """Legacy plugins: format hala çalışmalı"""
    pass

def test_mixed_manifest_formats():
    """Eski ve yeni manifest'ler birlikte çalışmalı"""
    pass
```

---

## 6. PHASE 6 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `IncludeLoader` oluşturuldu (!include çalışıyor)
- [ ] Directory include çalışıyor (!include ./dir/)
- [ ] `ConfigNormalizer` oluşturuldu
- [ ] FlexGet style detection çalışıyor
- [ ] Legacy format desteği korundu
- [ ] `ManifestNormalizer` oluşturuldu
- [ ] category → stage dönüşümü çalışıyor
- [ ] expects → requires dönüşümü çalışıyor
- [ ] `AliasResolver` oluşturuldu
- [ ] Env var expansion çalışıyor
- [ ] Unit testler PASS
- [ ] Integration testler PASS

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ Config schema validation (P7'de)
- ❌ Manifest schema validation (P7'de)
- ❌ Plugin migration (manuel, zamanla)

---

## 7. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                    | Belirti          | Çözüm                                 |
| ------------------------ | ---------------- | ------------------------------------- |
| Include path not found   | YAMLError        | Relative path doğru mu kontrol        |
| Circular include         | RecursionError   | Include path tracking ekle            |
| Plugin not detected      | Plugin disabled  | KNOWN_PLUGINS listesine ekle          |
| Env var not set          | ValueError       | Default değer kullan: ${VAR:-default} |
| Manifest validation fail | Plugin load fail | Manifest normalizer kontrol           |

---

## 8. SONRAKİ PHASE'E GEÇİŞ

Phase 6 tamamlandığında:

1. Git commit: `feat(config): add FlexGet style config and !include directive`
2. Git tag: `v0.x.x-phase6`
3. `07_PHASE7_VALIDATION.md` dosyasını oku
4. Validation system tasarımına başla

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/utils/test_config_loader.py` çalıştır
- !include directive çalışıyor mu test et
- Mevcut config.yml hala çalışıyor mu kontrol et
- Plugin manifest'ler normalize ediliyor mu test et
