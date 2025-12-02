# TODO

```yaml
session: 7
last_update: 2025-11-28
```

---

## PENDING

### HIGH
| Task | File | Status |
|------|------|--------|
| EventBus DI Refactor | `events/bus.py` | Ready |
| Task Queue (Taskiq+MongoDB) | `core/workers/` | Planned |
| Plugin SDK Structure | `plugins/sdk/` | Planned |

### MEDIUM
| Task | File | Status |
|------|------|--------|
| WebSocket/SSE Progress | `api/v1/` | Planned |
| Async ExecutionService | `core/services/` | Planned |

### LOW
| Task | File | Status |
|------|------|--------|
| Pydantic response_model | `api/v1/*/router.py` | Planned |
| Type hints | Various | Planned |

---

## COMPLETED

| Session | Task |
|---------|------|
| 6 | StateManager DI Refactor |
| 5 | Annotated DI Pattern, pyproject.toml |
| 4 | Motor to PyMongo Async |
| 1-3 | PyMongoPersistence, Test fixtures |

---

## DECISIONS

| Decision | Reason |
|----------|--------|
| Taskiq + MongoDB | Redis unnecessary, MongoDB sufficient |
| Plugin SDK | Stremio/Jellyfin style |
| Disable omdb/tvmaze/tvdb | Save refactoring time |
