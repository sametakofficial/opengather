# MANIFEST SCHEMA - FINAL SPEC

```yaml
date: 2025-12-02
type: technical-spec
status: final
```

---

## 1. CURRENT STATE

```yaml
# plugins/tmdb/manifest.yml (existing)
name: tmdb
version: 1.0.0
category: output
class_name: TMDbPlugin
depends_on: [renamer]
expects: [renamer.parsed]
categories: [movie, show]
config_schema: {...}
```

**Problems:**
- `category` too generic (input/output only)
- `depends_on` duplicates `expects` logic
- No execution mode declaration
- No stage/phase information

---

## 2. PROPOSED SCHEMA

```yaml
# plugins/{name}/manifest.yml
name: string                    # required, lowercase, [a-z0-9_-]+
version: string                 # required, semver
description: string             # optional

# Execution
stage: input | parse | metadata | output
mode: per_job | per_run         # default: per_job

# Dependencies (DAG)
requires: [string]              # data paths: renamer.parsed
provides: [string]              # capabilities: data.metadata

# Implementation
class_name: string              # required
entry_point: string             # default: client.py

# Config validation
config_schema:                  # optional
  field_name:
    type: string | int | bool | list | dict
    required: bool
    default: any
```

---

## 3. INDUSTRY COMPARISON

```
+------------------+----------------+----------------+----------------+
| System           | Dependencies   | Capabilities   | Execution      |
+------------------+----------------+----------------+----------------+
| Home Assistant   | dependencies   | -              | integration_   |
|                  | after_deps     |                | type           |
+------------------+----------------+----------------+----------------+
| Grafana          | dependencies   | -              | type           |
|                  | .plugins[]     |                | (panel/app)    |
+------------------+----------------+----------------+----------------+
| VSCode           | extension      | contributes    | activation     |
|                  | Dependencies   | capabilities   | Events         |
+------------------+----------------+----------------+----------------+
| Archiverr        | requires       | provides       | stage + mode   |
+------------------+----------------+----------------+----------------+
```

**Decision:** Follow Home Assistant simplicity + VSCode capabilities pattern.

---

## 4. SCHEMA RATIONALE

### 4.1 stage vs category

```
CURRENT: category = input | output
         Too coarse, no execution order semantics

PROPOSED: stage = input | parse | metadata | output
          Clear execution pipeline
```

```
+---------+    +-------+    +----------+    +--------+
|  INPUT  | -> | PARSE | -> | METADATA | -> | OUTPUT |
+---------+    +-------+    +----------+    +--------+
  scanner      renamer       tmdb/tvdb       tasker
```

### 4.2 requires vs depends_on

```
CURRENT:
  depends_on: [renamer]           # plugin name
  expects: [renamer.parsed]       # data path

PROBLEM: Redundant. If you expect renamer.parsed, you implicitly depend on renamer.

PROPOSED:
  requires: [renamer.parsed]      # data path only
  
RESOLUTION: Orchestrator derives plugin order from data dependencies.
```

### 4.3 provides - Standard Values

```
REJECTED (from 15_final_architecture.md):
  - input.files          # too specific
  - parsed.movie         # archiverr-specific
  - metadata.movie       # archiverr-specific
  - output.moved         # action-specific

PROPOSED (industry-aligned):
  Category      Values                    Description
  ----------------------------------------------------------------
  data          data.input                Input data (scanner)
                data.parsed               Parsed data (renamer)
                data.metadata             Metadata (tmdb)
                data.media_info           Media info (ffprobe)
  
  io            io.read                   File read capability
                io.write                  File write capability
                io.delete                 File delete capability
  
  network       network.http              HTTP requests
                network.api               External API calls

RATIONALE:
  - Generic, not archiverr-specific
  - Matches common capability patterns
  - Enables future extensibility
```

---

## 5. EXECUTION FLOW SCHEMA

