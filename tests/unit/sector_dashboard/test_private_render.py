from __future__ import annotations

import ast
import json
import os
import subprocess
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import investo.sector_dashboard.private_render as private_render_module
from investo.models import (
    BENCHMARK_TICKER,
    SECTOR_TICKERS,
    CoverageSummary,
    NavPoint,
    NavSeries,
    SectorCoverageStatus,
    SectorDashboardSnapshot,
    SectorSeriesBundle,
    SectorTicker,
)
from investo.sector_dashboard.metrics import compute_sector_snapshot
from investo.sector_dashboard.private_render import (
    REPORT_NAME,
    SNAPSHOT_NAME,
    PrivateOutputRejectedError,
    PrivateTransactionError,
    open_private_output_session,
    render_private_projection,
    verify_private_projection,
)

_START = date(2026, 1, 2)


def _series(ticker: SectorTicker, count: int) -> NavSeries:
    points = tuple(
        NavPoint(
            trading_date=_START + timedelta(days=index),
            nav=Decimal("100") + Decimal(index) / Decimal("10"),
        )
        for index in range(count)
    )
    return NavSeries(
        ticker=ticker,
        points=points,
        first_date=points[0].trading_date,
        latest_date=points[-1].trading_date,
    )


def _snapshot(
    status: SectorCoverageStatus = SectorCoverageStatus.NORMAL,
    *,
    fingerprint: str = "a",
) -> SectorDashboardSnapshot:
    if status is SectorCoverageStatus.INSUFFICIENT:
        coverage = CoverageSummary(
            status=status,
            available_sector_count=0,
            benchmark_available=False,
            benchmark_observation_count=0,
            missing_tickers=SECTOR_TICKERS,
        )
        bundle = SectorSeriesBundle(coverage=coverage)
        return compute_sector_snapshot(bundle)

    count = 10 if status is SectorCoverageStatus.WARMING_UP else 70
    missing = SECTOR_TICKERS[-3:] if status is SectorCoverageStatus.PARTIAL else ()
    benchmark = _series(BENCHMARK_TICKER, count)
    sectors = tuple(_series(ticker, count) for ticker in SECTOR_TICKERS if ticker not in missing)
    coverage = CoverageSummary(
        status=status,
        available_sector_count=len(sectors),
        benchmark_available=True,
        common_as_of=benchmark.latest_date,
        benchmark_observation_count=count,
        missing_tickers=missing,
    )
    bundle = SectorSeriesBundle(
        as_of_date=benchmark.latest_date,
        benchmark=benchmark,
        sectors=sectors,
        coverage=coverage,
        input_fingerprint="sha256:" + fingerprint * 64,
    )
    return compute_sector_snapshot(bundle)


def test_normal_projection_is_canonical_private_pair() -> None:
    first = render_private_projection(_snapshot())
    second = render_private_projection(_snapshot())

    assert first.snapshot_bytes == second.snapshot_bytes
    assert first.report_bytes == second.report_bytes
    payload = json.loads(first.snapshot_bytes)
    assert tuple(payload)[:2] == ("schema_version", "snapshot_id")
    assert payload["snapshot_id"] == first.snapshot.snapshot_id
    report = first.report_bytes.decode()
    assert report.index("PRIVATE VALIDATION") < report.index("## 커버리지")
    assert "## 레이더 요약" in report
    assert "## 섹터 지표" in report
    assert "## 텍스트 국면" in report
    assert "private policy sensitivity only" in report
    assert report.count("<!-- snapshot_id:") == 1
    assert "NAV 기준 실현변동성" in report
    assert "가격수익률" not in report


def test_projection_contains_no_unapproved_private_or_public_claim_surface() -> None:
    projection = render_private_projection(_snapshot())
    combined = (projection.snapshot_bytes + projection.report_bytes).decode("utf-8").casefold()
    forbidden = (
        "raw_rows",
        "raw_cells",
        "provider payload",
        "exchange volume",
        "dollar volume",
        "actual flow",
        "shares",
        "holdings",
        "earnings",
        "가격수익률",
        "거래량",
        "거래대금",
        "자금 유입",
        "public ready",
        "license approval",
        "tradingview",
        "archive/",
        "site_docs/",
        "/private/sentinel",
    )
    assert all(fragment.casefold() not in combined for fragment in forbidden)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: value + b"benign changed note\n",
        lambda value: value.replace(
            "## 섹터 지표".encode(),
            "## 섹터 지표 수정".encode(),
            1,
        ),
    ),
)
def test_at_rest_pair_validation_rejects_noncanonical_report(
    mutate: Callable[[bytes], bytes],
) -> None:
    projection = render_private_projection(_snapshot())
    with pytest.raises(PrivateTransactionError):
        private_render_module._validate_pair_bytes(
            projection.snapshot_bytes,
            mutate(projection.report_bytes),
        )


