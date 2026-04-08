# Project Brief

## What Is Archiverr?

Plugin-based media metadata enrichment system. Scans media files, fetches metadata from multiple APIs (TMDb, TVDb, TVMaze, OMDb), parses filenames, and outputs structured results via Jinja2 templates.

## Core Architecture Rule

**Plugin-Agnostic Core**: The core system MUST NEVER reference plugin names or implementations. Zero tolerance. Plugins declare everything about themselves in `manifest.yml`. Core discovers, loads, and executes plugins generically.

## Pipeline

```
INPUT (per_run) -> PARSE (per_job) -> DATA (per_job) -> OUTPUT (per_job)
  scanner           renamer            tmdb/tvdb/...      tasker
  file-reader                          ffprobe
```

## Plugins (9 active)

| Plugin | Stage | Purpose |
|--------|-------|---------|
| scanner | input | Directory/file scanning |
| file-reader | input | Read targets from file |
| renamer | parse | Filename parsing (movie/show detection) |
| tmdb | data | The Movie Database API |
| tvdb | data | TheTVDB API (JWT auth) |
| tvmaze | data | TVmaze API |
| omdb | data | OMDb/IMDb API |
| ffprobe | data | Video/audio technical metadata |
| tasker | output | Print, save, conditional tasks |

## Non-Goals

Video transcoding, torrent clients, media playback, duplicate detection, plugin marketplace.

## Success Criteria (All Achieved)

- Process 100+ files without errors
- Clean plugin isolation (no cross-plugin imports)
- Template rendering <10ms per match
- Zero hardcoded plugin names in core
- Expects-based runtime validation
- Professional structured logging
