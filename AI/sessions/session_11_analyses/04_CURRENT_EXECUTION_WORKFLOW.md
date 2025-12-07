# MEVCUT EXECUTION WORKFLOW

```yaml
tarih: 2025-12-04
durum: current_state
kaynak: src/archiverr/ codebase analysis
```

---

## 1. GENEL AKIŞ

```
┌─────────────────────────────────────────────────────────────────────┐
│                         __main__.py                                  │
│                         (~170 satır)                                 │
├─────────────────────────────────────────────────────────────────────┤
│  1. CLI/API mode detection                                          │
│  2. load_config_with_tracking("config.yml")                         │
│  3. ConfigValidator.validate(config)                                │
│  4. build_orchestrator(config)                                      │
│  5. orchestrator.run()                                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                                  │
│                    (orchestrator.py ~500 satır)                      │
├─────────────────────────────────────────────────────────────────────┤
│  1. _initialize()                                                    │
│     ├── PluginRegistry.discover_and_load()                          │
│     ├── validate_at_startup(config, manifests, enabled_plugins)     │
│     ├── state.start_execution(config)                               │
│     └── Create StageExecutor                                        │
│                                                                      │
│  2. _execute_stages()                                                │
│     for stage in [INPUT, PARSE, DATA, OUTPUT]:                      │
│         _execute_single_stage(stage)                                │
│                                                                      │
│  3. _finalize(success)                                              │
│     ├── state.complete_execution()                                  │
│     └── event_bus.emit("run.completed")                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. STAGE EXECUTOR AKIŞI

```
┌─────────────────────────────────────────────────────────────────────┐
│                      STAGE EXECUTOR                                  │
│                  (stage_executor.py ~750 satır)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  execute_stage(stage):                                               │
│  ├── plugins = registry.get_plugins_for_stage(stage)                │
│  ├── sorted_plugins = topological_sort(plugins)                     │
│  │                                                                   │
│  ├── if stage == INPUT:  # per_run mode                             │
│  │   └── for plugin in sorted_plugins:                              │
│  │         result = plugin.execute_run(services)                    │
│  │         # Scanner creates jobs here                              │
│  │                                                                   │
│  └── else:  # per_job mode (PARSE, DATA, OUTPUT)                    │
│      └── for job in jobs:                                           │
│            for plugin in sorted_plugins:                            │
│              if requires_validator.validate(plugin, job):           │
│                result = plugin.execute(job, services)               │
│                state.update_plugin_data(job.id, plugin.name, result)│
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. PLUGIN SERVICES

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PLUGIN SERVICES                                  │
│               (services/__init__.py ~140 satır)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  @dataclass                                                          │
│  class PluginServices:                                               │
│      state: StateService      # State okuma/yazma                   │
│      events: EventService     # Event emit/subscribe                │
│      logger: LoggerService    # Loglama                             │
│      config: ConfigService    # Config erişimi                      │
│                                                                      │
│  create_plugin_services(                                             │
│      state_manager,                                                  │
│      event_bus,                                                      │
│      debugger,                                                       │
│      config,                                                         │
│      plugin_name                                                     │
│  ) -> PluginServices                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. REQUIRES VALIDATION AKIŞI

