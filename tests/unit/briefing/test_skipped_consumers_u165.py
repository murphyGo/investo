"""A deliberate non-attempt remains visible and cannot improve data health."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
import yaml

from investo.briefing._reader_enhance.coverage_badge import _render_coverage_badge
from investo.briefing.event_input import event_collection_limited
from investo.briefing.event_trace import collection_stage_receipt
from investo.briefing.quality_eval import (
    compute_quality_history,
    compute_quality_kpis,
    render_quality_page,
)
from investo.briefing.quality_history import QualitySnapshot, append_quality_snapshot
from investo.briefing.segments import build_segment_coverage, resolve_macro_actual_health
from investo.models import NormalizedItem, SourceOutcome
from investo.models.event_narratives import EventGenerationPayload
from investo.models.events import EventSelectionPlan
from investo.orchestrator.source_health import append_daily_coverage, detect_consecutive_failed
from investo.orchestrator.weekly_ops_digest import build_weekly_digest_text
from investo.publisher.event_blocks import COLLECTION_LIMITED_EVENTS, event_empty_message
from investo.publisher.evidence_accounting import count_rendered_evidence
from investo.visuals.cards import build_data_confidence_card
from investo.visuals.render import render_card_svg

_DAY = date(2026, 10, 8)
_SKIP = SourceOutcome.skipped("coingecko-price", "price", reason="operator_disabled")


def _coverage():
    items = [
        NormalizedItem(
            source_name="theblock-crypto",
            category="news",
            title="Synthetic news",
            published_at=datetime(2026, 10, 8, tzinfo=UTC),
        )
        for _ in range(30)
    ]
    items += [
        NormalizedItem(
            source_name="defillama-market-structure",
            category="price",
            title="Synthetic independent context",
            published_at=datetime(2026, 10, 8, tzinfo=UTC),
        )
    ]
    return build_segment_coverage("crypto", items, source_outcomes=(_SKIP,), body_used_count=5)


def test_all_core_skipped_is_limited_and_counts_are_truthful() -> None:
    coverage = _coverage()
    assert coverage.status == "limited"
    assert coverage.targeted_count == coverage.skipped_count == 1
    assert coverage.attempted_count == coverage.succeeded_count == coverage.zero_count == 0
    assert coverage.failed_count == coverage.body_used_count == 0
    assert "CORE_SKIPPED" in coverage.reason_codes
    assert "CORE_ZERO" not in coverage.reason_codes
    badge = _render_coverage_badge(coverage)
    assert "시도 0 / 비활성 1" in badge
    assert "coingecko-price 비활성 (운영자 비활성 설정)" in badge
    card = build_data_confidence_card(_DAY, coverage)
    assert card.source_rows[0].status == "skipped"
    assert card.source_rows[0].detail == "운영자 비활성 설정"
    svg = render_card_svg(card)
    assert "비활성" in svg and "운영자 비활성 설정" in svg


def test_skipped_macro_is_missing_and_skipped_news_is_not_completed() -> None:
    macro = SourceOutcome.skipped("bea-macro-actuals", "macro", reason="operator_disabled")
    assert (
        resolve_macro_actual_health(
            "us-equity", (), (macro,), macro_sensitive_claim_made=True
        ).status
        == "missing"
    )
    news = SourceOutcome.skipped("cnbc-top-news", "news", reason="access_denied")
    assert event_collection_limited((), (news,))
    payload = EventGenerationPayload(
        plan=EventSelectionPlan(),
        narratives=(),
        collection_limited=event_collection_limited((), (news,)),
    )
    assert event_empty_message(payload) == COLLECTION_LIMITED_EVENTS
    assert not event_collection_limited((), (SourceOutcome.zero("fed-speech-rss", "news"),))
    receipt = collection_stage_receipt((), (news,))
    assert receipt.status == "failed" and receipt.count is None
    assert receipt.trace[0].reason == "source_unavailable"
    empty = collection_stage_receipt((), (SourceOutcome.zero("fed-speech-rss", "news"), news))
    assert empty.status == "completed" and empty.count == 0


def test_skip_never_counts_as_public_body_use() -> None:
    markdown = "## ① 요약\n[coingecko-price](https://www.coingecko.com/) 가격 미확보."
    assert (
        count_rendered_evidence(
            markdown, segment="crypto", source_outcomes=(_SKIP,)
        ).body_used_count
        == 0
    )
    healthy = SourceOutcome.ok("theblock-crypto", "news", 1)
    assert (
        count_rendered_evidence(
            markdown, segment="crypto", source_outcomes=(_SKIP, healthy)
        ).body_used_count
        == 0
    )


@pytest.mark.parametrize(
    "link",
    ["[CNBC](https://www.cnbc.com/world/)", '<a href="https://www.cnbc.com/world/">자료</a>'],
)
def test_skipped_unique_provider_domain_is_not_body_use(link) -> None:
    skipped = SourceOutcome.skipped("cnbc-top-news", "news", reason="access_denied")
    healthy = SourceOutcome.ok("sec-newsroom-rss", "news", 1)
    counts = count_rendered_evidence(
        "## ① 요약\n" + link + " 자료 미확보.",
        segment="us-equity",
        source_outcomes=(skipped, healthy),
    )
    assert counts.body_used_count == 0


def test_healthy_sibling_provider_domain_keeps_its_evidence() -> None:
    healthy = SourceOutcome.ok("coingecko-global-market", "price", 1)
    counts = count_rendered_evidence(
        "## ① 요약\n[CoinGecko](https://www.coingecko.com/) 전체시장.",
        segment="crypto",
        source_outcomes=(_SKIP, healthy),
    )
    assert counts.body_used_count == 1


def test_canonical_attempt_floor_reconciles_stale_all_skipped_kpi(tmp_path) -> None:
    from investo.briefing.quality_eval import QualityKPIs
    from investo.publisher.quality_consistency import reconcile_kpis_with_history

    path = tmp_path / "quality.jsonl"
    snapshot = QualitySnapshot(
        source_liveness=1.0,
        figures_presence=0.0,
        fallback_ratio=0.0,
        published_segments=0,
        total_items=1,
        total_failed_sources=0,
        current_run_configured_sources=2,
        current_run_attempted_sources=1,
        current_run_skipped_sources=1,
    )
    append_quality_snapshot(_DAY, snapshot=snapshot, history_path=path)
    kpis = QualityKPIs(
        today=_DAY,
        window_days=7,
        runs_observed=1,
        runs_with_failed_source=0,
        briefings_observed=0,
        briefings_data_limited=0,
        briefings_with_figures=0,
        runs_attempted=0,
        configured_sources=2,
        skipped_sources=2,
        source_counts_by_date=((_DAY.isoformat(), 2, 2, 0, 0),),
    )
    reconciled = reconcile_kpis_with_history(kpis, target_date=_DAY, history_path=path)
    assert reconciled.runs_attempted == 1 and reconciled.source_liveness_rate == 1.0
    assert reconciled.configured_sources == 2 and reconciled.skipped_sources == 1
    assert "| 수집 시도 소스 누적 | 1 회 | 1 회 |" in render_quality_page(reconciled)


def test_skipped_history_resets_failures_and_same_date_latest_wins(tmp_path) -> None:
    path = tmp_path / "coverage.jsonl"
    failed = SourceOutcome.from_failure(
        "coingecko-price", "price", message="offline", transient=True
    )
    for offset in (2, 1, 0):
        append_daily_coverage(_DAY - timedelta(days=offset), (failed,), path=path)
    assert detect_consecutive_failed(today=_DAY, path=path) == ("coingecko-price",)
    append_daily_coverage(_DAY, (_SKIP,), path=path)
    assert detect_consecutive_failed(today=_DAY, path=path) == ()
    row = json.loads(path.read_text().splitlines()[-1])
    assert row["outcomes"][0]["skip_reason"] == "operator_disabled"
    assert "skip_reason" not in json.loads(path.read_text().splitlines()[0])["outcomes"][0]


def test_all_skipped_kpi_and_digest_use_na(tmp_path) -> None:
    path = tmp_path / "coverage.jsonl"
    append_daily_coverage(_DAY, (_SKIP,), path=path)
    kpis = compute_quality_kpis(_DAY, coverage_path=path, archive_root=tmp_path / "archive")
    assert kpis.runs_observed == 1 and kpis.runs_attempted == 0
    assert kpis.source_liveness_rate is None
    assert kpis.configured_sources == kpis.skipped_sources == 1
    assert "| 소스 라이브니스 | n/a | 0 회 |" in render_quality_page(kpis)
    digest = build_weekly_digest_text(_DAY, path=path)
    assert "성공률: n/a" in digest and "비활성 1" in digest


def test_same_date_all_skip_replaces_failure_numerator_and_denominator(tmp_path) -> None:
    from investo.publisher.quality_consistency import reconcile_kpis_with_history

    coverage_path = tmp_path / "coverage.jsonl"
    history_path = tmp_path / "quality.jsonl"
    failed = SourceOutcome.from_failure(
        "coingecko-price", "price", message="offline", transient=True
    )
    for day in (_DAY - timedelta(days=1), _DAY):
        append_daily_coverage(day, (failed,), path=coverage_path)
    kpis = compute_quality_kpis(
        _DAY, coverage_path=coverage_path, archive_root=tmp_path / "archive"
    )
    snapshot = QualitySnapshot(
        source_liveness=None,
        figures_presence=0.0,
        fallback_ratio=1.0,
        published_segments=0,
        total_items=0,
        total_failed_sources=0,
        current_run_configured_sources=1,
        current_run_attempted_sources=0,
        current_run_skipped_sources=1,
    )
    append_quality_snapshot(_DAY, snapshot=snapshot, history_path=history_path)
    reconciled = reconcile_kpis_with_history(kpis, target_date=_DAY, history_path=history_path)
    assert reconciled.runs_attempted == reconciled.runs_with_failed_source == 1
    assert reconciled.failed_sources == 1 and reconciled.skipped_sources == 1
    assert reconciled.source_liveness_rate == 0.0


def test_mixed_historical_rows_exclude_only_non_attempt_runs(tmp_path) -> None:
    path = tmp_path / "coverage.jsonl"
    append_daily_coverage(_DAY - timedelta(days=2), (_SKIP,), path=path)
    failed = SourceOutcome.from_failure(
        "coingecko-price", "price", message="offline", transient=True
    )
    append_daily_coverage(_DAY - timedelta(days=1), (failed, _SKIP), path=path)
    append_daily_coverage(_DAY, (SourceOutcome.zero("coingecko-price", "price"),), path=path)
    kpis = compute_quality_kpis(_DAY, coverage_path=path, archive_root=tmp_path / "archive")
    assert kpis.runs_observed == 3 and kpis.runs_attempted == 2
    assert kpis.source_liveness_rate == 0.5
    assert kpis.failed_sources == kpis.zero_item_sources == 1
    assert "성공률: 50.0%" in build_weekly_digest_text(_DAY, path=path)


def test_nullable_liveness_snapshot_keeps_other_history_fields(tmp_path) -> None:
    path = tmp_path / "quality.jsonl"
    snapshot = QualitySnapshot(
        source_liveness=None,
        figures_presence=0.0,
        fallback_ratio=1.0,
        published_segments=1,
        total_items=0,
        total_failed_sources=0,
        current_run_configured_sources=1,
        current_run_attempted_sources=0,
        current_run_skipped_sources=1,
        worst_severity="limited",
    )
    append_quality_snapshot(_DAY, snapshot=snapshot, history_path=path)
    row = json.loads(path.read_text())
    assert row["source_liveness"] is None
    assert row["current_run_attempted_sources"] == 0
    rows = compute_quality_history(history_path=path, today=_DAY)
    assert rows[-1].source_liveness is None and rows[-1].published_segments == 1
    assert rows[-1].fallback_ratio == 1.0
    append_quality_snapshot(
        _DAY, snapshot=replace(snapshot, worst_severity="normal"), history_path=path
    )
    assert json.loads(path.read_text())["worst_severity"] == "limited"


@pytest.mark.parametrize(
    "filename",
    [".github/workflows/daily-briefing.yml", "ops/private-runtime/production-briefing.yml"],
)
def test_lifecycle_override_workflow_wiring(filename) -> None:
    from pathlib import Path

    workflow = yaml.safe_load(Path(filename).read_text())
    envs = [
        step.get("env", {}) for job in workflow["jobs"].values() for step in job.get("steps", [])
    ]
    for name in ("INVESTO_SOURCE_ENABLE", "INVESTO_SOURCE_DISABLE"):
        assert any(env.get(name) == "${{ vars." + name + " }}" for env in envs)
