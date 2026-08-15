# Active Context

**Last Updated:** May 02, 2026  
**Focus:** Post-Session 39 stabilization: Data Resolver Namespace + Render Refactor are implemented; preserve plugin-agnostic core while cleaning remaining S39 carry-over risks.

## Current State

- Archiverr is a plugin-based media metadata enrichment system with a plugin-agnostic core.
- Core execution path is manifest-driven and all 9 active plugins are on the modern contract.
- `services.events` is read-only for plugins; plugin-side emit/subscribe is intentionally not part of the active contract.
- Rendering is now a core capability: `core/render/ConfigRenderEngine` owns Jinja2 rendering with `ChainableUndefined`.
- `tasker` no longer imports Jinja2 directly; it consumes `services.render_engine` / `services.get_runtime_config()` and acts as a print/save dispatcher.
- Template context no longer exposes the synthetic `plugin.<name>.{data,status}` namespace. Use `jobs[job_id].plugins.<name>`, `job.plugins.<name>`, `data.*`, and `run.*`.
- `data.<jobindex>.<category>.<dotted.path>` is the resolver namespace for prioritized metadata access.
- `RunState.data` is persisted under `runs.data`; G1 real E2E confirmed Breaking Bad flat-shape rendering and Mongo persistence.
- Recovery model is currently **slim**: practical single-orchestrator assumption for a given Mongo deployment.
- MongoDB is not mandatory for CLI/API usage; degraded/off modes exist.
- FastAPI lifespan creates Mongo indexes idempotently; CLI and API share the same index contract.
- API run responses expose persistence visibility (`mode`, `backend`, `persisted`).

## Recent Changes

1. Session 39 completed the R15 Data Resolver Namespace + Render Refactor plan on `dev/communication-refactoring`.
2. 23 commits landed across 7 phases: A=3, C=2, H=5, I=1, B=1, C5=1, D=5, E=2, F=2, G=1.
3. Added `manifest.emits` and config `data_priority`; resolver uses longest-prefix priority matching.
4. Added `src/archiverr/core/render/` with `ConfigRenderEngine`, AST walker, and parse-time template dependency validator.
5. Added `src/archiverr/state/data_resolver.py` and `RunState.data` envelope recomputation/persistence.
6. Removed `_build_plugin_surface` and the synthetic `plugin.<name>.{data,status}` Jinja namespace.
7. Standardized TMDb output to flat `show` + `movie` top-level keys; episode/season details are baked into `show`.
8. Fixed four audit blockers: H10 AST walker, H11 jobs list-to-dict context, H12 save_run on job plugin update, H13 tasker no-Jinja path.
9. G1 real E2E caught and fixed Mongo persistence failure from integer job-index keys via `RunState.to_dict()` key stringification.
10. Added `docs/PLUGIN_CONVENTIONS.md` and refreshed datasets `01-config.yml`, `02-manifest.yml`, `04-template-context.yml`, `13-plugin-system-overview.yml`.

## Active Decisions

- **Plugin-agnostic core stays non-negotiable.** Core must not know plugin names; S39 plugin-agnostic guard remains 9/9 passing.
- **Memory Bank is canonical; old analysis docs are not.** Historical analysis should not be auto-loaded as default context.
- **Keep current pipeline shape.** No new stage or framework expansion without a concrete need.
- **Render capability lives in core, not in tasker.** Plugins access rendered runtime config through services.
- **Resolver participation is opt-in.** Plugins declare metadata paths through `manifest.emits`; config controls precedence through `data_priority`.
- **TMDb flat shape is current truth.** OMDb/TVMaze/TVDB still declare their current non-flat shape and convention alignment is deferred.
- **Mongo persistence must be honest to callers.** Degraded mode may complete without writes, but API responses must surface `persisted=false`.
- **FastAPI Mongo path uses one async client boundary.** `AsyncMongoDB` singleton + lifespan is the active async path.
- **Subprocess `/run/` must not fake success IDs.** CLI stdout marker `ARCHIVERR_RUN_ID=<id>` is the contract; unknown stays `unknown`.
- **Per-run plugin executions remain out of scope.** Current `plugin_executions` contract is per-job; per-run wiring needs a separate schema decision.
- **Prefer small, factual docs.** Current truth belongs here; long narrative history belongs in archive/session files.

## Known Open Areas

- OMDb / TVMaze / TVDB declare current non-flat shape in `emits`; they were not migrated to TMDb's flat shape in S39.
- S39 code smells: `_recompute_data_envelope` reaches into `context._jobs`, constructs a fresh `DataResolver` per call, and enumerates category roots even for sub-path-specific priority keys.
- Untracked artifacts remain in `AI/`, `ONEMLI/`, `user-prompts/`, and `datasets/15-runtime-state-example.json`; decide commit / `.gitignore` / `.deleted/`.
- B1-B6 carry-over from S37 remains relevant: RunRepository stub cleanup, per-run plugin_executions writer decision, legacy Mongo collection backup/drop, CI/CD, plugin developer docs, real TMDb smoke test.
- Pydantic dead schema cleanup and `/run/` long-term deprecation are backlog decisions.
- Pre-existing ruff whitespace/docstring debt remains, but is not an S39 regression.

## Next Steps

1. Decide whether to migrate OMDb/TVMaze/TVDB to TMDb-style flat shape or explicitly document divergence as accepted.
2. Address S39 resolver-envelope smells: private `_jobs` access, resolver caching, and sub-path enumeration work.
3. Decide disposition of untracked artifacts.
4. Clean up `RunRepository` stubs.
5. Decide schema/wiring for per-run `plugin_executions` if recovery needs it.
6. Back up/drop pre-S36 legacy Mongo collections if live data exists.
7. Set up CI for pytest + ruff.
8. Run a real TMDb smoke test.
