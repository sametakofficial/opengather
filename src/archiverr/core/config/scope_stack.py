"""Scope stack for path-aware interpolation (WP-3).

A ``ScopeStack`` carries the aliases visible at each level as the
interpolator walks a config tree.  Frames are pushed when a mapping
declares its own ``aliases`` key; inner frames shadow outer ones.

Per ``datasets/10-aliases.yml``:

* ``root``       - ``aliases`` at config top-level, visible everywhere.
* ``subtree``    - ``aliases`` under any mapping, visible in that mapping
                   and its descendants; shadows outer.
* ``manifest``   - ``aliases`` inside a plugin manifest, visible in that
                   manifest's merged config branch only.

The stack also tracks the absolute path of the node currently being
resolved so ``${.field}`` and ``${..field}`` can locate siblings and
parents in the tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScopeFrame:
    """A single scope layer.

    ``path`` is the absolute dotted path of the mapping that declared
    the frame (``()`` for root).  ``aliases`` is the alias map local to
    this layer - keys are alias names, values are whatever the config
    wrote (typically a string like ``"${config.plugin.tmdb.data}"``).
    """

    path: tuple[str, ...]
    aliases: dict[str, Any] = field(default_factory=dict)


class ScopeStack:
    """LIFO of scope frames with alias lookup walking inner → outer.

    Pushing a frame whose ``aliases`` is empty is a no-op for resolution
    but still required to anchor ``path`` for relative lookups; callers
    push one frame per mapping they enter so ``current_path`` always
    reflects the node being walked.
    """

    def __init__(self) -> None:
        self._frames: list[ScopeFrame] = []

    def push(self, frame: ScopeFrame) -> None:
        self._frames.append(frame)

    def pop(self) -> ScopeFrame:
        return self._frames.pop()

    def __len__(self) -> int:
        return len(self._frames)

    @property
    def depth(self) -> int:
        return len(self._frames)

    def current_path(self) -> tuple[str, ...]:
        """Absolute path of the innermost frame, ``()`` if empty."""
        return self._frames[-1].path if self._frames else ()

    def parent_path(self) -> tuple[str, ...]:
        """Absolute path of the parent of the innermost frame.

        For the root frame and an empty stack this is ``()``.
        """
        path = self.current_path()
        return path[:-1] if path else ()

    def resolve_alias(self, name: str) -> Any | None:
        """Walk frames from innermost outwards; first hit wins.

        Returns ``None`` when the alias is not declared in any visible
        frame - callers decide whether that is a hard error.
        """
        for frame in reversed(self._frames):
            if name in frame.aliases:
                return frame.aliases[name]
        return None

    def visible_aliases(self) -> dict[str, Any]:
        """Flatten visible aliases with inner frames winning."""
        merged: dict[str, Any] = {}
        for frame in self._frames:
            merged.update(frame.aliases)
        return merged
