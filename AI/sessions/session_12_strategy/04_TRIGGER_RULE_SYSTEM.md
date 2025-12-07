# TRIGGER RULE SYSTEM

```yaml
tarih: 2024-12-08
durum: strategy
session: 12
konu: State-based dependency resolution with value checking
kaynak: Apache Airflow trigger rules pattern
```

---

## OVERVIEW

Session 12 trigger rule sistemi **iki seviyeli** dependency check yapar:

1. **Standard Trigger Rules** (Airflow pattern)
   - `all_success`, `one_success`, `all_done`, `all_fail`, `none_fail`
   - Manifest seviyesinde tanımlanır

2. **Value-based Trigger Rules** (Inline)
   - Requires satırında `:` ile değer kontrolü
   - State path'ine spesifik değer veya durum kontrolü

---

## STANDARD TRIGGER RULES

### Airflow Pattern

Session 12'de Airflow'dan esinlenilen 5 trigger rule var:

```yaml
all_success      # Tüm requires SUCCESS olmalı (default)
one_success      # En az bir requires SUCCESS olmalı
all_done         # Tüm requires DONE olmalı (success veya fail)
all_fail         # Tüm requires FAIL olmalı
none_fail        # Hiçbir requires FAIL olmamalı
```

### Manifest Kullanımı

```yaml
# plugins/tmdb/manifest.yml
name: tmdb
run_mode: per_job
stage: data
requires:
  - plugin.renamer.data.parsed:success
  - plugin.ffprobe.data.video:success
trigger_rule: all_success  # Default
```

### Trigger Rule Semantics

#### all_success (default)

```
RULE: Tüm dependencies SUCCESS olmalı
USE CASE: Normal sequential execution

EXAMPLE:
  requires: [plugin.renamer.data.parsed:success, plugin.ffprobe.data:success]
  trigger_rule: all_success
  
  ✅ ÇALIŞIR: renamer=SUCCESS, ffprobe=SUCCESS
  ❌ BEKLER: renamer=SUCCESS, ffprobe=PENDING
  ❌ SKIP: renamer=FAIL, ffprobe=SUCCESS
```

#### one_success

```
RULE: En az bir dependency SUCCESS olmalı
USE CASE: Branching, alternatif veri kaynakları

EXAMPLE:
  requires: [plugin.tmdb.data.movie:success, plugin.omdb.data.movie:success]
  trigger_rule: one_success
  
  ✅ ÇALIŞIR: tmdb=SUCCESS, omdb=PENDING
  ✅ ÇALIŞIR: tmdb=FAIL, omdb=SUCCESS
  ❌ SKIP: tmdb=FAIL, omdb=FAIL
```

#### all_done

```
RULE: Tüm dependencies tamamlanmalı (success veya fail)
USE CASE: Cleanup, summary plugins

EXAMPLE:
  requires: [plugin.tmdb, plugin.tvdb, plugin.ffprobe]
  trigger_rule: all_done
  
  ✅ ÇALIŞIR: tmdb=SUCCESS, tvdb=FAIL, ffprobe=SUCCESS
  ✅ ÇALIŞIR: tmdb=FAIL, tvdb=FAIL, ffprobe=FAIL
  ❌ BEKLER: tmdb=SUCCESS, tvdb=PENDING, ffprobe=SUCCESS
```

#### all_fail

```
RULE: Tüm dependencies FAIL olmalı
USE CASE: Failure handlers, retry logic

EXAMPLE:
  requires: [plugin.tmdb, plugin.omdb]
  trigger_rule: all_fail
  
  ✅ ÇALIŞIR: tmdb=FAIL, omdb=FAIL
  ❌ SKIP: tmdb=SUCCESS, omdb=FAIL
  ❌ SKIP: tmdb=FAIL, omdb=SUCCESS
```

#### none_fail

