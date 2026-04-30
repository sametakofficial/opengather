# Archiverr Plugin Development Guide

> **Audience:** developers writing new plugins for archiverr.
> **Authoritative sources:** this guide cross-references actual code paths and
> the dataset specs under `datasets/`. When this doc disagrees with code,
> the code is the bug — file an issue. When this doc disagrees with the
> datasets, the datasets win (per `datasets/README.yml`).
> **Last verified:** 2026-04-30 against `dev/communication-refactoring`
> (initial draft + post-audit fixes for C1 `:any` removal,
> C2 events/provides matcher wiring, C3 Stage-enum 3-value clarification,
> C4 update_plugin replace-footgun callout, G1 enabled flag, G2 executor
> safety nets, G3 PluginResult-only enforcement).

---

## Table of Contents

1.  [Architecture in 60 seconds](#1-architecture-in-60-seconds)
2.  [The pipeline: per_run, then PARSE → DATA → OUTPUT](#2-the-pipeline)
3.  [Project layout](#3-project-layout)
4.  [`manifest.yml` — the contract](#4-manifestyml--the-contract)
5.  [Plugin classes — what to subclass and what to implement](#5-plugin-classes)
6.  [`PluginResult` — the return contract](#6-pluginresult--the-return-contract)
7.  [`services` — the only legal way to talk to the system](#7-services--talking-to-the-system)
8.  [`requires` / `provides` / `trigger_rule`](#8-requires--provides--trigger_rule)
9.  [Plugin output: `plugin.<name>.data` surface](#9-plugin-output-pluginnamedata-surface)
10. [Template context (Jinja2)](#10-template-context-jinja2)
11. [Configuration: `config_schema` and the three-layer merge](#11-configuration)
12. [Run safety: `dry_run`, `hardlink`, `no_delete`](#12-run-safety)
13. [Events — strictly read-only for plugins](#13-events--strictly-read-only-for-plugins)
14. [Logging](#14-logging)
15. [Persistence (MongoDB) — what gets written and where](#15-persistence-mongodb)
16. [Worked examples](#16-worked-examples)
17. [Testing](#17-testing)
18. [Plugin-agnostic core: rules the *core* enforces on itself](#18-plugin-agnostic-core)
19. [Dead schema fields — declared but unused](#19-dead-schema-fields)
20. [Reference index — file paths and line numbers](#20-reference-index)

---

## 1. Architecture in 60 seconds

Archiverr is a **plugin-orchestrated media-metadata pipeline**. The core
knows nothing about specific plugins — every plugin name (`scanner`,
`renamer`, `tmdb`, `ffprobe`, `tasker`, …) is forbidden as a string
literal inside `src/archiverr/core/` and a guard test
(`tests/unit/core/test_plugin_agnostic.py`) fails CI if one slips in.

The core knows only:

* **Stages** — `PARSE`, `DATA`, `OUTPUT` (enum at
  `src/archiverr/core/plugins/registry.py:23-37`). The `Stage` enum has
  exactly three values. `input` is a *manifest value* that maps to
  `per_run` mode and runs **outside** the stage system
  (`registry.py:202-212` translates `stage: input` to `Stage = None`,
  i.e. "no stage; run as per_run before any stage starts").
* **Run modes** — `per_run` (runs once before stages start) and `per_job`
  (runs once per job, inside a stage). Use `stage: input` in your
  manifest if and only if your `run_mode: per_run` and you produce
  jobs.
* **Capabilities** — opaque tags like `http.request`, `state.update`,
  `output.render` declared in `provides:` and matched by other plugins
  in `requires:`.
* **Trigger rules** — Airflow-style booleans (`all_success`,
  `one_success`, `all_done`, `all_fail`, `none_fail`) that decide
  whether a plugin runs given the state of its dependencies.

Everything else — what a plugin *does* — is the plugin's business.

---

## 2. The pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ INPUT (per_run)                                                     │
│   scanner / file-reader run once, call services.create_job(...)     │
│   one input → one or more JobState objects                          │
├─────────────────────────────────────────────────────────────────────┤
│ For every job, in order:                                            │
│                                                                     │
│   PARSE  (per_job)   parse filenames / detect category              │
│   DATA   (per_job)   API enrichment (tmdb, tvdb, omdb, ffprobe…)    │
│   OUTPUT (per_job)   produce side effects (tasker writes/copies)    │
└─────────────────────────────────────────────────────────────────────┘
```

* **Stages run in order** — PARSE first, then DATA, then OUTPUT.
* **Within a stage**, plugins run in **dependency-resolved groups**.
  `DependencyResolver.resolve()` topologically sorts plugins by their
  `requires:` edges and returns a list of groups; groups run
  sequentially, plugins inside a group can be ordered freely
  (today's executor still walks them sequentially).
  See `src/archiverr/core/plugins/resolver.py`.
* **Per-job plugins run for every job inside a stage.** Cross-job
  parallelism is not implemented yet — jobs are processed one at a
  time.
* **`input` is special.** Input plugins do NOT run inside a stage;
  they run once per run, *before* the PARSE stage starts, and their
  job is to populate the run with `JobState` objects via
  `services.create_job(...)`.

> **Why `input` is `per_run` not `per_job`** — there are no jobs yet
> when input plugins fire. They *create* the jobs.

---

## 3. Project layout

```
src/archiverr/plugins/<plugin_name>/
├── manifest.yml           # required — declares contract
├── client.py              # convention — entry point (overridable via manifest)
├── plugin.py              # alternative entry point (only tasker uses this today)
└── extras.py              # optional — plugin-internal helpers (tmdb, tvdb, tvmaze use this)
```

Conventions:

* **Directory name = plugin name** (`name:` in manifest must match).
  Use kebab-case for multi-word names (e.g. `file-reader`).
* **`client.py` is the default entry point** — `manifest.yml`'s
  `entry_point:` defaults to `client.py`. You only need to set it if
  you want a different filename (e.g. tasker uses `plugin.py`).
* **`class_name:` is required** — there is no implicit
  "{Name}Plugin" convention in the loader. The class is resolved
  with `importlib.import_module(f"archiverr.plugins.{name}.{entry}")`
  followed by `getattr(module, class_name)`.

---

## 4. `manifest.yml` — the contract

### Schema

Defined by `PluginManifest` (Pydantic v2) at
`src/archiverr/core/plugins/sdk/manifest.py:16-85`. Spec lives at
`datasets/02-manifest.yml`.

### Required fields

| Field         | Type                                  | Notes                                                                                         |
| ------------- | ------------------------------------- | --------------------------------------------------------------------------------------------- |
| `name`        | string (lowercase, no spaces)         | Must equal the directory name.                                                                |
| `stage`       | `input` \| `parse` \| `data` \| `output` | **Must be explicit** — `None` raises `ValueError` at load (manifest.py:51-55).                 |
| `run_mode`    | `per_run` \| `per_job`                | **Must be explicit** — `None` raises `ValueError` at load (manifest.py:56-60).                 |
| `class_name`  | string                                | Python class to import.                                                                       |
| `entry_point` | string (default `client.py`)          | Python file under the plugin directory.                                                       |

### Important optional fields

| Field           | Type                              | Default          | Notes                                                                          |
| --------------- | --------------------------------- | ---------------- | ------------------------------------------------------------------------------ |
| `version`       | string (semver)                   | `"1.0.0"`        | Free-form, not enforced.                                                       |
| `description`   | string                            | `None`           | Human-readable summary.                                                        |
| `requires`      | list of dependency strings        | `[]`             | See [section 8](#8-requires--provides--trigger_rule).                          |
| `provides`      | list of capability strings        | `[]`             | Free-form tags. See [section 8](#8-requires--provides--trigger_rule).          |
| `trigger_rule`  | `all_success` / `one_success` / `all_done` / `all_fail` / `none_fail` | `"all_success"`  | Default applies if you omit the field.                                          |
| `categories`    | list[string]                      | `[]`             | Hint values (`movie`, `show`). Used **only** for UI summary at `models/response_builder.py:208-215`. **Does not** route the pipeline. Empty = "all". |
| `config_schema` | dict                              | `None`           | See [section 11](#11-configuration).                                            |
| `fs_lock`       | list of absolute paths (no vars)  | `[]`             | Validated for static collisions at startup by `core/locking/{manager,validator}.py`. **Does not** gate execution at runtime. |

### Honest warning — fields with no runtime effect

`PluginManifest` *accepts* these fields (Pydantic schema), but **no
runtime code reads them today**:

* `capabilities`
* `hooks`
* `listens_to`
* `reactive`

They are scaffolding from Session 34 (commit `5c24b22`) for a reactive
plugin model that was never wired. Datasets/02-manifest.yml line 35-43
documents the removal. **Don't rely on these fields for behavior.** If
you set them, nothing happens.

### Minimal manifest examples

**Per-run input plugin** (file-reader, real):

```yaml
name: file-reader
version: 1.0.0
description: Reads target file paths from a targets.txt file
stage: input
run_mode: per_run
class_name: FileReaderPlugin
entry_point: client.py
requires: []
provides:
  - job.create
  - fs.read
trigger_rule: all_success
categories: []
```

**Per-job parse plugin** (renamer, real):

```yaml
name: renamer
version: 1.0.0
description: Parses media file names to extract movie/show metadata
run_mode: per_job
stage: parse
class_name: RenamerPlugin
entry_point: client.py
requires: []
provides:
  - state.update
trigger_rule: all_success
categories: [movie, show]

config_schema:
  media_type:
    type: string
    default: auto
    description: "Media type detection (auto, movie, show)"
```

**Per-job data plugin with dependencies + secret config** (tmdb, real, abridged):

```yaml
name: tmdb
version: 1.0.0
description: Fetches movie and TV show metadata from TMDb API
run_mode: per_job
stage: data
class_name: TMDbPlugin
entry_point: client.py

requires:
  - plugin.renamer.parsed:success      # wait for renamer to publish 'parsed'

provides:
  - http.request
  - state.update

trigger_rule: all_success
categories: [movie, show]

config_schema:
  api_key:
    type: string
    required: true
    min_length: 10
    pattern: "^[a-zA-Z0-9_-]+$"
    not_contains: ['"', "'", " "]
    secret: true
    description: "TMDb API key (v3)"
  language:
    type: string
    pattern: "^[a-z]{2}-[A-Z]{2}$"
    default: en-US
```

---

## 5. Plugin classes

There are exactly two base classes you'll subclass. Both live in
`src/archiverr/core/plugins/sdk/base.py`.

### `InputPlugin` — for `run_mode: per_run`

```python
from typing import Any
from archiverr.core.plugins.sdk import InputPlugin


class FileReaderPlugin(InputPlugin):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "file_reader"

    def execute_run(self, services: Any) -> dict[str, Any]:
        # ... discover inputs ...
        for path in discovered_paths:
            services.create_job(
                input_value=path,
                input_data={"virtual": False},
            )
        return {"jobs_created": len(discovered_paths)}
```

* **You implement `execute_run(self, services) -> dict`.**
* **Do NOT implement `execute()`** — `InputPlugin.execute()` raises
  `NotImplementedError` by design (base.py:148-151).
* **The return value** is logged but is *not* the way you produce
  jobs. You produce jobs by calling `services.create_job(...)`.

### `OutputPlugin` — for `run_mode: per_job`

```python
from datetime import datetime
from typing import Any
from archiverr.core.plugins.sdk import OutputPlugin, PluginResult


class RenamerPlugin(OutputPlugin):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "renamer"

    def execute(self, job: Any, services: Any) -> PluginResult:
        started_at = datetime.now()
        path = job.input.value

        parsed = parse_filename(path)            # plugin-internal
        services.update_plugin(data={
            "parsed": parsed,
            "category": parsed.get("category"),
        })

        return PluginResult.success_result(
            data={"parsed": parsed, "category": parsed.get("category")},
            started_at=started_at,
        )
```

* **You implement `execute(self, job, services) -> PluginResult`.**
  `job` is a `JobState` and `services` is a `PluginServices`.
* The base class' name (`OutputPlugin`) is misleading — it covers
  PARSE, DATA, *and* OUTPUT stages. The name predates the 3-stage
  pipeline; renaming would touch every plugin file. Treat it as
  "the per-job base class".
* **Always return a `PluginResult`** — see [section 6](#6-pluginresult--the-return-contract).

### Don't subclass `BasePlugin` directly

`BasePlugin` is abstract (`base.py:24-141`). It exists so `InputPlugin`
and `OutputPlugin` can share `__init__`, logging helpers, and the
`set_context()` hook the executor calls before each invocation. You
won't gain anything by subclassing it directly.

### Logging helpers

`BasePlugin` exposes four logging methods that all plugins inherit:

```python
self.debug("found 12 paths", target=target_path)
self.info("rename completed", source=src, dest=dst)
self.warn("API rate limited; backing off", attempt=2)
self.error("subprocess failed", returncode=rc)
```

Internally these route to `self._context.debugger.<level>(...)`.
`set_context()` is called by the executor before every invocation
(per_run and per_job alike), so by the time `execute_run` /
`execute` is on the stack, `self._context` is populated.

### Executor safety nets you can rely on

Two guarantees from `src/archiverr/core/plugins/stage_executor.py`:

1. **Unhandled exceptions are caught.** The executor wraps each
   per_job invocation in `try / except PluginError / except Exception`
   (`stage_executor.py:326-335`). A raised exception becomes a
   `PluginExecutionResult(success=False, data={}, error=str(exc))`.
   The run continues. So:
   * `raise SomeError("bad input")` and `return PluginResult.error_result("bad input")`
     reach the same MongoDB document, *almost*: the latter lets you
     attach `metadata` (api_calls, retry counts) and a clean
     `started_at`. **Prefer `error_result`.** Bare `raise` is fine for
     truly unexpected paths (programming errors).
   * **Never** wrap your own `try / except: pass` around `execute()` —
     you'll just hide the error from the executor's logging path.

2. **`PluginResult` is the only legal return type.** The executor
   refuses anything else (`stage_executor.py:451-455` raises
   `PluginError(f"Plugin returned unsupported type {type(result).__name__}; expected PluginResult")`).
   Don't return a dict, a tuple, or `None`. Session 34 deleted the
   legacy "return a dict" adapter; old example code on the internet
   may show that pattern — ignore it.

---

## 6. `PluginResult` — the return contract

Defined at `src/archiverr/core/plugins/sdk/result.py`. It's a
Pydantic model with these fields:

| Field         | Type            | Meaning                                                            |
| ------------- | --------------- | ------------------------------------------------------------------ |
| `success`     | bool            | `True` if the plugin's job succeeded, `False` otherwise.            |
| `data`        | `dict[str, Any]`| Plugin output. Goes to `plugin.<name>.data` and to MongoDB.        |
| `error`       | `str \| None`   | Required when `success=False`.                                      |
| `started_at`  | `datetime`      | When `execute()` started.                                           |
| `finished_at` | `datetime`      | When `execute()` finished.                                          |
| `metadata`    | `dict[str, Any]`| Free-form (`api_calls`, `cache_hits`, `skipped`, `skip_reason`, …). |

### Use the factory methods

```python
# Happy path
return PluginResult.success_result(data={"parsed": parsed}, started_at=t0)

# Error
return PluginResult.error_result("TMDb 401: invalid api_key", started_at=t0)

# "I correctly decided not to do anything" (NOT a failure)
return PluginResult.skipped_result(
    reason="virtual path; nothing to scan",
    started_at=t0,
)
```

`skipped_result()` returns `success=True` with
`metadata={"skipped": True, "skip_reason": reason}`. The orchestrator
treats it as a success that emits the `plugin.skipped` event instead
of `plugin.completed`.

### `duration_ms` is computed for you

```python
result.duration_ms  # int, derived from finished_at - started_at
```

Don't set it yourself.

---

## 7. `services` — talking to the system

The `services` argument passed to your plugin is a `PluginServices`
instance defined at
`src/archiverr/core/services/plugin_services.py:19`. **It is the only
sanctioned channel between a plugin and the system.** Don't reach
around it (don't import `GlobalStateManager`, don't fetch
`EventBus.emit`, don't read `core.config` directly).

### Mode-dependent access

| Capability                 | per_run | per_job | Notes                                                                                            |
| -------------------------- | :-----: | :-----: | ------------------------------------------------------------------------------------------------ |
| `services.create_job(...)` |   ✅    |   ✅    | per_run: how you populate the run. per_job: rare, but legal (e.g. fan-out one path into N jobs). |
| `services.get_run()`       |   ✅    |   ✅    | Returns the immutable `RunState` snapshot.                                                       |
| `services.get_config()`    |   ✅    |   ✅    | Returns the frozen, fully-resolved config dict.                                                  |
| `services.get_current_job()` | ❌    |   ✅    | The job your plugin is currently being invoked for.                                              |
| `services.get_all_jobs()`  |   ✅    |   ✅    | Read-only; per_run sees jobs created so far in this run.                                         |
| `services.update_job(...)` |   ❌    |   ✅    | Dot-notation write into the current job (e.g. `key="output.values"`).                            |
| `services.update_plugin(...)` |  ❌    |   ✅    | Canonical writer into `plugin.<name>.data`.                                                      |
| `services.get_plugin_data(target_id, plugin_name)` | ✅ | ✅ | Read another plugin's data for this job/run.                                  |
| `services.events`          |   ✅    |   ✅    | **Read-only**. See [section 13](#13-events--strictly-read-only-for-plugins).                       |
| `services.provides`        |   ✅    |   ✅    | Early-completion markers. See [section 8](#8-requires--provides--trigger_rule).                    |
| `services.run_safety`      |   ✅    |   ✅    | Returns `{"dry_run", "hardlink", "no_delete"}`. See [section 12](#12-run-safety).                  |

> **The "cannot access" rules above are documented contracts, not
> hard runtime guards.** A misbehaving per_run plugin that asks for
> `services.get_current_job()` will get back the manager's "current
> job" pointer, which during input is `None`. Rely on convention; the
> tests are your safety net (see [section 17](#17-testing)).

### Method signatures (with line numbers)

```python
# plugin_services.py:62
def create_job(self, input_value: str, input_data: dict[str, Any] = None) -> str

# plugin_services.py:87
def update_job(self, job_id: str = None, key: str = None, value: Any = None) -> None
#   key uses dot notation: "output.values", "output.data.foo.bar"
#   job_id defaults to current_job_id (per_job mode)

# plugin_services.py:109
def update_plugin(self, target_id: str = None, plugin_name: str = None,
                  data: dict[str, Any] = None) -> None
#   target_id defaults to current_job_id; plugin_name defaults to current_plugin_name
#   data REPLACES the existing plugin data dict (it is not merged) — see footgun below

# plugin_services.py:135
def get_plugin_data(self, target_id: str, plugin_name: str) -> dict[str, Any] | None

# plugin_services.py:148
def get_run(self) -> RunState

# plugin_services.py:156
def get_current_job(self) -> JobState

# plugin_services.py:162
def get_all_jobs(self) -> list[JobState]
```

### `services.update_plugin(data=...)` is the canonical write

The 99% case: a per_job plugin produces a result, calls
`services.update_plugin(data={...})`, and *also* puts the same data
into its `PluginResult.data`. The double-write looks redundant but
each side has a purpose:

* `services.update_plugin(data=...)` makes the data visible to
  *other plugins in this stage and downstream stages* via
  `plugin.<name>.data` in the template context and via
  `services.get_plugin_data(...)`.
* `PluginResult(data=...)` is what the executor persists to MongoDB
  (`plugin_executions` collection) and includes in event payloads.

Most plugins do both. See `RenamerPlugin.execute()` at
`src/archiverr/plugins/renamer/client.py:80-82` for the canonical
pattern.

> ### ⚠️ FOOTGUN: `update_plugin(data=...)` REPLACES, doesn't merge
>
> Each call to `services.update_plugin(data={...})` does
> `job.plugins[name] = data` (or `run.plugins[name] = data`)
> wholesale — verified at
> `src/archiverr/state/plugin_data_manager.py:99` and `:124`.
> If you call it twice during one execution, the second call
> **erases everything from the first**.
>
> If you need to update incrementally, **read first, then merge,
> then write**:
>
> ```python
> current = services.get_plugin_data(job.id, services.current_plugin_name) or {}
> services.update_plugin(data={**current, "new_field": value})
> ```
>
> Alternatively, accumulate into a local dict and `update_plugin`
> exactly once at the end of `execute()`. The existing plugins
> (renamer, tmdb, tasker) all use the "build once, write once" pattern.

### Properties

```python
services.mode                    # "per_run" or "per_job"
services.current_job_id          # str or None
services.current_plugin_name     # str or None
services.run_id                  # str or None
services.run_safety              # dict — see section 12
```

---

## 8. `requires` / `provides` / `trigger_rule`

This is the dependency graph layer.

### `requires:` — what your plugin needs *before it runs*

`requires:` entries are evaluated in two places:

1. **`DependencyResolver`** (`src/archiverr/core/plugins/resolver.py`)
   uses them to topologically sort plugins inside a stage.
2. **`ValueMatcher`** (`src/archiverr/core/triggers/matcher.py`)
   evaluates them at trigger time to decide whether the plugin
   actually runs given live state.

Supported formats (verified against `matcher.py:80-115`):

| Format                                          | Example                                | Meaning                                                                                               |
| ----------------------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `plugin.<name>.<field>:success`                 | `plugin.renamer.parsed:success`        | `<field>` must exist under `plugin.<name>.data` AND the plugin must have completed `success`.         |
| `plugin.<name>.<field>:fail`                    | `plugin.renamer.parsed:fail`           | Plugin produced `<field>` but its execution was a failure.                                            |
| `plugin.<name>.<field>` (no suffix)             | `plugin.tmdb.movie`                    | Field must exist; existence implies it was published. (`success`/`fail` only applies if you say so.)  |
| `provides.<capability>:completed`               | `provides.http.request:completed`      | At least one plugin marked the capability completed (via `services.provides.complete()`).             |
| `provides.<capability>:pending`                 | `provides.http.request:pending`        | All plugins offering this capability are still pending.                                               |
| `provides.<capability>:failed`                  | `provides.http.request:failed`         | At least one plugin offering this capability failed.                                                  |
| `events.<event_name>:fired`                     | `events.plugin.completed:fired`        | At least one event with this name has been emitted on the bus.                                        |
| `events.<event_name>` (existence)               | `events.plugin.completed`              | Same as `:fired` — existence implies fired.                                                           |
| `job.<field>`                                   | `job.input.value`                      | Field must exist on the `JobState`.                                                                   |

> **`:any` is NOT supported.** The matcher rejects it
> (`matcher.py:91-94`). Use the no-suffix form (`plugin.<name>.<field>`)
> if you only care about field existence.

The resolver itself only walks `plugin.<name>...` entries when
building the dependency graph (`resolver.py:127-128`); `provides.*`
and `events.*` requires don't add edges to the graph but they DO gate
execution at trigger evaluation time.

### `provides:` — what your plugin makes available

Free-form capability tags. The orchestrator does not validate them
against an enum; the dataset spec (`datasets/02-manifest.yml:15-16`)
recommends conventional values:

```
http.request    fs.read    fs.write    fs.move
job.create      output.render          state.update
metadata.<source>
```

Two real consumers exist today:

1. **`DependencyResolver`** uses `requires:` (which contains
   `plugin.<name>...`) to topologically sort plugins. `provides:` is
   *informational*; it does NOT directly drive ordering. The graph
   is built from `requires:` only.
2. **`ProvidesRegistry`** (accessed via `services.provides`) lets a
   plugin mark a single capability as completed *during* execution
   so dependent plugins can start as soon as that capability lands,
   even if the plugin itself is still doing other work:

   ```python
   services.provides.complete("http.request")        # mark now
   services.provides.is_completed("http.request")    # bool
   services.provides.get_status("http.request")      # dict
   ```

   Today this is used by long-running data plugins that want to
   release `http.request` early. If you don't call `complete(...)`,
   the orchestrator marks all your provides complete when your
   plugin returns successfully.

### `trigger_rule:` — when your plugin runs given the state of `requires:`

Evaluated at `src/archiverr/core/triggers/evaluator.py:20`.

| Rule           | Runs if…                                                            |
| -------------- | ------------------------------------------------------------------- |
| `all_success`  | (default) every requirement is matched (the upstream plugin succeeded and produced the field). |
| `one_success`  | at least one requirement is matched.                                |
| `all_done`     | every dependency has finished (success *or* fail).                  |
| `all_fail`     | every dependency failed (rare; useful for fallback plugins).        |
| `none_fail`    | every requirement is matched (current implementation: behaves identically to `all_success`; see note). |

> **Honest note on `none_fail`** — the current evaluator
> (`src/archiverr/core/triggers/evaluator.py:179-201`) returns
> `False` if any requirement is unmatched, exactly like
> `all_success`. The "more lenient" wording in the codebase
> docstring is aspirational; treat `none_fail` as functionally
> equivalent to `all_success` until the evaluator is updated.

Empty `requires: []` always satisfies the rule (you'll always run).

### Wiring it together

```yaml
# tasker manifest
requires:
  - plugin.tmdb.data:success           # need TMDb data
  - plugin.renamer.parsed:success      # need renamer parsing

trigger_rule: all_done
# all_done = "run me regardless of upstream success/fail" — used so
# tasker always emits a final result even if data plugins flaked.
```

---

## 9. Plugin output: `plugin.<name>.data` surface

After your per_job plugin returns `PluginResult.success_result(data={...})`,
that `data` dict ends up in three places:

1. **In-memory state** — `job.plugins[name]` (so other plugins in the
   same job can read it via `services.get_plugin_data(job_id, name)`).
   Reaches there only if you explicitly call
   `services.update_plugin(data={...})` — the executor does not
   propagate `PluginResult.data` to `job.plugins[name]` for you.
2. **Template context** — `plugin.<name>.data.<field>` for any
   downstream Jinja2 template (tasker uses this heavily).
3. **MongoDB** — the `plugin_executions` collection records the full
   `data` payload from `PluginResult` alongside `started_at`,
   `finished_at`, `duration_ms`, `error`, `metadata`
   (see [section 15](#15-persistence-mongodb)).

> **Reminder:** `services.update_plugin(data=...)` is REPLACE, not
> merge. See the footgun box in [section 7](#7-services--talking-to-the-system).

### Shape conventions

The dataset `datasets/07-plugin-io.yml` documents the canonical shape
for every existing plugin's `data:` payload. New plugins should
follow the same shape conventions, e.g.:

```python
# data plugin enriching a movie
{
    "movie": {
        "media_type": "movie",
        "identifiers": {"tmdb_id": "603", "imdb_id": "tt0133093"},
        "title": {"primary": "The Matrix", "original": "The Matrix",
                  "localized": "The Matrix"},
        "release": {"date": "1999-03-30", "year": 1999},
        "runtime": 136,
        "ratings": {"tmdb": {"score": 8.2, "votes": 24000}},
        ...
    },
    # OR
    "show": {...},
    # OR
    "episode": {...},
}
```

The category key (`movie` / `show` / `episode`) is set by the
**renamer** plugin upstream and read by data plugins to decide which
endpoint to call.

---

## 10. Template context (Jinja2)

The OUTPUT stage's `tasker` plugin renders Jinja2 templates against a
context built by `TemplateContextBuilder`
(`src/archiverr/state/template_context.py:13`). Spec:
`datasets/04-template-context.yml`.

### Top-level keys

```jinja
{{ run.id }}                         # string
{{ run.status.success }}             # bool
{{ run.status.total_jobs }}
{{ run.status.completed }}
{{ run.status.failed }}
{{ run.config.options.dry_run }}     # frozen run config

{{ job.id }}                         # "job_<run_id>_<index>"
{{ job.index }}                      # 0-based
{{ job.input.value }}                # source path / query
{{ job.input.data.virtual }}         # input plugin metadata
{{ job.output.values }}              # list of paths your save-tasks wrote
{{ job.output.data }}                # arbitrary nested dict
{{ job.status.success }}
{{ job.status.executed }}            # list of plugin names
{{ job.status.failed }}              # list
{{ job.status.skipped }}             # list

{{ jobs }}                           # [{index, id, input, plugins}, ...]

{{ config }}                         # frozen full config
{{ options }}                        # config.options shortcut
{{ events }}                         # event bus snapshot (dict[name -> list[event]])

{{ plugin.tmdb.data.movie.title.primary }}
{{ plugin.tmdb.status.state }}       # pending|running|completed|failed|skipped
```

### Custom filters available in tasker

Registered in `src/archiverr/plugins/tasker/plugin.py:34-37`:

| Filter      | Source                                  | Notes                                              |
| ----------- | --------------------------------------- | -------------------------------------------------- |
| `truncate`  | Jinja built-in                          | Standard Jinja behavior.                           |
| `format`    | tasker (alias for `%`)                  | `"{{ '%s/%d' | format(name, year) }}"`             |
| `count`     | tasker (alias for `len`)                | `{{ items | count }}` — Jinja built-in.            |

**`tojson`** is a Jinja built-in available without registration.

### Forbidden Jinja features

Documented at `datasets/04-template-context.yml:67-72` but **not
runtime-enforced**:

* `{% include %}`
* `{% import %}`
* Custom globals at render time (use pre-resolved aliases instead).

These will fail at render time with the standard Jinja error.

### Where the context comes from

```python
from archiverr.state.template_context import TemplateContextBuilder

context = TemplateContextBuilder().build_job_context(
    job=job_state,
    run=run_state,
    all_jobs=services.get_all_jobs(),
    events=services.events.snapshot(),
)
```

Tasker does this for you. If you write a new output-stage plugin that
also needs templating, **always** go through `TemplateContextBuilder`
— `04-template-context.yml` says "**source: TemplateContextBuilder
only; forbidden_sources: tasker local _build_context**".

---

## 11. Configuration

### `config_schema:` in your manifest

A simple, archiverr-flavored validation schema (validated by
`src/archiverr/core/plugins/sdk/validators.py`, called from the
plugin loader at `src/archiverr/core/plugins/loader.py:49-66`).

Supported field types: `string`, `integer`, `boolean`, `array`,
`list` (alias of array), `dict`, `object`.

Per-field validation keys:

| Key            | Applies to        | Example                                |
| -------------- | ----------------- | -------------------------------------- |
| `required`     | any               | `required: true`                       |
| `default`      | any               | `default: en-US`                       |
| `min_length`   | string, list      | `min_length: 1`                        |
| `max_length`   | string, list      | `max_length: 50`                       |
| `pattern`      | string            | `pattern: "^[A-Z]{2}$"`                |
| `not_contains` | string            | `not_contains: ['"', "'", " "]`        |
| `secret`       | string            | `secret: true` (logger redacts).        |
| `description`  | any               | Free text.                             |

Schema **failures raise at plugin load**; the run aborts before
stages start. Don't ship a plugin that needs runtime guards for
config sanity — let the loader do it.

### The three-layer merge

Spec: `datasets/02-manifest.yml:63-75`. Implemented by the loader
at `src/archiverr/core/plugins/loader.py:122-136`.

When a plugin's runtime config is computed, three layers contribute:

```
priority (lowest first):
  _manifest.config_schema.<field>.default      # default declared in manifest
  manifest.defaults.<field>                    # manifest "defaults:" block (optional)
  user                                         # config.yml plugin section (authoritative)

→ _resolved (computed once per run, frozen)
```

User-provided values **always win**. The merged result is what your
`__init__(self, config)` receives.

You can read the original layers from inside a plugin via
`${plugin.<name>._manifest.*}` substitution, but in 95% of cases you
just call `self.config.get("foo", default)` and let the merge do the
work.

### Enabling a plugin in `config.yml`

The loader at `src/archiverr/core/plugins/loader.py:230-259`
(`_is_plugin_enabled`) accepts four formats. As a plugin author,
the format you should document for users is the canonical one:

```yaml
# config.yml — canonical
plugins:
  letterboxd:
    enabled: true
    api_base: "https://api.letterboxd.com/v0"
    timeout_seconds: 10
```

Rules:

* **A bare key with no body is "enabled with defaults"** when the
  config presents the plugin as a top-level FlexGet-style mapping
  (`<name>: enabled: true` is implicit if the value is a dict).
* **`<name>: false`** disables the plugin explicitly.
* **`enabled: false`** inside the dict also disables it.
* **Missing entirely** = disabled (the loader treats unknown plugins
  as disabled).

In tests and dev configs you'll also see normalized internal forms
(`_enabled_plugins: [scanner, renamer]` and `_plugins.<name>._enabled: true`).
Those are produced by the config normalizer; user-facing configs use
the `plugins:` block above.

---

## 12. Run safety

Three boolean flags are owned by the orchestrator and threaded into
plugins via `services.run_safety`:

| Key          | Meaning                                                                                               |
| ------------ | ----------------------------------------------------------------------------------------------------- |
| `dry_run`    | If `True`, the plugin must not perform side effects on disk / network mutating endpoints.             |
| `hardlink`   | If `True`, file copy operations should prefer hardlinks (`safe_copy(..., hardlink=True)`).            |
| `no_delete`  | If `True`, the plugin must not delete or `mv` to `.deleted/`. (Honored by the no-delete policy.)      |

```python
flags = services.run_safety
if flags["dry_run"]:
    self.info("dry_run: skipping copy", source=src, dest=dst)
    return PluginResult.skipped_result(reason="dry_run", started_at=t0)
```

**Don't read these from `config['options']` directly.** The
orchestrator resolves them once via
`core.safety.resolve_run_safety(...)` at run start and that resolution
may differ from the literal config (e.g. CLI override, API request).
`services.run_safety` is the single source of truth.

---

## 13. Events — strictly read-only for plugins

Plugins **cannot emit events** and **cannot subscribe** to them.
This is a documented architecture decision; the executor / lifecycle
hooks own publishing. Datasets/08-services.yml lines 21-30 spell
this out, and `PluginServices.events` exposes only the read surface:

```python
services.events.has_fired("plugin.completed")           # bool
services.events.history("plugin.completed")             # list[event_dict]
services.events.snapshot()                              # dict[name -> list]
```

The events that exist today and have at least one runtime emitter
(per `datasets/05-events.yml`):

```
run.started   run.completed   run.error
stage.started stage.completed stage.failed
job.created   job.completed   job.failed   job.updated   job.stage_completed
plugin.completed   plugin.failed   plugin.skipped   plugin.updated
```

> **Heads-up** — many other event names (`plugin.started`,
> `plugin.progress`, `task.*`, `db.*`, …) appear in some older
> places. They have **no runtime emitter** and were removed from the
> dataset on 2026-04-30. Don't subscribe to them; you'll wait
> forever.

---

## 14. Logging

Use the inherited helpers; they go to the `Debugger` (which writes
to `output/run_<id>_debug.log` and the configured backend).

```python
self.debug("attempting fetch", url=url, attempt=n)
self.info("fetched", id=movie_id)
self.warn("rate limited; backing off", retry_after=ra)
self.error("permanent failure", status=502)
```

Conventions:

* **Never use bare `print()`** for logs (tasker has `print` tasks for
  *user output*, not logging — see its `_execute_print`).
* **Never `except: pass`.** Always log exceptions before swallowing
  them, or — preferred — let them bubble and return
  `PluginResult.error_result(...)`.
* Use **kwargs** for structured fields, not f-strings into the
  message. The debugger formats kwargs distinctly.

---

## 15. Persistence (MongoDB)

Schema: `datasets/06-mongodb.yml`. Four canonical collections:

| Collection            | Written by                                                          | Holds                                                                                                                            |
| --------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `runs`                | `state/manager.py` (`save_run` / `complete_run`)                    | One doc per run. Includes `persistence_mode`, status, totals, started/finished timestamps.                                       |
| `jobs`                | `state/job_manager.py` after job completion                         | One doc per job. Includes `input`, `output`, `status`, full `plugins` map.                                                       |
| `plugins`             | `state/plugin_data_manager.py` (canonical writer)                   | Per-plugin data documents (currently underused — most data lives in `jobs.plugins.<name>` and `plugin_executions`).              |
| `plugin_executions`   | `core/plugins/stage_executor.py` after every per_job invocation     | One doc per (job_id, plugin_name, attempt). Includes `state`, `success`, `data`, `error`, `metadata`, timing.                    |

### `persistence_mode`

```
full       — Mongo is up and writes are required. Failed write → run aborts.
degraded   — Mongo writes attempted; failures fall back to NullPersistence (logs warn).
off        — "Dangerously bypass MongoDB". NullPersistence used; nothing persists.
```

The chosen mode is recorded on the `runs` document and surfaced in
the FastAPI `RunResponse` as
`{"persistence": {"mode": "...", "backend": "...", "persisted": true|false}}`.

Plugin authors don't need to touch this — but **be aware your
per_job execution may run with no persistence at all**. Don't write
plugins that depend on reading their *own previous run's* persisted
data; use `services.get_plugin_data(...)` for in-run state instead.

---

## 16. Worked examples

### A. New per_run input plugin: `glob_reader`

Goal: read paths matching a shell glob.

```yaml
# src/archiverr/plugins/glob_reader/manifest.yml
name: glob_reader
version: 1.0.0
description: Creates jobs from a shell-glob-resolved list of paths
stage: input
run_mode: per_run
class_name: GlobReaderPlugin
entry_point: client.py
requires: []
provides: [job.create, fs.read]
trigger_rule: all_success
categories: []

config_schema:
  pattern:
    type: string
    required: true
    min_length: 1
    description: "Shell glob, e.g. '/media/movies/**/*.mkv'"
  recursive:
    type: boolean
    default: true
```

```python
# src/archiverr/plugins/glob_reader/client.py
"""Glob-based input plugin."""
import glob
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import InputPlugin


class GlobReaderPlugin(InputPlugin):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "glob_reader"
        self.pattern: str = config["pattern"]
        self.recursive: bool = config.get("recursive", True)

    def execute_run(self, services: Any) -> dict[str, Any]:
        paths = sorted(glob.glob(self.pattern, recursive=self.recursive))
        self.info("glob resolved", pattern=self.pattern, count=len(paths))

        created = 0
        for path in paths:
            p = Path(path)
            services.create_job(
                input_value=str(p),
                input_data={
                    "filename": p.name,
                    "extension": p.suffix.lstrip("."),
                    "size_bytes": p.stat().st_size if p.exists() else 0,
                    "source": "glob_reader",
                },
            )
            created += 1

        return {"jobs_created": created}
```

### B. New per_job DATA-stage plugin: `letterboxd`

Goal: enrich movies with Letterboxd ratings, depending on TMDb.

```yaml
# src/archiverr/plugins/letterboxd/manifest.yml
name: letterboxd
version: 0.1.0
description: Adds Letterboxd ratings using tmdb_id
run_mode: per_job
stage: data
class_name: LetterboxdPlugin
entry_point: client.py

requires:
  - plugin.tmdb.data:success      # need tmdb_id
  - plugin.renamer.parsed:success # need to know it's a movie

provides:
  - http.request

trigger_rule: all_success
categories: [movie]

config_schema:
  api_base:
    type: string
    default: "https://api.letterboxd.com/v0"
  timeout_seconds:
    type: integer
    default: 10
```

```python
# src/archiverr/plugins/letterboxd/client.py
from datetime import datetime
from typing import Any

import httpx

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult


class LetterboxdPlugin(OutputPlugin):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "letterboxd"
        self.api_base: str = config["api_base"]
        self.timeout: int = config.get("timeout_seconds", 10)

    def execute(self, job: Any, services: Any) -> PluginResult:
        started_at = datetime.now()

        # Read upstream data via the canonical surface
        tmdb_data = services.get_plugin_data(job.id, "tmdb") or {}
        movie = tmdb_data.get("movie")
        if not movie:
            return PluginResult.skipped_result(
                reason="no movie data from tmdb (likely a TV show)",
                started_at=started_at,
            )

        tmdb_id = movie.get("identifiers", {}).get("tmdb_id")
        if not tmdb_id:
            return PluginResult.skipped_result(
                reason="no tmdb_id available",
                started_at=started_at,
            )

        # Make request
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.api_base}/film/by-tmdb/{tmdb_id}")
                resp.raise_for_status()
                payload = resp.json()
        except Exception as exc:
            self.error("Letterboxd request failed", tmdb_id=tmdb_id, exc=str(exc))
            return PluginResult.error_result(str(exc), started_at=started_at)

        # Mark provides as soon as the network is done so dependents can start
        services.provides.complete("http.request")

        data = {
            "movie": {
                "identifiers": {"letterboxd_slug": payload.get("slug")},
                "ratings": {
                    "letterboxd": {
                        "score": payload.get("rating", {}).get("average"),
                        "votes": payload.get("rating", {}).get("count"),
                    }
                },
            }
        }

        # Publish to the in-memory state surface
        services.update_plugin(data=data)

        return PluginResult.success_result(
            data=data,
            started_at=started_at,
            metadata={"api_calls": 1},
        )
```

Notes on the example:

* It depends on TMDb (`plugin.tmdb.data:success`) and the parser
  (`plugin.renamer.parsed:success`). The resolver guarantees both
  finish first.
* It returns `skipped_result(...)` when there's nothing to do
  (TV show, missing id) — *not* an error.
* It calls `services.provides.complete("http.request")` after the
  network call — if you have downstream plugins that consume the
  same provide, they can start immediately.

---

## 17. Testing

### Two non-negotiable test layers

1. **`tests/unit/core/test_plugin_agnostic.py` — guard for the core.**
   Forbids plugin names as string literals inside `src/archiverr/core/`.
   You don't add anything here when you write a plugin; you just don't
   regress it.
2. **Your plugin's own unit tests** under `tests/unit/plugins/<name>/`.

### Patterns that work

```python
# tests/unit/plugins/letterboxd/test_letterboxd.py
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from archiverr.plugins.letterboxd.client import LetterboxdPlugin


@pytest.fixture
def services_mock():
    s = MagicMock()
    s.run_safety = {"dry_run": False, "hardlink": False, "no_delete": False}
    s.get_plugin_data.return_value = {
        "movie": {"identifiers": {"tmdb_id": "603"}}
    }
    return s


@pytest.fixture
def job_mock():
    j = MagicMock()
    j.id = "job_test_0"
    j.input.value = "/media/movies/the.matrix.1999.mkv"
    return j


def test_skips_when_no_tmdb_data(services_mock, job_mock):
    services_mock.get_plugin_data.return_value = None
    plugin = LetterboxdPlugin({"api_base": "x", "timeout_seconds": 1})
    result = plugin.execute(job_mock, services_mock)
    assert result.success is True
    assert result.metadata.get("skipped") is True
```

### Things to NOT do in plugin tests

* **Don't import `GlobalStateManager` directly** to seed state —
  use a `MagicMock()` for `services`. Touching the real state
  manager couples your plugin tests to core internals and breaks
  whenever the manager moves.
* **Don't network-hit external APIs in unit tests.** Mock the HTTP
  client. Real-API tests live in `tests/test_real_api.py` and run
  separately.

---

## 18. Plugin-agnostic core

The single most important architectural rule in this codebase:

> The core (`src/archiverr/core/**/*.py`) **must not** contain any
> plugin name as a string literal — not in dicts, not in `==`
> comparisons, not in `in (...)` membership tests.

Enforcement: `tests/unit/core/test_plugin_agnostic.py`. The guard
runs three regex sweeps (map / equality / membership) over every
`.py` under `src/archiverr/core/` and fails CI on the first hit.

If you find yourself wanting to write `if name == "tmdb":` in core,
the fix is **always** to push that decision into the manifest. The
`provides:` / `requires:` / `categories:` / `stage:` fields exist
precisely so the core can stay agnostic.

This applies to **core only**. Inside `src/archiverr/plugins/*` you
can hardcode whatever plugin name you like — it's *your* plugin.

---

## 19. Dead schema fields

These manifest fields are **declared in `PluginManifest`** but have
**zero runtime consumers** as of 2026-04-30:

| Field          | Status                                                                                     |
| -------------- | ------------------------------------------------------------------------------------------ |
| `capabilities` | Pydantic accepts it; no code path reads it.                                                |
| `hooks`        | Same.                                                                                      |
| `listens_to`   | Same.                                                                                      |
| `reactive`     | Same.                                                                                      |
| `fs_lock`      | Validated for static-path collisions at startup. **No** runtime acquire/release.            |
| `categories`   | Read **only** by `models/response_builder.py:208-215` for UI summary. No pipeline routing. |

If you set them, you don't get an error — but you also don't get the
behavior the field name implies. Don't depend on them.

The Pydantic SDK at `manifest.py` will be cleaned up at some point;
until then, the dataset (`datasets/02-manifest.yml`) is the
authority and it lists them in the "REMOVED 2026-04-30" comment block.

---

## 20. Reference index

Absolute paths (from repo root):

### SDK / contracts
* `src/archiverr/core/plugins/sdk/base.py` — `BasePlugin`, `InputPlugin`, `OutputPlugin`, `ValidationResult`.
* `src/archiverr/core/plugins/sdk/types.py` — `PerRunPlugin`, `PerJobPlugin` runtime-checkable Protocols, enums (`PluginCategory`, `PluginStatus`, `MediaCategory`).
* `src/archiverr/core/plugins/sdk/result.py` — `PluginResult` Pydantic model + factories.
* `src/archiverr/core/plugins/sdk/manifest.py` — `PluginManifest` schema, `VALID_STAGES`, `VALID_TRIGGER_RULES`.
* `src/archiverr/core/plugins/sdk/context.py` — `ExecutionContext` dataclass.
* `src/archiverr/core/plugins/sdk/validators.py` — `validate_plugin_config`.

### Runtime
* `src/archiverr/core/plugins/discovery.py` — manifest discovery (`manifest.yml` → `manifest.yaml` → `plugin.yml` → `plugin.yaml` → `plugin.json`).
* `src/archiverr/core/plugins/loader.py` — class loading + 3-layer config merge.
* `src/archiverr/core/plugins/registry.py` — `PluginRegistry`, `Stage` enum.
* `src/archiverr/core/plugins/resolver.py` — `DependencyResolver` (topological sort).
* `src/archiverr/core/plugins/stage_executor.py` — per-job stage execution, `PluginExecutionResult`, event emission.
* `src/archiverr/core/triggers/evaluator.py` — `TriggerRuleEvaluator`.
* `src/archiverr/core/services/plugin_services.py` — `PluginServices` (the `services` argument).
* `src/archiverr/core/services/event_service.py` — read-only event view.
* `src/archiverr/core/services/provides_service.py` — `services.provides`.

### State
* `src/archiverr/state/template_context.py` — `TemplateContextBuilder`.
* `src/archiverr/state/manager.py` — `GlobalStateManager`.
* `src/archiverr/state/models.py` — `RunState`, `JobState`, `JobInput`, `JobOutput`.

### Datasets (specs are authoritative)
* `datasets/02-manifest.yml` — manifest schema, three-layer merge, valid values.
* `datasets/03-run-state.yml` — run/job state shape.
* `datasets/04-template-context.yml` — Jinja2 context shape, custom filters.
* `datasets/05-events.yml` — event constants and payloads (with verified emitters).
* `datasets/06-mongodb.yml` — MongoDB collection schemas.
* `datasets/07-plugin-io.yml` — per-plugin canonical input/output shapes.
* `datasets/08-services.yml` — `PluginServices` API spec.
* `datasets/10-aliases.yml` — alias resolution.
* `datasets/11-recovery.yml` — `persistence_mode` contract.
* `datasets/12-safety.yml` — `dry_run`, `hardlink`, `no_delete`.

### Tests to read for examples
* `tests/unit/core/test_plugin_agnostic.py` — the guard you must not regress.
* `tests/unit/plugins/<name>/` — existing plugins' unit tests show the mock-services pattern.

### Existing plugins (read these before writing your own)
| Plugin        | Stage  | Mode    | Notes                                                                                        |
| ------------- | ------ | ------- | -------------------------------------------------------------------------------------------- |
| `scanner`     | input  | per_run | Filesystem walker. `src/archiverr/plugins/scanner/`.                                          |
| `file-reader` | input  | per_run | Reads paths from a `.txt` file. Simplest input plugin to crib from.                          |
| `renamer`     | parse  | per_job | Filename → `{movie | show}` parser. Template for any local-only PARSE plugin.                |
| `tmdb`        | data   | per_job | HTTP API, dependency on renamer, `secret: true` config. Template for any external-API plugin.|
| `tvdb`        | data   | per_job | Same shape as tmdb.                                                                          |
| `omdb`        | data   | per_job | Same shape as tmdb.                                                                          |
| `tvmaze`      | data   | per_job | Same shape as tmdb.                                                                          |
| `ffprobe`     | data   | per_job | Subprocess-based local enrichment.                                                           |
| `tasker`      | output | per_job | Jinja2 templating + side effects (`save`, `print`). `entry_point: plugin.py`.                |

---

## Appendix A — checklist before opening a PR

* [ ] `manifest.yml` declares `name`, `stage`, `run_mode`, `class_name`, `entry_point`.
* [ ] `requires:` only references existing plugins / fields.
* [ ] `config_schema:` validates every field your `__init__` reads.
* [ ] Per-job plugin returns `PluginResult` (success / error / skipped factory).
* [ ] Per-run plugin calls `services.create_job(...)` to populate the run.
* [ ] Honors `services.run_safety["dry_run"]` for any side effect.
* [ ] No `print()` for logs (only for user output via tasker tasks).
* [ ] No `except: pass`; exceptions logged or returned as `error_result`.
* [ ] Unit tests cover happy path + at least one error path + skipped path.
* [ ] No plugin name string literal added to `src/archiverr/core/`.
* [ ] `pytest tests/unit/plugins/<name>/ -v` is green.
* [ ] `ruff check src/` is clean.
* [ ] `pytest tests/unit/core/test_plugin_agnostic.py -v` still passes.

---

## Appendix B — when this guide goes stale

If you discover the code disagrees with this doc:

1. Check the relevant dataset (`datasets/0X-*.yml`) — datasets are authoritative.
2. If the dataset agrees with the code → update this doc.
3. If the dataset disagrees with the code → file an issue per the
   "code is the bug" policy in `datasets/README.yml`.

The audit timestamp at the top of this doc is the last manual
verification date.
