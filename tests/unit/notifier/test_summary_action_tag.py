"""u56 — Telegram summary surface carries the new observation ActionTag set.

The notifier surfaces ``market_summary`` verbatim; we therefore verify
that the new tag set survives round-trip through ``build_summary`` and
that legacy tags from pre-cutover archive content still surface
unchanged (the alias map is producer-side only).
"""

from __future__ import annotations

from datetime import date

import pytest

from investo.briefing.disclaimer import DISCLAIMER
from investo.models import Briefing
from investo.notifier.summary import build_summary


def _build_briefing(market_summary: str) -> Briefing:
    return Briefing(
        target_date=date(2026, 5, 13),
        market_summary=market_summary,
        key_issues="핵심 이슈",
        sector_flow="섹터",
        indicators_events="지표",
        notable_tickers="종목",
        today_watch="관전",
        disclaimer=DISCLAIMER,
        rendered_markdown=(
            "# 2026-05-13 미국 증시 시황\n\n"
            f"> **오늘의 결론**: {market_summary}\n\n"
            "## ① 요약\n\n본문\n\n"
            f"{DISCLAIMER}\n"
        ),
    )


@pytest.mark.parametrize(
    "tag",
    ["[상승 관찰]", "[하락 관찰]", "[혼재]", "[변동성 확대]", "[데이터부족]"],
)
def test_new_observation_tag_surfaces_in_summary(tag: str) -> None:
    briefing = _build_briefing(f"오늘은 흐름이 명확합니다. {tag}")
    out = build_summary(briefing, site_url="https://example.com/x.md")
    assert tag in out


def test_legacy_stance_tag_from_archive_still_surfaces() -> None:
    """When the digest re-reads a pre-cutover archive briefing, the
    legacy stance tag is part of that file's prose and should appear
    in the summary verbatim — the alias map is producer-side only."""
    briefing = _build_briefing("어제 흐름 연장입니다. [강세]")
    out = build_summary(briefing, site_url="https://example.com/x.md")
    assert "[강세]" in out
