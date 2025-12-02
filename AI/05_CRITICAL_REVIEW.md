# CRITICAL REVIEW

```yaml
session: 10
last_update: 2025-11-28
reviewer: AI Strategy Agent
```

---

## SESSION 7-8-9 COMPREHENSIVE REVIEW

### Session 7 Analysis (~50% Complete)

| Claim | Reality | Evidence |
|-------|---------|----------|
| "EventBus DI Refactor" | ⚠️ Partial | Singleton removed but not fully tested |
| "SDK Structure Created" | ✅ Done | `plugins/sdk/` files exist |
| "Workers Skeleton" | ✅ Done | `core/workers/` exists but unused |

### Session 8 Analysis (~60% Complete)

| Claim | Reality | Evidence |
|-------|---------|----------|
| "SDK moved to core/plugin_sdk/" | ❌ WRONG | Actually at `core/plugins/sdk/` |
| "Pydantic validation" | ✅ Done | discovery.py uses PluginManifest |
| "Plugins migrated" | ⚠️ Partial | Only imports changed, not actual usage |
| "ExecutionContext wired" | ⚠️ Partial | Passed to plugins but often ignored |

### Session 9 Analysis (~70% Complete)

| Claim | Reality | Evidence |
|-------|---------|----------|
| "Context-based logging" | ✅ Done | Active plugins use self.debug(), self.info() |
| "TMDb returns PluginResult" | ❌ FALSE | Still returns Dict[str, Any] |
| "emit_task() works" | ❌ Not used | Zero plugins call it |
| "Lifecycle hooks" | ✅ Done | setup/teardown exist, TMDb uses setup() |
| "PLUGIN_SDK.md" | ✅ Done | 334 lines of documentation |
| "SDK unit tests" | ❌ Not done | No tests written |

### Code Evidence - What Changed (Session 9)

```python
# ACTIVE PLUGINS NOW USE CONTEXT (CORRECT):
# scanner/client.py
self.debug("Starting scan", targets=len(targets))  # ✅ Uses context

# tmdb/client.py
self.info("TMDb plugin initialized", api_key_set=bool(self.api_key))  # ✅ Uses context
```

### Code Evidence - What's Still Wrong

```python
# DISABLED PLUGINS STILL USE get_debugger():
# omdb/client.py, tvdb/client.py, tvmaze/client.py
self.debugger = get_debugger()  # ❌ Still wrong

# TMDb DOES NOT RETURN PluginResult:
# tmdb/client.py line 73
def execute(self, match_data: Dict[str, Any]) -> Dict[str, Any]:  # ❌ Should be PluginResult
    return {
        'status': {...},
        'movie': {...}
    }  # ❌ Returns dict, not PluginResult

# emit_task() NEVER CALLED:
# grep -r "self.emit_task" src/archiverr/plugins/ → 0 results

# Core components still use get_debugger():
# discovery.py line 35, loader.py line 14, executor.py line 21
self.debugger = get_debugger()  # ❌ Should use DI
```

---

## CRITICAL ISSUES

### 1. Plugin-Context Disconnect (SEVERITY: CRITICAL)

**Problem:** ExecutionContext geçiriliyor ama pluginler ignore ediyor.

**Executor (does this):**
```python
context = ExecutionContext(...)
plugin.set_context(context)  # ✅ Sets context
```

**Plugin (ignores it):**
```python
def __init__(self, config):
    self.debugger = get_debugger()  # ❌ Ignores context

def execute(self, match_data):
    self.debugger.info(...)  # ❌ Uses standalone debugger
    # Never touches self.context
```

**Impact:**
- emit_task() broken
- emit_progress() broken
- Per-plugin events broken
- Centralized logging broken

### 2. No PluginResult Usage (SEVERITY: HIGH)

**Current State:**
```python
# TMDb returns raw dict
return {
    'status': {...},
    'movie': {...}
}
```

**Should Return:**
```python
return PluginResult(
    success=True,
    data={'movie': {...}},
    started_at=start,
    finished_at=datetime.now()
)
```

**Impact:**
- No standardized error handling
- No timing metrics standardization
- Response format inconsistent

