# JOB LIFECYCLE AND EXECUTION

```yaml
tarih: 2024-12-08
durum: strategy
session: 12
konu: Job queue management, stage execution, and FS lock system
```

---

## OVERVIEW

Session 12'de sistem **job queue paradigması** ile çalışır:
- Per-run pluginler job oluşturur
- Joblar queue'ya eklenir
- Her job 3 stage'den geçer: parse → data → output
- FS lock ile concurrent access kontrolü

---

## JOB LIFECYCLE STAGES

### Stage 1: Creation (per_run)

```
┌──────────────────────────────────────┐
│  PER-RUN PLUGINS (Input Generators)  │
└──────────────────────────────────────┘
                 ↓
     createJob(path, metadata)
                 ↓
┌──────────────────────────────────────┐
│         JOB CREATED                  │
│  - id: generated                     │
│  - input.value: path                 │
│  - input.data: metadata              │
│  - status: pending                   │
└──────────────────────────────────────┘
                 ↓
        Added to Job Queue
```

### Stage 2: Queueing

```
┌──────────────────────────────────────┐
│          JOB QUEUE                   │
│                                      │
│  [Job1] [Job2] [Job3] ...           │
│   ↓                                  │
│   Processing...                     │
└──────────────────────────────────────┘
```

### Stage 3: Processing (per_job)

```
┌──────────────────────────────────────┐
│       PARSE STAGE                    │
│  - Renamer: Parse filename          │
│  - Extract metadata                  │
└──────────────────────────────────────┘
                 ↓
┌──────────────────────────────────────┐
│       DATA STAGE                     │
│  - TMDb: Fetch movie data           │
│  - FFprobe: Probe video              │
│  - TVDb: Fetch show data (optional) │
└──────────────────────────────────────┘
                 ↓
┌──────────────────────────────────────┐
│       OUTPUT STAGE                   │
│  - Tasker: Execute tasks             │
│  - RClone: Upload (optional)         │
└──────────────────────────────────────┘
                 ↓
┌──────────────────────────────────────┐
│       JOB COMPLETED                  │
│  - status: completed | failed       │
│  - output.values: [paths]           │
│  - Persist to MongoDB                │
└──────────────────────────────────────┘
```

---

## JOB QUEUE MANAGEMENT

### Queue Architecture

```python
class JobQueue:
    """
    Job queue manager
    
    Manages pending jobs and execution order
    """
    
    def __init__(self):
        self._queue: List[JobState] = []
        self._processing: Optional[JobState] = None
        self._completed: List[JobState] = []
        self._failed: List[JobState] = []
    
    def enqueue(self, job: JobState) -> None:
        """Add job to queue"""
        self._queue.append(job)
    
    def dequeue(self) -> Optional[JobState]:
        """Get next job from queue"""
        if not self._queue:
            return None
        return self._queue.pop(0)
    
    def mark_processing(self, job: JobState) -> None:
        """Mark job as currently processing"""
        self._processing = job
        job.status.state = "running"
    
    def mark_completed(self, job: JobState) -> None:
        """Mark job as completed"""
        self._processing = None
        self._completed.append(job)
        job.status.state = "completed"
        job.status.success = True
    
    def mark_failed(self, job: JobState) -> None:
        """Mark job as failed"""
        self._processing = None
        self._failed.append(job)
        job.status.state = "failed"
        job.status.success = False
    
    @property
    def pending_count(self) -> int:
        return len(self._queue)
    
    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0 and self._processing is None
```

### Queue Execution Pattern

