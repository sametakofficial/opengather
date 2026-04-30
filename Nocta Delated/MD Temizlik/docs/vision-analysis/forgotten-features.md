# Forgotten Features -- Planned But Never Built

**Analyzed by:** Claude Opus 4.6 (1M context)
**Date:** April 10, 2026
**Sources:** All session reports, memory-bank snapshots, planning documents, config files

---

## Tier 1: High-Profile Features That Were Repeatedly Planned

### 1. MongoDB Backend Integration
- **First mentioned:** Session 12 (Nov 2025), in planned_system_datasets.yml
- **Repeatedly prioritized:** Sessions 14-17, 28, old progress.md ("HIGH PRIORITY - READY TO START")
- **Original plan:** Motor (async) + Beanie ODM, documented in MONGODB_STRUCTURE.md (now missing)
- **What happened:** Stack decision changed from Motor+Beanie to raw PyMongo sync (Session 29+). pymongo_persistence.py exists but is not wired to the orchestrator. docker-compose.yml exists with MongoDB 7.0 config.
- **Current status:** pymongo_persistence.py written, interface.py exists, PersistenceDelegate in state management -- but none connected to live pipeline. The strategic plan (Session 32) says "only if someone uses the API."
- **What was lost:** The entire Beanie ODM approach was abandoned. The elaborate MongoDB collection design in planned_system_datasets.yml (runs, jobs, plugins, branches collections) was designed but never implemented. The "branches" concept for git-like media state versioning was dropped entirely.

### 2. Web UI
- **First mentioned:** Old progress.md (Nov 2025) -- "Web UI for configuration and monitoring"
- **Planned components:** Task builder interface, Config editor, Response viewer, Plugin manager, Debug log viewer
- **What happened:** Draft UI files existed (empty). The strategic plan (Session 32) explicitly says "KILL: Web UI / Phase G -- no users, no demand."
- **Current status:** KILLED. No code, no plans.

### 3. FastAPI Integration (Live Pipeline Connection)
- **First mentioned:** Session 12 area, old progress.md
- **What was planned:** REST API endpoints for queries, commit history API, branch management API, diagnostics viewer API, WebSocket for live updates
- **What exists:** FastAPI routes exist (api/ directory, 15 files, ~2500 LOC), CORS middleware, Pydantic schemas, versioned routes (/api/v1/). 14 tests fail without MongoDB.
- **What's missing:** Endpoints are not connected to the live orchestrator. process_executor.py expects old report format. No WebSocket implementation.
- **Current status:** DEFERRED. Strategic plan says "only if someone uses the API."

### 4. Unit Test Coverage
- **First mentioned:** Session 1 (AI deep investigation, Dec 2024) -- "Test coverage: 3/10"
- **Old target:** 60%+ minimum, then 80%+
- **What happened:** Tests went from ~0 to 425 passing (sessions 29-31), but many test files are still 0-byte: test_plugin_services.py, test_startup_validator.py, test_pymongo_persistence.py. E2E and integration directories are empty.
- **Current status:** Partially addressed. Core tests exist but plugin-level and integration tests never written.

### 5. Config Validation Enforcement
- **First mentioned:** Old progress.md -- "JSON Schema for config.yml, validate on load"
- **What exists:** config.schema.json exists, ConfigValidator is Pydantic-based, StartupValidator was wired in Session 31
- **What's missing:** JSON Schema is not enforced at load time. Config validation exists but doesn't use the schema file.
- **Current status:** PARTIALLY DONE. Startup validation wired, but schema enforcement never completed.

---

## Tier 2: Features That Were Brainstormed But Never Started

### 6. Plugin Hot-Reloading
- **Source:** Old progress.md "Advanced Features" section
- **What was planned:** Dynamic plugin installation, plugin hot-reload, plugin marketplace, custom filter registration, plugin versioning checks, compatibility matrix
- **Current status:** NEVER STARTED. Strategic plan doesn't mention it. Likely YAGNI for 9 plugins.

