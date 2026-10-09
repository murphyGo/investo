"""Synthetic E1-to-E6 fixture using the real visual producer and finalizer."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from investo._internal.archive_layout import ArchiveLayout
from investo.models import NormalizedItem
from investo.models.facts import VerifiedFactBundle
from investo.models.market_anchor import MarketAnchor
from investo.models.segments import SEGMENT_LABELS, SegmentCoverage
from investo.models.watchlist import WatchlistImpact, WatchlistMatch
from investo.publisher.public_document import (
    PublicDocumentContext,
    PublicDocumentSupplement,
    _apply_pre_finalization_supplements,
    _assemble_phase_one_presentation_briefings,
    finalize_public_bundle,
)
from investo.visuals.assets import (
    VisualMarkdownBlock,
    insert_prebuilt_visual_blocks,
    prepare_segment_visual_assets,
)
from tests._helpers.briefings import build_briefing

DAY = date(2026, 10, 7)
SEGMENTS = ("domestic-equity", "us-equity", "crypto")


def build_reader_fixture(
    root: Path, *, unsupported_html: bool = False, repeated_labels: bool = False
):
    originals = {}
    for segment in SEGMENTS:
        briefing = build_briefing(target_date=DAY)
        intro = (
            f"# {DAY.isoformat()} {SEGMENT_LABELS[segment]} 시황\n\n"
            "> **오늘의 결론**: 확인된 수집 근거의 조건을 정리했습니다.\n"
            "> **핵심 동인**: 확인한 자료의 흐름을 함께 읽습니다.\n"
            "> **주의할 점**: 추가 근거가 필요한 부분을 점검합니다.\n\n"
        )
        originals[segment] = briefing.model_copy(
            update={"rendered_markdown": intro + briefing.rendered_markdown},
        )
    briefs = _assemble_phase_one_presentation_briefings(
        originals,
        target_date=DAY,
        active_segments=SEGMENTS,
    )
    briefs = {
        segment: briefing.model_copy(
            update={
                "rendered_markdown": briefing.rendered_markdown.replace(
                    "## ⑦ 면책조항",
                    "<details><summary>수집/품질 진단</summary>\n정상 수집\n</details>\n\n"
                    "## ⑦ 면책조항",
                )
            }
        )
        for segment, briefing in briefs.items()
    }
    coverage, sources, anchors, supplements, artifacts, prepared_briefs = {}, {}, {}, {}, {}, {}
    for segment in SEGMENTS:
        ticker = {"domestic-equity": "^KOSPI", "us-equity": "^GSPC", "crypto": "BTC-USD"}[segment]
        key = {"domestic-equity": "kospi_close", "us-equity": "spx_close", "crypto": "btc_usd"}[
            segment
        ]
        crypto = segment == "crypto"
        metadata = (
            {"symbol": "btc", "price_usd": "100.00", "pct_24h": "1.01"}
            if crypto
            else {"ticker": ticker, "close": "100.00", "prev_close": "99.00"}
        )
        metadata[f"core_fact:{key}"] = "100.00"
        price = NormalizedItem(
            source_name="coingecko-price" if crypto else "yfinance-price",
            category="price",
            title=f"고정 테스트 {ticker}",
            raw_metadata=metadata,
            published_at=datetime(2026, 10, 7, tzinfo=UTC),
        )
        news = NormalizedItem(
            source_name="synthetic-news",
            category="news",
            title=(
                "S&P 500은 10% 급락했습니다."
                if unsupported_html and segment == "us-equity"
                else f"{SEGMENT_LABELS[segment]} 고정 기사 제목 " * 8
            ),
            url="https://example.invalid/source",
            published_at=price.published_at,
        )
        items = tuple([price] * 12 + [news])
        sources[segment] = items
        coverage[segment] = SegmentCoverage(
            segment=segment,
            status="partial",
            item_count=13,
            source_count=2,
            categories=("price", "news"),
            missing_categories=("macro",),
        )
        anchors[segment] = (
            MarketAnchor(
                ticker=ticker,
                close=Decimal("100.00"),
                prev_close=Decimal("99.00"),
                pct=Decimal("1.01"),
                is_ath=False,
            ),
        )
        if unsupported_html and segment == "us-equity":
            anchors[segment] = ()
        impact = WatchlistImpact(
            configured=True, matches=(WatchlistMatch(term="고정", kind="keyword", item=news),)
        )
        from investo.visuals import assets

        original_price_builder = assets.build_price_snapshot_card

        def price_builder(*args, _builder=original_price_builder, **kwargs):
            card = _builder(*args, **kwargs)
            if card is not None and repeated_labels:
                return card.model_copy(
                    update={
                        "rows": tuple(
                            row.model_copy(update={"label": "조회시점(UTC)"}) for row in card.rows
                        )
                    }
                )
            return card

        with patch.object(assets, "build_price_snapshot_card", price_builder):
            prepared = prepare_segment_visual_assets(
                briefs[segment],
                archive_layout=ArchiveLayout(root),
                target_date=DAY,
                segment=segment,
                items=items,
                coverage=coverage[segment],
                watchlist_impact=impact,
                staging_root=root,
            )
        blocks = prepared.markdown_blocks
        supplements[segment] = tuple(
            PublicDocumentSupplement(
                supplement_id=f"{segment}.visual.{b.placement_key}",
                kind="visual",
                markdown=b.markdown,
                stable_order=n,
                artifact_ids=b.artifact_ids,
            )
            for n, b in enumerate(blocks)
        )
        artifacts[segment] = prepared.staged_artifacts

        def place(markdown, rendered_blocks, source_blocks=blocks):
            return insert_prebuilt_visual_blocks(
                markdown,
                blocks=tuple(
                    VisualMarkdownBlock(placement_key=source.placement_key, markdown=value)
                    for source, value in zip(source_blocks, rendered_blocks, strict=True)
                ),
            )

        prepared_briefs[segment] = _apply_pre_finalization_supplements(
            briefs[segment],
            supplements=supplements[segment],
            place=place,
        )
    context = PublicDocumentContext(
        target_date=DAY,
        expected_segments=SEGMENTS,
        input_absences={},
        anchors_by_segment=anchors,
        items_by_segment=sources,
        coverage_by_segment=coverage,
        source_outcomes=(),
        bundle_context=None,
        fact_bundle=VerifiedFactBundle(target_date=DAY),
        entity_observed_at_utc=datetime(2026, 10, 7, tzinfo=UTC),
        supplements_by_segment=supplements,
        staged_artifacts_by_segment=artifacts,
    )
    return finalize_public_bundle(prepared_briefs, context=context)
