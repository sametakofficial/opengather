# Tech Context

## Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Models | Pydantic v2 |
| Templates | Jinja2 via core `ConfigRenderEngine` |
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
      render/        # config/template rendering + dependency validation
    plugins/         # 9 active plugin implementations + manifests
    api/             # FastAPI surface
    cli/             # CLI entry point
    events/          # event bus and event definitions
    infrastructure/  # persistence and external integrations
    state/           # run/job state management + data resolver
    utils/           # config loading, helpers, filters
  tests/             # unit + e2e + integration coverage
  memory-bank/       # canonical low-noise project context
  datasets/          # documented contracts and schema-like references
  docs/              # author-facing guides, including plugin conventions
  config.yml         # main runtime config
  pyproject.toml     # project configuration
```

## Main Entry Points

- `src/archiverr/__main__.py` — module entry point
- `src/archiverr/cli/main.py` — CLI flow
- `src/archiverr/api/main.py` — API app entry
- `src/archiverr/core/orchestrator.py` — main orchestration boundary
- `src/archiverr/core/render/render_engine.py` — core Jinja2 render engine
- `src/archiverr/state/data_resolver.py` — data namespace resolver

## Active Plugin Set

There are 9 active plugin directories under `src/archiverr/plugins/`:

- `scanner`
- `file-reader`
- `renamer`
- `tmdb`
- `tvdb`
- `tvmaze`
- `omdb`
- `ffprobe`
- `tasker`

Non-plugin utility/cache directories such as `__pycache__` or `.deleted` are not active plugins.

## Key Technical Rules

- Pipeline is manifest-driven.
- Core stays plugin-agnostic; S39 guard baseline is 9/9 passing.
- Per-run and per-job plugin contracts are explicit.
- Dry-run safety is a first-class operating mode.
- Rendering belongs to core/render, not tasker-specific code.
- Plugins can opt into resolver namespace by declaring `manifest.emits`.
- `data_priority` uses longest-prefix matching for `data.<jobindex>.<category>.<dotted.path>` resolution.
- Template context uses `jobs[job_id].plugins.<name>`, `job.plugins.<name>`, `data.*`, and `run.*`; synthetic `plugin.<name>.{data,status}` is removed.
- Historical analysis docs are not the source of truth; current contracts live in code, datasets, docs, and the core Memory Bank files.

## Useful Commands

```bash
cd codebase/archiverr && source .venv/bin/activate
pytest tests/ -v
ruff check src/
mypy src/archiverr/
python -m archiverr
```
