# Progress

**Last Updated:** Session 29 - April 8, 2026

## What Works

### Core System
- [x] Plugin discovery (manifest.yml based, auto-loading)
- [x] Dependency resolution (topological sort, parallel groups)
- [x] Expects system (runtime data validation)
- [x] 4-stage pipeline (PARSE -> DATA -> OUTPUT with per_run init)
- [x] Plugin-agnostic core (ENFORCED, guard test protects)
- [x] Config-driven execution (YAML with env var expansion)
- [x] EventBus pub/sub communication
- [x] Response builder v4 (simplified, plugin-managed validation)
- [x] Compact response system (94% size reduction)
- [x] Debug logging (structured, config-driven)
- [x] State management (SRP with 5 delegates)
- [x] PARTIAL state (mixed success/failure runs)
- [x] Full UUID identifiers (no truncation)

### All 9 Plugins Working
- [x] scanner, file-reader (input)
- [x] renamer (parse)
- [x] tmdb, tvdb, tvmaze, omdb, ffprobe (data)
- [x] tasker (output - print, save, conditional, summary)

### All 9 Plugins Have manifest.yml
- [x] Explicit stage, provides, requires, run_mode
- [x] No legacy plugin.json files remain
- [x] config_schema with validation rules

### Template System
- [x] Jinja2 with 40+ custom filters
- [x] Per-match and summary task execution
- [x] Conditional templates

### Testing (340 passed)
- [x] Manifest normalizer tests (24)
- [x] State model tests
- [x] Config normalizer/YAML loader tests
- [x] Plugin-agnostic guard (static analysis of core)
- [x] API endpoint tests (4 fail without MongoDB - expected)
- [x] Validation tests (requires, dependency, manifest)

## What Doesn't Work

### Tests Not Written (0-byte files)
- [ ] `test_orchestrator.py` - Main execution coordinator (903 LOC, 0 tests)
- [ ] `test_stage_executor.py` - Per-job execution (903 LOC, 0 tests)
- [ ] `test_plugin_services.py` - Plugin-state interface
- [ ] `test_startup_validator.py` - Startup validation
- [ ] `test_pymongo_persistence.py` - MongoDB persistence
- [ ] `tests/e2e/` - Empty directory
- [ ] `tests/integration/` - Empty directory

### Not Implemented
- [ ] MongoDB backend integration (designed, pymongo_persistence.py exists but not wired to orchestrator)
- [ ] FastAPI endpoint connection to live orchestrator
- [ ] Async persistence interface for FastAPI
- [ ] Config validation enforcement (schema exists, not applied)
- [ ] Web UI

### Technical Debt
- [ ] Plugin data stored in 5 places (should be single source)
- [ ] Deprecated Motor code (527 LOC dead code)
- [ ] 928 ruff whitespace warnings
- [ ] TVDb/TVMaze debug logging partial
- [ ] Tasker plugin has renamer coupling (`if 'renamer' in plugins_data`)
- [ ] No MongoDB transaction support for multi-collection writes
- [ ] `response.globals` naming used at 3 levels (ambiguous)

## Session History

| Session | Date | Focus | Key Outcome |
|---------|------|-------|-------------|
| 1-10 | - | Initial development | Plugin system, core architecture |
| 11 | Nov 8, 2025 | Stage-based system | Expects system, debug integration |
| 12 | Nov 8, 2025 | Manifest migration | manifest.yml format introduced |
| 13-14 | Nov 2025 | Structure fixes | Input/output metadata, clean folders |
| 15 | Nov 2025 | (init only) | - |
| 16-17 | Nov 2025 | Communication refactoring | Trigger system, requires format |
| 21 | - | (init only) | - |
| 27 | - | (init only) | - |
| 28 | Apr 8, 2026 | Full analysis | SESSION_28_REPORT.md, 6 SVG diagrams |
| **29** | **Apr 8, 2026** | **Architecture fix** | **Hardcoded names removed, manifests completed, UUID+PARTIAL fixed** |