```
                           MANIFEST LOADING
                                 |
                                 v
+----------------------------------------------------------------+
|                        DISCOVERY                                |
|  1. Scan plugins/*/manifest.yml                                |
|  2. Validate with Pydantic                                     |
|  3. Build plugin registry                                      |
+----------------------------------------------------------------+
                                 |
                                 v
+----------------------------------------------------------------+
|                      DEPENDENCY RESOLUTION                      |
|  1. Parse requires fields                                      |
|  2. Build DAG (directed acyclic graph)                         |
|  3. Topological sort                                           |
|  4. Group by stage                                             |
+----------------------------------------------------------------+
                                 |
                                 v
+----------------------------------------------------------------+
|                       STAGE EXECUTION                           |
|                                                                 |
|  for stage in [INPUT, PARSE, METADATA, OUTPUT]:                |
|      plugins = get_plugins_for_stage(stage)                    |
|      sorted_plugins = topological_sort(plugins)                |
|                                                                 |
|      for plugin in sorted_plugins:                             |
|          if plugin.mode == PER_RUN:                            |
|              plugin.execute_run(services)                      |
|          else:                                                 |
|              for job in jobs:                                  |
|                  if check_requires(plugin, job):               |
|                      plugin.execute(job, services)             |
|                  else:                                         |
|                      skip(plugin, job)                         |
+----------------------------------------------------------------+
```

---

## 6. MIGRATION PATH

```
STEP 1: Keep existing manifest.yml files working
        - category: output -> stage: metadata (inferred)
        - depends_on ignored (use requires)
        - expects -> requires (alias)

STEP 2: Update manifest schema validation
        - Warn on deprecated fields
        - Accept both old and new format

STEP 3: Migrate plugins one by one
        - scanner: stage: input, mode: per_run
        - renamer: stage: parse
        - tmdb: stage: metadata
        - tasker: stage: output

STEP 4: Remove deprecated field support
```

---

## 7. EXAMPLE MANIFESTS

### 7.1 Scanner (Input Plugin)

```yaml
name: scanner
version: 1.0.0
stage: input
mode: per_run
provides: [data.input]
class_name: ScannerPlugin

config_schema:
  targets:
    type: list
    required: true
  recursive:
    type: bool
    default: false
```

### 7.2 Renamer (Parse Plugin)

```yaml
name: renamer
version: 1.0.0
stage: parse
mode: per_job
requires: [data.input]
provides: [data.parsed]
class_name: RenamerPlugin
```

### 7.3 TMDb (Metadata Plugin)

```yaml
name: tmdb
version: 1.0.0
stage: metadata
mode: per_job
requires: [data.parsed]
provides: [data.metadata, network.api]
class_name: TMDbPlugin

config_schema:
  api_key:
    type: string
    required: true
    secret: true
```

### 7.4 Tasker (Output Plugin)

```yaml
name: tasker
version: 1.0.0
stage: output
mode: per_job
requires: [data.metadata]
provides: [io.write]
class_name: TaskerPlugin

config_schema:
  tasks:
    type: list
    required: true
```

---

## 8. VALIDATION RULES

```python
# Manifest validation (Pydantic)
class ManifestValidator:
    def validate(self, manifest: dict) -> ValidationResult:
        errors = []
        
        # Required fields
        if not manifest.get('name'):
            errors.append('name is required')
        if not manifest.get('stage'):
            errors.append('stage is required')
        
        # Stage enum
        if manifest.get('stage') not in ['input', 'parse', 'metadata', 'output']:
            errors.append(f'invalid stage: {manifest.get("stage")}')
        
        # Mode enum
        mode = manifest.get('mode', 'per_job')
        if mode not in ['per_job', 'per_run']:
            errors.append(f'invalid mode: {mode}')
        
        # Provides validation (optional)
        for provide in manifest.get('provides', []):
            if not self._is_valid_capability(provide):
                errors.append(f'unknown capability: {provide}')
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
```

---

## CHANGELOG

```
- Removed: depends_on (redundant with requires)
- Removed: expects (renamed to requires)
- Removed: categories (media types - plugin decides internally)
- Changed: category -> stage (execution phase)
- Added: mode (per_job | per_run)
- Added: provides (standardized capabilities)
```

---

**Status: FINAL - Ready for implementation**