```
RULE: Hiçbir dependency FAIL olmamalı
USE CASE: Data validation, quality gates

EXAMPLE:
  requires: [plugin.renamer, plugin.tmdb]
  trigger_rule: none_fail
  
  ✅ ÇALIŞIR: renamer=SUCCESS, tmdb=SUCCESS
  ✅ ÇALIŞIR: renamer=SUCCESS, tmdb=SKIPPED
  ❌ SKIP: renamer=FAIL, tmdb=SUCCESS
```

---

## VALUE-BASED TRIGGER RULES

### 🔴 KRİTİK KURAL

```yaml
# success/fail SADECE plugin ve plugins için!
# Non-plugin paths için SADECE exact value match
```

### Syntax

```yaml
# ✅ Plugin paths için
requires:
  - plugin.{name}.data.{field}:success    # Plugin success
  - plugin.{name}.data.{field}:fail       # Plugin failed
  - plugin.{name}.data.{field}:value      # Exact match

# ✅ Non-plugin paths için (SADECE exact value)
requires:
  - run.total_jobs:10                     # int
  - config.options.debug:true             # boolean
  - job.input.value:"/path"               # string

# ❌ YASAK (validation error)
requires:
  - run.status:success        # Non-plugin için success/fail YASAK
  - job.output:success        # Non-plugin için success/fail YASAK
```

### Value Check Types

#### 1. Exact Value Match (Primitives)

```yaml
# ✅ Non-plugin paths için exact value
requires:
  - run.total_jobs:10                         # int exact match
  - config.options.debug:true                 # boolean exact match
  - job.input.value:"/path/to/file"           # string exact match
  - plugin.renamer.data.parsed.movie.year:2024  # Plugin field exact match
```

**Evaluation**:
```python
def check_exact_value(path, expected):
    actual = state.get(path)
    return actual == expected
```

#### 2. Success Check (SADECE Plugin)

```yaml
# ✅ Plugin paths için success check
requires:
  - plugin.tmdb.data.movie:success         # Plugin data exists
  - plugin.renamer.data.parsed:success     # Plugin data exists
  - plugins[0].tmdb.data.movie:success     # Plugins array

# ❌ YASAK - Non-plugin için success
# - job.input.value:success       → VALIDATION ERROR
# - run.status:success            → VALIDATION ERROR
```

**Evaluation**:
```python
def check_success(path):
    value = state.get(path)
    
    if value is None:
        return False
    
    if isinstance(value, (dict, list, str)):
        return len(value) > 0
    
    return True
```

#### 3. Fail Check (SADECE Plugin)

```yaml
# ✅ Plugin paths için fail check
requires:
  - plugin.tmdb.data.movie:fail        # Plugin failed or data empty
  - plugin.renamer.data:fail           # Plugin failed

# ❌ YASAK - Non-plugin için fail
# - job.output.values:fail     → VALIDATION ERROR
# - run.status:fail            → VALIDATION ERROR
```

**Evaluation**:
```python
def check_fail(path):
    # Check plugin status first
    plugin_status = state.get_plugin_status(path)
    if plugin_status and plugin_status.state == "failed":
        return True
    
    # Check value existence
    value = state.get(path)
    return value is None or (hasattr(value, '__len__') and len(value) == 0)
```

### Mixed Usage

```yaml
# Manifest - Plugin success + Primitive values
requires:
  - plugin.renamer.data.parsed:success  # ✅ Plugin success
  - run.total_jobs:10                   # ✅ Primitive exact match
  - config.options.debug:true           # ✅ Primitive exact match
trigger_rule: all_success
```

**Evaluation Order**:
1. İlk önce value-based requirements check edilir
2. Sonra genel requirements trigger_rule ile değerlendirilir

---

## TRIGGER RULE MANAGER

### Architecture

```
TriggerRuleManager
├── StateResolver
│   ├── resolve_path()         # State path resolution
│   ├── get_value()            # Value extraction
│   └── check_plugin_status()  # Plugin status check
│
├── ValueMatcher
│   ├── match_exact()          # Exact value match
│   ├── match_success()        # Success check
│   └── match_fail()           # Fail check
│
└── RuleEvaluator
    ├── evaluate_all_success()
    ├── evaluate_one_success()
    ├── evaluate_all_done()
    ├── evaluate_all_fail()
    └── evaluate_none_fail()
```

