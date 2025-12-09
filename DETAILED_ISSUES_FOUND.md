# Detailed Issues Found in Archiverr Session 12 Refactoring

## 1. HARDCODED PLUGIN NAMES (PLUGIN-AGNOSTIC VIOLATION)

### Issue #1.1: Hardcoded Plugin Names in API Process Executor

**File:** `src/archiverr/api/process_executor.py:85-87`
**Severity:** 🔴 CRITICAL

```python
# Apply target overrides if provided
if targets:
    for plugin_name in ['scanner', 'file_reader', 'file-reader']:  # ← HARDCODED!
        if plugin_name in config.get('plugins', {}):
            config['plugins'][plugin_name]['targets'] = targets
```

**Problem:** API layer has hardcoded knowledge of specific input plugins.

**Fix:**

```python
# Apply target overrides if provided
if targets:
    # Find any enabled input plugin dynamically
    input_plugins = [
        name for name, cfg in config.get('plugins', {}).items()
        if cfg.get('category') == 'input' or cfg.get('stage') is None
    ]
    for plugin_name in input_plugins:
        config['plugins'][plugin_name]['targets'] = targets
```

---

### Issue #1.2: Hardcoded Plugin Names in Execution Service

**File:** `src/archiverr/core/services/execution_service.py:158-160`
**Severity:** 🔴 CRITICAL

```python
# Override targets if provided
if targets:
    # Find the enabled input plugin and override its targets
    for plugin_name in ['scanner', 'file-reader', 'file_reader']:  # ← HARDCODED!
        if plugin_name in config.get('plugins', {}):
            config['plugins'][plugin_name]['targets'] = targets
```

**Same issue as #1.1**

---

### Issue #1.3: Hardcoded Plugin Data Fetching in Tasker

**File:** `src/archiverr/plugins/tasker/plugin.py:76-83`
**Severity:** 🔴 CRITICAL

```python
# Fallback: services.state
if hasattr(services, 'state'):
    for plugin_name in ['renamer', 'ffprobe', 'tmdb', 'tvdb', 'omdb']:  # ← HARDCODED!
        if plugin_name not in plugins_data:
            try:
                data = services.state.get_plugin_data(job.id, plugin_name)
                if data:
                    plugins_data[plugin_name] = data
            except Exception:
                pass
```

**Problem:** Tasker plugin has explicit knowledge of other plugins!

**Fix:**

```python
# Fallback: services.state - get ALL plugin data dynamically
if hasattr(services, 'state'):
    available_plugins = services.state.get_job_plugin_names(job.id)
    for plugin_name in available_plugins:
        if plugin_name not in plugins_data:
            try:
                data = services.state.get_plugin_data(job.id, plugin_name)
                if data:
                    plugins_data[plugin_name] = data
            except Exception:
                pass
```

---

### Issue #1.4: Hardcoded Plugin References in Comments

**File:** `src/archiverr/core/orchestrator.py`
**Severity:** 🟡 MEDIUM

**Line 262:** "They typically create jobs (e.g., scanner plugin)"
**Line 294:** "# Execute plugin (scanner creates jobs via services.createJob)"
**Line 299:** "# Legacy: scanner uses get_matches"

**Problem:** Core orchestrator has comments explicitly mentioning specific plugins.

**Fix:** Use generic terminology:

- "Input plugins create jobs" instead of "scanner creates jobs"
- "per_run plugins" instead of "scanner plugin"

---

## 2. HARDCODED EXECUTION ORDER (CONDITION-BASED EXECUTION MISSING)

### Issue #2.1: Sequential Stage Execution

**File:** `src/archiverr/core/orchestrator.py:156-160`
**Severity:** 🔴 CRITICAL

```python
# Phase 1.5: Execute per_run plugins (Session 12: before stages)
self._execute_per_run_plugins()

# Phase 2: Execute stages (per_job plugins)
self._execute_stages()
```

**Problem:** Hardcoded execution order - per_run always before stages.

**User Requirement:**

> "per run pluginlerde per job larda koşullar sağlandığında direkt çalıştırılır yani bu iş hardcoding bir sıralama ile değil koşullar sağlanma durumunda gore"

