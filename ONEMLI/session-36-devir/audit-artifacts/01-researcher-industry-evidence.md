# Agent Response | session:ef30ac79 | agent:architecture-researcher | agent_id:aff7427226776d6b8 | seq:26 | 2026-04-30 01:53:46
# transcript: /home/samet/.claude/projects/-home-samet-Workspace-bedrock-bedrock-Tasarilar-archiverr/ef30ac79-18cf-4997-9bfa-f1382bd1099b/subagents/agent-aff7427226776d6b8.jsonl

I have all the evidence I need. Now I'll synthesize the verdict.

---

## EXEC SUMMARY (5 lines)

1. **Audit decision M1 (event handler garbage upsert) — VERDICT DELETE/FIX, audit was right.** The bug is real (`id=""` filter shape mismatch), and what was lost (job/plugin completion event recording) is the wrong layer for an audit trail. AGENT.md §"Safety beats convenience" + "no silent failures" + Current Weakness #5 (no retry/timeout policy yet) — this code is not "audit log asset", it is a partial-overwrite write path that fights the canonical writer.
2. **Audit decision M4 (save_plugin_result/update_plugin_result/save_plugin_data dead chain) — VERDICT DELETE the chain, but KEEP `plugin_executions` writes.** AGENT.md explicitly says "Avoid backwards-compatible magic, signature introspection, dict fallbacks". A `hasattr` guard returning silent `False` is exactly that anti-pattern. Recovery does not need these — `plugin_executions` (already wired) is the slim recovery surface per `11-recovery.yml`.
3. **Audit decision P2/M14 (3-tier plugin storage = waste) — VERDICT PARTIAL CHALLENGE. Real industry pattern is 2-tier, not 3.** `jobs.plugins` embedded (hot path) + `plugins` collection (separate per-plugin-per-job rows for unbounded growth and cross-run query) is the canonical workflow-core / MongoDB-recommended pattern. `plugin_docs` is the third copy that has zero readers — that one is genuinely waste. Audit's "triple copy garbage" framing was 2/3 right, 1/3 wrong: keep both `jobs.plugins` AND `plugins`; drop `plugin_docs`.
4. **Bigger picture:** Archiverr is at three-strikes step 1 of AGENT.md (proving the media metadata recipe). Adding event-store/CQRS/audit-log infrastructure now is exactly what AGENT.md "What Not To Do" §1 forbids. Slim contract is correct.
5. **Above the line items the audit got right; below it items it overshot:** correct = M1 fix, M2 dead indexes, M3 datasets sync, M5 name drift, drop `plugin_docs`. Overshot/risky = M4 unconditional delete (some methods deserve to stay as protocol stubs for `plugin_executions` future-work fields), and the framing of `plugins` collection as "duplicate".

---

## A) MongoDB document model — orchestration evidence