def test_private_runner_has_no_network_or_public_pipeline_import() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    paths = (
        Path(private_render_module.__file__),
        Path(private_render_module.__file__).parent / "__init__.py",
        repository_root / "scripts" / "validate_sector_dashboard_private.py",
    )
    imported: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    forbidden_prefixes = (
        "httpx",
        "requests",
        "socket",
        "urllib",
        "investo.sources",
        "investo.briefing",
        "investo.publisher",
        "investo.notifier",
        "investo.orchestrator",
    )
    assert not {
        name for name in imported if any(name.startswith(prefix) for prefix in forbidden_prefixes)
    }
    source_registry = repository_root / "src" / "investo" / "sources" / "__init__.py"
    assert "sector_dashboard" not in source_registry.read_text(encoding="utf-8")
    reverse_integration_paths = (
        *(
            path
            for package in ("orchestrator", "publisher", "notifier")
            for path in (repository_root / "src" / "investo" / package).rglob("*.py")
        ),
        repository_root / "src" / "investo" / "briefing" / "pipeline.py",
        *(repository_root / ".github" / "workflows").glob("*.yml"),
        repository_root / "mkdocs.yml",
    )
    for path in reverse_integration_paths:
        content = path.read_text(encoding="utf-8")
        assert "sector_dashboard" not in content
        assert "validate_sector_dashboard_private" not in content

    tracked_diff = subprocess.run(
        (
            "git",
            "diff",
            "--no-ext-diff",
            "--",
            "archive",
            "site_docs",
            "mkdocs.yml",
            ".github/workflows",
        ),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "/private/SENTINEL" not in tracked_diff
    assert "validate_sector_dashboard_private" not in tracked_diff
    assert "sector-dashboard-private" not in tracked_diff


@pytest.mark.parametrize(
    ("status", "required", "forbidden"),
    [
        (
            SectorCoverageStatus.PARTIAL,
            ("## 레이더 요약", "## 진단 요약", "데이터 부족"),
            (),
        ),
        (
            SectorCoverageStatus.WARMING_UP,
            ("## 섹터 단기 지표", "## 진단 요약"),
            ("## 레이더 요약", "## 텍스트 국면", "10 bps (primary)"),
        ),
        (
            SectorCoverageStatus.INSUFFICIENT,
            ("기준일 없음", "## 진단 요약"),
            ("## 레이더 요약", "## 섹터 지표", "## 텍스트 국면", "민감도"),
        ),
    ],
)
def test_projection_obeys_coverage_surface(
    status: SectorCoverageStatus,
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> None:
    report = render_private_projection(_snapshot(status)).report_bytes.decode()
    assert all(fragment in report for fragment in required)
    assert all(fragment not in report for fragment in forbidden)


@settings(max_examples=20, deadline=None)
@given(st.text(alphabet="0123456789abcdef", min_size=64, max_size=64))
def test_projection_serialization_is_idempotent_and_round_trips(fingerprint: str) -> None:
    source = _snapshot().model_copy(update={"input_fingerprint": f"sha256:{fingerprint}"})
    projection = render_private_projection(source)

    verify_private_projection(projection.snapshot_bytes, projection.report_bytes)
    restored = SectorDashboardSnapshot.model_validate_json(projection.snapshot_bytes)
    rerendered = render_private_projection(restored.model_copy(update={"snapshot_id": None}))
    assert rerendered.snapshot_bytes == projection.snapshot_bytes
    assert rerendered.report_bytes == projection.report_bytes


def test_projection_verifier_rejects_forbidden_and_mismatched_content() -> None:
    projection = render_private_projection(_snapshot())
    forbidden_report = projection.report_bytes.replace(
        b"PRIVATE VALIDATION",
        "PRIVATE VALIDATION 거래량".encode(),
    )
    with pytest.raises(PrivateTransactionError, match=r"transaction\.failed"):
        verify_private_projection(projection.snapshot_bytes, forbidden_report)

    other = render_private_projection(_snapshot(fingerprint="b"))
    with pytest.raises(PrivateTransactionError, match=r"transaction\.failed"):
        verify_private_projection(projection.snapshot_bytes, other.report_bytes)


def test_projection_rejects_open_rank_reason_vocabulary_without_leaking_it() -> None:
    snapshot = _snapshot(SectorCoverageStatus.PARTIAL)
    record = snapshot.records[-1]
    sentinel = "/private/sentinel-input.xlsx"
    bad_rank = record.relative_rank.model_copy(update={"missing_reason": sentinel})
    bad_record = record.model_copy(update={"relative_rank": bad_rank})
    bad_snapshot = snapshot.model_copy(update={"records": (*snapshot.records[:-1], bad_record)})

    with pytest.raises(PrivateTransactionError) as caught:
        render_private_projection(bad_snapshot)
    assert sentinel not in str(caught.value)


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "private-output"
    return repository, output


def test_pair_commit_is_owner_only_idempotent_and_replace_is_explicit(tmp_path: Path) -> None:
    repository, output = _roots(tmp_path)
    original = _snapshot()
    changed = _snapshot(fingerprint="b")

    with open_private_output_session(output, repository_root=repository) as session:
        first = session.commit(original)
    assert first.changed
    assert stat_mode(output) == 0o700
    assert stat_mode(output / SNAPSHOT_NAME) == 0o600
    assert stat_mode(output / REPORT_NAME) == 0o600
    before = (
        (output / SNAPSHOT_NAME).read_bytes(),
        (output / REPORT_NAME).read_bytes(),
        (output / SNAPSHOT_NAME).stat().st_mtime_ns,
        (output / REPORT_NAME).stat().st_mtime_ns,
    )

    with open_private_output_session(output, repository_root=repository) as session:
        no_op = session.commit(original)
    assert not no_op.changed
    assert (output / SNAPSHOT_NAME).stat().st_mtime_ns == before[2]
    assert (output / REPORT_NAME).stat().st_mtime_ns == before[3]

    with (
        pytest.raises(PrivateOutputRejectedError, match=r"output\.forbidden_path"),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(changed)
    assert (output / SNAPSHOT_NAME).read_bytes() == before[0]
    assert (output / REPORT_NAME).read_bytes() == before[1]

    with open_private_output_session(output, repository_root=repository) as session:
        replaced = session.commit(changed, replace=True)
    assert replaced.changed
    assert replaced.snapshot_id != first.snapshot_id


@pytest.mark.parametrize(
    "phase",
    (
        "render",
        "prepared_fsync",
        "backup",
        "prepared",
        "snapshot_promote",
        "report_promote",
        "verify",
    ),
)
def test_caught_fault_at_each_phase_preserves_old_pair(tmp_path: Path, phase: str) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    old = ((output / SNAPSHOT_NAME).read_bytes(), (output / REPORT_NAME).read_bytes())

    def fail_at(current: str) -> None:
        if current == phase:
            raise RuntimeError("sentinel private value")

    with (
        pytest.raises(PrivateTransactionError, match=r"transaction\.failed") as caught,
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=fail_at)
    assert "sentinel" not in str(caught.value)
    assert (output / SNAPSHOT_NAME).read_bytes() == old[0]
    assert (output / REPORT_NAME).read_bytes() == old[1]
    assert not (output.parent / f".{output.name}.sector-dashboard.transaction.json").exists()


def test_interrupted_promotion_finishes_preserved_prepared_pair_before_new_input(
    tmp_path: Path,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    expected = render_private_projection(_snapshot(fingerprint="b"))

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "snapshot_promote":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=crash)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert marker.exists()
    assert stat_mode(marker) == 0o600
    assert set(_marker_payload(marker)) == {
        "schema_version",
        "phase",
        "prepared_name",
        "backup_name",
        "expected_snapshot_id",
        "backup_snapshot_id",
        "expected_report_sha256",
        "backup_report_sha256",
    }
    with open_private_output_session(output, repository_root=repository):
        assert (output / SNAPSHOT_NAME).read_bytes() == expected.snapshot_bytes
        assert (output / REPORT_NAME).read_bytes() == expected.report_bytes
    assert not marker.exists()


def test_partial_marker_append_recovers_from_last_complete_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    expected = render_private_projection(_snapshot(fingerprint="b"))

    class SimulatedCrash(BaseException):
        pass

    original_write_all = private_render_module._write_all

    def interrupt_marker_append(descriptor: int, data: bytes) -> None:
        if b'"phase":"snapshot_promoted"' in data:
            os.write(descriptor, b"{")
            raise SimulatedCrash
        original_write_all(descriptor, data)

    monkeypatch.setattr(private_render_module, "_write_all", interrupt_marker_append)
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert _marker_payload(marker)["phase"] == "promoting"
    monkeypatch.setattr(private_render_module, "_write_all", original_write_all)
    with open_private_output_session(output, repository_root=repository):
        assert (output / SNAPSHOT_NAME).read_bytes() == expected.snapshot_bytes
        assert (output / REPORT_NAME).read_bytes() == expected.report_bytes
    assert not marker.exists()


def test_marker_fsync_interruption_accepts_last_or_new_complete_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    expected = render_private_projection(_snapshot(fingerprint="b"))

    class SimulatedCrash(BaseException):
        pass

    original_write_all = private_render_module._write_all
    original_fsync = private_render_module.os.fsync
    interrupt_next_fsync = False

    def track_marker_append(descriptor: int, data: bytes) -> None:
        nonlocal interrupt_next_fsync
        original_write_all(descriptor, data)
        if b'"phase":"snapshot_promoted"' in data:
            interrupt_next_fsync = True

    def interrupt_marker_fsync(descriptor: int) -> None:
        nonlocal interrupt_next_fsync
        if interrupt_next_fsync:
            interrupt_next_fsync = False
            raise SimulatedCrash
        original_fsync(descriptor)

    monkeypatch.setattr(private_render_module, "_write_all", track_marker_append)
    monkeypatch.setattr(private_render_module.os, "fsync", interrupt_marker_fsync)
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True)

    monkeypatch.setattr(private_render_module, "_write_all", original_write_all)
    monkeypatch.setattr(private_render_module.os, "fsync", original_fsync)
    with open_private_output_session(output, repository_root=repository):
        assert (output / SNAPSHOT_NAME).read_bytes() == expected.snapshot_bytes
        assert (output / REPORT_NAME).read_bytes() == expected.report_bytes


def test_interrupted_rollback_uses_complete_preserved_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    old = ((output / SNAPSHOT_NAME).read_bytes(), (output / REPORT_NAME).read_bytes())

    class SimulatedCrash(BaseException):
        pass

    original_replace = private_render_module._replace_pair_from
    replace_calls = 0

    def interrupt_first_restore(
        source: Path,
        target: Path,
        *,
        source_fd: int | None = None,
        expected_source_snapshot_id: str | None = None,
        target_fd: int | None = None,
    ) -> None:
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 1:
            raise SimulatedCrash
        original_replace(
            source,
            target,
            source_fd=source_fd,
            expected_source_snapshot_id=expected_source_snapshot_id,
            target_fd=target_fd,
        )

    def caught_fault(current: str) -> None:
        if current == "snapshot_promote":
            raise RuntimeError("caught fault")

    monkeypatch.setattr(private_render_module, "_replace_pair_from", interrupt_first_restore)
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=caught_fault)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert _marker_payload(marker)["phase"] == "rolling_back"
    with open_private_output_session(output, repository_root=repository):
        assert (output / SNAPSHOT_NAME).read_bytes() == old[0]
        assert (output / REPORT_NAME).read_bytes() == old[1]
    assert not marker.exists()


def test_completed_current_pair_does_not_hide_noncanonical_backup_evidence(
    tmp_path: Path,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "report_promote":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=crash)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    payload = _marker_payload(marker)
    backup_report = output.parent / payload["backup_name"] / REPORT_NAME
    backup_report.write_bytes(backup_report.read_bytes() + b"benign changed note\n")

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()
    assert backup_report.exists()


def test_completed_current_pair_does_not_hide_canonical_wrong_backup(
    tmp_path: Path,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "report_promote":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=crash)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    payload = _marker_payload(marker)
    backup_dir = output.parent / str(payload["backup_name"])
    wrong = render_private_projection(_snapshot(fingerprint="c"))
    (backup_dir / SNAPSHOT_NAME).write_bytes(wrong.snapshot_bytes)
    (backup_dir / REPORT_NAME).write_bytes(wrong.report_bytes)

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()
    assert (backup_dir / SNAPSHOT_NAME).read_bytes() == wrong.snapshot_bytes
    assert (backup_dir / REPORT_NAME).read_bytes() == wrong.report_bytes


def test_commit_rejects_noncanonical_current_pair(tmp_path: Path) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    report = output / REPORT_NAME
    report.write_bytes(report.read_bytes() + b"benign changed note\n")

    with (
        pytest.raises(PrivateTransactionError),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot())

    assert report.read_bytes().endswith(b"benign changed note\n")


def test_committed_cleanup_phase_recovers_after_interrupted_directory_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    original_remove = private_render_module._remove_managed_directory
    remove_calls = 0

    def interrupt_first_remove(directory: Path, *, directory_fd: int | None = None) -> None:
        nonlocal remove_calls
        remove_calls += 1
        if remove_calls == 1:
            raise SimulatedCrash
        original_remove(directory, directory_fd=directory_fd)

    monkeypatch.setattr(
        private_render_module,
        "_remove_managed_directory",
        interrupt_first_remove,
    )
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot())

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert _marker_payload(marker)["phase"] == "cleaning_up"
    with open_private_output_session(output, repository_root=repository):
        verify_private_projection(
            (output / SNAPSHOT_NAME).read_bytes(),
            (output / REPORT_NAME).read_bytes(),
        )
    assert not marker.exists()


