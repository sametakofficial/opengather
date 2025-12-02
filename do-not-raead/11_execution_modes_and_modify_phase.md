# EXECUTION MODES & MODIFY PHASE

```yaml
date: 2025-11-30
sources: industry research (FlexGet, Airflow), user feedback
status: final
```

---

## 1. EXECUTION MODE TANIMI

```
MODE        WHEN                    USE CASE
────────────────────────────────────────────────────────────
per_job     Her job için ayrı       Renamer, FFProbe, TMDb
per_run     Run başına bir kez      Rclone sync, Summary report
```

**per_run = batch DEĞİL**

```
batch       → "Tüm job'lara erişir ama her job için ayrı result üretir"
per_run     → "Run'da bir kez çalışır, job bazlı değil"
```

---

## 2. PHASE + MODE MATRİSİ

```
Phase       Allowed Modes      Typical Plugins
─────────────────────────────────────────────────────────────
input       per_run            Scanner (run başında bir kez)
parse       per_job            Renamer (her job için)
metadata    per_job            TMDb, FFProbe (her job için)
modify      per_job, per_run   DuplicateCleaner, Rclone
finalize    per_run            Summary, Cleanup, Sync
```

**Yeni Phase: FINALIZE**

```
input → parse → metadata → modify → finalize → task_execution
                                       │
                                       └── per_run only, always runs
```

---

## 3. FINALIZE PHASE

### 3.1 Neden Gerekli?

```
Problem:
- Rclone sync tüm işlemler bittikten sonra çalışmalı
- DuplicateCleaner dosya sildikten sonra Rclone tetiklenmeli
- Summary report en son çalışmalı

Çözüm:
- finalize phase: Her zaman en son çalışır
- trigger_rule: all_done (Airflow pattern)
```

### 3.2 FlexGet Karşılaştırması

```
FlexGet Phases:
start → input → metainfo → filter → download → modify → output → learn → exit

Archiverr Phases:
input → parse → metadata → modify → finalize → (task execution)
```

---

## 4. ÇAKIŞMA YÖNETİMİ

### 4.1 Problem Senaryosu

```
DuplicateCleaner       Rclone Sync
      │                     │
      │ silme işlemi        │ sync işlemi
      ▼                     ▼
   /media/                /remote/
      │                     │
      └─────────────────────┘
              ?
      Sonsuz döngü riski
```

### 4.2 Çözüm: Event-Driven Coordination

```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT COORDINATION                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  EventBus Events:                                            │
│  ├── file.created     {path, job_id}                         │
│  ├── file.deleted     {path, job_id}                         │
│  ├── file.moved       {src, dst, job_id}                     │
│  ├── file.renamed     {old, new, job_id}                     │
│  └── files.batch_changed {changes: [...]}                    │
│                                                              │
│  Phase Events:                                               │
│  ├── phase.started    {phase_name}                           │
│  ├── phase.completed  {phase_name, stats}                    │
│  └── phase.failed     {phase_name, error}                    │
│                                                              │
│  Plugin Events:                                              │
│  ├── plugin.started   {name, phase}                          │
│  ├── plugin.completed {name, phase, duration}                │
│  └── plugin.failed    {name, phase, error}                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Çakışma Çözümü

```
DuplicateCleaner (modify phase):
├── Dosya sil
├── EventBus.emit('file.deleted', {path})
└── Complete

Rclone (finalize phase):
├── Subscribe: file.deleted, file.moved, file.renamed
├── Collect changes during run
├── finalize phase başladığında:
│   └── Batch sync (collected changes)
└── Complete
```

---

## 5. PRIORITY SİSTEMİ

### 5.1 Phase İçi Sıralama

```python
# manifest.yml
name: duplicate_cleaner
phase: modify
priority: 100              # Lower = runs first

name: rclone_sync
phase: finalize
priority: 200              # Runs after cleanup
```

### 5.2 Priority Ranges

```
Priority    Purpose
────────────────────────────────────
1-99        Critical (runs first)
100-199     Normal
200-255     Deferred (runs last)
```

---

## 6. MANIFEST SCHEMA UPDATE

```yaml
# plugins/{name}/manifest.yml
name: string
version: string
phase: input | parse | metadata | modify | finalize
execution_mode: per_job | per_run
priority: int                    # 1-255, default: 100
requires: List[string]

# Event subscriptions
subscribes:
  - file.deleted
  - file.moved
  - phase.completed

