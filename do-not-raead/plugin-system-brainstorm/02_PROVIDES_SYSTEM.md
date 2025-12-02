# PROVIDES SYSTEM - CAPABILITY DECLARATION

```yaml
date: 2025-12-02
type: technical-spec
status: final
```

---

## 1. CURRENT STATE

```yaml
# 15_final_architecture.md (rejected)
provides:
  - input.files
  - parsed.movie
  - parsed.show
  - metadata.movie
  - metadata.show
  - output.moved
  - output.copied
  - output.linked
```

**Problems:**
- Too archiverr-specific (movie, show)
- Mixes data types with actions
- Not extensible
- No industry precedent

---

## 2. INDUSTRY RESEARCH

### 2.1 OSGi Bundle Capabilities

```
osgi.service;objectClass=org.example.MyService
osgi.wiring.package;osgi.wiring.package=org.example.api
osgi.ee;osgi.ee="JavaSE-11"
```

### 2.2 Gradle Capabilities

```kotlin
capabilities {
    providesCapability("org.example:feature:1.0")
}
```

### 2.3 npm/package.json

```json
{
  "exports": {
    ".": "./index.js",
    "./utils": "./utils.js"
  }
}
```

### 2.4 VSCode Contributes

```json
{
  "contributes": {
    "commands": [...],
    "languages": [...],
    "menus": [...]
  }
}
```

**Pattern:** Generic capability categories, not domain-specific values.

---

## 3. PROPOSED CAPABILITY TAXONOMY

```
CATEGORY        VALUE               DESCRIPTION
----------------------------------------------------------------
data            data.input          Raw input (scanner output)
                data.parsed         Parsed/structured data
                data.metadata       External metadata
                data.mediainfo      Media technical info

io              io.read             Reads files
                io.write            Writes files
                io.delete           Deletes files
                io.rename           Renames files
                io.move             Moves files

network         network.http        Makes HTTP requests
                network.api         Calls external APIs

transform       transform.parse     Parses/extracts data
                transform.format    Formats output
                transform.validate  Validates data
```

---

## 4. CAPABILITY RESOLUTION SCHEMA

```
                    PROVIDES FLOW
                         |
                         v
+------------------------------------------------------------+
|                    PLUGIN EXECUTION                         |
|                                                             |
|  scanner.execute() returns:                                |
|    PluginResult(provides=['data.input'])                   |
|                            |                                |
|                            v                                |
|  Orchestrator tracks:                                      |
|    available_capabilities = {'data.input'}                 |
|                            |                                |
|                            v                                |
|  renamer.requires = ['data.input']                         |
|  check: 'data.input' in available_capabilities             |
|  result: True -> execute renamer                           |
|                            |                                |
|                            v                                |
|  renamer.execute() returns:                                |
|    PluginResult(provides=['data.parsed'])                  |
|                            |                                |
|                            v                                |
|  available_capabilities = {'data.input', 'data.parsed'}    |
+------------------------------------------------------------+
```

---

## 5. REQUIRES/PROVIDES MATCHING

### 5.1 Exact Match (Default)

```yaml
# tmdb/manifest.yml
requires: [data.parsed]

# Job state
available: [data.input, data.parsed]

# Check
'data.parsed' in available -> True -> EXECUTE
```

### 5.2 Any-Of Match

```yaml
# tmdb/manifest.yml
requires:
  any_of: [data.parsed, data.input]

# If either exists -> EXECUTE
```

### 5.3 All-Of Match (Default behavior)

```yaml
# notification/manifest.yml
requires:
  all_of: [data.metadata, io.write]

# Both must exist -> EXECUTE
```

---

## 6. CAPABILITY TRACKING SCHEMA

