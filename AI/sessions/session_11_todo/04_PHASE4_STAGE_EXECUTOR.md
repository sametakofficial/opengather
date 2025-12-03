# PHASE 4: STAGE EXECUTOR

```yaml
öncelik: P2
tahmini_süre: 6-8 saat
bağımlılık: Phase 1 (models), Phase 2 (manifest)
hedef: 4-stage execution sistemi
risk: ORTA (yeni dosya, mevcut executor korunur)
```

---

## MEVCUT DURUM ANALİZİ

### core/plugins/executor.py

```python
# MEVCUT YAKLASIM
class PluginExecutor:
    execute_input_plugins(input_plugins) → List[match]
    execute_output_pipeline(output_plugins, groups, match, ...) → Dict

# 2 CATEGORY: input ve output
# input → match oluşturur
# output → match'i zenginleştirir
```

### HEDEF YAKLASIM (4 STAGE)

```
INPUT (per_run)
    └─→ Job'ları oluştur

PARSE (per_job)
    └─→ Her job için filename parse

DATA (per_job)
    └─→ Her job için metadata fetch

OUTPUT (per_job)
    └─→ Her job için dosya kaydet
```

---

## TASK LİSTESİ

### 4.1 StageExecutor Base Class

**Dosya:** `core/stage_executor.py` (YENİ DOSYA)

**Ne yapılacak:**

```python
class StageExecutor:
    """
    4-stage execution manager.
    Mevcut PluginExecutor'dan BAĞIMSIZ.
    """

    STAGES = ["input", "parse", "data", "output"]

    def __init__(self, state_manager, event_bus, config):
        self.state = state_manager
        self.events = event_bus
        self.config = config
        self.plugins_by_stage = {}  # stage → [plugins]
```

**Kabul Kriteri:**

```python
executor = StageExecutor(state, events, config)
assert executor.STAGES == ["input", "parse", "data", "output"]
```

---

### 4.2 Plugin Stage Grouping

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def group_plugins_by_stage(self, plugins: Dict[str, Dict]) -> Dict[str, List]:
    """
    Pluginleri stage'e göre grupla.

    Args:
        plugins: {name: metadata} from discovery

    Returns:
        {"input": [p1], "parse": [p2, p3], "data": [p4], "output": [p5]}
    """
    grouped = {stage: [] for stage in self.STAGES}
    for name, meta in plugins.items():
        stage = meta.get('_effective_stage', 'output')
        if stage in grouped:
            grouped[stage].append(name)
    return grouped
```

**Kabul Kriteri:**

```python
plugins = {
    "scanner": {"_effective_stage": "input"},
    "renamer": {"_effective_stage": "parse"},
    "tmdb": {"_effective_stage": "data"},
    "tasker": {"_effective_stage": "output"}
}
grouped = executor.group_plugins_by_stage(plugins)
assert grouped["input"] == ["scanner"]
assert grouped["data"] == ["tmdb"]
```

---

### 4.3 Stage Execution Order

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def get_stage_execution_order(self, stage_plugins: List[str],
                               all_plugins: Dict) -> List[List[str]]:
    """
    Stage içindeki pluginleri topological sort ile sırala.

    Returns:
        [[paralel_grup_1], [paralel_grup_2], ...]
    """
    # requires'a göre dependency graph oluştur
    # Bağımlılığı olmayanlar paralel çalışabilir
    # Topological sort ile grupla
```

**Not:** Mevcut `resolver.py` kullanılabilir veya basitleştirilmiş versiyon

---

### 4.4 Execute Input Stage (per_run)

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def execute_input_stage(self, input_plugins: List[str],
                        loaded_plugins: Dict) -> List[str]:
    """
    Input stage: per_run mode - tüm job'ları oluştur.

    Returns:
        List of created job IDs
    """
    job_ids = []

    for plugin_name in input_plugins:
        plugin = loaded_plugins[plugin_name]

        # Plugin execute_run() metodunu çağır
        if hasattr(plugin, 'execute_run'):
            result = plugin.execute_run(self._create_services())

            # Result'tan job'ları oluştur
            for item in result.items:
                job = self.state.create_job(
                    index=len(job_ids),
                    input_value=item['value'],
                    input_data=item.get('data', {})
                )
                job_ids.append(job.id)

    return job_ids
```

**FINAL_DATASETS.yml Referansı:**

```yaml
execution_modes:
  per_run:
    description: tum run icin bir kez calisir
    method: execute_run(self, services)
    examples: [scanner, rclone, summary]
