"""E2E: ``safe_copy`` must honour ``dry_run`` without touching disk.

Session 34 WP-5 routes every fs write through ``archiverr.core.safety``.
Guards:

* ``dry_run=True``  → returns ``PlannedOperation(op='skip', executed=False)``,
  target file does not appear on disk.
* ``dry_run=False`` → copies the bytes.
"""

from pathlib import Path

from archiverr.core.safety import safe_copy


def test_dry_run_does_not_write(tmp_path: Path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"hello")
    dst = tmp_path / "out" / "dst.bin"

    planned = safe_copy(str(src), str(dst), dry_run=True)

    assert planned.op == "skip"
    assert planned.executed is False
    assert planned.dry_run is True
    assert not dst.exists()


def test_non_dry_run_writes(tmp_path: Path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"payload")
    dst = tmp_path / "out" / "dst.bin"

    planned = safe_copy(str(src), str(dst), dry_run=False)

    assert planned.op in {"copy", "link"}
    assert planned.executed is True
    assert dst.exists()
    assert dst.read_bytes() == b"payload"


def test_missing_source_is_planned_error(tmp_path: Path):
    planned = safe_copy(str(tmp_path / "nope"), str(tmp_path / "out"), dry_run=False)
    assert planned.op == "error"
    assert planned.executed is False
