"""u22: source expansion must not overflow or hide status groups on the card.

Outcomes here are synthetic builder inputs, not provider-response fixtures.
The regression counts match the 2026-11-12 runtime failure (target Nov 11).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

import pytest

from investo._internal.archive_layout import ArchiveLayout
from investo._internal.public_quality_language import first_forbidden_public_evidence
from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.models.coverage import SourceOutcome
from investo.models.segments import SegmentCoverage
from investo.models.watchlist import WatchlistImpact
from investo.visuals.assets import prepare_segment_visual_assets, validate_visual_asset
from investo.visuals.cards import build_data_confidence_card
from investo.visuals.provenance import read_manifest
from investo.visuals.render import render_card_svg

_TARGET = date(2026, 11, 11)


def _outcomes(
    failed: int = 0, zero: int = 0, skipped: int = 0, ok: int = 0
) -> tuple[SourceOutcome, ...]:
    return (
        *(
            SourceOutcome.from_failure(
                f"failed-{i}", "news", message="Connection reset", transient=True
            )
            for i in range(failed)
        ),
        *(SourceOutcome.zero(f"zero-{i}", "calendar") for i in range(zero)),
        *(
            SourceOutcome.skipped(f"skipped-{i}", "news", reason="access_denied")
            for i in range(skipped)
        ),
        *(SourceOutcome.ok(f"ok-{i}", "macro", item_count=1) for i in range(ok)),
    )


def _coverage(outcomes: tuple[SourceOutcome, ...]) -> SegmentCoverage:
    # Test the card's projection of an existing verdict, not coverage classification.
    return SegmentCoverage(
        segment="us-equity",
        status="partial",
        item_count=sum(outcome.item_count for outcome in outcomes),
        source_count=sum(outcome.status == "ok" for outcome in outcomes),
        categories=("macro",),
        missing_categories=("price", "news"),
        reason_codes=("SOURCE_FAILED",),
        source_outcomes=outcomes,
    )


@pytest.mark.parametrize("healthy_count", [16, 13])
def test_incident_counts_fit_all_four_statuses_without_mutating_coverage(
    healthy_count: int,
) -> None:
    # Also reproduce the pre-expansion variant: removing the three healthy
    # macro adapters used to leave the same 13-row validation failure.
    coverage = _coverage(_outcomes(failed=3, zero=7, skipped=2, ok=healthy_count))
    before = asdict(coverage)

    card = build_data_confidence_card(_TARGET, coverage)

    assert [(row.source_name, row.status) for row in card.source_rows] == [
        ("수집 실패 소스 3개", "failed"),
        ("0건 반환 소스 7개", "zero"),
        ("비활성 소스 2개", "skipped"),
        (f"정상 {healthy_count}개", "ok"),
    ]
    assert card.source_rows[0].detail == "대표 failed-0 · Connection reset"
    assert card.source_rows[1].detail == "대표 zero-0 · 0건 반환"
    assert card.source_rows[2].detail == "대표 skipped-0 · 접근 제한"
    assert card.source_rows[3].detail == f"ok-0, ok-1, ok-2 외 {healthy_count - 3}개"
    assert card.coverage_status == coverage.status
    assert (card.item_count, card.source_count) == (coverage.item_count, coverage.source_count)
    assert card.reason_labels == coverage.reason_labels
    assert card.missing_categories == ("가격", "뉴스")
    assert asdict(coverage) == before
    assert card == build_data_confidence_card(_TARGET, coverage)


def test_four_or_fewer_rows_preserve_individual_detail_and_priority() -> None:
    outcomes = _outcomes(failed=1, zero=1, skipped=1, ok=2)
    card = build_data_confidence_card(_TARGET, _coverage(tuple(reversed(outcomes))))
    assert [row.model_dump() for row in card.source_rows] == [
        {"source_name": "failed-0", "status": "failed", "detail": "Connection reset"},
        {"source_name": "zero-0", "status": "zero", "detail": "0건 반환"},
        {"source_name": "skipped-0", "status": "skipped", "detail": "접근 제한"},
        {"source_name": "정상 2개", "status": "ok", "detail": "ok-1, ok-0"},
    ]


@pytest.mark.parametrize("total", [5, 12, 13, 1000])
@pytest.mark.parametrize(
    "status,label",
    [("failed", "수집 실패 소스"), ("zero", "0건 반환 소스"), ("skipped", "비활성 소스")],
)
def test_large_single_status_does_not_invent_a_healthy_summary(
    total: int, status: str, label: str
) -> None:
    outcomes = _outcomes(
        failed=total if status == "failed" else 0,
        zero=total if status == "zero" else 0,
        skipped=total if status == "skipped" else 0,
    )
    rows = build_data_confidence_card(_TARGET, _coverage(outcomes)).source_rows
    assert len(rows) == 1
    assert (rows[0].status, rows[0].source_name) == (status, f"{label} {total}개")


def test_overflow_preserves_singleton_groups_and_different_skip_reasons() -> None:
    outcomes = (
        *_outcomes(failed=1, zero=1, skipped=1, ok=1),
        SourceOutcome.skipped("removed", "news", reason="endpoint_removed"),
    )
    rows = build_data_confidence_card(_TARGET, _coverage(outcomes)).source_rows
    assert [row.source_name for row in rows] == [
        "failed-0",
        "zero-0",
        "비활성 소스 2개",
        "정상 1개",
    ]
    assert rows[0].detail == "Connection reset"
    assert rows[2].detail == "대표 skipped-0 · 접근 제한"
    assert outcomes[-1].skip_reason_label == "종료된 수집 경로"


def test_empty_outcomes_have_no_rows() -> None:
    assert build_data_confidence_card(_TARGET, _coverage(())).source_rows == ()


def test_healthy_only_and_aggregated_long_details_fit_the_input_contract() -> None:
    healthy = tuple(SourceOutcome.ok(str(i) * 100, "macro", item_count=1) for i in range(3))
    card = build_data_confidence_card(_TARGET, _coverage(healthy))
    assert len(card.source_rows) == 1
    assert card.source_rows[0].source_name == "정상 3개"
    assert len(card.source_rows[0].detail) == 160
    assert card.source_rows[0].detail.endswith("…")
    failure = SourceOutcome.from_failure(
        "f" * 100, "news", message="upstream connection reset " * 5, transient=False
    )
    card = build_data_confidence_card(_TARGET, _coverage((failure, *_outcomes(failed=5))))
    assert len(card.source_rows[0].detail) == 160
    assert card.source_rows[0].detail.startswith("대표 ")
    assert card.source_rows[0].detail.endswith("…")


def test_compacted_failure_detail_remains_redacted_and_svg_escaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "fake-only-regression-secret-93827"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", secret)
    failure = SourceOutcome.from_failure(
        "broken", "news", message=f"<svg> {secret}", transient=False
    )
    card = build_data_confidence_card(_TARGET, _coverage((failure, *_outcomes(failed=5))))
    assert secret not in card.source_rows[0].detail
    assert "REDACTED" in card.source_rows[0].detail
    for variant in ("light", "dark"):
        svg = render_card_svg(card, variant=variant)
        assert "대표 broken" in svg
        # Existing markdown cleanup removes '>' before XML escaping.
        assert "&lt;svg" in svg
        assert "<svg>" not in svg
        assert secret not in svg
        ElementTree.fromstring(svg)


def test_incident_counts_complete_visual_asset_preparation(tmp_path: Path) -> None:
    coverage = _coverage(_outcomes(failed=3, zero=7, skipped=2, ok=16))
    briefing = Briefing(
        target_date=_TARGET,
        market_summary="확인된 데이터 요약",
        key_issues="이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="일정",
        disclaimer=DISCLAIMER,
        rendered_markdown=f"# 미국 증시 시황\n\n## ① 요약\n확인된 데이터 요약\n\n{DISCLAIMER}",
    )
    prepared = prepare_segment_visual_assets(
        briefing,
        archive_layout=ArchiveLayout(tmp_path / "archive"),
        target_date=_TARGET,
        segment="us-equity",
        items=(),
        coverage=coverage,
        watchlist_impact=WatchlistImpact(configured=False, matches=()),
    )
    light = next(path for path in prepared.asset_paths if path.name == "data-confidence.svg")
    dark = next(
        path for path in prepared.companion_paths if path.name == "data-confidence-dark.svg"
    )
    validate_visual_asset(light)
    assert read_manifest(light).additional_metadata["dark_variant"] == dark.name
    for path in (light, dark):
        svg = path.read_text(encoding="utf-8")
        root = ElementTree.fromstring(svg)
        assert (root.attrib["width"], root.attrib["height"]) == ("1200", "630")
        for label in (
            "수집 실패 소스 3개",
            "0건 반환 소스 7개",
            "비활성 소스 2개",
            "정상 16개",
            "정보 제공용 시황 카드",
        ):
            assert label in svg
        assert first_forbidden_public_evidence(svg) is None
    assert "2026-11-11.assets/data-confidence.svg" in prepared.briefing.rendered_markdown
    assert "2026-11-11.assets/data-confidence-dark.svg" in prepared.briefing.rendered_markdown
    assert DISCLAIMER in prepared.briefing.rendered_markdown
