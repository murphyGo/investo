"""News-first ordering keeps numeric evidence and finalizer safety intact."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from investo._internal.data_limited_segment import build_data_limited_briefing
from investo.models.facts import VerifiedFactBundle
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import (
    CRYPTO,
    DOMESTIC_EQUITY,
    US_EQUITY,
    MarketSegment,
    SegmentCoverage,
)
from investo.publisher import public_document as public
from investo.publisher.reader_format.preamble import (
    MARKET_DATA_CLOSE,
    MARKET_DATA_OPEN,
    compose_canonical_preamble,
    preamble_issue_codes,
    unwrap_market_data,
)

DAY = date(2026, 10, 8)
ROOT = Path(__file__).parents[3]
SEGMENTS = (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)
TITLE = "# 2026-10-08 미국 증시 시황"
SUMMARY = """## 한눈에 보기

정책 발표를 확인했습니다.
새 서비스를 발표했습니다.
추가 일정을 확인합니다.

"""
TABLE = """| 종목 | 종가 | 변동 | 비고 |
|------|------|------|------|
| AAPL | 123.45 | +1.20% | 근거 |
"""
BODY = """## ① 요약

사건 설명을 유지합니다.

## ② 전일 핵심 이슈

| 실적 | 값 |
|---|---|
| 매출 | 123 |
"""


def context(segments: tuple[MarketSegment, ...] = SEGMENTS) -> public.PublicDocumentContext:
    symbols = {DOMESTIC_EQUITY: "^KS11", US_EQUITY: "^GSPC", CRYPTO: "BTC"}
    return public.PublicDocumentContext(
        target_date=DAY,
        expected_segments=segments,
        input_absences={},
        anchors_by_segment={
            segment: (
                MarketAnchor(
                    ticker=symbols[segment],
                    close=Decimal("1234.50"),
                    pct=Decimal("1.20"),
                    is_ath=False,
                ),
            )
            for segment in segments
        },
        items_by_segment={},
        coverage_by_segment={
            segment: SegmentCoverage(
                segment=segment,
                status="limited",
                item_count=0,
                source_count=0,
                categories=(),
                missing_categories=("news",),
            )
            for segment in segments
        },
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=DAY),
        entity_observed_at_utc=datetime(2026, 10, 9, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    "segment,day",
    [(DOMESTIC_EQUITY, "2026-10-08"), (US_EQUITY, "2026-10-08"), (CRYPTO, "2026-10-07")],
)
def test_real_archive_layout_moves_tables_and_preserves_body_assets_and_values(
    segment: str, day: str
) -> None:
    source = (ROOT / f"archive/{segment}/2026/10/{day}.md").read_text()
    title = source.splitlines()[0]
    out = compose_canonical_preamble(source, title=title)
    assert preamble_issue_codes(out, title=title) == ()
    assert compose_canonical_preamble(out, title=title) == out
    assert out.split("## ① 요약", 1)[1] == source.split("## ① 요약", 1)[1]
    assert out.count(title) == 1
    before, details = out.split(MARKET_DATA_OPEN, 1)
    assert not any(line.startswith("|") for line in before.splitlines())
    original_tables = [
        line for line in source.split("## ① 요약")[0].splitlines() if line.startswith("|")
    ]
    assert [
        line for line in details.split(MARKET_DATA_CLOSE)[0].splitlines() if line.startswith("|")
    ] == original_tables
    markers = r"<!-- investo:block .*?<!-- /investo:block [^>]+ -->"
    assert re.findall(markers, source, re.S) == re.findall(markers, out, re.S)
    assert (
        out.index("## 한눈에 보기")
        < out.index("<!-- investo:block visual:")
        < out.index(MARKET_DATA_OPEN)
    )


@pytest.mark.parametrize(
    "extra",
    [
        "```markdown\n# example\n| example | value |\n|---|---|\n| x | 1 |\n```\n",
        (
            "<!-- investo:block carryover:test.carryover -->\n"
            "| example | value |\n"
            "|---|---|\n"
            "| x | 1 |\n"
            "<!-- /investo:block carryover:test.carryover -->\n"
        ),
    ],
)
def test_protected_preamble_bytes_do_not_count_as_visible_numeric_table(extra: str) -> None:
    out = compose_canonical_preamble(
        TITLE + "\n\n" + TABLE + "\n" + extra + "\n" + SUMMARY + BODY, title=TITLE
    )
    assert extra.rstrip("\n") in out
    assert preamble_issue_codes(out, title=TITLE) == ()
    assert compose_canonical_preamble(out, title=TITLE) == out


@pytest.mark.parametrize("extra", ["# conflicting title\n\n", "## 한눈에 보기\n\n- duplicate\n\n"])
def test_unsupported_title_or_summary_is_preserved_and_rejected(extra: str) -> None:
    out = compose_canonical_preamble(TITLE + "\n\n" + SUMMARY + extra + BODY, title=TITLE)
    assert extra.rstrip("\n") in out
    assert preamble_issue_codes(out, title=TITLE)


def test_fourth_summary_claim_is_never_discarded() -> None:
    summary = SUMMARY.replace(
        "추가 일정을 확인합니다.\n",
        "추가 일정을 확인합니다.\n[위험한 근거](https://example.invalid/...)\n",
    )
    out = compose_canonical_preamble(TITLE + "\n\n" + summary + BODY, title=TITLE)
    assert "[위험한 근거](https://example.invalid/...)" in out
    assert "structure.tldr_shape" in preamble_issue_codes(out, title=TITLE)


@pytest.mark.parametrize(
    "segments", [(DOMESTIC_EQUITY,), (US_EQUITY,), (CRYPTO,), SEGMENTS, (US_EQUITY, CRYPTO)]
)
def test_real_finalizer_seals_and_refinalizes_same_bytes_and_summary(
    segments: tuple[MarketSegment, ...],
) -> None:
    ctx = context(segments)
    bundle = public.finalize_public_bundle(
        {seg: build_data_limited_briefing(DAY, seg) for seg in segments}, context=ctx
    )
    again = public.finalize_public_bundle(
        {doc.segment: doc.briefing for doc in bundle.documents}, context=ctx
    )
    for first, second in zip(bundle.documents, again.documents, strict=True):
        md = first.briefing.rendered_markdown
        assert first.briefing.rendered_markdown == second.briefing.rendered_markdown
        assert first.notification_summary == second.notification_summary
        assert md.count(MARKET_DATA_OPEN) == md.count(MARKET_DATA_CLOSE) == 1
        assert "1,234.50" in md.split(MARKET_DATA_OPEN)[1]
        assert md.index(MARKET_DATA_CLOSE) < md.index("## ① 요약")
        assert not any(line.startswith("|") for line in md.split(MARKET_DATA_OPEN)[0].splitlines())
        if DOMESTIC_EQUITY not in segments:
            assert "국내 증시(미발행)" in md


def test_numeric_region_replacement_and_link_scanner_preserve_shell() -> None:
    ctx = context((US_EQUITY,))
    doc = public.finalize_public_bundle(
        {US_EQUITY: build_data_limited_briefing(DAY, US_EQUITY)}, context=ctx
    ).documents[0]
    expectation = public.PublicRegionExpectation(
        target_date=DAY,
        segment=US_EQUITY,
        segmented_mode=True,
        supplement_ids=(),
        shared_macro_required=False,
        crypto_indicators_required=False,
        channel_anchors_required=True,
        daily_thesis_required=False,
        anchor_table_required=True,
        canonical_preamble_required=True,
    )
    layout = public.PublicDocumentLayout.reindex(
        doc.briefing.rendered_markdown, expectation=expectation
    )
    truncated = layout.replace_region_body(
        "summary:tldr", "\n- 기관의 본문 참고.\n- 둘째입니다.\n- 셋째입니다.\n\n"
    )
    assert any(
        finding.region_id == "summary:tldr" and finding.issue.code == "summary.truncated_mid_token"
        for finding in public._find_owned_surface_quality_issues(truncated)
    )
    broken = layout.replace_region_body(
        "anchor:channel", "\n[자료](https://example.invalid/...)\n\n"
    )
    findings = public._find_owned_surface_quality_issues(broken)
    assert any(
        f.region_id == "anchor:channel" and f.issue.code == "markdown.href_ellipsis"
        for f in findings
    )
    replaced = broken.replace_region_body(
        "anchor:channel", "\n확인 가능한 기준선이 제한적입니다.\n\n"
    )
    assert (
        replaced.markdown.count(MARKET_DATA_OPEN) == replaced.markdown.count(MARKET_DATA_CLOSE) == 1
    )
    for name in ("open", "close"):
        shell = next(
            region for region in replaced.regions if region.region_id == f"shell:market_data:{name}"
        )
        assert shell.content_start == shell.content_end
    assert preamble_issue_codes(replaced.markdown, title=TITLE) == ()


def test_hidden_compliance_claim_is_still_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    compose = public.compose_canonical_preamble

    def with_unsafe_claim(markdown: str, *, title: str) -> str:
        out = compose(markdown, title=title)
        return out.replace(MARKET_DATA_CLOSE, "확실한 수익을 보장합니다.\n\n" + MARKET_DATA_CLOSE)

    monkeypatch.setattr(public, "compose_canonical_preamble", with_unsafe_claim)
    with pytest.raises(public.PublicDocumentFinalizationError) as error:
        public.finalize_public_bundle(
            {US_EQUITY: build_data_limited_briefing(DAY, US_EQUITY)}, context=context((US_EQUITY,))
        )
    assert "compliance.language" in error.value.issue_codes


def test_unwrap_is_exact_and_keeps_every_interior_byte() -> None:
    source = TITLE + "\n\n" + SUMMARY + TABLE + "\n" + BODY
    out = compose_canonical_preamble(source, title=TITLE)
    assert TABLE.rstrip("\n") in unwrap_market_data(out)
    malformed = out.replace(MARKET_DATA_CLOSE, "</details>")
    assert unwrap_market_data(malformed) == malformed
