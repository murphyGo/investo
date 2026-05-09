"""Tests for ``investo.notifier.summary.build_summary`` (FR-004).

Pins UTF-16-aware truncation, footer preservation, and the
defense-in-depth round-trip through ``BriefingNotification``'s
4096-unit validator.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing, BriefingNotification, NormalizedItem
from investo.notifier.summary import (
    DEFAULT_MAX_UNITS,
    _utf16_truncate,
    _utf16_units,
    build_segmented_summary,
    build_summary,
    plain_text_summary,
)

_TARGET_DATE = date(2026, 4, 25)
_SITE_URL = "https://example.github.io/investo/2026/04/2026-04-25/"
_SEGMENT_URLS = {
    DOMESTIC_EQUITY: "https://example.github.io/investo/archive/domestic-equity/2026/04/2026-04-25/",
    US_EQUITY: "https://example.github.io/investo/archive/us-equity/2026/04/2026-04-25/",
    CRYPTO: "https://example.github.io/investo/archive/crypto/2026/04/2026-04-25/",
}


def _build_briefing(*, market_summary: str = "오늘 시장 요약") -> Briefing:
    """Factory for `Briefing` with a controllable `market_summary`."""
    body = (
        market_summary
        + "\n\n## ② 전일 핵심 이슈\n핵심 이슈\n\n"
        + "## ③ 섹터/수급 동향\n섹터 동향\n\n"
        + "## ④ 지표·이벤트\n지표 이벤트\n\n"
        + "## ⑤ 주요 종목\n종목 본문\n\n"
        + "## ⑥ 오늘의 관전 포인트\n관전 포인트\n\n"
        + DISCLAIMER
    )
    rendered = "## ① 요약\n" + body
    return Briefing(
        target_date=_TARGET_DATE,
        market_summary=market_summary,
        key_issues="이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )


def _price_item(
    *,
    source_name: str,
    title: str,
    raw_metadata: dict[str, str],
) -> NormalizedItem:
    return NormalizedItem(
        source_name=source_name,
        category="price",
        title=title,
        published_at=datetime(2026, 4, 25, tzinfo=UTC),
        raw_metadata=raw_metadata,
    )


# ---------------------------------------------------------------------------
# UTF-16 helpers (white-box)
# ---------------------------------------------------------------------------


def test_utf16_units_ascii_is_one_per_char() -> None:
    assert _utf16_units("hello") == 5


def test_utf16_units_korean_is_one_per_char() -> None:
    """Korean syllables in BMP — 1 UTF-16 unit each."""
    assert _utf16_units("안녕") == 2


def test_utf16_units_emoji_is_two_per_codepoint() -> None:
    """``📈`` is U+1F4C8 (non-BMP) → 2 UTF-16 units (surrogate pair)."""
    assert _utf16_units("📈") == 2
    assert _utf16_units("📈📈📈") == 6


def test_utf16_truncate_passthrough_when_under_limit() -> None:
    assert _utf16_truncate("hello", 100) == "hello"


def test_utf16_truncate_drops_partial_surrogate_pair() -> None:
    """Truncating between the high + low halves of a surrogate pair
    must drop the orphan high half so the result is valid UTF-16.
    """
    text = "AB📈CD"  # A B [hi-surr] [lo-surr] C D = 6 UTF-16 units
    assert _utf16_units(text) == 6
    # Truncating to 3 units would land mid-surrogate-pair (after the
    # high half). Expect the orphan to be dropped → "AB" (2 units).
    truncated = _utf16_truncate(text, 3)
    assert truncated == "AB"


def test_utf16_truncate_zero_max_returns_empty() -> None:
    assert _utf16_truncate("anything", 0) == ""


def test_utf16_truncate_drops_lone_high_surrogate_at_position_zero() -> None:
    """Step 7 sub-agent review Q2 follow-up — ``_utf16_truncate("📈AB", 1)``
    yields "" because the single requested unit lands on the high
    surrogate of 📈 with no room for the low surrogate. The orphan
    must be dropped (returning "" not "\\ud83d") to keep the result
    valid UTF-16.
    """
    result = _utf16_truncate("📈AB", 1)
    assert result == ""
    # Sanity: result is valid UTF-16 (re-encoding round-trips cleanly).
    result.encode("utf-16-le").decode("utf-16-le")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_build_summary_includes_target_date_and_url() -> None:
    briefing = _build_briefing(market_summary="짧은 요약")
    summary = build_summary(briefing, site_url=_SITE_URL)

    assert "2026-04-25" in summary
    assert "짧은 요약" in summary
    assert _SITE_URL in summary
    assert f"[상세보기]({_SITE_URL})" in summary
    assert f"상세보기: {_SITE_URL}" not in summary
    assert "📈" in summary  # the emoji header anchor


def test_build_summary_short_briefing_no_truncation() -> None:
    briefing = _build_briefing(market_summary="요약")
    summary = build_summary(briefing, site_url=_SITE_URL)
    assert "…" not in summary  # no truncation suffix for short input


def test_build_summary_fits_under_default_max_units() -> None:
    briefing = _build_briefing(market_summary="요약")
    summary = build_summary(briefing, site_url=_SITE_URL)
    assert _utf16_units(summary) <= DEFAULT_MAX_UNITS


# ---------------------------------------------------------------------------
# Truncation cases
# ---------------------------------------------------------------------------


def test_build_summary_truncates_long_korean_market_summary() -> None:
    long_korean = "가" * 5000  # 5000 BMP chars = 5000 UTF-16 units
    briefing = _build_briefing(market_summary=long_korean)
    summary = build_summary(briefing, site_url=_SITE_URL)

    assert _utf16_units(summary) <= DEFAULT_MAX_UNITS
    assert summary.endswith(f"\n\n[상세보기]({_SITE_URL})")
    assert "…" in summary  # truncation suffix present


def test_build_summary_emoji_2_unit_per_codepoint_accounting() -> None:
    """2100 emoji = 4200 UTF-16 units; with header + footer this overflows
    4096 and must be truncated. ``len(s)`` would say 2100 chars and
    incorrectly believe it fits — pinning that we use UTF-16 counting.
    """
    emoji_blob = "📈" * 2100  # 4200 UTF-16 units, well over the cap
    briefing = _build_briefing(market_summary=emoji_blob)
    summary = build_summary(briefing, site_url=_SITE_URL)

    assert _utf16_units(summary) <= DEFAULT_MAX_UNITS
    assert "…" in summary


def test_build_summary_footer_url_always_preserved_at_truncation() -> None:
    """The footer line ``상세보기: {url}`` survives truncation intact."""
    long_text = "x" * 10000
    briefing = _build_briefing(market_summary=long_text)
    summary = build_summary(briefing, site_url=_SITE_URL)

    assert summary.endswith(f"\n\n[상세보기]({_SITE_URL})")
    assert _SITE_URL in summary


def test_plain_text_summary_removes_markdown_markers_but_preserves_urls() -> None:
    result = plain_text_summary(
        "🇺🇸 *미국 증시* [부분]\n[상세보기](https://example.com/us)\n반도체 **실적** 확인"
    )

    assert result == ("🇺🇸 미국 증시 [부분]\n상세보기: https://example.com/us\n반도체 실적 확인")


def test_build_segmented_summary_includes_all_labels_and_urls() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="코스피 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "📈 2026-04-25 데일리 시황" in summary
    assert f"🇰🇷 *국내 증시*\n[상세보기]({_SEGMENT_URLS[DOMESTIC_EQUITY]})\n코스피 요약" in summary
    assert f"🇺🇸 *미국 증시*\n[상세보기]({_SEGMENT_URLS[US_EQUITY]})\nS&P 500 요약" in summary
    assert f"₿ *크립토*\n[상세보기]({_SEGMENT_URLS[CRYPTO]})\nBitcoin 요약" in summary
    assert "• 국내 증시: [상세보기](" in summary
    assert "• 미국 증시: [상세보기](" in summary
    assert "• 크립토: [상세보기](" in summary
    for url in _SEGMENT_URLS.values():
        assert url in summary


def test_segmented_summary_preserves_default_bundle_badge() -> None:
    rendered = (
        "## ① 요약\n"
        "> **오늘의 결론**: 반도체 강세\n"
        "반도체 강세\n\n"
        "## ② 전일 핵심 이슈\n이슈\n\n"
        "## ③ 섹터/수급 동향\n섹터\n\n"
        "## ④ 지표·이벤트\n지표\n\n"
        "## ⑤ 주요 종목\n"
        "> **내 관심 자산 영향**: 1건 확인 (기본 바스켓) — NVDA: NVIDIA rallies\n\n"
        "## ⑥ 오늘의 관전 포인트\n관전\n\n" + DISCLAIMER
    )
    briefing = Briefing(
        target_date=_TARGET_DATE,
        market_summary="반도체 강세",
        key_issues="이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=rendered,
    )

    summary = build_segmented_summary({US_EQUITY: briefing}, site_urls=_SEGMENT_URLS)

    assert "관심: 1건 확인 (기본 바스켓)" in summary


def test_build_segmented_summary_adds_market_snapshot_from_price_items() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="코스피 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }
    price_items = (
        _price_item(
            source_name="yfinance-price",
            title="^GSPC 5,200.00 (+0.42%)",
            raw_metadata={"ticker": "^GSPC", "close": "5200.000000", "prev_close": "5178.249353"},
        ),
        _price_item(
            source_name="yfinance-price",
            title="^IXIC 16,700.00 (+0.69%)",
            raw_metadata={"ticker": "^IXIC", "close": "16700.000000", "prev_close": "16585.015889"},
        ),
        _price_item(
            source_name="fsc-krx-index-price",
            title="코스피 2,650.00 (-0.20%)",
            raw_metadata={
                "index_name": "코스피",
                "close": "2650.000000",
                "pct_change": "-0.200000",
            },
        ),
        _price_item(
            source_name="binance-crypto-market",
            title="BTCUSDT 24h 108,200.00 (-1.23%)",
            raw_metadata={
                "symbol": "BTCUSDT",
                "last_price": "108200.000000",
                "pct_change_24h": "-1.230000",
            },
        ),
    )

    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        price_items=price_items,
    )

    assert "📈 2026-04-25 데일리 시황\n" in summary
    assert "🕐 KST " in summary  # publish-time label inserted before snapshot
    assert "전 거래일: 2026-04-25" in summary
    assert "시장: " in summary
    assert "SPX +0.4%" in summary
    assert "NDX +0.7%" in summary
    assert "KOSPI -0.2%" in summary
    assert "BTC 108.2k(-1.2%)" in summary


def test_build_segmented_summary_omits_market_snapshot_when_price_items_missing() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="코스피 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "\n시장: " not in summary


def test_build_segmented_summary_prefers_clean_rendered_conclusion() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="1. **깨진 요약**"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }
    briefings[DOMESTIC_EQUITY] = briefings[DOMESTIC_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 국내 증시 시황\n\n"
                "> **오늘의 결론**: [국내 증시](https://example.com)는 **데이터 부족**입니다.\n\n"
                + briefings[DOMESTIC_EQUITY].rendered_markdown
            )
        }
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "🇰🇷 *국내 증시*\n[상세보기](" in summary
    assert "국내 증시는 데이터 부족입니다." in summary
    assert "🇰🇷 *국내 증시*\n1." not in summary
    assert "[국내 증시]" not in summary
    assert "**데이터 부족**" not in summary


def test_build_segmented_summary_includes_clean_coverage_label_when_present() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }
    briefings[CRYPTO] = briefings[CRYPTO].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 크립토 시황\n\n"
                "> **데이터 상태**: 부분 — 수집 1건 / 소스 1개 / 누락: 뉴스\n"
                "> **오늘의 결론**: Bitcoin 가격 근거만 확인됐습니다.\n\n"
                + briefings[CRYPTO].rendered_markdown
            )
        }
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "₿ *크립토* [부분]" in summary
    assert "부분 — Bitcoin 가격 근거만 확인됐습니다." in summary
    assert "수집 1건" not in summary


def test_build_segmented_summary_includes_watchlist_impact_when_present() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }
    briefings[US_EQUITY] = briefings[US_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 미국 증시 시황\n\n"
                "> **오늘의 결론**: 반도체 실적을 확인합니다.\n"
                "> **내 관심 자산 영향**: 1건 확인 — NVDA: NVDA rallies after earnings\n\n"
                + briefings[US_EQUITY].rendered_markdown
            )
        }
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "🇺🇸 *미국 증시*\n[상세보기](" in summary
    assert "반도체 실적을 확인합니다. / 관심: 1건 확인 — NVDA" in summary


def test_build_segmented_summary_omits_coverage_hold_watchlist_suffix() -> None:
    """u28 — when the watchlist callout is the coverage-hold branch, the
    Telegram one-liner must NOT add a "/ 관심: 데이터 수집 부족" suffix
    (the segment coverage badge already conveys insufficient data)."""
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }
    briefings[US_EQUITY] = briefings[US_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 미국 증시 시황\n\n"
                "> **오늘의 결론**: 반도체 실적을 확인합니다.\n"
                "> **내 관심 자산 영향**: 데이터 수집 부족으로 매칭 판단 보류 — "
                "추가 수집 후 재평가됩니다.\n\n" + briefings[US_EQUITY].rendered_markdown
            )
        }
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    # Conclusion still surfaces, but the coverage-hold prefix does not bleed
    # into the Telegram suffix.
    assert "반도체 실적을 확인합니다." in summary
    assert "관심: 데이터 수집 부족" not in summary


def test_build_segmented_summary_preserves_all_urls_under_truncation() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 " + ("가" * 5000)),
        US_EQUITY: _build_briefing(market_summary="미국 " + ("나" * 5000)),
        CRYPTO: _build_briefing(market_summary="크립토 " + ("다" * 5000)),
    }

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert _utf16_units(summary) <= DEFAULT_MAX_UNITS
    assert "…" in summary
    for url in _SEGMENT_URLS.values():
        assert url in summary


def test_build_segmented_summary_rejects_footer_that_cannot_fit() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내"),
        US_EQUITY: _build_briefing(market_summary="미국"),
        CRYPTO: _build_briefing(market_summary="크립토"),
    }

    with pytest.raises(ValueError, match="fixed content exceeds"):
        build_segmented_summary(briefings, site_urls=_SEGMENT_URLS, max_units=80)


def test_build_summary_truncation_suffix_at_body_end() -> None:
    """The "…" lands between the truncated body and the footer."""
    long_text = "Y" * 10000
    briefing = _build_briefing(market_summary=long_text)
    summary = build_summary(briefing, site_url=_SITE_URL)

    # The pattern: ...truncated body...…\n\n상세보기: {url}
    assert f"…\n\n[상세보기]({_SITE_URL})" in summary


# ---------------------------------------------------------------------------
# Defense-in-depth: round-trip through BriefingNotification
# ---------------------------------------------------------------------------


def test_build_summary_round_trip_through_briefing_notification() -> None:
    """The constructed summary, fed back to ``BriefingNotification``,
    passes the model's own 4096-unit validator. Belt-and-braces: if
    ``build_summary`` ever miscalculates the budget by 1 unit, the
    model rejects on construction.
    """
    long_korean = "가" * 5000
    briefing = _build_briefing(market_summary=long_korean)
    summary = build_summary(briefing, site_url=_SITE_URL)

    # The site_url field of the model takes an HttpUrl; we pass the
    # SAME url here as in the body so the model + summary stay
    # consistent.
    notification = BriefingNotification(
        target_date=_TARGET_DATE,
        summary_text=summary,
        site_url=_SITE_URL,  # type: ignore[arg-type]
    )
    # If construction succeeded, the validator passed — round-trip OK.
    assert notification.target_date == _TARGET_DATE


def test_build_segmented_summary_round_trip_through_briefing_notification() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 " + ("가" * 5000)),
        US_EQUITY: _build_briefing(market_summary="미국 " + ("나" * 5000)),
        CRYPTO: _build_briefing(market_summary="크립토 " + ("다" * 5000)),
    }
    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    notification = BriefingNotification(
        target_date=_TARGET_DATE,
        summary_text=summary,
        site_url=_SEGMENT_URLS[DOMESTIC_EQUITY],  # type: ignore[arg-type]
    )

    assert notification.target_date == _TARGET_DATE


# ---------------------------------------------------------------------------
# Custom max_units (defense in depth for future SMS / smaller targets)
# ---------------------------------------------------------------------------


def test_build_summary_respects_custom_max_units() -> None:
    """Caller can shrink the cap (e.g., for a future SMS gateway)."""
    briefing = _build_briefing(market_summary="x" * 5000)
    summary = build_summary(briefing, site_url=_SITE_URL, max_units=200)

    assert _utf16_units(summary) <= 200
    # Even at 200 units, footer + header + at least some body fit.
    assert _SITE_URL in summary


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_summary_module_exports_expected_names() -> None:
    from investo.notifier import summary as summary_module

    assert hasattr(summary_module, "build_summary")
    assert hasattr(summary_module, "DEFAULT_MAX_UNITS")
    assert summary_module.DEFAULT_MAX_UNITS == 4096


# ---------------------------------------------------------------------------
# u35 — deterministic imminent-event tag
# ---------------------------------------------------------------------------


def _imminent_briefings() -> dict:
    """Three briefings with a single rendered conclusion line each."""
    return {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약").model_copy(
            update={
                "rendered_markdown": (
                    "# 2026-04-25 국내 증시 시황\n\n> **오늘의 결론**: 국내 한 줄.\n\n"
                )
            }
        ),
        US_EQUITY: _build_briefing(market_summary="미국 요약").model_copy(
            update={
                "rendered_markdown": (
                    "# 2026-04-25 미국 증시 시황\n\n> **오늘의 결론**: 미국 한 줄.\n\n"
                )
            }
        ),
        CRYPTO: _build_briefing(market_summary="크립토 요약").model_copy(
            update={
                "rendered_markdown": (
                    "# 2026-04-25 크립토 시황\n\n> **오늘의 결론**: 크립토 한 줄.\n\n"
                )
            }
        ),
    }


def _earnings_item(*, symbol: str, scheduled_at_iso: str) -> object:
    from datetime import datetime

    from investo.models import NormalizedItem

    return NormalizedItem(
        source_name="nasdaq-earnings-calendar",
        category="earnings",
        title=f"{symbol} earnings — after-hours",
        published_at=datetime(2026, 4, 25, tzinfo=__import__("datetime").timezone.utc),
        scheduled_at=datetime.fromisoformat(scheduled_at_iso),
        raw_metadata={"symbol": symbol, "company_name": f"{symbol} Inc."},
    )


def _fomc_item(*, scheduled_at_iso: str) -> object:
    from datetime import datetime

    from investo.models import NormalizedItem

    return NormalizedItem(
        source_name="fomc-rss",
        category="calendar",
        title="FOMC press release — Federal Open Market Committee",
        published_at=datetime(2026, 4, 25, tzinfo=__import__("datetime").timezone.utc),
        scheduled_at=datetime.fromisoformat(scheduled_at_iso),
        raw_metadata={"event": "FOMC"},
    )


def test_imminent_tag_prepended_for_event_within_72h() -> None:
    """An event 2 days out emits ``📊 NVDA 실적 D-2 ·`` prefix on the line."""
    from datetime import datetime

    briefings = _imminent_briefings()
    now_utc = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    nvda = _earnings_item(symbol="NVDA", scheduled_at_iso="2026-04-27T20:00:00+00:00")
    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        lookahead_items_by_segment={US_EQUITY: (nvda,)},
        now_utc=now_utc,
    )
    assert "📊 NVDA 실적 D-2" in summary
    # Other segments untouched.
    assert "📊" not in summary.split("🇰🇷")[0] if "🇰🇷" in summary else True


def test_imminent_tag_absent_when_event_outside_horizon() -> None:
    """Event 5 days out > 72h horizon → no tag."""
    from datetime import datetime

    briefings = _imminent_briefings()
    now_utc = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    nvda = _earnings_item(symbol="NVDA", scheduled_at_iso="2026-04-30T20:00:00+00:00")
    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        lookahead_items_by_segment={US_EQUITY: (nvda,)},
        now_utc=now_utc,
    )
    assert "NVDA 실적 D-" not in summary


def test_imminent_tag_picks_earliest_when_multiple_qualify() -> None:
    """Ties broken by ``scheduled_at`` ascending — deterministic ordering."""
    from datetime import datetime

    briefings = _imminent_briefings()
    now_utc = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    earlier = _earnings_item(symbol="AAA", scheduled_at_iso="2026-04-26T08:00:00+00:00")
    later = _earnings_item(symbol="ZZZ", scheduled_at_iso="2026-04-27T08:00:00+00:00")
    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        lookahead_items_by_segment={US_EQUITY: (later, earlier)},
        now_utc=now_utc,
    )
    assert "AAA 실적 D-0" in summary
    assert "ZZZ 실적" not in summary


def test_imminent_tag_uses_fomc_label_for_calendar_source() -> None:
    """FOMC RSS rows get the 📅 icon and the title-derived label.

    Pin the exact truncated label substring so silent drift in
    ``_imminent_event_label`` (e.g. tweaking the ``title[:23] + "…"``
    budget or the leading-character handling) breaks this test instead
    of shipping a malformed Telegram preview.
    """
    from datetime import datetime

    briefings = _imminent_briefings()
    now_utc = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)
    fomc = _fomc_item(scheduled_at_iso="2026-04-27T18:00:00+00:00")
    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        lookahead_items_by_segment={US_EQUITY: (fomc,)},
        now_utc=now_utc,
    )
    assert "📅" in summary
    assert "D-2" in summary
    # The fixture title "FOMC press release — Federal Open Market Committee"
    # is longer than 24 chars, so the label is truncated to the first 23
    # characters with a trailing ellipsis. Pin both the leading title
    # substring and the exact truncated form to catch silent label drift.
    assert "FOMC press release" in summary
    assert "📅 FOMC press release — Fe… D-2" in summary


def test_no_lookahead_argument_means_no_tag() -> None:
    """Backward-compat: omitting the kwarg yields the historic line shape."""
    briefings = _imminent_briefings()
    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)
    assert "D-" not in summary


# ---------------------------------------------------------------------------
# u30 Step 2 — segment collapse + enabled_segments toggle
# ---------------------------------------------------------------------------


def _build_coverage(segment, status, *, item_count=0):  # type: ignore[no-untyped-def]
    from investo.briefing.segments import SegmentCoverage

    return SegmentCoverage(
        segment=segment,
        status=status,
        item_count=item_count,
        source_count=0 if not item_count else 1,
        categories=(),
        missing_categories=(),
    )


def test_insufficient_segment_collapses_to_single_line_when_coverage_supplied() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    coverage = {
        DOMESTIC_EQUITY: _build_coverage(DOMESTIC_EQUITY, "insufficient"),
        US_EQUITY: _build_coverage(US_EQUITY, "normal", item_count=10),
        CRYPTO: _build_coverage(CRYPTO, "normal", item_count=10),
    }

    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        coverage_by_segment=coverage,
    )

    # Domestic-equity collapses: single line with status badge + link, no
    # body/conclusion line below.
    expected_collapse = f"🇰🇷 *국내 증시* [부족] · [상세보기]({_SEGMENT_URLS[DOMESTIC_EQUITY]})"
    assert expected_collapse in summary
    assert f"🇰🇷 *국내 증시*\n[상세보기]({_SEGMENT_URLS[DOMESTIC_EQUITY]})\n" not in summary

    # Other segments keep the legacy 3-line block.
    assert f"🇺🇸 *미국 증시*\n[상세보기]({_SEGMENT_URLS[US_EQUITY]})\n미국 요약" in summary
    assert f"₿ *크립토*\n[상세보기]({_SEGMENT_URLS[CRYPTO]})\n크립토 요약" in summary


def test_partial_or_normal_segment_keeps_three_line_block() -> None:
    """``status != 'insufficient'`` must NOT trigger the collapse."""
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    coverage = {
        DOMESTIC_EQUITY: _build_coverage(DOMESTIC_EQUITY, "partial", item_count=2),
        US_EQUITY: _build_coverage(US_EQUITY, "normal", item_count=10),
        CRYPTO: _build_coverage(CRYPTO, "normal", item_count=10),
    }

    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        coverage_by_segment=coverage,
    )

    # No collapsed line for the partial segment.
    assert "🇰🇷 *국내 증시* [부족] · [상세보기]" not in summary
    assert f"🇰🇷 *국내 증시*\n[상세보기]({_SEGMENT_URLS[DOMESTIC_EQUITY]})\n" in summary


def test_enabled_segments_filter_drops_other_segments_from_body_and_footer() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }

    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        enabled_segments=(US_EQUITY, CRYPTO),
    )

    # Body + footer omit the disabled segment entirely.
    assert "국내 증시" not in summary
    assert "미국 증시" in summary
    assert "크립토" in summary
    assert _SEGMENT_URLS[DOMESTIC_EQUITY] not in summary


def test_enabled_segments_falls_back_to_all_when_filter_excludes_everything() -> None:
    """Operator misconfiguration must not produce a link-less alert."""
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }

    # ``enabled_segments=()`` filters everything out; expect fallback to
    # all published segments instead of an empty body/footer.
    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        enabled_segments=(),
    )

    for url in _SEGMENT_URLS.values():
        assert url in summary


def test_resolve_enabled_segments_reads_canonical_and_alias_tokens(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from investo.notifier.summary import resolve_enabled_segments

    monkeypatch.setenv("INVESTO_TELEGRAM_ENABLED_SEGMENTS", "us, crypto, unknown")
    assert resolve_enabled_segments() == (US_EQUITY, CRYPTO)


def test_resolve_enabled_segments_returns_none_for_empty_or_unset(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from investo.notifier.summary import resolve_enabled_segments

    monkeypatch.delenv("INVESTO_TELEGRAM_ENABLED_SEGMENTS", raising=False)
    assert resolve_enabled_segments() is None
    monkeypatch.setenv("INVESTO_TELEGRAM_ENABLED_SEGMENTS", "  ,  ")
    assert resolve_enabled_segments() is None


def test_resolve_enabled_segments_explicit_raw_overrides_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from investo.notifier.summary import resolve_enabled_segments

    monkeypatch.setenv("INVESTO_TELEGRAM_ENABLED_SEGMENTS", "us")
    assert resolve_enabled_segments("crypto") == (CRYPTO,)


def test_resolve_enabled_segments_preserves_canonical_order() -> None:
    from investo.notifier.summary import resolve_enabled_segments

    # Token order is irrelevant; output is canonical (domestic → us → crypto).
    assert resolve_enabled_segments("crypto, domestic-equity, us-equity") == (
        DOMESTIC_EQUITY,
        US_EQUITY,
        CRYPTO,
    )


# ---------------------------------------------------------------------------
# u30 Step 3 — action tag is preserved through the Telegram one-liner
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# u30 Step 4 — KST publish time + watchlist price suffix
# ---------------------------------------------------------------------------


def test_header_includes_kst_publish_time_and_previous_trading_day_label() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    # 2026-04-25T22:30Z → 2026-04-26T07:30 KST.
    now_utc = datetime(2026, 4, 25, 22, 30, tzinfo=UTC)
    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS, now_utc=now_utc)
    assert "🕐 KST 07:30 · 전 거래일: 2026-04-25" in summary


def test_publish_time_is_deterministic_when_now_utc_provided() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    now_utc = datetime(2026, 4, 25, 0, 0, tzinfo=UTC)
    out1 = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS, now_utc=now_utc)
    out2 = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS, now_utc=now_utc)
    assert out1 == out2


def test_watchlist_match_gets_price_suffix_when_price_item_available() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    briefings[US_EQUITY] = briefings[US_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 미국 증시 시황\n\n"
                "> **오늘의 결론**: 반도체 실적을 확인합니다.\n"
                "> **내 관심 자산 영향**: 1건 확인 — NVDA: NVDA rallies after earnings\n\n"
                + briefings[US_EQUITY].rendered_markdown
            )
        }
    )
    price_items = (
        _price_item(
            source_name="yfinance-price",
            title="NVDA price",
            raw_metadata={
                "ticker": "NVDA",
                "close": "950.00",
                "prev_close": "920.00",
            },
        ),
    )

    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        price_items=price_items,
    )

    # ``+3.3%`` derived from (950 - 920) / 920 * 100.
    assert "관심: 1건 확인 — NVDA(+3.3%): NVDA rallies after earnings" in summary


def test_watchlist_match_falls_back_to_ticker_only_when_price_missing() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    briefings[US_EQUITY] = briefings[US_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 미국 증시 시황\n\n"
                "> **오늘의 결론**: 반도체 실적을 확인합니다.\n"
                "> **내 관심 자산 영향**: 1건 확인 — NVDA: NVDA rallies after earnings\n\n"
                + briefings[US_EQUITY].rendered_markdown
            )
        }
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    # No price suffix because no price_items were provided.
    assert "관심: 1건 확인 — NVDA: NVDA rallies after earnings" in summary
    assert "NVDA(" not in summary


def test_watchlist_match_decoration_skips_unmatched_terms() -> None:
    """Multi-match watchlist line: each term decorated independently."""
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    briefings[US_EQUITY] = briefings[US_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 미국 증시 시황\n\n"
                "> **오늘의 결론**: 결론입니다.\n"
                "> **내 관심 자산 영향**: 2건 확인 — NVDA: news A; AAPL: news B\n\n"
                + briefings[US_EQUITY].rendered_markdown
            )
        }
    )
    price_items = (
        _price_item(
            source_name="yfinance-price",
            title="NVDA price",
            raw_metadata={"ticker": "NVDA", "pct_change": "1.20"},
        ),
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS, price_items=price_items)

    assert "NVDA(+1.2%): news A" in summary
    # AAPL has no price item, stays ticker-only.
    assert "AAPL: news B" in summary
    assert "AAPL(" not in summary


def test_action_tag_is_preserved_in_telegram_one_liner() -> None:
    """The conclusion's terminal closed-set tag survives extraction.

    The notifier reads the rendered ``> **오늘의 결론**:`` line and
    cleans markdown punctuation. The bracketed tag must NOT be stripped
    — readers rely on it as the day's stance signal.
    """
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="국내 요약"),
        US_EQUITY: _build_briefing(market_summary="미국 요약"),
        CRYPTO: _build_briefing(market_summary="크립토 요약"),
    }
    briefings[US_EQUITY] = briefings[US_EQUITY].model_copy(
        update={
            "rendered_markdown": (
                "# 2026-04-25 미국 증시 시황\n\n"
                "> **오늘의 결론**: 반도체 실적 카탈리스트가 진행 중입니다. [강세]\n\n"
                + briefings[US_EQUITY].rendered_markdown
            )
        }
    )

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "[강세]" in summary
    # The closed-set tag should appear right at the end of the conclusion
    # line — adjacent to the "기간 진행 중입니다." sentence.
    assert "진행 중입니다. [강세]" in summary


# ---------------------------------------------------------------------------
# u43 / DEBT-067 M1 — clock-explicit contract
# ---------------------------------------------------------------------------


def test_lookahead_items_supplied_without_now_utc_raises_value_error() -> None:
    """When the caller supplies ``lookahead_items_by_segment`` it must
    also pass ``now_utc`` explicitly. The notifier never reads
    ``datetime.now(UTC)`` for the imminent-tag selector — the
    orchestrator owns the clock so test fixtures see deterministic
    output. Regression: a refactor that re-introduces the implicit
    fallback on the imminent-tag path silently breaks every D-N
    fixture in this file.
    """
    briefings = _imminent_briefings()
    nvda = _earnings_item(symbol="NVDA", scheduled_at_iso="2026-04-27T20:00:00+00:00")

    with pytest.raises(ValueError, match="now_utc required"):
        build_segmented_summary(
            briefings,
            site_urls=_SEGMENT_URLS,
            lookahead_items_by_segment={US_EQUITY: (nvda,)},
            now_utc=None,
        )


def test_now_utc_supplied_without_lookahead_items_is_legal() -> None:
    """The inverse direction is **not** an error: callers may pass
    ``now_utc`` for header-publish-time rendering even without a
    lookahead bucket. The contract only fires on the asymmetric
    ``lookahead_items=set, now_utc=None`` shape.
    """
    briefings = _imminent_briefings()
    now_utc = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)

    summary = build_segmented_summary(
        briefings,
        site_urls=_SEGMENT_URLS,
        now_utc=now_utc,
    )
    assert summary  # rendered without raising
