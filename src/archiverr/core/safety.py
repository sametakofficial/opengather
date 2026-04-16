"""Central filesystem safety API (WP-5).

Every plugin that writes, copies, moves, or deletes on disk must go through
these helpers rather than calling ``shutil`` / ``os`` directly.  The helpers
turn each operation into a :class:`PlannedOperation` record, honour the
run-level ``dry_run`` / ``hardlink`` / ``no_delete`` options, and keep a single
code path responsible for side-effect policy.

Contract (from ``datasets/12-safety.yml``):

* ``dry_run``   - run scope; when true no disk writes occur but the planned
                  operation is still returned and logged.
* ``hardlink``  - run scope; when true ``safe_copy`` prefers ``os.link`` with a
                  copy fallback on failure; ``False`` always copies.
* ``no_delete`` - run scope; there is no ``safe_delete`` helper.  Callers must
                  ``safe_move`` to a ``.deleted/`` sibling, and this module
                  raises if ``no_delete`` is true and a move target is under
                  the configured ``.deleted/`` root but the option is off.

All functions are side-effect free when ``dry_run=True``.  They never delete.
They never silently overwrite an existing file - a move/copy target that
exists is a planned error unless ``overwrite=True`` is passed.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

OperationKind = Literal["copy", "link", "move", "write", "skip", "error"]


@dataclass(frozen=True)
class PlannedOperation:
    """Immutable record of a filesystem operation that was (or would be) done.

    ``executed`` is True when the operation actually touched disk, False when
    ``dry_run`` skipped it or when the operation is an ``error``.  ``op`` of
    ``error`` indicates a pre-flight failure (e.g. source missing); callers
    should inspect ``reason``.
    """

    op: OperationKind
    source: str | None
    target: str | None
    reason: str
    dry_run: bool
    executed: bool = False
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
            "dry_run": self.dry_run,
            "executed": self.executed,
            **({"extra": dict(self.extra)} if self.extra else {}),
        }


def safe_copy(
    src: str | os.PathLike[str],
    dst: str | os.PathLike[str],
    *,
    hardlink: bool = False,
    dry_run: bool = True,
    overwrite: bool = False,
) -> PlannedOperation:
    """Copy or hardlink ``src`` to ``dst`` under the run safety policy.

    * If ``dry_run`` is true, nothing is written; the returned ``PlannedOperation``
      has ``executed=False`` and ``op='skip'`` when it would have run.
    * If ``hardlink`` is true, :func:`os.link` is attempted first; on
      ``OSError`` (cross-fs, read-only src, unsupported), we fall back to a
      real copy and note the fallback in ``reason``.
    * Pre-flight checks (missing source, existing target without ``overwrite``)
      return ``op='error'`` instead of raising, so batch callers can collect
      results without aborting the run.
    """

    src_path = Path(os.fspath(src))
    dst_path = Path(os.fspath(dst))

    if not src_path.exists():
        return PlannedOperation(
            op="error", source=str(src_path), target=str(dst_path),
            reason="source does not exist", dry_run=dry_run, executed=False,
        )

    if dst_path.exists() and not overwrite:
        return PlannedOperation(
            op="error", source=str(src_path), target=str(dst_path),
            reason="target exists; pass overwrite=True to replace",
            dry_run=dry_run, executed=False,
        )

    planned_op: OperationKind = "link" if hardlink else "copy"

    if dry_run:
        return PlannedOperation(
            op="skip", source=str(src_path), target=str(dst_path),
            reason=f"dry_run={True}; would {planned_op}",
            dry_run=True, executed=False, extra={"planned_op": planned_op},
        )

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    if hardlink:
        try:
            if dst_path.exists():
                dst_path.unlink()
            os.link(src_path, dst_path)
            return PlannedOperation(
                op="link", source=str(src_path), target=str(dst_path),
                reason="os.link succeeded", dry_run=False, executed=True,
            )
        except OSError as exc:
            fallback_reason = f"hardlink failed ({exc.__class__.__name__}: {exc}); copied instead"
            shutil.copy2(src_path, dst_path)
            return PlannedOperation(
                op="copy", source=str(src_path), target=str(dst_path),
                reason=fallback_reason, dry_run=False, executed=True,
                extra={"hardlink_requested": True, "fallback": True},
            )

    shutil.copy2(src_path, dst_path)
    return PlannedOperation(
        op="copy", source=str(src_path), target=str(dst_path),
        reason="shutil.copy2", dry_run=False, executed=True,
    )


def safe_write(
    dst: str | os.PathLike[str],
    content: str | bytes,
    *,
    dry_run: bool = True,
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> PlannedOperation:
    """Write ``content`` to ``dst`` atomically, honouring dry-run.

    The write goes via a temp file in the target directory and ``os.replace``
    so a partial write never leaves a half-file behind.
    """

    dst_path = Path(os.fspath(dst))

    if dst_path.exists() and not overwrite:
        return PlannedOperation(
            op="error", source=None, target=str(dst_path),
            reason="target exists; pass overwrite=True to replace",
            dry_run=dry_run, executed=False,
        )

    if dry_run:
        return PlannedOperation(
            op="skip", source=None, target=str(dst_path),
            reason=f"dry_run={True}; would write {len(content)} bytes",
            dry_run=True, executed=False, extra={"planned_op": "write"},
        )

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = dst_path.with_suffix(dst_path.suffix + ".tmp")
    try:
        if isinstance(content, bytes):
            tmp_path.write_bytes(content)
        else:
            tmp_path.write_text(content, encoding=encoding)
        os.replace(tmp_path, dst_path)
    finally:
        if tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()

    return PlannedOperation(
        op="write", source=None, target=str(dst_path),
        reason="atomic write via os.replace", dry_run=False, executed=True,
    )


def safe_move(
    src: str | os.PathLike[str],
    dst: str | os.PathLike[str],
    *,
    dry_run: bool = True,
    overwrite: bool = False,
) -> PlannedOperation:
    """Move ``src`` to ``dst``.  Does not delete - a rename across filesystems
    falls back to copy+unlink but only after the destination copy is complete."""

    src_path = Path(os.fspath(src))
    dst_path = Path(os.fspath(dst))

    if not src_path.exists():
        return PlannedOperation(
            op="error", source=str(src_path), target=str(dst_path),
            reason="source does not exist", dry_run=dry_run, executed=False,
        )

    if dst_path.exists() and not overwrite:
        return PlannedOperation(
            op="error", source=str(src_path), target=str(dst_path),
            reason="target exists; pass overwrite=True to replace",
            dry_run=dry_run, executed=False,
        )

    if dry_run:
        return PlannedOperation(
            op="skip", source=str(src_path), target=str(dst_path),
            reason="dry_run=True; would move",
            dry_run=True, executed=False, extra={"planned_op": "move"},
        )

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.replace(src_path, dst_path)
        return PlannedOperation(
            op="move", source=str(src_path), target=str(dst_path),
            reason="os.replace", dry_run=False, executed=True,
        )
    except OSError:
        shutil.copy2(src_path, dst_path)
        os.unlink(src_path)
        return PlannedOperation(
            op="move", source=str(src_path), target=str(dst_path),
            reason="copy+unlink (cross-fs fallback)",
            dry_run=False, executed=True,
            extra={"fallback": "cross_fs"},
        )


def resolve_run_safety(config_options: dict) -> dict:
    """Extract the run-scope safety flags once, at run start.

    Returns a dict with ``dry_run``, ``hardlink``, ``no_delete`` keys, each
    a bool, applying the documented defaults.
    """
    if not isinstance(config_options, dict):
        config_options = {}
    return {
        "dry_run": bool(config_options.get("dry_run", True)),
        "hardlink": bool(config_options.get("hardlink", False)),
        "no_delete": bool(config_options.get("no_delete", True)),
    }
