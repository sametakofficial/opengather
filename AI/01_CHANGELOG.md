# CHANGELOG

## Session 10 (2025-11-28) - Strategy COMPLETE 
- **Part 1**: Session 7-8-9 local analysis 
- **Part 2**: Online research (Stremio, Home Assistant, Pluggy) 
- **Part 3**: Executable plan created 
- **Decision**: manifest.yml (industry standard naming)
- **Decision**: Sadece TMDb üzerinde çalış (omdb, tvdb, tvmaze dokunma)
- **Decision**: aliases, capabilities, provides, hooks KALDIRILACAK (overengineering)
- **Created**: 1400+ line strategy document with code examples
- **Updated**: WORKFLOW.md, CURRENT_STATUS.md, TODO.md, CHANGELOG.md
- **Next**: Execution - 6 tasks, ~2 hours

## Session 7 (2025-11-28) - Strategy
- Analyzed codebase and industry standards
- Decision: Taskiq + MongoDB (not Redis)
- Decision: Plugin SDK (Stremio style)
- Found: EventBus singleton inconsistency
- Created: AI workflow system

## Session 6 (2025-11-27) - Execution
- StateManager singleton removed
- DI pattern implemented
- Tests updated (205 passing)

## Session 5 (2025-11-27) - Execution
- Annotated DI pattern for FastAPI
- pyproject.toml created (PEP 621)
- Bare except clauses fixed

## Session 4 (2025-11-27) - Execution
- Motor migrated to PyMongo AsyncMongoClient
- Plugin-agnostic fixes in state/manager.py

## Session 1-3 (2025-11-27) - Execution
- PyMongoPersistence created
- Test fixtures added
- Response builder refactored
