"""
Config module - Configuration management for Archiverr.

- Phase 6

Components:
- AliasResolver: Template context alias resolution
"""

from .alias_resolver import AliasResolver, create_alias_resolver

__all__ = ['AliasResolver', 'create_alias_resolver']
