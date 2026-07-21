"""Typed descriptors for file-backed public-document supplements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
)

PublicArtifactKind = Literal["visual", "chart", "carryover"]

_ARTIFACT_KINDS: Final[frozenset[str]] = frozenset({"visual", "chart", "carryover"})
_SEGMENTS: Final[frozenset[str]] = frozenset({DOMESTIC_EQUITY, US_EQUITY, CRYPTO})
_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    """One immutable file prepared below a run-owned staging root."""

    artifact_id: str
    segment: MarketSegment
    kind: PublicArtifactKind
    relative_public_path: PurePosixPath
    staged_path: Path
    sha256: str

    def __post_init__(self) -> None:
        if _ID_RE.fullmatch(self.artifact_id) is None:
            raise ValueError("artifact_id must be a bounded lowercase identifier")
        if self.segment not in _SEGMENTS:
            raise ValueError("segment must be a known market segment")
        if self.kind not in _ARTIFACT_KINDS:
            raise ValueError("kind must be visual, chart, or carryover")
        if not isinstance(self.relative_public_path, PurePosixPath):
            raise TypeError("relative_public_path must be PurePosixPath")
        if self.relative_public_path.is_absolute() or ".." in self.relative_public_path.parts:
            raise ValueError("relative_public_path must be relative and contain no '..'")
        if str(self.relative_public_path) in {"", "."}:
            raise ValueError("relative_public_path must identify a public file")
        if not isinstance(self.staged_path, Path):
            raise TypeError("staged_path must be Path")
        if _SHA256_RE.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be lowercase hexadecimal")


def build_staged_artifact(
    *,
    staging_root: Path,
    staged_path: Path,
    segment: MarketSegment,
    kind: PublicArtifactKind,
) -> StagedArtifact:
    """Validate a staged regular file and derive its stable descriptor."""

    root = staging_root.resolve()
    candidate = staged_path.resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("staged_path must be contained by staging_root") from exc
    if candidate == root or staged_path.is_symlink() or not candidate.is_file():
        raise ValueError("staged_path must be a non-symlink regular file")
    relative_public_path = PurePosixPath(relative.as_posix())
    payload = candidate.read_bytes()
    digest = sha256(payload).hexdigest()
    id_digest = sha256(f"{segment}:{kind}:{relative_public_path.as_posix()}".encode()).hexdigest()[
        :24
    ]
    return StagedArtifact(
        artifact_id=f"{segment}.{kind}.{id_digest}",
        segment=segment,
        kind=kind,
        relative_public_path=relative_public_path,
        staged_path=candidate,
        sha256=digest,
    )


__all__ = ["PublicArtifactKind", "StagedArtifact", "build_staged_artifact"]