```

---

### 4.5 Execute Per-Job Stage

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def execute_stage_per_job(self, stage: str, plugins: List[str],
                          loaded_plugins: Dict, job_ids: List[str]):
    """
    Parse/Data/Output stage: per_job mode.
    Her job için sırayla çalıştır.
    """
    for job_id in job_ids:
        job = self.state.get_job(job_id)

        # Stage içindeki pluginleri sırayla çalıştır
        for group in self.get_stage_execution_order(plugins, loaded_plugins):
            # Paralel çalıştırılabilir pluginler
            for plugin_name in group:
                self._execute_plugin_for_job(plugin_name, job, loaded_plugins)
```

**FINAL_DATASETS.yml Referansı:**

```yaml
execution_modes:
  per_job:
    description: her job icin bir kez calisir
    method: execute(self, job, services)
    examples: [renamer, tmdb, tasker]
```

---

### 4.6 Plugin Execution Wrapper

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def _execute_plugin_for_job(self, plugin_name: str, job: JobState,
                            loaded_plugins: Dict):
    """Tek plugin'i tek job için çalıştır"""
    plugin = loaded_plugins[plugin_name]

    # 1. Requires check
    if not self._check_requires(plugin_name, job):
        self.state.mark_plugin_skipped(job.index, plugin_name)
        return

    # 2. Execute
    try:
        services = self._create_services(job)
        result = plugin.execute(job, services)

        # 3. Update state
        self.state.update_plugin_result(job.index, plugin_name, result)

    except Exception as e:
        # Error handling (run durmasin!)
        self.state.mark_plugin_failed(job.index, plugin_name, str(e))
```

---

### 4.7 Requires Checker

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def _check_requires(self, plugin_name: str, job: JobState) -> bool:
    """
    Plugin'in requires'ları karşılanmış mı?

    Prefix'lere göre kontrol:
    - job.*: job state'de path var mı
    - provides.*: provide tamamlandı mı
    - events.*: event emit edildi mi
    """
    plugin_meta = self.all_plugins[plugin_name]
    requires = plugin_meta.get('_effective_requires', [])

    for req in requires:
        if req.startswith('job.'):
            # job.plugins.renamer.parsed → job state'de kontrol
            path = req[4:]  # "plugins.renamer.parsed"
            if not self._path_exists(job, path):
                return False
        elif req.startswith('provides.'):
            # provides.http.request → provide registry kontrol
            # Phase 5'te detaylandırılacak
            pass
        elif req.startswith('events.'):
            # events.file.created → event history kontrol
            pass

    return True
```

**PHILOSOPHY.md Referansı:**

```yaml
REQUIRES PREFIX SISTEMI: job.*      | GlobalState | Path dolu olana kadar bekle
  provides.* | ProvideRegistry | Provide tamamlanana kadar bekle
  events.*   | EventBus | Event emit edilene kadar bekle
```

---

### 4.8 Services Factory

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde

**Ne yapılacak:**

```python
def _create_services(self, job: JobState = None) -> 'PluginServices':
    """
    Plugin için services objesi oluştur.

    Services:
    - state: StateService (job update)
    - events: EventService (emit)
    - logger: LoggerService
    - config: ConfigService (frozen)
    """
    return PluginServices(
        state=StateService(self.state, job),
        events=EventService(self.events),
        logger=self.logger,
        config=self.config
    )
```

**Not:** PluginServices tam implementasyonu Phase 6'da

---

### 4.9 Full Run Execution

**Dosya:** `core/stage_executor.py`

**Nerede:** `StageExecutor` class içinde - main method

**Ne yapılacak:**

```python
def execute_run(self, loaded_plugins: Dict) -> str:
    """
    Full execution: 4 stage sırayla.

    Returns:
        run_id
    """
    # 1. Start run
    run_id = self.state.start_run(self.config)

    # 2. Group plugins by stage
    stage_groups = self.group_plugins_by_stage(loaded_plugins)

    # 3. INPUT stage (per_run)
    job_ids = self.execute_input_stage(
        stage_groups['input'], loaded_plugins
    )

    # 4. PARSE stage (per_job)
    self.execute_stage_per_job('parse', stage_groups['parse'],
                               loaded_plugins, job_ids)

    # 5. DATA stage (per_job)
    self.execute_stage_per_job('data', stage_groups['data'],
                               loaded_plugins, job_ids)

    # 6. OUTPUT stage (per_job)
    self.execute_stage_per_job('output', stage_groups['output'],
                               loaded_plugins, job_ids)

    # 7. Complete run
    self.state.complete_run()

    return run_id
```

---

### 4.10 Event Emission

**Dosya:** `core/stage_executor.py`

**Nerede:** Execute metodları içinde

**Ne yapılacak:**

