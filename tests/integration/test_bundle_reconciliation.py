"""Integration tests for u57 — BundleContext wire-through (Step 6).

Synthetic-fixture tests that drive the orchestrator
``_apply_reader_format_to_segments`` chain end-to-end with a
deterministic :class:`BundleContext`. No live LLM calls (R10).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing, NormalizedItem
from investo.models.bundle_context import BundleContext, MarketStateSummary
from investo.orchestrator.bundle_context import compute_bundle_context
from investo.orchestrator.pipeline import _apply_reader_format_to_segments

IMMUNEFI_TITLE = "Immunefi to absorb Code4rena bug bounty customers after shutdown decision"


def _make_briefing(segment: str, markdown: str) -> Briefing:
    full_markdown = f"{markdown}\n{DISCLAIMER}\n"
    return Briefing(
        target_date=date(2026, 5, 11),
        market_summary="요약 [상승 관찰]",
        key_issues="핵심 이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=full_markdown,
    )


def _item(
    *,
    source: str,
    title: str,
    category: str = "news",
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source,
        category=category,  # type: ignore[arg-type]
        title=title,
        url="https://example.com/item",
        published_at=datetime(2026, 5, 11, 9, 0, tzinfo=UTC),
        raw_metadata={},
    )


def _ctx(close_states: dict[str, str], *, shared_macro: str | None = None) -> BundleContext:
    return BundleContext(
        bundle_id="2026-05-11-bundle",
        target_kst_date=date(2026, 5, 11),
        segments={
            seg: MarketStateSummary(
                segment=seg,
                target_date=date(2026, 5, 11),
                tz="UTC",
                close_state=state,  # type: ignore[arg-type]
            )
            for seg, state in close_states.items()
        },
        shared_macro_block=shared_macro,
    )


MINIMAL_BODY = (
    "## ① 요약\n\n오늘의 시장.\n\n## ② 전일 핵심 이슈\n\n"
    "### 코스피 종가\n0.5% 하락 마감.\n\n## ③ 섹터/수급 동향\n\n섹터.\n\n"
    "## ④ 지표·이벤트\n\n지표.\n\n## ⑤ 주요 종목\n\n종목.\n\n"
    "## ⑥ 오늘의 관전 포인트\n\n관전.\n"
)


class TestSharedMacroInjection:
    def test_macro_block_injected(self) -> None:
        ctx = _ctx(
            {DOMESTIC_EQUITY: "close", US_EQUITY: "close", CRYPTO: "pending"},
            shared_macro="- **국제 유가** — Brent 79$",
        )
        briefings = {DOMESTIC_EQUITY: _make_briefing(DOMESTIC_EQUITY, MINIMAL_BODY)}
        out = _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        assert "## ⓪ 오늘의 매크로" in out[DOMESTIC_EQUITY].rendered_markdown
        assert "국제 유가" in out[DOMESTIC_EQUITY].rendered_markdown

    def test_no_macro_when_block_none(self) -> None:
        ctx = _ctx({DOMESTIC_EQUITY: "close"}, shared_macro=None)
        briefings = {DOMESTIC_EQUITY: _make_briefing(DOMESTIC_EQUITY, MINIMAL_BODY)}
        out = _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        assert "## ⓪" not in out[DOMESTIC_EQUITY].rendered_markdown

    def test_computed_ust_macro_uses_canonical_evidence_and_stays_idempotent(self) -> None:
        ctx = compute_bundle_context(
            {
                US_EQUITY: [
                    _item(
                        source="fred-macro",
                        category="macro",
                        title="DGS10 4.46 (+0.0400 from prior)",
                    ),
                ],
                CRYPTO: [
                    _item(
                        source="theblock-crypto",
                        title=IMMUNEFI_TITLE,
                    ),
                    _item(
                        source="treasury-rates",
                        category="macro",
                        title="UST curve 2026-05-13: 10Y 4.46%, 2Y10Y +0.48pp",
                    ),
                ],
            },
            now_kst=datetime(2026, 5, 11, 9, 0, tzinfo=UTC),
        )
        assert ctx.shared_macro_block is not None
        briefings = {US_EQUITY: _make_briefing(US_EQUITY, MINIMAL_BODY)}
        once = _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        twice = _apply_reader_format_to_segments(
            once,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        rendered = twice[US_EQUITY].rendered_markdown
        assert rendered.count("## ⓪ 오늘의 매크로") == 1
        assert "미 국채 수익률" in rendered
        assert "UST curve 2026-05-13" in rendered
        assert "Immunefi to absorb Code4rena" not in rendered


class TestTimeStateContradictionLogged:
    def test_us_close_with_domestic_open_wording_logs_reject(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        body_with_contradiction = MINIMAL_BODY.replace(
            "오늘의 시장.",
            "오늘 미국 증시가 하락 출발했다고 본다.",
        )
        ctx = _ctx({US_EQUITY: "close", DOMESTIC_EQUITY: "pending", CRYPTO: "pending"})
        briefings = {DOMESTIC_EQUITY: _make_briefing(DOMESTIC_EQUITY, body_with_contradiction)}
        caplog.set_level(logging.WARNING)
        _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        assert any(
            "cross_segment_lint.time_state_contradiction" in rec.getMessage()
            for rec in caplog.records
        )


class TestForeignTickerLinkageLogged:
    def test_bare_foreign_logs_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        body_with_aapl = MINIMAL_BODY.replace(
            "오늘의 시장.",
            "오늘 AAPL 단독 등장.",
        )
        ctx = _ctx({DOMESTIC_EQUITY: "pending", US_EQUITY: "pending", CRYPTO: "pending"})
        briefings = {DOMESTIC_EQUITY: _make_briefing(DOMESTIC_EQUITY, body_with_aapl)}
        caplog.set_level(logging.WARNING)
        _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        assert any(
            "cross_segment_lint.foreign_ticker_no_linkage" in rec.getMessage()
            for rec in caplog.records
        )

    def test_foreign_with_linkage_passes(self, caplog: pytest.LogCaptureFixture) -> None:
        body_with_link = MINIMAL_BODY.replace(
            "오늘의 시장.",
            "오늘 AAPL 등장 — 국내 영향 제한적.",
        )
        ctx = _ctx({DOMESTIC_EQUITY: "pending", US_EQUITY: "pending", CRYPTO: "pending"})
        briefings = {DOMESTIC_EQUITY: _make_briefing(DOMESTIC_EQUITY, body_with_link)}
        caplog.set_level(logging.WARNING)
        _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=ctx,
        )
        assert not any(
            "cross_segment_lint.foreign_ticker_no_linkage" in rec.getMessage()
            for rec in caplog.records
        )


class TestNoBundleContextNoLint:
    def test_bundle_context_none_skips_chain(self, caplog: pytest.LogCaptureFixture) -> None:
        body_with_aapl = MINIMAL_BODY.replace("오늘의 시장.", "AAPL 단독.")
        briefings = {DOMESTIC_EQUITY: _make_briefing(DOMESTIC_EQUITY, body_with_aapl)}
        caplog.set_level(logging.WARNING)
        _apply_reader_format_to_segments(
            briefings,
            anchors_by_segment={},
            bundle_context=None,
        )
        # No lint records because we skipped the chain.
        assert not any("cross_segment_lint" in rec.getMessage() for rec in caplog.records)
