"""u67 — segment-specific prompt depth notes.

Pins that ``_render_segment_context`` injects:
* the domestic-equity depth note (KOSPI/KOSDAQ close + 원/달러 in §①,
  반도체/2차전지 sector narration in §③, overnight-US → KR-open bridge),
* the crypto forbidden-term note for crypto,
* nothing extra for us-equity.
"""

from __future__ import annotations

from investo.briefing.pipeline import _render_segment_context
from investo.briefing.prompts import (
    CRYPTO_FORBIDDEN_TERMS_NOTE,
    CRYPTO_UTC_FRAME_NOTE,
    DOMESTIC_DEPTH_NOTE,
    format_crypto_indicator_context,
)


def test_domestic_segment_carries_depth_note() -> None:
    rendered = _render_segment_context("domestic-equity", data_limited=False)
    assert DOMESTIC_DEPTH_NOTE in rendered
    # The three reader-facing asks are present.
    assert "원/달러" in rendered
    assert "반도체" in rendered and "2차전지" in rendered
    assert "전일 미국장" in rendered
    # Crypto note must not bleed into domestic.
    assert CRYPTO_FORBIDDEN_TERMS_NOTE not in rendered


def test_crypto_segment_keeps_forbidden_term_note() -> None:
    rendered = _render_segment_context("crypto", data_limited=False)
    assert CRYPTO_FORBIDDEN_TERMS_NOTE in rendered
    assert DOMESTIC_DEPTH_NOTE not in rendered


def test_u66_crypto_segment_carries_utc_frame_note() -> None:
    rendered = _render_segment_context("crypto", data_limited=False)
    assert CRYPTO_UTC_FRAME_NOTE in rendered
    assert "UTC 24h 기준" in rendered
    assert "전일 종가" in rendered  # appears in the "do not use" instruction


def test_u66_utc_frame_note_crypto_only() -> None:
    for seg in ("us-equity", "domestic-equity"):
        rendered = _render_segment_context(seg, data_limited=False)  # type: ignore[arg-type]
        assert CRYPTO_UTC_FRAME_NOTE not in rendered


def test_u66_indicator_context_formats_only_when_block_present() -> None:
    assert format_crypto_indicator_context("") == ""
    assert format_crypto_indicator_context("   \n  ") == ""
    out = format_crypto_indicator_context("## ⓪-A 크립토 지표\n| 지표 | 값 |\n")
    assert "값 발명 금지" in out
    assert "## ⓪-A 크립토 지표" in out


def test_us_segment_has_no_extra_note() -> None:
    rendered = _render_segment_context("us-equity", data_limited=False)
    assert DOMESTIC_DEPTH_NOTE not in rendered
    assert CRYPTO_FORBIDDEN_TERMS_NOTE not in rendered
    assert CRYPTO_UTC_FRAME_NOTE not in rendered
