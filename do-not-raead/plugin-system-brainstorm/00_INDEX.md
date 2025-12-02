# PLUGIN SYSTEM BRAINSTORM - INDEX

```yaml
date: 2025-12-02
status: final
type: index
```

---

## PURPOSE

This folder contains finalized, industry-researched specifications for the Archiverr plugin system. Each document follows the structure:

1. **Current State** - What exists now
2. **Proposed Changes** - What we're changing
3. **Industry Comparison** - How others do it
4. **Schema/Diagrams** - Visual specifications
5. **Implementation** - Code snippets

---

## DOCUMENTS

```
01_MANIFEST_SCHEMA.md       Manifest structure, stage/mode, migration
02_PROVIDES_SYSTEM.md       Capability taxonomy, requires/provides
03_STAGE_EXECUTION.md       4-stage model, parallel execution
04_EVENTBUS_AND_SERVICES.md PluginServices, event naming
05_CONFIG_SYSTEM.md         FlexGet-style config, env vars
06_STATE_MODEL.md           Run/Job terminology, dataclasses
07_IMPLEMENTATION_PLAN.md   Phases, file changes, rollback
```

---

## KEY DECISIONS

```
DECISION                    RATIONALE
--------------------------------------------------------------------
4-stage model               Clearer than 6-stage, matches flow
Generic provides            Not archiverr-specific, extensible
FlexGet-style config        Less verbose, industry standard
Run/Job terminology         Industry standard (Jenkins, Airflow)
PluginServices injection    Single access point, testable
Trust-based security        Python CLI standard (FlexGet, VSCode)
```

---

## TERMINOLOGY CHANGES

```
OLD                 NEW                 NOTES
--------------------------------------------------------------------
ExecutionState      Run                 Shorter
MatchState          Job                 Industry standard
execution_id        run_id              Consistent
match_index         job_index           Internal only
category            stage               Execution phase
depends_on          (removed)           Redundant with requires
expects             requires            Simpler
SDK                 PluginServices      Clearer purpose
batch               per_run             Clearer
```

---

## INDUSTRY SOURCES

```
Home Assistant      dependencies, after_dependencies
Grafana             dependencies.plugins
VSCode              extensionDependencies, contributes
pytest/pluggy       hookspec, hookimpl
FlexGet             flat config, plugin-as-config-key
```

---

## ESTIMATED EFFORT

```
Phase               Hours
--------------------------------------------------------------------
Foundation          4
Plugin System       6
Execution           4
Migration           2
--------------------------------------------------------------------
Total               16
```

---

## NEXT STEPS

1. Review all documents
2. Create feature branch
3. Implement Phase 1 (state models)
4. Run existing tests
5. Continue with remaining phases

---

**Status: FINAL - Ready for execution phase**
