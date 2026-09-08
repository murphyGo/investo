"""Unit tests for u57 Step 1.5 — :func:`compute_bundle_context`."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, note, seed, settings
from hypothesis import strategies as st

from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Category, NormalizedItem
from investo.models.bundle_context import (
    CROSS_MARKET_CORE_ALLOWED,
    BundleContext,
    SharedMacroKey,
)
from investo.models.segments import MarketSegment
from investo.orchestrator.bundle_context import (
    compute_bundle_context,
    redecide_daily_thesis_for_successful_segments,
)

NOW = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
IMMUNEFI_TITLE = "Immunefi to absorb Code4rena bug bounty customers after shutdown decision"


def make_item(
    *,
    source: str,
    title: str,
    published_at: datetime,
    category: Category = "news",
    url: str = "https://example.com/x",
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category=category,
        title=title,
        url=url,
        published_at=published_at,
        raw_metadata={},
    )


class TestEmpty:
    def test_empty_input_three_pending_segments(self) -> None:
        ctx = compute_bundle_context({}, now_kst=NOW)
        assert isinstance(ctx, BundleContext)
        assert set(ctx.segments) == {DOMESTIC_EQUITY, US_EQUITY, CRYPTO}
        for summ in ctx.segments.values():
            assert summ.close_state == "pending"
            assert summ.headline_native_fact is None
        assert ctx.shared_macro_block is None

    def test_target_date_from_now_kst(self) -> None:
        ctx = compute_bundle_context({}, now_kst=NOW)
        assert ctx.target_kst_date == NOW.date()

    def test_bundle_id_default(self) -> None:
        ctx = compute_bundle_context({}, now_kst=NOW)
        assert "2026-05-11" in ctx.bundle_id
        assert ctx.daily_thesis_decision.mode == "omit"
        assert ctx.daily_thesis_decision.reason == "insufficient_successful_segments"


class TestPerSegmentCloseState:
    def test_us_close_detected(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="yfinance-price",
                    title="S&P 500 0.5% 상승 마감",
                    published_at=NOW,
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.segments[US_EQUITY].close_state == "close"
        assert ctx.segments[DOMESTIC_EQUITY].close_state == "pending"
        assert ctx.segments[CRYPTO].close_state == "pending"

    def test_latest_item_wins(self) -> None:
        # Earlier 'open' item; later 'close' item — close should win
        # because it has the later published_at.
        early = make_item(
            source="x",
            title="코스피 상승 출발",
            published_at=datetime(2026, 5, 11, 0, 0, tzinfo=UTC),
        )
        late = make_item(
            source="x",
            title="코스피 마감",
            published_at=datetime(2026, 5, 11, 6, 0, tzinfo=UTC),
        )
        ctx = compute_bundle_context({DOMESTIC_EQUITY: [early, late]}, now_kst=NOW)
        assert ctx.segments[DOMESTIC_EQUITY].close_state == "close"

    def test_headline_truncated_at_120(self) -> None:
        long_title = "코스피 마감" + "x" * 200
        routed = {
            DOMESTIC_EQUITY: [
                make_item(source="x", title=long_title, published_at=NOW),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        headline = ctx.segments[DOMESTIC_EQUITY].headline_native_fact
        assert headline is not None
        assert len(headline) <= 120

    def test_no_time_state_match_pending(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(source="x", title="애플 신제품 발표", published_at=NOW),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.segments[US_EQUITY].close_state == "pending"


class TestSharedMacroDetection:
    def test_ust_in_two_segments_shared(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="fred-macro",
                    title="미 국채 10년물 수익률 4.42%",
                    published_at=NOW,
                    category="macro",
                ),
            ],
            CRYPTO: [
                make_item(
                    source="news",
                    title="UST 수익률 상승에 비트코인 약세",
                    published_at=NOW,
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is not None
        assert "미 국채 수익률" in ctx.shared_macro_block

    def test_customers_does_not_match_ust_yield(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="theblock-crypto",
                    title=IMMUNEFI_TITLE,
                    published_at=NOW,
                ),
            ],
            CRYPTO: [
                make_item(
                    source="theblock-crypto",
                    title="Trust custody platform expands services",
                    published_at=NOW,
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is None

    @pytest.mark.parametrize(
        "title",
        [
            "customers plan migration",
            "trust company adds crypto custody",
            "dust settles after protocol upgrade",
            "UST stablecoin collapse",
            "UST depeg",
            "UST custody product",
            "한국 국채 10년물 금리 3.5%",
        ],
    )
    def test_ust_false_positive_titles_rejected(self, title: str) -> None:
        routed = {
            US_EQUITY: [make_item(source="news-a", title=title, published_at=NOW)],
            CRYPTO: [make_item(source="news-b", title=title, published_at=NOW)],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is None

    @pytest.mark.parametrize(
        "title",
        [
            "UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp",
            "DGS10 4.46 (+0.0400 from prior)",
            "10Y Treasury yield rises to 4.46%",
            "미 국채 10년물 수익률 4.42%",
        ],
    )
    def test_real_ust_titles_match_with_canonical_source(self, title: str) -> None:
        routed = {
            US_EQUITY: [
                make_item(source="fred-macro", title=title, published_at=NOW, category="macro"),
            ],
            CRYPTO: [
                make_item(
                    source="treasury-rates",
                    title="UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp",
                    published_at=NOW,
                    category="macro",
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is not None
        assert "미 국채 수익률" in ctx.shared_macro_block

    def test_non_canonical_ust_titles_suppressed(self, caplog: pytest.LogCaptureFixture) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="news-a",
                    title="10Y Treasury yield rises to 4.46%",
                    published_at=NOW,
                ),
            ],
            CRYPTO: [
                make_item(
                    source="news-b",
                    title="UST curve steepens as 10Y rate rises",
                    published_at=NOW,
                ),
            ],
        }
        caplog.set_level(logging.INFO, logger="investo.orchestrator.bundle_context")
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is None
        assert any(
            "shared_macro.key_suppressed" in record.getMessage() for record in caplog.records
        )

    def test_canonical_ust_wins_over_earlier_generic_news(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="news-a",
                    title="10Y Treasury yield rises to 4.46%",
                    published_at=NOW,
                ),
                make_item(
                    source="fred-macro",
                    title="DGS10 4.46 (+0.0400 from prior)",
                    published_at=NOW,
                    category="macro",
                ),
            ],
            CRYPTO: [
                make_item(
                    source="theblock-crypto",
                    title=IMMUNEFI_TITLE,
                    published_at=NOW,
                ),
                make_item(
                    source="treasury-rates",
                    title="UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp",
                    published_at=NOW,
                    category="macro",
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is not None
        assert "UST curve 2026-05-13" in ctx.shared_macro_block
        assert "Immunefi" not in ctx.shared_macro_block
        assert "10Y Treasury yield rises" not in ctx.shared_macro_block

    def test_fred_macro_alone_does_not_create_shared_ust(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="fred-macro",
                    title="DGS10 4.46 (+0.0400 from prior)",
                    published_at=NOW,
                    category="macro",
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is None

    def test_oil_in_only_one_segment_not_shared(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(source="x", title="WTI 유가 상승", published_at=NOW),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is None

    def test_multiple_macros_alphabetical_order(self) -> None:
        # fomc + oil + ust_yield all in two segments — output should
        # be alphabetically ordered by macro key (deterministic).
        routed = {
            US_EQUITY: [
                make_item(source="x", title="FOMC 회의 결과", published_at=NOW),
                make_item(source="x", title="WTI 급등", published_at=NOW),
                make_item(
                    source="fred-macro",
                    title="미 국채 10년물 수익률 4.42%",
                    published_at=NOW,
                    category="macro",
                ),
            ],
            CRYPTO: [
                make_item(source="x", title="FOMC 후 코인 변동", published_at=NOW),
                make_item(source="x", title="Brent 영향", published_at=NOW),
                make_item(source="x", title="UST 수익률 영향", published_at=NOW),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        block = ctx.shared_macro_block
        assert block is not None
        # Order: fomc < oil < ust_yield
        idx_fomc = block.find("FOMC 일정")
        idx_oil = block.find("국제 유가")
        idx_ust = block.find("미 국채 수익률")
        assert idx_fomc < idx_oil < idx_ust

    def test_oil_and_fomc_boundary_false_positives_rejected(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(source="x", title="Brentwood office lease signed", published_at=NOW),
                make_item(source="x", title="Platform FOMCish token launches", published_at=NOW),
            ],
            CRYPTO: [
                make_item(source="x", title="Brentwood expansion continues", published_at=NOW),
                make_item(source="x", title="No FOMCish details today", published_at=NOW),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is None

    def test_real_fomc_adapter_titles_still_match(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="fomc-calendar",
                    title="FOMC press release",
                    published_at=NOW,
                    category="calendar",
                ),
            ],
            CRYPTO: [
                make_item(
                    source="fomc-rss",
                    title="Federal Reserve issues FOMC statement",
                    published_at=NOW,
                    category="calendar",
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.shared_macro_block is not None
        assert "FOMC 일정" in ctx.shared_macro_block

    def test_candidate_logs_are_r13_safe(self, caplog: pytest.LogCaptureFixture) -> None:
        routed = {
            US_EQUITY: [
                make_item(
                    source="news-a",
                    title=(
                        "UST custody product TELEGRAM_BOT_TOKEN=123456:abcdefghijklmnopqrstuvwxyz"
                    ),
                    published_at=NOW,
                    url="https://example.com/safe",
                ),
            ],
            CRYPTO: [
                make_item(
                    source="treasury-rates",
                    title="UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp",
                    published_at=NOW,
                    category="macro",
                ),
            ],
        }
        caplog.set_level(logging.INFO, logger="investo.orchestrator.bundle_context")
        compute_bundle_context(routed, now_kst=NOW)
        for record in caplog.records:
            assert "raw_metadata" not in record.__dict__
            assert "abcdefghijklmnopqrstuvwxyz" not in str(record.__dict__.get("title_preview", ""))


class TestAllowListPin:
    def test_allowlist_carried(self) -> None:
        ctx = compute_bundle_context({}, now_kst=NOW)
        assert ctx.cross_market_core_allowed == CROSS_MARKET_CORE_ALLOWED


class TestWithSelfPending:
    def test_with_self_pending_only_target_segment(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(source="x", title="S&P 500 마감", published_at=NOW),
            ],
            DOMESTIC_EQUITY: [
                make_item(source="x", title="코스피 마감", published_at=NOW),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        # Force US to pending — domestic should remain close.
        rewritten = ctx.with_self_pending(US_EQUITY)
        assert rewritten.segments[US_EQUITY].close_state == "pending"
        assert rewritten.segments[DOMESTIC_EQUITY].close_state == "close"


class TestIdempotence:
    def test_same_input_same_output(self) -> None:
        routed = {
            US_EQUITY: [
                make_item(source="x", title="S&P 500 마감", published_at=NOW),
            ],
        }
        a = compute_bundle_context(routed, now_kst=NOW)
        b = compute_bundle_context(routed, now_kst=NOW)
        assert a == b


class TestDailyThesis:
    def test_strong_decision_from_two_segment_fed_signal(self) -> None:
        routed = {
            DOMESTIC_EQUITY: [
                make_item(
                    source="treasury-rates",
                    title="UST 10Y yield closes higher",
                    published_at=NOW,
                    category="macro",
                ),
            ],
            US_EQUITY: [
                make_item(
                    source="fred-macro",
                    title="DGS10 Treasury yield update",
                    published_at=NOW,
                    category="macro",
                ),
            ],
        }

        ctx = compute_bundle_context(routed, now_kst=NOW)

        assert ctx.daily_thesis_decision.mode == "strong"
        assert ctx.daily_thesis_decision.reason == "shared_core_signal"
        assert ctx.daily_thesis_decision.macro_keys == ("ust_yield",)
        assert ctx.daily_thesis_decision.supporting_segments == (
            DOMESTIC_EQUITY,
            US_EQUITY,
        )
        assert ctx.daily_thesis_decision.line is not None
        assert "금리와 달러 변수" in ctx.daily_thesis_decision.line
        assert not any(ch.isdigit() for ch in ctx.daily_thesis_decision.line)
        assert (
            ctx.daily_thesis_decision.per_segment_lines[DOMESTIC_EQUITY]
            != (ctx.daily_thesis_decision.per_segment_lines[US_EQUITY])
        )
        assert "KOSPI" in ctx.daily_thesis_decision.per_segment_lines[DOMESTIC_EQUITY]
        assert "Nasdaq" in ctx.daily_thesis_decision.per_segment_lines[US_EQUITY]

    def test_data_limited_decision_when_two_segments_have_no_shared_signal(self) -> None:
        routed = {
            DOMESTIC_EQUITY: [
                make_item(source="krx", title="코스피 상승 마감", published_at=NOW),
            ],
            US_EQUITY: [
                make_item(source="nasdaq", title="AAPL earnings preview", published_at=NOW),
            ],
        }

        ctx = compute_bundle_context(routed, now_kst=NOW)

        assert ctx.daily_thesis_decision.mode == "data_limited"
        assert ctx.daily_thesis_decision.reason == "no_shared_core_signal"
        assert "공통 핵심 신호가 제한적" in (ctx.daily_thesis_decision.line or "")
        assert set(ctx.daily_thesis_decision.per_segment_lines) == {
            DOMESTIC_EQUITY,
            US_EQUITY,
        }
        assert all(
            "이 세그먼트의 공통 신호는 제한적" in line
            for line in ctx.daily_thesis_decision.per_segment_lines.values()
        )

    def test_strong_decision_renders_three_distinct_segment_consequences(self) -> None:
        routed = {
            DOMESTIC_EQUITY: [
                make_item(
                    source="news",
                    title="UST 수익률 상승에 코스피 약세",
                    published_at=NOW,
                ),
            ],
            US_EQUITY: [
                make_item(
                    source="fred-macro",
                    title="DGS10 Treasury yield update",
                    published_at=NOW,
                    category="macro",
                ),
            ],
            CRYPTO: [
                make_item(
                    source="treasury-rates",
                    title="UST 10Y yield pressure weighs on BTC",
                    published_at=NOW,
                    category="macro",
                ),
            ],
        }

        ctx = compute_bundle_context(routed, now_kst=NOW)
        lines = ctx.daily_thesis_decision.per_segment_lines

        assert ctx.daily_thesis_decision.mode == "strong"
        assert set(lines) == {DOMESTIC_EQUITY, US_EQUITY, CRYPTO}
        assert len(set(lines.values())) == 3
        assert "KOSPI" in lines[DOMESTIC_EQUITY]
        assert "Nasdaq" in lines[US_EQUITY]
        assert "BTC" in lines[CRYPTO]
        assert not any(any(ch.isdigit() for ch in line) for line in lines.values())

    def test_daily_thesis_is_redecided_from_generated_segments_only(self) -> None:
        routed = {
            DOMESTIC_EQUITY: [
                make_item(
                    source="news",
                    title="UST 수익률 상승에 코스피 약세",
                    published_at=NOW,
                ),
            ],
            US_EQUITY: [
                make_item(
                    source="fred-macro",
                    title="DGS10 Treasury yield update",
                    published_at=NOW,
                    category="macro",
                ),
            ],
            CRYPTO: [
                make_item(
                    source="news",
                    title="UST 수익률 상승에 비트코인 약세",
                    published_at=NOW,
                ),
            ],
        }
        ctx = compute_bundle_context(routed, now_kst=NOW)
        assert ctx.daily_thesis_decision.mode == "strong"

        filtered = redecide_daily_thesis_for_successful_segments(ctx, (US_EQUITY,))

        assert filtered.daily_thesis_decision.mode == "omit"
        assert filtered.daily_thesis_decision.reason == "insufficient_successful_segments"
        assert filtered.daily_thesis_decision.supporting_segments == ()
        assert {signal.segment for signal in filtered.daily_thesis_signals} == {US_EQUITY}


@pytest.mark.parametrize(
    "explicit_bundle_id",
    ["custom-id-2026-05-11", "abc123"],
)
def test_bundle_id_override(explicit_bundle_id: str) -> None:
    ctx = compute_bundle_context({}, now_kst=NOW, bundle_id=explicit_bundle_id)
    assert ctx.bundle_id == explicit_bundle_id


# u151: Step 1 synthetic characterization converted to Step 2 exclusion regressions.
# Historical title: d553035:archive/us-equity/2026/09/2026-09-04.md:27.
# Metadata and timing below are synthetic, not captured upstream responses.
U151_NOW = datetime(2026, 9, 5, 9, tzinfo=ZoneInfo("Asia/Seoul"))
U151_CFTC_SOURCE = "cftc-cot-positioning"
U151MetadataKind = Literal["full", "missing", "scalar_defect"]
U151_METADATA_KINDS: tuple[U151MetadataKind, ...] = ("full", "missing", "scalar_defect")


def _positioning_u151(
    metadata_kind: U151MetadataKind = "full",
    net_contracts: int = 94281,
) -> NormalizedItem:
    metadata: dict[str, str | int | float] = {
        "contract_group": "energy",
        "contract_label": "WTI crude oil",
        "trader_category": "managed_money",
        "net_contracts": str(net_contracts),
        "as_of_date": "2026-09-01",
        "release_date": "2026-09-04",
        "data_frequency": "weekly",
    }
    if metadata_kind == "missing":
        metadata = {}
    elif metadata_kind == "scalar_defect":
        # Model-valid defects, not nested/bool values rejected by NormalizedItem.
        metadata = {"contract_group": 7, "net_contracts": "", "as_of_date": 0}
    return NormalizedItem(
        source_name=U151_CFTC_SOURCE,
        category="macro",
        title=f"CFTC WTI crude oil managed_money net {net_contracts:+d} contracts",
        published_at=datetime(2026, 9, 4, 20, tzinfo=UTC),
        raw_metadata=metadata,
    )


def _oil_news_u151(source: str) -> NormalizedItem:
    return make_item(
        source=source,
        title="WTI oil price rises on supply news",
        published_at=U151_NOW,
    )


class TestPositioningExclusionU151:
    """CFTC stays routed, but cannot supply shared price/policy evidence."""

    @pytest.mark.parametrize("metadata_kind", U151_METADATA_KINDS)
    def test_cftc_only_cannot_promote_contracts_to_shared_oil(
        self, metadata_kind: U151MetadataKind
    ) -> None:
        item = _positioning_u151(metadata_kind)
        routed = {segment: (item,) for segment in (DOMESTIC_EQUITY, US_EQUITY, CRYPTO)}
        before = item.model_copy(deep=True)

        ctx = compute_bundle_context(routed, now_kst=U151_NOW)

        assert ctx.shared_macro_block is None
        assert ctx.detected_macro_keys == frozenset()
        assert ctx.daily_thesis_signals == ()
        assert ctx.daily_thesis_decision.mode == "data_limited"
        assert ctx.daily_thesis_decision.reason == "no_shared_core_signal"
        assert ctx.daily_thesis_decision.macro_keys == ()
        assert ctx.daily_thesis_decision.supporting_segments == (
            DOMESTIC_EQUITY,
            US_EQUITY,
            CRYPTO,
        )
        assert item == before
        assert all(items == (before,) for items in routed.values())

    @pytest.mark.parametrize("metadata_kind", U151_METADATA_KINDS)
    @pytest.mark.parametrize("position_count", [1, 3])
    def test_one_news_segment_plus_cftc_cannot_cross_shared_threshold(
        self, metadata_kind: U151MetadataKind, position_count: int
    ) -> None:
        news = _oil_news_u151("synthetic-oil-news")
        positions = tuple(_positioning_u151(metadata_kind) for _ in range(position_count))
        without_position = compute_bundle_context({US_EQUITY: (news,)}, now_kst=U151_NOW)
        assert without_position.shared_macro_block is None
        assert without_position.daily_thesis_signals == ()

        ctx = compute_bundle_context({US_EQUITY: (news,), CRYPTO: positions}, now_kst=U151_NOW)

        assert ctx.shared_macro_block is None
        assert ctx.detected_macro_keys == frozenset()
        assert ctx.daily_thesis_signals == ()
        assert ctx.daily_thesis_decision.mode == "data_limited"
        assert ctx.daily_thesis_decision.supporting_segments == (US_EQUITY, CRYPTO)

    def test_cftc_cannot_supply_thesis_when_two_news_segments_already_qualify(self) -> None:
        routed = {
            DOMESTIC_EQUITY: (_oil_news_u151("synthetic-oil-news-kr"),),
            US_EQUITY: (_oil_news_u151("synthetic-oil-news-us"),),
            CRYPTO: (_positioning_u151(),),
        }

        ctx = compute_bundle_context(routed, now_kst=U151_NOW)

        assert ctx.detected_macro_keys == frozenset({"oil"})
        assert ctx.shared_macro_block == "- **국제 유가** — WTI oil price rises on supply news"
        assert tuple(
            (signal.segment, signal.key, signal.source_ids) for signal in ctx.daily_thesis_signals
        ) == (
            (DOMESTIC_EQUITY, "oil", ("synthetic-oil-news-kr",)),
            (US_EQUITY, "oil", ("synthetic-oil-news-us",)),
        )
        assert ctx.daily_thesis_decision.supporting_segments == (
            DOMESTIC_EQUITY,
            US_EQUITY,
        )

    def test_eligible_oil_in_two_segments_remains_a_positive_control(self) -> None:
        ctx = compute_bundle_context(
            {
                US_EQUITY: (_oil_news_u151("synthetic-oil-news-us"),),
                CRYPTO: (_oil_news_u151("synthetic-oil-news-crypto"),),
            },
            now_kst=U151_NOW,
        )

        assert ctx.shared_macro_block == "- **국제 유가** — WTI oil price rises on supply news"
        assert ctx.detected_macro_keys == frozenset({"oil"})
        assert {signal.segment for signal in ctx.daily_thesis_signals} == {US_EQUITY, CRYPTO}
        assert len(ctx.daily_thesis_signals) == 2
        assert all(
            signal.key == "oil" and signal.tier == "core" for signal in ctx.daily_thesis_signals
        )
        assert ctx.daily_thesis_decision.mode == "strong"
        assert ctx.daily_thesis_decision.macro_keys == ("oil",)

    @pytest.mark.parametrize("position_count", [1, 3])
    def test_many_items_in_one_segment_do_not_replace_distinct_segments(
        self, position_count: int
    ) -> None:
        items = (
            _oil_news_u151("synthetic-oil-news"),
            *(_positioning_u151() for _ in range(position_count)),
        )

        ctx = compute_bundle_context({US_EQUITY: items}, now_kst=U151_NOW)

        assert ctx.shared_macro_block is None
        assert ctx.detected_macro_keys == frozenset()
        assert ctx.daily_thesis_signals == ()
        assert ctx.daily_thesis_decision.mode == "omit"
        assert ctx.daily_thesis_decision.reason == "insufficient_successful_segments"


@st.composite
def _positioning_routes_u151(
    draw: st.DrawFn,
) -> dict[MarketSegment, tuple[NormalizedItem, ...]]:
    """Structured bounded routes; only oil matches, so no overlap-policy oracle."""
    net = draw(st.integers(min_value=-1_000_000, max_value=1_000_000))
    metadata_kind = draw(st.sampled_from(U151_METADATA_KINDS))
    positions = tuple(
        _positioning_u151(metadata_kind, net)
        for _ in range(draw(st.integers(min_value=1, max_value=3)))
    )
    return {
        US_EQUITY: (_oil_news_u151("synthetic-oil-news-us"), *positions),
        CRYPTO: (_oil_news_u151("synthetic-oil-news-crypto"),),
    }


@seed(15120260908)
@settings(max_examples=40)
@given(routed=_positioning_routes_u151())
def test_u151_property_repeated_context_preserves_original_routed_items(
    routed: dict[MarketSegment, tuple[NormalizedItem, ...]],
) -> None:
    note("u151 seed=15120260908")
    before = {
        segment: tuple(item.model_copy(deep=True) for item in items)
        for segment, items in routed.items()
    }

    first = compute_bundle_context(routed, now_kst=U151_NOW)
    second = compute_bundle_context(routed, now_kst=U151_NOW)

    assert first == second
    assert routed == before
    assert first.daily_thesis_decision.mode == "strong"  # Two genuine oil-news segments.
    assert first.detected_macro_keys == frozenset({"oil"})
    assert first.shared_macro_block == "- **국제 유가** — WTI oil price rises on supply news"
    assert all(U151_CFTC_SOURCE not in signal.source_ids for signal in first.daily_thesis_signals)


@seed(15120260908)
@settings(max_examples=40)
@given(routed=_positioning_routes_u151(), data=st.data())
def test_u151_property_equivalent_candidate_permutations_preserve_context(
    routed: dict[MarketSegment, tuple[NormalizedItem, ...]], data: st.DataObject
) -> None:
    note("u151 seed=15120260908")
    segment_order = data.draw(st.permutations(tuple(routed)), label="segment_order")
    permuted = {
        segment: tuple(data.draw(st.permutations(routed[segment]), label=segment))
        for segment in segment_order
    }

    assert compute_bundle_context(permuted, now_kst=U151_NOW) == compute_bundle_context(
        routed, now_kst=U151_NOW
    )


U151_KEYS: tuple[SharedMacroKey, ...] = ("fomc", "oil", "ust_yield")
U151_OVERLAP_TITLE = "FOMC meeting WTI oil and UST 10Y yield"
U151_KEY_LABELS = {"fomc": "FOMC 일정", "oil": "국제 유가", "ust_yield": "미 국채 수익률"}
U151_KEY_SUBSETS: tuple[frozenset[SharedMacroKey], ...] = tuple(
    frozenset(key for index, key in enumerate(U151_KEYS) if mask & (1 << index))
    for mask in range(8)
)


def _selected_subset_routes_u151(
    keys: frozenset[SharedMacroKey],
) -> dict[MarketSegment, tuple[NormalizedItem, ...]]:
    support: dict[SharedMacroKey, NormalizedItem] = {
        "fomc": make_item(source="fomc-calendar", title="FOMC meeting", published_at=U151_NOW),
        "oil": _oil_news_u151("synthetic-oil-support"),
        "ust_yield": make_item(
            source="treasury-rates",
            title="UST 10Y yield",
            published_at=U151_NOW,
            category="macro",
        ),
    }
    return {
        US_EQUITY: (
            make_item(
                source="synthetic-overlap",
                title=U151_OVERLAP_TITLE,
                published_at=U151_NOW,
            ),
        ),
        CRYPTO: tuple(support[key] for key in sorted(keys)),
        DOMESTIC_EQUITY: (
            make_item(
                source=U151_CFTC_SOURCE,
                title=U151_OVERLAP_TITLE,
                category="macro",
                published_at=U151_NOW,
            ),
        ),
    }


def _assert_selected_subset_u151(ctx: BundleContext, keys: frozenset[SharedMacroKey]) -> None:
    assert ctx.detected_macro_keys == keys
    labels = [line.split("**")[1] for line in (ctx.shared_macro_block or "").splitlines()]
    assert labels == [U151_KEY_LABELS[key] for key in sorted(keys)]
    assert tuple(
        signal.key for signal in ctx.daily_thesis_signals if signal.segment == US_EQUITY
    ) == ((min(keys),) if keys else ())
    assert len(ctx.daily_thesis_signals) == (len(keys) + 1 if keys else 0)
    assert all(
        signal.key in keys and signal.tier == "core" and U151_CFTC_SOURCE not in signal.source_ids
        for signal in ctx.daily_thesis_signals
    )
    assert ctx.daily_thesis_decision.macro_keys == ((min(keys),) if keys else ())


@pytest.mark.parametrize(
    "keys", U151_KEY_SUBSETS, ids=lambda keys: ",".join(sorted(keys)) or "empty"
)
def test_u151_overlap_emits_first_selected_key_but_retains_all_shared_keys(
    keys: frozenset[SharedMacroKey],
) -> None:
    _assert_selected_subset_u151(
        compute_bundle_context(_selected_subset_routes_u151(keys), now_kst=U151_NOW), keys
    )


@pytest.mark.parametrize(
    "group",
    [
        "energy",
        "rates",
        "crypto",
        "equity_index",
        "volatility",
        "fx",
        "metals",
        "unrecognized",
        "",
        7,
        None,
    ],
)
@pytest.mark.parametrize("category", ["macro", "news", "calendar", "price", "earnings"])
def test_u151_all_cftc_groups_cannot_complete_any_threshold_or_supply_core(
    group: str | int | None,
    category: Category,
) -> None:
    # Matching all keys and a canonical UST source ensure the prerequisite
    # cannot hide a CFTC leak. Metadata is synthetic and model-valid.
    position = NormalizedItem(
        source_name=U151_CFTC_SOURCE,
        category=category,
        title=U151_OVERLAP_TITLE,
        published_at=U151_NOW,
        raw_metadata={} if group is None else {"contract_group": group},
    )
    canonical = make_item(
        source="treasury-rates",
        category="macro",
        title=U151_OVERLAP_TITLE,
        published_at=U151_NOW,
    )
    routed = {US_EQUITY: (canonical,), CRYPTO: (position,)}
    ctx = compute_bundle_context(routed, now_kst=U151_NOW)
    assert ctx.detected_macro_keys == frozenset()
    assert ctx.shared_macro_block is None
    assert ctx.daily_thesis_signals == ()
    # When all keys already qualify independently, CFTC still supplies no core
    # or representative even though its macro category outranks real news.
    two_eligible = {**routed, DOMESTIC_EQUITY: (canonical,)}
    selected = compute_bundle_context(two_eligible, now_kst=U151_NOW)
    assert selected.detected_macro_keys == frozenset(U151_KEYS)
    assert len(selected.daily_thesis_signals) == 2
    assert all(signal.source_ids == ("treasury-rates",) for signal in selected.daily_thesis_signals)
    assert routed[CRYPTO] == (position,)


def test_u151_noncanonical_ust_is_not_transported_as_a_selected_key() -> None:
    item = make_item(source="synthetic-news", title=U151_OVERLAP_TITLE, published_at=U151_NOW)
    ctx = compute_bundle_context({US_EQUITY: (item,), CRYPTO: (item,)}, now_kst=U151_NOW)
    assert ctx.detected_macro_keys == frozenset({"fomc", "oil"})
    assert ctx.shared_macro_block is not None
    assert "미 국채 수익률" not in ctx.shared_macro_block
    assert [signal.key for signal in ctx.daily_thesis_signals] == ["fomc", "fomc"]


def test_u151_producer_exclusion_is_exact_not_prefix_or_title_based() -> None:
    item = make_item(
        source="cftc-cot-positioning-news",
        title="CFTC WTI oil report",
        published_at=U151_NOW,
    )
    ctx = compute_bundle_context({US_EQUITY: (item,), CRYPTO: (item,)}, now_kst=U151_NOW)
    assert ctx.detected_macro_keys == frozenset({"oil"})
    assert len(ctx.daily_thesis_signals) == 2


def test_u151_cftc_still_participates_in_original_close_state_input() -> None:
    position = make_item(source=U151_CFTC_SOURCE, title="WTI 마감", published_at=U151_NOW)
    ctx = compute_bundle_context({US_EQUITY: (position,)}, now_kst=U151_NOW)
    assert ctx.segments[US_EQUITY].close_state == "close"
    assert ctx.segments[US_EQUITY].headline_native_fact == position.title
    assert ctx.detected_macro_keys == frozenset()


def test_u151_positioning_rejection_uses_only_existing_r13_safe_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_marker = "abcdefghijklmnopqrstuvwxyz"  # Synthetic test token, not a credential.
    position = NormalizedItem(
        source_name=U151_CFTC_SOURCE,
        category="macro",
        title=f"{U151_OVERLAP_TITLE} TELEGRAM_BOT_TOKEN=123456:{secret_marker} " + "x" * 200,
        published_at=U151_NOW,
        url="https://example.com/private-positioning-payload",
        raw_metadata={"private_payload": "u151-not-for-logs"},
    )
    caplog.set_level(logging.INFO, logger="investo.orchestrator.bundle_context")
    compute_bundle_context({US_EQUITY: (position,)}, now_kst=U151_NOW)
    records = [r for r in caplog.records if r.msg == "shared_macro.candidate_rejected"]
    assert len(records) == 3
    assert {r.__dict__["key"] for r in records} == set(U151_KEYS)
    base_fields = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
    allowed = {
        "key",
        "segment",
        "source_name",
        "category",
        "reason",
        "title_preview",
        "title_hash",
        "message",
        "asctime",
    }
    for record in records:
        assert record.__dict__["reason"] == "positioning_not_shared_macro"
        assert len(record.__dict__["title_preview"]) <= 120
        assert len(record.__dict__["title_hash"]) == 12
        assert set(record.__dict__) - base_fields <= allowed
        assert secret_marker not in str(record.__dict__)
        assert "u151-not-for-logs" not in str(record.__dict__)
        assert "private-positioning-payload" not in str(record.__dict__)


@seed(15120260908)
@settings(max_examples=40)
@given(keys=st.frozensets(st.sampled_from(U151_KEYS)), data=st.data())
def test_u151_property_selected_subsets_and_overlap_survive_permutation(
    keys: frozenset[SharedMacroKey],
    data: st.DataObject,
) -> None:
    note("u151 seed=15120260908")
    routed = _selected_subset_routes_u151(keys)
    before = {
        segment: tuple(item.model_copy(deep=True) for item in items)
        for segment, items in routed.items()
    }
    reordered = {
        segment: tuple(data.draw(st.permutations(routed[segment]), label=segment))
        for segment in data.draw(st.permutations(tuple(routed)), label="segment_order")
    }
    ctx = compute_bundle_context(routed, now_kst=U151_NOW)
    _assert_selected_subset_u151(ctx, keys)
    assert compute_bundle_context(reordered, now_kst=U151_NOW) == ctx
    assert routed == before


def test_u151_selected_keys_and_thesis_are_stable_across_interpreter_hash_seeds() -> None:
    script = """