### State Resolution

```python
class StateResolver:
    """Resolve state paths to actual values"""
    
    def __init__(self, state: StateManager):
        self._state = state
    
    def resolve_path(self, path: str) -> Any:
        """
        Resolve dot-notation path to value
        
        Examples:
            "run.total_jobs" → 10
            "plugin.tmdb.movie.title" → "Movie Name"
            "job.input.value" → "/path/to/file"
        """
        parts = path.split(".")
        root = parts[0]
        
        # Get root object
        if root == "run":
            obj = self._state.get_run()
        elif root == "config":
            obj = self._state.get_config()
        elif root == "job":
            obj = self._state.get_current_job()
        elif root == "jobs":
            obj = self._state.get_all_jobs()
        elif root == "plugin":
            obj = self._state.get_current_plugins()
        elif root == "plugins":
            obj = self._state.get_all_plugins()
        else:
            raise ValueError(f"Unknown root: {root}")
        
        # Navigate to nested value
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return None
        
        return obj
    
    def check_plugin_status(self, plugin_path: str) -> Optional[Dict]:
        """
        Check if plugin has failed
        
        Example: "plugin.tmdb" → {"state": "failed", "success": False}
        """
        parts = plugin_path.split(".")
        
        if parts[0] != "plugin":
            return None
        
        if len(parts) < 2:
            return None
        
        plugin_name = parts[1]
        current_plugins = self._state.get_current_plugins()
        
        if plugin_name not in current_plugins:
            return None
        
        return current_plugins[plugin_name].get("status")
```

### Value Matching

```python
class ValueMatcher:
    """Match values with expected criteria"""
    
    def match(self, path: str, expected: str, resolver: StateResolver) -> bool:
        """
        Match value with expected
        
        Args:
            path: State path (e.g., "plugin.tmdb.movie.title")
            expected: Expected value (e.g., "success", "fail", or actual value)
            resolver: State resolver
        
        Returns:
            True if match, False otherwise
        """
        if expected == "success":
            return self.match_success(path, resolver)
        elif expected == "fail":
            return self.match_fail(path, resolver)
        else:
            return self.match_exact(path, expected, resolver)
    
    def match_exact(self, path: str, expected: str, resolver: StateResolver) -> bool:
        """Exact value match"""
        actual = resolver.resolve_path(path)
        
        # Type conversion
        if expected.lower() == "true":
            expected_val = True
        elif expected.lower() == "false":
            expected_val = False
        elif expected.isdigit():
            expected_val = int(expected)
        else:
            expected_val = expected
        
        return actual == expected_val
    
    def match_success(self, path: str, resolver: StateResolver) -> bool:
        """Check if value exists and is not empty"""
        # Check plugin status first
        plugin_status = resolver.check_plugin_status(path)
        if plugin_status:
            return plugin_status.get("success", False)
        
        # Check value existence
        value = resolver.resolve_path(path)
        
        if value is None:
            return False
        
        if isinstance(value, (dict, list, str)):
            return len(value) > 0
        
        return True
    
    def match_fail(self, path: str, resolver: StateResolver) -> bool:
        """Check if value is empty or plugin failed"""
        # Check plugin status first
        plugin_status = resolver.check_plugin_status(path)
        if plugin_status:
            return not plugin_status.get("success", True)
        
        # Check value existence
        value = resolver.resolve_path(path)
        
        if value is None:
            return True
        
        if isinstance(value, (dict, list, str)):
            return len(value) == 0
        
        return False
```

### Rule Evaluation

