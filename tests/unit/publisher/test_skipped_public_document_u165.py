"""The sealed producer, canonical gate and archive replay share skip accounting."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investo.briefing._reader_enhance.coverage_badge import _render_coverage_badge
from investo.briefing.segments import build_segment_coverage
from investo.models import NormalizedItem, SourceOutcome
from investo.models.facts import VerifiedFactBundle
from investo.models.segments import SegmentCoverage
from investo.publisher.briefing_replay import _check_markdown
from investo.publisher.evidence_accounting import count_rendered_evidence
from investo.publisher.public_document import PublicDocumentContext, finalize_public_bundle
from investo.publisher.quality_consistency import (
    build_canonical_snapshot,
    check_quality_consistency,
    parse_segment_status_block,
)
from tests._helpers.briefings import build_briefing

_DATE = date(2026, 10, 8)
_CLOCK = datetime(2026, 10, 9, tzinfo=UTC)


def test_finalizer_canonical_gate_and_replay_agree_about_disabled_provider() -> None:
    skip = SourceOutcome.skipped("cnbc-top-news", "news", reason="access_denied")
    healthy = SourceOutcome.ok("sec-newsroom-rss", "news", 1)
    outcomes = (skip, healthy)
    item = NormalizedItem(
        source_name="sec-newsroom-rss", category="news", title="Synthetic news", published_at=_CLOCK
    )
    coverage = build_segment_coverage("us-equity", (item,), source_outcomes=outcomes)
    assert "SOURCE_SKIPPED" in coverage.reason_codes
    markdown = (
        f"# {_DATE} 미국 증시 시황\n\n"
        "> **오늘의 결론**: 시장 흐름을 확인합니다.\n"
        "> **핵심 동인**: 금리 경로를 살핍니다.\n"
        "> **주의할 점**: 변동성을 확인합니다.\n\n"
        + _render_coverage_badge(coverage)
        + "\n"
        + "\n\n".join(
            f"## {heading}\n\n시장 흐름을 살핍니다."
            for heading in (
                "① 요약",
                "② 전일 핵심 이슈",
                "③ 섹터/수급 동향",
                "④ 지표·이벤트",
                "⑤ 주요 종목",
                "⑥ 오늘의 관전 포인트",
            )
        )
        + "\n[CNBC](https://www.cnbc.com/world/) 자료는 미확보입니다.\n"
        + "\n## ⑦ 면책조항\n면책 문구\n"
    )
    item = NormalizedItem(
        source_name="sec-newsroom-rss", category="news", title="Synthetic news", published_at=_CLOCK
    )
    context = PublicDocumentContext(
        target_date=_DATE,
        expected_segments=("us-equity",),
        input_absences={},
        anchors_by_segment={},
        items_by_segment={"us-equity": (item,)},
        coverage_by_segment={"us-equity": coverage},
        source_outcomes=outcomes,
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=_DATE),
        entity_observed_at_utc=_CLOCK,
    )
    briefing = build_briefing(target_date=_DATE).model_copy(update={"rendered_markdown": markdown})
    bundle = finalize_public_bundle({"us-equity": briefing}, context=context)
    assert len(bundle.documents) == 1
    document = bundle.documents[0]
    text = document.briefing.rendered_markdown
    assert "시도 1 / 비활성 1" in text
    assert (
        count_rendered_evidence(text, segment="us-equity", source_outcomes=outcomes).body_used_count
        == 0
    )
    assert count_rendered_evidence(text, segment="us-equity").body_used_count == 0
    assert parse_segment_status_block(text, "us-equity").known_body_evidence_count == 0
    snapshot = build_canonical_snapshot(_DATE, segment_texts={"us-equity": text}, history_row=None)
    assert not any(
        f.code == "quality.body_evidence_untracked"
        for f in check_quality_consistency(snapshot, quality_page_text=None)
    )
    assert not any(
        f.code == "body-evidence-untracked"
        for f in _check_markdown("us-equity", text, markdown_path=Path("synthetic.md"))
    )
    repeated = finalize_public_bundle({"us-equity": document.briefing}, context=context)
    assert repeated.documents[0].markdown_sha256 == document.markdown_sha256


@pytest.mark.parametrize(
    "diagnostic",
    [
        "```\n> **소스별 상태**: cnbc-top-news 비활성 (접근 제한)\n```",
        "> **소스별 상태**: cnbc-top-news 비활성 (unknown-private-token)",
        "> **소스별 상태**: unknown-source 비활성 (접근 제한)",
    ],
)
def test_invalid_or_fenced_skip_record_cannot_suppress_body_evidence(diagnostic) -> None:
    markdown = diagnostic + "\n## ① 요약\n[CNBC](https://www.cnbc.com/world/) 자료."
    assert count_rendered_evidence(markdown, segment="us-equity").body_used_count == 1


def test_public_diagnostic_keeps_healthy_shared_provider_identity() -> None:
    skip = SourceOutcome.skipped("coingecko-price", "price", reason="operator_disabled")
    healthy = SourceOutcome.ok("coingecko-global-market", "price", 1)
    coverage = SegmentCoverage(
        segment="crypto",
        status="limited",
        item_count=1,
        source_count=1,
        categories=("price",),
        missing_categories=(),
        source_outcomes=(skip, healthy),
        targeted_count=2,
        succeeded_count=1,
        skipped_count=1,
    )
    markdown = (
        _render_coverage_badge(coverage)
        + "\n## ① 요약\n[CoinGecko](https://www.coingecko.com/) 전체시장."
    )
    assert "coingecko-global-market 정상" in markdown
    assert count_rendered_evidence(markdown, segment="crypto").body_used_count == 1
