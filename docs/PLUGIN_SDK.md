# Archiverr Plugin SDK

A comprehensive guide for developing plugins for Archiverr.

## Quick Start

```python
from archiverr.core.plugins import OutputPlugin, PluginResult

class MyPlugin(OutputPlugin):
    async def execute(self, match_data: dict) -> PluginResult:
        self.log("info", "Processing...")
        
        # Access previous plugin data
        renamer = self.get_previous_result("renamer")
        
        # Do work...
        result = {"movie": {"title": "..."}}
        
        return PluginResult.success_result(data=result)
```

## Base Classes

| Class | Purpose |
|-------|---------|
| `InputPlugin` | Collect matches (scanner, file_reader) |
| `OutputPlugin` | Process matches (tmdb, renamer, ffprobe) |

## Plugin Lifecycle

```
1. __init__(config)     # Configuration passed
2. set_context(ctx)     # Context injected (automatic)
3. setup()              # Initialize resources (async, optional)
4. execute(match_data)  # Main execution
5. teardown()           # Cleanup resources (async, optional)
```

## Context Access

Plugins have access to an `ExecutionContext` via `self.context` or convenience methods:

### Logging

```python
# Convenience methods (recommended)
self.debug("Processing file", path="/path/to/file")
self.info("Movie found", title="Inception")
self.warn("Low confidence match", score=0.6)
self.error("API request failed", error=str(e))

# Or via context directly
self.log("info", "message", key=value)
```

### Progress

```python
self.emit_progress(50, "Halfway done")
```

### Task Emission

```python
self.emit_task({
    "type": "print", 
    "template": "Found: {{ data.movie.title }}"
})
```

### Previous Plugin Results

```python
# Get result from a previous plugin
renamer_data = self.get_previous_result("renamer")

# Access parsed info
if renamer_data:
    parsed = renamer_data.get("parsed", {})
    movie = parsed.get("movie")
```

## PluginResult

All plugins should return a `PluginResult` object:

```python
from archiverr.core.plugins import PluginResult
from datetime import datetime

# Success result (recommended factory method)
return PluginResult.success_result(
    data={"movie": {"title": "Inception", "year": 2010}},
    metadata={"api_calls": 3, "cache_hits": 1}
)

# Error result
return PluginResult.error_result("API connection failed")

# Full control
return PluginResult(
    success=True,
    data={"movie": {...}},
    started_at=start_time,
    finished_at=datetime.now(),
    metadata={"api_calls": 3}
)
```

## Plugin Manifest (plugin.yml)

Every plugin needs a manifest file:

```yaml
# plugin.yml
name: my_plugin
version: 1.0.0
description: My custom plugin
category: output  # or 'input'
class_name: MyPlugin

# Dependencies
depends_on:
  - renamer        # Must run after renamer

expects:
  - renamer.parsed # Only run if this data exists

# Capability System
capabilities:
  - metadata.movie
  - metadata.show

provides:
  - movie
  - normalized

# Event System (optional)
hooks:
  - metadata.found

# Config Schema (optional)
config_schema:
  api_key:
    type: string
    required: true
    secret: true
  timeout:
    type: integer
    default: 30
```

## Directory Structure

```
plugins/my_plugin/
├── plugin.yml      # Manifest (required)
├── client.py       # Plugin class (required)
├── __init__.py     # Empty or exports
└── utils/          # Optional helpers
    └── api.py
```

## Input Plugin Example

```python
from archiverr.core.plugins import InputPlugin
from typing import Dict, Any, List

class MyScannerPlugin(InputPlugin):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "my_scanner"
    
    def execute(self) -> List[Dict[str, Any]]:
        """Return list of matches"""
        matches = []
        
        for path in self.config.get("paths", []):
            self.debug("Scanning", path=path)
            matches.append({
                "status": {"success": True, ...},
                "input": {"path": path, "virtual": False}
            })
        
        self.info("Scan complete", found=len(matches))
        return matches
```

## Output Plugin Example

```python
from archiverr.core.plugins import OutputPlugin, PluginResult
from typing import Dict, Any
from datetime import datetime

class MyMetadataPlugin(OutputPlugin):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "my_metadata"
        self.api_key = config.get("api_key", "")
    
    async def setup(self) -> None:
        """Initialize API client"""
        self.api = MyAPIClient(self.api_key)
        self._initialized = True
        self.info("Plugin initialized")
    
    def execute(self, match_data: Dict[str, Any]) -> PluginResult:
        """Fetch metadata"""
        start_time = datetime.now()
        
        # Get input from match
        input_data = match_data.get("input", {})
        path = input_data.get("path", "")
        
        # Get parsed info from renamer
        renamer = match_data.get("renamer", {})
        parsed = renamer.get("parsed", {})
        movie = parsed.get("movie")
        
        if not movie:
            return PluginResult.error_result("No movie data")
        
        # Fetch from API
        self.debug("Searching", name=movie.get("name"))
        result = self.api.search(movie.get("name"))
        
        return PluginResult.success_result(
            data={"movie": result},
            started_at=start_time
        )
    
    async def teardown(self) -> None:
        """Cleanup"""
        if hasattr(self, "api"):
            self.api.close()
```

## Configuration (config.yml)

Plugins are configured in `config.yml`:

```yaml
plugins:
  my_plugin:
    enabled: true
    api_key: "${MY_PLUGIN_API_KEY}"  # Environment variable
    timeout: 30
```

## Best Practices

1. **Always set `self.name`** in `__init__` for proper logging
2. **Use `PluginResult`** for standardized output format
3. **Log with context** using `self.debug()`, `self.info()`, etc.
4. **Handle errors gracefully** - return `PluginResult.error_result()`
5. **Check expectations** before processing (renamer.parsed, etc.)
6. **Use `setup()` for initialization** of API clients, caches
7. **Use `teardown()` for cleanup** of resources

## Migration from Old Pattern

Old pattern:
```python
from archiverr.utils.debug import get_debugger

class MyPlugin:
    def __init__(self, config):
        self.debugger = get_debugger()  # ❌ DON'T
    
    def execute(self, data):
        self.debugger.info("plugin", "msg")  # ❌ DON'T
        return {"status": {...}, ...}  # ❌ raw dict
```

New pattern:
```python
from archiverr.core.plugins import OutputPlugin, PluginResult

class MyPlugin(OutputPlugin):
    def __init__(self, config):
        super().__init__(config)
        self.name = "my_plugin"  # ✅ DO
    
    def execute(self, data) -> PluginResult:
        self.info("msg")  # ✅ DO - uses context
        return PluginResult.success_result(data={...})  # ✅ DO
```

## Testing Plugins

```python
import pytest
from my_plugin.client import MyPlugin

def test_plugin_execute():
    config = {"api_key": "test"}
    plugin = MyPlugin(config)
    
    match_data = {
        "input": {"path": "/test.mkv"},
        "renamer": {"parsed": {"movie": {"name": "Test", "year": 2024}}}
    }
    
    result = plugin.execute(match_data)
    
    assert result.success
    assert "movie" in result.data
```

## SDK Exports

```python
from archiverr.core.plugins import (
    # Base classes
    BasePlugin,
    InputPlugin,
    OutputPlugin,
    
    # Models
    PluginManifest,
    PluginResult,
    ExecutionContext,
    ValidationResult,
    
    # Types
    PluginCategory,
    PluginStatus,
    MediaCategory,
)
```