def test_cleanup_recovery_rejects_dangling_managed_directory_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    original_remove = private_render_module._remove_managed_directory

    def interrupt_cleanup(directory: Path, *, directory_fd: int | None = None) -> None:
        del directory, directory_fd
        raise SimulatedCrash

    monkeypatch.setattr(
        private_render_module,
        "_remove_managed_directory",
        interrupt_cleanup,
    )
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot())

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    prepared = output.parent / str(_marker_payload(marker)["prepared_name"])
    moved = prepared.with_name(prepared.name + "-moved")
    prepared.rename(moved)
    prepared.symlink_to(output.parent / "missing-managed-directory", target_is_directory=True)
    monkeypatch.setattr(
        private_render_module,
        "_remove_managed_directory",
        original_remove,
    )

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()
    assert prepared.is_symlink()
    assert moved.exists()


def test_backup_phase_rejects_unanchored_canonical_current_pair(tmp_path: Path) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "prepared":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=crash)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    payload = _marker_payload(marker)
    assert payload["phase"] == "backup"
    foreign = render_private_projection(_snapshot(fingerprint="c"))
    (output / SNAPSHOT_NAME).write_bytes(foreign.snapshot_bytes)
    (output / REPORT_NAME).write_bytes(foreign.report_bytes)

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()
    assert (output.parent / str(payload["prepared_name"])).exists()
    assert (output.parent / str(payload["backup_name"])).exists()


