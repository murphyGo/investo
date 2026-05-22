"""Unit tests for u57 Step 1.5 — :func:`compute_bundle_context`."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import NormalizedItem
from investo.models.bundle_context import (
    CROSS_MARKET_CORE_ALLOWED,
    BundleContext,
)
from investo.orchestrator.bundle_context import compute_bundle_context

NOW = datetime(2026, 5, 11, 9, 0, tzinfo=UTC)
IMMUNEFI_TITLE = "Immunefi to absorb Code4rena bug bounty customers after shutdown decision"


def make_item(
    *,
    source: str,
    title: str,
    published_at: datetime,
    category: str = "news",
    url: str = "https://example.com/x",
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category=category,  # type: ignore[arg-type]
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


@pytest.mark.parametrize(
    "explicit_bundle_id",
    ["custom-id-2026-05-11", "abc123"],
)
def test_bundle_id_override(explicit_bundle_id: str) -> None:
    ctx = compute_bundle_context({}, now_kst=NOW, bundle_id=explicit_bundle_id)
    assert ctx.bundle_id == explicit_bundle_id
