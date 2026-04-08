# Product Context

## Problem

Media collections grow chaotic. Files have inconsistent names, scattered metadata, no organization system. Manual renaming doesn't scale. Existing tools (FileBot, Sonarr) are either paid, limited to specific use cases, or don't support plugin-based extensibility.

## Solution

Archiverr is a plugin-based pipeline that:
1. Scans media files (scanner/file-reader)
2. Parses filenames to extract title/year/season/episode (renamer)
3. Fetches metadata from 4 APIs simultaneously (tmdb/tvdb/tvmaze/omdb)
4. Outputs results via configurable Jinja2 templates (tasker)

## User Flow

```
Configure (config.yml) -> Dry-run (safe preview) -> Review -> Execute
```

## Target Users

- Media archivists with large collections
- Home server admins (Plex/Jellyfin/Emby)
- Developers building media automation
- Power users needing extensible metadata pipelines

## Differentiators

| Feature | Archiverr | FileBot | Sonarr |
|---------|-----------|---------|--------|
| Multi-API | 4 APIs + ffprobe | 1 API | 1 API |
| Plugin system | Yes (manifest-based) | No | No |
| Template engine | Full Jinja2 | Limited | Limited |
| Dry-run safety | Default on | Manual | No |
| Extensible | Add plugins without core changes | No | Plugins but tightly coupled |
| Cost | Free/Open source | Paid | Free |
