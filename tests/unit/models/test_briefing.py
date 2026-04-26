"""Unit tests for ``investo.models.briefing`` (Briefing + BriefingNotification)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from investo.models.briefing import (
    TELEGRAM_MESSAGE_LIMIT,
    Briefing,
    BriefingNotification,
)

_BRIEFING_FIELDS = (
    "market_summary",
    "key_issues",
    "sector_flow",
    "indicators_events",
    "notable_tickers",
    "today_watch",
    "disclaimer",
    "rendered_markdown",
)


def _briefing_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "target_date": date(2026, 4, 27),
        "market_summary": "summary",
        "key_issues": "issues",
        "sector_flow": "sector",
        "indicators_events": "indicators",
        "notable_tickers": "tickers",
        "today_watch": "watch",
        "disclaimer": "Not investment advice.",
        "rendered_markdown": "# Briefing\n\nbody\n\nNot investment advice.",
    }
    base.update(overrides)
    return base


def _notif_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "target_date": date(2026, 4, 27),
        "summary_text": "short summary",
        "site_url": "https://example.com/2026-04-27",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Briefing — valid construction
# ---------------------------------------------------------------------------


def test_valid_briefing() -> None:
    b = Briefing(**_briefing_kwargs())
    assert b.target_date == date(2026, 4, 27)
    assert b.disclaimer == "Not investment advice."
    assert "Briefing" in b.rendered_markdown


def test_briefing_preserves_section_whitespace() -> None:
    # Markdown sections legitimately end with newlines.
    b = Briefing(**_briefing_kwargs(market_summary="요약\n\n"))
    assert b.market_summary == "요약\n\n"


# ---------------------------------------------------------------------------
# Briefing — blank rejection on every required section
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", _BRIEFING_FIELDS)
def test_empty_section_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        Briefing(**_briefing_kwargs(**{field: ""}))


@pytest.mark.parametrize("field", _BRIEFING_FIELDS)
def test_whitespace_only_section_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        Briefing(**_briefing_kwargs(**{field: "   \n  "}))


# ---------------------------------------------------------------------------
# Briefing — frozen + extra field
# ---------------------------------------------------------------------------


def test_briefing_frozen() -> None:
    b = Briefing(**_briefing_kwargs())
    with pytest.raises(ValidationError):
        b.market_summary = "different"  # type: ignore[misc]


def test_briefing_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        Briefing(**_briefing_kwargs(extra="x"))


# ---------------------------------------------------------------------------
# BriefingNotification — basics
# ---------------------------------------------------------------------------


def test_valid_briefing_notification() -> None:
    n = BriefingNotification(**_notif_kwargs())
    assert n.target_date == date(2026, 4, 27)
    assert n.summary_text == "short summary"
    assert str(n.site_url) == "https://example.com/2026-04-27"


def test_invalid_site_url_rejected() -> None:
    with pytest.raises(ValidationError):
        BriefingNotification(**_notif_kwargs(site_url="not-a-url"))


def test_briefing_notification_frozen() -> None:
    n = BriefingNotification(**_notif_kwargs())
    with pytest.raises(ValidationError):
        n.summary_text = "different"  # type: ignore[misc]


def test_briefing_notification_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        BriefingNotification(**_notif_kwargs(extra="x"))


def test_briefing_notification_blank_summary_rejected() -> None:
    with pytest.raises(ValidationError, match="non-whitespace"):
        BriefingNotification(**_notif_kwargs(summary_text="   "))


# ---------------------------------------------------------------------------
# BriefingNotification — UTF-16 length contract (H1 fix from review)
# ---------------------------------------------------------------------------


def test_summary_text_at_limit_accepted_ascii() -> None:
    BriefingNotification(**_notif_kwargs(summary_text="x" * TELEGRAM_MESSAGE_LIMIT))


def test_summary_text_one_over_limit_rejected_ascii() -> None:
    with pytest.raises(ValidationError, match="UTF-16"):
        BriefingNotification(**_notif_kwargs(summary_text="x" * (TELEGRAM_MESSAGE_LIMIT + 1)))


def test_summary_text_at_limit_accepted_korean_bmp() -> None:
    # BMP Korean characters (가): 1 code point = 1 UTF-16 unit
    BriefingNotification(**_notif_kwargs(summary_text="가" * TELEGRAM_MESSAGE_LIMIT))


def test_summary_text_emoji_boundary_accepted() -> None:
    # 📈 is U+1F4C8 (non-BMP) → 2 UTF-16 units. 2048 emoji = 4096 units.
    BriefingNotification(**_notif_kwargs(summary_text="📈" * (TELEGRAM_MESSAGE_LIMIT // 2)))


def test_summary_text_emoji_one_over_limit_rejected() -> None:
    # 2049 emoji = 4098 UTF-16 units → reject (would have passed under
    # naive Python char count of 2049 ≤ 4096).
    with pytest.raises(ValidationError, match="4098 UTF-16"):
        BriefingNotification(**_notif_kwargs(summary_text="📈" * (TELEGRAM_MESSAGE_LIMIT // 2 + 1)))


def test_summary_text_mixed_ascii_emoji_counts_correctly() -> None:
    # 4000 ASCII + 50 emoji = 4000 + 100 = 4100 UTF-16 → reject
    with pytest.raises(ValidationError, match="4100 UTF-16"):
        BriefingNotification(**_notif_kwargs(summary_text="x" * 4000 + "📈" * 50))
