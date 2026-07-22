"""U144 Step 8 pre-git rollback integrity regressions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from investo.orchestrator import pipeline
from investo.publisher.errors import PublisherIOError

_TARGET_DATE = date(2026, 7, 22)


def test_rollback_restores_existing_bytes_atomically_and_removes_new_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = tmp_path / "archive" / "existing.md"
    created = tmp_path / "archive" / "created.md"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"after")
    created.write_bytes(b"new")
    calls: list[tuple[Path, bytes]] = []
    real_write_atomic_bytes = pipeline.write_atomic_bytes

    def observe_atomic_restore(path: Path, payload: bytes) -> None:
        calls.append((path, payload))
        real_write_atomic_bytes(path, payload)

    monkeypatch.setattr(pipeline, "write_atomic_bytes", observe_atomic_restore)

    pipeline._rollback_paths(
        {existing: b"before", created: None},
        target_date=_TARGET_DATE,
    )

    assert calls == [(existing, b"before")]
    assert existing.read_bytes() == b"before"
    assert not created.exists()


def test_rollback_unlink_failure_is_observable_and_remaining_paths_are_attempted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "blocked.md"
    removable = tmp_path / "removable.md"
    blocked.write_bytes(b"blocked")
    removable.write_bytes(b"remove")
    real_unlink = Path.unlink

    def fail_one_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == blocked:
            raise OSError("injected unlink failure")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_one_unlink)

    with pytest.raises(PublisherIOError) as raised:
        pipeline._rollback_paths(
            {blocked: None, removable: None},
            target_date=_TARGET_DATE,
        )

    assert raised.value.path == blocked
    assert blocked.exists()
    assert not removable.exists()


def test_rollback_restore_failure_is_observable_and_later_restore_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = tmp_path / "blocked.md"
    restored = tmp_path / "restored.md"
    blocked.write_bytes(b"after-blocked")
    restored.write_bytes(b"after-restored")
    real_write_atomic_bytes = pipeline.write_atomic_bytes

    def fail_one_restore(path: Path, payload: bytes) -> None:
        if path == blocked:
            raise OSError("injected restore failure")
        real_write_atomic_bytes(path, payload)

    monkeypatch.setattr(pipeline, "write_atomic_bytes", fail_one_restore)

    with pytest.raises(PublisherIOError) as raised:
        pipeline._rollback_paths(
            {blocked: b"before-blocked", restored: b"before-restored"},
            target_date=_TARGET_DATE,
        )

    assert raised.value.path == blocked
    assert blocked.read_bytes() == b"after-blocked"
    assert restored.read_bytes() == b"before-restored"