```python
class RuleEvaluator:
    """Evaluate trigger rules"""
    
    def __init__(self, resolver: StateResolver, matcher: ValueMatcher):
        self._resolver = resolver
        self._matcher = matcher
    
    def evaluate(
        self, 
        requires: List[str], 
        trigger_rule: str = "all_success"
    ) -> bool:
        """
        Evaluate if plugin should execute
        
        Args:
            requires: List of requirements (with optional values)
            trigger_rule: Standard trigger rule
        
        Returns:
            True if plugin should execute, False to skip
        
        Raises:
            ValidationError: If non-plugin path uses success/fail
        """
        # Separate value-based and general requirements
        value_based = []
        general = []
        
        for req in requires:
            if ":" in req:
                path, value = req.split(":", 1)
                path = path.strip()
                value = value.strip()
                
                # 🔴 VALIDATION: success/fail only for plugin paths
                if value in ["success", "fail"]:
                    if not (path.startswith("plugin.") or path.startswith("plugins")):
                        raise ValidationError(
                            f"success/fail only allowed for plugin paths. "
                            f"Got: {req}. Use exact value match for non-plugin paths."
                        )
                
                value_based.append((path, value))
            else:
                general.append(req.strip())
        
        # 1. Check value-based requirements first (must ALL pass)
        for path, expected in value_based:
            if not self._matcher.match(path, expected, self._resolver):
                return False
        
        # 2. Check general requirements with trigger rule
        if not general:
            return True  # No general requirements
        
        # Evaluate based on trigger rule
        if trigger_rule == "all_success":
            return self._all_success(general)
        elif trigger_rule == "one_success":
            return self._one_success(general)
        elif trigger_rule == "all_done":
            return self._all_done(general)
        elif trigger_rule == "all_fail":
            return self._all_fail(general)
        elif trigger_rule == "none_fail":
            return self._none_fail(general)
        else:
            raise ValueError(f"Unknown trigger rule: {trigger_rule}")
    
    def _all_success(self, requirements: List[str]) -> bool:
        """All must succeed"""
        for req in requirements:
            if not self._is_success(req):
                return False
        return True
    
    def _one_success(self, requirements: List[str]) -> bool:
        """At least one must succeed"""
        return any(self._is_success(req) for req in requirements)
    
    def _all_done(self, requirements: List[str]) -> bool:
        """All must be done (success or fail)"""
        for req in requirements:
            if not self._is_done(req):
                return False
        return True
    
    def _all_fail(self, requirements: List[str]) -> bool:
        """All must fail"""
        for req in requirements:
            if not self._is_fail(req):
                return False
        return True
    
    def _none_fail(self, requirements: List[str]) -> bool:
        """None must fail"""
        for req in requirements:
            if self._is_fail(req):
                return False
        return True
    
    def _is_success(self, path: str) -> bool:
        """Check if path has successful value"""
        plugin_status = self._resolver.check_plugin_status(path)
        if plugin_status:
            return plugin_status.get("success", False)
        
        value = self._resolver.resolve_path(path)
        return value is not None and (
            not hasattr(value, '__len__') or len(value) > 0
        )
    
    def _is_done(self, path: str) -> bool:
        """Check if plugin is done (success or fail)"""
        plugin_status = self._resolver.check_plugin_status(path)
        if plugin_status:
            return plugin_status.get("state") in ["completed", "failed", "skipped"]
        
        # If not a plugin, check value existence
        value = self._resolver.resolve_path(path)
        return value is not None
    
    def _is_fail(self, path: str) -> bool:
        """Check if plugin failed or value is empty"""
        plugin_status = self._resolver.check_plugin_status(path)
        if plugin_status:
            return not plugin_status.get("success", True)
        
        value = self._resolver.resolve_path(path)
        return value is None or (hasattr(value, '__len__') and len(value) == 0)
```

### TriggerRuleManager Interface