def test_same_process_promotion_rechecks_anchored_current_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    foreign = render_private_projection(_snapshot(fingerprint="c"))
    original_promote = private_render_module.PrivateOutputSession._promote_prepared

    def replace_current_before_promotion(
        session: private_render_module.PrivateOutputSession,
        prepared_dir: Path,
        backup_dir: Path | None,
        expected_snapshot_id: str | None,
        backup_snapshot_id: str | None,
        expected_report_sha256: str,
        backup_report_sha256: str | None,
        hook: object,
    ) -> bool:
        (output / SNAPSHOT_NAME).write_bytes(foreign.snapshot_bytes)
        (output / REPORT_NAME).write_bytes(foreign.report_bytes)
        return original_promote(
            session,
            prepared_dir,
            backup_dir,
            expected_snapshot_id,
            backup_snapshot_id,
            expected_report_sha256,
            backup_report_sha256,
            hook,
        )

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_promote_prepared",
        replace_current_before_promotion,
    )
    with (
        pytest.raises(PrivateTransactionError),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True)

    assert (output / SNAPSHOT_NAME).read_bytes() == foreign.snapshot_bytes
    assert (output / REPORT_NAME).read_bytes() == foreign.report_bytes


def test_recovered_phase_requires_restored_backup_as_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())

    class SimulatedCrash(BaseException):
        pass

    original_remove = private_render_module._remove_managed_directory

    def interrupt_after_restore(directory: Path, *, directory_fd: int | None = None) -> None:
        del directory, directory_fd
        raise SimulatedCrash

    def caught_fault(current: str) -> None:
        if current == "snapshot_promote":
            raise RuntimeError("caught fault")

    monkeypatch.setattr(
        private_render_module,
        "_remove_managed_directory",
        interrupt_after_restore,
    )
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True, _fault_hook=caught_fault)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert _marker_payload(marker)["phase"] == "recovered"
    candidate = render_private_projection(_snapshot(fingerprint="b"))
    (output / SNAPSHOT_NAME).write_bytes(candidate.snapshot_bytes)
    (output / REPORT_NAME).write_bytes(candidate.report_bytes)
    monkeypatch.setattr(
        private_render_module,
        "_remove_managed_directory",
        original_remove,
    )

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()


