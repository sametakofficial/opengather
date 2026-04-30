# Tech Context

## Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Models | Pydantic v2 |
| Templates | Jinja2 |
| HTTP | Requests |
| Config | PyYAML |
| Database | PyMongo |
| API Framework | FastAPI (optional path) |
| Linting | Ruff |
| Typing | Mypy |
| Formatting | Black |
| Testing | Pytest |

## Project Structure

```text
codebase/archiverr/
  src/archiverr/
    core/            # orchestration, plugins, validation, triggers, services
    plugins/         # active plugin implementations + manifests
    api/             # FastAPI surface
    cli/             # CLI entry point
    events/          # event bus and event definitions
    infrastructure/  # persistence and external integrations
    state/           # run/job state management
    utils/           # config loading, helpers, filters
  tests/             # unit + e2e + integration coverage
  memory-bank/       # canonical low-noise project context
  datasets/          # documented contracts and schema-like references
  config.yml         # main runtime config
  pyproject.toml     # project configuration
```

## Main Entry Points

- `src/archiverr/__main__.py` — module entry point
- `src/archiverr/cli/main.py` — CLI flow
- `src/archiverr/api/main.py` — API app entry
- `src/archiverr/core/orchestrator.py` — main orchestration boundary

## Key Technical Rules

- Pipeline is manifest-driven.
- Core stays plugin-agnostic.
- Per-run and per-job plugin contracts are explicit.
- Dry-run safety is a first-class operating mode.
- Historical analysis docs are not the source of truth; current contracts live in code, datasets, and the core Memory Bank files.

## Useful Commands

```bash
cd codebase/archiverr && source .venv/bin/activate
pytest tests/ -v
ruff check src/
mypy src/archiverr/
python -m archiverr
```
