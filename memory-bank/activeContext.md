# Active Context

**Last Updated:** April 18, 2026  
**Focus:** Keep Memory Bank as the primary low-noise context layer.

## Current State

- Archiverr is a plugin-based media metadata enrichment system with a plugin-agnostic core.
- Core execution path is manifest-driven and all active plugins are on the modern contract.
- `services.events` is read-only for plugins; plugin-side emit/subscribe is intentionally not part of the active contract.
- `{{ events }}` is available in template context via snapshot-based injection.
- Recovery model is currently **slim**: practical single-orchestrator assumption for a given Mongo deployment.
- MongoDB is not mandatory for CLI usage; degraded/off modes exist.

## Active Decisions

- **Plugin-agnostic core stays non-negotiable.** Core must not know plugin names.
- **Memory Bank is canonical; old analysis docs are not.** Historical analysis should not be auto-loaded as default context.
- **Keep current pipeline shape.** No new stage or framework expansion without a concrete need.
- **Prefer small, factual docs.** Current truth belongs here; long narrative history belongs in archive/session files.

## Known Open Areas

- Plugin data still has some structural duplication and could be consolidated later.
- FastAPI layer is still not the main proven execution path.
- CI/CD is still a missing operational layer.
- Some legacy cleanup and lint cleanup remain, but they are not architecture blockers.

## Next Steps

1. Add or improve plugin developer documentation.
2. Run a real pipeline smoke test with current template/event contract.
3. Set up CI for pytest + ruff.
4. Only revisit larger executor decomposition if a real maintenance pain appears.
