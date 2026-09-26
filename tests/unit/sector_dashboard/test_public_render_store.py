"""Step 4 tests for the u145 deterministic renderer and derived-only store."""

from __future__ import annotations

import ast
import hashlib
import json
import traceback
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import investo.sector_dashboard.public_render as public_render
import investo.sector_dashboard.public_store as public_store
from investo.models.market_calendar import is_trading_day
from investo.models.sector import BENCHMARK_TICKER, SectorCoverageStatus, SectorTicker
from investo.models.sector_public import (
    PUBLIC_REQUEST_TICKERS,
    PUBLIC_SUPPORTED_SECTOR_TICKERS,
    PublicBarPoint,
    PublicBarSeries,
    PublicDiagnosticCode,
    PublicParsedSet,
    PublicSectorBuildStatus,
    PublicSourceFailure,
    PublicSourceIssueCode,
    RenderedPublicSectorProjection,
)
from investo.sector_dashboard.public_metrics import (
    build_public_series_bundle,
    compute_public_sector_snapshot,
)
from investo.sector_dashboard.public_render import (
    MAX_PUBLIC_PROJECTION_BYTES,
    PublicProjectionError,
    render_public_sector_projection,
    verify_public_sector_projection,
)
from investo.sector_dashboard.public_store import (
    PUBLIC_MARKDOWN_NAME,
    PUBLIC_SECTOR_DIRECTORY,
    PUBLIC_SNAPSHOT_NAME,
    PublicSectorStoreError,
    hold_public_sector_last_good,
    promote_public_sector_projection,
    read_public_sector_projection,
)

_AS_OF = date(2026, 8, 31)


def _trading_dates(count: int, *, end: date = _AS_OF) -> tuple[date, ...]:
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if is_trading_day("us-equity", cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(days))


def _bars(
    ticker: SectorTicker,
    *,
    count: int = 64,
    end: date = _AS_OF,
    volume: int = 1_000,
    slope_delta: Decimal = Decimal(0),
) -> PublicBarSeries:
    offset = Decimal(PUBLIC_REQUEST_TICKERS.index(ticker))
    slope = Decimal("0.15") + offset * Decimal("0.02")
    if ticker is SectorTicker.XLK:
        slope += slope_delta
    points = []
    for index, day in enumerate(_trading_dates(count, end=end)):
        close = Decimal("100") + offset + Decimal(index) * slope
        points.append(
            PublicBarPoint(
                trading_date=day,
                open=close - Decimal("0.10"),
                high=close + Decimal("0.50"),
                low=close - Decimal("0.50"),
                close=close,
                volume=volume + index,
            )
        )
    return PublicBarSeries(
        ticker=ticker,
        points=tuple(points),
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


def _snapshot(
    *,
    count: int = 64,
    end: date = _AS_OF,
    volume: int = 1_000,
    slope_delta: Decimal = Decimal(0),
    sectors: tuple[SectorTicker, ...] = PUBLIC_SUPPORTED_SECTOR_TICKERS,
):
    failures = tuple(
        PublicSourceFailure(
            ticker=ticker,
            issue_code=PublicSourceIssueCode.TRANSPORT,
            retryable=True,
        )
        for ticker in PUBLIC_SUPPORTED_SECTOR_TICKERS
        if ticker not in sectors
    )
    parsed = PublicParsedSet(
        benchmark=_bars(BENCHMARK_TICKER, count=count, end=end, volume=volume),
        sectors={
            ticker: _bars(
                ticker,
                count=count,
                end=end,
                volume=volume,
                slope_delta=slope_delta,
            )
            for ticker in sectors
        },
        failures=failures,
    )
    bundle = build_public_series_bundle(parsed, target_date=_AS_OF)
    return compute_public_sector_snapshot(bundle)


def _projection(**kwargs: object) -> RenderedPublicSectorProjection:
    return render_public_sector_projection(_snapshot(**kwargs))


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "site_docs").mkdir(parents=True)
    return root


def _pair_paths(root: Path) -> tuple[Path, Path]:
    output = root / PUBLIC_SECTOR_DIRECTORY
    return output / PUBLIC_MARKDOWN_NAME, output / PUBLIC_SNAPSHOT_NAME


