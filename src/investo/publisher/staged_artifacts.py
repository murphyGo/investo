"""Post-E6 promotion of validated file-backed public supplements."""

from __future__ import annotations

from collections.abc import MutableMapping
from hashlib import sha256
from pathlib import Path

from investo._internal._io import write_atomic_bytes
from investo.models.public_artifact import StagedArtifact
from investo.publisher.errors import PublisherIOError
from investo.publisher.public_document import FinalizedPublicBundle


def _promotion_error(bundle: FinalizedPublicBundle, path: Path) -> PublisherIOError:
    return PublisherIOError(target_date=bundle.target_date, path=path, cause=None)


def _has_symlink_component(root: Path, candidate: Path) -> bool:
    """Return whether root or any existing lexical child component is a symlink."""

    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    current = root
    if current.is_symlink():
        return True
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _validate_manifest_artifact(
    bundle: FinalizedPublicBundle,
    artifact: StagedArtifact,
    *,
    staging_root: Path,
    archive_root: Path,
) -> tuple[Path, bytes]:
    expected_staged = staging_root.joinpath(*artifact.relative_public_path.parts)
    destination = archive_root.joinpath(*artifact.relative_public_path.parts)
    artifact_path = artifact.staged_path.absolute()
    if (
        artifact_path != expected_staged
        or _has_symlink_component(staging_root, expected_staged)
        or _has_symlink_component(archive_root, destination)
    ):
        raise _promotion_error(bundle, artifact.staged_path)
    try:
        resolved_staged = artifact.staged_path.resolve(strict=True)
        resolved_expected = expected_staged.resolve(strict=True)
        resolved_staging_root = staging_root.resolve(strict=True)
        resolved_archive_root = archive_root.resolve(strict=False)
        resolved_destination = destination.resolve(strict=False)
        resolved_staged.relative_to(resolved_staging_root)
        resolved_destination.relative_to(resolved_archive_root)
    except (OSError, ValueError) as exc:
        cause = exc if isinstance(exc, OSError) else None
        raise PublisherIOError(
            target_date=bundle.target_date,
            path=artifact.staged_path,
            cause=cause,
        ) from exc
    if (
        resolved_staged != resolved_expected
        or artifact.staged_path.is_symlink()
        or not resolved_staged.is_file()
    ):
        raise _promotion_error(bundle, artifact.staged_path)
    try:
        payload = resolved_staged.read_bytes()
    except OSError as exc:
        raise PublisherIOError(
            target_date=bundle.target_date,
            path=artifact.staged_path,
            cause=exc,
        ) from exc
    if sha256(payload).hexdigest() != artifact.sha256:
        raise _promotion_error(bundle, artifact.staged_path)
    return destination, payload


def promote_finalized_bundle_artifacts(
    bundle: FinalizedPublicBundle,
    *,
    staging_root: Path,
    archive_root: Path,
    snapshots: MutableMapping[Path, bytes | None],
) -> tuple[Path, ...]:
    """Promote exactly the E6 manifest after validating the full set first.

    The caller owns the surrounding publish transaction and uses ``snapshots``
    for its existing rollback path. No Markdown or URL is inspected here.
    """

    lexical_staging_root = staging_root.absolute()
    lexical_archive_root = archive_root.absolute()
    validated = tuple(
        _validate_manifest_artifact(
            bundle,
            artifact,
            staging_root=lexical_staging_root,
            archive_root=lexical_archive_root,
        )
        for artifact in bundle.promotion_manifest
    )
    promoted: list[Path] = []
    for destination, payload in validated:
        try:
            if destination not in snapshots:
                snapshots[destination] = destination.read_bytes() if destination.exists() else None
            write_atomic_bytes(destination, payload)
        except OSError as exc:
            raise PublisherIOError(
                target_date=bundle.target_date,
                path=destination,
                cause=exc,
            ) from exc
        promoted.append(destination)
    return tuple(promoted)


__all__ = ["promote_finalized_bundle_artifacts"]
