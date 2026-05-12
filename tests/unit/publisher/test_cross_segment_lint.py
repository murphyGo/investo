"""Unit tests for u57 Step 3 — cross-segment lint."""

from __future__ import annotations

from datetime import date

import pytest

from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models.bundle_context import BundleContext, MarketStateSummary
from investo.publisher.cross_segment_lint import (
    DOMESTIC_LINKAGE_KEYWORDS,
    FOREIGN_TICKER_PATTERN,
    lint_domestic_foreign_linkage,
    lint_native_fact_priority,
    lint_time_state_consistency,
    run_all_cross_segment_lints,
)


def make_ctx(close_states: dict[str, str]) -> BundleContext:
    return BundleContext(
        bundle_id="b",
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
    )


class TestForeignTickerLinkage:
    def test_pass_when_foreign_and_domestic_in_same_paragraph(self) -> None:
        text = "AAPL이 005930 삼성전자에 미치는 영향이 크다."
        assert lint_domestic_foreign_linkage(text) == []

    def test_pass_when_linkage_keyword_present(self) -> None:
        text = "AAPL 상승 — 국내 영향은 제한적."
        assert lint_domestic_foreign_linkage(text) == []

    def test_violation_foreign_alone(self) -> None:
        text = "AAPL이 2% 상승했다."
        violations = lint_domestic_foreign_linkage(text)
        assert len(violations) == 1
        assert violations[0].kind == "cross_segment_lint.foreign_ticker_no_linkage"
        assert violations[0].evidence == "AAPL"

    def test_severity_warn_outside_watchlist(self) -> None:
        text = "AAPL이 2% 상승했다."
        violations = lint_domestic_foreign_linkage(text)
        assert violations[0].severity == "WARN"

    def test_severity_reject_inside_watchlist(self) -> None:
        text = "## ⑤ 워치리스트\n\nTSMC가 신고가 경신.\n"
        violations = lint_domestic_foreign_linkage(text)
        # The header paragraph carries the foreign-ticker mention but
        # let's also feed a follow-up paragraph to be explicit.
        # Add a clear ticker in its own paragraph under watchlist.
        text2 = "## ⑤ 워치리스트\n\nThis section.\n\nTSMC 가 신고가 경신.\n"
        violations = lint_domestic_foreign_linkage(text2)
        assert any(v.severity == "REJECT" for v in violations)

    def test_strict_watchlist_off_demotes_to_warn(self) -> None:
        text = "## ⑤ 워치리스트\n\nThis section.\n\nTSMC 가 신고가 경신.\n"
        violations = lint_domestic_foreign_linkage(text, strict_watchlist=False)
        assert all(v.severity == "WARN" for v in violations)

    def test_empty_text(self) -> None:
        assert lint_domestic_foreign_linkage("") == []

    def test_no_foreign_ticker(self) -> None:
        text = "코스피가 0.5% 상승 마감했다."
        assert lint_domestic_foreign_linkage(text) == []

    def test_multiple_paragraphs_only_offenders_flagged(self) -> None:
        text = (
            "AAPL과 005930 삼성전자 동조화.\n\nNVDA 단독 등장.\n\n외국인 매매와 함께 META 언급.\n"
        )
        violations = lint_domestic_foreign_linkage(text)
        # Only the middle paragraph violates.
        assert len(violations) == 1
        assert violations[0].evidence == "NVDA"


