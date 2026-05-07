"""Tests for ``investo.notifier.summary.build_summary`` (FR-004).

Pins UTF-16-aware truncation, footer preservation, and the
defense-in-depth round-trip through ``BriefingNotification``'s
4096-unit validator.
"""

from __future__ import annotations

from datetime import date

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.briefing.segments import CRYPTO, DOMESTIC_EQUITY, US_EQUITY
from investo.models import Briefing, BriefingNotification
from investo.notifier.summary import (
    DEFAULT_MAX_UNITS,
    _utf16_truncate,
    _utf16_units,
    build_segmented_summary,
    build_summary,
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
    assert summary.endswith(f"\n\n상세보기: {_SITE_URL}")
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

    assert summary.endswith(f"\n\n상세보기: {_SITE_URL}")
    assert _SITE_URL in summary


def test_build_segmented_summary_includes_all_labels_and_urls() -> None:
    briefings = {
        DOMESTIC_EQUITY: _build_briefing(market_summary="코스피 요약"),
        US_EQUITY: _build_briefing(market_summary="S&P 500 요약"),
        CRYPTO: _build_briefing(market_summary="Bitcoin 요약"),
    }

    summary = build_segmented_summary(briefings, site_urls=_SEGMENT_URLS)

    assert "국내 증시: 코스피 요약" in summary
    assert "미국 증시: S&P 500 요약" in summary
    assert "크립토: Bitcoin 요약" in summary
    for url in _SEGMENT_URLS.values():
        assert url in summary


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

    assert "국내 증시: 국내 증시는 데이터 부족입니다." in summary
    assert "국내 증시: 1." not in summary
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

    assert "크립토: 부분 — Bitcoin 가격 근거만 확인됐습니다." in summary
    assert "수집 1건" not in summary


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
    assert f"…\n\n상세보기: {_SITE_URL}" in summary


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