```
Her kritik noktada event emit:
- run.started
- stage.started, stage.completed
- job.started, job.completed
- plugin.started, plugin.completed, plugin.failed
```

**FINAL_DATASETS.yml Referansı:**

```yaml
events:
  run: [run.started, run.completed, run.failed]
  job: [job.created, job.started, job.completed, job.failed]
  stage: [stage.started, stage.completed, stage.failed]
  plugin: [plugin.started, plugin.completed, plugin.failed]
```

---

### 4.11 Error Handling (Run Durmasin)

**Dosya:** `core/stage_executor.py`

**Nerede:** Tüm execute metodlarında

**Ne yapılacak:**

```python
# PHILOSOPHY: Run ASLA durmasin
try:
    result = plugin.execute(job, services)
except Exception as e:
    # Log error
    self.logger.error(f"Plugin {name} failed: {e}")

    # Mark as failed
    self.state.mark_plugin_failed(job.index, name, str(e))

    # CONTINUE - don't raise!
    # Next plugin will check trigger_rule
```

**PHILOSOPHY.md Referansı:**

```
Run = ASLA durmasin (plugin fail != job fail)
```

---

### 4.12 Parallel Execution Support

**Dosya:** `core/stage_executor.py`

**Nerede:** `execute_stage_per_job` içinde

**Ne yapılacak:**

```python
async def _execute_parallel_group(self, plugins: List[str],
                                   job: JobState, loaded: Dict):
    """Bağımsız pluginleri paralel çalıştır"""
    tasks = []
    for plugin_name in plugins:
        task = asyncio.create_task(
            self._execute_plugin_async(plugin_name, job, loaded)
        )
        tasks.append(task)

    await asyncio.gather(*tasks, return_exceptions=True)
```

**Not:** İlk aşamada sequential, sonra paralel eklenebilir

---

### 4.13 Integration with Existing Code

**Dosya:** Şimdilik değişiklik YOK

**Ne yapılacak:**

```
StageExecutor TAMAMEN BAĞIMSIZ çalışacak.
__main__.py DEĞİŞMEYECEK (henüz).

Test için ayrı script:
  python -m archiverr.core.stage_executor
```

---

### 4.14 Unit Tests

**Dosya:** `tests/unit/core/test_stage_executor.py` (YENİ)

**Ne yapılacak:**

```
Test cases:
1. test_group_plugins_by_stage
2. test_stage_execution_order
3. test_execute_input_stage_creates_jobs
4. test_execute_per_job_stage
5. test_requires_checker_job_path
6. test_requires_checker_provides
7. test_plugin_failure_continues_run
8. test_full_run_execution
9. test_event_emission
10. test_services_factory
```

---

## BAĞIMLILIK GRAFİ

```
4.1 StageExecutor Base
     │
     ├──→ 4.2 Plugin Stage Grouping
     │
     └──→ 4.3 Stage Execution Order

4.4 Execute Input Stage (per_run)
     │
     └──→ 4.5 Execute Per-Job Stage
              │
              └──→ 4.6 Plugin Execution Wrapper
                       │
                       ├──→ 4.7 Requires Checker
                       │
                       └──→ 4.8 Services Factory

4.6 + 4.7 + 4.8 ──→ 4.9 Full Run Execution
                         │
                         ├──→ 4.10 Event Emission
                         │
                         ├──→ 4.11 Error Handling
                         │
                         └──→ 4.12 Parallel Support
                                   │
                                   └──→ 4.13 Integration
                                            │
                                            └──→ 4.14 Tests
```

---

## MEVCUT EXECUTOR İLE KARŞILAŞTIRMA

| Özellik        | Mevcut PluginExecutor | Yeni StageExecutor          |
| -------------- | --------------------- | --------------------------- |
| Stage sayısı   | 2 (input/output)      | 4 (input/parse/data/output) |
| Execution mode | Hep aynı              | per_run / per_job           |
| Requires check | expects field         | requires prefix system      |
| Error handling | Exception raise       | Log and continue            |
| Event emission | Manual                | Automatic                   |

---

## TAMAMLAMA KRİTERİ

Phase 4 TAMAMLANDI sayılır eğer:

- [ ] StageExecutor class oluşturuldu
- [ ] 4 stage execution çalışıyor
- [ ] per_run ve per_job modları çalışıyor
- [ ] Requires checker implement edildi
- [ ] Error handling "run durmasın" prensibine uygun
- [ ] Mevcut PluginExecutor ETKİLENMEDİ
- [ ] Tüm testler geçiyor

---

**SONRAKİ PHASE:** `05_PHASE5_VALIDATION.md`
