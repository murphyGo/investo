from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path, PurePosixPath

import pytest

from investo.models.public_artifact import StagedArtifact, build_staged_artifact


def test_build_staged_artifact_derives_identity_path_and_digest(tmp_path: Path) -> None:
    root = tmp_path / "stage"
    path = root / "us-equity/2026/07/day.assets/hero.svg"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"hero")

    artifact = build_staged_artifact(
        staging_root=root,
        staged_path=path,
        segment="us-equity",
        kind="visual",
    )

    assert artifact.relative_public_path == PurePosixPath("us-equity/2026/07/day.assets/hero.svg")
    assert artifact.staged_path == path.resolve()
    assert len(artifact.sha256) == 64
    assert artifact.artifact_id.startswith("us-equity.visual.")
    with pytest.raises(FrozenInstanceError):
        artifact.sha256 = "0" * 64  # type: ignore[misc]


def test_build_staged_artifact_rejects_escape_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "stage"
    root.mkdir()
    outside = tmp_path / "outside.svg"
    outside.write_bytes(b"outside")

    with pytest.raises(ValueError, match="contained"):
        build_staged_artifact(
            staging_root=root,
            staged_path=outside,
            segment="us-equity",
            kind="visual",
        )

    link = root / "link.svg"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match=r"contained|non-symlink"):
        build_staged_artifact(
            staging_root=root,
            staged_path=link,
            segment="us-equity",
            kind="visual",
        )


def test_descriptor_rejects_traversal_and_bad_digest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="contain no"):
        StagedArtifact(
            artifact_id="us-equity.visual.hero",
            segment="us-equity",
            kind="visual",
            relative_public_path=PurePosixPath("../hero.svg"),
            staged_path=tmp_path / "hero.svg",
            sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        StagedArtifact(
            artifact_id="us-equity.visual.hero",
            segment="us-equity",
            kind="visual",
            relative_public_path=PurePosixPath("hero.svg"),
            staged_path=tmp_path / "hero.svg",
            sha256="BAD",
        )