import json
from datetime import UTC, datetime
from investo.models import NormalizedItem
from investo.orchestrator.bundle_context import compute_bundle_context
now = datetime(2026, 9, 5, 9, tzinfo=UTC)
item = NormalizedItem(source_name="treasury-rates", category="macro",
    title="FOMC meeting WTI oil and UST 10Y yield", published_at=now, raw_metadata={})
ctx = compute_bundle_context({"us-equity": (item,), "crypto": (item,)}, now_kst=now)
print(json.dumps({
    "keys": ctx.model_dump(mode="json")["detected_macro_keys"],
    "block": ctx.shared_macro_block,
    "signals": [signal.model_dump(mode="json") for signal in ctx.daily_thesis_signals],
    "decision": ctx.daily_thesis_decision.model_dump(mode="json"),
}, sort_keys=True))
"""
    outputs = [
        subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, "PYTHONHASHSEED": str(hash_seed)},
        ).stdout
        # Interpreter seeds are uint32; the larger Hypothesis seed is separate.
        for hash_seed in (1, 2, 42, 20260908)
    ]
    assert len(set(outputs)) == 1
    projection = json.loads(outputs[0])
    assert projection["keys"] == list(U151_KEYS)
    assert [signal["key"] for signal in projection["signals"]] == ["fomc", "fomc"]
    assert projection["decision"]["macro_keys"] == ["fomc"]
    assert len(projection["block"].splitlines()) == 3
