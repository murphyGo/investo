"""Tests for ``investo.notifier._summary_extract`` (u80 extraction layer).

These assert on STRUCTURED DATA only — no Telegram byte layout, no
UTF-16 budget, no percent/price string formatting. Byte-level layout
is covered by the unchanged ``test_summary.py`` suite; here we pin that
the extraction returns the right plain values so the layer can be
reasoned about independently of presentation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing, NormalizedItem
from investo.notifier._summary_extract import (
    ConclusionData,
    SnapshotEntry,
    clean_summary_text,
    conclusion_data,
    coverage_label,
    market_snapshot_entries,
    pct_change,
    price_value,
    watchlist_index_keys,
    watchlist_match_terms,
)

_TARGET_DATE = date(2026, 4, 25)


def _briefing(*, market_summary: str = "오늘 시장 요약", rendered: str | None = None) -> Briefing:
    body = (
        market_summary
        + "\n\n## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        + "## ③ 섹터/수급 동향\n섹터 동향\n\n"
        + "## ④ 지표·이벤트\n지표 이벤트\n\n"
        + "## ⑤ 주요 종목\n종목 본문\n\n"
        + "## ⑥ 오늘의 관전 포인트\n관전 포인트\n\n"
        + DISCLAIMER
    )
    if rendered is not None:
        rendered_md = rendered if DISCLAIMER in rendered else rendered + "\n\n" + DISCLAIMER
    else:
        rendered_md = "## ① 요약\n" + body
    return Briefing(
        target_date=_TARGET_DATE,
        market_summary=market_summary,
        key_issues="이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered_md,
    )


def _price_item(*, raw_metadata: dict[str, str], source_name: str = "yfinance") -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="price",
        title="px",
        published_at=datetime(2026, 4, 25, tzinfo=UTC),
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# clean_summary_text
# ---------------------------------------------------------------------------


def test_clean_summary_text_strips_markdown_tokens_and_links() -> None:
    assert clean_summary_text("**굵게** [라벨](http://x)") == "굵게 라벨"


def test_clean_summary_text_returns_empty_when_no_meaningful_chars() -> None:
    assert clean_summary_text("***") == ""
    assert clean_summary_text("   ") == ""


def test_clean_summary_text_strips_leading_list_marker() -> None:
    assert clean_summary_text("- 항목 하나") == "항목 하나"
    assert clean_summary_text("1. 첫째") == "첫째"


# ---------------------------------------------------------------------------
# coverage_label
# ---------------------------------------------------------------------------


def test_coverage_label_returns_text_before_em_dash() -> None:
    rendered = "## ① 요약\n> **데이터 상태**: 정상 — 3개 소스 수집\n"
    assert coverage_label(_briefing(rendered=rendered)) == "정상"


def test_coverage_label_none_when_absent() -> None:
    assert coverage_label(_briefing()) is None


# ---------------------------------------------------------------------------
# conclusion_data
# ---------------------------------------------------------------------------


def test_conclusion_data_pulls_conclusion_coverage_and_watchlist() -> None:
    rendered = (
        "## ① 요약\n"
        "> **오늘의 결론**: 상승 마감.\n"
        "> **데이터 상태**: 정상 — 풀 커버리지\n"
        "> **내 관심 자산 영향**: 1건 확인 — NVDA: 강세\n"
    )
    data = conclusion_data(_briefing(rendered=rendered))
    assert isinstance(data, ConclusionData)
    assert data.conclusion == "상승 마감."
    assert data.coverage_label == "정상"
    assert data.watchlist == "1건 확인 — NVDA: 강세"


def test_conclusion_data_filters_site_only_watchlist_nudges() -> None:
    rendered = "## ① 요약\n> **오늘의 결론**: 보합.\n> **내 관심 자산 영향**: 관심 목록 미설정\n"
    data = conclusion_data(_briefing(rendered=rendered))
    assert data.watchlist is None


def test_conclusion_data_falls_back_to_first_market_summary_line() -> None:
    data = conclusion_data(_briefing(market_summary="첫 줄 요약\n둘째 줄"))
    assert data.conclusion == "첫 줄 요약"
    assert data.coverage_label is None
    assert data.watchlist is None


def test_conclusion_data_sentinel_when_no_meaningful_line() -> None:
    # No conclusion line and a market_summary whose only line cleans to
    # empty (markdown tokens only) → the "데이터 부족" sentinel.
    data = conclusion_data(_briefing(market_summary="***"))
    assert data.conclusion == "데이터 부족"


# ---------------------------------------------------------------------------
# numeric parsing
# ---------------------------------------------------------------------------


def test_pct_change_prefers_explicit_field() -> None:
    item = _price_item(raw_metadata={"pct_change": "1.5"})
    assert pct_change(item) == 1.5


def test_pct_change_derives_from_close_and_prev_close() -> None:
    item = _price_item(raw_metadata={"close": "110", "prev_close": "100"})
    assert pct_change(item) == 10.0


def test_pct_change_none_when_prev_close_zero() -> None:
    item = _price_item(raw_metadata={"close": "110", "prev_close": "0"})
    assert pct_change(item) is None


def test_price_value_reads_first_available_key() -> None:
    assert price_value(_price_item(raw_metadata={"last_price": "42.5"})) == 42.5
    assert price_value(_price_item(raw_metadata={"price_usd": "108000"})) == 108000.0
    assert price_value(_price_item(raw_metadata={})) is None


# ---------------------------------------------------------------------------
# market_snapshot_entries
# ---------------------------------------------------------------------------


def test_market_snapshot_entries_order_and_kind() -> None:
    items = [
        _price_item(raw_metadata={"ticker": "^GSPC", "pct_change": "1.2"}),
        _price_item(raw_metadata={"index_name": "코스피", "pct_change": "-0.3"}),
        _price_item(raw_metadata={"symbol": "BTCUSDT", "price_usd": "108000", "pct_24h": "0.4"}),
    ]
    entries = market_snapshot_entries(items)
    # S&P 500 then KOSPI then BTC (Nasdaq absent).
    assert [e.label for e in entries] == ["S&P500", "KOSPI", "BTC"]
    assert all(isinstance(e, SnapshotEntry) for e in entries)
    sp, kospi, btc = entries
    assert sp.with_price is False and sp.pct == 1.2
    assert kospi.with_price is False and kospi.pct == -0.3
    assert btc.with_price is True and btc.price == 108000.0 and btc.pct == 0.4


def test_market_snapshot_entries_empty_without_price_rows() -> None:
    assert market_snapshot_entries([]) == []


# ---------------------------------------------------------------------------
# watchlist helpers
# ---------------------------------------------------------------------------


def test_watchlist_index_keys_includes_btc_from_pair() -> None:
    keys = watchlist_index_keys(_price_item(raw_metadata={"symbol": "BTCUSDT"}))
    assert "btcusdt" in keys
    assert "btc" in keys


def test_watchlist_match_terms_splits_term_and_rest() -> None:
    pairs = watchlist_match_terms("NVDA: 강세; TSLA: 약세")
    assert pairs == [("NVDA", "강세"), ("TSLA", "약세")]


def test_watchlist_match_terms_passes_through_unmatched_segment() -> None:
    pairs = watchlist_match_terms("그냥 텍스트")
    assert pairs == [("", "그냥 텍스트")]