```
+----------------------------------------------------------------+
|                    CAPABILITY TRACKING                          |
+----------------------------------------------------------------+
|                                                                 |
|  class CapabilityTracker:                                      |
|      def __init__(self):                                       |
|          self._provided: Set[str] = set()                      |
|          self._by_plugin: Dict[str, Set[str]] = {}             |
|                                                                 |
|      def register(self, plugin: str, caps: List[str]):         |
|          self._by_plugin[plugin] = set(caps)                   |
|          self._provided.update(caps)                           |
|                                                                 |
|      def check(self, requires: List[str]) -> bool:             |
|          return all(r in self._provided for r in requires)     |
|                                                                 |
|      def get_providers(self, cap: str) -> List[str]:           |
|          return [p for p, c in self._by_plugin.items()         |
|                  if cap in c]                                  |
|                                                                 |
+----------------------------------------------------------------+

EXECUTION FLOW:

  Run Start
      |
      v
  tracker = CapabilityTracker()
      |
      v
  [INPUT STAGE]
  scanner.execute() -> tracker.register('scanner', ['data.input'])
      |
      v
  [PARSE STAGE]
  tracker.check(['data.input']) -> True
  renamer.execute() -> tracker.register('renamer', ['data.parsed'])
      |
      v
  [METADATA STAGE]
  tracker.check(['data.parsed']) -> True
  tmdb.execute() -> tracker.register('tmdb', ['data.metadata', 'network.api'])
      |
      v
  [OUTPUT STAGE]
  tracker.check(['data.metadata']) -> True
  tasker.execute() -> tracker.register('tasker', ['io.write'])
```

---

## 7. PROVIDES VS DATA PATH

```
IMPORTANT DISTINCTION:

  requires: [data.parsed]      # Capability check
  vs
  requires: [renamer.parsed]   # Data path check (old style)

RECOMMENDATION: Use capability-based requires for loose coupling.

Example:
  # Tight coupling (avoid)
  requires: [renamer.parsed.movie]
  
  # Loose coupling (preferred)  
  requires: [data.parsed]
  
WHY:
  - Any plugin providing data.parsed can satisfy the requirement
  - Allows swapping renamer with alternative parsers
  - More flexible plugin ecosystem
```

---

## 8. RUNTIME PROVIDES DECLARATION

```python
# Plugin can declare provides at runtime based on result

class TMDbPlugin(OutputPlugin):
    def execute(self, job: Job, services: Services) -> PluginResult:
        if self._found_movie(job):
            return PluginResult.success(
                data={'movie': {...}},
                provides=['data.metadata', 'data.metadata.movie']
            )
        elif self._found_show(job):
            return PluginResult.success(
                data={'show': {...}},
                provides=['data.metadata', 'data.metadata.show']
            )
        else:
            return PluginResult.skipped('No match found')
```

---

## 9. VALIDATION

```python
VALID_CAPABILITIES = {
    # Data
    'data.input',
    'data.parsed', 
    'data.metadata',
    'data.mediainfo',
    
    # IO
    'io.read',
    'io.write',
    'io.delete',
    'io.rename',
    'io.move',
    
    # Network
    'network.http',
    'network.api',
    
    # Transform
    'transform.parse',
    'transform.format',
    'transform.validate',
}

def validate_provides(provides: List[str]) -> List[str]:
    errors = []
    for cap in provides:
        if cap not in VALID_CAPABILITIES:
            # Allow sub-capabilities like data.metadata.movie
            base = cap.rsplit('.', 1)[0]
            if base not in VALID_CAPABILITIES:
                errors.append(f'Unknown capability: {cap}')
    return errors
```

---

## 10. EXAMPLE USAGE

```yaml
# Scanner
provides: [data.input]

# Renamer  
requires: [data.input]
provides: [data.parsed, transform.parse]

# TMDb
requires: [data.parsed]
provides: [data.metadata, network.api]

# FFProbe
requires: [data.input]
provides: [data.mediainfo]

# Tasker
requires: [data.metadata]
provides: [io.write, transform.format]
```

```
DEPENDENCY GRAPH:

  data.input -----> data.parsed -----> data.metadata
       |                                     |
       |                                     v
       +-----------> data.mediainfo      io.write
```

---

## CHANGELOG

```
- Removed: archiverr-specific provides (parsed.movie, etc.)
- Added: Generic capability categories (data, io, network, transform)
- Added: Capability tracking system
- Added: Runtime provides declaration
- Added: Validation against known capabilities
```

---

**Status: FINAL - Ready for implementation**