def test_post_commit_backup_cleanup_failure_reports_success_and_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    expected = render_private_projection(_snapshot(fingerprint="b"))
    original_create = private_render_module.PrivateOutputSession._create_managed_directory
    original_fsync = private_render_module.os.fsync
    backup_path: Path | None = None
    backup_fd: int | None = None
    interrupted = False

    def track_backup(
        session: private_render_module.PrivateOutputSession,
        kind: str,
    ) -> Path:
        nonlocal backup_fd, backup_path
        created = original_create(session, kind)
        if kind == "backup":
            backup_path = created
            backup_fd = session._managed_fds[created.name][0]
        return created

    def fail_empty_backup_fsync(descriptor: int) -> None:
        nonlocal interrupted
        if (
            backup_fd is not None
            and descriptor == backup_fd
            and not interrupted
            and not os.listdir(descriptor)
        ):
            interrupted = True
            raise OSError("cleanup fsync")
        original_fsync(descriptor)

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        track_backup,
    )
    monkeypatch.setattr(
        private_render_module.os,
        "fsync",
        fail_empty_backup_fsync,
    )
    with open_private_output_session(output, repository_root=repository) as session:
        result = session.commit(_snapshot(fingerprint="b"), replace=True)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert result.changed
    assert interrupted
    assert marker.exists()
    assert backup_path is not None and backup_path.is_dir()
    assert not tuple(backup_path.iterdir())
    assert (output / SNAPSHOT_NAME).read_bytes() == expected.snapshot_bytes
    assert (output / REPORT_NAME).read_bytes() == expected.report_bytes
    monkeypatch.setattr(private_render_module.os, "fsync", original_fsync)
    with open_private_output_session(output, repository_root=repository):
        pass
    assert not marker.exists()