```
┌─────────────────────────────────────────────────────────────────────┐
│                   REQUIRES VALIDATOR                                 │
│              (requires_validator.py ~200 satır)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  validate(plugin, job) -> RequiresResult:                            │
│  │                                                                   │
│  │  for path in plugin.manifest.requires:                           │
│  │    │                                                              │
│  │    ├── if path.startswith("job."):                               │
│  │    │     # State path check                                      │
│  │    │     value = get_nested_value(job, path)                     │
│  │    │     if value is None: missing.append(path)                  │
│  │    │                                                              │
│  │    ├── if path.startswith("provides."):                          │
│  │    │     # Provide completion check                              │
│  │    │     if not provides_registry.is_complete(path):             │
│  │    │       missing.append(path)                                  │
│  │    │                                                              │
│  │    └── if path.startswith("events."):                            │
│  │          # Event fired check                                     │
│  │          if not event_bus.has_fired(path):                       │
│  │            missing.append(path)                                  │
│  │                                                                   │
│  └── return RequiresResult(can_execute=len(missing)==0, missing)    │
│                                                                      │
│  TRIGGER RULES:                                                      │
│  ├── all_success: Tüm requires SUCCESS                              │
│  ├── one_success: En az biri SUCCESS                                │
│  ├── all_done: Hepsi DONE (fail dahil)                              │
│  ├── all_fail: Hepsi FAIL                                           │
│  └── none_fail: Hiçbiri FAIL değil                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. TEMPLATE CONTEXT (MEVCUT)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   TEMPLATE MANAGER                                   │
│              (template_manager.py ~450 satır)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  render(template, context, current_index):                           │
│                                                                      │
│  jinja_context = {                                                   │
│      # SYSTEM ALIASES (8 adet - FINAL_DATASETS.yml)                 │
│      'run': {...},          # Run state                             │
│      'job': {...},          # Current job state                     │
│      'jobs': [...],         # All jobs list                         │
│      'plugins': {...},      # Current job plugins                   │
│      'config': {...},       # Frozen config (readonly)              │
│      'options': {...},      # config.options shortcut               │
│      'provides': {},        # TODO: Active provides registry        │
│      'events': {},          # TODO: Event bus history               │
│                                                                      │
│      # LEGACY COMPAT                                                 │
│      'index', 'total', 'globals', ...                               │
│  }                                                                   │
│                                                                      │
│  # User aliases from config.aliases                                  │
│  for alias, path in user_aliases:                                    │
│      jinja_context[alias] = resolve_path(path)                      │
│                                                                      │
│  # Plugin data direct access ({{ tmdb.movie }})                      │
│  for plugin_name, data in plugins:                                   │
│      jinja_context[plugin_name] = data                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. CONFIG LOADING AKIŞI

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONFIG LOADER                                     │
│               (config_loader.py ~330 satır)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  load_config_with_tracking("config.yml"):                            │
│  │                                                                   │
│  ├── 1. load_yaml_with_includes(path)                               │
│  │       ├── Parse YAML                                             │
│  │       └── Process !include directives                            │
│  │                                                                   │
│  ├── 2. expand_env_vars(config)                                     │
│  │       └── ${VAR} → value                                         │
│  │                                                                   │
│  ├── 3. normalize_config(config)                                    │
│  │       └── FlexGet style detection                                │
│  │                                                                   │
│  └── return expanded_config                                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. STATE HIERARCHY

```
┌─────────────────────────────────────────────────────────────────────┐
│                      STATE MODELS                                    │
│                 (state/models.py ~315 satır)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  RunState                                                            │
│  ├── id: str              "run_abc123"                              │
│  ├── status: RunStatus                                              │
│  │   ├── state: StateEnum (pending|running|completed|failed)       │
│  │   ├── success: bool                                              │
│  │   ├── total_jobs: int                                            │
│  │   ├── completed: int                                             │
│  │   └── failed: int                                                │
│  └── config: Dict         (frozen snapshot)                         │
│                                                                      │
│  JobState                                                            │
│  ├── id: str              "job_run_abc123_0"                        │
│  ├── index: int           0                                         │
│  ├── run_id: str          "run_abc123"                              │
│  ├── input: InputData                                               │
│  │   ├── value: str       "/path/file.mkv"                          │
│  │   └── data: Dict       {filename, extension, size_bytes}         │
│  ├── output: OutputData                                             │
│  │   ├── values: List[str]                                          │
│  │   └── data: Dict                                                 │
│  └── status: JobStatus                                              │
│      ├── state: StateEnum                                           │
│      ├── executed: List[str]                                        │
│      ├── failed: List[str]                                          │
│      └── skipped: List[str]                                         │
│                                                                      │
│  PluginData (ayrı collection - memory management)                   │
│  ├── job_id: str                                                    │
│  ├── plugin_name: str                                               │
│  ├── stage: str                                                     │
│  ├── status: Dict                                                   │
│  └── data: Dict           (plugin-specific output)                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. EVENT BUS

```
┌─────────────────────────────────────────────────────────────────────┐
│                       EVENT BUS                                      │
│                  (events/__init__.py)                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  LIFECYCLE EVENTS:                                                   │
│  ├── run.started                                                    │
│  ├── run.completed                                                  │
│  ├── run.failed                                                     │
│  ├── stage.started                                                  │
│  ├── stage.completed                                                │
│  ├── stage.failed                                                   │
│  ├── plugin.started                                                 │
│  ├── plugin.completed                                               │
│  ├── plugin.failed                                                  │
│  ├── job.created                                                    │
│  ├── job.started                                                    │
│  ├── job.completed                                                  │
│  └── job.failed                                                     │
│                                                                      │
│  USAGE:                                                              │
│  event_bus.emit("plugin.completed", {                               │
│      "plugin_name": "tmdb",                                         │
│      "job_id": "job_abc_0",                                         │
│      "data": {...}                                                  │
│  })                                                                  │
│                                                                      │
│  event_bus.subscribe("job.completed", handler_func)                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. ALIAS SYSTEM (MEVCUT)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ALIAS SYSTEM                                     │
│              (alias_resolver.py ~260 satır)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SYSTEM_ALIASES (8 adet - override edilemez):                       │
│  ├── run        # Run state                                         │
│  ├── job        # Current job state                                 │
│  ├── jobs       # All jobs list                                     │
│  ├── plugins    # Current job plugins                               │
│  ├── config     # Frozen config (readonly)                          │
│  ├── options    # config.options shortcut                           │
│  ├── provides   # Provides registry (readonly)                      │
│  └── events     # Event bus (readonly)                              │
│                                                                      │
│  SHORT_ALIASES = {} # Kullanıcı tanımlar                            │
│                                                                      │
│  USER_ALIASES (config.aliases):                                      │
│  ├── m: job.plugins.tmdb.movie                                      │
│  ├── p: job.plugins.renamer.parsed                                  │
│  └── ... (kullanıcı tanımlı)                                        │
│                                                                      │
│  INLINE ALIASES (Jinja2):                                            │
│  {% set m = job.plugins.tmdb.movie %}                               │
│  {{ m.title }}                                                       │
│                                                                      │
│  PRIORITY:                                                           │
│  1. Inline (Jinja2 set)     ← HIGHEST                               │
│  2. User (config.aliases)                                           │
│  3. System (run, job, ...)  ← LOWEST                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. SORUNLAR VE EKSİKLER

| Sorun | Durum | Açıklama |
|-------|-------|----------|
| provides alias inject | ⚠️ TODO | Şu an boş dict |
| events alias inject | ⚠️ TODO | Şu an boş dict |
| Inline alias (manifest.yml) | ❌ YOK | Manifest'te alias kullanılamıyor |
| Config loop/condition docs | ❌ YOK | Dokümante edilmemiş |
| Tasker requires | ⚠️ Eksik | fs.write sağlayanlardan sonra çalışmalı |

---

**Son Güncelleme:** 2025-12-04