```python
def execute_job_queue(queue: JobQueue, orchestrator: Orchestrator):
    """Execute all jobs in queue"""
    
    while not queue.is_empty:
        # Get next job
        job = queue.dequeue()
        
        if job is None:
            break
        
        # Mark as processing
        queue.mark_processing(job)
        
        try:
            # Execute job through stages
            execute_job(job, orchestrator)
            
            # Mark as completed
            queue.mark_completed(job)
            
        except JobExecutionError as e:
            # Job failed
            logger.error(f"Job {job.id} failed: {e}")
            queue.mark_failed(job)
            
            # Continue with next job (best effort)
        
        except CriticalError as e:
            # Critical error, stop processing
            logger.error(f"Critical error: {e}")
            queue.mark_failed(job)
            raise
```

---

## STAGE EXECUTION

### Parse Stage

```python
def execute_parse_stage(job: JobState, state: StateManager):
    """
    Parse stage: Filename parsing and basic analysis
    
    Plugins:
    - Renamer: Parse filename, extract movie/show metadata
    - Other parse plugins
    """
    stage = "parse"
    plugins = plugin_registry.get_plugins_by_stage(stage)
    
    logger.info(f"Executing {stage} stage", job_id=job.id)
    emit_event("stage.started", {"job_id": job.id, "stage": stage})
    
    # Set current job in state
    state.set_current_job(job)
    state.set_current_plugins({})
    
    # Execute plugins with trigger rule checking
    executed = []
    failed = []
    skipped = []
    
    for plugin in plugins:
        # Check trigger rules
        if not trigger_manager.should_execute(plugin.manifest):
            logger.debug(f"Plugin {plugin.name} skipped (trigger rules)")
            skipped.append(plugin.name)
            continue
        
        # Execute plugin
        services = PluginServices(state, events, logger, config, mode="per_job")
        
        try:
            result = plugin.execute(job, services)
            
            if result.status == "success":
                executed.append(plugin.name)
            elif result.status == "failed":
                failed.append(plugin.name)
            elif result.status == "skipped":
                skipped.append(plugin.name)
            
            # Update plugin status
            state.update_plugin_status(plugin.name, result)
            
        except Exception as e:
            logger.error(f"Plugin {plugin.name} crashed", error=str(e))
            failed.append(plugin.name)
    
    # Update job status
    job.status.executed.extend(executed)
    job.status.failed.extend(failed)
    job.status.skipped.extend(skipped)
    
    emit_event("stage.completed", {
        "job_id": job.id,
        "stage": stage,
        "executed": executed,
        "failed": failed,
        "skipped": skipped
    })
```

### Data Stage

```python
def execute_data_stage(job: JobState, state: StateManager):
    """
    Data stage: External data fetching
    
    Plugins:
    - TMDb: Fetch movie metadata
    - TVDb: Fetch TV show metadata
    - OMDb: Alternative metadata source
    - FFprobe: Video file analysis
    - Other data plugins
    
    Note: Plugins can run in parallel if no dependencies
    """
    stage = "data"
    plugins = plugin_registry.get_plugins_by_stage(stage)
    
    logger.info(f"Executing {stage} stage", job_id=job.id)
    emit_event("stage.started", {"job_id": job.id, "stage": stage})
    
    # Topological sort for dependency order
    plugin_groups = topological_sort_plugins(plugins)
    
    # Execute groups (within group = parallel)
    for group in plugin_groups:
        # Filter by trigger rules
        ready = [
            p for p in group
            if trigger_manager.should_execute(p.manifest)
        ]
        
        if not ready:
            continue
        
        # Sequential execution (parallel can be added later)
        for plugin in ready:
            services = PluginServices(state, events, logger, config, mode="per_job")
            
            try:
                result = plugin.execute(job, services)
                
                if result.status == "success":
                    job.status.executed.append(plugin.name)
                elif result.status == "failed":
                    job.status.failed.append(plugin.name)
                elif result.status == "skipped":
                    job.status.skipped.append(plugin.name)
                
                state.update_plugin_status(plugin.name, result)
                
            except Exception as e:
                logger.error(f"Plugin {plugin.name} crashed", error=str(e))
                job.status.failed.append(plugin.name)
    
    emit_event("stage.completed", {
        "job_id": job.id,
        "stage": stage,
        "executed": job.status.executed,
        "failed": job.status.failed
    })
```

