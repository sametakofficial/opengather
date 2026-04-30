# Active Context

**Last Updated:** April 30, 2026 afternoon  
**Focus:** Post-Session 37 stabilization: MongoDB + FastAPI are now E2E-proven; keep Memory Bank low-noise and factual.

## Current State

- Archiverr is a plugin-based media metadata enrichment system with a plugin-agnostic core.
- Core execution path is manifest-driven and all active plugins are on the modern contract.
- `services.events` is read-only for plugins; plugin-side emit/subscribe is intentionally not part of the active contract.
- `{{ events }}` is available in template context via snapshot-based injection.
- Recovery model is currently **slim**: practical single-orchestrator assumption for a given Mongo deployment.
- MongoDB is not mandatory for CLI/API usage; degraded/off modes exist.
- MongoDB + FastAPI E2E flow is proven: Docker Mongo, CLI run, API POST/GET, canonical collection reads/writes.
- FastAPI lifespan now creates Mongo indexes idempotently; CLI and API share the same index contract.
- API run responses expose persistence visibility (`mode`, `backend`, `persisted`).

## Active Decisions

- **Plugin-agnostic core stays non-negotiable.** Core must not know plugin names.
- **Memory Bank is canonical; old analysis docs are not.** Historical analysis should not be auto-loaded as default context.
- **Keep current pipeline shape.** No new stage or framework expansion without a concrete need.
- **Mongo persistence must be honest to callers.** Degraded mode may complete without writes, but API responses must surface `persisted=false`.
- **FastAPI Mongo path uses one async client boundary.** `AsyncMongoDB` singleton + lifespan is the active async path.
- **Subprocess `/run/` must not fake success IDs.** CLI stdout marker `ARCHIVERR_RUN_ID=<id>` is the contract; unknown stays `unknown`.
- **Per-run plugin executions remain out of scope.** Current `plugin_executions` contract is per-job; per-run wiring needs a separate schema decision.
- **Prefer small, factual docs.** Current truth belongs here; long narrative history belongs in archive/session files.

## Known Open Areas

- FastAPI in-process `/runs/` + Mongo read/write path is E2E-proven; remaining `/run/` is a subprocess proxy by design.
- Per-run plugin execution records are intentionally not wired into `plugin_executions` yet.
- Legacy Mongo collection backup/drop remains deferred.
- CI/CD is still a missing operational layer.
- Plugin developer docs and real TMDb smoke remain open.
- Pydantic dead schema cleanup and `/run/` long-term deprecation are backlog decisions.
- Pre-existing ruff whitespace/docstring debt remains, but is not an S37 regression.
- Tasker plugin has a non-blocking `'data'` KeyError on virtual-path scan.

## Next Steps

1. Clean up `RunRepository` stubs.
2. Decide schema/wiring for per-run `plugin_executions` if recovery needs it.
3. Back up/drop pre-S36 legacy Mongo collections if live data exists.
4. Set up CI for pytest + ruff.
5. Add plugin developer docs and run a real TMDb smoke test.