def test_post_commit_partial_backup_cleanup_recovers_from_report_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    original_create = private_render_module.PrivateOutputSession._create_managed_directory
    original_unlink = private_render_module.os.unlink
    backup_path: Path | None = None
    backup_fd: int | None = None
    interrupted = False

    def track_backup(
        session: private_render_module.PrivateOutputSession,
        kind: str,
    ) -> Path:
        nonlocal backup_fd, backup_path
        created = original_create(session, kind)
        if kind == "backup":
            backup_path = created
            backup_fd = session._managed_fds[created.name][0]
        return created

    def fail_report_unlink(
        path: object,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal interrupted
        if dir_fd == backup_fd and path == REPORT_NAME and not interrupted:
            interrupted = True
            raise OSError("cleanup unlink")
        original_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        track_backup,
    )
    monkeypatch.setattr(private_render_module.os, "unlink", fail_report_unlink)
    with open_private_output_session(output, repository_root=repository) as session:
        result = session.commit(_snapshot(fingerprint="b"), replace=True)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert result.changed
    assert interrupted
    assert marker.exists()
    assert backup_path is not None
    assert not (backup_path / SNAPSHOT_NAME).exists()
    assert (backup_path / REPORT_NAME).exists()
    monkeypatch.setattr(private_render_module.os, "unlink", original_unlink)
    with open_private_output_session(output, repository_root=repository):
        pass
    assert not marker.exists()


def test_interrupted_complete_prepared_pair_finishes_on_next_session(tmp_path: Path) -> None:
    repository, output = _roots(tmp_path)
    expected = render_private_projection(_snapshot())

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "prepared":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(), _fault_hook=crash)

    assert not (output / SNAPSHOT_NAME).exists()
    with open_private_output_session(output, repository_root=repository):
        assert (output / SNAPSHOT_NAME).read_bytes() == expected.snapshot_bytes
        assert (output / REPORT_NAME).read_bytes() == expected.report_bytes


def test_interrupted_mismatched_prepared_pair_fails_closed_and_keeps_evidence(
    tmp_path: Path,
) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "prepared":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(), _fault_hook=crash)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    marker_payload = _marker_payload(marker)
    prepared_report = output.parent / marker_payload["prepared_name"] / REPORT_NAME
    prepared_report.write_bytes(
        prepared_report.read_bytes().replace(b"snapshot_id", b"snapshot_ID")
    )

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()
    assert prepared_report.exists()
    assert not (output / SNAPSHOT_NAME).exists()
    assert not (output / REPORT_NAME).exists()


def test_recovery_refuses_disagreeing_current_and_prepared_pairs(tmp_path: Path) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "prepared":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(), _fault_hook=crash)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    prepared_name = _marker_payload(marker)["prepared_name"]
    prepared_dir = output.parent / str(prepared_name)
    foreign = render_private_projection(_snapshot(fingerprint="b"))
    (output / SNAPSHOT_NAME).write_bytes(foreign.snapshot_bytes)
    (output / REPORT_NAME).write_bytes(foreign.report_bytes)
    (output / SNAPSHOT_NAME).chmod(0o600)
    (output / REPORT_NAME).chmod(0o600)

    with pytest.raises(PrivateTransactionError):
        open_private_output_session(output, repository_root=repository)
    assert marker.exists()
    assert prepared_dir.exists()
    assert (output / SNAPSHOT_NAME).read_bytes() == foreign.snapshot_bytes
    assert (output / REPORT_NAME).read_bytes() == foreign.report_bytes


def test_interrupted_caught_abort_recovers_to_no_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    original_unlink = private_render_module._unlink_projection_if_present
    unlink_calls = 0

    def interrupt_first_unlink(path: Path, *, directory_fd: int | None = None) -> None:
        nonlocal unlink_calls
        unlink_calls += 1
        if unlink_calls == 1:
            raise SimulatedCrash
        original_unlink(path, directory_fd=directory_fd)

    def fail_after_snapshot(current: str) -> None:
        if current == "snapshot_promote":
            raise RuntimeError("caught fault")

    monkeypatch.setattr(
        private_render_module,
        "_unlink_projection_if_present",
        interrupt_first_unlink,
    )
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(), _fault_hook=fail_after_snapshot)

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert _marker_payload(marker)["phase"] == "aborting"
    with open_private_output_session(output, repository_root=repository):
        assert not (output / SNAPSHOT_NAME).exists()
        assert not (output / REPORT_NAME).exists()
    assert not marker.exists()


def test_session_rejects_public_overlap_symlink_permissions_and_live_lock(tmp_path: Path) -> None:
    repository, output = _roots(tmp_path)
    with pytest.raises(PrivateOutputRejectedError):
        open_private_output_session(repository / "private", repository_root=repository)

    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(PrivateOutputRejectedError):
        open_private_output_session(alias, repository_root=repository)

    with open_private_output_session(output, repository_root=repository) as first:
        input_file = output / "input.xlsx"
        input_file.touch(mode=0o600)
        with pytest.raises(PrivateOutputRejectedError):
            first.validate_input_paths((input_file,))
        with pytest.raises(PrivateTransactionError):
            open_private_output_session(output, repository_root=repository)

    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    os.chmod(output / REPORT_NAME, 0o644)
    with (
        pytest.raises(PrivateOutputRejectedError),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot())