### Output Stage

```python
def execute_output_stage(job: JobState, state: StateManager):
    """
    Output stage: File operations and task execution
    
    Plugins:
    - Tasker: Execute tasks (save, print, etc.)
    - RClone: Upload to cloud (optional)
    - Other output plugins
    
    Note: FS locks are enforced here
    """
    stage = "output"
    plugins = plugin_registry.get_plugins_by_stage(stage)
    
    logger.info(f"Executing {stage} stage", job_id=job.id)
    emit_event("stage.started", {"job_id": job.id, "stage": stage})
    
    # Check FS locks before execution
    fs_lock_manager.acquire_locks(plugins, job)
    
    try:
        # Execute plugins
        for plugin in plugins:
            # Check trigger rules
            if not trigger_manager.should_execute(plugin.manifest):
                logger.debug(f"Plugin {plugin.name} skipped")
                job.status.skipped.append(plugin.name)
                continue
            
            # Execute
            services = PluginServices(state, events, logger, config, mode="per_job")
            
            try:
                result = plugin.execute(job, services)
                
                if result.status == "success":
                    job.status.executed.append(plugin.name)
                elif result.status == "failed":
                    job.status.failed.append(plugin.name)
                elif result.status == "skipped":
                    job.status.skipped.append(plugin.name)
                
                state.update_plugin_status(plugin.name, result)
                
            except Exception as e:
                logger.error(f"Plugin {plugin.name} crashed", error=str(e))
                job.status.failed.append(plugin.name)
    
    finally:
        # Release FS locks
        fs_lock_manager.release_locks(plugins, job)
    
    emit_event("stage.completed", {
        "job_id": job.id,
        "stage": stage,
        "executed": job.status.executed,
        "failed": job.status.failed
    })
```

---

## FILESYSTEM LOCK SYSTEM

### FS Lock Architecture

```python
class FSLockManager:
    """
    File system lock manager
    
    Prevents concurrent access to same paths by different plugins
    """
    
    def __init__(self):
        self._locks: Dict[str, str] = {}  # path -> plugin_name
        self._lock = threading.Lock()
    
    def acquire_lock(self, path: str, plugin_name: str):
        """
        Acquire file system lock
        
        Args:
            path: Static file system path (NO variables allowed)
            plugin_name: Plugin requesting lock
        
        Notes:
            - Path must be static (validated at startup)
            - No config/job/run variables allowed
        
        Raises:
            FSLockError: If path already locked
        """
        with self._lock:
            if path in self._locks:
                raise FSLockError(
                    f"Path {path} already locked by {self._locks[path]}"
                )
            self._locks[path] = plugin_name
            logger.debug(f"Lock acquired: {path} by {plugin_name}")
    
    def release_lock(self, path: str, plugin_name: str):
        """Release file system lock"""
        with self._lock:
            if path in self._locks and self._locks[path] == plugin_name:
                del self._locks[path]
                logger.debug(f"Lock released: {path}")
```

### Lock Conflict Detection (Startup)

```python
def detect_lock_conflicts(plugins: List[Plugin]) -> List[str]:
    """
    Detect potential lock conflicts at startup
    
    Returns:
        List of conflict warnings
    """
    conflicts = []
    
    # Group plugins by stage
    stage_plugins = defaultdict(list)
    for plugin in plugins:
        stage = plugin.manifest.get("stage")
        stage_plugins[stage].append(plugin)
    
    # Check each stage
    for stage, plugins_in_stage in stage_plugins.items():
        # Collect lock paths
        lock_paths = defaultdict(list)  # path -> [plugin_names]
        
        for plugin in plugins_in_stage:
            fs_locks = plugin.manifest.get("fs_lock", [])
            
            for lock_path in fs_locks:
                # Resolve static paths
                try:
                    resolved = resolve_static_path(lock_path)
                    lock_paths[resolved].append(plugin.name)
                except:
                    # Dynamic path, check prefix overlap
                    prefix = extract_static_prefix(lock_path)
                    lock_paths[prefix].append(plugin.name)
        
        # Find conflicts (same path locked by multiple plugins)
        for path, plugin_names in lock_paths.items():
            if len(plugin_names) > 1:
                conflicts.append(
                    f"Stage {stage}: Path {path} locked by {plugin_names}"
                )
    
    return conflicts
```

