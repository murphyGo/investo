"""Deterministic private projections and recoverable pair transaction for u139.

The module has no network or public-pipeline dependency.  It renders only approved
aggregate fields from :class:`SectorDashboardSnapshot` and commits ``snapshot.json``
plus ``report.md`` to an explicit owner-only directory outside the repository.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from typing import Final, Self

from pydantic import ValidationError

from investo.models import (
    REGIME_BANDS_BPS,
    MetricMissingReason,
    MetricValue,
    PrivateArtifactSet,
    PrivateDiagnostic,
    SectorCoverageStatus,
    SectorDashboardSnapshot,
    SectorMetricName,
    SectorRecord,
    SectorRegime,
)

SNAPSHOT_NAME: Final[str] = "snapshot.json"
REPORT_NAME: Final[str] = "report.md"
_PROMOTION_SNAPSHOT_NAME: Final[str] = ".snapshot.json.promote"
_PROMOTION_REPORT_NAME: Final[str] = ".report.md.promote"
MAX_PROJECTION_BYTES: Final[int] = 2 * 1024 * 1024
MAX_MARKER_BYTES: Final[int] = 16 * 1024
_SNAPSHOT_ID_RE: Final[re.Pattern[str]] = re.compile(r"sha256:[0-9a-f]{64}")
_SNAPSHOT_MARKER_RE: Final[re.Pattern[str]] = re.compile(
    r"<!-- snapshot_id: (sha256:[0-9a-f]{64}) -->"
)
_REPORT_REQUIRED_LABELS: Final[tuple[str, ...]] = (
    "PRIVATE VALIDATION",
    "NAV 수익률 기준",
    "실제 시장 OHLCV 아님",
    "공개 게시 금지",
    "State Street NAV History (private input)",
)
_REPORT_FORBIDDEN_TERMS: Final[tuple[str, ...]] = (
    "가격수익률",
    "거래량",
    "거래대금",
    "자금 유입",
    "actual flow",
    "exchange volume",
    "dollar volume",
    "shares",
    "holdings",
    "earnings",
    "tradingview",
    "public ready",
    "license approval",
    "archive/",
    "site_docs/",
)
_SNAPSHOT_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "volume",
        "dollar_volume",
        "flow",
        "shares",
        "aum",
        "holdings",
        "earnings",
        "raw_rows",
        "raw_cells",
        "manifest_path",
        "workbook_path",
        "output_path",
        "public_ready",
        "publishable",
    }
)
_RANK_MISSING_REASONS: Final[frozenset[str]] = frozenset(
    {
        "coverage_insufficient",
        "warming_up",
        "insufficient_comparables",
        "insufficient_horizons",
    }
)
_REGIME_LABELS: Final[Mapping[SectorRegime, str]] = {
    SectorRegime.LEADING: "주도 (leading)",
    SectorRegime.WEAKENING: "둔화 (weakening)",
    SectorRegime.RECOVERING: "회복 (recovering)",
    SectorRegime.LAGGING: "부진 (lagging)",
    SectorRegime.INSUFFICIENT: "상태 계산 불가 (insufficient)",
}
_FULL_METRICS: Final[tuple[SectorMetricName, ...]] = (
    SectorMetricName.NAV_RETURN_1D,
    SectorMetricName.NAV_EXCESS_5D,
    SectorMetricName.NAV_EXCESS_21D,
    SectorMetricName.NAV_EXCESS_63D,
    SectorMetricName.NAV_RELATIVE_ACCELERATION_5D,
    SectorMetricName.NAV_REALIZED_VOLATILITY_20D,
    SectorMetricName.NAV_MAX_DRAWDOWN_20D,
)
_WARMING_METRICS: Final[tuple[SectorMetricName, ...]] = (
    SectorMetricName.NAV_RETURN_1D,
    SectorMetricName.NAV_RETURN_5D,
    SectorMetricName.NAV_EXCESS_1D,
    SectorMetricName.NAV_EXCESS_5D,
)
_FaultHook = Callable[[str], None]


class PrivateOutputRejectedError(ValueError):
    """A redacted output/path/policy rejection returned as CLI exit code 2."""

    def __init__(self) -> None:
        super().__init__("output.forbidden_path")


class PrivateTransactionError(RuntimeError):
    """A redacted transaction/recovery failure returned as CLI exit code 4."""

    def __init__(self) -> None:
        super().__init__("transaction.failed")


class _PrivateCleanupPendingError(PrivateTransactionError):
    """The committed pair is durable, but private cleanup needs recovery."""


@dataclass(frozen=True, slots=True)
class RenderedPrivateProjection:
    """Verified deterministic bytes for one immutable snapshot."""

    snapshot: SectorDashboardSnapshot
    snapshot_bytes: bytes
    report_bytes: bytes


@dataclass(frozen=True, slots=True)
class PrivateCommitResult:
    """Committed artifact paths and whether durable bytes changed."""

    artifacts: PrivateArtifactSet
    snapshot_id: str
    changed: bool


@dataclass(frozen=True, slots=True)
class _ValidatedPair:
    snapshot: SectorDashboardSnapshot
    snapshot_bytes: bytes
    report_bytes: bytes


@dataclass(frozen=True, slots=True)
class _MarkerState:
    phase: str
    prepared_name: str | None = None
    backup_name: str | None = None
    expected_snapshot_id: str | None = None
    backup_snapshot_id: str | None = None
    expected_report_sha256: str | None = None
    backup_report_sha256: str | None = None

    def as_bytes(self) -> bytes:
        payload = {
            "schema_version": 1,
            "phase": self.phase,
            "prepared_name": self.prepared_name,
            "backup_name": self.backup_name,
            "expected_snapshot_id": self.expected_snapshot_id,
            "backup_snapshot_id": self.backup_snapshot_id,
            "expected_report_sha256": self.expected_report_sha256,
            "backup_report_sha256": self.backup_report_sha256,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")


def _valid_marker_shape(state: _MarkerState) -> bool:
    if state.phase == "locked":
        return (
            state.prepared_name is None
            and state.backup_name is None
            and state.expected_snapshot_id is None
            and state.backup_snapshot_id is None
            and state.expected_report_sha256 is None
            and state.backup_report_sha256 is None
        )
    if (
        state.phase
        not in {
            "preparing",
            "backing_up",
            "prepared",
            "backup",
            "promoting",
            "snapshot_promoted",
            "report_promoted",
            "cleaning_up",
            "aborting",
            "recovered",
            "promotion_recovered",
            "rolling_back",
        }
        or state.prepared_name is None
        or state.expected_snapshot_id is None
        or _SNAPSHOT_ID_RE.fullmatch(state.expected_snapshot_id) is None
        or (
            state.backup_snapshot_id is not None
            and _SNAPSHOT_ID_RE.fullmatch(state.backup_snapshot_id) is None
        )
        or ((state.expected_snapshot_id is None) != (state.expected_report_sha256 is None))
        or ((state.backup_snapshot_id is None) != (state.backup_report_sha256 is None))
        or (
            state.expected_report_sha256 is not None
            and _SNAPSHOT_ID_RE.fullmatch(state.expected_report_sha256) is None
        )
        or (
            state.backup_report_sha256 is not None
            and _SNAPSHOT_ID_RE.fullmatch(state.backup_report_sha256) is None
        )
    ):
        return False
    if state.phase == "preparing":
        return state.backup_name is None
    if state.phase == "prepared":
        return state.backup_name is None and state.backup_snapshot_id is None
    if state.phase in {"backing_up", "backup", "rolling_back"}:
        return state.backup_name is not None and state.backup_snapshot_id is not None
    return (state.backup_name is None) == (state.backup_snapshot_id is None)


def _decode_marker_state(raw: bytes) -> _MarkerState:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        raise PrivateTransactionError from None
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "phase",
        "prepared_name",
        "backup_name",
        "expected_snapshot_id",
        "backup_snapshot_id",
        "expected_report_sha256",
        "backup_report_sha256",
    }:
        raise PrivateTransactionError
    if payload["schema_version"] != 1 or not isinstance(payload["phase"], str):
        raise PrivateTransactionError
    for key in (
        "prepared_name",
        "backup_name",
        "expected_snapshot_id",
        "backup_snapshot_id",
        "expected_report_sha256",
        "backup_report_sha256",
    ):
        if payload[key] is not None and not isinstance(payload[key], str):
            raise PrivateTransactionError
    state = _MarkerState(
        phase=payload["phase"],
        prepared_name=payload["prepared_name"],
        backup_name=payload["backup_name"],
        expected_snapshot_id=payload["expected_snapshot_id"],
        backup_snapshot_id=payload["backup_snapshot_id"],
        expected_report_sha256=payload["expected_report_sha256"],
        backup_report_sha256=payload["backup_report_sha256"],
    )
    if not _valid_marker_shape(state):
        raise PrivateTransactionError
    return state


def render_private_projection(snapshot: SectorDashboardSnapshot) -> RenderedPrivateProjection:
    """Create byte-identical JSON and Markdown projections from one snapshot."""

    without_id = snapshot.model_copy(update={"snapshot_id": None})
    digest = hashlib.sha256(_snapshot_json_bytes(without_id, include_id=False)).hexdigest()
    snapshot_id = f"sha256:{digest}"
    identified = without_id.model_copy(update={"snapshot_id": snapshot_id})
    snapshot_bytes = _snapshot_json_bytes(identified, include_id=True)
    report_bytes = _render_report(identified).encode("utf-8")
    projection = RenderedPrivateProjection(
        snapshot=identified,
        snapshot_bytes=snapshot_bytes,
        report_bytes=report_bytes,
    )
    verify_private_projection(snapshot_bytes, report_bytes)
    return projection


def verify_private_projection(snapshot_bytes: bytes, report_bytes: bytes) -> None:
    """Fail closed unless both bytes form the canonical approved private pair."""

    _validate_pair_bytes(snapshot_bytes, report_bytes)


def open_private_output_session(
    output_dir: Path,
    *,
    repository_root: Path,
) -> PrivateOutputSession:
    """Acquire one exclusive owner-only output session and recover it first."""

    return PrivateOutputSession(output_dir, repository_root=repository_root)


class PrivateOutputSession(AbstractContextManager["PrivateOutputSession"]):
    """Exclusive output target held across manifest validation, parsing, and commit."""

    def __init__(self, output_dir: Path, *, repository_root: Path) -> None:
        _require_supported_platform()
        self.repository_root = _resolved_repository(repository_root)
        self.output_dir = _prepare_output_directory(output_dir, self.repository_root)
        output_stat = _verify_owned_entry(self.output_dir, kind="directory", mode=0o700)
        self._output_identity = (output_stat.st_dev, output_stat.st_ino)
        self._output_fd = _open_private_directory(self.output_dir, self._output_identity)
        self._managed_fds: dict[str, tuple[int, tuple[int, int]]] = {}
        self.artifacts = PrivateArtifactSet(
            snapshot_path=self.output_dir / SNAPSHOT_NAME,
            report_path=self.output_dir / REPORT_NAME,
        )
        self._marker_path = (
            self.output_dir.parent / f".{self.output_dir.name}.sector-dashboard.transaction.json"
        )
        try:
            self._marker_fd, existed = _open_and_lock_marker(self._marker_path)
        except BaseException:
            os.close(self._output_fd)
            raise
        self._transaction_active = False
        try:
            if existed:
                self._recover_interrupted_transaction()
            self._write_marker(_MarkerState(phase="locked"))
        except (PrivateOutputRejectedError, PrivateTransactionError):
            self._close_fd_only()
            raise
        except Exception:
            self._close_fd_only()
            raise PrivateTransactionError from None
        except BaseException:
            self._close_fd_only()
            raise

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        preserve = self._transaction_active
        self._close(preserve_marker=preserve)

    def validate_input_paths(self, paths: Iterable[Path]) -> None:
        """Reject output/input overlap after manifest resolution, before workbook reads."""

        self._assert_output_identity()
        for path in paths:
            if not path.is_absolute():
                raise PrivateOutputRejectedError
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                raise PrivateOutputRejectedError from None
            if (
                resolved == self.output_dir
                or self.output_dir in resolved.parents
                or resolved in self.output_dir.parents
            ):
                raise PrivateOutputRejectedError

    def commit(
        self,
        snapshot: SectorDashboardSnapshot,
        *,
        replace: bool = False,
        _fault_hook: _FaultHook | None = None,
    ) -> PrivateCommitResult:
        """Commit a verified pair, preserving or recovering the prior valid pair."""

        hook = _fault_hook or _no_fault
        self._assert_output_identity()
        existing = _read_optional_valid_pair_at(self._output_fd)
        existing_snapshot_id = _snapshot_id(existing.snapshot) if existing is not None else None
        try:
            hook("render")
            projection = render_private_projection(snapshot)
            expected_report_sha256 = _bytes_sha256(projection.report_bytes)
            backup_report_sha256 = (
                _bytes_sha256(existing.report_bytes) if existing is not None else None
            )
            # Preserve the stable transaction marker even if the process is
            # interrupted in the tiny window between mkdtemp and phase journaling.
            self._transaction_active = True
            prepared_dir = self._create_managed_directory("prepared")
            self._write_marker(
                _MarkerState(
                    phase="preparing",
                    prepared_name=prepared_dir.name,
                    expected_snapshot_id=_snapshot_id(projection.snapshot),
                    backup_snapshot_id=existing_snapshot_id,
                    expected_report_sha256=expected_report_sha256,
                    backup_report_sha256=backup_report_sha256,
                )
            )
            prepared_fd = self._managed_fd(prepared_dir)
            _write_pair_at(
                prepared_fd,
                projection.snapshot_bytes,
                projection.report_bytes,
            )
            hook("prepared_fsync")
            prepared = _read_valid_pair_at(prepared_fd)
            if (
                prepared.snapshot.snapshot_id != projection.snapshot.snapshot_id
                or _bytes_sha256(prepared.report_bytes) != expected_report_sha256
            ):
                raise PrivateTransactionError

            current = _read_optional_valid_pair_at(self._output_fd)
            if (existing is None) != (current is None) or (
                existing is not None
                and current is not None
                and (
                    existing.snapshot_bytes != current.snapshot_bytes
                    or existing.report_bytes != current.report_bytes
                )
            ):
                raise PrivateTransactionError
            if existing is not None and (
                existing.snapshot_bytes == projection.snapshot_bytes
                and existing.report_bytes == projection.report_bytes
            ):
                self._remove_managed_directory(prepared_dir)
                self._transaction_active = False
                self._write_marker(_MarkerState(phase="locked"))
                return PrivateCommitResult(
                    artifacts=self.artifacts,
                    snapshot_id=_snapshot_id(projection.snapshot),
                    changed=False,
                )
            if existing is not None and not replace:
                self._remove_managed_directory(prepared_dir)
                self._transaction_active = False
                self._write_marker(_MarkerState(phase="locked"))
                raise PrivateOutputRejectedError

            backup_dir: Path | None = None
            backup_snapshot_id = existing_snapshot_id
            if existing is not None:
                backup_dir = self._create_managed_directory("backup")
                self._write_marker(
                    _MarkerState(
                        phase="backing_up",
                        prepared_name=prepared_dir.name,
                        backup_name=backup_dir.name,
                        expected_snapshot_id=_snapshot_id(projection.snapshot),
                        backup_snapshot_id=backup_snapshot_id,
                        expected_report_sha256=expected_report_sha256,
                        backup_report_sha256=backup_report_sha256,
                    )
                )
                backup_fd = self._managed_fd(backup_dir)
                _write_pair_at(backup_fd, existing.snapshot_bytes, existing.report_bytes)
                hook("backup")
                stored_backup = _read_valid_pair_at(backup_fd)
                if (
                    stored_backup.snapshot.snapshot_id != backup_snapshot_id
                    or _bytes_sha256(stored_backup.report_bytes) != backup_report_sha256
                ):
                    raise PrivateTransactionError
                phase = "backup"
            else:
                phase = "prepared"
            self._write_marker(
                _MarkerState(
                    phase=phase,
                    prepared_name=prepared_dir.name,
                    backup_name=backup_dir.name if backup_dir is not None else None,
                    expected_snapshot_id=_snapshot_id(projection.snapshot),
                    backup_snapshot_id=backup_snapshot_id,
                    expected_report_sha256=expected_report_sha256,
                    backup_report_sha256=backup_report_sha256,
                )
            )
            hook("prepared")

            cleanup_complete = self._promote_prepared(
                prepared_dir,
                backup_dir,
                projection.snapshot.snapshot_id,
                backup_snapshot_id,
                expected_report_sha256,
                backup_report_sha256,
                hook,
            )
            self._transaction_active = not cleanup_complete
            return PrivateCommitResult(
                artifacts=self.artifacts,
                snapshot_id=_snapshot_id(projection.snapshot),
                changed=True,
            )
        except PrivateOutputRejectedError:
            if self._transaction_active:
                try:
                    self._rollback_caught_failure()
                except Exception:
                    raise PrivateTransactionError from None
            raise
        except Exception:
            if self._transaction_active:
                try:
                    self._rollback_caught_failure()
                except Exception:
                    raise PrivateTransactionError from None
            raise PrivateTransactionError from None

    def _promote_prepared(
        self,
        prepared_dir: Path,
        backup_dir: Path | None,
        expected_snapshot_id: str | None,
        backup_snapshot_id: str | None,
        expected_report_sha256: str,
        backup_report_sha256: str | None,
        hook: _FaultHook,
    ) -> bool:
        if expected_snapshot_id is None:
            raise PrivateTransactionError
        self._assert_output_identity()
        current = _read_optional_valid_pair_at(self._output_fd)
        current_id = _snapshot_id(current.snapshot) if current is not None else None
        if current_id != backup_snapshot_id:
            raise PrivateTransactionError
        self._write_marker(
            _MarkerState(
                phase="promoting",
                prepared_name=prepared_dir.name,
                backup_name=backup_dir.name if backup_dir is not None else None,
                expected_snapshot_id=expected_snapshot_id,
                backup_snapshot_id=backup_snapshot_id,
                expected_report_sha256=expected_report_sha256,
                backup_report_sha256=backup_report_sha256,
            )
        )
        prepared_fd = self._managed_fd(prepared_dir)
        prepared = _read_valid_pair_at(prepared_fd)
        if (
            prepared.snapshot.snapshot_id != expected_snapshot_id
            or _bytes_sha256(prepared.report_bytes) != expected_report_sha256
        ):
            raise PrivateTransactionError
        if backup_dir is not None:
            backup = _read_valid_pair_at(self._managed_fd(backup_dir))
            if (
                backup.snapshot.snapshot_id != backup_snapshot_id
                or _bytes_sha256(backup.report_bytes) != backup_report_sha256
            ):
                raise PrivateTransactionError
        _write_promotion_copies_at(prepared_fd, prepared)
        os.replace(
            _PROMOTION_SNAPSHOT_NAME,
            SNAPSHOT_NAME,
            src_dir_fd=prepared_fd,
            dst_dir_fd=self._output_fd,
        )
        _chmod_exact_at(self._output_fd, SNAPSHOT_NAME, 0o600)
        os.fsync(self._output_fd)
        self._write_marker(
            _MarkerState(
                phase="snapshot_promoted",
                prepared_name=prepared_dir.name,
                backup_name=backup_dir.name if backup_dir is not None else None,
                expected_snapshot_id=expected_snapshot_id,
                backup_snapshot_id=backup_snapshot_id,
                expected_report_sha256=expected_report_sha256,
                backup_report_sha256=backup_report_sha256,
            )
        )
        hook("snapshot_promote")
        self._assert_output_identity()
        os.replace(
            _PROMOTION_REPORT_NAME,
            REPORT_NAME,
            src_dir_fd=prepared_fd,
            dst_dir_fd=self._output_fd,
        )
        _chmod_exact_at(self._output_fd, REPORT_NAME, 0o600)
        os.fsync(self._output_fd)
        self._write_marker(
            _MarkerState(
                phase="report_promoted",
                prepared_name=prepared_dir.name,
                backup_name=backup_dir.name if backup_dir is not None else None,
                expected_snapshot_id=expected_snapshot_id,
                backup_snapshot_id=backup_snapshot_id,
                expected_report_sha256=expected_report_sha256,
                backup_report_sha256=backup_report_sha256,
            )
        )
        hook("report_promote")
        current = _read_valid_pair_at(self._output_fd)
        if current.snapshot.snapshot_id != expected_snapshot_id:
            raise PrivateTransactionError
        hook("verify")
        self._write_marker(
            _MarkerState(
                phase="cleaning_up",
                prepared_name=prepared_dir.name,
                backup_name=backup_dir.name if backup_dir is not None else None,
                expected_snapshot_id=expected_snapshot_id,
                backup_snapshot_id=backup_snapshot_id,
                expected_report_sha256=expected_report_sha256,
                backup_report_sha256=backup_report_sha256,
            )
        )
        try:
            self._remove_validated_managed_pair(
                prepared_dir,
                expected_snapshot_id,
                expected_report_sha256,
                cleanup_committed=True,
            )
            if backup_dir is not None:
                if backup_snapshot_id is None:
                    raise PrivateTransactionError
                if backup_report_sha256 is None:
                    raise PrivateTransactionError
                self._remove_validated_managed_pair(
                    backup_dir,
                    backup_snapshot_id,
                    backup_report_sha256,
                    cleanup_committed=True,
                )
        except _PrivateCleanupPendingError:
            return False
        self._write_marker(_MarkerState(phase="locked"))
        return True

    def _rollback_caught_failure(self) -> None:
        self._assert_output_identity()
        state = self._read_marker()
        if state.phase == "locked":
            self._cleanup_locked_orphans()
            self._transaction_active = False
            return
        backup_dir = self._managed_directory(state.backup_name, "backup")
        prepared_dir = self._managed_directory(state.prepared_name, "prepared")
        current = _probe_valid_pair_at(self._output_fd)
        prepared = self._probe_managed_pair(prepared_dir)
        backup = self._probe_managed_pair(backup_dir)
        if isinstance(prepared, _ValidatedPair) and (
            prepared.snapshot.snapshot_id != state.expected_snapshot_id
            or _bytes_sha256(prepared.report_bytes) != state.expected_report_sha256
        ):
            raise PrivateTransactionError
        if isinstance(backup, _ValidatedPair) and (
            backup.snapshot.snapshot_id != state.backup_snapshot_id
            or _bytes_sha256(backup.report_bytes) != state.backup_report_sha256
        ):
            raise PrivateTransactionError
        self._validate_recovery_current(state, current, prepared, backup)
        if state.phase in {"preparing", "backing_up"}:
            if current is False:
                if not isinstance(backup, _ValidatedPair) or backup_dir is None:
                    raise PrivateTransactionError
                self._restore_backup(state, backup_dir, backup)
            for directory in (prepared_dir, backup_dir):
                if directory is not None and _lexically_present(directory):
                    self._remove_managed_directory(directory)
            self._cleanup_locked_orphans()
            self._write_marker(_MarkerState(phase="locked"))
            self._transaction_active = False
            return
        if backup_dir is not None:
            if not isinstance(backup, _ValidatedPair):
                raise PrivateTransactionError
            self._restore_backup(state, backup_dir, backup)
        else:
            self._write_marker(
                _MarkerState(
                    phase="aborting",
                    prepared_name=state.prepared_name,
                    expected_snapshot_id=state.expected_snapshot_id,
                    expected_report_sha256=state.expected_report_sha256,
                )
            )
            _unlink_projection_if_present(
                self.artifacts.snapshot_path,
                directory_fd=self._output_fd,
            )
            _unlink_projection_if_present(
                self.artifacts.report_path,
                directory_fd=self._output_fd,
            )
            os.fsync(self._output_fd)
        if prepared_dir is not None:
            if state.expected_snapshot_id is None or state.expected_report_sha256 is None:
                raise PrivateTransactionError
            self._remove_validated_managed_pair(
                prepared_dir,
                state.expected_snapshot_id,
                state.expected_report_sha256,
            )
        if backup_dir is not None and _lexically_present(backup_dir):
            if state.backup_snapshot_id is None or state.backup_report_sha256 is None:
                raise PrivateTransactionError
            self._remove_validated_managed_pair(
                backup_dir,
                state.backup_snapshot_id,
                state.backup_report_sha256,
            )
        self._write_marker(_MarkerState(phase="locked"))
        self._transaction_active = False

    def _restore_backup(
        self,
        state: _MarkerState,
        backup_dir: Path,
        backup: _ValidatedPair,
    ) -> None:
        backup_id = _snapshot_id(backup.snapshot)
        if (
            state.backup_snapshot_id != backup_id
            or _bytes_sha256(backup.report_bytes) != state.backup_report_sha256
        ):
            raise PrivateTransactionError
        self._write_marker(
            _MarkerState(
                phase="rolling_back",
                prepared_name=state.prepared_name,
                backup_name=state.backup_name,
                expected_snapshot_id=state.expected_snapshot_id,
                backup_snapshot_id=backup_id,
                expected_report_sha256=state.expected_report_sha256,
                backup_report_sha256=state.backup_report_sha256,
            )
        )
        _replace_pair_from(
            backup_dir,
            self.output_dir,
            source_fd=self._managed_fd(backup_dir),
            expected_source_snapshot_id=backup_id,
            target_fd=self._output_fd,
        )
        restored = _read_valid_pair_at(self._output_fd)
        if restored.snapshot.snapshot_id != backup_id:
            raise PrivateTransactionError
        self._write_marker(
            _MarkerState(
                phase="recovered",
                prepared_name=state.prepared_name,
                backup_name=state.backup_name,
                expected_snapshot_id=state.expected_snapshot_id,
                backup_snapshot_id=backup_id,
                expected_report_sha256=state.expected_report_sha256,
                backup_report_sha256=state.backup_report_sha256,
            )
        )

    def _recover_interrupted_transaction(self) -> None:
        self._assert_output_identity()
        state = self._read_marker()
        if state.phase == "locked":
            if any(
                value is not None
                for value in (
                    state.prepared_name,
                    state.backup_name,
                    state.expected_snapshot_id,
                    state.backup_snapshot_id,
                )
            ):
                raise PrivateTransactionError
            self._cleanup_locked_orphans()
            return
        prepared_dir = self._managed_directory(state.prepared_name, "prepared")
        backup_dir = self._managed_directory(state.backup_name, "backup")
        current = _probe_valid_pair_at(self._output_fd)
        prepared = self._probe_managed_pair(prepared_dir)
        backup = self._probe_managed_pair(backup_dir)
        if isinstance(prepared, _ValidatedPair) and (
            prepared.snapshot.snapshot_id != state.expected_snapshot_id
            or _bytes_sha256(prepared.report_bytes) != state.expected_report_sha256
        ):
            raise PrivateTransactionError
        if isinstance(backup, _ValidatedPair) and (
            backup.snapshot.snapshot_id != state.backup_snapshot_id
            or _bytes_sha256(backup.report_bytes) != state.backup_report_sha256
        ):
            raise PrivateTransactionError
        self._validate_recovery_current(state, current, prepared, backup)

        if state.phase == "aborting":
            expected = state.expected_snapshot_id
            if isinstance(current, _ValidatedPair):
                if current.snapshot.snapshot_id != expected:
                    raise PrivateTransactionError
                _unlink_projection_if_present(
                    self.artifacts.snapshot_path,
                    directory_fd=self._output_fd,
                )
                _unlink_projection_if_present(
                    self.artifacts.report_path,
                    directory_fd=self._output_fd,
                )
                os.fsync(self._output_fd)
            elif current is False:
                if expected is None or not _partial_pair_matches_expected_at(
                    self._output_fd, expected
                ):
                    raise PrivateTransactionError
                _unlink_projection_if_present(
                    self.artifacts.snapshot_path,
                    directory_fd=self._output_fd,
                )
                _unlink_projection_if_present(
                    self.artifacts.report_path,
                    directory_fd=self._output_fd,
                )
                os.fsync(self._output_fd)
            self._cleanup_recovery_directories(
                prepared_dir,
                backup_dir,
                expected_prepared_id=state.expected_snapshot_id,
                expected_backup_id=state.backup_snapshot_id,
                expected_prepared_report_sha256=state.expected_report_sha256,
                expected_backup_report_sha256=state.backup_report_sha256,
                allow_partial=True,
            )
            self._write_marker(_MarkerState(phase="locked"))
            return
        if state.phase in {"recovered", "promotion_recovered"}:
            required_current_id = (
                state.backup_snapshot_id
                if state.phase == "recovered"
                else state.expected_snapshot_id
            )
            if (
                not isinstance(current, _ValidatedPair)
                or current.snapshot.snapshot_id != required_current_id
            ):
                raise PrivateTransactionError
            self._cleanup_recovery_directories(
                prepared_dir,
                backup_dir,
                expected_prepared_id=state.expected_snapshot_id,
                expected_backup_id=state.backup_snapshot_id,
                expected_prepared_report_sha256=state.expected_report_sha256,
                expected_backup_report_sha256=state.backup_report_sha256,
                allow_partial=True,
            )
            self._write_marker(_MarkerState(phase="locked"))
            return
        if state.phase == "cleaning_up":
            if (
                not isinstance(current, _ValidatedPair)
                or current.snapshot.snapshot_id != state.expected_snapshot_id
            ):
                raise PrivateTransactionError
            self._cleanup_recovery_directories(
                prepared_dir,
                backup_dir,
                expected_prepared_id=state.expected_snapshot_id,
                expected_backup_id=state.backup_snapshot_id,
                expected_prepared_report_sha256=state.expected_report_sha256,
                expected_backup_report_sha256=state.backup_report_sha256,
                allow_partial=True,
            )
            self._write_marker(_MarkerState(phase="locked"))
            return
        if state.phase == "rolling_back":
            if (
                prepared is False
                or not isinstance(backup, _ValidatedPair)
                or backup_dir is None
                or backup.snapshot.snapshot_id != state.backup_snapshot_id
            ):
                raise PrivateTransactionError
            self._restore_backup(state, backup_dir, backup)
            self._cleanup_recovery_directories(
                prepared_dir,
                backup_dir,
                expected_prepared_id=state.expected_snapshot_id,
                expected_backup_id=state.backup_snapshot_id,
                expected_prepared_report_sha256=state.expected_report_sha256,
                expected_backup_report_sha256=state.backup_report_sha256,
                allow_partial=True,
            )
            self._write_marker(_MarkerState(phase="locked"))
            return
        if state.phase in {"preparing", "backing_up"}:
            if current is False:
                raise PrivateTransactionError
            self._cleanup_recovery_directories(prepared_dir, backup_dir)
            self._cleanup_locked_orphans()
            self._write_marker(_MarkerState(phase="locked"))
            return

        expected = state.expected_snapshot_id
        if expected is None or _SNAPSHOT_ID_RE.fullmatch(expected) is None:
            raise PrivateTransactionError
        if prepared is False or backup is False:
            raise PrivateTransactionError
        if isinstance(current, _ValidatedPair) and current.snapshot.snapshot_id == expected:
            if (
                not isinstance(prepared, _ValidatedPair)
                or prepared.snapshot.snapshot_id != expected
            ):
                raise PrivateTransactionError
            if state.backup_name is not None and not isinstance(backup, _ValidatedPair):
                raise PrivateTransactionError
            self._write_marker(
                _MarkerState(
                    phase="cleaning_up",
                    prepared_name=state.prepared_name,
                    backup_name=state.backup_name,
                    expected_snapshot_id=state.expected_snapshot_id,
                    backup_snapshot_id=state.backup_snapshot_id,
                    expected_report_sha256=state.expected_report_sha256,
                    backup_report_sha256=state.backup_report_sha256,
                )
            )
            self._cleanup_recovery_directories(
                prepared_dir,
                backup_dir,
                expected_prepared_id=state.expected_snapshot_id,
                expected_backup_id=state.backup_snapshot_id,
                expected_prepared_report_sha256=state.expected_report_sha256,
                expected_backup_report_sha256=state.backup_report_sha256,
                allow_partial=True,
            )
            self._write_marker(_MarkerState(phase="locked"))
            return
        if (
            prepared_dir is not None
            and isinstance(prepared, _ValidatedPair)
            and prepared.snapshot.snapshot_id == expected
            and not (
                state.phase == "prepared"
                and isinstance(current, _ValidatedPair)
                and current.snapshot.snapshot_id != expected
            )
        ):
            try:
                _replace_pair_from(
                    prepared_dir,
                    self.output_dir,
                    source_fd=self._managed_fd(prepared_dir),
                    expected_source_snapshot_id=expected,
                    target_fd=self._output_fd,
                )
                promoted = _read_valid_pair_at(self._output_fd)
                if promoted.snapshot.snapshot_id != expected:
                    raise PrivateTransactionError
            except Exception:
                if isinstance(backup, _ValidatedPair) and backup_dir is not None:
                    self._restore_backup(state, backup_dir, backup)
                    self._cleanup_recovery_directories(
                        prepared_dir,
                        backup_dir,
                        expected_prepared_id=state.expected_snapshot_id,
                        expected_backup_id=state.backup_snapshot_id,
                        expected_prepared_report_sha256=state.expected_report_sha256,
                        expected_backup_report_sha256=state.backup_report_sha256,
                        allow_partial=True,
                    )
                    self._write_marker(_MarkerState(phase="locked"))
                    return
                else:
                    raise PrivateTransactionError from None
            self._write_marker(
                _MarkerState(
                    phase="promotion_recovered",
                    prepared_name=state.prepared_name,
                    backup_name=state.backup_name,
                    expected_snapshot_id=expected,
                    backup_snapshot_id=state.backup_snapshot_id,
                    expected_report_sha256=state.expected_report_sha256,
                    backup_report_sha256=state.backup_report_sha256,
                )
            )
            self._cleanup_recovery_directories(
                prepared_dir,
                backup_dir,
                expected_prepared_id=state.expected_snapshot_id,
                expected_backup_id=state.backup_snapshot_id,
                expected_prepared_report_sha256=state.expected_report_sha256,
                expected_backup_report_sha256=state.backup_report_sha256,
                allow_partial=True,
            )
            self._write_marker(_MarkerState(phase="locked"))
            return
        raise PrivateTransactionError

    def _validate_recovery_current(
        self,
        state: _MarkerState,
        current: _ValidatedPair | bool | None,
        prepared: _ValidatedPair | bool | None,
        backup_pair: _ValidatedPair | bool | None,
    ) -> None:
        current_id = current.snapshot.snapshot_id if isinstance(current, _ValidatedPair) else None
        expected = state.expected_snapshot_id
        backup = state.backup_snapshot_id
        known_pairs = tuple(
            pair
            for pair, required_id in (
                (prepared, expected),
                (backup_pair, backup),
            )
            if isinstance(pair, _ValidatedPair) and pair.snapshot.snapshot_id == required_id
        )
        if state.phase == "preparing":
            if (backup is None and current is not None) or (
                backup is not None and current_id != backup
            ):
                raise PrivateTransactionError
            return
        if state.phase == "prepared":
            if current is not None:
                raise PrivateTransactionError
            return
        if state.phase in {"backing_up", "backup"}:
            if backup is None or current_id != backup:
                raise PrivateTransactionError
            return
        if state.phase == "promoting":
            if current_id == backup:
                return
            if current is False and _partial_output_matches_known_pairs_at(
                self._output_fd, known_pairs
            ):
                return
            raise PrivateTransactionError
        if state.phase == "snapshot_promoted":
            if current_id == expected:
                return
            if current is False and _partial_output_matches_known_pairs_at(
                self._output_fd, known_pairs
            ):
                return
            raise PrivateTransactionError
        if state.phase in {"report_promoted", "cleaning_up", "promotion_recovered"}:
            if current_id != expected:
                raise PrivateTransactionError
            return
        if state.phase == "rolling_back":
            if current_id in {expected, backup} and current_id is not None:
                return
            if current is False and _partial_output_matches_known_pairs_at(
                self._output_fd,
                known_pairs,
            ):
                return
            raise PrivateTransactionError
        if state.phase == "recovered":
            if backup is None or current_id != backup:
                raise PrivateTransactionError
            return
        if state.phase == "aborting":
            if current is None or current_id == expected:
                return
            if current is False and _partial_output_matches_known_pairs_at(
                self._output_fd, known_pairs
            ):
                return
            raise PrivateTransactionError
        raise PrivateTransactionError

    def _cleanup_recovery_directories(
        self,
        prepared_dir: Path | None,
        backup_dir: Path | None,
        *,
        expected_prepared_id: str | None = None,
        expected_backup_id: str | None = None,
        expected_prepared_report_sha256: str | None = None,
        expected_backup_report_sha256: str | None = None,
        allow_partial: bool = False,
    ) -> None:
        for directory, expected_id, report_sha256 in (
            (
                prepared_dir,
                expected_prepared_id,
                expected_prepared_report_sha256,
            ),
            (backup_dir, expected_backup_id, expected_backup_report_sha256),
        ):
            if directory is not None and _lexically_present(directory):
                if expected_id is None:
                    self._remove_managed_directory(directory)
                else:
                    if report_sha256 is None:
                        raise PrivateTransactionError
                    self._remove_validated_managed_pair(
                        directory,
                        expected_id,
                        report_sha256,
                        allow_partial=allow_partial,
                    )

    def _cleanup_locked_orphans(self) -> None:
        """Remove only empty, owned temp dirs left before their first journal entry."""

        prefixes = tuple(f".{self.output_dir.name}.{kind}-" for kind in ("prepared", "backup"))
        try:
            candidates = tuple(
                path for path in self.output_dir.parent.iterdir() if path.name.startswith(prefixes)
            )
        except OSError:
            raise PrivateTransactionError from None
        if len(candidates) > 2:
            raise PrivateTransactionError
        for directory in candidates:
            try:
                _verify_owned_entry(directory, kind="directory", mode=0o700)
                directory_fd = self._pin_managed_directory(directory)
                if os.listdir(directory_fd):
                    raise PrivateTransactionError
                self._remove_managed_directory(directory)
            except PrivateTransactionError:
                raise
            except (OSError, PrivateOutputRejectedError):
                raise PrivateTransactionError from None

    def _create_managed_directory(self, kind: str) -> Path:
        prefix = f".{self.output_dir.name}.{kind}-"
        created: Path | None = None
        identity: tuple[int, int] | None = None
        try:
            created = Path(tempfile.mkdtemp(prefix=prefix, dir=self.output_dir.parent))
            initial = created.lstat()
            if not stat.S_ISDIR(initial.st_mode) or initial.st_uid != os.getuid():
                raise OSError
            identity = (initial.st_dev, initial.st_ino)
            os.chmod(created, 0o700)
            _verify_owned_entry(created, kind="directory", mode=0o700)
            self._pin_managed_directory(created)
            return created
        except (OSError, PrivateOutputRejectedError):
            if created is not None and identity is not None:
                try:
                    current = created.lstat()
                    if (
                        stat.S_ISDIR(current.st_mode)
                        and not stat.S_ISLNK(current.st_mode)
                        and current.st_uid == os.getuid()
                        and (current.st_dev, current.st_ino) == identity
                        and not any(created.iterdir())
                    ):
                        created.rmdir()
                        _fsync_directory(created.parent)
                except (OSError, PrivateTransactionError):
                    pass
            raise PrivateTransactionError from None

    def _managed_directory(self, name: str | None, kind: str) -> Path | None:
        if name is None:
            return None
        prefix = f".{self.output_dir.name}.{kind}-"
        if not name.startswith(prefix) or name in {".", ".."} or "/" in name or "\\" in name:
            raise PrivateTransactionError
        path = self.output_dir.parent / name
        if not _lexically_present(path):
            return path
        try:
            _verify_owned_entry(path, kind="directory", mode=0o700)
            if path.parent.resolve(strict=True) != self.output_dir.parent:
                raise PrivateTransactionError
            self._pin_managed_directory(path)
        except PrivateTransactionError:
            raise
        except (OSError, PrivateOutputRejectedError):
            raise PrivateTransactionError from None
        return path

    def _pin_managed_directory(self, directory: Path) -> int:
        existing = self._managed_fds.get(directory.name)
        if existing is not None:
            return self._managed_fd(directory)
        entry = _verify_owned_entry(directory, kind="directory", mode=0o700)
        identity = (entry.st_dev, entry.st_ino)
        descriptor = _open_private_directory(directory, identity)
        self._managed_fds[directory.name] = (descriptor, identity)
        return descriptor

    def _managed_fd(self, directory: Path) -> int:
        held = self._managed_fds.get(directory.name)
        if held is None:
            raise PrivateTransactionError
        descriptor, identity = held
        try:
            descriptor_stat = os.fstat(descriptor)
            path_stat = directory.lstat()
        except OSError:
            raise PrivateTransactionError from None
        if (
            not stat.S_ISDIR(descriptor_stat.st_mode)
            or descriptor_stat.st_uid != os.getuid()
            or stat.S_IMODE(descriptor_stat.st_mode) != 0o700
            or (descriptor_stat.st_dev, descriptor_stat.st_ino) != identity
            or stat.S_ISLNK(path_stat.st_mode)
            or (path_stat.st_dev, path_stat.st_ino) != identity
        ):
            raise PrivateTransactionError
        return descriptor

    def _probe_managed_pair(self, directory: Path | None) -> _ValidatedPair | bool | None:
        if directory is None:
            return None
        try:
            return _read_optional_valid_pair_at(self._managed_fd(directory))
        except (PrivateOutputRejectedError, PrivateTransactionError):
            return False

    def _remove_managed_directory(self, directory: Path) -> None:
        descriptor = self._managed_fd(directory)
        try:
            _remove_managed_directory(directory, directory_fd=descriptor)
        except PrivateTransactionError:
            if not _lexically_present(directory):
                os.close(descriptor)
                self._managed_fds.pop(directory.name, None)
                raise _PrivateCleanupPendingError from None
            raise
        os.close(descriptor)
        self._managed_fds.pop(directory.name, None)

    def _remove_validated_managed_pair(
        self,
        directory: Path,
        expected_snapshot_id: str,
        expected_report_sha256: str,
        *,
        allow_partial: bool = False,
        cleanup_committed: bool = False,
    ) -> None:
        descriptor = self._managed_fd(directory)
        try:
            pair = _read_valid_pair_at(descriptor)
        except (PrivateOutputRejectedError, PrivateTransactionError):
            if not allow_partial or not _partial_managed_cleanup_matches_at(
                descriptor,
                expected_snapshot_id,
                expected_report_sha256,
            ):
                raise PrivateTransactionError from None
        else:
            if (
                pair.snapshot.snapshot_id != expected_snapshot_id
                or _bytes_sha256(pair.report_bytes) != expected_report_sha256
            ):
                raise PrivateTransactionError
        try:
            self._remove_managed_directory(directory)
        except _PrivateCleanupPendingError:
            raise
        except (OSError, PrivateTransactionError):
            if cleanup_committed and self._managed_fd(directory) == descriptor:
                raise _PrivateCleanupPendingError from None
            raise

    def _write_marker(self, state: _MarkerState) -> None:
        # An append-only, newline-committed journal keeps the same locked inode.
        # A crash can leave only an incomplete trailing record; the prior complete
        # phase remains recoverable and is always conservative enough to replay.
        data = state.as_bytes() + b"\n"
        try:
            self._assert_marker_identity()
            file_stat = os.fstat(self._marker_fd)
            if file_stat.st_size + len(data) > MAX_MARKER_BYTES:
                raise PrivateTransactionError
            os.lseek(self._marker_fd, 0, os.SEEK_END)
            _write_all(self._marker_fd, data)
            os.fsync(self._marker_fd)
            self._assert_marker_identity()
            _fsync_directory(self._marker_path.parent)
        except OSError:
            raise PrivateTransactionError from None

    def _read_marker(self) -> _MarkerState:
        try:
            self._assert_marker_identity()
            file_stat = os.fstat(self._marker_fd)
            if file_stat.st_size > MAX_MARKER_BYTES:
                raise PrivateTransactionError
            os.lseek(self._marker_fd, 0, os.SEEK_SET)
            raw = os.read(self._marker_fd, MAX_MARKER_BYTES + 1)
        except OSError:
            raise PrivateTransactionError from None
        records = raw.splitlines(keepends=True)
        if not records:
            return _MarkerState(phase="locked")
        state: _MarkerState | None = None
        valid_size = 0
        for index, record in enumerate(records):
            if not record.endswith(b"\n"):
                if index != len(records) - 1:
                    raise PrivateTransactionError
                break
            state = _decode_marker_state(record[:-1])
            valid_size += len(record)
        if state is None:
            initial_record = _MarkerState(phase="locked").as_bytes() + b"\n"
            if len(records) != 1 or not raw or not initial_record.startswith(raw):
                raise PrivateTransactionError
            try:
                os.ftruncate(self._marker_fd, 0)
                os.fsync(self._marker_fd)
                self._assert_marker_identity()
            except OSError:
                raise PrivateTransactionError from None
            return _MarkerState(phase="locked")
        if valid_size != len(raw):
            try:
                os.ftruncate(self._marker_fd, valid_size)
                os.fsync(self._marker_fd)
                self._assert_marker_identity()
            except OSError:
                raise PrivateTransactionError from None
        return state

    def _assert_output_identity(self) -> None:
        try:
            current = self.output_dir.lstat()
            descriptor = os.fstat(self._output_fd)
        except OSError:
            raise PrivateTransactionError from None
        if (
            not stat.S_ISDIR(current.st_mode)
            or stat.S_ISLNK(current.st_mode)
            or current.st_uid != os.getuid()
            or stat.S_IMODE(current.st_mode) != 0o700
            or (current.st_dev, current.st_ino) != self._output_identity
            or not stat.S_ISDIR(descriptor.st_mode)
            or descriptor.st_uid != os.getuid()
            or stat.S_IMODE(descriptor.st_mode) != 0o700
            or (descriptor.st_dev, descriptor.st_ino) != self._output_identity
        ):
            raise PrivateTransactionError

    def _assert_marker_identity(self) -> None:
        try:
            descriptor_stat = os.fstat(self._marker_fd)
            path_stat = self._marker_path.lstat()
        except OSError:
            raise PrivateTransactionError from None
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
            or stat.S_ISLNK(path_stat.st_mode)
            or descriptor_stat.st_uid != os.getuid()
            or stat.S_IMODE(descriptor_stat.st_mode) != 0o600
            or descriptor_stat.st_nlink != 1
            or descriptor_stat.st_dev != path_stat.st_dev
            or descriptor_stat.st_ino != path_stat.st_ino
            or path_stat.st_nlink != 1
        ):
            raise PrivateTransactionError

    def _close(self, *, preserve_marker: bool) -> None:
        try:
            if not preserve_marker:
                marker_stat = self._marker_path.lstat()
                descriptor_stat = os.fstat(self._marker_fd)
                if (
                    stat.S_ISREG(marker_stat.st_mode)
                    and marker_stat.st_nlink == 1
                    and descriptor_stat.st_nlink == 1
                    and marker_stat.st_dev == descriptor_stat.st_dev
                    and marker_stat.st_ino == descriptor_stat.st_ino
                ):
                    self._marker_path.unlink()
                    _fsync_directory(self._marker_path.parent)
        except OSError:
            if not preserve_marker:
                raise PrivateTransactionError from None
        finally:
            self._close_fd_only()

    def _close_fd_only(self) -> None:
        for descriptor, _identity in self._managed_fds.values():
            with suppress(OSError):
                os.close(descriptor)
        self._managed_fds.clear()
        with suppress(OSError):
            fcntl.flock(self._marker_fd, fcntl.LOCK_UN)
        with suppress(OSError):
            os.close(self._marker_fd)
        with suppress(OSError):
            os.close(self._output_fd)


def _render_report(snapshot: SectorDashboardSnapshot) -> str:
    lines = ["# 미국 섹터 코어 레이더", "", *_render_banner(), *_render_coverage(snapshot)]
    status = snapshot.coverage.status
    if status in (SectorCoverageStatus.NORMAL, SectorCoverageStatus.PARTIAL):
        lines.extend(_render_summary(snapshot))
        lines.extend(_render_full_table(snapshot.records))
        lines.extend(_render_quadrant(snapshot.records))
        lines.extend(_render_sensitivity(snapshot.records))
    elif status is SectorCoverageStatus.WARMING_UP:
        lines.extend(_render_warming_table(snapshot.records))
    if snapshot.diagnostics or status is not SectorCoverageStatus.NORMAL:
        lines.extend(_render_diagnostics(snapshot.diagnostics))
    lines.extend(_render_method_note(snapshot))
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_banner() -> list[str]:
    return [
        "> **PRIVATE VALIDATION**",
        "> NAV 수익률 기준",
        "> 실제 시장 OHLCV 아님",
        "> 공개 게시 금지",
        "",
    ]


def _render_coverage(snapshot: SectorDashboardSnapshot) -> list[str]:
    coverage = snapshot.coverage
    as_of = snapshot.as_of_date.isoformat() if snapshot.as_of_date is not None else "기준일 없음"
    benchmark = "사용 가능" if coverage.benchmark_available else "사용 불가"
    return [
        "## 커버리지",
        "",
        f"- 상태: `{coverage.status.value}`",
        f"- 기준일: {as_of}",
        f"- 섹터: {coverage.available_sector_count}/11",
        f"- SPY 벤치마크: {benchmark}",
        "- 입력 표지: State Street NAV History (private input)",
        f"- 기본 정책: `{snapshot.primary_policy.policy_id}` / 10 bps",
        "",
    ]


def _render_summary(snapshot: SectorDashboardSnapshot) -> list[str]:
    ranked = [record for record in snapshot.records if record.relative_rank.score is not None]
    complete_counts: Counter[SectorRegime] = Counter(
        record.primary_regime.regime
        for record in snapshot.records
        if record.primary_regime.regime is not SectorRegime.INSUFFICIENT
    )
    unavailable_63d = sum(
        record.metrics.nav_excess_63d.value is None for record in snapshot.records
    )
    lines = ["## 레이더 요약", ""]
    if len(ranked) >= 4:
        lines.extend(
            [
                f"- 상위 2개: {', '.join(record.ticker.value for record in ranked[:2])}",
                f"- 하위 2개: {', '.join(record.ticker.value for record in ranked[-2:])}",
            ]
        )
    else:
        lines.append("- 상·하위 비교: 데이터 부족 (insufficient_comparables)")
    lines.append(
        "- 국면 수: "
        + ", ".join(
            f"{_REGIME_LABELS[regime]} {complete_counts[regime]}"
            for regime in (
                SectorRegime.LEADING,
                SectorRegime.WEAKENING,
                SectorRegime.RECOVERING,
                SectorRegime.LAGGING,
            )
        )
    )
    lines.extend(
        [
            f"- 63D 지표 미제공: {unavailable_63d}",
            "- 순위는 SPY 대비 NAV 모멘텀만 나타내며 섹터 건전성이나 투자 가능성을 뜻하지 않는다.",
            "",
        ]
    )
    return lines


def _render_full_table(records: Sequence[SectorRecord]) -> list[str]:
    lines = [
        "## 섹터 지표",
        "",
        "| 순위 | 티커 | 기본 국면 | NAV 1D | SPY 대비 5D | SPY 대비 21D | "
        "SPY 대비 63D | 5D 상대 가속 | NAV 기준 실현변동성 20D | "
        "NAV 최대 낙폭 20D | 가용성 |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in records:
        rank = _format_rank(record)
        metrics = record.metrics
        lines.append(
            "| "
            + " | ".join(
                (
                    rank,
                    record.ticker.value,
                    _REGIME_LABELS[record.primary_regime.regime],
                    _format_ratio(metrics.nav_return_1d, "%"),
                    _format_ratio(metrics.nav_excess_5d, "pp"),
                    _format_ratio(metrics.nav_excess_21d, "pp"),
                    _format_ratio(metrics.nav_excess_63d, "pp"),
                    _format_ratio(metrics.nav_relative_acceleration_5d, "pp"),
                    _format_ratio(metrics.nav_realized_volatility_20d, "%"),
                    _format_ratio(metrics.nav_max_drawdown_20d, "%"),
                    _availability_note(record, _FULL_METRICS),
                )
            )
            + " |"
        )
    lines.append("")
    return lines


def _render_warming_table(records: Sequence[SectorRecord]) -> list[str]:
    lines = [
        "## 섹터 단기 지표",
        "",
        "| 티커 | NAV 1D | NAV 5D | SPY 대비 1D | SPY 대비 5D | 가용성 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for record in records:
        metrics = record.metrics
        lines.append(
            "| "
            + " | ".join(
                (
                    record.ticker.value,
                    _format_ratio(metrics.nav_return_1d, "%"),
                    _format_ratio(metrics.nav_return_5d, "%"),
                    _format_ratio(metrics.nav_excess_1d, "pp"),
                    _format_ratio(metrics.nav_excess_5d, "pp"),
                    _availability_note(record, _WARMING_METRICS),
                )
            )
            + " |"
        )
    lines.append("")
    return lines


def _render_quadrant(records: Sequence[SectorRecord]) -> list[str]:
    lines = ["## 텍스트 국면", ""]
    for regime in (
        SectorRegime.LEADING,
        SectorRegime.WEAKENING,
        SectorRegime.RECOVERING,
        SectorRegime.LAGGING,
    ):
        tickers = [
            record.ticker.value for record in records if record.primary_regime.regime is regime
        ]
        lines.append(f"- {_REGIME_LABELS[regime]}: {', '.join(tickers) if tickers else '없음'}")
    insufficient = [
        record.ticker.value
        for record in records
        if record.primary_regime.regime is SectorRegime.INSUFFICIENT
    ]
    lines.extend(
        [
            f"- 상태 계산 불가: {', '.join(insufficient) if insufficient else '없음'}",
            "",
        ]
    )
    return lines


def _render_sensitivity(records: Sequence[SectorRecord]) -> list[str]:
    lines = [
        "## 중립 구간 민감도",
        "",
        "private policy sensitivity only",
        "",
        "| 티커 | 0 bps | 5 bps | 10 bps (primary) | 15 bps | 20 bps |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| "
            + " | ".join(
                [record.ticker.value]
                + [record.sensitivity_regimes[band].value for band in REGIME_BANDS_BPS]
            )
            + " |"
        )
    lines.extend(["", "변경 수 (10 bps 기본 정책 대비):"])
    for band in REGIME_BANDS_BPS:
        changed = sum(
            record.sensitivity_regimes[band] is not record.sensitivity_regimes[10]
            for record in records
        )
        lines.append(f"- {band} bps: {changed}")
    lines.append("")
    return lines


def _render_diagnostics(diagnostics: Sequence[PrivateDiagnostic]) -> list[str]:
    grouped: Counter[tuple[str, str, str, str, str, str]] = Counter()
    for diagnostic in diagnostics:
        grouped[
            (
                diagnostic.issue_code.value,
                diagnostic.ticker.value if diagnostic.ticker is not None else "-",
                diagnostic.metric_name.value if diagnostic.metric_name is not None else "-",
                str(diagnostic.row_count) if diagnostic.row_count is not None else "-",
                diagnostic.first_date.isoformat() if diagnostic.first_date is not None else "-",
                diagnostic.latest_date.isoformat() if diagnostic.latest_date is not None else "-",
            )
        ] += 1
    lines = [
        "## 진단 요약",
        "",
        "| 이슈 코드 | 티커 | 지표 | 행 수 | 시작일 | 종료일 | 건수 |",
        "| --- | --- | --- | ---: | --- | --- | ---: |",
    ]
    if not grouped:
        lines.append("| - | - | - | - | - | - | 0 |")
    else:
        for key, count in sorted(grouped.items()):
            lines.append("| " + " | ".join((*key, str(count))) + " |")
    lines.append("")
    return lines


def _render_method_note(snapshot: SectorDashboardSnapshot) -> list[str]:
    snapshot_id = _snapshot_id(snapshot)
    return [
        "## 방법 및 범위",
        "",
        "- 수익률은 단순 NAV 수익률이다.",
        "- 초과 수익률은 동일한 날짜 구간의 섹터 NAV 수익률에서 SPY NAV 수익률을 뺀 값이다.",
        "- 5D 상대 가속은 현재 5일과 직전의 겹치지 않는 5일 초과 수익률 차이다.",
        "- 변동성은 NAV 로그 수익률로 계산해 연율화한다.",
        "- 순위 산식은 변동성·낙폭·거래 활동·자금 이동·기업 실적을 제외한다.",
        "- u140은 계속 차단 상태이며 이 산출물은 공개 데이터 사용 권한을 부여하지 않는다.",
        f"<!-- snapshot_id: {snapshot_id} -->",
        "",
    ]


def _format_rank(record: SectorRecord) -> str:
    rank = record.relative_rank
    if rank.score is None or rank.ordinal is None:
        return f"데이터 부족 ({rank.missing_reason})"
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        score = rank.score.quantize(Decimal("0.0001"))
    return f"{rank.ordinal} ({score:.4f})"


def _format_ratio(metric: MetricValue, unit: str) -> str:
    if metric.value is None:
        reason = metric.missing_reason.value if metric.missing_reason is not None else "unknown"
        return f"데이터 부족 ({reason})"
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        displayed = (metric.value * Decimal(100)).quantize(Decimal("0.01"))
    if displayed == 0:
        displayed = Decimal("0.00")
    sign = "+" if displayed > 0 else ""
    return f"{sign}{displayed:.2f} {unit}"


def _availability_note(record: SectorRecord, names: Sequence[SectorMetricName]) -> str:
    reasons: list[MetricMissingReason] = []
    for name in names:
        reason = getattr(record.metrics, name.value).missing_reason
        if reason is not None and reason not in reasons:
            reasons.append(reason)
    if not reasons:
        return "사용 가능"
    return "데이터 부족 (" + ",".join(reason.value for reason in reasons) + ")"


def _snapshot_json_bytes(snapshot: SectorDashboardSnapshot, *, include_id: bool) -> bytes:
    projection = snapshot.model_dump(mode="json", exclude=None if include_id else {"snapshot_id"})
    if include_id:
        keys = tuple(projection)
        if keys[:2] != ("schema_version", "snapshot_id"):
            raise PrivateTransactionError
    return _json_bytes(projection)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, separators=(",", ": ")) + "\n").encode(
        "utf-8"
    )


def _validate_pair_bytes(snapshot_bytes: bytes, report_bytes: bytes) -> _ValidatedPair:
    if (
        not snapshot_bytes
        or not report_bytes
        or len(snapshot_bytes) > MAX_PROJECTION_BYTES
        or len(report_bytes) > MAX_PROJECTION_BYTES
        or b"\r" in snapshot_bytes
        or b"\r" in report_bytes
        or not snapshot_bytes.endswith(b"\n")
        or not report_bytes.endswith(b"\n")
    ):
        raise PrivateTransactionError
    try:
        raw = json.loads(snapshot_bytes)
        snapshot = SectorDashboardSnapshot.model_validate(raw)
        report = report_bytes.decode("utf-8")
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
        raise PrivateTransactionError from None
    if not isinstance(raw, dict) or tuple(raw)[:2] != ("schema_version", "snapshot_id"):
        raise PrivateTransactionError
    if any(
        record.relative_rank.missing_reason is not None
        and record.relative_rank.missing_reason not in _RANK_MISSING_REASONS
        for record in snapshot.records
    ):
        raise PrivateTransactionError
    _reject_forbidden_keys(raw)
    snapshot_id = _snapshot_id(snapshot)
    without_id = snapshot.model_copy(update={"snapshot_id": None})
    expected_id = (
        "sha256:" + hashlib.sha256(_snapshot_json_bytes(without_id, include_id=False)).hexdigest()
    )
    if snapshot_id != expected_id or snapshot_bytes != _snapshot_json_bytes(
        snapshot, include_id=True
    ):
        raise PrivateTransactionError
    markers = _SNAPSHOT_MARKER_RE.findall(report)
    if markers != [snapshot_id]:
        raise PrivateTransactionError
    if any(label not in report for label in _REPORT_REQUIRED_LABELS):
        raise PrivateTransactionError
    lowered = report.casefold()
    if any(term.casefold() in lowered for term in _REPORT_FORBIDDEN_TERMS):
        raise PrivateTransactionError
    if report_bytes != _render_report(snapshot).encode("utf-8"):
        raise PrivateTransactionError
    return _ValidatedPair(
        snapshot=snapshot,
        snapshot_bytes=snapshot_bytes,
        report_bytes=report_bytes,
    )


def _partial_pair_matches_expected(directory: Path, expected_snapshot_id: str) -> bool:
    snapshot_path = directory / SNAPSHOT_NAME
    report_path = directory / REPORT_NAME
    found = False
    try:
        if snapshot_path.exists() or snapshot_path.is_symlink():
            found = True
            snapshot_bytes = _read_secure_file(snapshot_path)
            raw = json.loads(snapshot_bytes)
            snapshot = SectorDashboardSnapshot.model_validate(raw)
            if (
                snapshot.snapshot_id != expected_snapshot_id
                or snapshot_bytes != _snapshot_json_bytes(snapshot, include_id=True)
            ):
                return False
            without_id = snapshot.model_copy(update={"snapshot_id": None})
            recomputed = (
                "sha256:"
                + hashlib.sha256(_snapshot_json_bytes(without_id, include_id=False)).hexdigest()
            )
            if recomputed != expected_snapshot_id:
                return False
        if report_path.exists() or report_path.is_symlink():
            found = True
            report = _read_secure_file(report_path).decode("utf-8")
            if _SNAPSHOT_MARKER_RE.findall(report) != [expected_snapshot_id]:
                return False
        return found
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        PrivateOutputRejectedError,
        PrivateTransactionError,
    ):
        return False


def _partial_pair_matches_expected_at(directory_fd: int, expected_snapshot_id: str) -> bool:
    found = False
    try:
        if _entry_exists_at(directory_fd, SNAPSHOT_NAME):
            found = True
            snapshot_bytes = _read_secure_file_at(directory_fd, SNAPSHOT_NAME)
            raw = json.loads(snapshot_bytes)
            snapshot = SectorDashboardSnapshot.model_validate(raw)
            if (
                snapshot.snapshot_id != expected_snapshot_id
                or snapshot_bytes != _snapshot_json_bytes(snapshot, include_id=True)
            ):
                return False
            without_id = snapshot.model_copy(update={"snapshot_id": None})
            recomputed = (
                "sha256:"
                + hashlib.sha256(_snapshot_json_bytes(without_id, include_id=False)).hexdigest()
            )
            if recomputed != expected_snapshot_id:
                return False
        if _entry_exists_at(directory_fd, REPORT_NAME):
            found = True
            report = _read_secure_file_at(directory_fd, REPORT_NAME).decode("utf-8")
            if _SNAPSHOT_MARKER_RE.findall(report) != [expected_snapshot_id]:
                return False
        return found
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        PrivateOutputRejectedError,
        PrivateTransactionError,
    ):
        return False


def _partial_output_matches_known_pairs_at(
    directory_fd: int,
    pairs: Sequence[_ValidatedPair],
) -> bool:
    found = False
    try:
        for name, attribute in (
            (SNAPSHOT_NAME, "snapshot_bytes"),
            (REPORT_NAME, "report_bytes"),
        ):
            if not _entry_exists_at(directory_fd, name):
                continue
            found = True
            value = _read_secure_file_at(directory_fd, name)
            if not any(value == getattr(pair, attribute) for pair in pairs):
                return False
        return found
    except (PrivateOutputRejectedError, PrivateTransactionError):
        return False


def _partial_managed_cleanup_matches_at(
    directory_fd: int,
    expected_snapshot_id: str,
    expected_report_sha256: str,
) -> bool:
    try:
        names = set(os.listdir(directory_fd))
        if not names:
            return True
        if not names <= {SNAPSHOT_NAME, REPORT_NAME}:
            return False
        if SNAPSHOT_NAME in names:
            snapshot_bytes = _read_secure_file_at(directory_fd, SNAPSHOT_NAME)
            raw = json.loads(snapshot_bytes)
            snapshot = SectorDashboardSnapshot.model_validate(raw)
            if (
                snapshot.snapshot_id != expected_snapshot_id
                or snapshot_bytes != _snapshot_json_bytes(snapshot, include_id=True)
            ):
                return False
            without_id = snapshot.model_copy(update={"snapshot_id": None})
            recomputed = (
                "sha256:"
                + hashlib.sha256(_snapshot_json_bytes(without_id, include_id=False)).hexdigest()
            )
            if recomputed != expected_snapshot_id:
                return False
        if REPORT_NAME in names:
            report_bytes = _read_secure_file_at(directory_fd, REPORT_NAME)
            if _bytes_sha256(report_bytes) != expected_report_sha256 or _SNAPSHOT_MARKER_RE.findall(
                report_bytes.decode("utf-8")
            ) != [expected_snapshot_id]:
                return False
        return True
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        PrivateOutputRejectedError,
        PrivateTransactionError,
    ):
        return False


def _reject_forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in _SNAPSHOT_FORBIDDEN_KEYS:
                raise PrivateTransactionError
            _reject_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _snapshot_id(snapshot: SectorDashboardSnapshot) -> str:
    if snapshot.snapshot_id is None or _SNAPSHOT_ID_RE.fullmatch(snapshot.snapshot_id) is None:
        raise PrivateTransactionError
    return snapshot.snapshot_id


def _bytes_sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _require_supported_platform() -> None:
    if os.name != "posix" or not hasattr(os, "getuid") or not hasattr(os, "replace"):
        raise PrivateOutputRejectedError


def _resolved_repository(repository_root: Path) -> Path:
    try:
        resolved = repository_root.resolve(strict=True)
    except OSError:
        raise PrivateOutputRejectedError from None
    if not resolved.is_dir():
        raise PrivateOutputRejectedError
    return resolved


def _prepare_output_directory(output_dir: Path, repository_root: Path) -> Path:
    if not output_dir.is_absolute() or output_dir.name in {"", ".", ".."}:
        raise PrivateOutputRejectedError
    try:
        if output_dir.exists() or output_dir.is_symlink():
            original = _verify_owned_entry(output_dir, kind="directory", mode=0o700)
            resolved = output_dir.resolve(strict=True)
        else:
            parent = output_dir.parent.resolve(strict=True)
            if not parent.is_dir():
                raise PrivateOutputRejectedError
            resolved = parent / output_dir.name
            if _paths_overlap(resolved, repository_root):
                raise PrivateOutputRejectedError
            os.mkdir(resolved, 0o700)
            os.chmod(resolved, 0o700)
            original = _verify_owned_entry(resolved, kind="directory", mode=0o700)
            resolved = resolved.resolve(strict=True)
    except PrivateOutputRejectedError:
        raise
    except OSError:
        raise PrivateOutputRejectedError from None
    if _paths_overlap(resolved, repository_root):
        raise PrivateOutputRejectedError
    final_spelling = _verify_owned_entry(output_dir, kind="directory", mode=0o700)
    final_resolved = _verify_owned_entry(resolved, kind="directory", mode=0o700)
    identities = {
        (original.st_dev, original.st_ino),
        (final_spelling.st_dev, final_spelling.st_ino),
        (final_resolved.st_dev, final_resolved.st_ino),
    }
    if len(identities) != 1:
        raise PrivateOutputRejectedError
    for name in (SNAPSHOT_NAME, REPORT_NAME):
        path = resolved / name
        if path.is_symlink():
            raise PrivateOutputRejectedError
    return resolved


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _lexically_present(path: Path) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateTransactionError from None


def _open_private_directory(path: Path, expected_identity: tuple[int, int]) -> int:
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        descriptor_stat = os.fstat(descriptor)
        path_stat = path.lstat()
        if (
            not stat.S_ISDIR(descriptor_stat.st_mode)
            or descriptor_stat.st_uid != os.getuid()
            or stat.S_IMODE(descriptor_stat.st_mode) != 0o700
            or (descriptor_stat.st_dev, descriptor_stat.st_ino) != expected_identity
            or (path_stat.st_dev, path_stat.st_ino) != expected_identity
        ):
            raise PrivateOutputRejectedError
        return descriptor
    except (OSError, PrivateOutputRejectedError):
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise PrivateOutputRejectedError from None
    except BaseException:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise


def _open_and_lock_marker(path: Path) -> tuple[int, bool]:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    flags = os.O_RDWR | nofollow
    existed = False
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
            os.fchmod(descriptor, 0o600)
        except FileExistsError:
            existed = True
            _verify_owned_entry(path, kind="file", mode=0o600)
            descriptor = os.open(path, flags)
        assert descriptor is not None
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(descriptor)
            descriptor = None
            raise PrivateTransactionError from None
        descriptor_stat = os.fstat(descriptor)
        path_stat = path.lstat()
        if (
            descriptor_stat.st_uid != os.getuid()
            or stat.S_IMODE(descriptor_stat.st_mode) != 0o600
            or not stat.S_ISREG(descriptor_stat.st_mode)
            or descriptor_stat.st_nlink != 1
            or path_stat.st_nlink != 1
            or descriptor_stat.st_dev != path_stat.st_dev
            or descriptor_stat.st_ino != path_stat.st_ino
        ):
            os.close(descriptor)
            descriptor = None
            raise PrivateOutputRejectedError
        return descriptor, existed
    except (PrivateOutputRejectedError, PrivateTransactionError):
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise
    except OSError:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise PrivateOutputRejectedError from None
    except BaseException:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        raise


def _verify_owned_entry(path: Path, *, kind: str, mode: int) -> os.stat_result:
    try:
        entry_stat = path.lstat()
    except OSError:
        raise PrivateOutputRejectedError from None
    expected_type = stat.S_ISDIR if kind == "directory" else stat.S_ISREG
    if (
        stat.S_ISLNK(entry_stat.st_mode)
        or not expected_type(entry_stat.st_mode)
        or entry_stat.st_uid != os.getuid()
        or stat.S_IMODE(entry_stat.st_mode) != mode
        or (kind == "file" and entry_stat.st_nlink != 1)
    ):
        raise PrivateOutputRejectedError
    return entry_stat


def _chmod_exact(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode, follow_symlinks=False)
        _verify_owned_entry(path, kind="file", mode=mode)
    except (NotImplementedError, OSError):
        raise PrivateTransactionError from None


def _chmod_exact_at(directory_fd: int, name: str, mode: int) -> None:
    try:
        os.chmod(
            name,
            mode,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not _is_owned_regular_file(current) or stat.S_IMODE(current.st_mode) != mode:
            raise PrivateTransactionError
    except (NotImplementedError, OSError):
        raise PrivateTransactionError from None


def _write_pair(directory: Path, snapshot_bytes: bytes, report_bytes: bytes) -> None:
    _write_secure_file(directory / SNAPSHOT_NAME, snapshot_bytes)
    _write_secure_file(directory / REPORT_NAME, report_bytes)
    _fsync_directory(directory)


def _write_pair_at(directory_fd: int, snapshot_bytes: bytes, report_bytes: bytes) -> None:
    _write_secure_file_at(directory_fd, SNAPSHOT_NAME, snapshot_bytes)
    _write_secure_file_at(directory_fd, REPORT_NAME, report_bytes)
    os.fsync(directory_fd)


def _write_secure_file(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, data)
        os.fsync(descriptor)
    except OSError:
        raise PrivateTransactionError from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
    _verify_owned_entry(path, kind="file", mode=0o600)


def _write_secure_file_at(directory_fd: int, name: str, data: bytes) -> None:
    descriptor: int | None = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, data)
        os.fsync(descriptor)
    except OSError:
        raise PrivateTransactionError from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
    current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if not _is_owned_regular_file(current):
        raise PrivateTransactionError


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:
            raise OSError("short write")
        offset += written


def _read_optional_valid_pair(directory: Path) -> _ValidatedPair | None:
    snapshot_path = directory / SNAPSHOT_NAME
    report_path = directory / REPORT_NAME
    snapshot_exists = snapshot_path.exists() or snapshot_path.is_symlink()
    report_exists = report_path.exists() or report_path.is_symlink()
    if not snapshot_exists and not report_exists:
        return None
    if not snapshot_exists or not report_exists:
        raise PrivateTransactionError
    return _read_valid_pair(directory)


def _read_optional_valid_pair_at(directory_fd: int) -> _ValidatedPair | None:
    snapshot_exists = _entry_exists_at(directory_fd, SNAPSHOT_NAME)
    report_exists = _entry_exists_at(directory_fd, REPORT_NAME)
    if not snapshot_exists and not report_exists:
        return None
    if not snapshot_exists or not report_exists:
        raise PrivateTransactionError
    return _read_valid_pair_at(directory_fd)


def _read_valid_pair(directory: Path) -> _ValidatedPair:
    snapshot_bytes = _read_secure_file(directory / SNAPSHOT_NAME)
    report_bytes = _read_secure_file(directory / REPORT_NAME)
    return _validate_pair_bytes(snapshot_bytes, report_bytes)


def _read_valid_pair_at(directory_fd: int) -> _ValidatedPair:
    snapshot_bytes = _read_secure_file_at(directory_fd, SNAPSHOT_NAME)
    report_bytes = _read_secure_file_at(directory_fd, REPORT_NAME)
    return _validate_pair_bytes(snapshot_bytes, report_bytes)


def _entry_exists_at(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateTransactionError from None


def _read_secure_file(path: Path) -> bytes:
    _verify_owned_entry(path, kind="file", mode=0o600)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if (
            not _is_owned_regular_file(before)
            or before.st_size <= 0
            or before.st_size > MAX_PROJECTION_BYTES
        ):
            raise PrivateTransactionError
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                raise PrivateTransactionError
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        current = path.lstat()
        if (
            not _is_owned_regular_file(after)
            or not _is_owned_regular_file(current)
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or after.st_dev != current.st_dev
            or after.st_ino != current.st_ino
            or after.st_size != current.st_size
            or after.st_mtime_ns != current.st_mtime_ns
            or after.st_ctime_ns != current.st_ctime_ns
        ):
            raise PrivateTransactionError
        return b"".join(chunks)
    except OSError:
        raise PrivateTransactionError from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _read_secure_file_at(directory_fd: int, name: str) -> bytes:
    descriptor: int | None = None
    try:
        before_path = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not _is_owned_regular_file(before_path):
            raise PrivateOutputRejectedError
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags, dir_fd=directory_fd)
        before = os.fstat(descriptor)
        if (
            not _is_owned_regular_file(before)
            or before.st_size <= 0
            or before.st_size > MAX_PROJECTION_BYTES
            or before.st_dev != before_path.st_dev
            or before.st_ino != before_path.st_ino
        ):
            raise PrivateTransactionError
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                raise PrivateTransactionError
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not _is_owned_regular_file(after)
            or not _is_owned_regular_file(current)
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or after.st_dev != current.st_dev
            or after.st_ino != current.st_ino
            or after.st_size != current.st_size
            or after.st_mtime_ns != current.st_mtime_ns
            or after.st_ctime_ns != current.st_ctime_ns
        ):
            raise PrivateTransactionError
        return b"".join(chunks)
    except OSError:
        raise PrivateTransactionError from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _is_owned_regular_file(value: os.stat_result) -> bool:
    return (
        stat.S_ISREG(value.st_mode)
        and not stat.S_ISLNK(value.st_mode)
        and value.st_uid == os.getuid()
        and stat.S_IMODE(value.st_mode) == 0o600
        and value.st_nlink == 1
    )


def _probe_valid_pair(directory: Path | None) -> _ValidatedPair | bool | None:
    if directory is None or not directory.exists():
        return None
    try:
        return _read_optional_valid_pair(directory)
    except (PrivateOutputRejectedError, PrivateTransactionError):
        return False


def _probe_valid_pair_at(directory_fd: int) -> _ValidatedPair | bool | None:
    try:
        return _read_optional_valid_pair_at(directory_fd)
    except (PrivateOutputRejectedError, PrivateTransactionError):
        return False


def _replace_pair_from(
    source: Path,
    target: Path,
    *,
    source_fd: int | None = None,
    expected_source_snapshot_id: str | None = None,
    target_fd: int | None = None,
) -> None:
    pair = _read_valid_pair_at(source_fd) if source_fd is not None else _read_valid_pair(source)
    if (
        expected_source_snapshot_id is not None
        and pair.snapshot.snapshot_id != expected_source_snapshot_id
    ):
        raise PrivateTransactionError
    if source_fd is None:
        _write_promotion_copies(source, pair)
    else:
        _write_promotion_copies_at(source_fd, pair)
    if target_fd is None:
        os.replace(source / _PROMOTION_SNAPSHOT_NAME, target / SNAPSHOT_NAME)
        _chmod_exact(target / SNAPSHOT_NAME, 0o600)
        _fsync_directory(target)
        os.replace(source / _PROMOTION_REPORT_NAME, target / REPORT_NAME)
        _chmod_exact(target / REPORT_NAME, 0o600)
        _fsync_directory(target)
        return
    os.replace(
        _PROMOTION_SNAPSHOT_NAME if source_fd is not None else source / _PROMOTION_SNAPSHOT_NAME,
        SNAPSHOT_NAME,
        src_dir_fd=source_fd,
        dst_dir_fd=target_fd,
    )
    _chmod_exact_at(target_fd, SNAPSHOT_NAME, 0o600)
    os.fsync(target_fd)
    os.replace(
        _PROMOTION_REPORT_NAME if source_fd is not None else source / _PROMOTION_REPORT_NAME,
        REPORT_NAME,
        src_dir_fd=source_fd,
        dst_dir_fd=target_fd,
    )
    _chmod_exact_at(target_fd, REPORT_NAME, 0o600)
    os.fsync(target_fd)


def _write_promotion_copies(source: Path, pair: _ValidatedPair) -> None:
    for name in (_PROMOTION_SNAPSHOT_NAME, _PROMOTION_REPORT_NAME):
        path = source / name
        if path.exists() or path.is_symlink():
            _verify_owned_entry(path, kind="file", mode=0o600)
            path.unlink()
    _write_secure_file(source / _PROMOTION_SNAPSHOT_NAME, pair.snapshot_bytes)
    _write_secure_file(source / _PROMOTION_REPORT_NAME, pair.report_bytes)
    _fsync_directory(source)


def _write_promotion_copies_at(source_fd: int, pair: _ValidatedPair) -> None:
    for name in (_PROMOTION_SNAPSHOT_NAME, _PROMOTION_REPORT_NAME):
        if _entry_exists_at(source_fd, name):
            current = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
            if not _is_owned_regular_file(current):
                raise PrivateTransactionError
            os.unlink(name, dir_fd=source_fd)
    _write_secure_file_at(source_fd, _PROMOTION_SNAPSHOT_NAME, pair.snapshot_bytes)
    _write_secure_file_at(source_fd, _PROMOTION_REPORT_NAME, pair.report_bytes)
    os.fsync(source_fd)


def _unlink_projection_if_present(path: Path, *, directory_fd: int | None = None) -> None:
    if directory_fd is not None:
        try:
            current = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        except OSError:
            raise PrivateTransactionError from None
        if not _is_owned_regular_file(current):
            raise PrivateTransactionError
        try:
            os.unlink(path.name, dir_fd=directory_fd)
        except OSError:
            raise PrivateTransactionError from None
        return
    if not path.exists() and not path.is_symlink():
        return
    _verify_owned_entry(path, kind="file", mode=0o600)
    path.unlink()


def _remove_managed_directory(directory: Path, *, directory_fd: int | None = None) -> None:
    _verify_owned_entry(directory, kind="directory", mode=0o700)
    if directory_fd is not None:
        for name in (
            SNAPSHOT_NAME,
            REPORT_NAME,
            _PROMOTION_SNAPSHOT_NAME,
            _PROMOTION_REPORT_NAME,
        ):
            if _entry_exists_at(directory_fd, name):
                current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if not _is_owned_regular_file(current):
                    raise PrivateTransactionError
                os.unlink(name, dir_fd=directory_fd)
        if os.listdir(directory_fd):
            raise PrivateTransactionError
        os.fsync(directory_fd)
        directory.rmdir()
        _fsync_directory(directory.parent)
        return
    for name in (
        SNAPSHOT_NAME,
        REPORT_NAME,
        _PROMOTION_SNAPSHOT_NAME,
        _PROMOTION_REPORT_NAME,
    ):
        path = directory / name
        if path.exists() or path.is_symlink():
            _verify_owned_entry(path, kind="file", mode=0o600)
            path.unlink()
    if any(directory.iterdir()):
        raise PrivateTransactionError
    directory.rmdir()
    _fsync_directory(directory.parent)


def _fsync_directory(directory: Path) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        os.fsync(descriptor)
    except OSError:
        raise PrivateTransactionError from None
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)


def _no_fault(phase: str) -> None:
    del phase


__all__ = [
    "PrivateCommitResult",
    "PrivateOutputRejectedError",
    "PrivateOutputSession",
    "PrivateTransactionError",
    "RenderedPrivateProjection",
    "open_private_output_session",
    "render_private_projection",
    "verify_private_projection",
]
