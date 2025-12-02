# MEMORY MANAGEMENT

```yaml
date: 2025-11-30
sources: v7, industry research
status: final
priority: OPTIONAL (Phase 2)
```

**Not:** Bu sistem 10,000+ dosya senaryoları için tasarlandı.
Küçük scale için (< 1000 dosya) gerekli değil. Implementation
Phase 2'de yapılabilir.

---

## 1. PROBLEM

```
10,000 dosya tarama senaryosu:
├── Scanner → 10,000 job oluşturur
├── Renamer → Her job için parse data
├── TMDb → Her job için API response (~5KB)
├── FFProbe → Her job için media info (~2KB)
└── Toplam: ~70-100MB sadece plugin data

Sorun: Unbounded memory growth
```

---

## 2. ÇÖZÜM: HOT/COLD TIERING

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  HOT (RAM)                     COLD (MongoDB)                │
│  ┌─────────────────┐           ┌─────────────────┐          │
│  │ Active jobs     │──flush───►│ Completed jobs  │          │
│  │ Current run     │           │ Historical runs │          │
│  │ max: 500MB      │◄──lazy────│                 │          │
│  └─────────────────┘   load    └─────────────────┘          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. CONFIG

```yaml
# config.yml
options:
  memory:
    max_state_mb: 500           # RAM limit (default: 500)
    flush_threshold: 0.8        # Flush at 80% capacity
    eviction_policy: completed_first
    lazy_cache_size: 10         # LRU cache for loaded jobs
```

---

## 4. COMPONENTS

### 4.1 MemoryTracker

```python
class MemoryTracker:
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self._sizes: Dict[str, int] = {}  # job_id -> size
    
    def track(self, job_id: str, job: JobState) -> None:
        size = self._estimate_size(job)
        self._sizes[job_id] = size
        self.current_bytes += size
    
    def untrack(self, job_id: str) -> None:
        if job_id in self._sizes:
            self.current_bytes -= self._sizes.pop(job_id)
    
    def should_flush(self) -> bool:
        threshold = self.max_bytes * 0.8
        return self.current_bytes >= threshold
    
    def _estimate_size(self, obj) -> int:
        # Deep size estimation
        return len(json.dumps(obj.to_dict()))
```

### 4.2 FlushManager

```python
class FlushManager:
    def __init__(self, persistence: PersistenceInterface, tracker: MemoryTracker):
        self._persistence = persistence
        self._tracker = tracker
    
    def flush_completed(self, state: StateManager) -> int:
        """Flush completed jobs, return count"""
        flushed = 0
        for job in state.get_completed_jobs():
            self._persistence.save_job(job)
            for name, data in job.plugins.items():
                self._persistence.save_plugin_result(
                    job.run_id, job.job_id, name, data
                )
            state.evict_job(job.job_id)
            self._tracker.untrack(job.job_id)
            flushed += 1
        return flushed
    
    def flush_if_needed(self, state: StateManager) -> None:
        if self._tracker.should_flush():
            self.flush_completed(state)
```

### 4.3 LazyLoader

```python
class LazyLoader:
    def __init__(self, persistence: PersistenceInterface, cache_size: int = 10):
        self._persistence = persistence
        self._cache: OrderedDict[str, JobState] = OrderedDict()
        self._cache_size = cache_size
    
    def load(self, job_id: str) -> Optional[JobState]:
        # Check cache
        if job_id in self._cache:
            self._cache.move_to_end(job_id)
            return self._cache[job_id]
        
        # Load from MongoDB
        job = self._persistence.get_job(job_id)
        if not job:
            return None
        
        # Add to cache with LRU eviction
        self._cache[job_id] = job
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        
        return job
```

---

## 5. STATE MANAGER INTEGRATION