**Expected Behavior:**

- Scanner: Execute immediately (no conditions)
- Renamer: Execute when job exists
- TMDb: Execute when renamer completed successfully
- Tasker: Execute when all data plugins completed

**Solution:** Implement condition-based execution engine:

```python
def execute_plugins_by_conditions(self):
    """Execute plugins when their trigger conditions are satisfied."""

    all_plugins = self._get_all_plugins_with_triggers()
    executed = set()

    while len(executed) < len(all_plugins):
        ready_plugins = []

        for plugin in all_plugins:
            if plugin.name in executed:
                continue

            # Evaluate trigger rule
            if self._evaluate_trigger(plugin.trigger_rule, plugin.requires):
                ready_plugins.append(plugin)

        if not ready_plugins:
            break  # No more plugins can execute

        # Execute ready plugins (can be parallel if no conflicts)
        for plugin in ready_plugins:
            self._execute_plugin(plugin)
            executed.add(plugin.name)
```

---

## 3. LOGGING SYSTEM ISSUES

### Issue #3.1: Missing CRITICAL Log Level

**File:** `src/archiverr/utils/debug.py`
**Severity:** 🔴 CRITICAL

**Current levels:** DEBUG, INFO, WARN, ERROR
**Missing:** CRITICAL (level 50)

**Python Standard:**

```python
DEBUG = 10      # Detailed diagnostic information
INFO = 20       # Confirmation things work
WARNING = 30    # Something unexpected (note: WARNING not WARN)
ERROR = 40      # Serious problem
CRITICAL = 50   # Program may be unable to continue
```

**Impact:**

- Cannot distinguish between recoverable errors and fatal failures
- Non-standard naming (WARN vs WARNING)
- No level-based filtering

---

### Issue #3.2: Binary Debug Toggle

**File:** Configuration system
**Severity:** 🟡 MEDIUM

**Current:** `options.debug: true/false` (binary)
**Problem:** Cannot enable INFO without DEBUG noise

**Solution:**

```yaml
options:
  log_level: INFO # DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_output: stderr # stderr, file, both
  log_format: structured # structured, text, json
```

---

### Issue #3.3: Inconsistent Naming - warn() vs warning()

**File:** `src/archiverr/utils/debug.py:115-117`
**Severity:** 🟡 MEDIUM

```python
def warn(self, component: str, message: str, **fields):
    """WARN level - Warning messages"""
    self._log("WARN", component, message, **fields)
```

**Python Standard:** `warning()` not `warn()`
**Fix:** Rename to `warning()`, keep `warn()` as alias for backward compatibility

---

## 4. LIVE LOGGING ISSUES

### Issue #4.1: Batch Logging in Orchestrator

**File:** `src/archiverr/core/orchestrator.py:278-311`
**Severity:** 🟠 HIGH

```python
for plugin_name, plugin_instance in per_run_plugins:
    try:
        self._log("debug", f"Executing per_run plugin: {plugin_name}")

        # ... 50 lines of execution code with NO LOGGING ...

        self._log("info", f"{plugin_name} completed: {result.get('data', {}).get('count', 0)} jobs created")
```

**Problem:** Logs only before and after execution. During execution (potentially seconds): NOTHING!

**User Concern:**

> "plugin sistemi bana canlı bir şekilde akıyormuş gibi gelmedi sanki bittikten sonra herşey loglanıyormuş gibi geldi"

**Fix:** Ensure plugins log during execution:

```python
class ScannerPlugin:
    def execute_run(self, services):
        self.info("Starting scan", targets=len(self.config['targets']))

        for target in targets:
            self.debug("Scanning", path=target)

            for file in discover_files(target):
                self.info("Found", file=file.name, size=file.stat().st_size)
                job_id = services.createJob(str(file), {...})
                self.debug("Created job", job_id=job_id)

        self.info("Scan complete", total_jobs=count)
```

---

### Issue #4.2: Job Stage Completion Event Timing

**File:** `src/archiverr/core/plugins/stage_executor.py:254-258`
**Severity:** 🟡 MEDIUM

