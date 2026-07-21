"""Unit tests for the shared atomic-write primitives (u78)."""

from __future__ import annotations

from pathlib import Path

import pytest

from investo._internal._io import write_atomic, write_atomic_bytes


def test_write_atomic_writes_utf8_text(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_atomic(target, "héllo 한국어")
    assert target.read_text(encoding="utf-8") == "héllo 한국어"


def test_write_atomic_bytes_writes_verbatim(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    payload = b"\x00\x01\x02PNG\xff"
    write_atomic_bytes(target, payload)
    assert target.read_bytes() == payload


def test_write_atomic_creates_missing_parents(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c" / "out.txt"
    write_atomic(target, "deep")
    assert target.read_text(encoding="utf-8") == "deep"


def test_write_atomic_bytes_creates_missing_parents(tmp_path: Path) -> None:
    target = tmp_path / "x" / "y" / "out.bin"
    write_atomic_bytes(target, b"deep")
    assert target.read_bytes() == b"deep"


def test_write_atomic_leaves_no_tmp_sibling_on_success(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_atomic(target, "ok")
    assert target.exists()
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_write_atomic_bytes_leaves_no_tmp_sibling_on_success(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    write_atomic_bytes(target, b"ok")
    assert target.exists()
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_write_atomic_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    write_atomic(target, "first")
    write_atomic(target, "second")
    assert target.read_text(encoding="utf-8") == "second"


def test_write_atomic_failed_replace_keeps_prior_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ``os.replace`` fails, the prior destination content survives
    (atomicity) and the OSError propagates unchanged for callers to map.
    """
    target = tmp_path / "out.txt"
    write_atomic(target, "original")

    def boom(src: object, dst: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("investo._internal._io.os.replace", boom)

    with pytest.raises(OSError, match="synthetic replace failure"):
        write_atomic(target, "should not land")

    assert target.read_text(encoding="utf-8") == "original"
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_write_atomic_bytes_failed_replace_keeps_prior_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.bin"
    write_atomic_bytes(target, b"original")

    def boom(src: object, dst: object) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr("investo._internal._io.os.replace", boom)

    with pytest.raises(OSError, match="synthetic replace failure"):
        write_atomic_bytes(target, b"should not land")

    assert target.read_bytes() == b"original"
    assert not target.with_suffix(target.suffix + ".tmp").exists()