def test_output_resolution_rejects_lstat_to_resolve_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "private-output"
    output.mkdir(mode=0o700)
    moved = tmp_path / "private-output-moved"
    target = tmp_path / "swap-target"
    target.mkdir(mode=0o700)
    original_verify = private_render_module._verify_owned_entry
    output_checks = 0

    def swap_after_first_check(
        path: Path,
        *,
        kind: str,
        mode: int,
    ) -> os.stat_result:
        nonlocal output_checks
        result = original_verify(path, kind=kind, mode=mode)
        if path == output:
            output_checks += 1
            if output_checks == 1:
                output.rename(moved)
                output.symlink_to(target, target_is_directory=True)
        return result

    monkeypatch.setattr(private_render_module, "_verify_owned_entry", swap_after_first_check)
    with pytest.raises(PrivateOutputRejectedError):
        private_render_module._prepare_output_directory(output, repository)


def test_promotion_uses_pinned_output_directory_after_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    moved_output = output.with_name("private-output-moved")
    original_write_copies = private_render_module._write_promotion_copies_at
    swapped = False

    def swap_after_preparing(
        source_fd: int,
        pair: private_render_module._ValidatedPair,
    ) -> None:
        nonlocal swapped
        original_write_copies(source_fd, pair)
        if not swapped:
            swapped = True
            output.rename(moved_output)
            output.symlink_to(repository, target_is_directory=True)

    monkeypatch.setattr(
        private_render_module,
        "_write_promotion_copies_at",
        swap_after_preparing,
    )
    with (
        pytest.raises(PrivateTransactionError),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot())

    assert output.is_symlink()
    assert not (repository / SNAPSHOT_NAME).exists()
    assert not (repository / REPORT_NAME).exists()
    assert (moved_output / SNAPSHOT_NAME).exists()


@pytest.mark.parametrize("swapped_kind", ("prepared", "backup"))
def test_managed_directory_swap_never_writes_through_repository_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swapped_kind: str,
) -> None:
    repository, output = _roots(tmp_path)
    if swapped_kind == "backup":
        with open_private_output_session(output, repository_root=repository) as session:
            session.commit(_snapshot())
    original_create = private_render_module.PrivateOutputSession._create_managed_directory
    moved: Path | None = None

    def swap_created_directory(
        session: private_render_module.PrivateOutputSession,
        kind: str,
    ) -> Path:
        nonlocal moved
        created = original_create(session, kind)
        if kind == swapped_kind:
            moved = created.with_name(created.name + "-moved")
            created.rename(moved)
            created.symlink_to(repository, target_is_directory=True)
        return created

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        swap_created_directory,
    )
    with (
        pytest.raises(PrivateTransactionError),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(
            _snapshot(fingerprint="b"),
            replace=swapped_kind == "backup",
        )

    assert moved is not None
    assert not (repository / SNAPSHOT_NAME).exists()
    assert not (repository / REPORT_NAME).exists()


def test_hardlinked_transaction_marker_is_rejected_without_mutating_victim(
    tmp_path: Path,
) -> None:
    repository, output = _roots(tmp_path)
    output.mkdir(mode=0o700)
    victim = repository / "transaction-state.json"
    victim.write_bytes(
        b'{"schema_version":1,"phase":"locked","prepared_name":null,'
        b'"backup_name":null,"expected_snapshot_id":null}\n'
    )
    victim.chmod(0o600)
    before = victim.read_bytes()
    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    os.link(victim, marker)

    with pytest.raises(PrivateOutputRejectedError):
        open_private_output_session(output, repository_root=repository)

    assert victim.read_bytes() == before
    assert victim.stat().st_nlink == 2
    assert marker.exists()


@pytest.mark.parametrize("initial_bytes", (b"", b"{"))
def test_interrupted_initial_marker_write_recovers_as_locked_state(
    tmp_path: Path,
    initial_bytes: bytes,
) -> None:
    repository, output = _roots(tmp_path)
    output.mkdir(mode=0o700)
    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    marker.write_bytes(initial_bytes)
    marker.chmod(0o600)

    with open_private_output_session(output, repository_root=repository):
        pass

    assert not marker.exists()


def test_recovery_oserror_is_typed_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    def crash(current: str) -> None:
        if current == "prepared":
            raise SimulatedCrash

    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(), _fault_hook=crash)

    sentinel = "/private/SENTINEL-workbook.xlsx"

    def fail_recovery(session: private_render_module.PrivateOutputSession) -> None:
        del session
        raise OSError(sentinel)

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_recover_interrupted_transaction",
        fail_recovery,
    )
    with pytest.raises(PrivateTransactionError) as caught:
        open_private_output_session(output, repository_root=repository)
    assert sentinel not in str(caught.value)