### 7. Advanced Branching (Git-Like Media State Versioning)
- **Source:** Old progress.md, planned_system_datasets.yml (branches collection)
- **Original vision:** Git-like versioning for media states, with branches and commits
- **What was built:** planned_system_datasets.yml has a branches collection design. FINAL_DATASETS.yml has no branches.
- **What happened:** Explicitly removed. planned_system_datasets.yml comments: "REMOVED: head_commit_id (no commits!)", "REMOVED: Commits reference (no commits!)" The owner's own comment in the file: "beyendim aferim" (liked and approved the simplification).
- **Current status:** KILLED by design. The owner approved removing the git-like complexity.

### 8. Plugin Self-Reporting (updateStatus)
- **Source:** planned_system_datasets.yml, detailed design
- **Original vision:** Plugins call services.updateStatus(state, success, message, error) to report their own status. Manifests would have status_reporting config (auto_start, auto_complete, timeout_ms).
- **What exists:** PluginServices.update_status() exists and is wired. But: (a) no manifest status_reporting config, (b) no timeout enforcement, (c) system still tracks plugin status alongside self-reporting.
- **Current status:** PARTIALLY DONE. The method exists but the full vision (manifest-driven status reporting behavior with timeouts) was never implemented.

### 9. CI/CD Pipeline
- **Source:** AI/session_1_deep_investigation/ACTION_ITEMS.md -- "Priority 3 (1 Month)"
- **What was planned:** GitHub Actions CI with ruff check, pytest --cov. Pre-commit hooks with ruff, trailing-whitespace, end-of-file-fixer.
- **Current status:** NEVER DONE. No .github/workflows, no .pre-commit-config.yaml.

### 10. Documentation Suite
- **Source:** AI/session_1_deep_investigation/ACTION_ITEMS.md
- **Planned docs:** README.md, INSTALLATION.md, CONFIGURATION.md, PLUGIN_DEVELOPMENT.md, API_REFERENCE.md, ARCHITECTURE.md, CONTRIBUTING.md
- **Current status:** NEVER DONE. No user-facing documentation exists.

### 11. Logging Modernization (Loguru)
- **Source:** AI/session_1_deep_investigation/ACTION_ITEMS.md -- "Priority 4 (3 months)"
- **Original plan:** Replace custom Debugger with Loguru
- **What happened:** planned_system_datasets.yml suggested standard Python logging. Current code still uses custom Debugger class.
- **Current status:** NEVER DONE. Custom Debugger persists.

### 12. Performance Optimization Suite
- **Source:** Old progress.md "Performance" section
- **Planned:** Response caching, template compilation caching, parallel plugin execution optimization, memory usage profiling, performance benchmarks
- **Current status:** NEVER DONE. ThreadPoolExecutor exists for parallel execution but no caching or profiling.

---

## Tier 3: Config Features Designed But Not Implemented

### 13. Variable Definitions Everywhere in Config
- **Source:** planned_system_datasets.yml, FINAL_DATASETS.yml
- **Design:** Config aliases would expand from shorthand to full plugin paths: `m -> plugin.tmdb.data.movie`, `s -> plugin.tmdb.data.show`, `p -> plugin.renamer.data.parsed`
- **What exists in config.yml:** Aliases exist but use old format: `m: "match"`, `movie: "renamer.parsed.movie"` -- these are the v1 alias paths, not the new plugin.* format from planned_system_datasets.yml
- **Current status:** PARTIALLY DONE. Old aliases work but the new plugin.* path format from the planned design was never adopted in config.yml.

### 14. Enhanced Requires Syntax (exists, success:true)
- **Source:** planned_system_datasets.yml
- **Design:** `plugin.renamer.data.parsed:exists` and `plugin.renamer.status.success:true` as separate checks
- **What exists:** `plugin.renamer.parsed:success` format works. ValueMatcher supports provides.*:completed.
- **What's missing:** The `:exists` check (separate from `:success`) was never implemented.
- **Current status:** PARTIALLY DONE. success/fail checks work, but exists as a separate concept was dropped.

### 15. Retry-Failed Plugin
- **Source:** planned_system_datasets.yml execution_flow example
- **Design:** A plugin that waits for `run.status.completed:true` then creates new jobs for failed items
- **Current status:** NEVER BUILT. Pure design artifact.

### 16. Plugin Status Timeout
- **Source:** planned_system_datasets.yml manifest section
- **Design:** `status_reporting.timeout_ms: 30000` -- if no status update, mark as failed
- **Current status:** NEVER BUILT.

