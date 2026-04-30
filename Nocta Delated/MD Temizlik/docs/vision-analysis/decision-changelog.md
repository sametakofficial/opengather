# Decision Changelog -- Decisions Made, Changed, or Reversed

**Analyzed by:** Claude Opus 4.6 (1M context)
**Date:** April 10, 2026

---

## Format

Each entry: **Decision** -> **When** -> **What Changed** -> **Why** -> **Current Status**

---

## Architecture Decisions

### D1: Plugin Discovery Format
- **Original (Sessions 1-10):** plugin.json
- **Changed (Session 12, Nov 2025):** manifest.yml introduced alongside plugin.json
- **Changed (Session 29, Apr 2026):** All plugin.json files moved to .deleted/, manifest.yml is the only format
- **Why:** YAML is more readable, supports comments, and aligns with industry practice (Home Assistant uses manifest.json but the principle is the same)
- **Current:** manifest.yml is the single source. Discovery priority still supports 5 formats (manifest.yml > manifest.yaml > plugin.yml > plugin.yaml > plugin.json) for backward compatibility, but only manifest.yml files exist.

### D2: Template Engine
- **Original (Sessions 1-10):** Custom variable engine with {var:filter} syntax
- **Changed (v2.0):** Replaced with Jinja2
- **Why:** "Industry-standard tools, less custom code to maintain, easier to extend"
- **Current:** Jinja2 with 40+ custom filters. PERMANENT decision. Never revisited.

### D3: Plugin-Agnostic Core
- **Original:** Core had hardcoded plugin names (class_name mapping in loader.py, 'renamer' check in executor.py)
- **Formalized (Session 11-12, Nov 2025):** "Plugin-agnostic core" declared as architecture rule
- **Enforced (Session 29, Apr 2026):** test_plugin_agnostic.py added as static analysis guard
- **Why:** "Infinitely scalable. Core never breaks when adding new plugins."
- **Current:** ZERO TOLERANCE policy. Guard test scans all core source files for plugin name literals. Any violation fails the test suite.

### D4: MongoDB Stack
- **Original (Nov 2025):** Motor (async driver) + Beanie ODM
- **Changed (Session 29, Apr 2026):** PyMongo sync for CLI, Motor deprecated
- **Changed further:** Beanie ODM dropped, raw PyMongo instead
- **Why:** CLI doesn't need async. PyMongo is simpler. Beanie added unnecessary abstraction.
- **Current:** pymongo_persistence.py exists (sync). Motor code is dead (526 LOC in mongodb.py, marked for .deleted/). AsyncMongoDB class exists for FastAPI path.

### D5: State Management Architecture
- **Original (planned_system_datasets.yml, Dec 2024):** 3 core objects (run, config, context) replacing 6 separate objects
- **Implemented (Sessions 12-14):** GlobalStateManager with SRP delegates (JobManager, PluginDataManager, PersistenceDelegate, StateEventEmitter, TemplateContextBuilder, ExecutionContext)
- **Owner comment on plan:** "beyendim aferim" (approved the 6->3 simplification)
- **Current:** 5 delegates exist. The planned 6->3 reduction was partially achieved -- it became a delegate-based architecture instead of a 3-object simplification.

### D6: Git-Like Branching for Media States
- **Original (Sessions 1-10):** Planned branches and commits for media state versioning
- **Designed (planned_system_datasets.yml):** Full branches collection with name, description, is_default
- **Killed (planned_system_datasets.yml):** "REMOVED: head_commit_id (no commits!)", "REMOVED: Commits reference (no commits!)"
- **Why:** Over-engineering. The owner recognized it was unnecessary.
- **Current:** DEAD. run.branch is a simple string tag, not a git-like branch system.

### D7: Schema System
- **Original:** ~3,500 LOC schema validation system
- **Removed (Session area, Nov 2025):** Entirely deleted
- **Why:** Over-engineering. Plugin-managed validation replaced it.
- **Current:** GONE. Plugins manage their own validation in plugin.globals.validation.

### D8: Naming Conventions (execution -> run, match -> job)
- **Planned (planned_system_datasets.yml):** Full rename: execution->run, match->job, debugger->logger
- **Partially done:** execution->run and match->job are in the codebase. Some code still uses old names.
- **debugger->logger:** NEVER DONE. Custom Debugger class persists.
- **Current:** Mostly migrated. Some vestiges of old naming remain.

---

## Plugin System Decisions

### D9: Provides/Requires Semantic Gap
- **Original design (planned_system_datasets.yml):** provides and requires would intersect -- provides declares capabilities, requires references them
- **Reality discovered (Session 31 brainstorm):** "These two systems never intersect." Provides declares generic capabilities (http.request, state.update). Requires uses specific data paths (plugin.renamer.parsed:success). Different namespaces = no functional connection.
- **Options proposed:** (A) Data contract provides, (B) Wire ProvidesRegistry, (C) Drop provides entirely, (D) Hybrid
- **Decision (Session 31):** Wire ProvidesRegistry into execution lifecycle (Phase 1). Added provides.*:completed syntax (Phase 3).
- **Current:** ProvidesRegistry is wired. Provides is still mostly decorative metadata but now at least tracked during execution. The semantic gap is acknowledged but not fully resolved.

