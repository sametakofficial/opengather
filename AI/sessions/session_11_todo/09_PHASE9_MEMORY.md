# PHASE 9: MEMORY MANAGEMENT

```yaml
phase: 9
öncelik: 🟢 DÜŞÜK (OPSİYONEL)
tahmini_süre: 4-6 saat
bağımlılık: P2 (MongoDB), P8 (FastAPI)
strateji_belgesi: 07_memory_management.md
test_türü: performance
```

---

## ⚠️ ÖNEMLİ NOT

**Bu phase OPSİYONEL'dir.** Sadece aşağıdaki durumlarda gereklidir:

- 10.000+ dosya işleniyorsa
- Memory tüketimi 1GB'ı aşıyorsa
- Performans sorunları yaşanıyorsa

Küçük-orta ölçekli kullanımda bu phase atlanabilir.

---

## ✅ ÖN KOŞUL KONTROLÜ

- [ ] P2 tamamlandı (MongoDB persistence çalışıyor)
- [ ] P8 tamamlandı (API endpoints çalışıyor)
- [ ] Performans sorunu tespit edildi
- [ ] Memory profiling yapıldı

---

## 1. MEVCUT DURUM VE PROBLEM

### 1.1 Problem Senaryosu

```
10.000 dosya x 5 plugin x 10KB/plugin data = ~500MB memory

SORUN: Tüm plugin data memory'de tutuluyor
- Aktif run: ~50MB (sadece gerekli)
- Tamamlanmış: ~450MB (erişilmeyebilir)
```

### 1.2 Mevcut Davranış

```python
# MEVCUT - Tüm data memory'de
class StateManager:
    def __init__(self):
        self._jobs = {}  # Tüm job'lar
        self._plugins = {}  # Tüm plugin data

    def update_plugin_data(self, job_id, plugin_name, data):
        # Memory'e yaz
        self._plugins[job_id][plugin_name] = data
        # MongoDB'ye de yaz
        self._persistence.save_plugin(...)
```

---

## 2. HEDEF YAPI: HOT/COLD TİERİNG

### 2.1 Konsept

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY TİERİNG SİSTEMİ                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  HOT TIER (Memory)              COLD TIER (MongoDB)         │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │ Aktif Run        │          │ Tamamlanmış      │         │
│  │ + jobs           │   ──→    │ Run'lar          │         │
│  │ + plugins        │ EVICT    │ + plugins        │         │
│  │ (hızlı erişim)   │          │ (kalıcı)         │         │
│  └──────────────────┘          └──────────────────┘         │
│         ↑                              │                     │
│         │ LAZY LOAD                    │                     │
│         └──────────────────────────────┘                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Eviction Policy

```
┌─────────────────────────────────────────────────────────────┐
│                    EVICTION POLİCY                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Policy: completed_first                                     │
│                                                              │
│  1. Memory threshold aşıldı (500MB default)                 │
│  2. Tamamlanmış job'ların plugin data'sı seçilir            │
│  3. Plugin data MongoDB'ye yazılır (zaten yazılmış)         │
│  4. Memory'den silinir (only reference)                     │
│  5. Aktif job'ların data'sı KORUNUR                         │
│                                                              │
│  PRIORITY:                                                   │
│  - En eski completed job → ilk evict                        │
│  - Aktif run job'ları → ASLA evict                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. ADIM ADIM UYGULAMA

### ADIM 1: MemoryTracker Class

**Dosya:** `src/archiverr/core/memory/tracker.py` (YENİ)

```python
"""Memory usage tracking"""

import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass
import gc


@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_mb: float
    plugins_mb: float
    jobs_mb: float
    threshold_mb: float
    should_evict: bool