```python
class TriggerRuleManager:
    """Main trigger rule manager"""
    
    def __init__(self, state: StateManager):
        self._resolver = StateResolver(state)
        self._matcher = ValueMatcher()
        self._evaluator = RuleEvaluator(self._resolver, self._matcher)
    
    def should_execute(
        self, 
        plugin_manifest: Dict,
        context_type: str = "per_job"
    ) -> bool:
        """
        Check if plugin should execute based on trigger rules
        
        Args:
            plugin_manifest: Plugin manifest with requires and trigger_rule
            context_type: "per_run" or "per_job"
        
        Returns:
            True if plugin should execute, False to skip
        """
        requires = plugin_manifest.get("requires", [])
        trigger_rule = plugin_manifest.get("trigger_rule", "all_success")
        
        # No requirements = always execute
        if not requires:
            return True
        
        # Evaluate
        return self._evaluator.evaluate(requires, trigger_rule)
    
    def get_unmet_requirements(
        self,
        plugin_manifest: Dict
    ) -> List[str]:
        """
        Get list of unmet requirements for debugging
        
        Returns:
            List of requirement paths that are not satisfied
        """
        requires = plugin_manifest.get("requires", [])
        unmet = []
        
        for req in requires:
            if ":" in req:
                path, expected = req.split(":", 1)
                if not self._matcher.match(path.strip(), expected.strip(), self._resolver):
                    unmet.append(req)
            else:
                if not self._evaluator._is_success(req.strip()):
                    unmet.append(req)
        
        return unmet
```

---

## USAGE EXAMPLES

### Example 1: Sequential Dependency

```yaml
# plugins/tmdb/manifest.yml
requires:
  - plugin.renamer.data.parsed:success
trigger_rule: all_success
```

```python
# Evaluation
# renamer.data.parsed must be SUCCESS
if plugin.renamer.status.success and plugin.renamer.data.parsed exists:
    execute_tmdb()
else:
    skip_tmdb()
```

### Example 2: Alternative Sources

```yaml
# plugins/metadata_merger/manifest.yml
requires:
  - plugin.tmdb.data.movie:success
  - plugin.omdb.data.movie:success
trigger_rule: one_success
```

```python
# Evaluation
# At least one metadata source must succeed
if plugin.tmdb.data.movie exists OR plugin.omdb.data.movie exists:
    execute_merger()
else:
    skip_merger()
```

### Example 3: Cleanup Plugin

```yaml
# plugins/cleanup/manifest.yml
requires:
  - plugin.tasker
  - plugin.rclone
trigger_rule: all_done
```

```python
# Evaluation
# Both must be done (success or fail)
if (tasker.status.state in [completed, failed]) AND 
   (rclone.status.state in [completed, failed]):
    execute_cleanup()
else:
    wait()
```

### Example 4: Value-based Check

```yaml
# plugins/4k_processor/manifest.yml
requires:
  - plugin.ffprobe.data.video.height:2160  # Exact value match
  - plugin.renamer.data.parsed:success     # Plugin success
trigger_rule: all_success
```

```python
# Evaluation
# 1. Check video height = 2160 (exact match)
# 2. Check parsed data exists (plugin success)
if (plugin.ffprobe.data.video.height == 2160) AND 
   (plugin.renamer.status.success and plugin.renamer.data.parsed):
    execute_4k_processor()
else:
    skip_4k_processor()
```

### Example 5: Config-based Execution

```yaml
# plugins/debug_printer/manifest.yml
requires:
  - config.options.debug:true
trigger_rule: all_success
```

```python
# Evaluation
# Only execute if debug mode is enabled
if config.options.debug == True:
    execute_debug_printer()
else:
    skip_debug_printer()
```

---

## STAGE EXECUTION WITH TRIGGER RULES