```python
class StateManager:
    def __init__(self, config: Dict):
        memory_config = config.get('memory', {})
        max_mb = memory_config.get('max_state_mb', 500)
        
        self._tracker = MemoryTracker(max_mb * 1024 * 1024)
        self._flush_manager = FlushManager(self._persistence, self._tracker)
        self._lazy_loader = LazyLoader(self._persistence)
        
        self._hot_jobs: Dict[str, JobState] = {}
        self._cold_job_ids: Set[str] = set()
    
    def register_job(self, index: int, path: str) -> JobState:
        job = JobState(index=index, run_id=self._run.id, ...)
        self._hot_jobs[job.job_id] = job
        self._tracker.track(job.job_id, job)
        
        # Check memory
        self._flush_manager.flush_if_needed(self)
        
        return job
    
    def get_job(self, job_id: str) -> Optional[JobState]:
        # Hot path
        if job_id in self._hot_jobs:
            return self._hot_jobs[job_id]
        
        # Cold path
        if job_id in self._cold_job_ids:
            return self._lazy_loader.load(job_id)
        
        return None
    
    def evict_job(self, job_id: str) -> None:
        """Move job from hot to cold"""
        if job_id in self._hot_jobs:
            del self._hot_jobs[job_id]
            self._cold_job_ids.add(job_id)
    
    def get_completed_jobs(self) -> List[JobState]:
        """Get jobs ready for flushing"""
        return [
            j for j in self._hot_jobs.values()
            if j.status.state == JobStatusEnum.COMPLETED
        ]
```

---

## 6. EXECUTION FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY-AWARE EXECUTION                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Register job                                             │
│     ├── Create JobState in hot_jobs                          │
│     └── Track memory                                         │
│                                                              │
│  2. Execute plugins                                          │
│     ├── Add plugin data to job.plugins                       │
│     └── Update memory tracking                               │
│                                                              │
│  3. Complete job                                             │
│     ├── Mark as COMPLETED                                    │
│     └── Check: should_flush()?                               │
│         ├── YES: flush_completed()                           │
│         │   ├── Save to MongoDB                              │
│         │   ├── Remove from hot_jobs                         │
│         │   └── Add to cold_job_ids                          │
│         └── NO: Continue                                     │
│                                                              │
│  4. Plugin needs old job?                                    │
│     └── lazy_loader.load(job_id)                             │
│         ├── Check LRU cache                                  │
│         └── Load from MongoDB if needed                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. EVICTION POLICIES

### 7.1 completed_first (Default)

```
Priority: Flush completed jobs first
Reason: Completed jobs are less likely to be accessed
```

### 7.2 lru

```
Priority: Least Recently Used
Reason: Jobs not accessed recently are cold
```

### 7.3 oldest_first

```
Priority: By index (lowest first)
Reason: Earlier jobs are typically processed first
```

---

## 8. BATCH MODE HANDLING

```python
class BatchModeJobAccess:
    """Streaming access for batch plugins"""
    
    def __init__(self, state: StateManager):
        self._state = state
    
    def iter_all_jobs(self) -> Iterator[JobState]:
        """Stream jobs without loading all in memory"""
        # Hot jobs first
        for job in self._state._hot_jobs.values():
            yield job
        
        # Cold jobs from MongoDB
        for job_id in self._state._cold_job_ids:
            job = self._state._lazy_loader.load(job_id)
            if job:
                yield job
    
    def get_job_count(self) -> int:
        return len(self._state._hot_jobs) + len(self._state._cold_job_ids)
```

---

## 9. MEMORY ESTIMATION

```python
def estimate_memory_per_job() -> int:
    """Average memory per job in bytes"""
    
    # Base JobState: ~500 bytes
    # JobInput: ~200 bytes
    # JobStatus: ~300 bytes
    # JobOutput: ~200 bytes (varies)
    
    # Plugin data (typical):
    # - scanner: ~100 bytes
    # - renamer: ~500 bytes
    # - tmdb: ~5000 bytes
    # - ffprobe: ~2000 bytes
    
    # Total: ~9000 bytes per job
    return 9000

def estimate_max_jobs(max_mb: int) -> int:
    """Max jobs that fit in memory"""
    max_bytes = max_mb * 1024 * 1024
    per_job = estimate_memory_per_job()
    return max_bytes // per_job

# Example:
# 500 MB / 9 KB = ~55,000 jobs in memory
```

---

## 10. MONITORING

```python
class MemoryStats:
    def __init__(self, tracker: MemoryTracker):
        self._tracker = tracker
    
    def get_stats(self) -> Dict:
        return {
            'current_bytes': self._tracker.current_bytes,
            'max_bytes': self._tracker.max_bytes,
            'usage_percent': (self._tracker.current_bytes / self._tracker.max_bytes) * 100,
            'jobs_in_memory': len(self._tracker._sizes),
            'should_flush': self._tracker.should_flush()
        }
```

---

**Son Güncelleme:** 2025-11-30