def _table_rows(markdown: str) -> list[str]:
    table = markdown.split("## 섹터 레이더\n\n", maxsplit=1)[1].split("\n\n## ", maxsplit=1)[0]
    return [line for line in table.splitlines()[2:] if line.startswith("| ")]


def _canonical_rehashed_snapshot(raw: dict[str, object]) -> bytes:
    identity = {key: value for key, value in raw.items() if key != "snapshot_id"}
    canonical_identity = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    raw["snapshot_id"] = f"sha256:{hashlib.sha256(canonical_identity).hexdigest()}"
    return (
        json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def test_fresh_projection_is_canonical_complete_and_first_viewport_qualified() -> None:
    snapshot = _snapshot()
    first = render_public_sector_projection(snapshot)
    second = render_public_sector_projection(snapshot)

    assert first == second
    assert verify_public_sector_projection(first.snapshot_bytes, first.markdown_bytes) == snapshot
    raw = json.loads(first.snapshot_bytes)
    expected_json = (
        json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    assert first.snapshot_bytes == expected_json
    assert raw["snapshot_id"] == first.snapshot_id

    markdown = first.markdown_bytes.decode()
    radar_position = markdown.index("## 섹터 레이더")
    for label in (
        "제한 공개 베타",
        "IEX venue sample 기준",
        "10/11 섹터 사용 가능 · XLRE unavailable",
        "미국 전체시장 거래량 또는 자금 흐름이 아님",
    ):
        assert markdown.index(label) < radar_position
    assert len(_table_rows(markdown)) == 11
    assert "| 순위 | 섹터/티커 | 가용성 | 국면 |" in markdown
    assert "부동산 (XLRE) | provider 미지원 | 분류 불가" in markdown
    assert "## 레이더 요약" in markdown
    assert "## 텍스트 국면" in markdown
    assert markdown.count("<!-- snapshot_id:") == 1
    assert "<script" not in markdown.casefold()


def test_complete_sector_rows_do_not_report_missing_metrics() -> None:
    rows = _table_rows(_projection().markdown_bytes.decode())
    labels = [row.split("|")[3].strip() for row in rows]

    assert labels.count("사용 가능") == 10
    assert labels.count("provider 미지원") == 1
    assert all("일부 지표 부족" not in label for label in labels)


def test_projection_renders_attribution_method_and_two_decimal_half_even_values() -> None:
    projection = _projection()
    markdown = projection.markdown_bytes.decode()

    assert "HF Data Library (Elkassabgi 2026)" in markdown
    assert "https://hfdatalibrary.com/pages/license" in markdown
    assert "Data provided for free by IEX" in markdown
    assert "https://www.iex.io/legal/hist-data-terms" in markdown
    assert "IEX volume은 점수, 순위, 국면 및 요약에서 제외" in markdown
    assert "정보 제공용이며 투자 권유, 예측 또는 개인화된 조언이 아닙니다" in markdown
    assert (
        public_render._format_metric(public_render.MetricValue(value=Decimal("0.01225")), "%")
        == "+1.22 %"
    )
    assert (
        public_render._format_metric(public_render.MetricValue(value=Decimal("-0.01225")), "pp")
        == "-1.22 pp"
    )


def test_warming_projection_keeps_eleven_rows_and_hides_ranked_sections() -> None:
    snapshot = _snapshot(count=20)
    projection = render_public_sector_projection(snapshot)
    markdown = projection.markdown_bytes.decode()

    assert snapshot.coverage.status is SectorCoverageStatus.WARMING_UP
    assert len(_table_rows(markdown)) == 11
    assert "## 레이더 요약" not in markdown
    assert "## 텍스트 국면" not in markdown
    assert "사용 가능 · 장기 지표 준비 중" in markdown
    assert "| — |" in markdown


def test_non_close_bar_changes_cannot_change_complete_projection() -> None:
    ordinary = _projection(volume=1_000)
    adversarial = _projection(volume=9_000_000)
    assert adversarial == ordinary


@pytest.mark.parametrize(
    "mutate",
    (
        lambda projection: (
            json.dumps(json.loads(projection.snapshot_bytes), ensure_ascii=False, indent=2).encode()
            + b"\n",
            projection.markdown_bytes,
        ),
        lambda projection: (
            projection.snapshot_bytes,
            projection.markdown_bytes.replace(
                "## 레이더 요약".encode(), "## 변조된 요약".encode(), 1
            ),
        ),
        lambda projection: (
            projection.snapshot_bytes.replace(
                projection.snapshot_id.encode(),
                ("sha256:" + "f" * 64).encode(),
                1,
            ),
            projection.markdown_bytes,
        ),
    ),
)
def test_pair_verifier_rejects_noncanonical_or_mismatched_bytes(
    mutate: Callable[[RenderedPublicSectorProjection], tuple[bytes, bytes]],
) -> None:
    projection = _projection()
    snapshot_bytes, markdown_bytes = mutate(projection)
    with pytest.raises(PublicProjectionError, match=r"public_projection\.invalid"):
        verify_public_sector_projection(snapshot_bytes, markdown_bytes)


def test_pair_verifier_rejects_raw_shape_secret_and_resource_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    sentinel = "short-hf-sentinel"
    monkeypatch.setenv("HF_DATA_API_KEY", sentinel)
    raw = json.loads(projection.snapshot_bytes)
    raw["volume"] = [1, 2, 3]
    with pytest.raises(PublicProjectionError):
        verify_public_sector_projection(
            (json.dumps(raw, sort_keys=True, separators=(",", ":")) + "\n").encode(),
            projection.markdown_bytes,
        )
    with pytest.raises(PublicProjectionError) as exc_info:
        verify_public_sector_projection(
            projection.snapshot_bytes,
            projection.markdown_bytes.replace(b"\n", f" {sentinel}\n".encode(), 1),
        )
    assert sentinel not in str(exc_info.value)
    with pytest.raises(PublicProjectionError):
        verify_public_sector_projection(
            b"{" + b" " * MAX_PUBLIC_PROJECTION_BYTES + b"}\n",
            projection.markdown_bytes,
        )


def test_pair_verifier_closes_deep_json_recursion() -> None:
    nested = b"[" * 1_100 + b"0" + b"]" * 1_100 + b"\n"

    with pytest.raises(PublicProjectionError, match=r"public_projection\.invalid"):
        verify_public_sector_projection(nested, b"placeholder\n")


@pytest.mark.parametrize("mutation", ["duplicate_ordinal", "wrong_denominator"])
def test_pair_verifier_rejects_rehashed_cross_record_rank_mismatch(mutation: str) -> None:
    projection = _projection()
    raw = json.loads(projection.snapshot_bytes)
    first_rank = raw["records"][0]["relative_rank"]
    if mutation == "duplicate_ordinal":
        first_rank["ordinal"] = raw["records"][1]["relative_rank"]["ordinal"]
    else:
        first_rank["comparable_sector_count"] = 11

    with pytest.raises(PublicProjectionError, match=r"public_projection\.invalid"):
        verify_public_sector_projection(
            _canonical_rehashed_snapshot(raw),
            projection.markdown_bytes,
        )


def test_public_render_and_store_have_no_network_or_client_side_runtime() -> None:
    imported: set[str] = set()
    for module in (public_render, public_store):
        path = Path(module.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    forbidden = ("httpx", "requests", "socket", "urllib", "investo.sources")
    assert not {name for name in imported if name.startswith(forbidden)}
    assert "<script" not in _projection().markdown_bytes.decode().casefold()


def test_first_promotion_and_read_are_exact_and_leave_no_transaction_files(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    projection = _projection()
    outcome = promote_public_sector_projection(root, projection)

    markdown_path, snapshot_path = _pair_paths(root)
    assert outcome.status is PublicSectorBuildStatus.PROMOTED
    assert markdown_path.read_bytes() == projection.markdown_bytes
    assert snapshot_path.read_bytes() == projection.snapshot_bytes
    assert read_public_sector_projection(root) == projection
    assert sorted(path.name for path in (root / "site_docs").iterdir()) == ["sectors"]


def test_equal_projection_is_unchanged_without_entering_transaction(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    projection = _projection()
    promote_public_sector_projection(root, projection)
    before = tuple(path.stat().st_mtime_ns for path in _pair_paths(root))
    phases: list[str] = []

    outcome = promote_public_sector_projection(root, projection, _fault_hook=phases.append)

    assert outcome.status is PublicSectorBuildStatus.UNCHANGED
    assert phases == []
    assert tuple(path.stat().st_mtime_ns for path in _pair_paths(root)) == before


def test_changed_projection_promotes_as_one_verified_pair(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    first = _projection()
    second = _projection(slope_delta=Decimal("0.031"))
    promote_public_sector_projection(root, first)

    outcome = promote_public_sector_projection(root, second)

    assert outcome.status is PublicSectorBuildStatus.PROMOTED
    assert outcome.snapshot_id == second.snapshot_id
    assert read_public_sector_projection(root) == second


def test_existing_pair_mismatch_is_rejected_without_replacement(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    first = _projection()
    second = _projection(slope_delta=Decimal("0.031"))
    promote_public_sector_projection(root, first)
    markdown_path, snapshot_path = _pair_paths(root)
    markdown_path.write_bytes(markdown_path.read_bytes() + b"tampered\n")
    before = (markdown_path.read_bytes(), snapshot_path.read_bytes())

    with pytest.raises(PublicSectorStoreError, match="pair_invalid"):
        promote_public_sector_projection(root, second)

    assert (markdown_path.read_bytes(), snapshot_path.read_bytes()) == before


def test_nonpromotable_first_snapshot_writes_nothing(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    warming = _projection(count=20)

    with pytest.raises(PublicSectorStoreError, match="projection_not_promotable"):
        promote_public_sector_projection(root, warming)

    assert not (root / PUBLIC_SECTOR_DIRECTORY).exists()


@pytest.mark.parametrize("failure_phase", ["markdown_promoted", "snapshot_promoted"])
def test_first_publish_failure_removes_partial_pair(
    tmp_path: Path,
    failure_phase: str,
) -> None:
    root = _repository(tmp_path)

    def fail_during_promotion(phase: str) -> None:
        if phase == failure_phase:
            raise RuntimeError("synthetic")

    with pytest.raises(PublicSectorStoreError, match="promotion_failed"):
        promote_public_sector_projection(root, _projection(), _fault_hook=fail_during_promotion)

    markdown_path, snapshot_path = _pair_paths(root)
    assert not markdown_path.exists()
    assert not snapshot_path.exists()
    assert list((root / "site_docs").glob(".sectors.public.*")) == []


def test_marker_post_replace_failure_reenters_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repository(tmp_path)
    original = public_store._write_marker
    failed = False

    def write_then_fail(
        paths: public_store._StorePaths,
        state: public_store._TransactionState,
        *,
        parent_descriptor: int | None = None,
    ) -> None:
        nonlocal failed
        original(paths, state, parent_descriptor=parent_descriptor)
        if not failed:
            failed = True
            raise PublicSectorStoreError("promotion_failed")

    monkeypatch.setattr(public_store, "_write_marker", write_then_fail)
    with pytest.raises(PublicSectorStoreError, match="promotion_failed"):
        promote_public_sector_projection(root, _projection())

    markdown_path, snapshot_path = _pair_paths(root)
    assert not markdown_path.exists()
    assert not snapshot_path.exists()
    assert list((root / "site_docs").glob(".sectors.public.*")) == []


@pytest.mark.parametrize("failure_phase", ["markdown_promoted", "snapshot_promoted"])
def test_failed_replacement_restores_prior_pair_byte_for_byte(
    tmp_path: Path,
    failure_phase: str,
) -> None:
    root = _repository(tmp_path)
    first = _projection()
    second = _projection(slope_delta=Decimal("0.031"))
    promote_public_sector_projection(root, first)
    before = tuple(path.read_bytes() for path in _pair_paths(root))

    def fail_during_promotion(phase: str) -> None:
        if phase == failure_phase:
            raise RuntimeError("synthetic")

    with pytest.raises(PublicSectorStoreError, match="promotion_failed"):
        promote_public_sector_projection(root, second, _fault_hook=fail_during_promotion)

    assert tuple(path.read_bytes() for path in _pair_paths(root)) == before
    assert read_public_sector_projection(root) == first


def test_reader_cannot_recover_an_active_writer_transaction(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    first = _projection()
    second = _projection(slope_delta=Decimal("0.031"))
    promote_public_sector_projection(root, first)
    busy_reasons: list[str] = []

    def try_read_during_promotion(phase: str) -> None:
        if phase != "markdown_promoted":
            return
        with pytest.raises(PublicSectorStoreError) as caught:
            read_public_sector_projection(root)
        busy_reasons.append(caught.value.reason)

    outcome = promote_public_sector_projection(
        root,
        second,
        _fault_hook=try_read_during_promotion,
    )

    assert outcome.status is PublicSectorBuildStatus.PROMOTED
    assert busy_reasons == ["transaction_busy"]
    assert read_public_sector_projection(root) == second


def test_output_symlink_swap_never_writes_outside_repository(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    def replace_output_with_symlink(phase: str) -> None:
        if phase != "prepared":
            return
        output = root / PUBLIC_SECTOR_DIRECTORY
        output.rmdir()
        output.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PublicSectorStoreError, match="promotion_failed"):
        promote_public_sector_projection(
            root,
            _projection(),
            _fault_hook=replace_output_with_symlink,
        )

    assert list(outside.iterdir()) == []


def test_parent_symlink_swap_never_writes_outside_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    parent = root / "site_docs"
    detached_parent = tmp_path / "detached-site-docs"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = public_store._stage_pair
    swapped = False

    def swap_parent_then_stage(
        paths: public_store._StorePaths,
        projection: RenderedPublicSectorProjection,
        *,
        prefix: str,
        parent_descriptor: int,
    ) -> Path:
        nonlocal swapped
        if not swapped:
            swapped = True
            parent.rename(detached_parent)
            parent.symlink_to(outside, target_is_directory=True)
        return original(
            paths,
            projection,
            prefix=prefix,
            parent_descriptor=parent_descriptor,
        )

    monkeypatch.setattr(public_store, "_stage_pair", swap_parent_then_stage)
    with pytest.raises(PublicSectorStoreError, match="promotion_failed"):
        promote_public_sector_projection(root, _projection())

    assert list(outside.iterdir()) == []


def test_completed_rollback_survives_backup_cleanup_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    first = _projection()
    second = _projection(slope_delta=Decimal("0.031"))
    promote_public_sector_projection(root, first)
    original = public_store._complete_transaction
    interrupted = False

    def interrupt_after_backup_removal(
        paths: public_store._StorePaths,
        state: public_store._TransactionState,
        *,
        parent_descriptor: int | None = None,
    ) -> None:
        nonlocal interrupted
        if state.phase == "rolled_back" and state.backup_name is not None and not interrupted:
            interrupted = True
            public_store._remove_unpublished_directory(
                paths.parent / state.backup_name,
                paths,
                public_store._BACKUP_PREFIX,
                parent_descriptor=parent_descriptor,
            )
            raise PublicSectorStoreError("recovery_failed")
        original(paths, state, parent_descriptor=parent_descriptor)

    monkeypatch.setattr(public_store, "_complete_transaction", interrupt_after_backup_removal)

    def fail_after_snapshot(phase: str) -> None:
        if phase == "snapshot_promoted":
            raise RuntimeError("synthetic")

    with pytest.raises(PublicSectorStoreError, match="recovery_failed"):
        promote_public_sector_projection(root, second, _fault_hook=fail_after_snapshot)
    monkeypatch.setattr(public_store, "_complete_transaction", original)

    assert read_public_sector_projection(root) == first
    assert list((root / "site_docs").glob(".sectors.public.*")) == []


@pytest.mark.parametrize("failure_stage", ["partial_backup", "removed_backup", "removed_marker"])
@pytest.mark.parametrize("interrupt_restore", [False, True])
def test_promotion_cleanup_failure_restores_prior_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
    interrupt_restore: bool,
) -> None:
    root = _repository(tmp_path)
    first = _projection()
    second = _projection(slope_delta=Decimal("0.031"))
    promote_public_sector_projection(root, first)
    original = public_store._complete_transaction
    original_write = public_store._write_atomic_fsynced_at
    interrupted = False
    restore_interrupted = False

    def interrupt_rollback_write(
        descriptor: int,
        name: str,
        payload: bytes,
        *,
        reason: public_store.StoreErrorReason,
    ) -> None:
        nonlocal restore_interrupted
        original_write(descriptor, name, payload, reason=reason)
        if (
            interrupt_restore
            and interrupted
            and not restore_interrupted
            and name == PUBLIC_MARKDOWN_NAME
            and payload == first.markdown_bytes
        ):
            restore_interrupted = True
            raise PublicSectorStoreError("recovery_failed")

    def interrupt_cleanup(
        paths: public_store._StorePaths,
        state: public_store._TransactionState,
        *,
        parent_descriptor: int | None = None,
    ) -> None:
        nonlocal interrupted
        if state.phase == "promoting" and state.backup_name is not None and not interrupted:
            interrupted = True
            if failure_stage == "partial_backup":
                (paths.parent / state.backup_name / PUBLIC_MARKDOWN_NAME).unlink()
            elif failure_stage == "removed_backup":
                public_store._remove_unpublished_directory(
                    paths.parent / state.backup_name,
                    paths,
                    public_store._BACKUP_PREFIX,
                    parent_descriptor=parent_descriptor,
                )
            else:
                original(paths, state, parent_descriptor=parent_descriptor)
            raise PublicSectorStoreError("recovery_failed")
        original(paths, state, parent_descriptor=parent_descriptor)

    monkeypatch.setattr(public_store, "_complete_transaction", interrupt_cleanup)
    monkeypatch.setattr(public_store, "_write_atomic_fsynced_at", interrupt_rollback_write)
    with pytest.raises(PublicSectorStoreError, match="recovery_failed"):
        promote_public_sector_projection(root, second)

    assert interrupted
    if interrupt_restore:
        assert restore_interrupted
        # The previous pair must still be recoverable after a second interruption
        # leaves the restored Markdown beside the newly promoted JSON.
        assert read_public_sector_projection(root) == first
    assert tuple(path.read_bytes() for path in _pair_paths(root)) == (
        first.markdown_bytes,
        first.snapshot_bytes,
    )
    assert read_public_sector_projection(root) == first
    assert list((root / "site_docs").glob(".sectors.public.*")) == []


def test_markerless_transaction_orphans_are_removed(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    projection = _projection()
    for prefix in (public_store._PREPARED_PREFIX, public_store._BACKUP_PREFIX):
        orphan = root / "site_docs" / f"{prefix}ABC123"
        orphan.mkdir()
        (orphan / PUBLIC_MARKDOWN_NAME).write_bytes(projection.markdown_bytes)
        (orphan / PUBLIC_SNAPSHOT_NAME).write_bytes(projection.snapshot_bytes)

    assert read_public_sector_projection(root) is None
    assert list((root / "site_docs").glob(".sectors.public.*")) == []


def test_interrupted_cleanup_is_recovered_on_next_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    projection = _projection()
    original = public_store._complete_transaction

    def fail_cleanup(*_args: object, **_kwargs: object) -> None:
        raise PublicSectorStoreError("recovery_failed")

    monkeypatch.setattr(public_store, "_complete_transaction", fail_cleanup)
    with pytest.raises(PublicSectorStoreError, match="recovery_failed"):
        promote_public_sector_projection(root, projection)
    monkeypatch.setattr(public_store, "_complete_transaction", original)

    assert read_public_sector_projection(root) is None
    assert list((root / "site_docs").glob(".sectors.public.*")) == []


def test_last_good_hold_preserves_bytes_and_first_hold_is_blocked(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    codes = (PublicSourceIssueCode.AUTH_REJECTED,)
    blocked = hold_public_sector_last_good(root, failure_codes=codes)

    assert blocked.status is PublicSectorBuildStatus.BLOCKED
    assert not (root / PUBLIC_SECTOR_DIRECTORY).exists()

    projection = _projection()
    promote_public_sector_projection(root, projection)
    before = tuple(path.read_bytes() for path in _pair_paths(root))
    held = hold_public_sector_last_good(root, failure_codes=codes)

    assert held.status is PublicSectorBuildStatus.HELD_LAST_GOOD
    assert held.snapshot_id == projection.snapshot_id
    assert held.as_of_date == _AS_OF
    assert tuple(path.read_bytes() for path in _pair_paths(root)) == before


def test_store_rejects_symlink_target_and_malicious_marker(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / PUBLIC_SECTOR_DIRECTORY).symlink_to(outside, target_is_directory=True)
    with pytest.raises(PublicSectorStoreError, match="path_invalid"):
        promote_public_sector_projection(root, _projection())
    assert list(outside.iterdir()) == []

    (root / PUBLIC_SECTOR_DIRECTORY).unlink()
    marker = root / "site_docs" / ".sectors.public.transaction.json"
    marker.write_text(
        json.dumps(
            {
                "backup_name": None,
                "backup_snapshot_id": None,
                "expected_snapshot_id": _projection().snapshot_id,
                "prepared_name": "../outside",
                "version": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PublicSectorStoreError, match="recovery_failed"):
        read_public_sector_projection(root)
    assert list(outside.iterdir()) == []


def test_store_closes_deep_marker_json_recursion(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    marker = root / "site_docs" / ".sectors.public.transaction.json"
    marker.write_bytes(b"[" * 1_100 + b"0" + b"]" * 1_100 + b"\n")

    with pytest.raises(PublicSectorStoreError, match="recovery_failed"):
        read_public_sector_projection(root)


def test_store_closes_file_read_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repository(tmp_path)
    promote_public_sector_projection(root, _projection())

    def fail_read(*_args: object, **_kwargs: object) -> bytes:
        raise OSError("synthetic-read")

    monkeypatch.setattr(public_store.os, "read", fail_read)
    with pytest.raises(PublicSectorStoreError, match="pair_invalid") as caught:
        read_public_sector_projection(root)
    assert "synthetic-read" not in str(caught.value)


def test_store_removes_owner_bound_atomic_temp_orphans(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    projection = _projection()
    promote_public_sector_projection(root, projection)
    output = root / PUBLIC_SECTOR_DIRECTORY
    orphans = (
        output / f".{PUBLIC_MARKDOWN_NAME}.0123456789abcdef",
        output / f".{PUBLIC_SNAPSHOT_NAME}.fedcba9876543210",
        root / "site_docs" / "..sectors.public.transaction.json.0011223344556677",
    )
    for orphan in orphans:
        orphan.write_bytes(b"orphan")

    assert read_public_sector_projection(root) == projection
    assert all(not orphan.exists() for orphan in orphans)


def test_hold_requires_closed_failure_and_rejects_half_pair(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    with pytest.raises(ValueError, match="must not be empty"):
        hold_public_sector_last_good(root, failure_codes=())

    output = root / PUBLIC_SECTOR_DIRECTORY
    output.mkdir()
    (output / PUBLIC_MARKDOWN_NAME).write_text("partial\n", encoding="utf-8")
    with pytest.raises(PublicSectorStoreError, match="pair_invalid"):
        hold_public_sector_last_good(
            root,
            failure_codes=(PublicDiagnosticCode.TEMPORARILY_UNAVAILABLE,),
        )


def test_store_paths_are_fixed_under_repository_site_docs(tmp_path: Path) -> None:
    relative = tmp_path / "repo"
    relative.mkdir()
    with pytest.raises(PublicSectorStoreError, match="path_invalid"):
        read_public_sector_projection(Path("repo"))

    root = _repository(tmp_path / "nested")
    assert public_store._store_paths(root).output == root / "site_docs" / "sectors"


def test_store_error_traceback_does_not_disclose_rejected_path(tmp_path: Path) -> None:
    rejected = tmp_path / "sensitive-repository-name"
    try:
        read_public_sector_projection(rejected)
    except PublicSectorStoreError:
        rendered = traceback.format_exc()
    else:
        pytest.fail("expected closed store failure")

    assert str(rejected) not in rendered
    assert "public_sector_store.path_invalid" in rendered