### D10: Plugin Interface (hasattr vs Protocol)
- **Original:** 22+ hasattr checks in stage_executor for runtime introspection
- **Session 31 brainstorm:** Proposed PerRunPlugin and PerJobPlugin protocols
- **Session 31 Phase 2:** Protocols defined and implemented. hasattr reduced 23->8.
- **Current:** Protocols exist. 8 hasattr calls remain. 3 legacy plugins (tvdb, tvmaze, omdb) still use old execute(match_data) interface.

### D11: Topological Sort Implementation
- **Original:** stage_executor._topological_sort() -- pseudo-sort by len(requires)
- **Built but unused:** DependencyResolver in resolver.py -- proper topo sort with cycle detection
- **Session 31 Phase 1:** DependencyResolver wired into StageExecutor
- **Current:** Real topo sort is active. Old pseudo-sort removed.

### D12: PluginServices Implementation
- **Two implementations existed:** (1) Concrete class in plugin_services.py (used), (2) @dataclass with protocol-typed fields in services/__init__.py (dead)
- **Session 31 Phase 2:** Dead dataclass removed from services/__init__.py
- **Current:** Single concrete implementation. Clean.

### D13: Extras Plugin
- **Session 28 report mentions:** "10 working plugins: scanner, file-reader, ffprobe, renamer, tmdb, tvdb, tvmaze, omdb, tasker, extras"
- **Current state (Session 31):** Only 9 plugins listed. "extras" disappeared.
- **What happened:** Extras functionality was merged into individual plugins (tmdb has extras.py, tvdb has extras.py, etc.) rather than being a separate plugin.

---

## Infrastructure Decisions

### D14: Async vs Sync
- **AI/session_1_deep_investigation recommended (Dec 2024):** "Decide: fully sync (CLI), fully async (API), or hybrid"
- **Decision (Session 29+):** PyMongo sync for CLI. Async only for FastAPI path.
- **Current:** Hybrid. CLI is sync. API path would be async (if ever connected).

### D15: Event Handler Naming
- **Original:** Legacy names (MATCH_COMPLETED, MATCH_FAILED, EXECUTION_STARTED)
- **Session 31 discovery:** Handlers listened for legacy names that the pipeline never emitted
- **Session 31 Phase 4:** Event handlers updated to current event names
- **Current:** Fixed. But most handlers are still rarely used in practice.

### D16: complete_job() Bug
- **Discovered (Session 32 strategic plan):** complete_job() is never called, so run stats are always wrong
- **Status:** Known bug, fix planned for Session 32 (1 line + 1 test)
- **Current:** STILL BROKEN as of Session 31.

### D17: Dual RUN_STARTED Event
- **Discovered (Session 32 strategic plan):** Both orchestrator.py:253 and state/manager.py:141 emit run.started
- **Status:** Known bug, fix planned for Session 32 (1 line delete)
- **Current:** STILL BROKEN as of Session 31.

---

## Strategic Decisions

### D18: Build Product vs Build Playground
- **Original vision (Sessions 1-10):** Product (compete with FileBot)
- **Shifted (Sessions 11-14):** Playground with product aspirations
- **Acknowledged (Session 32 strategic plan):** "The playground framing is the correct framing. The value is in the architecture practice."
- **Current:** PLAYGROUND. The 6-agent analysis confirmed: "No market demand. FileBot has millions of users."

### D19: Refactoring vs Feature Development
- **Sessions 1-31:** 31 sessions of iterative architecture refinement
- **Session 32 strategic plan:** "Stop refactoring the framework. Start writing plugins that do interesting things."
- **Rule proposed:** "Every refactoring session must include something user-visible."
- **Current:** Rule proposed but not yet tested (Session 32 hasn't happened).

### D20: Dead Code Policy
- **Accumulated:** ~909 LOC of confirmed dead code (StateServiceImpl 278, _topological_sort 20, check_expects 15, MongoDBPersistence 527, motor.py 47, validate_dependencies 22)
- **Strategic plan says:** "DO IT" (all agents agree on removal)
- **Current:** STILL IN CODEBASE. Removal planned for Session 32.

---

## Decision Pattern Analysis

### Decisions That Stuck
1. Jinja2 over custom engine -- PERMANENT
2. Plugin-agnostic core -- PERMANENT, now enforced
3. Manifest-driven discovery -- PERMANENT
4. Stage-based pipeline (PARSE->DATA->OUTPUT) -- PERMANENT
5. No-delete policy (.deleted/ instead of rm) -- PERMANENT
6. Dry-run as default -- PERMANENT

### Decisions That Were Reversed
1. Motor+Beanie -> PyMongo sync (good reversal, simpler)
2. Git-like branching -> simple string tag (good reversal, YAGNI)
3. Schema system (3,500 LOC) -> plugin-managed validation (good reversal)
4. Custom variable engine -> Jinja2 (good reversal)
5. Pseudo topo-sort -> real DependencyResolver (good reversal, correctness)

### Decisions That Were Made But Never Executed
1. MongoDB backend implementation (5 months dormant)
2. CI/CD pipeline
3. Documentation suite
4. Loguru migration
5. Performance benchmarks
6. Config validation enforcement
7. Plugin hot-reloading

### Pattern
The owner is excellent at **recognizing when to simplify** (removing 3,500 LOC, killing git branching, approving 6->3 state reduction). But there's a pattern of **planning infrastructure that never gets built** (MongoDB, CI/CD, docs) while **refactoring existing infrastructure** (31 sessions of architecture work).
