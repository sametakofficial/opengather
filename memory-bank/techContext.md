# Tech Context

## Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.10+ (dev on 3.14.2) |
| Models | Pydantic | v2.4+ |
| Templates | Jinja2 | 3.1+ |
| HTTP | Requests | 2.31+ |
| Config | PyYAML | 6.0+ |
| Database | PyMongo (sync) | 4.10+ |
| API Framework | FastAPI | 0.104+ (optional) |
| Linting | Ruff | 0.1+ |
| Typing | Mypy | 1.5+ |
| Formatting | Black | 23+ |
| Testing | Pytest | 7.4+ |

## Project Structure

```
codebase/archiverr/
  src/archiverr/
    core/
      plugins/          # Registry, discovery, loader, executor, resolver
        sdk/            # PluginManifest Pydantic model, base classes
      tasks/            # Task execution
      reports/          # Compact response system
      config/           # Config management
      services/         # Service layer
      validation/       # Validators (manifest, requires, dependency)
      triggers/         # Trigger system
      locking/          # FS lock system
    plugins/            # 9 plugins, each with manifest.yml + client.py
    api/                # FastAPI v1 routes (partially connected)
    cli/                # CLI entry point
    events/             # EventBus pub/sub
    infrastructure/     # MongoDB (pymongo_persistence.py is active)
    state/              # GlobalStateManager, JobState, RunState
    models/             # Response builder
    utils/              # Config loader, debug, Jinja2 filters
  tests/
    unit/               # 425 passing tests (4 MongoDB fail, 17 skipped)
      core/             # Manifest normalizer, plugin agnostic guard
      api/              # Endpoint tests (4 fail without MongoDB)
      state/            # State models, manager
      utils/            # Config normalizer, YAML loader
    e2e/                # Empty (needs implementation)
    integration/        # Empty (needs implementation)
  config.yml            # Main config
  pyproject.toml        # PEP 621 project config
```

## Key Files

| File | Purpose |
|------|---------|
| `core/plugins/manifest_normalizer.py` | Normalizes legacy manifests to stage-based format |
| `core/plugins/loader.py` | Loads and instantiates plugins with config validation |
| `core/plugins/discovery.py` | Discovers plugins from manifest files |
| `core/plugins/resolver.py` | Topological dependency resolution |
| `core/plugins/sdk/types.py` | PerRunPlugin/PerJobPlugin protocols (@runtime_checkable) |
| `core/plugins/stage_executor.py` | Per-job plugin execution in stages (decomposed, early completion) |
| `core/triggers/matcher.py` | ValueMatcher with provides.*:completed syntax |
| `events/handlers.py` | Event handlers (modernized in session 31) |
| `core/orchestrator.py` | Main execution coordinator (490 LOC) |
| `state/manager.py` | GlobalStateManager with SRP delegation |
| `state/models.py` | RunState, JobState, StateEnum (includes PARTIAL) |
| `infrastructure/database/pymongo_persistence.py` | Active MongoDB driver (sync) |
| `infrastructure/database/interface.py` | Persistence interface (sync only) |
| `utils/config_loader.py` | YAML loader with env var expansion, includes |

## Commands

```bash
cd codebase/archiverr && source .venv/bin/activate
pytest tests/ -v                          # all tests
pytest tests/unit/ -v                     # unit only
ruff check src/                           # lint
mypy src/archiverr/                       # typecheck
black src/ --check                        # format check
python -m archiverr                       # CLI (dry-run default)
```

## Git

- Remote: `origin -> github.com/sametakofficial/archiverr.git`
- Active branch: `dev/communication-refactoring`
- Stale branch: `feature/mongodb-implementation` (295 files diverged, unusable)
- Commit style: `session N: description` or `wip:`, `cleanup:`, `fix:`

## API Extras Support

| Extra | TMDb | TVDb | TVMaze | OMDb |
|-------|------|------|--------|------|
| Credits/Cast | movie, episode | show, movie, episode | show, episode | - |
| Images | movie, show, episode | show, movie, episode | show | - |
| Videos | movie, show | - | - | - |
| Keywords | movie | - | - | - |
| Ratings | - | - | - | imdb |

## Performance Constraints

- TMDb API: 40 req/10s (free tier)
- Target: <1s per file with cache
- Memory: <100MB for typical batches
- Dry-run mode enabled by default for safety