### FS Lock Examples

#### Static Lock

```yaml
# plugins/scanner/manifest.yml
fs_lock:
  - /downloads/movies                 # ✅ Static path only
  - /downloads/shows                  # ✅ Static path only
```

#### Invalid Lock (Runtime Variable)

```yaml
# ❌ INVALID - Runtime variable
fs_lock:
  - "{{job.input.value}}"  # ❌ YASAK - no variables
  - "{{plugin.tmdb.id}}"   # ❌ YASAK - no variables
```

---

## JOB EXECUTION FLOW

### Complete Flow

```python
def execute_job(job: JobState, orchestrator: Orchestrator):
    """
    Execute complete job through all stages
    
    Args:
        job: Job to execute
        orchestrator: Orchestrator instance
    """
    logger.info(f"Starting job execution", job_id=job.id)
    emit_event("job.started", {"job_id": job.id})
    
    job.status.started_at = datetime.now()
    
    try:
        # Stage 1: Parse
        execute_parse_stage(job, state)
        
        # Check if parse failed critically
        if critical_failure_in_stage(job, "parse"):
            raise JobExecutionError("Parse stage failed critically")
        
        # Stage 2: Data
        execute_data_stage(job, state)
        
        # Check if data failed critically
        if critical_failure_in_stage(job, "data"):
            raise JobExecutionError("Data stage failed critically")
        
        # Stage 3: Output
        execute_output_stage(job, state)
        
        # Job completed
        job.status.finished_at = datetime.now()
        job.status.state = "completed"
        job.status.success = len(job.status.failed) == 0
        
        emit_event("job.completed", {
            "job_id": job.id,
            "success": job.status.success,
            "executed": job.status.executed,
            "failed": job.status.failed
        })
        
        logger.info(
            f"Job completed",
            job_id=job.id,
            success=job.status.success,
            duration_ms=job.status.duration_ms
        )
        
    except Exception as e:
        # Job failed
        job.status.finished_at = datetime.now()
        job.status.state = "failed"
        job.status.success = False
        
        emit_event("job.failed", {
            "job_id": job.id,
            "error": str(e)
        })
        
        logger.error(f"Job failed", job_id=job.id, error=str(e))
        
        # Re-raise for queue handler
        raise JobExecutionError(str(e))


def critical_failure_in_stage(job: JobState, stage: str) -> bool:
    """
    Check if stage had critical failures
    
    Returns:
        True if stage should stop job execution
    """
    # For now, continue even with failures (best effort)
    # Can be configured per plugin or per stage
    return False
```

---

## ORCHESTRATOR INTEGRATION

### Run Lifecycle

