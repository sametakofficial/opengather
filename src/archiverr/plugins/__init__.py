"""
Plugins package.
All plugins (scanner, ffprobe, tmdb, etc.) live here.

Base classes are in core.plugins.sdk (or core.plugins).
Import:
    from archiverr.core.plugins import InputPlugin, OutputPlugin
"""
# Re-export from SDK for backward compatibility
from archiverr.core.plugins.sdk import BasePlugin, InputPlugin, OutputPlugin

__all__ = ['BasePlugin', 'InputPlugin', 'OutputPlugin']
