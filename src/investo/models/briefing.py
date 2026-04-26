"""Briefing model produced by the briefing generator.

The Briefing Generator (US-002, US-009) produces a ``Briefing`` after the
two-stage Claude Code CLI prompt and the auto-appended disclaimer. The
Publisher (US-003, US-006) writes ``rendered_markdown`` to
``archive/YYYY/MM/YYYY-MM-DD.md`` and verifies disclaimer presence
(NFR-004) before commit. The BriefingPublisher (FR-004, US-004) packs
a short summary into ``BriefingNotification`` for the Telegram channel.

Reference: aidlc-docs/inception/application-design/component-methods.md
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from investo.models._validators import reject_blank_preserve

# Telegram's hard limit for ``sendMessage`` text payload, measured in
# UTF-16 code units (the unit Telegram's API uses for length checks).
TELEGRAM_MESSAGE_LIMIT = 4096


class Briefing(BaseModel):
    """Daily Korean-language market briefing in 7 fixed sections.

    The seven section strings are individually accessible (for templating
    or alternate renderings) and ``rendered_markdown`` is the final
    stitched markdown — the exact bytes written to the archive and
    rendered by mkdocs. ``disclaimer`` is auto-appended by
    ``briefing.append_disclaimer`` and re-verified by
    ``publisher.verify_disclaimer`` immediately before publish (NFR-004).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_date: date
    market_summary: str = Field(min_length=1)  # ① 요약
    key_issues: str = Field(min_length=1)  # ② 전일 핵심 이슈
    sector_flow: str = Field(min_length=1)  # ③ 섹터/수급 동향
    indicators_events: str = Field(min_length=1)  # ④ 지표·이벤트
    notable_tickers: str = Field(min_length=1)  # ⑤ 주요 종목
    today_watch: str = Field(min_length=1)  # ⑥ 오늘의 관전 포인트
    disclaimer: str = Field(min_length=1)  # ⑦ 면책조항
    rendered_markdown: str = Field(min_length=1)

    @field_validator(
        "market_summary",
        "key_issues",
        "sector_flow",
        "indicators_events",
        "notable_tickers",
        "today_watch",
        "disclaimer",
        "rendered_markdown",
    )
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # ``min_length=1`` rejects ``""`` but not whitespace-only content.
        # Markdown sections legitimately carry leading/trailing newlines
        # so we preserve the value rather than stripping it.
        return reject_blank_preserve(value)


class BriefingNotification(BaseModel):
    """Public Telegram channel payload (FR-004, US-004).

    The 4096-unit limit comes from Telegram's ``sendMessage`` text-field
    cap, **counted in UTF-16 code units** — non-BMP characters such as
    common market emoji (📈, 📉, 🇰🇷) consume 2 units per code point, so
    a Python-char count is unsafe. The validator below enforces the
    correct contract; the BriefingPublisher must truncate or summarize
    beyond that. The site URL points to the archived markdown (full
    briefing).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_date: date
    summary_text: str = Field(min_length=1)
    site_url: HttpUrl

    @field_validator("summary_text")
    @classmethod
    def _validate_summary_text(cls, value: str) -> str:
        value = reject_blank_preserve(value)
        # Telegram counts text length in UTF-16 code units. Encoding to
        # ``utf-16-le`` gives 2 bytes per code unit, so dividing by 2
        # yields the count Telegram will see.
        utf16_units = len(value.encode("utf-16-le")) // 2
        if utf16_units > TELEGRAM_MESSAGE_LIMIT:
            raise ValueError(
                f"summary_text is {utf16_units} UTF-16 code units, "
                f"exceeds Telegram's {TELEGRAM_MESSAGE_LIMIT}-unit limit"
            )
        return value
