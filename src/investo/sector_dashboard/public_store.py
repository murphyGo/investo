"""Recoverable derived-only pair storage for the u145 public sector radar."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import stat
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal

from investo.models.sector import SectorCoverageStatus
from investo.models.sector_public import (
    FreshnessState,
    PublicFailureCode,
    PublicSectorBuildOutcome,
    PublicSectorBuildStatus,
    PublicSectorDashboardSnapshot,
    RenderedPublicSectorProjection,
)
from investo.sector_dashboard.public_render import (
    MAX_PUBLIC_PROJECTION_BYTES,
    PublicProjectionError,
    verify_public_sector_projection,
)

PUBLIC_SECTOR_DIRECTORY: Final[Path] = Path("site_docs/sectors")
PUBLIC_MARKDOWN_NAME: Final[str] = "index.md"
PUBLIC_SNAPSHOT_NAME: Final[str] = "latest.json"
_TRANSACTION_MARKER_NAME: Final[str] = ".sectors.public.transaction.json"
_PREPARED_PREFIX: Final[str] = ".sectors.public.prepared-"
_BACKUP_PREFIX: Final[str] = ".sectors.public.backup-"
_MAX_MARKER_BYTES: Final[int] = 4096
_FaultHook = Callable[[str], None]
StoreErrorReason = Literal[
    "path_invalid",
    "pair_invalid",
    "projection_not_promotable",
    "promotion_failed",
    "recovery_failed",
    "transaction_busy",
]


class PublicSectorStoreError(RuntimeError):
    """Closed store failure without rejected bytes, paths, or provider text."""

    reason: StoreErrorReason

    def __init__(self, reason: StoreErrorReason) -> None:
        self.reason = reason
        super().__init__(f"public_sector_store.{reason}")


@dataclass(frozen=True, slots=True)
class _StorePaths:
    repository_root: Path
    parent: Path
    parent_identity: tuple[int, int]
    output: Path
    markdown: Path
    snapshot: Path
    marker: Path


@dataclass(frozen=True, slots=True)
class _StoredPair:
    projection: RenderedPublicSectorProjection
    snapshot: PublicSectorDashboardSnapshot


@dataclass(frozen=True, slots=True)
class _TransactionState:
    prepared_name: str
    backup_name: str | None
    expected_snapshot_id: str
    backup_snapshot_id: str | None
    phase: Literal["promoting", "rolled_back"] = "promoting"


def promote_public_sector_projection(
    repository_root: Path,
    projection: RenderedPublicSectorProjection,
    *,
    _fault_hook: _FaultHook | None = None,
) -> PublicSectorBuildOutcome:
    """Promote one verified pair, restoring the prior pair on pre-git failure."""

    paths = _store_paths(repository_root)
    with _store_lock(paths):
        parent_descriptor = _open_directory_descriptor(
            paths.parent,
            reason="path_invalid",
            expected_identity=paths.parent_identity,
        )
        try:
            return _promote_public_sector_projection_locked(
                paths,
                projection,
                parent_descriptor=parent_descriptor,
                fault_hook=_fault_hook,
            )
        finally:
            with suppress(OSError):
                os.close(parent_descriptor)


def _promote_public_sector_projection_locked(
    paths: _StorePaths,
    projection: RenderedPublicSectorProjection,
    *,
    parent_descriptor: int,
    fault_hook: _FaultHook | None,
) -> PublicSectorBuildOutcome:
    try:
        snapshot = verify_public_sector_projection(
            projection.snapshot_bytes,
            projection.markdown_bytes,
        )
    except PublicProjectionError:
        raise PublicSectorStoreError("pair_invalid") from None
    if projection.snapshot_id != snapshot.snapshot_id:
        raise PublicSectorStoreError("pair_invalid")
    _require_promotable(snapshot)
    _recover_transaction(paths, parent_descriptor=parent_descriptor)
    existing = _read_optional_pair_from_parent(parent_descriptor)
    if existing is not None and existing.projection == projection:
        return _successful_outcome(PublicSectorBuildStatus.UNCHANGED, snapshot)

    _create_output_directory_at(parent_descriptor)
    output_descriptor = _open_child_directory(
        parent_descriptor,
        PUBLIC_SECTOR_DIRECTORY.name,
        reason="promotion_failed",
    )
    prepared: Path | None = None
    backup: Path | None = None
    state: _TransactionState | None = None
    marker_written = False
    cleanup_started = False
    hook = fault_hook or _no_fault
    try:
        if _read_optional_pair_from_descriptor(output_descriptor) != existing:
            raise PublicSectorStoreError("promotion_failed")
        prepared = _stage_pair(
            paths,
            projection,
            prefix=_PREPARED_PREFIX,
            parent_descriptor=parent_descriptor,
        )
        if existing is not None:
            backup = _stage_pair(
                paths,
                existing.projection,
                prefix=_BACKUP_PREFIX,
                parent_descriptor=parent_descriptor,
            )
        state = _TransactionState(
            prepared_name=prepared.name,
            backup_name=backup.name if backup is not None else None,
            expected_snapshot_id=projection.snapshot_id,
            backup_snapshot_id=(existing.projection.snapshot_id if existing is not None else None),
            phase="promoting",
        )
        _write_marker(paths, state, parent_descriptor=parent_descriptor)
        marker_written = True
        hook("prepared")
        _assert_directory_attached(paths.parent, parent_descriptor, reason="promotion_failed")
        _assert_directory_attached(paths.output, output_descriptor, reason="promotion_failed")
        if _read_optional_pair_from_descriptor(output_descriptor) != existing:
            raise PublicSectorStoreError("promotion_failed")

        _write_atomic_fsynced_at(
            output_descriptor,
            PUBLIC_MARKDOWN_NAME,
            projection.markdown_bytes,
            reason="promotion_failed",
        )
        hook("markdown_promoted")
        _assert_directory_attached(paths.parent, parent_descriptor, reason="promotion_failed")
        _assert_directory_attached(paths.output, output_descriptor, reason="promotion_failed")
        _write_atomic_fsynced_at(
            output_descriptor,
            PUBLIC_SNAPSHOT_NAME,
            projection.snapshot_bytes,
            reason="promotion_failed",
        )
        hook("snapshot_promoted")
        _assert_directory_attached(paths.parent, parent_descriptor, reason="promotion_failed")
        _assert_directory_attached(paths.output, output_descriptor, reason="promotion_failed")
        promoted = _read_pair_from_descriptor(output_descriptor)
        if promoted.projection != projection:
            raise PublicSectorStoreError("promotion_failed")
        cleanup_started = True
        _complete_transaction(paths, state, parent_descriptor=parent_descriptor)
        marker_written = False
        return _successful_outcome(PublicSectorBuildStatus.PROMOTED, snapshot)
    except BaseException as exc:
        if state is not None or marker_written:
            try:
                active_state = state or _read_marker(paths)
                if active_state is None:
                    raise PublicSectorStoreError("recovery_failed")
                if cleanup_started and existing is not None:
                    # Cleanup may already have removed all or part of the backup.
                    # Persist the verified prior pair again before rollback so a
                    # second interruption cannot strand a mixed pair on disk.
                    rollback_backup = _stage_pair(
                        paths,
                        existing.projection,
                        prefix=_BACKUP_PREFIX,
                        parent_descriptor=parent_descriptor,
                    )
                    active_state = replace(active_state, backup_name=rollback_backup.name)
                    _write_marker(paths, active_state, parent_descriptor=parent_descriptor)
                _rollback_transaction(
                    paths,
                    active_state,
                    parent_descriptor=parent_descriptor,
                    output_descriptor=output_descriptor,
                )
            except PublicSectorStoreError:
                raise PublicSectorStoreError("recovery_failed") from None
        else:
            _remove_unpublished_directory(
                prepared,
                paths,
                _PREPARED_PREFIX,
                parent_descriptor=parent_descriptor,
            )
            _remove_unpublished_directory(
                backup,
                paths,
                _BACKUP_PREFIX,
                parent_descriptor=parent_descriptor,
            )
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, PublicSectorStoreError):
            raise
        raise PublicSectorStoreError("promotion_failed") from None
    finally:
        with suppress(OSError):
            os.close(output_descriptor)


def hold_public_sector_last_good(
    repository_root: Path,
    *,
    failure_codes: Sequence[PublicFailureCode],
) -> PublicSectorBuildOutcome:
    """Return an honest hold/block outcome without changing the stored pair."""

    codes = tuple(failure_codes)
    if not codes:
        raise ValueError("failure_codes must not be empty")
    paths = _store_paths(repository_root)
    with _store_lock(paths):
        parent_descriptor = _open_directory_descriptor(
            paths.parent,
            reason="path_invalid",
            expected_identity=paths.parent_identity,
        )
        try:
            _recover_transaction(paths, parent_descriptor=parent_descriptor)
            existing = _read_optional_pair_from_parent(parent_descriptor)
        finally:
            with suppress(OSError):
                os.close(parent_descriptor)
        if existing is None:
            return PublicSectorBuildOutcome(
                status=PublicSectorBuildStatus.BLOCKED,
                failure_codes=codes,
            )
        snapshot = existing.snapshot
        if snapshot.snapshot_id is None or snapshot.as_of_date is None:
            raise PublicSectorStoreError("pair_invalid")
        return PublicSectorBuildOutcome(
            status=PublicSectorBuildStatus.HELD_LAST_GOOD,
            snapshot_id=snapshot.snapshot_id,
            as_of_date=snapshot.as_of_date,
            failure_codes=codes,
        )


def read_public_sector_projection(repository_root: Path) -> RenderedPublicSectorProjection | None:
    """Read and fully verify the current public pair, recovering a prior transaction first."""

    paths = _store_paths(repository_root)
    with _store_lock(paths):
        parent_descriptor = _open_directory_descriptor(
            paths.parent,
            reason="path_invalid",
            expected_identity=paths.parent_identity,
        )
        try:
            _recover_transaction(paths, parent_descriptor=parent_descriptor)
            stored = _read_optional_pair_from_parent(parent_descriptor)
            return stored.projection if stored is not None else None
        finally:
            with suppress(OSError):
                os.close(parent_descriptor)


@contextmanager
def _store_lock(paths: _StorePaths) -> Iterator[None]:
    """Serialize readers and writers without leaving repository artifacts."""

    descriptor: int | None = None
    try:
        lock_root = Path(tempfile.gettempdir()).resolve(strict=True)
        lock_name = hashlib.sha256(str(paths.repository_root).encode()).hexdigest()
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(lock_root / f"investo-sector-public-{lock_name}.lock", flags, 0o600)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
        ):
            raise OSError("unsafe lock file")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise PublicSectorStoreError("transaction_busy") from None
    try:
        yield
    finally:
        if descriptor is not None:
            with suppress(OSError):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            with suppress(OSError):
                os.close(descriptor)


def _store_paths(repository_root: Path) -> _StorePaths:
    try:
        if not repository_root.is_absolute() or repository_root.is_symlink():
            raise PublicSectorStoreError("path_invalid")
        root = repository_root.resolve(strict=True)
        if not root.is_dir():
            raise PublicSectorStoreError("path_invalid")
        parent = root / PUBLIC_SECTOR_DIRECTORY.parent
        if parent.is_symlink() or not parent.is_dir():
            raise PublicSectorStoreError("path_invalid")
        if parent.resolve(strict=True) != parent:
            raise PublicSectorStoreError("path_invalid")
        parent_metadata = parent.stat(follow_symlinks=False)
        output = parent / PUBLIC_SECTOR_DIRECTORY.name
        if (output.exists() or output.is_symlink()) and (
            output.is_symlink() or not output.is_dir() or output.resolve(strict=True) != output
        ):
            raise PublicSectorStoreError("path_invalid")
    except OSError:
        raise PublicSectorStoreError("path_invalid") from None
    return _StorePaths(
        repository_root=root,
        parent=parent,
        parent_identity=(parent_metadata.st_dev, parent_metadata.st_ino),
        output=output,
        markdown=output / PUBLIC_MARKDOWN_NAME,
        snapshot=output / PUBLIC_SNAPSHOT_NAME,
        marker=parent / _TRANSACTION_MARKER_NAME,
    )


def _create_output_directory(paths: _StorePaths) -> None:
    try:
        paths.output.mkdir(mode=0o755)
    except FileExistsError:
        pass
    except OSError:
        raise PublicSectorStoreError("promotion_failed") from None
    refreshed = _store_paths(paths.repository_root)
    if refreshed.output != paths.output:
        raise PublicSectorStoreError("path_invalid")
    _fsync_directory(paths.parent)


def _create_output_directory_at(parent_descriptor: int) -> None:
    try:
        os.mkdir(PUBLIC_SECTOR_DIRECTORY.name, mode=0o755, dir_fd=parent_descriptor)
    except FileExistsError:
        pass
    except OSError:
        raise PublicSectorStoreError("promotion_failed") from None
    output_descriptor = _open_child_directory(
        parent_descriptor,
        PUBLIC_SECTOR_DIRECTORY.name,
        reason="path_invalid",
    )
    with suppress(OSError):
        os.close(output_descriptor)
    try:
        os.fsync(parent_descriptor)
    except OSError:
        raise PublicSectorStoreError("promotion_failed") from None


def _stage_pair(
    paths: _StorePaths,
    projection: RenderedPublicSectorProjection,
    *,
    prefix: str,
    parent_descriptor: int,
) -> Path:
    name = f"{prefix}{secrets.token_hex(8)}"
    child_descriptor: int | None = None
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
        child_descriptor = _open_child_directory(
            parent_descriptor,
            name,
            reason="promotion_failed",
        )
        _write_new_fsynced_at(
            child_descriptor,
            PUBLIC_MARKDOWN_NAME,
            projection.markdown_bytes,
        )
        _write_new_fsynced_at(
            child_descriptor,
            PUBLIC_SNAPSHOT_NAME,
            projection.snapshot_bytes,
        )
        os.fsync(child_descriptor)
        staged = _read_pair_from_descriptor(child_descriptor)
        if staged.projection != projection:
            raise PublicSectorStoreError("pair_invalid")
    except (OSError, PublicSectorStoreError) as exc:
        if child_descriptor is not None:
            with suppress(OSError):
                os.close(child_descriptor)
            child_descriptor = None
        _remove_unpublished_directory(
            paths.parent / name,
            paths,
            prefix,
            parent_descriptor=parent_descriptor,
        )
        if isinstance(exc, PublicSectorStoreError):
            raise
        raise PublicSectorStoreError("promotion_failed") from None
    finally:
        if child_descriptor is not None:
            with suppress(OSError):
                os.close(child_descriptor)
    return paths.parent / name


def _read_optional_pair(paths: _StorePaths) -> _StoredPair | None:
    output_exists = paths.output.exists()
    if not output_exists:
        return None
    markdown_exists = paths.markdown.exists() or paths.markdown.is_symlink()
    snapshot_exists = paths.snapshot.exists() or paths.snapshot.is_symlink()
    if not markdown_exists and not snapshot_exists:
        return None
    if markdown_exists != snapshot_exists:
        raise PublicSectorStoreError("pair_invalid")
    stored = _read_pair_from_directory(paths.output)
    _require_promotable(stored.snapshot)
    return stored


def _read_optional_pair_from_parent(parent_descriptor: int) -> _StoredPair | None:
    try:
        metadata = os.stat(
            PUBLIC_SECTOR_DIRECTORY.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return None
    except OSError:
        raise PublicSectorStoreError("pair_invalid") from None
    if not stat.S_ISDIR(metadata.st_mode):
        raise PublicSectorStoreError("pair_invalid")
    output_descriptor = _open_child_directory(
        parent_descriptor,
        PUBLIC_SECTOR_DIRECTORY.name,
        reason="pair_invalid",
    )
    try:
        stored = _read_optional_pair_from_descriptor(output_descriptor)
    finally:
        with suppress(OSError):
            os.close(output_descriptor)
    if stored is not None:
        _require_promotable(stored.snapshot)
    return stored


def _read_required_pair(paths: _StorePaths) -> _StoredPair:
    stored = _read_optional_pair(paths)
    if stored is None:
        raise PublicSectorStoreError("pair_invalid")
    return stored


def _read_pair_from_directory(directory: Path) -> _StoredPair:
    snapshot_bytes = _read_bounded_file(directory / PUBLIC_SNAPSHOT_NAME)
    markdown_bytes = _read_bounded_file(directory / PUBLIC_MARKDOWN_NAME)
    try:
        snapshot = verify_public_sector_projection(snapshot_bytes, markdown_bytes)
    except PublicProjectionError:
        raise PublicSectorStoreError("pair_invalid") from None
    if snapshot.snapshot_id is None:
        raise PublicSectorStoreError("pair_invalid")
    return _StoredPair(
        projection=RenderedPublicSectorProjection(
            snapshot_bytes=snapshot_bytes,
            markdown_bytes=markdown_bytes,
            snapshot_id=snapshot.snapshot_id,
        ),
        snapshot=snapshot,
    )


def _read_optional_pair_from_descriptor(descriptor: int) -> _StoredPair | None:
    existence: list[bool] = []
    for name in (PUBLIC_MARKDOWN_NAME, PUBLIC_SNAPSHOT_NAME):
        try:
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            existence.append(False)
            continue
        except OSError:
            raise PublicSectorStoreError("pair_invalid") from None
        if not stat.S_ISREG(metadata.st_mode):
            raise PublicSectorStoreError("pair_invalid")
        existence.append(True)
    if existence == [False, False]:
        return None
    if existence != [True, True]:
        raise PublicSectorStoreError("pair_invalid")
    return _read_pair_from_descriptor(descriptor)


def _read_pair_from_descriptor(descriptor: int) -> _StoredPair:
    snapshot_bytes = _read_bounded_file_at(descriptor, PUBLIC_SNAPSHOT_NAME)
    markdown_bytes = _read_bounded_file_at(descriptor, PUBLIC_MARKDOWN_NAME)
    try:
        snapshot = verify_public_sector_projection(snapshot_bytes, markdown_bytes)
    except PublicProjectionError:
        raise PublicSectorStoreError("pair_invalid") from None
    if snapshot.snapshot_id is None:
        raise PublicSectorStoreError("pair_invalid")
    return _StoredPair(
        projection=RenderedPublicSectorProjection(
            snapshot_bytes=snapshot_bytes,
            markdown_bytes=markdown_bytes,
            snapshot_id=snapshot.snapshot_id,
        ),
        snapshot=snapshot,
    )


def _read_bounded_file(path: Path, *, limit: int = MAX_PUBLIC_PROJECTION_BYTES) -> bytes:
    parent_descriptor = _open_directory_descriptor(path.parent, reason="pair_invalid")
    try:
        return _read_bounded_file_at(parent_descriptor, path.name, limit=limit)
    finally:
        with suppress(OSError):
            os.close(parent_descriptor)


def _read_bounded_file_at(
    parent_descriptor: int,
    name: str,
    *,
    limit: int = MAX_PUBLIC_PROJECTION_BYTES,
) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    except OSError:
        raise PublicSectorStoreError("pair_invalid") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0 or metadata.st_size > limit:
            raise PublicSectorStoreError("pair_invalid")
        chunks: list[bytes] = []
        remaining = metadata.st_size + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) != metadata.st_size:
            raise PublicSectorStoreError("pair_invalid")
        return payload
    except OSError:
        raise PublicSectorStoreError("pair_invalid") from None
    finally:
        with suppress(OSError):
            os.close(descriptor)


def _require_promotable(snapshot: PublicSectorDashboardSnapshot) -> None:
    if (
        snapshot.freshness is not FreshnessState.FRESH
        or snapshot.coverage.status
        not in (SectorCoverageStatus.PARTIAL, SectorCoverageStatus.NORMAL)
        or snapshot.snapshot_id is None
        or snapshot.as_of_date is None
    ):
        raise PublicSectorStoreError("projection_not_promotable")


def _successful_outcome(
    status: Literal[PublicSectorBuildStatus.PROMOTED, PublicSectorBuildStatus.UNCHANGED],
    snapshot: PublicSectorDashboardSnapshot,
) -> PublicSectorBuildOutcome:
    if snapshot.snapshot_id is None or snapshot.as_of_date is None:
        raise PublicSectorStoreError("pair_invalid")
    return PublicSectorBuildOutcome(
        status=status,
        snapshot_id=snapshot.snapshot_id,
        as_of_date=snapshot.as_of_date,
    )


def _write_marker(
    paths: _StorePaths,
    state: _TransactionState,
    *,
    parent_descriptor: int | None = None,
) -> None:
    payload = {
        "backup_name": state.backup_name,
        "backup_snapshot_id": state.backup_snapshot_id,
        "expected_snapshot_id": state.expected_snapshot_id,
        "phase": state.phase,
        "prepared_name": state.prepared_name,
        "version": 2,
    }
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if parent_descriptor is None:
        _write_atomic_fsynced(paths.marker, encoded)
    else:
        _write_atomic_fsynced_at(
            parent_descriptor,
            _TRANSACTION_MARKER_NAME,
            encoded,
            reason="promotion_failed",
        )


def _read_marker(
    paths: _StorePaths,
    *,
    parent_descriptor: int | None = None,
) -> _TransactionState | None:
    try:
        if parent_descriptor is None:
            if not (paths.marker.exists() or paths.marker.is_symlink()):
                return None
            payload = _read_bounded_file(paths.marker, limit=_MAX_MARKER_BYTES)
        else:
            try:
                os.stat(_TRANSACTION_MARKER_NAME, dir_fd=parent_descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return None
            payload = _read_bounded_file_at(
                parent_descriptor,
                _TRANSACTION_MARKER_NAME,
                limit=_MAX_MARKER_BYTES,
            )
    except (OSError, PublicSectorStoreError):
        raise PublicSectorStoreError("recovery_failed") from None
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise PublicSectorStoreError("recovery_failed") from None
    expected_keys = {
        "backup_name",
        "backup_snapshot_id",
        "expected_snapshot_id",
        "phase",
        "prepared_name",
        "version",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys or raw["version"] != 2:
        raise PublicSectorStoreError("recovery_failed")
    prepared_name = raw["prepared_name"]
    backup_name = raw["backup_name"]
    expected_id = raw["expected_snapshot_id"]
    backup_id = raw["backup_snapshot_id"]
    phase = raw["phase"]
    if (
        not isinstance(prepared_name, str)
        or not _valid_transaction_name(prepared_name, _PREPARED_PREFIX)
        or (backup_name is not None and not isinstance(backup_name, str))
        or (
            isinstance(backup_name, str)
            and not _valid_transaction_name(backup_name, _BACKUP_PREFIX)
        )
        or not _valid_snapshot_id(expected_id)
        or (backup_id is not None and not _valid_snapshot_id(backup_id))
        or ((backup_name is None) != (backup_id is None))
        or phase not in ("promoting", "rolled_back")
    ):
        raise PublicSectorStoreError("recovery_failed")
    return _TransactionState(
        prepared_name=prepared_name,
        backup_name=backup_name,
        expected_snapshot_id=expected_id,
        backup_snapshot_id=backup_id,
        phase=phase,
    )


def _recover_transaction(paths: _StorePaths, *, parent_descriptor: int | None = None) -> None:
    try:
        _recover_transaction_unchecked(paths, parent_descriptor=parent_descriptor)
    except PublicSectorStoreError as exc:
        if exc.reason == "recovery_failed":
            raise
        raise PublicSectorStoreError("recovery_failed") from None


def _recover_transaction_unchecked(
    paths: _StorePaths,
    *,
    parent_descriptor: int | None,
) -> None:
    _cleanup_atomic_temp_files(paths, parent_descriptor=parent_descriptor)
    state = _read_marker(paths, parent_descriptor=parent_descriptor)
    if state is None:
        _cleanup_orphan_transaction_directories(
            paths,
            parent_descriptor=parent_descriptor,
        )
        return
    current: _StoredPair | None
    try:
        current = (
            _read_optional_pair(paths)
            if parent_descriptor is None
            else _read_optional_pair_from_parent(parent_descriptor)
        )
    except PublicSectorStoreError:
        current = None
    if state.phase == "rolled_back":
        rollback_is_visible = (
            current is None
            if state.backup_snapshot_id is None
            else current is not None and current.projection.snapshot_id == state.backup_snapshot_id
        )
        if not rollback_is_visible:
            raise PublicSectorStoreError("recovery_failed")
        _complete_transaction(paths, state, parent_descriptor=parent_descriptor)
        _cleanup_orphan_transaction_directories(
            paths,
            parent_descriptor=parent_descriptor,
        )
        return
    if current is not None and current.projection.snapshot_id == state.expected_snapshot_id:
        _complete_transaction(paths, state, parent_descriptor=parent_descriptor)
        _cleanup_orphan_transaction_directories(
            paths,
            parent_descriptor=parent_descriptor,
        )
        return
    _restore_backup_or_clear(paths, state, parent_descriptor=parent_descriptor)
    rolled_back = _mark_rolled_back(paths, state, parent_descriptor=parent_descriptor)
    _complete_transaction(paths, rolled_back, parent_descriptor=parent_descriptor)
    _cleanup_orphan_transaction_directories(
        paths,
        parent_descriptor=parent_descriptor,
    )


def _rollback_transaction(
    paths: _StorePaths,
    state: _TransactionState,
    *,
    parent_descriptor: int | None = None,
    output_descriptor: int | None = None,
) -> None:
    """Undo the current promotion even when both new files reached disk."""

    _restore_backup_or_clear(
        paths,
        state,
        parent_descriptor=parent_descriptor,
        output_descriptor=output_descriptor,
    )
    rolled_back = _mark_rolled_back(
        paths,
        state,
        parent_descriptor=parent_descriptor,
    )
    _complete_transaction(paths, rolled_back, parent_descriptor=parent_descriptor)
    _cleanup_orphan_transaction_directories(
        paths,
        parent_descriptor=parent_descriptor,
    )


def _mark_rolled_back(
    paths: _StorePaths,
    state: _TransactionState,
    *,
    parent_descriptor: int | None = None,
) -> _TransactionState:
    rolled_back = _TransactionState(
        prepared_name=state.prepared_name,
        backup_name=state.backup_name,
        expected_snapshot_id=state.expected_snapshot_id,
        backup_snapshot_id=state.backup_snapshot_id,
        phase="rolled_back",
    )
    _write_marker(paths, rolled_back, parent_descriptor=parent_descriptor)
    return rolled_back


def _restore_backup_or_clear(
    paths: _StorePaths,
    state: _TransactionState,
    *,
    parent_descriptor: int | None = None,
    output_descriptor: int | None = None,
) -> None:
    if state.backup_name is not None:
        if parent_descriptor is None:
            backup_directory = _transaction_directory(
                paths,
                state.backup_name,
                prefix=_BACKUP_PREFIX,
                required=True,
            )
            if backup_directory is None:
                raise PublicSectorStoreError("recovery_failed")
            backup = _read_pair_from_directory(backup_directory)
        else:
            if not _valid_transaction_name(state.backup_name, _BACKUP_PREFIX):
                raise PublicSectorStoreError("recovery_failed")
            backup_descriptor = _open_child_directory(
                parent_descriptor,
                state.backup_name,
                reason="recovery_failed",
            )
            try:
                backup = _read_pair_from_descriptor(backup_descriptor)
            finally:
                with suppress(OSError):
                    os.close(backup_descriptor)
        _require_promotable(backup.snapshot)
        if backup.projection.snapshot_id != state.backup_snapshot_id:
            raise PublicSectorStoreError("recovery_failed")
        if parent_descriptor is None:
            _create_output_directory(paths)
        else:
            _create_output_directory_at(parent_descriptor)
        if output_descriptor is None:
            if parent_descriptor is None:
                _write_atomic_fsynced(paths.markdown, backup.projection.markdown_bytes)
                _write_atomic_fsynced(paths.snapshot, backup.projection.snapshot_bytes)
                restored = _read_required_pair(paths)
            else:
                restore_descriptor = _open_child_directory(
                    parent_descriptor,
                    PUBLIC_SECTOR_DIRECTORY.name,
                    reason="recovery_failed",
                )
                try:
                    _write_atomic_fsynced_at(
                        restore_descriptor,
                        PUBLIC_MARKDOWN_NAME,
                        backup.projection.markdown_bytes,
                        reason="recovery_failed",
                    )
                    _write_atomic_fsynced_at(
                        restore_descriptor,
                        PUBLIC_SNAPSHOT_NAME,
                        backup.projection.snapshot_bytes,
                        reason="recovery_failed",
                    )
                    restored = _read_pair_from_descriptor(restore_descriptor)
                finally:
                    with suppress(OSError):
                        os.close(restore_descriptor)
        else:
            _write_atomic_fsynced_at(
                output_descriptor,
                PUBLIC_MARKDOWN_NAME,
                backup.projection.markdown_bytes,
                reason="recovery_failed",
            )
            _write_atomic_fsynced_at(
                output_descriptor,
                PUBLIC_SNAPSHOT_NAME,
                backup.projection.snapshot_bytes,
                reason="recovery_failed",
            )
            restored = _read_pair_from_descriptor(output_descriptor)
        if restored.projection != backup.projection:
            raise PublicSectorStoreError("recovery_failed")
    else:
        _remove_first_publish_partial(
            paths,
            parent_descriptor=parent_descriptor,
            output_descriptor=output_descriptor,
        )


def _complete_transaction(
    paths: _StorePaths,
    state: _TransactionState,
    *,
    parent_descriptor: int | None = None,
) -> None:
    entries: tuple[tuple[str, str], ...] = ((state.prepared_name, _PREPARED_PREFIX),)
    if state.backup_name is not None:
        entries += ((state.backup_name, _BACKUP_PREFIX),)
    for name, prefix in entries:
        _remove_unpublished_directory(
            paths.parent / name,
            paths,
            prefix,
            parent_descriptor=parent_descriptor,
        )
    if parent_descriptor is None:
        try:
            if paths.marker.is_symlink():
                raise PublicSectorStoreError("recovery_failed")
            paths.marker.unlink(missing_ok=True)
            _fsync_directory(paths.parent)
        except OSError:
            raise PublicSectorStoreError("recovery_failed") from None
        return
    try:
        try:
            metadata = os.stat(
                _TRANSACTION_MARKER_NAME,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            metadata = None
        if metadata is not None and not stat.S_ISREG(metadata.st_mode):
            raise PublicSectorStoreError("recovery_failed")
        if metadata is not None:
            os.unlink(_TRANSACTION_MARKER_NAME, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
    except OSError:
        raise PublicSectorStoreError("recovery_failed") from None


def _remove_first_publish_partial(
    paths: _StorePaths,
    *,
    parent_descriptor: int | None = None,
    output_descriptor: int | None = None,
) -> None:
    if output_descriptor is None:
        if parent_descriptor is None:
            if not paths.output.exists():
                return
            descriptor = _open_directory_descriptor(paths.output, reason="recovery_failed")
        else:
            try:
                os.stat(
                    PUBLIC_SECTOR_DIRECTORY.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return
            descriptor = _open_child_directory(
                parent_descriptor,
                PUBLIC_SECTOR_DIRECTORY.name,
                reason="recovery_failed",
            )
        close_descriptor = True
    else:
        descriptor = output_descriptor
        close_descriptor = False
    try:
        for name in (PUBLIC_MARKDOWN_NAME, PUBLIC_SNAPSHOT_NAME):
            try:
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            except OSError:
                raise PublicSectorStoreError("recovery_failed") from None
            if not stat.S_ISREG(metadata.st_mode):
                raise PublicSectorStoreError("recovery_failed")
            try:
                os.unlink(name, dir_fd=descriptor)
            except OSError:
                raise PublicSectorStoreError("recovery_failed") from None
        os.fsync(descriptor)
    except OSError:
        raise PublicSectorStoreError("recovery_failed") from None
    finally:
        if close_descriptor:
            with suppress(OSError):
                os.close(descriptor)


def _remove_unpublished_directory(
    directory: Path | None,
    paths: _StorePaths,
    prefix: str,
    *,
    parent_descriptor: int | None = None,
) -> None:
    if directory is None:
        return
    name = directory.name
    if not _valid_transaction_name(name, prefix):
        raise PublicSectorStoreError("recovery_failed")
    if parent_descriptor is None:
        active_parent_descriptor = _open_directory_descriptor(
            paths.parent,
            reason="recovery_failed",
            expected_identity=paths.parent_identity,
        )
        close_parent_descriptor = True
    else:
        active_parent_descriptor = parent_descriptor
        close_parent_descriptor = False
    child_descriptor: int | None = None
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            child_descriptor = os.open(name, flags, dir_fd=active_parent_descriptor)
        except FileNotFoundError:
            return
        child_metadata = os.fstat(child_descriptor)
        if child_metadata.st_uid != os.getuid() or child_metadata.st_nlink < 2:
            raise PublicSectorStoreError("recovery_failed")
        entries = os.listdir(child_descriptor)
        if not set(entries).issubset({PUBLIC_MARKDOWN_NAME, PUBLIC_SNAPSHOT_NAME}):
            raise PublicSectorStoreError("recovery_failed")
        for entry in entries:
            metadata = os.stat(entry, dir_fd=child_descriptor, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise PublicSectorStoreError("recovery_failed")
            os.unlink(entry, dir_fd=child_descriptor)
        os.fsync(child_descriptor)
        os.close(child_descriptor)
        child_descriptor = None
        os.rmdir(name, dir_fd=active_parent_descriptor)
        os.fsync(active_parent_descriptor)
    except OSError:
        raise PublicSectorStoreError("recovery_failed") from None
    finally:
        if child_descriptor is not None:
            with suppress(OSError):
                os.close(child_descriptor)
        if close_parent_descriptor:
            with suppress(OSError):
                os.close(active_parent_descriptor)


def _cleanup_orphan_transaction_directories(
    paths: _StorePaths,
    *,
    parent_descriptor: int | None = None,
) -> None:
    if parent_descriptor is None:
        descriptor = _open_directory_descriptor(
            paths.parent,
            reason="recovery_failed",
            expected_identity=paths.parent_identity,
        )
        close_descriptor = True
    else:
        descriptor = parent_descriptor
        close_descriptor = False
    try:
        names = tuple(os.listdir(descriptor))
        for name in names:
            prefix = next(
                (
                    candidate
                    for candidate in (_PREPARED_PREFIX, _BACKUP_PREFIX)
                    if name.startswith(candidate)
                ),
                None,
            )
            if prefix is None:
                continue
            _remove_unpublished_directory(
                paths.parent / name,
                paths,
                prefix,
                parent_descriptor=descriptor,
            )
    except OSError:
        raise PublicSectorStoreError("recovery_failed") from None
    finally:
        if close_descriptor:
            with suppress(OSError):
                os.close(descriptor)


def _cleanup_atomic_temp_files(
    paths: _StorePaths,
    *,
    parent_descriptor: int | None = None,
) -> None:
    _cleanup_atomic_temp_files_in(
        paths.parent,
        prefixes=(f".{_TRANSACTION_MARKER_NAME}.",),
        directory_descriptor=parent_descriptor,
    )
    if parent_descriptor is None:
        if paths.output.is_symlink():
            raise PublicSectorStoreError("recovery_failed")
        output_exists = paths.output.exists()
    else:
        try:
            metadata = os.stat(
                PUBLIC_SECTOR_DIRECTORY.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            output_exists = False
        else:
            if not stat.S_ISDIR(metadata.st_mode):
                raise PublicSectorStoreError("recovery_failed")
            output_exists = True
    if output_exists:
        output_descriptor = (
            None
            if parent_descriptor is None
            else _open_child_directory(
                parent_descriptor,
                PUBLIC_SECTOR_DIRECTORY.name,
                reason="recovery_failed",
            )
        )
        try:
            _cleanup_atomic_temp_files_in(
                paths.output,
                prefixes=(f".{PUBLIC_MARKDOWN_NAME}.", f".{PUBLIC_SNAPSHOT_NAME}."),
                directory_descriptor=output_descriptor,
            )
        finally:
            if output_descriptor is not None:
                with suppress(OSError):
                    os.close(output_descriptor)


def _cleanup_atomic_temp_files_in(
    directory: Path,
    *,
    prefixes: tuple[str, ...],
    directory_descriptor: int | None = None,
) -> None:
    if directory_descriptor is None:
        descriptor = _open_directory_descriptor(directory, reason="recovery_failed")
        close_descriptor = True
    else:
        descriptor = directory_descriptor
        close_descriptor = False
    removed = False
    try:
        for name in os.listdir(descriptor):
            prefix = next((candidate for candidate in prefixes if name.startswith(candidate)), None)
            if prefix is None:
                continue
            suffix = name[len(prefix) :]
            if len(suffix) != 16 or any(
                character not in "0123456789abcdef" for character in suffix
            ):
                continue
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
            ):
                raise PublicSectorStoreError("recovery_failed")
            os.unlink(name, dir_fd=descriptor)
            removed = True
        if removed:
            os.fsync(descriptor)
    except OSError:
        raise PublicSectorStoreError("recovery_failed") from None
    finally:
        if close_descriptor:
            with suppress(OSError):
                os.close(descriptor)


def _transaction_directory(
    paths: _StorePaths,
    name: str,
    *,
    prefix: str,
    required: bool,
) -> Path | None:
    if not _valid_transaction_name(name, prefix):
        raise PublicSectorStoreError("recovery_failed")
    candidate = paths.parent / name
    if not candidate.exists():
        if required:
            raise PublicSectorStoreError("recovery_failed")
        return None
    try:
        if candidate.is_symlink() or not candidate.is_dir():
            raise PublicSectorStoreError("recovery_failed")
        if candidate.resolve(strict=True).parent != paths.parent:
            raise PublicSectorStoreError("recovery_failed")
    except OSError:
        raise PublicSectorStoreError("recovery_failed") from None
    return candidate


def _valid_transaction_name(name: str, prefix: str) -> bool:
    suffix = name[len(prefix) :] if name.startswith(prefix) else ""
    return (
        Path(name).name == name
        and 6 <= len(suffix) <= 32
        and all(character.isalnum() or character in "-_" for character in suffix)
    )


def _valid_snapshot_id(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        return False
    return all(character in "0123456789abcdef" for character in value[7:])


def _write_new_fsynced(path: Path, payload: bytes) -> None:
    parent_descriptor = _open_directory_descriptor(path.parent, reason="promotion_failed")
    try:
        _write_new_fsynced_at(parent_descriptor, path.name, payload)
    finally:
        with suppress(OSError):
            os.close(parent_descriptor)


def _write_new_fsynced_at(parent_descriptor: int, name: str, payload: bytes) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
            dir_fd=parent_descriptor,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise PublicSectorStoreError("promotion_failed") from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _write_atomic_fsynced(path: Path, payload: bytes) -> None:
    parent_descriptor = _open_directory_descriptor(path.parent, reason="promotion_failed")
    try:
        _write_atomic_fsynced_at(
            parent_descriptor,
            path.name,
            payload,
            reason="promotion_failed",
        )
    finally:
        with suppress(OSError):
            os.close(parent_descriptor)


def _write_atomic_fsynced_at(
    parent_descriptor: int,
    name: str,
    payload: bytes,
    *,
    reason: StoreErrorReason,
) -> None:
    temporary_name = f".{name}.{secrets.token_hex(8)}"
    descriptor: int | None = None
    try:
        try:
            target = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        except FileNotFoundError:
            target = None
        if target is not None and not stat.S_ISREG(target.st_mode):
            raise PublicSectorStoreError("path_invalid")
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=parent_descriptor,
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o644)
        os.replace(
            temporary_name,
            name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        os.fsync(parent_descriptor)
    except OSError:
        raise PublicSectorStoreError(reason) from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        with suppress(OSError):
            os.unlink(temporary_name, dir_fd=parent_descriptor)


def _fsync_directory(directory: Path) -> None:
    descriptor = _open_directory_descriptor(directory, reason="promotion_failed")
    try:
        os.fsync(descriptor)
    except OSError:
        raise PublicSectorStoreError("promotion_failed") from None
    finally:
        with suppress(OSError):
            os.close(descriptor)


def _open_directory_descriptor(
    path: Path,
    *,
    reason: StoreErrorReason,
    expected_identity: tuple[int, int] | None = None,
) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        path_metadata = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or not stat.S_ISDIR(path_metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (path_metadata.st_dev, path_metadata.st_ino)
            or (
                expected_identity is not None
                and (metadata.st_dev, metadata.st_ino) != expected_identity
            )
        ):
            raise OSError("directory identity changed")
        return descriptor
    except OSError:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise PublicSectorStoreError(reason) from None


def _open_child_directory(
    parent_descriptor: int,
    name: str,
    *,
    reason: StoreErrorReason,
) -> int:
    if Path(name).name != name:
        raise PublicSectorStoreError(reason)
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
        metadata = os.fstat(descriptor)
        path_metadata = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or not stat.S_ISDIR(path_metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (path_metadata.st_dev, path_metadata.st_ino)
        ):
            raise OSError("directory identity changed")
        return descriptor
    except OSError:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise PublicSectorStoreError(reason) from None


def _assert_directory_attached(
    path: Path,
    descriptor: int,
    *,
    reason: StoreErrorReason,
) -> None:
    try:
        metadata = os.fstat(descriptor)
        path_metadata = os.stat(path, follow_symlinks=False)
        if not stat.S_ISDIR(path_metadata.st_mode) or (metadata.st_dev, metadata.st_ino) != (
            path_metadata.st_dev,
            path_metadata.st_ino,
        ):
            raise OSError("directory identity changed")
    except OSError:
        raise PublicSectorStoreError(reason) from None


def _no_fault(_phase: str) -> None:
    return


__all__ = [
    "PUBLIC_MARKDOWN_NAME",
    "PUBLIC_SECTOR_DIRECTORY",
    "PUBLIC_SNAPSHOT_NAME",
    "PublicSectorStoreError",
    "hold_public_sector_last_good",
    "promote_public_sector_projection",
    "read_public_sector_projection",
]