### 3. Missing Lifecycle Hooks (SEVERITY: MEDIUM)

**Current:** Only `execute()` method

**Missing:**
- `setup()` - Initialize resources (API clients, caches)
- `teardown()` - Cleanup resources
- `on_config()` - Config validation/modification
- `on_before_execute()` - Pre-processing
- `on_after_execute()` - Post-processing

**Impact:**
- No resource initialization point
- No cleanup mechanism
- Memory leaks possible

### 4. No Capability Declaration (SEVERITY: MEDIUM)

**Current plugin.yml:**
```yaml
name: tmdb
category: output
depends_on: [renamer]
expects: [renamer.parsed]
```

**Missing:**
```yaml
capabilities:
  - metadata.movie
  - metadata.show
  - validation.duration

provides:
  - movie
  - show
  - episode
  - normalized
```

**Impact:**
- Core can't know what plugin provides
- No capability-based routing
- No validation of plugin outputs

### 5. Config Validation Missing (SEVERITY: MEDIUM)

**Current:** Plugin config passed as raw dict

**Missing:** Schema validation per-plugin

```yaml
config_schema:
  api_key:
    type: string
    required: true
    secret: true
```

**Impact:**
- Invalid config causes runtime errors
- No type checking
- Secrets not marked

---

## ARCHITECTURE VIOLATIONS

### 1. Hardcoded Debugger Pattern

**Pattern Found:**
```python
from archiverr.utils.debug import get_debugger

class Plugin:
    def __init__(self):
        self.debugger = get_debugger()  # ❌ GLOBAL STATE
```

**Correct Pattern:**
```python
class Plugin(BasePlugin):
    def execute(self, match_data):
        self.log("info", "message")  # ✅ Uses context
```

### 2. Duplicate Base Classes (Resolved in Session 8)

~~`plugins/base.py` and `plugins/sdk/base.py` were duplicates~~

✅ Fixed: Now only `core/plugin_sdk/base.py` exists

### 3. Sync vs Async Inconsistency

**Current:** All plugins are sync

**Executor:** Uses `asyncio.to_thread(plugin.execute, ...)`

**Problem:** Wrapping sync in async, not true async

**Solution:** Make plugins async-native

---

## SECURITY ISSUES

### 1. API Keys in Config (Already Fixed)

✅ Moved to .env file

### 2. No Secret Marking in Config Schema

**Problem:** Can't distinguish secrets from regular config

**Solution:** Add `secret: true` in config_schema

---

## TECHNICAL DEBT

### 1. No Unit Tests for SDK

**Missing Tests:**
- PluginManifest validation
- PluginResult serialization
- ExecutionContext methods
- BasePlugin lifecycle

### 2. Response Format Inconsistency

**Current:**
- `items` vs `matches`
- `matchGlobals` vs `match_globals`
- Snake_case vs camelCase mixed

### 3. Async/Sync Mixed

**CLI:** Sync with asyncio.run()
**API:** Async with FastAPI

**Problem:** Two execution paths with different behaviors

---

## RECOMMENDATIONS

### Immediate (Session 9)

1. **Remove all `get_debugger()` calls from plugins**
2. **Make plugins use `self.context` for logging**
3. **Convert TMDb to return PluginResult**
4. **Add setup/teardown lifecycle hooks**
5. **Create PLUGIN_SDK.md documentation**

### Short-term (Session 10-11)

1. Make plugins async-native
2. Add capability system
3. Add config schema validation
4. Update omdb/tvmaze/tvdb plugins

### Long-term (Session 12+)

1. Plugin event system (hooks)
2. Plugin marketplace architecture
3. Hot reload support
4. Remote plugin support (HTTP)

---

## METRICS

| Metric | Session 7 | Session 8 | Target |
|--------|-----------|-----------|--------|
| Plugins using context | 0 | 0 | 4 |
| Plugins returning PluginResult | 0 | 0 | 4 |
| Lifecycle hooks | 0 | 0 | 2 |
| Unit test coverage | ~20% | ~20% | 60% |
| Documentation pages | 0 | 0 | 1 |