### 17. Reactive Plugins
- **Source:** AI/DATASETS.md manifest definition -- `reactive: boolean` field
- **Design:** Plugins that react to events rather than running in pipeline stages
- **Current status:** NEVER BUILT. The field exists in the manifest schema documentation but no code supports it.

### 18. Plugin Hooks and listens_to
- **Source:** AI/DATASETS.md manifest definition -- `hooks: [string]`, `listens_to: [string]`
- **Design:** Plugins could declare hooks they implement and events they listen to
- **Current status:** NEVER BUILT. Pure schema documentation.

### 19. Plugin Capabilities Field
- **Source:** AI/DATASETS.md manifest definition -- `capabilities: [string]`
- **Design:** Separate from provides, declaring what capabilities a plugin has
- **Current status:** NEVER BUILT. The provides field serves a similar purpose (though it's also largely decorative).

---

## Tier 4: Infrastructure That Was Built But Abandoned

### 20. Memory System (core/memory/)
- **Source:** planned_system_datasets.yml removals section
- **What happened:** 644 lines of code removed. Described as "premature optimization, v2'de eklenecek" (will be added in v2).
- **Current status:** REMOVED. Never came back in v2.

### 21. Celery Workers (core/workers/)
- **Source:** planned_system_datasets.yml removals section
- **What happened:** 189 lines removed. "Unused Celery integration."
- **Current status:** REMOVED. Distributed task execution was abandoned.

### 22. Custom Variable Engine ({var:filter} syntax)
- **Source:** Old progress.md "Removed Features" section
- **What happened:** Replaced by Jinja2. Described as "simpler architecture, industry-standard tools."
- **Current status:** REMOVED by design. Jinja2 was the correct replacement.

### 23. Priority Lists (tv_priority, movie_priority)
- **Source:** Old progress.md "Removed Features" section
- **What happened:** Replaced by plugin enable/disable in config.yml
- **Current status:** REMOVED by design.

### 24. APIManager with Fallback
- **Source:** Old progress.md "Removed Features" section
- **What happened:** Replaced by plugin execution groups (dependency-based ordering)
- **Current status:** REMOVED by design.

---

## Summary Table

| # | Feature | First Mentioned | Current Status | Should Revive? |
|---|---------|----------------|----------------|----------------|
| 1 | MongoDB Backend | Session 12 | Partially built, not wired | YES (when needed) |
| 2 | Web UI | Nov 2025 | KILLED | NO |
| 3 | FastAPI Live Connection | Session 12 | Exists but disconnected | DEFER |
| 4 | Unit Test Coverage | Session 1 | Partially done (425 tests) | YES (incrementally) |
| 5 | Config Validation | Nov 2025 | Partially done | LOW PRIORITY |
| 6 | Plugin Hot-Reload | Nov 2025 | Never started | NO (YAGNI) |
| 7 | Git-Like Branching | Nov 2025 | KILLED by owner | NO |
| 8 | Plugin Self-Reporting | Dec 2024 | Partially done | LOW PRIORITY |
| 9 | CI/CD | Dec 2024 | Never done | YES |
| 10 | Documentation | Dec 2024 | Never done | YES (if users emerge) |
| 11 | Loguru Migration | Dec 2024 | Never done | NO (custom Debugger works) |
| 12 | Performance Suite | Nov 2025 | Never done | DEFER |
| 13 | New Config Aliases | Dec 2024 | Partially done | LOW PRIORITY |
| 14 | :exists Requires | Dec 2024 | Dropped | NO |
| 15 | Retry-Failed Plugin | Dec 2024 | Never built | INTERESTING |
| 16 | Status Timeout | Dec 2024 | Never built | LOW PRIORITY |
| 17 | Reactive Plugins | Dec 2024 | Never built | INTERESTING (future) |
| 18 | Plugin Hooks | Dec 2024 | Never built | DEFER |
| 19 | Capabilities Field | Dec 2024 | Never built | NO (overlaps provides) |
| 20 | Memory System | Pre-v2 | Removed | NO |
| 21 | Celery Workers | Pre-v2 | Removed | NO |
| 22 | Custom Variable Engine | Pre-v2 | Replaced by Jinja2 | NO |
| 23 | Priority Lists | Pre-v2 | Replaced | NO |
| 24 | APIManager Fallback | Pre-v2 | Replaced | NO |
