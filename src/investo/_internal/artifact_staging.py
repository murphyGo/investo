"""Run-owned temporary staging-root lifecycle for public artifacts."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def temporary_artifact_staging_root() -> Iterator[Path]:
    """Yield one private root and remove it on every context-manager exit."""

    with TemporaryDirectory(prefix="investo-public-") as directory:
        yield Path(directory).resolve()


__all__ = ["temporary_artifact_staging_root"]