```python
for job in jobs:
    for group in plugin_groups:
        # Execute plugins...

    # Emit job stage progress AFTER all plugins complete
    self._event_bus.emit("job.stage_completed", {
        "job_id": job.id,
        "stage": stage.value
    })
```

**Problem:** Event emitted only after ALL plugins complete for a job.

**Expected:** Events during plugin execution:

```
plugin.started  → job_001, plugin: renamer
plugin.completed → job_001, plugin: renamer
plugin.started  → job_001, plugin: tmdb
plugin.completed → job_001, plugin: tmdb
job.stage_completed → job_001, stage: data
```

---

## 5. MISSING DEPENDENCIES

### Issue #5.1: Pydantic Not in Core Dependencies

**File:** `requirements.txt` and `pyproject.toml`
**Severity:** 🔴 CRITICAL

**Error:**

```
ModuleNotFoundError: No module named 'pydantic'
```

**Used in:**

- `src/archiverr/core/plugins/sdk/manifest.py:9`

**Current Location:** Listed under "FUTURE FEATURES" comment in requirements.txt (line 71)

**Fix:** Move to core dependencies:

```toml
# pyproject.toml
dependencies = [
    "pyyaml>=6.0.1,<7.0.0",
    "jinja2>=3.1.2",
    "requests>=2.31.0,<3.0.0",
    "python-dotenv>=1.0.0,<2.0.0",
    "pydantic>=2.4.0,<3.0.0",  # ← ADD THIS
]
```

---

## 6. MIXED DEPENDENCY SYSTEMS

### Issue #6.1: Three Dependency Systems Coexisting

**Files:** Multiple
**Severity:** 🟠 HIGH

**Found Systems:**

1. **Legacy:** `depends_on` field
2. **Session 11:** `requires/provides` fields
3. **Session 12:** `trigger_rule` field

**Evidence:**

```python
# stage_executor.py:283-285
requires = manifest.get('requires', []) if manifest else []
trigger_rule = manifest.get('trigger_rule', 'all_success') if manifest else 'all_success'

# Also check legacy expects/depends_on
if not requires:
    requires = manifest.get('expects', []) if manifest else []
```

**Problem:**

- Confusion about which system to use
- No clear migration path
- Systems work in parallel
- Documentation doesn't match implementation

**Solution:** Deprecate old systems, migrate all plugins:

1. Deprecation warnings for `depends_on` and `expects`
2. Migration guide for plugin authors
3. Remove legacy code after migration period

---

## 7. LEGACY CODE & COMMENTS

### Issue #7.1: "Session 12: X removed" Comments Everywhere

**Files:** Multiple
**Severity:** 🟢 LOW

Examples:

```python
# Session 12: Provides registry removed
# Session 12: Provides system removed
# Note: INPUT stage removed in Session 12
```

**Problem:** Code is littered with removal notes but doesn't clean up references.

**Fix:** Clean up pass to:

1. Remove commented explanations
2. Update docstrings
3. Remove unused imports

---

### Issue #7.2: Unused Provides Registry System

**File:** `src/archiverr/core/provides_registry.py` (398 lines)
**Severity:** 🟡 MEDIUM

**Status:** Still imported in multiple files but marked as "removed in Session 12"

**Found in:**

- `src/archiverr/core/validation/startup_validator.py:22`
- `src/archiverr/core/services/__init__.py:31,38,91,118`
- `src/archiverr/core/services/provides_service.py:9`

**Decision Needed:**

- If removed: Delete file and all imports
- If used: Remove "removed" comments and document properly

---

## 8. CODE ORGANIZATION ISSUES

### Issue #8.1: Deep Path Calculation

**File:** `src/archiverr/api/process_executor.py:78`
**Severity:** 🟢 LOW

```python
# Get the project root (where config.yml is)
project_root = Path(__file__).parent.parent.parent.parent.parent
```

**Problem:** Five levels of `.parent` is fragile and hard to maintain.

**Fix:**

```python
# More robust project root detection
import archiverr
project_root = Path(archiverr.__file__).parent.parent.parent
# Or use a config constant
```

---

### Issue #8.2: Inconsistent Stage Naming

**Files:** Documentation vs Code
**Severity:** 🟡 MEDIUM