class MemoryTracker:
    """
    Track memory usage and determine when to evict.

    Uses sys.getsizeof for rough estimation.
    For production, consider tracemalloc or memory_profiler.
    """

    def __init__(self, threshold_mb: float = 500.0):
        self._threshold_mb = threshold_mb
        self._plugin_cache: Dict[str, Dict[str, Any]] = {}
        self._size_cache: Dict[str, int] = {}  # job_id -> estimated size

    def register_plugin_data(self, job_id: str, plugin_name: str, data: Any) -> None:
        """Register plugin data for tracking"""
        if job_id not in self._plugin_cache:
            self._plugin_cache[job_id] = {}

        self._plugin_cache[job_id][plugin_name] = data

        # Update size estimation
        self._size_cache[job_id] = self._estimate_size(self._plugin_cache[job_id])

    def unregister_job(self, job_id: str) -> None:
        """Remove job from tracking (after eviction)"""
        self._plugin_cache.pop(job_id, None)
        self._size_cache.pop(job_id, None)

    def get_stats(self) -> MemoryStats:
        """Get current memory statistics"""
        plugins_bytes = sum(self._size_cache.values())
        plugins_mb = plugins_bytes / (1024 * 1024)

        return MemoryStats(
            total_mb=self._get_process_memory_mb(),
            plugins_mb=plugins_mb,
            jobs_mb=0,  # TODO: Track jobs separately
            threshold_mb=self._threshold_mb,
            should_evict=plugins_mb > self._threshold_mb
        )

    def should_evict(self) -> bool:
        """Check if eviction is needed"""
        stats = self.get_stats()
        return stats.should_evict

    def get_eviction_candidates(self, completed_job_ids: list) -> list:
        """
        Get jobs to evict, prioritized by oldest first.

        Args:
            completed_job_ids: List of completed job IDs

        Returns:
            List of job IDs to evict
        """
        # Filter to only jobs we're tracking
        candidates = [
            job_id for job_id in completed_job_ids
            if job_id in self._plugin_cache
        ]

        # Sort by size (largest first for max memory recovery)
        candidates.sort(key=lambda jid: self._size_cache.get(jid, 0), reverse=True)

        return candidates

    def _estimate_size(self, obj: Any) -> int:
        """Estimate object size in bytes"""
        try:
            if isinstance(obj, dict):
                return sum(
                    self._estimate_size(k) + self._estimate_size(v)
                    for k, v in obj.items()
                )
            elif isinstance(obj, (list, tuple)):
                return sum(self._estimate_size(item) for item in obj)
            elif isinstance(obj, str):
                return len(obj.encode('utf-8'))
            else:
                return sys.getsizeof(obj)
        except Exception:
            return 100  # Default estimate

    def _get_process_memory_mb(self) -> float:
        """Get current process memory usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            # Fallback: use gc to estimate
            gc.collect()
            return sum(
                sys.getsizeof(obj) for obj in gc.get_objects()
            ) / (1024 * 1024)
```

---

### ADIM 2: FlushManager Class

**Dosya:** `src/archiverr/core/memory/flush_manager.py` (YENİ)

```python
"""Memory flush management"""

from typing import Dict, List, Set, Optional
from datetime import datetime
import threading

from archiverr.infrastructure.persistence import PersistenceInterface
from archiverr.state.manager import StateManager
from .tracker import MemoryTracker


class FlushManager:
    """
    Manages flushing (evicting) plugin data from memory to MongoDB.

    Eviction happens when:
    1. Memory threshold exceeded
    2. Run completed
    3. Manual trigger
    """

    def __init__(
        self,
        state: StateManager,
        persistence: PersistenceInterface,
        tracker: MemoryTracker
    ):
        self._state = state
        self._persistence = persistence
        self._tracker = tracker
        self._evicted_jobs: Set[str] = set()  # Jobs with evicted plugin data
        self._lock = threading.Lock()

    def check_and_evict(self) -> int:
        """
        Check memory and evict if needed.

        Returns:
            Number of jobs evicted
        """
        if not self._tracker.should_evict():
            return 0

        return self._evict_completed_jobs()

    def _evict_completed_jobs(self) -> int:
        """Evict completed job plugin data"""
        with self._lock:
            # Get completed job IDs
            completed_jobs = self._state.get_completed_job_ids()

            # Filter out already evicted
            candidates = [
                jid for jid in completed_jobs
                if jid not in self._evicted_jobs
            ]

            # Get prioritized candidates
            to_evict = self._tracker.get_eviction_candidates(candidates)

            evicted_count = 0
            for job_id in to_evict:
                if self._evict_job(job_id):
                    evicted_count += 1

                # Check if we're below threshold now
                if not self._tracker.should_evict():
                    break

            return evicted_count

    def _evict_job(self, job_id: str) -> bool:
        """
        Evict a single job's plugin data.

        Plugin data is already in MongoDB (written on plugin complete).
        We just need to clear the in-memory reference.

        Args:
            job_id: Job ID to evict

        Returns:
            True if evicted successfully
        """
        try:
            # Clear from state manager's cache
            self._state.clear_plugin_cache(job_id)

            # Clear from tracker
            self._tracker.unregister_job(job_id)

            # Mark as evicted
            self._evicted_jobs.add(job_id)

            return True
        except Exception as e:
            # Log error but don't fail
            print(f"Failed to evict job {job_id}: {e}")
            return False

    def evict_run(self, run_id: str) -> int:
        """
        Evict all plugin data for a completed run.

        Called when run completes.

        Args:
            run_id: Run ID

        Returns:
            Number of jobs evicted
        """
        with self._lock:
            jobs = self._state.get_jobs_by_run(run_id)

            evicted_count = 0
            for job in jobs:
                if self._evict_job(job.id):
                    evicted_count += 1

            return evicted_count

    def is_evicted(self, job_id: str) -> bool:
        """Check if job's plugin data was evicted"""
        return job_id in self._evicted_jobs