def test_marker_open_closes_descriptor_when_owner_mode_setup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "marker.json"
    opened: list[int] = []
    closed: list[int] = []
    original_open = private_render_module.os.open
    original_close = private_render_module.os.close

    def track_open(*args: object, **kwargs: object) -> int:
        descriptor = original_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def track_close(descriptor: int) -> None:
        closed.append(descriptor)
        original_close(descriptor)

    def fail_chmod(descriptor: int, mode: int) -> None:
        del descriptor, mode
        raise OSError

    monkeypatch.setattr(private_render_module.os, "open", track_open)
    monkeypatch.setattr(private_render_module.os, "close", track_close)
    monkeypatch.setattr(private_render_module.os, "fchmod", fail_chmod)

    with pytest.raises(PrivateOutputRejectedError):
        private_render_module._open_and_lock_marker(marker)
    assert opened
    assert opened[-1] in closed


def test_managed_directory_creation_failure_removes_owned_empty_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    original_chmod = private_render_module.os.chmod

    with open_private_output_session(output, repository_root=repository) as session:

        def fail_prepared_chmod(path: object, mode: int, *args: object, **kwargs: object) -> None:
            if ".prepared-" in str(path):
                raise OSError
            original_chmod(path, mode, *args, **kwargs)

        monkeypatch.setattr(private_render_module.os, "chmod", fail_prepared_chmod)
        with pytest.raises(PrivateTransactionError):
            session.commit(_snapshot())

    assert not tuple(output.parent.glob(f".{output.name}.prepared-*"))


def test_interrupted_directory_creation_is_removed_during_locked_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)

    class SimulatedCrash(BaseException):
        pass

    original_create = private_render_module.PrivateOutputSession._create_managed_directory

    def create_then_interrupt(
        session: private_render_module.PrivateOutputSession,
        kind: str,
    ) -> Path:
        original_create(session, kind)
        raise SimulatedCrash

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        create_then_interrupt,
    )
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot())

    marker = output.parent / f".{output.name}.sector-dashboard.transaction.json"
    assert marker.exists()
    assert tuple(output.parent.glob(f".{output.name}.prepared-*"))
    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        original_create,
    )
    with open_private_output_session(output, repository_root=repository):
        pass
    assert not marker.exists()
    assert not tuple(output.parent.glob(f".{output.name}.prepared-*"))


def test_interrupted_backup_directory_creation_keeps_current_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, output = _roots(tmp_path)
    with open_private_output_session(output, repository_root=repository) as session:
        session.commit(_snapshot())
    old_pair = ((output / SNAPSHOT_NAME).read_bytes(), (output / REPORT_NAME).read_bytes())

    class SimulatedCrash(BaseException):
        pass

    original_create = private_render_module.PrivateOutputSession._create_managed_directory

    def interrupt_backup_creation(
        session: private_render_module.PrivateOutputSession,
        kind: str,
    ) -> Path:
        created = original_create(session, kind)
        if kind == "backup":
            raise SimulatedCrash
        return created

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        interrupt_backup_creation,
    )
    with (
        pytest.raises(SimulatedCrash),
        open_private_output_session(output, repository_root=repository) as session,
    ):
        session.commit(_snapshot(fingerprint="b"), replace=True)

    monkeypatch.setattr(
        private_render_module.PrivateOutputSession,
        "_create_managed_directory",
        original_create,
    )
    with open_private_output_session(output, repository_root=repository):
        assert (output / SNAPSHOT_NAME).read_bytes() == old_pair[0]
        assert (output / REPORT_NAME).read_bytes() == old_pair[1]
    assert not tuple(output.parent.glob(f".{output.name}.prepared-*"))
    assert not tuple(output.parent.glob(f".{output.name}.backup-*"))


def test_secure_read_rechecks_mode_on_open_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = tmp_path / "projection.json"
    projection.write_bytes(b"safe")
    projection.chmod(0o600)
    original_open = private_render_module.os.open

    def chmod_after_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        descriptor = original_open(path, flags, *args, **kwargs)
        Path(path).chmod(0o644)
        return descriptor

    monkeypatch.setattr(private_render_module.os, "open", chmod_after_open)
    with pytest.raises(PrivateTransactionError):
        private_render_module._read_secure_file(projection)


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _marker_payload(path: Path) -> dict[str, object]:
    complete_records = [
        record[:-1]
        for record in path.read_bytes().splitlines(keepends=True)
        if record.endswith(b"\n")
    ]
    assert complete_records
    payload = json.loads(complete_records[-1])
    assert isinstance(payload, dict)
    return payload