# Trigger rule (for finalize phase)
trigger_rule: all_done | all_success   # default: all_success
```

---

## 7. ÖRNEK: RCLONE PLUGIN

```yaml
# plugins/rclone/manifest.yml
name: rclone
version: 1.0.0
description: Sync files to remote storage
phase: finalize
execution_mode: per_run
priority: 200
requires: []
subscribes:
  - file.created
  - file.moved
  - file.deleted
trigger_rule: all_done
```

```python
# plugins/rclone/client.py
class RclonePlugin(BasePlugin):
    def __init__(self):
        self._pending_syncs = []
    
    def on_event(self, event: str, data: Dict):
        """EventBus callback"""
        if event in ['file.created', 'file.moved']:
            self._pending_syncs.append(data['path'])
    
    def execute_run(self, services: PluginServices) -> PluginResult:
        """per_run execution"""
        if not self._pending_syncs:
            return PluginResult.skipped("No files to sync")
        
        # Batch sync all pending files
        synced = self._sync_batch(self._pending_syncs)
        self._pending_syncs.clear()
        
        return PluginResult.success({'synced_count': synced})
```

---

## 8. ÖRNEK: DUPLICATE CLEANER

```yaml
# plugins/duplicate_cleaner/manifest.yml
name: duplicate_cleaner
version: 1.0.0
phase: modify
execution_mode: per_run
priority: 100
requires:
  - ffprobe.video
```

```python
class DuplicateCleanerPlugin(BasePlugin):
    def execute_run(self, services: PluginServices) -> PluginResult:
        """Analyze all jobs, find and remove duplicates"""
        jobs = services.jobs.get_all()
        duplicates = self._find_duplicates(jobs)
        
        for dup in duplicates:
            os.remove(dup.path)
            services.events.emit('file.deleted', {'path': dup.path})
        
        return PluginResult.success({'removed': len(duplicates)})
```

---

## 9. EXECUTION FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    FULL EXECUTION FLOW                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT PHASE (per_run)                                       │
│  └── Scanner.execute_run() → creates jobs                    │
│                                                              │
│  PARSE PHASE (per_job)                                       │
│  └── For each job: Renamer.execute(job)                      │
│                                                              │
│  METADATA PHASE (per_job)                                    │
│  └── For each job: TMDb.execute(job), FFProbe.execute(job)   │
│                                                              │
│  MODIFY PHASE (per_job or per_run)                           │
│  ├── DuplicateCleaner.execute_run()                          │
│  │   └── emit('file.deleted') for each                       │
│  └── Splitter.execute_run() → may create new jobs            │
│                                                              │
│  FINALIZE PHASE (per_run, always runs)                       │
│  ├── Rclone.execute_run()                                    │
│  │   └── Batch sync collected changes                        │
│  └── Summary.execute_run()                                   │
│                                                              │
│  TASK EXECUTION (per job)                                    │
│  └── TaskManager handles print/save tasks                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. BASE PLUGIN INTERFACE

```python
class BasePlugin(ABC):
    @property
    def execution_mode(self) -> str:
        return self.manifest.execution_mode
    
    # per_job mode
    def execute(self, job: Job, services: PluginServices) -> PluginResult:
        raise NotImplementedError
    
    # per_run mode
    def execute_run(self, services: PluginServices) -> PluginResult:
        raise NotImplementedError
    
    # Event handler (optional)
    def on_event(self, event: str, data: Dict) -> None:
        pass
```

---

## 11. PHASE EXECUTOR UPDATE

```python
class PhaseExecutor:
    PHASES = ['input', 'parse', 'metadata', 'modify', 'finalize']
    
    def _execute_phase(self, phase: str) -> None:
        plugins = self._get_plugins_for_phase(phase)
        plugins = sorted(plugins, key=lambda p: p.priority)
        
        for plugin in plugins:
            # Subscribe to events
            for event in plugin.manifest.subscribes:
                self._event_bus.subscribe(event, plugin.on_event)
            
            # Execute based on mode
            if plugin.execution_mode == 'per_run':
                result = plugin.execute_run(self._services)
                self._state.update_run_plugin(plugin.name, result)
            else:
                for job in self._state.get_all_jobs():
                    result = plugin.execute(job, self._services)
                    self._state.update_plugin(job.index, plugin.name, result)
```

---

## 12. ÖZETr

```
Karar                          Detay
────────────────────────────────────────────────────────────
Execution modes                per_job, per_run (batch kaldırıldı)
Yeni phase                     finalize (her zaman en son)
Priority                       1-255, lower = earlier
Event coordination             file.*, phase.*, plugin.*
Çakışma çözümü                 Event-driven, collect & batch
trigger_rule                   all_done for finalize
```

---

**Son Güncelleme:** 2025-11-30