class TestNativeFactPriority:
    def test_us_pass_when_first_h3_is_spx(self) -> None:
        text = "## ② 코어 데이터\n\n### S&P 500 종가\n0.5% 상승.\n"
        assert lint_native_fact_priority(text, US_EQUITY) == []

    def test_us_violation_when_first_h3_is_iran(self) -> None:
        text = "## ② 코어 데이터\n\n### 이란 / 유가 변수\n지정학 리스크.\n"
        violations = lint_native_fact_priority(text, US_EQUITY)
        assert len(violations) == 1
        assert violations[0].kind == "cross_segment_lint.native_priority_violated"
        assert violations[0].severity == "WARN"

    def test_domestic_pass_when_first_h3_has_ticker(self) -> None:
        text = "## ② 코어 데이터\n\n### 005930 삼성전자 분석\n외국인 순매수.\n"
        assert lint_native_fact_priority(text, DOMESTIC_EQUITY) == []

    def test_domestic_pass_kospi_keyword(self) -> None:
        text = "## ② 코어 데이터\n\n### 코스피 종가\n0.3% 하락.\n"
        assert lint_native_fact_priority(text, DOMESTIC_EQUITY) == []

    def test_crypto_pass_btc(self) -> None:
        text = "## ② 코어\n\n### BTC 가격\n6만 달러.\n"
        assert lint_native_fact_priority(text, CRYPTO) == []

    def test_no_section_two_silent(self) -> None:
        text = "## ① 요약\n\nFoo bar.\n"
        assert lint_native_fact_priority(text, DOMESTIC_EQUITY) == []

    def test_section_two_empty_silent(self) -> None:
        text = "## ② 코어\n\n## ③ Other\n"
        assert lint_native_fact_priority(text, DOMESTIC_EQUITY) == []

    def test_fallback_to_first_line_when_no_h3(self) -> None:
        text = "## ② 코어\n\n코스피가 마감했다.\n"
        assert lint_native_fact_priority(text, DOMESTIC_EQUITY) == []

    def test_fallback_violation(self) -> None:
        text = "## ② 코어\n\nIran tensions dominate.\n"
        violations = lint_native_fact_priority(text, DOMESTIC_EQUITY)
        assert len(violations) == 1


class TestTimeStateConsistency:
    def test_violation_us_closed_but_body_says_open_down(self) -> None:
        text = "미국 증시가 하락 출발했다는 점에 주목."
        ctx = make_ctx({US_EQUITY: "close"})
        violations = lint_time_state_consistency(text, ctx)
        assert len(violations) == 1
        assert violations[0].severity == "REJECT"
        assert violations[0].kind == "cross_segment_lint.time_state_contradiction"

    def test_pass_when_us_is_actually_open(self) -> None:
        text = "미국 증시가 하락 출발."
        ctx = make_ctx({US_EQUITY: "open"})
        assert lint_time_state_consistency(text, ctx) == []

    def test_pass_when_no_segment_citation(self) -> None:
        text = "어딘가에서 하락 출발."
        ctx = make_ctx({US_EQUITY: "close"})
        assert lint_time_state_consistency(text, ctx) == []

    def test_pass_when_us_is_pending(self) -> None:
        text = "미국 증시가 하락 출발."
        ctx = make_ctx({US_EQUITY: "pending"})
        assert lint_time_state_consistency(text, ctx) == []


class TestRunAllAggregator:
    def test_domestic_segment_runs_linkage_lint(self) -> None:
        text = "AAPL이 단독 등장."
        ctx = make_ctx({DOMESTIC_EQUITY: "pending"})
        result = run_all_cross_segment_lints(text, segment=DOMESTIC_EQUITY, ctx=ctx)
        assert any(v.kind.startswith("cross_segment_lint.foreign") for v in result)

    def test_us_segment_skips_linkage_lint(self) -> None:
        text = "AAPL이 단독 등장."
        ctx = make_ctx({US_EQUITY: "pending"})
        result = run_all_cross_segment_lints(text, segment=US_EQUITY, ctx=ctx)
        assert not any(v.kind.startswith("cross_segment_lint.foreign") for v in result)


class TestConstantsPin:
    def test_foreign_pattern_matches_known_tickers(self) -> None:
        for tk in ("AAPL", "NVDA", "TSMC", "META"):
            assert FOREIGN_TICKER_PATTERN.search(tk) is not None

    def test_linkage_keywords_have_expected(self) -> None:
        for kw in ("국내 영향", "환율 경로", "외국인 매매"):
            assert kw in DOMESTIC_LINKAGE_KEYWORDS


class TestEdgeCases:
    @pytest.mark.parametrize("text", ["", "   ", "\n\n\n"])
    def test_empty_inputs(self, text: str) -> None:
        assert lint_domestic_foreign_linkage(text) == []
        ctx = make_ctx({US_EQUITY: "close"})
        assert lint_time_state_consistency(text, ctx) == []
