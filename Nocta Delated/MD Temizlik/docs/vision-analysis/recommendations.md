# Recommendations -- What to Revive, Defer, or Kill

**Analyzed by:** Claude Opus 4.6 (1M context)
**Date:** April 10, 2026

---

## Guiding Principle

The Session 32 strategic plan nailed it:

> "Stop refactoring the framework. Start writing plugins that do interesting things."

These recommendations are filtered through that lens. Only ideas that either (a) fix real bugs, (b) reduce maintenance burden, or (c) make the plugin system more powerful for plugin authors are recommended.

---

## REVIVE -- Do These

### R1: Fix the 2 Confirmed Bugs (Session 32, ~40 min)
- **complete_job() never called** -- 1 line + 1 test. Run stats are always wrong.
- **Dual RUN_STARTED emission** -- 1 line delete + 1 test.
- **Source:** Session 32 strategic plan, all 6 agents agreed.
- **Why now:** These are real correctness bugs. They make the system untrustworthy.

### R2: Delete the ~909 LOC Dead Code (Session 32, ~60 min)
- StateServiceImpl (278 LOC), mongodb.py + motor.py (574 LOC), _topological_sort (20 LOC), check_expects (15 LOC), validate_dependencies (22 LOC)
- **Source:** Session 32 strategic plan, all agents agreed.
- **Why now:** Dead code confuses future developers (including AI agents analyzing the codebase). Zero risk removal.

### R3: CI/CD Pipeline (1 session, ~90 min)
- **Originally proposed:** Session 1 (Dec 2024) -- 16 months ago
- **Why it was forgotten:** Always lower priority than architectural work
- **Why revive now:** The project has 425 tests, ruff, mypy. All the pieces exist. A GitHub Actions workflow would take 30 minutes and prevent regression forever. The fact that tests were broken for 5 months (Sessions 15-27) proves CI is needed.
- **Minimal viable CI:**
  ```yaml
  on: [push]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.12' }
        - run: pip install -e ".[dev]"
        - run: ruff check src/
        - run: pytest tests/unit/ -v --ignore=tests/unit/api/
  ```
- **Effort:** LOW. Impact: HIGH (prevents the 5-month rot scenario).

### R4: Write a Novel Plugin (1-2 sessions)
- **Why:** The strategic plan's most important recommendation is "write plugins that do interesting things." The plugin system's power is only visible when plugins exercise it.
- **Ideas for plugins that would showcase the architecture:**
  1. **nfo-writer** -- Generate .nfo files for Kodi/Jellyfin/Emby from tmdb/tvdb data. Uses the template system, reads from multiple data plugins, writes files (exercising fs_lock). Immediately useful for home server users.
  2. **subtitle-finder** -- Search OpenSubtitles API by IMDB ID (from tmdb/omdb data). Exercises the requires/provides chain across stages.
  3. **duplicate-detector** -- Compare ffprobe data across jobs to find duplicate files. Would be the first plugin that reads across ALL jobs, exercising the plugins (all jobs) data access.
  4. **metadata-exporter** -- Export enriched metadata to JSON/CSV/NFO formats. Simple but immediately useful.
- **Relevance:** This is what makes the playground interesting. One well-built plugin demonstrates more value than 5 more refactoring sessions.

---

## REVIVE (LOW PRIORITY) -- Do When Energy/Need Exists

### R5: Migrate 3 Legacy Plugins (tvdb, tvmaze, omdb)
- **Source:** Session 31 brainstorm finding #4
- **What:** Migrate from execute(match_data) to execute(job, services) interface
- **Why:** Eliminates the remaining hasattr-based dispatch and inspect.signature hack
- **Effort:** MEDIUM (each plugin ~30 min)
- **When:** Next time any of these plugins need a bug fix or feature change. Don't do it standalone.

### R6: Declare ffprobe Dependency in Data Plugin Manifests
- **Source:** Session 31 brainstorm finding #6
- **What:** tmdb, tvdb, omdb all read ffprobe data without declaring requires
- **Why:** Currently works because stage ordering guarantees ffprobe runs first, but it's undeclared coupling
- **Effort:** LOW (3 manifest edits)
- **When:** When migrating legacy plugins (R5)

### R7: Data Contract Provides (Future Architecture)
- **Source:** Session 31 brainstorm, Option A
- **What:** Change provides from generic capabilities to data contracts: `provides: [data.movie, data.show]` instead of `provides: [http.request, state.update]`
- **Why:** Would enable true plugin decoupling. Tasker could require `provides.data.movie:completed` instead of `plugin.tmdb.data:success`, meaning any movie-data-providing plugin would satisfy the dependency.
- **Effort:** HIGH
- **When:** Only if the plugin count grows beyond 15+ or if the owner wants to explore plugin interchangeability as an architectural experiment
- **This is the most architecturally interesting forgotten idea.** It was proposed in Session 31 but classified as "over-engineering for 9 plugins." It becomes valuable if the plugin ecosystem grows.

