# AI WORKFLOW

## Chat Types

### Strategy Chat
- Analyzes codebase
- Researches industry standards
- Creates plans and decisions
- Output: `sessions/session_X_strategy.md`

### Execution Chat
- Reads strategy file
- Implements changes
- No decision making, only coding
- Output: `sessions/session_X_execution.md`

---

## File Structure

```
AI/
├── WORKFLOW.md          # This file (read first)
├── 01_CHANGELOG.md      # Version history
├── 02_TODO.md           # Current tasks
├── 03_ARCHITECTURE.md   # System design
└── sessions/
    ├── session_7_strategy.md
    ├── session_7_execution.md
    ├── session_8_strategy.md
    └── ...
```

---

## Session Flow

```
Strategy Chat (Session N)
    ↓
Creates: session_N_strategy.md
    ↓
Execution Chat (Session N)
    ↓
Reads: session_N_strategy.md
Implements code changes
Creates: session_N_execution.md
    ↓
Strategy Chat (Session N+1)
    ↓
Reviews execution, plans next
```

---

## Rules

### Strategy Chat Must:
1. Read `02_TODO.md` first
2. Read previous session files
3. Research before deciding
4. Write clear, actionable strategy
5. Update `01_CHANGELOG.md` and `02_TODO.md`

### Execution Chat Must:
1. Read strategy file ONLY
2. Implement exactly what strategy says
3. No new decisions
4. Document what was done in execution file
5. Run tests after changes

---

## Plugin Development Rules

### Active Plugins (Work with these):
- scanner
- file_reader
- renamer
- ffprobe
- tmdb

### Disabled Plugins (Ignore during refactoring):
- omdb
- tvmaze
- tvdb

Reason: Saves hours of redundant work. These 3 plugins follow same pattern as tmdb. Once core plugin system is stable, they can be updated in one batch.

---

## Commands

```bash
# Run tests
python -m pytest tests/ -v

# Run app
python -m archiverr

# Start API
uvicorn archiverr.api.main:app --reload
```

---

## Current Session

Latest: **Session 11** (STRATEGY FINAL)
- Strategy: `sessions/session_11_strategy/`
- Plugin Brainstorm: `sessions/session_11_strategy/plugin-system-brainstorm/` (8 files)
- Execution: (not started)
- Status: **READY FOR EXECUTION**

### Plugin System Brainstorm (NEW)
```
plugin-system-brainstorm/
  00_INDEX.md              # Overview
  01_MANIFEST_SCHEMA.md    # stage, mode, requires, provides, after
  02_PROVIDES_SYSTEM.md    # Islem bazli provides (http.response, fs.write)
  03_STAGE_EXECUTION.md    # 4 stage: input/parse/metadata/output
  04_PLUGIN_SERVICES.md    # Tek interface: PluginServices
  05_CONFIG_SYSTEM.md      # FlexGet style + !include
  06_STATE_MODEL.md        # JobState, RunState
  07_ALIAS_SYSTEM.md       # Template alias
  08_IMPLEMENTATION.md     # Execution plan
```

### Key Decisions
- provides = islem bazli (http.response, NOT metadata.movie)
- PluginServices = tek interface (no get_debugger())
- FlexGet style config (no plugins: wrapper)
- 4 stage: input, parse, metadata, output

### Tahmini sure: 19-28 saat (5 phase)

Previous: **Session 10** ✅
- Status: **COMPLETED** (~95% accurate)
- Summary: `sessions/session_10_summary.md`
- Done: TMDb PluginResult, emit_task(), manifest.yml, validators.py, 58 new tests

Previous: **Session 9** ⚠️
- Status: **PARTIALLY COMPLETED (~70%)**
- Done: Context-based logging, Lifecycle hooks, PLUGIN_SDK.md
- Fixed in Session 10: TMDb PluginResult, emit_task(), SDK tests

Previous: **Session 8** ⚠️
- Status: **PARTIALLY COMPLETED (~60%)**
- Done: SDK relocated (to core/plugins/sdk/), Pydantic manifest validation
- Fixed in Session 10: PluginResult used, emit_task called

Previous: **Session 7** ⚠️
- Status: **PARTIALLY COMPLETED (~50%)**
- Done: EventBus DI (partial), SDK files created, Workers skeleton
- NOT Done: No integration, no tests