**Documentation mentions:** INPUT → PARSE → DATA → OUTPUT (4 stages)
**Code implements:** PARSE → DATA → OUTPUT (3 stages)
**Comments say:** "INPUT stage removed in Session 12"

**Fix:** Update all documentation to reflect 3-stage architecture.

---

## 9. EVENT SYSTEM ISSUES

### Issue #9.1: Synchronous Event Bus with Async Naming

**File:** `src/archiverr/events/bus.py`
**Severity:** 🟢 LOW

**Code says:** "Async-ready design" but all methods are synchronous
**Comment:** "Can be converted to async by changing emit() to async"

**Problem:** Misleading documentation - it's NOT async-ready, it's sync-only with async plans.

**Fix:** Either:

1. Implement async support now
2. Remove "async-ready" claims from docs

---

## 10. TESTING GAPS

### Issue #10.1: No Integration Tests for Hardcoded Execution Order

**Missing Test:**

```python
def test_condition_based_execution():
    """Test that plugins execute based on conditions, not hardcoded order."""
    # Setup: Scanner has no conditions, Renamer needs job, TMDb needs renamer

    # Execute
    orchestrator.run()

    # Verify execution order was condition-based
    assert execution_log[0] == 'scanner'  # No conditions
    assert execution_log[1] == 'renamer'  # After job created
    assert execution_log[2] == 'tmdb'     # After renamer completed
```

---

### Issue #10.2: No Live Logging Tests

**Missing Test:**

```python
def test_live_logging_during_plugin_execution():
    """Test that logs appear during plugin execution, not just before/after."""

    log_capture = []
    start_time = time.time()

    # Execute long-running plugin
    plugin.execute_run(services)

    # Verify logs appeared during execution
    assert any(log['timestamp'] < start_time + 0.1 for log in log_capture)
    assert any(log['message'] == 'Processing item 5/10' for log in log_capture)
```

---

### Issue #10.3: No Tests for Plugin-Agnostic Principle

**Missing Test:**

```python
def test_core_has_no_plugin_specific_knowledge():
    """Test that core code doesn't contain hardcoded plugin names."""

    core_files = glob('src/archiverr/core/**/*.py', recursive=True)
    plugin_names = ['scanner', 'renamer', 'tmdb', 'tvdb', 'tasker']

    for file in core_files:
        content = Path(file).read_text()
        for plugin_name in plugin_names:
            # Allow in comments explaining examples, but not in code
            assert f"['{plugin_name}'" not in content
            assert f'["{plugin_name}"' not in content
```

---

## SUMMARY OF ISSUES

| Category                   | Critical | High  | Medium | Low   | Total  |
| -------------------------- | -------- | ----- | ------ | ----- | ------ |
| Plugin-Agnostic Violations | 3        | 0     | 1      | 0     | 4      |
| Execution Flow             | 2        | 1     | 1      | 0     | 4      |
| Logging System             | 1        | 0     | 2      | 0     | 3      |
| Dependencies               | 1        | 1     | 0      | 0     | 2      |
| Legacy Code                | 0        | 0     | 1      | 1     | 2      |
| Code Organization          | 0        | 0     | 1      | 1     | 2      |
| Testing                    | 0        | 0     | 0      | 3     | 3      |
| **TOTAL**                  | **7**    | **2** | **6**  | **5** | **20** |

---

## PRIORITY ORDER FOR FIXES

### 🔴 MUST FIX (Critical - 7 issues)

1. Add `pydantic` to dependencies
2. Remove hardcoded plugin names from core (3 locations)
3. Implement condition-based execution
4. Add CRITICAL log level

### 🟠 SHOULD FIX (High - 2 issues)

5. Fix live logging in orchestrator
6. Deprecate mixed dependency systems

### 🟡 COULD FIX (Medium - 6 issues)

7. Binary debug toggle → log_level config
8. Rename warn() → warning()
9. Fix event timing for job stages
10. Clean up legacy "removed" comments
11. Clarify provides registry status
12. Update stage naming in docs

### 🟢 NICE TO HAVE (Low - 5 issues)

13. Deep path calculation
14. Event system async claims
15. Add missing integration tests

---

**End of Detailed Issues**
