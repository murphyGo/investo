from __future__ import annotations

from pathlib import Path

import pytest

from investo._internal.artifact_staging import temporary_artifact_staging_root


def test_temporary_artifact_root_cleans_after_normal_exit() -> None:
    with temporary_artifact_staging_root() as root:
        observed = root
        (root / "file").write_bytes(b"x")
        assert root.is_dir()
    assert not observed.exists()


def test_temporary_artifact_root_cleans_after_exception() -> None:
    observed: Path | None = None
    with pytest.raises(RuntimeError, match="stop"), temporary_artifact_staging_root() as root:
        observed = root
        (root / "file").write_bytes(b"x")
        raise RuntimeError("stop")
    assert observed is not None
    assert not observed.exists()
