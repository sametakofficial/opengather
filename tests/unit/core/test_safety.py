"""Unit tests for core.safety (WP-5)."""

import os
from pathlib import Path

import pytest

from archiverr.core.safety import (
    PlannedOperation,
    resolve_run_safety,
    safe_copy,
    safe_move,
    safe_write,
)


@pytest.fixture
def src_file(tmp_path) -> Path:
    p = tmp_path / "src.mkv"
    p.write_text("hello", encoding="utf-8")
    return p


class TestSafeCopy:
    def test_dry_run_no_disk_write(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        result = safe_copy(src_file, dst, hardlink=False, dry_run=True)
        assert result.op == "skip"
        assert result.executed is False
        assert not dst.exists()
        assert result.extra.get("planned_op") == "copy"

    def test_real_copy_executes(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        result = safe_copy(src_file, dst, hardlink=False, dry_run=False)
        assert result.op == "copy"
        assert result.executed is True
        assert dst.read_text(encoding="utf-8") == "hello"

    def test_hardlink_when_possible(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        result = safe_copy(src_file, dst, hardlink=True, dry_run=False)
        assert result.op in {"link", "copy"}  # filesystem may not support hardlink
        assert result.executed is True
        assert dst.exists()
        if result.op == "link":
            assert os.stat(src_file).st_ino == os.stat(dst).st_ino

    def test_missing_source_returns_error(self, tmp_path):
        result = safe_copy(tmp_path / "nope.mkv", tmp_path / "dst.mkv",
                            hardlink=False, dry_run=False)
        assert result.op == "error"
        assert result.executed is False
        assert "source does not exist" in result.reason

    def test_existing_target_returns_error(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        dst.write_text("existing", encoding="utf-8")
        result = safe_copy(src_file, dst, hardlink=False, dry_run=False)
        assert result.op == "error"
        assert dst.read_text() == "existing"

    def test_overwrite_replaces(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        dst.write_text("existing", encoding="utf-8")
        result = safe_copy(src_file, dst, hardlink=False, dry_run=False, overwrite=True)
        assert result.op == "copy"
        assert result.executed is True
        assert dst.read_text() == "hello"

    def test_creates_target_directory(self, tmp_path, src_file):
        dst = tmp_path / "deep" / "nested" / "dst.mkv"
        result = safe_copy(src_file, dst, hardlink=False, dry_run=False)
        assert result.executed is True
        assert dst.exists()


class TestSafeWrite:
    def test_dry_run_no_disk_write(self, tmp_path):
        dst = tmp_path / "out.json"
        result = safe_write(dst, "{}", dry_run=True)
        assert result.op == "skip"
        assert not dst.exists()

    def test_real_write_executes(self, tmp_path):
        dst = tmp_path / "out.json"
        result = safe_write(dst, "{}", dry_run=False)
        assert result.op == "write"
        assert dst.read_text() == "{}"

    def test_atomic_write_leaves_no_tmp(self, tmp_path):
        dst = tmp_path / "out.json"
        safe_write(dst, "{}", dry_run=False)
        assert not (tmp_path / "out.json.tmp").exists()

    def test_existing_target_returns_error(self, tmp_path):
        dst = tmp_path / "out.json"
        dst.write_text("old")
        result = safe_write(dst, "new", dry_run=False)
        assert result.op == "error"
        assert dst.read_text() == "old"

    def test_overwrite_replaces(self, tmp_path):
        dst = tmp_path / "out.json"
        dst.write_text("old")
        result = safe_write(dst, "new", dry_run=False, overwrite=True)
        assert result.op == "write"
        assert dst.read_text() == "new"

    def test_bytes_content_written_as_bytes(self, tmp_path):
        dst = tmp_path / "out.bin"
        safe_write(dst, b"\x00\x01\x02", dry_run=False)
        assert dst.read_bytes() == b"\x00\x01\x02"


class TestSafeMove:
    def test_dry_run_no_side_effect(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        result = safe_move(src_file, dst, dry_run=True)
        assert result.op == "skip"
        assert src_file.exists()
        assert not dst.exists()

    def test_real_move_executes(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        result = safe_move(src_file, dst, dry_run=False)
        assert result.op == "move"
        assert result.executed is True
        assert not src_file.exists()
        assert dst.read_text() == "hello"

    def test_missing_source_returns_error(self, tmp_path):
        result = safe_move(tmp_path / "nope", tmp_path / "dst", dry_run=False)
        assert result.op == "error"

    def test_existing_target_returns_error(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        dst.write_text("existing")
        result = safe_move(src_file, dst, dry_run=False)
        assert result.op == "error"
        assert src_file.exists()


class TestResolveRunSafety:
    def test_defaults(self):
        resolved = resolve_run_safety({})
        assert resolved == {"dry_run": True, "hardlink": False, "no_delete": True}

    def test_explicit_values(self):
        resolved = resolve_run_safety({
            "dry_run": False, "hardlink": True, "no_delete": False,
        })
        assert resolved == {"dry_run": False, "hardlink": True, "no_delete": False}

    def test_none_options_tolerated(self):
        resolved = resolve_run_safety(None)  # type: ignore[arg-type]
        assert resolved == {"dry_run": True, "hardlink": False, "no_delete": True}


class TestPlannedOperationRecord:
    def test_to_dict_serializes_all_fields(self, tmp_path, src_file):
        dst = tmp_path / "dst.mkv"
        op = safe_copy(src_file, dst, hardlink=False, dry_run=True)
        d = op.to_dict()
        assert d["op"] == "skip"
        assert d["source"] == str(src_file)
        assert d["target"] == str(dst)
        assert d["dry_run"] is True
        assert d["executed"] is False
        assert "extra" in d

    def test_frozen_dataclass(self, tmp_path, src_file):
        op = safe_copy(src_file, tmp_path / "x.mkv", hardlink=False, dry_run=True)
        with pytest.raises(Exception):
            op.op = "copy"  # type: ignore[misc]

    def test_ok_type(self):
        op = PlannedOperation(op="copy", source="a", target="b",
                              reason="ok", dry_run=False, executed=True)
        assert op.executed is True