```python
def execute_stage(stage: str, job: JobState):
    """Execute stage with trigger rule checking"""
    
    # Get plugins for this stage
    stage_plugins = plugin_registry.get_plugins_by_stage(stage)
    
    # Check trigger rules for each plugin
    ready_plugins = []
    waiting_plugins = []
    
    for plugin in stage_plugins:
        if trigger_manager.should_execute(plugin.manifest):
            ready_plugins.append(plugin)
        else:
            waiting_plugins.append(plugin)
            
            # Log why plugin is waiting
            unmet = trigger_manager.get_unmet_requirements(plugin.manifest)
            logger.debug(
                f"Plugin {plugin.name} waiting on: {unmet}",
                job_id=job.id
            )
    
    # Execute ready plugins
    for plugin in ready_plugins:
        services = PluginServices(state, events, logger, config, mode="per_job")
        result = plugin.execute(job, services)
        
        # Update plugin status
        state.update_plugin_status(plugin.name, result)
        
        # Re-check waiting plugins (dependencies might be satisfied now)
        if waiting_plugins:
            newly_ready = []
            still_waiting = []
            
            for waiting in waiting_plugins:
                if trigger_manager.should_execute(waiting.manifest):
                    newly_ready.append(waiting)
                else:
                    still_waiting.append(waiting)
            
            # Execute newly ready plugins
            for newly in newly_ready:
                result = newly.execute(job, services)
                state.update_plugin_status(newly.name, result)
            
            waiting_plugins = still_waiting
    
    # Skip remaining waiting plugins
    for skipped in waiting_plugins:
        logger.warn(
            f"Plugin {skipped.name} skipped (unmet requirements)",
            job_id=job.id,
            unmet=trigger_manager.get_unmet_requirements(skipped.manifest)
        )
        job.status.skipped.append(skipped.name)
```

---

## PERFORMANCE CONSIDERATIONS

### Caching

```python
class CachedStateResolver:
    """State resolver with caching for performance"""
    
    def __init__(self, state: StateManager):
        self._state = state
        self._cache = {}
    
    def resolve_path(self, path: str) -> Any:
        if path in self._cache:
            return self._cache[path]
        
        value = self._resolve_uncached(path)
        self._cache[path] = value
        return value
    
    def invalidate(self, path_prefix: str = None):
        """Invalidate cache after state updates"""
        if path_prefix:
            self._cache = {
                k: v for k, v in self._cache.items()
                if not k.startswith(path_prefix)
            }
        else:
            self._cache = {}
```

### Topological Sort

```python
def topological_sort_plugins(plugins: List[Plugin]) -> List[List[Plugin]]:
    """
    Sort plugins by dependencies using topological sort
    
    Returns:
        List of plugin groups (can be executed in parallel)
    """
    # Build dependency graph
    graph = defaultdict(list)
    in_degree = defaultdict(int)
    
    for plugin in plugins:
        requires = plugin.manifest.get("requires", [])
        
        for req in requires:
            # Extract plugin name from path
            if req.startswith("plugin."):
                dep_plugin = req.split(".")[1]
                graph[dep_plugin].append(plugin.name)
                in_degree[plugin.name] += 1
    
    # Kahn's algorithm
    queue = [p.name for p in plugins if in_degree[p.name] == 0]
    groups = []
    
    while queue:
        # Current group (can execute in parallel)
        current_group = queue[:]
        groups.append([p for p in plugins if p.name in current_group])
        
        # Process dependencies
        next_queue = []
        for plugin_name in current_group:
            for dependent in graph[plugin_name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_queue.append(dependent)
        
        queue = next_queue
    
    return groups
```

---

## SUMMARY

### Trigger Rule Types

| Type | Manifest Field | Inline Syntax | Evaluation |
|------|----------------|---------------|------------|
| Standard | trigger_rule | - | all_success, one_success, etc. |
| Value-based | requires | path:value | Exact match or success/fail check |

### Standard Rules

| Rule | Semantics | Use Case |
|------|-----------|----------|
| all_success | All deps SUCCESS | Sequential pipeline |
| one_success | ≥1 dep SUCCESS | Branching, alternatives |
| all_done | All deps DONE | Cleanup, summary |
| all_fail | All deps FAIL | Error handlers |
| none_fail | No deps FAIL | Quality gates |

### Value Checks

| Syntax | Meaning | Example | Allowed For |
|--------|---------|---------|-------------|
| path:success | Plugin success | plugin.tmdb.data.movie:success | plugin.*, plugins.* only |
| path:fail | Plugin failed | plugin.tmdb.data.movie:fail | plugin.*, plugins.* only |
| path:value | Exact match | run.total_jobs:10 | All paths (primitives) |

**🔴 KRİTİK**: success/fail sadece plugin paths için. Non-plugin = validation error.

---

**Next Document**: 05_JOB_LIFECYCLE_AND_EXECUTION.md