**Pattern 1 — workflow-core (danielgerlag, ~5k stars, .NET).** MongoDB persistence: `wfc.workflows`, `wfc.subscriptions`, `wfc.events`, `wfc.execution_errors`, `wfc.scheduled_commands`. `ExecutionPointers` (per-step state) are **embedded inside** `WorkflowInstance`. Errors are split into a separate collection. **Both** workflow status and per-step status coexist (intentional duplication, not waste).
Source: [MongoPersistenceProvider.cs](https://github.com/danielgerlag/workflow-core/blob/master/src/providers/WorkflowCore.Persistence.MongoDB/Services/MongoPersistenceProvider.cs)

**Pattern 2 — Temporal.** Event-sourced append-only log; full event history is the source of truth, separate from current-state snapshot. This is the heaviest pattern; Temporal earns it because it offers durable replay across days/weeks. Archiverr does not need this.
Source: [Temporal Event History](https://docs.temporal.io/encyclopedia/event-history)

**Pattern 3 — Kestra.** Three-layer split: Queue (Kafka/JDBC) for execution metadata flow, Repository (Elasticsearch/JDBC) for queryable history, Internal Storage for blob artifacts. Multi-store separation is the lesson, not "embed everything in one doc".
Source: [Kestra Data Components](https://kestra.io/docs/architecture/data-components), [Kestra Storage](https://kestra.io/docs/concepts/storage)

**Pattern 4 — MongoDB official guidance.** "Embed N-side if cardinality is one-to-few and child is not accessed outside parent." "Reference when relationship is unbounded, queried independently, or grows large." Plugin runs per job are bounded (~5–10), so embedding in `jobs.plugins` is fine. Per-plugin per-run statistics across many runs is unbounded → separate `plugins` collection is correct.
Source: [6 Rules of Thumb for MongoDB Schema Design](https://www.mongodb.com/blog/post/6-rules-of-thumb-for-mongodb-schema-design), [Embedding vs References](https://www.mongodb.com/docs/manual/data-modeling/concepts/embedding-vs-references/)

**Pattern 5 — Extended Reference Pattern.** Storing a small subset of related fields inside the parent document for read performance, while full data lives in separate collection, is documented MongoDB practice — NOT waste. This validates having `jobs.plugins` (extended ref) + `plugins` collection (full).
Source: [Extended Reference Pattern](https://www.mongodb.com/company/blog/building-with-patterns-the-extended-reference-pattern)

**Verdict for Archiverr:**
- `jobs.plugins` embedded: **hot path read** for orchestrator + UI, bounded by jobs config → KEEP (extended-reference pattern).
- `plugins` collection: **unbounded cross-run analytics surface**, "show me last 50 tmdb runs" query → KEEP (proper one-to-many reference).
- `plugin_docs`: zero API readers, zero plugin readers, written by `plugin_data_manager` only → DROP. This is the only true duplicate; not even a denormalization-for-reads (since nobody reads it).

---

## B) FastAPI + Mongo integration — modern stack

**Repository pattern + Beanie ODM is the dominant modern pattern.** TestDriven.io's reference (March 2025) and MongoDB's own developer docs both layer: config / models (Beanie Documents) / repositories / routes / schemas (Pydantic DTOs) / services. Beanie is async via Motor and Pydantic-native.
Sources: [TestDriven.io FastAPI+Beanie](https://testdriven.io/blog/fastapi-beanie/), [MongoDB FastAPI best practices](https://www.mongodb.com/developer/products/mongodb/8-fastapi-mongodb-best-practices/), [MongoDB FastAPI tutorial](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/integrations/fastapi-integration/)

**However** — for Archiverr, **adopting Beanie now is over-engineering**. AGENT.md §"Engineering Taste": "Complexity is allowed only when earned by a current requirement." The current requirement is "API can read runs/jobs/plugins"; direct PyMongo + a thin `pymongo_persistence.py` interface is fine. Beanie/ODM is earned only when (a) plugin authors write Mongo-aware code, or (b) the team grows beyond solo. Neither is true (per `kritik-bulgular.md` open question 1).

**SSE for live run progress:** FastAPI has first-class SSE support; the standard pattern is `EventSourceResponse` + a Redis pub/sub or in-memory queue between worker and API. For Archiverr's single-orchestrator slim contract, an in-memory event bus + SSE endpoint is sufficient.
Source: [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

**Schema versioning:** MongoDB's official "Schema Versioning Pattern" (add `schema_version` field, lazy-migrate on read) is the YAGNI-compatible approach. Archiverr's docs do not currently use it; adding the field defensively now costs ~5 lines and pays back the first time a `JobState.to_dict()` shape changes.
Source: [Schema Versioning Pattern](https://www.mongodb.com/blog/post/building-with-patterns-the-schema-versioning-pattern)

**Verdict for AGENT.md compatibility:**
- Direct PyMongo + repository thin layer: aligned with "no unnecessary abstractions".
- Beanie now: violates "complexity earned by current requirement" — defer until plugin SDK matures.
- SSE for run progress: aligned (real progress events, single-orchestrator scope).
- `schema_version` field: cheap, defensive, aligned.

---

## C) Audit decisions — challenged with evidence

### M1 (orchestrator.py:382-418 event handler) — VERDICT: DELETE/FIX, audit was right

**Evidence:**
- `pymongo_persistence.py:206 save_job` filter shape is `{"id": <value>}`. Handler sends `{"job_id": ..., "run_id": ..., "stage": ..., "status": ...}` → filter resolves to `{"id": ""}` → `upsert=True` writes a garbage doc with `id=""`. This is not "audit logging" — it is a parallel write path that creates non-readable docs.
- Real audit-trail patterns ([Arnaud LEMAIRE](https://medium.com/sundaytech/event-sourcing-audit-logs-and-event-logs-deb8f3c54663), [Kurrent](https://www.kurrent.io/blog/event-sourcing-audit)) recommend **dedicated** audit/events collection (capped or TTL'd), not partial-overwrite of business documents.
- AGENT.md §"What Not To Do": "Add stages without a domain reason." Audit-log infrastructure was added without a domain reason (zero readers).
- AGENT.md §"Current Weaknesses" #5: "No mature retry/timeout/failure-policy model yet" — the right layer for execution lifecycle events is `plugin_executions`, which is already wired.

**Action:** Delete the handler. If audit trail is a real future need, it goes into a dedicated `events` collection (capped or TTL), not into `save_job`/`save_plugin`.

### M4 (save_plugin_result, update_plugin_result, save_plugin_data) — VERDICT: DELETE 2 of 3, KEEP-AS-INTERFACE 0 of 3

**Evidence:**
- `save_plugin_result` is silently dropped via `hasattr` guard. AGENT.md §4: "Avoid backwards-compatible magic, signature introspection, dict fallbacks, or 'accept anything' adapters. They make the runtime harder to reason about." This is exactly that. **DELETE.**
- `update_plugin_result` has 0 runtime callers (per audit grep). Slim recovery in `11-recovery.yml` does not need it — startup-scan-and-mark-crashed model is the contract. **DELETE.**
- `save_plugin_data` has 0 plugin callers. **DELETE.**
- **Counter-evidence I considered:** Workflow-core, Prefect, Temporal all have richer plugin/task lifecycle hooks. But those systems earn it via real distributed execution. AGENT.md §A5/A6 (`kritik-bulgular.md`): lease/heartbeat/checkpoint deferred *intentionally*; slim contract is the explicit choice. Restoring these methods now violates the slim contract that was just earned.
- **The real future hook is `plugin_executions`**, which already exists and is wired (`stage_executor.py:402`, `orchestrator.py:494`). That is the recovery surface. The three dead methods are not a recovery surface — they are unfinished alternative APIs from earlier sessions.

**Action:** Delete all three. The recovery future-work fields (`claimed_at`, `lease_expires_at`, `idempotency_key`, `output_fingerprint`) belong on `plugin_executions`, where `11-recovery.yml#out_of_scope` already documents them. There is no reason to keep `save_plugin_result` as a "sleeper".

### P2/M14 (plugins vs plugin_docs vs jobs.plugins triple copy) — VERDICT: SPLIT VERDICT

**Evidence — keep `jobs.plugins` embedded:**
- workflow-core embeds `ExecutionPointers` inside `WorkflowInstance`. Same shape decision.
- Plugin count per job is bounded (manifest list, ~5–10). Embedding bounded one-to-few is canonical MongoDB design ([6 Rules of Thumb](https://www.mongodb.com/blog/post/6-rules-of-thumb-for-mongodb-schema-design)).
- Hot path: orchestrator runtime read needs full job doc with plugin state. Single round-trip wins.

**Evidence — keep `plugins` collection:**
- Cross-run analytics ("last 50 tmdb runs", "plugin success rate") is unbounded one-to-many. MongoDB official guidance: separate collection.
- workflow-core also splits `wfc.execution_errors` for the same reason.
- Indexable on `(job_id, plugin_name)` unique + `run_id` + `job_id` — exactly what cross-run dashboard queries need.
- This is the **Extended Reference pattern**, not duplication.

**Evidence — drop `plugin_docs`:**
- API readers: 0 (audit grep). Plugin readers: 0. Only `pymongo_persistence.get_plugin_doc` reads it, and that has 0 callers per audit.
- A denormalization-for-reads with no readers is not denormalization, it is dead write amplification.
- `_id` heterogeneity (run_id OR job_id) is a code smell: one document type cannot have two distinct identifier semantics. AGENT.md §"Decision Rule: Core or Plugin?": "Core owns invariants" — heterogenous `_id` violates the invariant.

**Action:** 2-tier (jobs.plugins embedded + plugins collection) is the industry pattern. Drop `plugin_docs`. Audit's "triple copy garbage" framing was directionally right but used the wrong reasoning — the issue is not that 3 copies is always bad, it is that the 3rd copy has zero readers.

### Other audit verdicts (one-line each)

- **M2 (dead indexes / `_create_indexes` cleanup)** — KEEP audit verdict. Dead indexes are pure cost.
- **M3 (datasets sync `plugin_docs`/`diagnostics`)** — Moot once `plugin_docs` is dropped; only `diagnostics` decision (E6) needs sync.
- **M5 (`started_at` vs `created_at` drift)** — KEEP audit verdict (K5). Trivial naming fix; align code to schema (`started_at` is more accurate semantics for execution rows).
- **F6 / M9 (legacy executions/matches/plugin_results readers)** — KEEP audit verdict. Migration debt, no domain value.
- **K9 / M10 (RunRepository stubs)** — KEEP audit verdict. AGENT.md §"no speculative extension points".
- **E6 / M12 (DiagnosticsLogger unwired)** — Decide: wire it OR delete. AGENT.md §"no defensive try/catch around impossible paths" + Current Weakness #5: a logger nobody connected to is dead code, even with good intentions. Recommend delete unless there is a specific operator pain it solves *today*.
- **E1/K6 (per_run plugins not in `plugin_executions`)** — Wire them. Recovery scan is the only invariant `plugin_executions` is supposed to cover; if a per_run plugin can crash the run, it must be in the scan surface. Cheap fix, big consistency win.
- **M13/A4 (audit/event log Mongo writes)** — DEFER. AGENT.md §"What Not To Do" #1. Slim contract chose not to. Re-evaluate only when an operator complains about a real forensic gap.
- **M15/A5/A6 (multi-orchestrator lease/heartbeat)** — DEFER per `kritik-bulgular.md` open question 2. Single-orchestrator-per-Mongo is the explicit contract.

---

## D) Proposed MongoDB + FastAPI plan skeleton (AGENT.md-compatible)

1. **Persistence collections (canonical, 4):** `runs`, `jobs`, `plugins`, `plugin_executions`. Drop `plugin_docs`. Defer `checkpoints`, `events` (audit log), `diagnostics` until earned.
2. **Index hygiene:** Merge `_create_indexes` + `_create_new_indexes` into one method. Drop dead indexes (`runs.started_at` top-level, `lease_expires_at`, `idempotency_key` for slim contract).
3. **Embedded vs reference rule (codified):** Per-job plugin run state lives embedded in `jobs.plugins` (extended-reference, hot read). Cross-run plugin queries hit the `plugins` collection. No third tier.
4. **Schema versioning field:** Add `schema_version: int` (default 1) to `runs`, `jobs`, `plugins`, `plugin_executions`. Lazy-migrate at read time. ~5 lines, defensive against future shape changes.
5. **Direct PyMongo + thin repository layer:** Keep `pymongo_persistence.py` as the only Mongo touchpoint. Defer Beanie/ODM until plugin SDK or third-party plugin authors arrive. Repository pattern OK; ODM not yet earned.
6. **API DTOs separate from Mongo docs:** Pydantic v2 response models (`api/v1/.../schemas.py`) are not the same class as in-memory state (`RunState`, `JobState`). One translation seam at the router; audit's "duplicate router" finding (B3 in `kritik-bulgular.md`) gets resolved by picking `api/v1/runs/` canonical.
7. **Recovery surface = `plugin_executions` only:** Per-run plugins also write here (E1/K6 fix). All three dead `save_plugin_*` methods deleted.
8. **Event handler (orchestrator.py:382-418):** Deleted. Run/job/plugin lifecycle is recorded via the canonical writers (`save_run`, `save_job`, `save_plugin`, `save_plugin_execution`), not via parallel event handlers.
9. **SSE for live run progress (when needed):** FastAPI `EventSourceResponse` reading from an in-process pub/sub keyed by run_id. Defer until UI exists.
10. **Future-work fields stay documented in `11-recovery.yml#out_of_scope`** — `claimed_at`, `lease_expires_at`, `idempotency_key`, `output_fingerprint`, `checkpoints` collection. These are not deleted from docs; they are simply not implemented. AGENT.md §"explicit retry policy, execution history" stays a learn-from-Temporal pointer, not a copy-from-Temporal mandate.

---

## E) AGENT.md deviations / risks in this plan

1. **Adding `schema_version` is a small speculative extension point** — borderline against §"no speculative extension points". Justification: MongoDB official pattern; cost is 5 lines per shape; payback is the first migration. Acceptable.
2. **Keeping `plugins` collection** could be argued as "not earned" if there is no analytics dashboard yet. Counter-justification: workflow-core, Kestra, MongoDB official guidance all use the same separation; cost is already paid (collection exists, indexes exist, writes are wired). The override would be deleting it, not keeping it.
3. **Dropping `plugin_docs` is irreversible without git history** — by AGENT.md and global no-delete policy, this means `mkdir -p .deleted && mv` for any file work, plus a one-shot Mongo migration that drops the collection on a backup, not on prod.
4. **Slim recovery contract is a deliberate AGENT.md deviation from Temporal-grade durability.** This must be re-stated in `11-recovery.yml` so future contributors do not fight the design (it already is).
5. **Deleting dead `save_plugin_*` APIs is correct per AGENT.md** but a contributor in the future might re-add similar methods thinking they are missing infrastructure. Mitigation: a one-line comment in `interface.py` saying "plugin lifecycle = `save_plugin_execution` only; do not add per-result CRUD".
6. **Risk of overshoot on M4:** if `update_plugin_result` semantics are needed later (e.g. plugin emits intermediate progress to surface), we will rebuild it on `plugin_executions` rows, not on the deleted three-method chain. That is a re-add cost, not a regression.
7. **API SSE recommendation is speculative** — there is no UI today. Including it in the plan only as a sketch; it is not on the implementation list until a UI consumer exists.

---

## Files referenced (absolute paths)

- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/AGENT.md
- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/ONEMLI/mongodb-audit.md
- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/ONEMLI/kritik-bulgular.md
- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/datasets/06-mongodb.yml
- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/datasets/03-run-state.yml
- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/datasets/09-api-fastapi.yml
- /home/samet/Workspace/bedrock/bedrock/Tasarilar/archiverr/codebase/archiverr/datasets/11-recovery.yml

## Sources

- [workflow-core MongoPersistenceProvider.cs](https://github.com/danielgerlag/workflow-core/blob/master/src/providers/WorkflowCore.Persistence.MongoDB/Services/MongoPersistenceProvider.cs)
- [MongoDB 6 Rules of Thumb for Schema Design](https://www.mongodb.com/blog/post/6-rules-of-thumb-for-mongodb-schema-design)
- [MongoDB Embedding vs References](https://www.mongodb.com/docs/manual/data-modeling/concepts/embedding-vs-references/)
- [MongoDB Extended Reference Pattern](https://www.mongodb.com/company/blog/building-with-patterns-the-extended-reference-pattern)
- [MongoDB Schema Versioning Pattern](https://www.mongodb.com/blog/post/building-with-patterns-the-schema-versioning-pattern)
- [MongoDB Capped Collections](https://www.mongodb.com/docs/manual/core/capped-collections/)
- [Temporal Event History](https://docs.temporal.io/encyclopedia/event-history)
- [Temporal Event Sourcing implementation](https://www.mintlify.com/temporalio/temporal/architecture/event-sourcing)
- [Kestra Architecture](https://kestra.io/docs/architecture)
- [Kestra Data Components](https://kestra.io/docs/architecture/data-components)
- [Kestra Storage](https://kestra.io/docs/concepts/storage)
- [Prefect States documentation](https://docs.prefect.io/v3/concepts/states)
- [TestDriven.io — FastAPI + Beanie CRUD](https://testdriven.io/blog/fastapi-beanie/)
- [MongoDB — 8 FastAPI + Mongo best practices](https://www.mongodb.com/developer/products/mongodb/8-fastapi-mongodb-best-practices/)
- [FastAPI SSE tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [Event Sourcing vs Audit Logs (Kurrent)](https://www.kurrent.io/blog/event-sourcing-audit)
- [Event Sourcing, Audit Logs, Event Logs (Arnaud LEMAIRE)](https://medium.com/sundaytech/event-sourcing-audit-logs-and-event-logs-deb8f3c54663)
- [Is the audit log a proper architecture driver for Event Sourcing? (event-driven.io)](https://event-driven.io/en/audit_log_event_sourcing/)