```

---

### ADIM 3: LazyLoader Class

**Dosya:** `src/archiverr/core/memory/lazy_loader.py` (YENİ)

```python
"""Lazy loading for evicted plugin data"""

from typing import Dict, Any, Optional

from archiverr.infrastructure.persistence import PersistenceInterface


class LazyLoader:
    """
    Lazy load plugin data from MongoDB.

    Used when accessing evicted plugin data.
    """

    def __init__(self, persistence: PersistenceInterface):
        self._persistence = persistence
        self._load_cache: Dict[str, Dict[str, Any]] = {}  # Temporary cache

    def load_plugin_data(
        self,
        job_id: str,
        plugin_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load plugin data from MongoDB.

        Args:
            job_id: Job ID
            plugin_name: Plugin name

        Returns:
            Plugin data dict or None if not found
        """
        cache_key = f"{job_id}:{plugin_name}"

        # Check temporary cache
        if cache_key in self._load_cache:
            return self._load_cache[cache_key]

        # Load from MongoDB
        plugins = self._persistence.get_plugins(filter_dict={
            "job_id": job_id,
            "plugin_name": plugin_name
        })

        if not plugins:
            return None

        data = plugins[0].get("data", {})

        # Store in temporary cache (don't keep forever)
        self._load_cache[cache_key] = data

        return data

    def load_all_plugins_for_job(self, job_id: str) -> Dict[str, Any]:
        """
        Load all plugin data for a job.

        Args:
            job_id: Job ID

        Returns:
            Dict of {plugin_name: data}
        """
        plugins = self._persistence.get_plugins(filter_dict={"job_id": job_id})

        result = {}
        for plugin in plugins:
            name = plugin.get("plugin_name")
            data = plugin.get("data", {})
            result[name] = data

            # Cache it
            cache_key = f"{job_id}:{name}"
            self._load_cache[cache_key] = data

        return result

    def clear_cache(self, job_id: str = None) -> None:
        """
        Clear temporary load cache.

        Args:
            job_id: If provided, clear only this job's cache
        """
        if job_id:
            keys_to_remove = [
                k for k in self._load_cache
                if k.startswith(f"{job_id}:")
            ]
            for key in keys_to_remove:
                del self._load_cache[key]
        else:
            self._load_cache.clear()
```

---

### ADIM 4: StateManager Entegrasyonu

**Dosya:** `src/archiverr/state/manager.py` (güncelle)

```python
# StateManager'a memory management ekleme

class StateManager:
    def __init__(self):
        # ... existing ...
        self._memory_tracker: Optional[MemoryTracker] = None
        self._flush_manager: Optional[FlushManager] = None
        self._lazy_loader: Optional[LazyLoader] = None

    def configure_memory_management(
        self,
        threshold_mb: float = 500.0,
        enabled: bool = True
    ) -> None:
        """
        Configure memory management.

        Args:
            threshold_mb: Memory threshold for eviction
            enabled: Enable/disable memory management
        """
        if not enabled:
            return

        from archiverr.core.memory import MemoryTracker, FlushManager, LazyLoader

        self._memory_tracker = MemoryTracker(threshold_mb)
        self._lazy_loader = LazyLoader(self._persistence)
        self._flush_manager = FlushManager(
            state=self,
            persistence=self._persistence,
            tracker=self._memory_tracker
        )

    def update_plugin_data(self, job_id: str, plugin_name: str, data: Any) -> None:
        """Update plugin data with memory tracking"""
        # Store in memory
        if job_id not in self._plugins:
            self._plugins[job_id] = {}
        self._plugins[job_id][plugin_name] = data

        # Track for memory management
        if self._memory_tracker:
            self._memory_tracker.register_plugin_data(job_id, plugin_name, data)

        # Persist to MongoDB
        self._persistence.save_plugin({
            "job_id": job_id,
            "run_id": self._current_run_id,
            "plugin_name": plugin_name,
            "data": data
        })

        # Check if eviction needed
        if self._flush_manager:
            self._flush_manager.check_and_evict()

    def get_plugin_data(self, job_id: str, plugin_name: str) -> Optional[Dict]:
        """Get plugin data with lazy loading"""
        # Check memory cache first
        if job_id in self._plugins and plugin_name in self._plugins[job_id]:
            return self._plugins[job_id][plugin_name]

        # If evicted, lazy load
        if self._flush_manager and self._flush_manager.is_evicted(job_id):
            if self._lazy_loader:
                return self._lazy_loader.load_plugin_data(job_id, plugin_name)

        return None

    def clear_plugin_cache(self, job_id: str) -> None:
        """Clear plugin data from memory (for eviction)"""
        self._plugins.pop(job_id, None)

    def complete_run(self, success: bool = True) -> None:
        """Complete run with memory cleanup"""
        # ... existing completion logic ...

        # Evict completed run's plugin data
        if self._flush_manager:
            self._flush_manager.evict_run(self._current_run_id)
```

---

## 4. CONFIG ENTEGRASYONU

```yaml
# config.yml

options:
  debug: true
  dry_run: false

  # Memory management (Phase 9)
  memory:
    enabled: true # Enable/disable
    threshold_mb: 500 # Eviction threshold
    eviction_policy: completed_first # Policy (only one for now)
```

```python
# Orchestrator'da config okuma
def _initialize(self):
    memory_config = self._config.get('options', {}).get('memory', {})

    if memory_config.get('enabled', False):
        self._state.configure_memory_management(
            threshold_mb=memory_config.get('threshold_mb', 500),
            enabled=True
        )
```

---

## 5. TEST SENARYOLARI

### 5.1 Unit Tests

```python
# tests/unit/core/memory/test_memory_management.py

import pytest
from archiverr.core.memory import MemoryTracker, FlushManager, LazyLoader


class TestMemoryTracker:
    def test_initial_state(self):
        tracker = MemoryTracker(threshold_mb=100)
        stats = tracker.get_stats()

        assert stats.threshold_mb == 100
        assert stats.plugins_mb == 0
        assert stats.should_evict == False

    def test_register_plugin_data(self):
        tracker = MemoryTracker(threshold_mb=1)  # 1MB threshold

        # Register small data
        tracker.register_plugin_data("job1", "plugin1", {"key": "value"})

        stats = tracker.get_stats()
        assert stats.plugins_mb > 0

    def test_should_evict_on_threshold(self):
        tracker = MemoryTracker(threshold_mb=0.001)  # Very low threshold

        # Register some data
        large_data = {"data": "x" * 10000}  # ~10KB
        tracker.register_plugin_data("job1", "plugin1", large_data)

        assert tracker.should_evict() == True

    def test_eviction_candidates(self):
        tracker = MemoryTracker(threshold_mb=100)

        tracker.register_plugin_data("job1", "p1", {"a": 1})
        tracker.register_plugin_data("job2", "p1", {"a": "x" * 1000})

        candidates = tracker.get_eviction_candidates(["job1", "job2"])

        # Larger job should be first
        assert candidates[0] == "job2"


class TestFlushManager:
    @pytest.fixture
    def setup(self):
        from unittest.mock import Mock

        state = Mock()
        persistence = Mock()
        tracker = MemoryTracker(threshold_mb=0.001)

        return FlushManager(state, persistence, tracker)

    def test_evict_job(self, setup):
        manager = setup
        manager._state.clear_plugin_cache = Mock()

        result = manager._evict_job("job1")

        assert result == True
        assert "job1" in manager._evicted_jobs


class TestLazyLoader:
    def test_load_from_mongodb(self):
        from unittest.mock import Mock

        persistence = Mock()
        persistence.get_plugins.return_value = [{
            "job_id": "job1",
            "plugin_name": "tmdb",
            "data": {"movie": {"title": "Test"}}
        }]

        loader = LazyLoader(persistence)
        data = loader.load_plugin_data("job1", "tmdb")

        assert data["movie"]["title"] == "Test"

    def test_cache_hit(self):
        from unittest.mock import Mock

        persistence = Mock()
        persistence.get_plugins.return_value = [{"data": {"x": 1}}]

        loader = LazyLoader(persistence)

        # First call - hits MongoDB
        loader.load_plugin_data("job1", "p1")

        # Second call - should hit cache
        loader.load_plugin_data("job1", "p1")

        # MongoDB should only be called once
        assert persistence.get_plugins.call_count == 1
```

### 5.2 Performance Tests

```python
# tests/performance/test_memory_management.py

import pytest
import time


class TestMemoryPerformance:
    def test_10k_jobs_memory_bounded(self):
        """10.000 job ile memory threshold aşılmamalı"""
        from archiverr.core.memory import MemoryTracker, FlushManager

        tracker = MemoryTracker(threshold_mb=50)  # 50MB limit

        # Simulate 10k jobs
        for i in range(10000):
            job_id = f"job_{i}"
            data = {"data": f"value_{i}" * 100}  # ~1KB per plugin

            tracker.register_plugin_data(job_id, "plugin1", data)

            # Check threshold periodically
            if i % 1000 == 0:
                stats = tracker.get_stats()
                print(f"Job {i}: {stats.plugins_mb:.2f}MB")

        stats = tracker.get_stats()
        # With eviction, should stay under control

    def test_lazy_load_performance(self):
        """Lazy load 1000 ms'den az sürmeli"""
        from unittest.mock import Mock
        from archiverr.core.memory import LazyLoader

        persistence = Mock()
        persistence.get_plugins.return_value = [{"data": {"x": 1}}]

        loader = LazyLoader(persistence)

        start = time.time()
        for i in range(1000):
            loader.load_plugin_data(f"job_{i}", "plugin1")
        duration = time.time() - start

        assert duration < 1.0, f"Too slow: {duration}s"
```

---

## 6. PHASE 9 TAMAMLAMA KRİTERLERİ

### ✅ Tamamlandı Sayılması İçin:

- [ ] `MemoryTracker` sınıfı oluşturuldu
- [ ] `FlushManager` sınıfı oluşturuldu
- [ ] `LazyLoader` sınıfı oluşturuldu
- [ ] StateManager entegrasyonu tamamlandı
- [ ] Config entegrasyonu (options.memory.\*)
- [ ] Eviction çalışıyor (threshold aşılınca)
- [ ] Lazy loading çalışıyor
- [ ] Aktif run korunuyor (evict edilmiyor)
- [ ] Unit testler PASS
- [ ] Performance testler PASS

### ⚠️ Henüz Yapılmaması Gerekenler:

- ❌ Async eviction (background thread)
- ❌ Multiple eviction policies
- ❌ Memory profiling dashboard
- ❌ Redis cache tier (gelecek versiyon)

---

## 7. OLASI SORUNLAR VE ÇÖZÜMLER

| Sorun                   | Belirti                | Çözüm                                   |
| ----------------------- | ---------------------- | --------------------------------------- |
| psutil not installed    | Fallback kullanılır    | pip install psutil (opsiyonel)          |
| Eviction too aggressive | Data sürekli lazy load | Threshold'u artır                       |
| Lazy load slow          | Yavaş API response     | MongoDB index kontrol                   |
| Memory still high       | Eviction çalışmıyor    | FlushManager.check_and_evict() log ekle |
| Concurrent access       | Race condition         | Lock kullan (thread-safe)               |

---

## 8. MONITORING

```python
# Memory stats endpoint (opsiyonel)
@router.get("/v1/system/memory")
async def get_memory_stats():
    stats = state_manager._memory_tracker.get_stats()

    return {
        "total_mb": stats.total_mb,
        "plugins_mb": stats.plugins_mb,
        "threshold_mb": stats.threshold_mb,
        "should_evict": stats.should_evict,
        "evicted_jobs": len(flush_manager._evicted_jobs)
    }
```

---

## 9. SONRAKİ ADIMLAR

Phase 9 tamamlandığında:

1. Git commit: `feat(memory): add hot/cold tiering for plugin data`
2. Git tag: `v0.x.x-phase9`
3. Performance testleri çalıştır
4. 10.000+ dosya ile gerçek test

---

**⚠️ HATIRLATMA: Bu phase opsiyoneldir!**

Performans sorunu yaşanmadıkça P1-P8 yeterlidir.

---

**✅ PHASE BİTİŞ KONTROLÜ:**

- `pytest tests/unit/core/memory/` çalıştır
- Performance test: `pytest tests/performance/ -v`
- Memory monitoring: `/v1/system/memory` endpoint
- Gerçek 10k dosya testi (opsiyonel)