```python
class Orchestrator:
    """Main orchestrator with job queue"""
    
    def run(self) -> RunResult:
        """Execute complete run"""
        
        # 1. Initialize
        self._initialize()
        
        # 2. Execute per-run plugins (create jobs)
        self._execute_per_run_plugins()
        
        # 3. Execute job queue
        self._execute_job_queue()
        
        # 4. Finalize
        self._finalize()
        
        return self._build_result()
    
    def _execute_per_run_plugins(self):
        """Execute per-run plugins to create jobs"""
        per_run_plugins = self._plugin_registry.get_per_run_plugins()
        
        for plugin in per_run_plugins:
            services = PluginServices(
                self._state,
                self._event_bus,
                self._logger,
                self._config,
                mode="per_run"
            )
            
            try:
                result = plugin.execute_run(services)
                
                if result.status == "failed":
                    self._logger.error(f"Per-run plugin {plugin.name} failed")
                    # Continue (best effort)
                
            except Exception as e:
                self._logger.error(f"Per-run plugin {plugin.name} crashed", error=str(e))
                # Continue (best effort)
    
    def _execute_job_queue(self):
        """Execute all jobs in queue"""
        queue = self._state.get_job_queue()
        
        while not queue.is_empty:
            job = queue.dequeue()
            
            if job is None:
                break
            
            queue.mark_processing(job)
            
            try:
                execute_job(job, self)
                queue.mark_completed(job)
                
            except JobExecutionError as e:
                self._logger.error(f"Job {job.id} failed: {e}")
                queue.mark_failed(job)
                # Continue with next job
            
            except CriticalError as e:
                self._logger.error(f"Critical error: {e}")
                queue.mark_failed(job)
                raise  # Stop processing
```

---

## ERROR HANDLING

### Job Failure

```
Job failure does NOT stop the run.
Each job is independent.

RULE:
- Plugin fails → Mark plugin as failed, continue with next plugin
- Stage fails → Continue to next stage
- Job fails → Continue to next job in queue
- Critical error → Stop run
```

### Plugin Failure Recovery

```python
def execute_plugin_safe(
    plugin: Plugin,
    job: JobState,
    services: PluginServices
) -> PluginResult:
    """Execute plugin with error recovery"""
    
    try:
        # Execute plugin
        result = plugin.execute(job, services)
        return result
        
    except Exception as e:
        # Plugin crashed
        logger.error(
            f"Plugin {plugin.name} crashed",
            job_id=job.id,
            error=str(e),
            traceback=traceback.format_exc()
        )
        
        # Return failed result
        return PluginResult.failed(str(e))
```

---

## PERFORMANCE OPTIMIZATION

### Parallel Job Execution (Future)

```python
async def execute_job_queue_parallel(
    queue: JobQueue,
    max_concurrent: int = 4
):
    """Execute jobs in parallel (future enhancement)"""
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_job_async(job):
        async with semaphore:
            await asyncio.to_thread(execute_job, job, orchestrator)
    
    tasks = []
    while not queue.is_empty:
        job = queue.dequeue()
        if job:
            task = asyncio.create_task(execute_job_async(job))
            tasks.append(task)
    
    await asyncio.gather(*tasks, return_exceptions=True)
```

### Parallel Plugin Execution (Within Stage)

```python
async def execute_plugins_parallel(
    plugins: List[Plugin],
    job: JobState,
    services: PluginServices
):
    """Execute independent plugins in parallel"""
    
    # Group by dependencies
    groups = topological_sort_plugins(plugins)
    
    for group in groups:
        # Execute group in parallel
        tasks = [
            asyncio.to_thread(p.execute, job, services)
            for p in group
            if trigger_manager.should_execute(p.manifest)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for plugin, result in zip(group, results):
            if isinstance(result, Exception):
                logger.error(f"Plugin {plugin.name} failed", error=str(result))
                job.status.failed.append(plugin.name)
            else:
                job.status.executed.append(plugin.name)
                state.update_plugin_status(plugin.name, result)
```

---

## SUMMARY

### Job Lifecycle

```
1. Creation (per_run) → createJob()
2. Queueing → Added to queue
3. Processing (per_job) → parse → data → output
4. Completion → Persist to MongoDB
```

### Stage Order

```
parse → data → output (3 stages)
```

### Execution Rules

```
- Plugin fail → Continue
- Stage fail → Continue
- Job fail → Continue to next job
- Critical error → Stop run
```

### FS Lock Rules

```
✅ ALLOWED: Static paths, config.* variables
❌ FORBIDDEN: job.* variables, run.* variables
```

---

**Next Document**: 06_FILE_STRUCTURE_AND_MODULES.md