### R8: The retry_failed Plugin Concept
- **Source:** planned_system_datasets.yml (Dec 2024)
- **What:** A plugin that waits for run completion, then creates new jobs for failed items
- **Why interesting:** It would be the first plugin that operates at the meta-level -- acting on run results rather than individual files. This would exercise the provides.*:completed trigger syntax and the create_job() capability.
- **Effort:** MEDIUM
- **When:** After at least one novel plugin (R4) exists. This is a "power user" plugin.

---

## DEFER -- Good Ideas, Not Now

### R9: MongoDB Backend Wiring
- **Source:** Every session since Session 12
- **Reality:** pymongo_persistence.py exists. docker-compose.yml exists. Interface exists. But: nobody uses the API, the CLI works fine without persistence, and the strategic plan says "only if someone uses the API."
- **When:** When there's an actual use case for querying historical runs (e.g., a real user, or the owner wants to analyze processing patterns).

### R10: FastAPI Live Connection
- **Source:** Sessions 12+
- **Reality:** 15 files, ~2500 LOC of API code. All disconnected. process_executor.py expects old format.
- **When:** When MongoDB is wired (R9) and there's a reason to expose the API.

### R11: Plugin Status Timeout
- **Source:** planned_system_datasets.yml manifest design
- **What:** status_reporting.timeout_ms -- auto-fail plugins that hang
- **When:** When a plugin actually hangs and causes problems. YAGNI until then.

### R12: Reactive Plugins
- **Source:** AI/DATASETS.md manifest definition
- **What:** Plugins that react to events rather than running in pipeline stages
- **When:** When the event system is heavily used and there's a plugin that needs to react to events from other plugins. Currently the event system is underutilized.

---

## KILL -- Don't Do These

### K1: Web UI
- **Source:** Old progress.md
- **Why kill:** No users. The strategic plan explicitly says "KILL." A CLI tool doesn't need a web UI.

### K2: Plugin Marketplace
- **Source:** Old progress.md "Advanced Features"
- **Why kill:** 9 plugins, 1 developer. A marketplace solves a problem that doesn't exist.

### K3: Plugin Hot-Reloading
- **Source:** Old progress.md "Advanced Features"
- **Why kill:** The development loop is already fast (pytest runs in seconds). Hot-reload is only valuable for long-running server processes.

### K4: Loguru Migration
- **Source:** Session 1 action items
- **Why kill:** The custom Debugger works. It's been in the codebase for 31 sessions. The effort-to-benefit ratio is poor. Standard Python logging would be fine but isn't worth migrating to either.

### K5: file-reader -> file_reader Rename
- **Source:** Session 1 action items
- **Why kill:** It's been 16 months since this was proposed. The hyphenated name works. Renaming it now would break git history, require config.yml changes, and provide zero functional benefit.

### K6: Documentation Suite
- **Source:** Session 1 action items
- **Why kill (for now):** No external users. The memory-bank, HANDOFF.md, and CLAUDE.md serve the development workflow. User documentation is valuable only when there are users. If the owner decides to publicize the project, write docs then.

### K7: Full Repository Pattern for DB
- **Source:** Session 1 action items (Priority 4, 3 months)
- **Why kill:** pymongo_persistence.py already implements the persistence interface. A full repository pattern with abstract base classes is over-engineering for a CLI tool with one storage backend.

---

## Priority Matrix

```
                    HIGH IMPACT
                        |
         R1 (bugs)      |     R4 (novel plugin)
         R2 (dead code)  |
         R3 (CI/CD)      |
    LOW ─────────────────+───────────────────── HIGH
    EFFORT               |                     EFFORT
                         |
         R6 (ffprobe)    |     R7 (data contracts)
         R5 (legacy)     |     R8 (retry plugin)
                         |     R9 (MongoDB)
                         |
                    LOW IMPACT
```

## Recommended Session Order

**Session 32 (Next):**
1. R1: Fix 2 bugs (40 min)
2. R2: Delete dead code (60 min)
3. R3: Set up CI/CD (30 min)

**Session 33:**
4. R4: Write one novel plugin (nfo-writer recommended) -- the entire session

**Session 34 (only if motivated):**
5. R5 + R6: Migrate legacy plugins + declare ffprobe deps

**Session 35+ (only if the plugin ecosystem grows):**
6. R7: Data contract provides
7. R8: retry_failed meta-plugin

---

## The One Thing

If the owner does nothing else from this analysis, do **R4: write a novel plugin**.

The architecture is solid. The guard test protects it. The protocols define the contract. The dependency resolver orders execution. The provides registry tracks completion. All of this infrastructure exists to make plugins powerful.

But the most complex plugin in the system is tasker, which is basically "render Jinja2 templates." The plugin system can do much more. A plugin that:
- Reads data from multiple other plugins (exercising requires)
- Writes files (exercising fs_lock and provides)
- Uses the template system for output formatting
- Does something no other media tool does

...would demonstrate the entire system's value in one concrete artifact.
